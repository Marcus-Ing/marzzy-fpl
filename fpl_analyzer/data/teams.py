"""Premier League club models from bootstrap-static."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Team:
    id: int
    name: str
    short_name: str
    code: int


def parse_teams(bootstrap: dict[str, Any]) -> dict[int, Team]:
    teams: dict[int, Team] = {}
    for row in bootstrap.get("teams", []):
        team = Team(
            id=int(row["id"]),
            name=str(row["name"]),
            short_name=str(row["short_name"]),
            code=int(row["code"]),
        )
        teams[team.id] = team
    return teams
