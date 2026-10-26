"""Analysis engine — form, fixtures, score, captaincy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fpl_analyzer.analysis.captaincy import CaptaincyAdvice, suggest_captaincy
from fpl_analyzer.analysis.fixtures import fixtures_for_team
from fpl_analyzer.analysis.scoring import PlayerAnalysis, SCORE_WEIGHTS, analyze_player
from fpl_analyzer.api.fpl_api import FplApi
from fpl_analyzer.data.fixtures import parse_fixtures
from fpl_analyzer.data.players import parse_players
from fpl_analyzer.config import RULES
from fpl_analyzer.data.squad import TeamSquad, load_team_squad

DEFAULT_FIXTURE_HORIZON = RULES.default_fixture_horizon


@dataclass(slots=True)
class SquadAnalysis:
    squad: TeamSquad
    target_event: int
    for_next: bool
    gameweeks_played: int
    horizon: int
    players: list[PlayerAnalysis] = field(default_factory=list)
    captaincy: CaptaincyAdvice | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def ranked(self) -> list[PlayerAnalysis]:
        return sorted(self.players, key=lambda a: a.score, reverse=True)


def _resolve_target(
    bootstrap: dict[str, Any], squad: TeamSquad
) -> tuple[int, bool, int, list[str]]:
    notes: list[str] = []
    events = bootstrap.get("events") or []
    current = next((e for e in events if e.get("is_current")), None)
    nxt = next((e for e in events if e.get("is_next")), None)
    finished_count = sum(1 for e in events if e.get("finished"))

    if current and not current.get("finished") and nxt:
        target = int(nxt["id"])
        for_next = True
        notes.append(
            f"Gameweek {current['id']} is in progress — "
            f"recommendations target Gameweek {target}."
        )
    elif current and not current.get("finished"):
        target = int(current["id"])
        for_next = False
        notes.append(f"Recommendations target Gameweek {target}.")
    elif nxt:
        target = int(nxt["id"])
        for_next = True
        notes.append(f"Recommendations target Gameweek {target}.")
    else:
        target = squad.gameweek.id
        for_next = False
        notes.append(f"Recommendations target Gameweek {target}.")

    gameweeks_played = max(
        1,
        finished_count
        + (1 if current and not current.get("finished") else 0),
    )
    return target, for_next, gameweeks_played, notes


def analyze_squad(
    squad: TeamSquad,
    *,
    api: FplApi | None = None,
    horizon: int = DEFAULT_FIXTURE_HORIZON,
) -> SquadAnalysis:
    owns = api is None
    client = api or FplApi()
    try:
        bootstrap = client.bootstrap_static()
        players = parse_players(bootstrap)
        fixtures = parse_fixtures(client.fixtures())
        target, for_next, gws_played, notes = _resolve_target(bootstrap, squad)

        analyses: list[PlayerAnalysis] = []
        for sp in squad.players:
            player = players.get(sp.element_id)
            if player is None:
                continue
            outlook = fixtures_for_team(
                fixtures, sp.team_id, from_event=target, horizon=horizon
            )
            analyses.append(
                analyze_player(
                    sp,
                    player,
                    outlook,
                    gameweeks_played=gws_played,
                    target_event=target,
                    for_next=for_next,
                )
            )
        return SquadAnalysis(
            squad=squad,
            target_event=target,
            for_next=for_next,
            gameweeks_played=gws_played,
            horizon=horizon,
            players=analyses,
            captaincy=suggest_captaincy(analyses),
            notes=notes,
        )
    finally:
        if owns:
            client.close()


def analyze_team(
    team_id: int, *, horizon: int = DEFAULT_FIXTURE_HORIZON
) -> SquadAnalysis:
    with FplApi() as client:
        squad = load_team_squad(team_id, api=client)
        return analyze_squad(squad, api=client, horizon=horizon)


__all__ = [
    "DEFAULT_FIXTURE_HORIZON",
    "SCORE_WEIGHTS",
    "CaptaincyAdvice",
    "PlayerAnalysis",
    "SquadAnalysis",
    "analyze_squad",
    "analyze_team",
    "suggest_captaincy",
]
