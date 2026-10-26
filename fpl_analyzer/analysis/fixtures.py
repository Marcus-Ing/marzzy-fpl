"""Fixture difficulty outlook from official FDR."""

from __future__ import annotations

from dataclasses import dataclass

from fpl_analyzer.data.fixtures import Fixture


@dataclass(frozen=True, slots=True)
class UpcomingFixture:
    event: int
    opponent_team_id: int
    is_home: bool
    fdr: int

    @property
    def ease(self) -> int:
        return 6 - self.fdr if 1 <= self.fdr <= 5 else 0


@dataclass(frozen=True, slots=True)
class FixtureOutlook:
    team_id: int
    fixtures: tuple[UpcomingFixture, ...]
    avg_fdr: float
    avg_ease: float
    horizon: int

    @property
    def summary(self) -> str:
        if not self.fixtures:
            return "no fixtures"
        parts = []
        for fx in self.fixtures:
            side = "H" if fx.is_home else "A"
            parts.append(f"GW{fx.event}:{side}/FDR{fx.fdr}")
        return " ".join(parts)


def fixtures_for_team(
    fixtures: list[Fixture],
    team_id: int,
    *,
    from_event: int,
    horizon: int = 3,
) -> FixtureOutlook:
    end = from_event + horizon - 1
    upcoming: list[UpcomingFixture] = []
    for fx in fixtures:
        if fx.event is None or fx.finished:
            continue
        if fx.event < from_event or fx.event > end:
            continue
        if fx.team_h == team_id:
            upcoming.append(
                UpcomingFixture(
                    event=fx.event,
                    opponent_team_id=fx.team_a,
                    is_home=True,
                    fdr=fx.team_h_difficulty or 3,
                )
            )
        elif fx.team_a == team_id:
            upcoming.append(
                UpcomingFixture(
                    event=fx.event,
                    opponent_team_id=fx.team_h,
                    is_home=False,
                    fdr=fx.team_a_difficulty or 3,
                )
            )
    upcoming.sort(key=lambda u: (u.event, not u.is_home))
    if upcoming:
        avg_fdr = sum(u.fdr for u in upcoming) / len(upcoming)
        avg_ease = sum(u.ease for u in upcoming) / len(upcoming)
    else:
        avg_fdr, avg_ease = 3.0, 3.0
    return FixtureOutlook(
        team_id=team_id,
        fixtures=tuple(upcoming),
        avg_fdr=avg_fdr,
        avg_ease=avg_ease,
        horizon=horizon,
    )
