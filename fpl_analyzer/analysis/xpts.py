"""Per-fixture multi-GW projected FPL points — rules-based V1 (FPL-11).

Sources: bootstrap xG/xA/xGI, ep_*, DefCon, opponent strength (FPL-12),
minutes/P(start) (FPL-10). Not ML.

Rough mapping per fixture:
  appearance ≈ 2 × P(≥60') + 1 × P(cameo)
  attack     ≈ (xG/90×p_start×4 + xA/90×p_start×3) × fixture_attack_mult
  clean_sheet≈ CS_pts × P(start) × cs_probability   (GKP/DEF; MID half)
  defcon     ≈ expected DefCon pts × P(start)
  bonus      ≈ small share of ICT-ish form

Returns horizon table and totals. Separated from transfer desirability.
"""

from __future__ import annotations

from dataclasses import dataclass

from fpl_analyzer.analysis.minutes import MinutesProjection
from fpl_analyzer.analysis.opponent import FixtureStrength
from fpl_analyzer.data.players import Player, Position


@dataclass(frozen=True, slots=True)
class FixtureXPts:
    event: int
    xpts: float
    p_start: float
    cs_prob: float
    label: str


@dataclass(frozen=True, slots=True)
class HorizonXPts:
    by_event: tuple[FixtureXPts, ...]
    total: float
    per_gw_avg: float

    def as_table(self) -> list[dict[str, float | int | str]]:
        rows = [
            {
                "GW": fx.event,
                "xPts": round(fx.xpts, 2),
                "P(start)": round(fx.p_start, 2),
                "CS%": round(fx.cs_prob * 100),
                "Fixture": fx.label,
            }
            for fx in self.by_event
        ]
        rows.append(
            {
                "GW": "Total",
                "xPts": round(self.total, 2),
                "P(start)": "",
                "CS%": "",
                "Fixture": "",
            }
        )
        return rows


def _per90(total: float, minutes: int) -> float:
    if minutes <= 0:
        return 0.0
    return total / minutes * 90.0


def project_fixture_xpts(
    player: Player,
    minutes: MinutesProjection,
    fixture: FixtureStrength,
) -> float:
    p = minutes.p_start * minutes.availability
    # Appearance
    p60 = p * min(1.0, minutes.xmins / 60.0) if minutes.xmins else p * 0.7
    appearance = 2.0 * p60 + 1.0 * max(0.0, p - p60) * 0.5

    xg90 = _per90(player.expected_goals, player.minutes)
    xa90 = _per90(player.expected_assists, player.minutes)
    # Attack multiplier: easier when opp_defence low / ease high
    att_mult = 0.75 + 0.5 * (fixture.ease / 5.0)
    attack = (xg90 * 4.0 + xa90 * 3.0) * p * att_mult

    # CS
    if player.element_type == Position.GKP:
        cs_pts = 4.0
    elif player.element_type == Position.DEF:
        cs_pts = 4.0
    elif player.element_type == Position.MID:
        cs_pts = 1.0
    else:
        cs_pts = 0.0
    # Harder opp attack → lower CS already in fixture.cs_probability
    clean = cs_pts * p * fixture.cs_probability

    # DefCon proxy — ~0.5–2 pts for defenders who rack contributions
    defcon_ps = (
        player.defensive_contribution / max(1, player.starts)
        if player.starts
        else 0.0
    )
    defcon = 0.0
    if player.element_type in (Position.GKP, Position.DEF, Position.MID):
        defcon = min(2.5, defcon_ps * 0.15) * p

    # Bonus / form drip
    bonus = min(1.2, max(0.0, player.form / 12.0)) * p

    # Saves for GKP (very rough from minutes)
    saves = 0.0
    if player.element_type == Position.GKP:
        saves = 0.6 * p * (0.8 + 0.4 * fixture.opp_attack)

    return appearance + attack + clean + defcon + bonus + saves


def project_horizon_xpts(
    player: Player,
    minutes: MinutesProjection,
    fixtures: list[FixtureStrength],
) -> HorizonXPts:
    rows: list[FixtureXPts] = []
    for fx in fixtures:
        pts = project_fixture_xpts(player, minutes, fx)
        side = "H" if fx.is_home else "A"
        rows.append(
            FixtureXPts(
                event=fx.event,
                xpts=pts,
                p_start=minutes.p_start,
                cs_prob=fx.cs_probability,
                label=f"{side} FDR{fx.fdr}",
            )
        )
    total = sum(r.xpts for r in rows)
    avg = total / len(rows) if rows else 0.0
    return HorizonXPts(by_event=tuple(rows), total=total, per_gw_avg=avg)


def risk_score(
    minutes: MinutesProjection,
    *,
    availability: float,
    ownership: float = 0.0,
) -> float:
    """
    0 = safe, 1 = high risk. Transparent: minutes variance + injury + (optional) ownership.
    Not a fake confidence %.
    """
    injury = 1.0 - availability
    minutes_risk = 1.0 - minutes.p_start
    # Slight risk bump for ultra-premium ownership concentration (optional signal)
    own_risk = 0.05 if ownership >= 40 else 0.0
    return max(0.0, min(1.0, 0.55 * injury + 0.40 * minutes_risk + own_risk))
