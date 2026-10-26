"""Reconstruct a manager's 15-man squad, bank, prices, and free transfers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fpl_analyzer.api.fpl_api import FplApi, FplApiError
from fpl_analyzer.data.players import Player, Position, parse_players
from fpl_analyzer.data.teams import Team, parse_teams


@dataclass(frozen=True, slots=True)
class GameweekInfo:
    id: int
    name: str
    is_current: bool
    is_next: bool
    finished: bool
    deadline_time: str | None


@dataclass(frozen=True, slots=True)
class SquadPlayer:
    element_id: int
    web_name: str
    position: Position
    team_id: int
    club_short: str
    club_name: str
    squad_slot: int
    is_starter: bool
    is_captain: bool
    is_vice_captain: bool
    purchase_price: int
    selling_price: int
    now_cost: int

    @property
    def purchase_price_m(self) -> float:
        return self.purchase_price / 10.0

    @property
    def selling_price_m(self) -> float:
        return self.selling_price / 10.0

    @property
    def now_cost_m(self) -> float:
        return self.now_cost / 10.0


@dataclass(slots=True)
class TeamSquad:
    team_id: int
    team_name: str
    manager_name: str
    gameweek: GameweekInfo
    bank: int
    team_value: int
    free_transfers: int | None
    free_transfers_note: str
    players: list[SquadPlayer] = field(default_factory=list)
    active_chip: str | None = None
    event_transfers: int = 0
    event_transfers_cost: int = 0

    @property
    def bank_m(self) -> float:
        return self.bank / 10.0

    @property
    def team_value_m(self) -> float:
        return self.team_value / 10.0


def selling_price(purchase: int, now_cost: int) -> int:
    if now_cost >= purchase:
        return purchase + (now_cost - purchase) // 2
    return now_cost


def _current_gameweek(bootstrap: dict[str, Any]) -> GameweekInfo:
    events = bootstrap.get("events") or []
    current = next((e for e in events if e.get("is_current")), None)
    if current is None:
        current = next((e for e in events if e.get("is_next")), None)
    if current is None and events:
        current = events[-1]
    if current is None:
        raise FplApiError("No gameweek events in bootstrap-static")
    return GameweekInfo(
        id=int(current["id"]),
        name=str(current["name"]),
        is_current=bool(current.get("is_current")),
        is_next=bool(current.get("is_next")),
        finished=bool(current.get("finished")),
        deadline_time=current.get("deadline_time"),
    )


def _chip_events(history: dict[str, Any]) -> tuple[set[int], set[int]]:
    freehit: set[int] = set()
    wildcard: set[int] = set()
    for chip in history.get("chips") or []:
        name = str(chip.get("name", "")).lower()
        event = int(chip["event"])
        if name == "freehit":
            freehit.add(event)
        elif name == "wildcard":
            wildcard.add(event)
    return freehit, wildcard


def _purchase_prices(
    *,
    team_id: int,
    api: FplApi,
    entry: dict[str, Any],
    history: dict[str, Any],
    transfers: list[dict[str, Any]],
    players: dict[int, Player],
    current_event: int,
) -> dict[int, int]:
    freehit_events, _ = _chip_events(history)
    started = int(entry.get("started_event") or 1)

    try:
        opening = api.entry_picks(team_id, started)
    except FplApiError:
        opening = api.entry_picks(team_id, current_event)
        return {
            int(p["element"]): players[int(p["element"])].season_start_cost
            if int(p["element"]) in players
            else 0
            for p in opening["picks"]
        }

    owned: dict[int, int] = {}
    for pick in opening["picks"]:
        eid = int(pick["element"])
        player = players.get(eid)
        owned[eid] = player.season_start_cost if player else 0

    ordered = sorted(
        transfers, key=lambda t: (t.get("time") or "", t.get("element_in", 0))
    )
    for transfer in ordered:
        if int(transfer["event"]) in freehit_events:
            continue
        owned.pop(int(transfer["element_out"]), None)
        owned[int(transfer["element_in"])] = int(transfer["element_in_cost"])
    return owned


def estimate_free_transfers(history: dict[str, Any]) -> tuple[int | None, str]:
    from fpl_analyzer.config import RULES

    current_rows = history.get("current") or []
    if not current_rows:
        return None, "No history yet"

    freehit_events, wildcard_events = _chip_events(history)
    fts = RULES.free_transfers_per_gw
    for row in current_rows:
        event = int(row["event"])
        made = int(row.get("event_transfers") or 0)
        if event in freehit_events or event in wildcard_events:
            fts = RULES.free_transfers_per_gw
            continue
        remaining = max(0, fts - made)
        fts = min(
            RULES.max_free_transfers_bank,
            remaining + RULES.free_transfers_per_gw,
        )
    return (
        fts,
        f"Estimated from public history (max bank {RULES.max_free_transfers_bank})",
    )


def load_team_squad(team_id: int, api: FplApi | None = None) -> TeamSquad:
    owns_api = api is None
    client = api or FplApi()
    try:
        bootstrap = client.bootstrap_static()
        players = parse_players(bootstrap)
        teams = parse_teams(bootstrap)
        gw = _current_gameweek(bootstrap)

        entry = client.entry(team_id)
        history = client.entry_history(team_id)
        transfers = client.entry_transfers(team_id)

        event_id = int(entry.get("current_event") or gw.id)
        if entry.get("current_event"):
            event_id = int(entry["current_event"])
            for row in bootstrap.get("events") or []:
                if int(row["id"]) == event_id:
                    gw = GameweekInfo(
                        id=event_id,
                        name=str(row["name"]),
                        is_current=bool(row.get("is_current")),
                        is_next=bool(row.get("is_next")),
                        finished=bool(row.get("finished")),
                        deadline_time=row.get("deadline_time"),
                    )
                    break

        picks_payload = client.entry_picks(team_id, event_id)
        entry_history = picks_payload.get("entry_history") or {}
        purchase_by_id = _purchase_prices(
            team_id=team_id,
            api=client,
            entry=entry,
            history=history,
            transfers=transfers,
            players=players,
            current_event=event_id,
        )

        squad_players: list[SquadPlayer] = []
        for pick in picks_payload["picks"]:
            eid = int(pick["element"])
            player = players.get(eid)
            if player is None:
                raise FplApiError(f"Player {eid} missing from bootstrap")
            club = teams.get(player.team_id) or Team(
                id=player.team_id, name="?", short_name="?", code=0
            )
            purchase = purchase_by_id.get(eid, player.season_start_cost)
            now = player.now_cost
            slot = int(pick["position"])
            squad_players.append(
                SquadPlayer(
                    element_id=eid,
                    web_name=player.web_name,
                    position=player.element_type,
                    team_id=player.team_id,
                    club_short=club.short_name,
                    club_name=club.name,
                    squad_slot=slot,
                    is_starter=slot <= 11,
                    is_captain=bool(pick.get("is_captain")),
                    is_vice_captain=bool(pick.get("is_vice_captain")),
                    purchase_price=purchase,
                    selling_price=selling_price(purchase, now),
                    now_cost=now,
                )
            )

        squad_players.sort(key=lambda p: p.squad_slot)
        fts, fts_note = estimate_free_transfers(history)
        manager = " ".join(
            part
            for part in (
                entry.get("player_first_name") or "",
                entry.get("player_last_name") or "",
            )
            if part
        ).strip() or "Unknown"

        bank = int(
            entry_history.get("bank")
            if entry_history.get("bank") is not None
            else entry.get("last_deadline_bank") or 0
        )
        value = int(
            entry_history.get("value")
            if entry_history.get("value") is not None
            else entry.get("last_deadline_value") or 0
        )

        return TeamSquad(
            team_id=team_id,
            team_name=str(entry.get("name") or f"Team {team_id}"),
            manager_name=manager,
            gameweek=gw,
            bank=bank,
            team_value=value,
            free_transfers=fts,
            free_transfers_note=fts_note,
            players=squad_players,
            active_chip=picks_payload.get("active_chip"),
            event_transfers=int(entry_history.get("event_transfers") or 0),
            event_transfers_cost=int(entry_history.get("event_transfers_cost") or 0),
        )
    finally:
        if owns_api:
            client.close()
