"""Multi-GW transfer strategies — now vs roll vs later (FPL-15)."""

from __future__ import annotations

from dataclasses import dataclass

from fpl_analyzer.config import RULES
from fpl_analyzer.optimizer.transfers import TransferPlan, TransferSearchResult


@dataclass(frozen=True, slots=True)
class StrategyOption:
    key: str
    title: str
    horizon_gain: float
    detail: str
    plan: TransferPlan | None


@dataclass(slots=True)
class StrategyComparison:
    horizon: int
    options: list[StrategyOption]
    preferred: StrategyOption


def compare_strategies(
    search: TransferSearchResult,
    *,
    horizon: int | None = None,
) -> StrategyComparison:
    """
    Compare:
    - Roll now (keep FT)
    - Transfer now (best 1T / 2T from search)
    - Defer: approximate value of banking FT then doing best 1T next week
      (uses best_one gain without hit if currently 1 FT — simple V1)
    """
    hz = horizon or RULES.strategy_horizon
    roll = search.roll
    best1 = search.best_one
    best2 = search.best_two
    rec = search.recommendation

    options: list[StrategyOption] = [
        StrategyOption(
            key="roll",
            title="Roll free transfer",
            horizon_gain=0.0,
            detail=(
                f"Keep squad; XI ≈ {roll.lineup.xi_xpts:.1f} xPts over {hz} GW look. "
                "Banks FT (max 2)."
            ),
            plan=roll,
        )
    ]

    if best1 is not None:
        options.append(
            StrategyOption(
                key="now_1t",
                title="Transfer now (1)",
                horizon_gain=best1.xpts_gain_vs_roll,
                detail=(
                    f"{best1.moves[0].label if best1.moves else '—'} · "
                    f"ΔxPts {best1.xpts_gain_vs_roll:+.1f} after hits"
                ),
                plan=best1,
            )
        )
    if best2 is not None:
        options.append(
            StrategyOption(
                key="now_2t",
                title="Transfer now (2)",
                horizon_gain=best2.xpts_gain_vs_roll,
                detail=(
                    " · ".join(m.label for m in best2.moves)
                    + f" · ΔxPts {best2.xpts_gain_vs_roll:+.1f} after hits"
                ),
                plan=best2,
            )
        )

    # Defer: if we have 1 FT, rolling then doing the best 1T without needing a hit next week
    # approximates best1 gain if best1 had 0 hits; if best1 needed a hit, deferring may save 4
    if best1 is not None:
        deferred_gain = best1.lineup.xi_xpts - roll.lineup.xi_xpts
        # No hit next week assumed when banking to 2 FTs — discount one GW of delay (~avg/GW)
        delay_penalty = (best1.lineup.xi_xpts - roll.lineup.xi_xpts) / max(
            1, best1.moves[0].player_in.horizon if best1.moves else hz
        )
        deferred_net = deferred_gain - max(0.0, delay_penalty)
        options.append(
            StrategyOption(
                key="defer",
                title="Hold now, transfer next GW",
                horizon_gain=deferred_net,
                detail=(
                    f"Bank FT then make the upgrade without a hit. "
                    f"Approx ΔxPts {deferred_net:+.1f} after one-GW delay penalty."
                ),
                plan=best1,
            )
        )

    preferred = max(options, key=lambda o: o.horizon_gain)
    # Prefer recommendation alignment if close
    if rec.is_roll:
        for o in options:
            if o.key == "roll":
                preferred = o
                break
    elif abs(preferred.horizon_gain - rec.xpts_gain_vs_roll) < 0.5:
        # keep preferred
        pass

    return StrategyComparison(horizon=hz, options=options, preferred=preferred)
