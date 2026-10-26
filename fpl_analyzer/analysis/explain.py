"""Structured Why? reasons for transfers and captain picks (FPL-13)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fpl_analyzer.optimizer.candidates import ScoredPlayer
    from fpl_analyzer.optimizer.transfers import TransferMove, TransferPlan


@dataclass(frozen=True, slots=True)
class ReasonBlock:
    title: str
    bullets: tuple[str, ...]
    risks: tuple[str, ...]


def explain_player(p: ScoredPlayer) -> ReasonBlock:
    bullets = [
        f"Projected {p.xpts_horizon:.1f} xPts over next {p.horizon} GW(s) "
        f"(avg {p.xpts_horizon / max(1, p.horizon):.1f}/GW)",
        f"P(start) {p.p_start:.0%} · xMins {p.xmins:.0f}",
        f"Desirability score {p.score:.1f} (form/fixtures blend)",
        f"Risk {p.risk:.0%} (injury + minutes uncertainty)",
    ]
    if p.fixtures.summary:
        bullets.append(f"Fixtures: {p.fixtures.summary}")
    risks = list(p.minutes_notes[:2]) if p.minutes_notes else []
    if p.form.availability < 0.85:
        risks.append(f"Availability only {p.form.availability:.0%}")
    if p.form.news:
        risks.append(f"News: {p.form.news}")
    if not risks:
        risks.append("No major red flags from availability/minutes model")
    return ReasonBlock(
        title=f"{p.web_name} ({p.club_short})",
        bullets=tuple(bullets),
        risks=tuple(risks),
    )


def explain_transfer(move: TransferMove) -> ReasonBlock:
    out_p, in_p = move.player_out, move.player_in
    dx = in_p.xpts_horizon - out_p.xpts_horizon
    dscore = in_p.score - out_p.score
    dprice = move.sell_price - move.buy_price
    bullets = [
        f"ΔxPts over horizon: {dx:+.1f} "
        f"({out_p.web_name} {out_p.xpts_horizon:.1f} → {in_p.web_name} {in_p.xpts_horizon:.1f})",
        f"Δ desirability: {dscore:+.1f}",
        f"P(start): {out_p.p_start:.0%} → {in_p.p_start:.0%}",
        f"Bank impact: sell £{move.sell_price/10:.1f}m / buy £{move.buy_price/10:.1f}m "
        f"({'+' if dprice >= 0 else ''}£{dprice/10:.1f}m)",
    ]
    if in_p.xmins > out_p.xmins + 5:
        bullets.append("Higher expected minutes")
    if in_p.risk < out_p.risk - 0.05:
        bullets.append("Lower risk profile")
    risks: list[str] = []
    if in_p.form.availability < 0.9:
        risks.append(f"{in_p.web_name} availability {in_p.form.availability:.0%}")
    if in_p.risk >= 0.45:
        risks.append(f"{in_p.web_name} risk {in_p.risk:.0%}")
    if dx < 1.0:
        risks.append("Projected points gain is modest — check fixtures manually")
    if not risks:
        risks.append("No standout model risks beyond normal FPL variance")
    return ReasonBlock(
        title=f"{out_p.web_name} → {in_p.web_name}",
        bullets=tuple(bullets),
        risks=tuple(risks),
    )


def explain_plan(plan: TransferPlan) -> ReasonBlock:
    if plan.is_roll:
        return ReasonBlock(
            title="Hold / roll FT",
            bullets=(
                f"XI projected xPts (horizon): {plan.lineup.xi_xpts:.1f}",
                "No transfers — bank the free transfer",
                f"Objective (xPts − hits): {plan.objective:.1f}",
            ),
            risks=("Rolling can miss a short-term upgrade if a starter is out",),
        )
    reasons: list[str] = [
        f"{plan.n_transfers} transfer(s), hits={plan.hits} (−{plan.hit_cost} pts)",
        f"ΔxPts vs hold (after hits): {plan.xpts_gain_vs_roll:+.1f}",
        f"Bank after: £{plan.bank_after/10:.1f}m",
    ]
    for m in plan.moves:
        block = explain_transfer(m)
        reasons.extend(block.bullets[:2])
    risks: list[str] = []
    for m in plan.moves:
        risks.extend(explain_transfer(m).risks[:1])
    if plan.hits:
        risks.append(f"Taking a −{plan.hit_cost} hit — only if the xPts gain sticks")
    return ReasonBlock(
        title="Recommended plan",
        bullets=tuple(reasons),
        risks=tuple(risks) or ("None flagged",),
    )
