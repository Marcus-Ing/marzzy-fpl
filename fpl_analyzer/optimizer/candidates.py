"""Score the full player pool with Phase 2 metrics for transfer search."""

from __future__ import annotations

from dataclasses import dataclass

from fpl_analyzer.analysis.fixtures import FixtureOutlook, fixtures_for_team
from fpl_analyzer.analysis.form import FormMetrics, compute_form_metrics
from fpl_analyzer.analysis.scoring import compute_score, project_xpts
from fpl_analyzer.data.fixtures import Fixture
from fpl_analyzer.data.players import Player, Position
from fpl_analyzer.data.teams import Team


@dataclass(frozen=True, slots=True)
class ScoredPlayer:
    player: Player
    club_short: str
    form: FormMetrics
    fixtures: FixtureOutlook
    ep_raw: float
    xpts: float
    score: float
    target_event: int

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


def score_player_pool(
    players: dict[int, Player],
    teams: dict[int, Team],
    fixtures: list[Fixture],
    *,
    target_event: int,
    for_next: bool,
    gameweeks_played: int,
    horizon: int,
) -> dict[int, ScoredPlayer]:
    scored: dict[int, ScoredPlayer] = {}
    outlook_cache: dict[int, FixtureOutlook] = {}
    for player in players.values():
        if player.team_id not in outlook_cache:
            outlook_cache[player.team_id] = fixtures_for_team(
                fixtures,
                player.team_id,
                from_event=target_event,
                horizon=horizon,
            )
        outlook = outlook_cache[player.team_id]
        form = compute_form_metrics(
            player, gameweeks_played=gameweeks_played, for_next=for_next
        )
        ep_raw, xpts = project_xpts(player, form, for_next=for_next)
        score, _ = compute_score(form, outlook, xpts, player.element_type)
        club = teams.get(player.team_id)
        scored[player.id] = ScoredPlayer(
            player=player,
            club_short=club.short_name if club else "?",
            form=form,
            fixtures=outlook,
            ep_raw=ep_raw,
            xpts=xpts,
            score=score,
            target_event=target_event,
        )
    return scored
