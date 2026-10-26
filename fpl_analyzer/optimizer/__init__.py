"""Transfer / XI / chips / multi-GW strategy optimiser."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fpl_analyzer.analysis import SquadAnalysis, analyze_squad
from fpl_analyzer.analysis.explain import ReasonBlock, explain_plan
from fpl_analyzer.api.fpl_api import FplApi
from fpl_analyzer.config import RULES
from fpl_analyzer.data.fixtures import parse_fixtures
from fpl_analyzer.data.players import parse_players
from fpl_analyzer.data.squad import load_team_squad
from fpl_analyzer.data.teams import parse_teams
from fpl_analyzer.optimizer.candidates import ScoredPlayer, score_player_pool
from fpl_analyzer.optimizer.chips import ChipAdvice, evaluate_chips
from fpl_analyzer.optimizer.starting_xi import Lineup, select_starting_xi
from fpl_analyzer.optimizer.strategy import StrategyComparison, compare_strategies
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
    strategy: StrategyComparison | None = None
    chips: list[ChipAdvice] = field(default_factory=list)
    why: ReasonBlock | None = None
    pool_size: int = 0
    notes: list[str] = field(default_factory=list)
    owned_scored: list[ScoredPlayer] = field(default_factory=list)

    @property
    def recommendation(self) -> TransferPlan:
        return self.search.recommendation

    @property
    def lineup(self) -> Lineup:
        return self.search.recommendation.lineup


def optimize_team(
    team_id: int,
    *,
    horizon: int | None = None,
    max_transfers: int = 2,
) -> OptimizationResult:
    hz = horizon or RULES.default_fixture_horizon
    with FplApi() as client:
        squad = load_team_squad(team_id, api=client)
        analysis = analyze_squad(squad, api=client, horizon=hz)
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
            horizon=hz,
            bootstrap=bootstrap,
        )
        search = search_transfers(
            squad,
            pool,
            free_transfers=squad.free_transfers,
            max_transfers=max_transfers,
        )
        owned = [pool[p.element_id] for p in squad.players if p.element_id in pool]
        strategy = compare_strategies(search, horizon=RULES.strategy_horizon)
        chips_used = set()
        # chips from history already applied in FT estimate; expose names via entry history chips if needed
        chips = evaluate_chips(
            owned,
            pool,
            roll_plan=search.roll,
            best_transfer_plan=search.recommendation,
            chips_used=chips_used,
        )
        why = explain_plan(search.recommendation)
        notes = list(analysis.notes) + list(search.notes)
        return OptimizationResult(
            analysis=analysis,
            search=search,
            strategy=strategy,
            chips=chips,
            why=why,
            pool_size=len(pool),
            notes=notes,
            owned_scored=owned,
        )


__all__ = [
    "HIT_POINTS",
    "ChipAdvice",
    "Lineup",
    "OptimizationResult",
    "ScoredPlayer",
    "StrategyComparison",
    "TransferPlan",
    "TransferSearchResult",
    "compare_strategies",
    "evaluate_chips",
    "optimize_team",
    "search_transfers",
    "select_starting_xi",
]
