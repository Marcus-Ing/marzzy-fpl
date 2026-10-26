"""Constrained 0–2 transfer search. Objective: Σ XI horizon xPts − hit cost."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Iterable

from fpl_analyzer.config import RULES
from fpl_analyzer.data.players import Position
from fpl_analyzer.data.squad import TeamSquad
from fpl_analyzer.optimizer.candidates import ScoredPlayer
from fpl_analyzer.optimizer.starting_xi import Lineup, select_starting_xi

# Back-compat aliases (avoid calling RULES.squad_counts at import time)
HIT_POINTS = RULES.hit_points
MAX_PER_CLUB = RULES.max_per_club
DEFAULT_OUT_CANDIDATES = RULES.transfer_out_candidates
DEFAULT_IN_PER_POS = RULES.transfer_in_per_pos


@dataclass(frozen=True, slots=True)
class TransferMove:
    player_out: ScoredPlayer
    player_in: ScoredPlayer
    sell_price: int
    buy_price: int

    @property
    def label(self) -> str:
        return (
            f"{self.player_out.web_name} ({self.player_out.club_short}) → "
            f"{self.player_in.web_name} ({self.player_in.club_short}) "
            f"[sell £{self.sell_price / 10:.1f}m / buy £{self.buy_price / 10:.1f}m]"
        )


@dataclass(slots=True)
class TransferPlan:
    moves: tuple[TransferMove, ...]
    free_transfers: int
    hits: int
    hit_cost: int
    bank_after: int
    lineup: Lineup
    objective: float  # XI xPts − hits
    gain_vs_roll: float  # objective delta
    xpts_gain_vs_roll: float
    notes: str = ""
    desirability_gain: float = 0.0

    @property
    def n_transfers(self) -> int:
        return len(self.moves)

    @property
    def is_roll(self) -> bool:
        return self.n_transfers == 0


@dataclass(slots=True)
class TransferSearchResult:
    free_transfers: int
    roll: TransferPlan
    best_one: TransferPlan | None
    best_two: TransferPlan | None
    recommendation: TransferPlan
    top_plans: list[TransferPlan] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _sell_price_map(squad: TeamSquad) -> dict[int, int]:
    return {p.element_id: p.selling_price for p in squad.players}


def _owned_scored(
    squad: TeamSquad, pool: dict[int, ScoredPlayer]
) -> list[ScoredPlayer]:
    return [pool[sp.element_id] for sp in squad.players]


def _club_ok(ids: Iterable[int], pool: dict[int, ScoredPlayer]) -> bool:
    counts: dict[int, int] = {}
    for eid in ids:
        tid = pool[eid].team_id
        counts[tid] = counts.get(tid, 0) + 1
        if counts[tid] > RULES.max_per_club:
            return False
    return True


def _out_candidates(owned: list[ScoredPlayer], limit: int) -> list[ScoredPlayer]:
    return sorted(
        owned, key=lambda p: (p.form.availability, p.xpts_horizon, p.score)
    )[:limit]


def _in_candidates(
    pool: dict[int, ScoredPlayer],
    *,
    position: Position,
    owned_ids: set[int],
    limit: int,
) -> list[ScoredPlayer]:
    market = [
        p
        for p in pool.values()
        if p.position == position
        and p.element_id not in owned_ids
        and p.form.status != "u"
    ]
    market.sort(key=lambda p: (p.xpts_horizon, p.score), reverse=True)
    return market[:limit]


def _hits(n_transfers: int, free_transfers: int) -> tuple[int, int]:
    return RULES.hit_cost(n_transfers, free_transfers)


def _evaluate_squad(
    squad_ids: list[int],
    pool: dict[int, ScoredPlayer],
    *,
    bank_after: int,
    moves: tuple[TransferMove, ...],
    free_transfers: int,
    roll_objective: float,
    roll_xi_xpts: float,
    roll_xi_score: float,
) -> TransferPlan | None:
    if bank_after < 0 or not _club_ok(squad_ids, pool):
        return None
    scored_squad = [pool[i] for i in squad_ids]
    for pos, need in RULES.squad_counts.items():
        if sum(1 for p in scored_squad if p.position == pos) != need:
            return None
    try:
        lineup = select_starting_xi(scored_squad)
    except ValueError:
        return None
    hits, hit_cost = _hits(len(moves), free_transfers)
    objective = lineup.xi_xpts - hit_cost
    return TransferPlan(
        moves=moves,
        free_transfers=free_transfers,
        hits=hits,
        hit_cost=hit_cost,
        bank_after=bank_after,
        lineup=lineup,
        objective=objective,
        gain_vs_roll=objective - roll_objective,
        xpts_gain_vs_roll=(lineup.xi_xpts - roll_xi_xpts) - hit_cost,
        desirability_gain=(lineup.xi_score - roll_xi_score),
    )


def search_transfers(
    squad: TeamSquad,
    pool: dict[int, ScoredPlayer],
    *,
    free_transfers: int | None = None,
    max_transfers: int = 2,
    out_limit: int = DEFAULT_OUT_CANDIDATES,
    in_per_pos: int = DEFAULT_IN_PER_POS,
) -> TransferSearchResult:
    notes: list[str] = []
    fts = free_transfers if free_transfers is not None else squad.free_transfers
    if fts is None:
        fts = 1
        notes.append("Free transfers unknown — assuming 1.")
    else:
        notes.append(f"Using {fts} free transfer(s).")

    sell_prices = _sell_price_map(squad)
    owned = _owned_scored(squad, pool)
    owned_ids = {p.element_id for p in owned}
    base_ids = [p.element_id for p in owned]
    bank = squad.bank

    roll_lineup = select_starting_xi(owned)
    roll_objective = roll_lineup.xi_xpts
    roll = TransferPlan(
        moves=(),
        free_transfers=fts,
        hits=0,
        hit_cost=0,
        bank_after=bank,
        lineup=roll_lineup,
        objective=roll_objective,
        gain_vs_roll=0.0,
        xpts_gain_vs_roll=0.0,
        notes="Roll FT — keep squad, optimise XI only.",
        desirability_gain=0.0,
    )

    outs = _out_candidates(owned, out_limit)
    plans: list[TransferPlan] = [roll]
    best_one: TransferPlan | None = None
    best_two: TransferPlan | None = None

    if max_transfers >= 1:
        for out_p in outs:
            sell = sell_prices[out_p.element_id]
            budget = bank + sell
            for in_p in _in_candidates(
                pool,
                position=out_p.position,
                owned_ids=owned_ids,
                limit=in_per_pos,
            ):
                if in_p.now_cost > budget:
                    continue
                if (
                    in_p.xpts_horizon <= out_p.xpts_horizon
                    and in_p.score <= out_p.score
                    and in_p.form.availability <= out_p.form.availability
                ):
                    continue
                new_ids = [
                    i for i in base_ids if i != out_p.element_id
                ] + [in_p.element_id]
                move = TransferMove(out_p, in_p, sell, in_p.now_cost)
                plan = _evaluate_squad(
                    new_ids,
                    pool,
                    bank_after=budget - in_p.now_cost,
                    moves=(move,),
                    free_transfers=fts,
                    roll_objective=roll_objective,
                    roll_xi_xpts=roll.lineup.xi_xpts,
                    roll_xi_score=roll.lineup.xi_score,
                )
                if plan is None:
                    continue
                plans.append(plan)
                if best_one is None or plan.objective > best_one.objective:
                    best_one = plan

    if max_transfers >= 2:
        for out_a, out_b in combinations(outs, 2):
            sell_a = sell_prices[out_a.element_id]
            sell_b = sell_prices[out_b.element_id]
            budget = bank + sell_a + sell_b
            cand_a = _in_candidates(
                pool,
                position=out_a.position,
                owned_ids=owned_ids,
                limit=in_per_pos,
            )
            cand_b = _in_candidates(
                pool,
                position=out_b.position,
                owned_ids=owned_ids,
                limit=in_per_pos,
            )
            for in_a in cand_a:
                for in_b in cand_b:
                    if in_a.element_id == in_b.element_id:
                        continue
                    buy_total = in_a.now_cost + in_b.now_cost
                    if buy_total > budget:
                        continue
                    if (
                        in_a.xpts_horizon + in_b.xpts_horizon
                        <= out_a.xpts_horizon + out_b.xpts_horizon
                    ):
                        continue
                    new_ids = [
                        i
                        for i in base_ids
                        if i not in (out_a.element_id, out_b.element_id)
                    ] + [in_a.element_id, in_b.element_id]
                    moves = (
                        TransferMove(out_a, in_a, sell_a, in_a.now_cost),
                        TransferMove(out_b, in_b, sell_b, in_b.now_cost),
                    )
                    plan = _evaluate_squad(
                        new_ids,
                        pool,
                        bank_after=budget - buy_total,
                        moves=moves,
                        free_transfers=fts,
                        roll_objective=roll_objective,
                        roll_xi_xpts=roll.lineup.xi_xpts,
                        roll_xi_score=roll.lineup.xi_score,
                    )
                    if plan is None:
                        continue
                    plans.append(plan)
                    if best_two is None or plan.objective > best_two.objective:
                        best_two = plan

    plans.sort(key=lambda p: p.objective, reverse=True)
    recommendation = plans[0]
    if recommendation.gain_vs_roll < 0.15:
        recommendation = roll
        notes.append("No transfer beats rolling on Σ xPts − hits; recommend roll.")
    elif recommendation.is_roll:
        notes.append("Best plan is roll FT.")
    else:
        notes.append(
            f"Recommend {recommendation.n_transfers} transfer(s): "
            f"ΔxPts {recommendation.xpts_gain_vs_roll:+.1f} after hits."
        )
    notes.append("Objective = Σ XI horizon xPts − 4×hits (not desirability alone).")

    return TransferSearchResult(
        free_transfers=fts,
        roll=roll,
        best_one=best_one,
        best_two=best_two,
        recommendation=recommendation,
        top_plans=plans[:8],
        notes=notes,
    )
