"""Transfer / XI optimiser. Chip timing remains stubbed."""

from __future__ import annotations

from dataclasses import dataclass, field

from fpl_analyzer.analysis import DEFAULT_FIXTURE_HORIZON, SquadAnalysis, analyze_squad
from fpl_analyzer.api.fpl_api import FplApi
from fpl_analyzer.data.fixtures import parse_fixtures
from fpl_analyzer.data.players import parse_players
from fpl_analyzer.data.squad import load_team_squad
from fpl_analyzer.data.teams import parse_teams
from fpl_analyzer.optimizer.candidates import ScoredPlayer, score_player_pool
from fpl_analyzer.optimizer.starting_xi import Lineup, select_starting_xi
from fpl_analyzer.optimizer.transfers import (
    HIT_POINTS,
    TransferPlan,
    TransferSearchResult,
    search_transfers,
)


@dataclass(slots=True)
class OptimizationResult:
    analysis: SquadAnalysis
    search: TransferSearchResult
    pool_size: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def recommendation(self) -> TransferPlan:
        return self.search.recommendation

    @property
    def lineup(self) -> Lineup:
        return self.search.recommendation.lineup


def optimize_team(
    team_id: int,
    *,
    horizon: int = DEFAULT_FIXTURE_HORIZON,
    max_transfers: int = 2,
) -> OptimizationResult:
    with FplApi() as client:
        squad = load_team_squad(team_id, api=client)
        analysis = analyze_squad(squad, api=client, horizon=horizon)
        bootstrap = client.bootstrap_static()
        players = parse_players(bootstrap)
        teams = parse_teams(bootstrap)
        fixtures = parse_fixtures(client.fixtures())
        pool = score_player_pool(
            players,
            teams,
            fixtures,
            target_event=analysis.target_event,
            for_next=analysis.for_next,
            gameweeks_played=analysis.gameweeks_played,
            horizon=horizon,
        )
        search = search_transfers(
            squad,
            pool,
            free_transfers=squad.free_transfers,
            max_transfers=max_transfers,
        )
        notes = list(analysis.notes) + list(search.notes)
        return OptimizationResult(
            analysis=analysis,
            search=search,
            pool_size=len(pool),
            notes=notes,
        )


__all__ = [
    "HIT_POINTS",
    "Lineup",
    "OptimizationResult",
    "ScoredPlayer",
    "TransferPlan",
    "TransferSearchResult",
    "optimize_team",
    "search_transfers",
    "select_starting_xi",
]
