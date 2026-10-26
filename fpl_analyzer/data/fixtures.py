"""Fixture models from the fixtures endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Fixture:
    id: int
    event: int | None
    team_h: int
    team_a: int
    team_h_difficulty: int
    team_a_difficulty: int
    kickoff_time: str | None
    finished: bool
    started: bool


def parse_fixtures(rows: list[dict[str, Any]]) -> list[Fixture]:
    fixtures: list[Fixture] = []
    for row in rows:
        fixtures.append(
            Fixture(
                id=int(row["id"]),
                event=int(row["event"]) if row.get("event") is not None else None,
                team_h=int(row["team_h"]),
                team_a=int(row["team_a"]),
                team_h_difficulty=int(row.get("team_h_difficulty") or 0),
                team_a_difficulty=int(row.get("team_a_difficulty") or 0),
                kickoff_time=row.get("kickoff_time"),
                finished=bool(row.get("finished")),
                started=bool(row.get("started")),
            )
        )
    return fixtures
