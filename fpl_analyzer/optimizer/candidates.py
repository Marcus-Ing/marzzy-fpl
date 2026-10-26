"""Score the full player pool with minutes, opponent strength, and multi-GW xPts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fpl_analyzer.analysis.fixtures import FixtureOutlook, fixtures_for_team
from fpl_analyzer.analysis.form import FormMetrics, compute_form_metrics
from fpl_analyzer.analysis.minutes import MinutesProjection, project_minutes
from fpl_analyzer.analysis.opponent import (
    TeamStrength,
    upcoming_strengths,
    parse_team_strengths,
)
from fpl_analyzer.analysis.scoring import compute_score, project_xpts
from fpl_analyzer.analysis.xpts import HorizonXPts, project_horizon_xpts, risk_score
from fpl_analyzer.config import RULES
from fpl_analyzer.data.fixtures import Fixture
from fpl_analyzer.data.players import Player, Position
from fpl_analyzer.data.teams import Team


@dataclass(frozen=True, slots=True)
class ScoredPlayer:
    player: Player
    club_short: str
    form: FormMetrics
    fixtures: FixtureOutlook
    minutes: MinutesProjection
    horizon_xpts: HorizonXPts
    ep_raw: float
    xpts: float  # next single-GW adjusted ep (legacy/compat)
    score: float  # desirability
    risk: float
    target_event: int
    horizon: int

    @property
    def element_id(self) -> int:
        return self.player.id

    @property
    def position(self) -> Position:
        return self.player.element_type

    @property
    def team_id(self) -> int:
        return self.player.team_id

    @property
    def web_name(self) -> str:
        return self.player.web_name

    @property
    def now_cost(self) -> int:
        return self.player.now_cost

    @property
    def p_start(self) -> float:
        return self.minutes.p_start

    @property
    def xmins(self) -> float:
        return self.minutes.xmins

    @property
    def xpts_horizon(self) -> float:
        return self.horizon_xpts.total

    @property
    def minutes_notes(self) -> tuple[str, ...]:
        return self.minutes.notes


def score_player_pool(
    players: dict[int, Player],
    teams: dict[int, Team],
    fixtures: list[Fixture],
    *,
    target_event: int,
    for_next: bool,
    gameweeks_played: int,
    horizon: int,
    bootstrap: dict[str, Any] | None = None,
) -> dict[int, ScoredPlayer]:
    strengths: dict[int, TeamStrength] = (
        parse_team_strengths(bootstrap) if bootstrap else {}
    )
    scored: dict[int, ScoredPlayer] = {}
    outlook_cache: dict[int, FixtureOutlook] = {}
    strength_cache: dict[int, list] = {}

    for player in players.values():
        if player.team_id not in outlook_cache:
            outlook_cache[player.team_id] = fixtures_for_team(
                fixtures,
                player.team_id,
                from_event=target_event,
                horizon=horizon,
            )
            strength_cache[player.team_id] = upcoming_strengths(
                fixtures,
                player.team_id,
                strengths,
                from_event=target_event,
                horizon=horizon,
            )
        outlook = outlook_cache[player.team_id]
        fx_strengths = strength_cache[player.team_id]
        form = compute_form_metrics(
            player, gameweeks_played=gameweeks_played, for_next=for_next
        )
        minutes = project_minutes(
            player,
            gameweeks_played=gameweeks_played,
            availability=form.availability,
            fixtures_in_horizon=len(fx_strengths) or len(outlook.fixtures),
        )
        ep_raw, xpts = project_xpts(player, form, for_next=for_next)
        # Prefer projected next-GW from horizon model when fixtures exist
        if fx_strengths:
            hz = project_horizon_xpts(player, minutes, fx_strengths)
            if hz.by_event:
                xpts = hz.by_event[0].xpts
        else:
            hz = project_horizon_xpts(player, minutes, [])
        desirability, _ = compute_score(
            form, outlook, xpts, player.element_type
        )
        risk = risk_score(
            minutes,
            availability=form.availability,
            ownership=player.selected_by_percent,
        )
        club = teams.get(player.team_id)
        scored[player.id] = ScoredPlayer(
            player=player,
            club_short=club.short_name if club else "?",
            form=form,
            fixtures=outlook,
            minutes=minutes,
            horizon_xpts=hz,
            ep_raw=ep_raw,
            xpts=xpts,
            score=desirability,
            risk=risk,
            target_event=target_event,
            horizon=horizon,
        )
    return scored
