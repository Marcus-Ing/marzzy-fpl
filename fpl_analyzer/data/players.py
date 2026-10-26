"""Player models from bootstrap-static."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class Position(IntEnum):
    GKP = 1
    DEF = 2
    MID = 3
    FWD = 4

    @property
    def short_name(self) -> str:
        return self.name


def _float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class Player:
    id: int
    web_name: str
    first_name: str
    second_name: str
    team_id: int
    element_type: Position
    now_cost: int
    cost_change_start: int
    status: str
    news: str
    form: float
    points_per_game: float
    total_points: int
    minutes: int
    starts: int
    expected_goals: float
    expected_assists: float
    expected_goal_involvements: float
    ep_this: float
    ep_next: float
    chance_of_playing_this_round: int | None
    chance_of_playing_next_round: int | None
    defensive_contribution: int
    selected_by_percent: float

    @property
    def season_start_cost(self) -> int:
        return self.now_cost - self.cost_change_start

    @property
    def now_cost_m(self) -> float:
        return self.now_cost / 10.0


def parse_players(bootstrap: dict[str, Any]) -> dict[int, Player]:
    players: dict[int, Player] = {}
    for row in bootstrap.get("elements", []):
        player = Player(
            id=int(row["id"]),
            web_name=str(row["web_name"]),
            first_name=str(row["first_name"]),
            second_name=str(row["second_name"]),
            team_id=int(row["team"]),
            element_type=Position(int(row["element_type"])),
            now_cost=int(row["now_cost"]),
            cost_change_start=int(row["cost_change_start"]),
            status=str(row.get("status", "")),
            news=str(row.get("news") or ""),
            form=_float(row.get("form")),
            points_per_game=_float(row.get("points_per_game")),
            total_points=int(row.get("total_points") or 0),
            minutes=int(row.get("minutes") or 0),
            starts=int(row.get("starts") or 0),
            expected_goals=_float(row.get("expected_goals")),
            expected_assists=_float(row.get("expected_assists")),
            expected_goal_involvements=_float(
                row.get("expected_goal_involvements")
            ),
            ep_this=_float(row.get("ep_this")),
            ep_next=_float(row.get("ep_next")),
            chance_of_playing_this_round=_optional_int(
                row.get("chance_of_playing_this_round")
            ),
            chance_of_playing_next_round=_optional_int(
                row.get("chance_of_playing_next_round")
            ),
            defensive_contribution=int(row.get("defensive_contribution") or 0),
            selected_by_percent=_float(row.get("selected_by_percent")),
        )
        players[player.id] = player
    return players
