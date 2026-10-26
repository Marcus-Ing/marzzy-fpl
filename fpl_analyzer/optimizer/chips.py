"""Chip evaluators — WC / FH / BB / TC using season rules + horizon xPts (FPL-16)."""

from __future__ import annotations

from dataclasses import dataclass

from fpl_analyzer.config import RULES
from fpl_analyzer.data.players import Position
from fpl_analyzer.optimizer.candidates import ScoredPlayer
from fpl_analyzer.optimizer.starting_xi import select_starting_xi
from fpl_analyzer.optimizer.transfers import TransferPlan


@dataclass(frozen=True, slots=True)
class ChipAdvice:
    name: str
    label: str
    worth_considering: bool
    estimated_gain: float
    rationale: str


def _xi_xpts(squad: list[ScoredPlayer]) -> float:
    try:
        return select_starting_xi(squad).xi_xpts
    except ValueError:
        return 0.0


def evaluate_chips(
    owned: list[ScoredPlayer],
    pool: dict[int, ScoredPlayer],
    *,
    roll_plan: TransferPlan,
    best_transfer_plan: TransferPlan,
    chips_used: set[str] | None = None,
) -> list[ChipAdvice]:
    """
    Simple V1 chip heuristics (rules, not ML):

    - Triple Captain: 3× captain xPts − 1× captain xPts vs normal C
      (= +2 × captain next-GW / per-GW avg)
    - Bench Boost: sum of bench horizon xPts (proxy for boosted week)
    - Free Hit: top-11 pool by xPts for one week vs current XI (same positions rough)
    - Wildcard: top-15 constrained rebuild value vs current over horizon − opportunity
    """
    used = {c.lower() for c in (chips_used or set())}
    lu = roll_plan.lineup
    advice: list[ChipAdvice] = []

    # Triple Captain
    if RULES.chip_3xc not in used:
        cap = lu.captain
        # Extra 2× of one-GW average
        per_gw = cap.xpts_horizon / max(1, cap.horizon)
        gain = 2.0 * per_gw
        advice.append(
            ChipAdvice(
                name=RULES.chip_3xc,
                label="Triple Captain",
                worth_considering=gain >= 8.0 and cap.p_start >= 0.8,
                estimated_gain=gain,
                rationale=(
                    f"TC on {cap.web_name}: ~+{gain:.1f} pts vs normal captain "
                    f"(2× their ~{per_gw:.1f} xPts/GW). Prefer a nailed premium."
                ),
            )
        )

    # Bench Boost
    if RULES.chip_bboost not in used:
        bench_pts = sum(p.xpts_horizon for p in lu.bench)
        # Scale to one strong week ~ avg
        one_week = bench_pts / max(1, (lu.bench[0].horizon if lu.bench else 1))
        advice.append(
            ChipAdvice(
                name=RULES.chip_bboost,
                label="Bench Boost",
                worth_considering=one_week >= 12.0,
                estimated_gain=one_week,
                rationale=(
                    f"Bench horizon xPts {bench_pts:.1f} "
                    f"(~{one_week:.1f}/GW). BB shines with 4 playing bench assets."
                ),
            )
        )

    # Free Hit — approximate best XI from entire pool by xPts (formation-agnostic top)
    if RULES.chip_freehit not in used:
        by_pos = {1: [], 2: [], 3: [], 4: []}
        for p in pool.values():
            if p.form.availability < 0.5:
                continue
            by_pos[int(p.position)].append(p)
        for k in by_pos:
            by_pos[k].sort(key=lambda x: x.xpts_horizon, reverse=True)
        # Build 1-3-4-3 dream XI
        dream: list[ScoredPlayer] = []
        if by_pos[1]:
            dream.append(by_pos[1][0])
        dream.extend(by_pos[2][:3])
        dream.extend(by_pos[3][:4])
        dream.extend(by_pos[4][:3])
        dream_pts = sum(p.xpts_horizon for p in dream)
        # Scale dream to one GW
        hz = dream[0].horizon if dream else 1
        fh_gain = dream_pts / max(1, hz) - (lu.xi_xpts / max(1, hz))
        advice.append(
            ChipAdvice(
                name=RULES.chip_freehit,
                label="Free Hit",
                worth_considering=fh_gain >= 15.0,
                estimated_gain=fh_gain,
                rationale=(
                    f"One-week dream XI vs current ≈ {fh_gain:+.1f} xPts. "
                    "Use on blank/double weeks or when half the squad is out."
                ),
            )
        )

    # Wildcard — compare unconstrained top-15 value vs current + best transfers
    if RULES.chip_wildcard not in used:
        # Cheap proxy: top N per position by xPts/cost with 3/club ignored lightly
        picks: list[ScoredPlayer] = []
        club_n: dict[int, int] = {}
        for pos in (Position.GKP, Position.DEF, Position.MID, Position.FWD):
            need = RULES.squad_counts[pos]
            for p in sorted(
                (x for x in pool.values() if x.position == pos),
                key=lambda x: x.xpts_horizon / max(4.0, x.now_cost / 10),
                reverse=True,
            ):
                if club_n.get(p.team_id, 0) >= RULES.max_per_club:
                    continue
                picks.append(p)
                club_n[p.team_id] = club_n.get(p.team_id, 0) + 1
                if sum(1 for x in picks if x.position == pos) >= need:
                    break
        try:
            wc_xi = select_starting_xi(picks) if len(picks) == RULES.squad_size else None
        except ValueError:
            wc_xi = None
        wc_pts = wc_xi.xi_xpts if wc_xi else roll_plan.lineup.xi_xpts
        transfer_pts = best_transfer_plan.lineup.xi_xpts - best_transfer_plan.hit_cost
        wc_gain = wc_pts - max(roll_plan.lineup.xi_xpts, transfer_pts)
        advice.append(
            ChipAdvice(
                name=RULES.chip_wildcard,
                label="Wildcard",
                worth_considering=wc_gain >= 8.0,
                estimated_gain=wc_gain,
                rationale=(
                    f"Wildcard rebuild XI xPts {wc_pts:.1f} vs best normal plan "
                    f"{max(roll_plan.lineup.xi_xpts, transfer_pts):.1f} "
                    f"(Δ {wc_gain:+.1f} over horizon). "
                    "Play when several fires or a fixture swing needs a full rebuild."
                ),
            )
        )

    return advice
