"""Opponent strength beyond FDR (FPL-12).

Uses bootstrap team strength fields when present, else FDR-derived proxies.
Outputs attack/defence indices (higher = stronger) and CS probability inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fpl_analyzer.data.fixtures import Fixture


@dataclass(frozen=True, slots=True)
class TeamStrength:
    team_id: int
    attack_home: float
    attack_away: float
    defence_home: float
    defence_away: float
    overall: float


@dataclass(frozen=True, slots=True)
class FixtureStrength:
    event: int
    is_home: bool
    opponent_id: int
    fdr: int
    # Relative: how tough for the player’s team (higher = harder)
    opp_attack: float
    opp_defence: float
    cs_probability: float
    ease: float  # higher better for player


def parse_team_strengths(bootstrap: dict[str, Any]) -> dict[int, TeamStrength]:
    out: dict[int, TeamStrength] = {}
    for row in bootstrap.get("teams") or []:
        tid = int(row["id"])
        # FPL bootstrap historically exposes strength_* fields (scale ~1000–1400)
        ah = float(row.get("strength_attack_home") or row.get("strength") or 1000)
        aa = float(row.get("strength_attack_away") or row.get("strength") or 1000)
        dh = float(row.get("strength_defence_home") or row.get("strength") or 1000)
        da = float(row.get("strength_defence_away") or row.get("strength") or 1000)
        overall = float(row.get("strength") or ((ah + aa + dh + da) / 4))
        out[tid] = TeamStrength(
            team_id=tid,
            attack_home=ah,
            attack_away=aa,
            defence_home=dh,
            defence_away=da,
            overall=overall,
        )
    return out


def _norm(value: float, lo: float = 900.0, hi: float = 1400.0) -> float:
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def fixture_strength_view(
    fx: Fixture,
    team_id: int,
    strengths: dict[int, TeamStrength],
) -> FixtureStrength | None:
    if fx.event is None or fx.finished:
        return None
    if fx.team_h == team_id:
        is_home, opp_id, fdr = True, fx.team_a, fx.team_h_difficulty or 3
    elif fx.team_a == team_id:
        is_home, opp_id, fdr = False, fx.team_h, fx.team_a_difficulty or 3
    else:
        return None

    self_s = strengths.get(team_id)
    opp_s = strengths.get(opp_id)
    if opp_s is None:
        # FDR-only fallback
        ease = float(6 - fdr)
        cs = {1: 0.45, 2: 0.35, 3: 0.25, 4: 0.15, 5: 0.08}.get(fdr, 0.2)
        return FixtureStrength(
            event=fx.event,
            is_home=is_home,
            opponent_id=opp_id,
            fdr=fdr,
            opp_attack=fdr / 5.0,
            opp_defence=fdr / 5.0,
            cs_probability=cs,
            ease=ease,
        )

    # Opponent attack facing us / our defence
    opp_attack = opp_s.attack_away if is_home else opp_s.attack_home
    opp_defence = opp_s.defence_away if is_home else opp_s.defence_home
    our_def = (
        (self_s.defence_home if is_home else self_s.defence_away) if self_s else 1100
    )
    our_att = (
        (self_s.attack_home if is_home else self_s.attack_away) if self_s else 1100
    )

    # CS prob: stronger our defence vs weaker opp attack
    cs = 0.12 + 0.38 * (1.0 - _norm(opp_attack)) * (0.5 + 0.5 * _norm(our_def))
    if is_home:
        cs = min(0.55, cs + 0.04)
    # Goal threat ease vs opp defence
    attack_edge = _norm(our_att) * (1.0 - _norm(opp_defence))
    ease = (6 - fdr) * 0.55 + attack_edge * 5.0 * 0.45

    return FixtureStrength(
        event=fx.event,
        is_home=is_home,
        opponent_id=opp_id,
        fdr=fdr,
        opp_attack=_norm(opp_attack),
        opp_defence=_norm(opp_defence),
        cs_probability=max(0.05, min(0.55, cs)),
        ease=ease,
    )


def upcoming_strengths(
    fixtures: list[Fixture],
    team_id: int,
    strengths: dict[int, TeamStrength],
    *,
    from_event: int,
    horizon: int,
) -> list[FixtureStrength]:
    end = from_event + horizon - 1
    out: list[FixtureStrength] = []
    for fx in fixtures:
        if fx.event is None or fx.event < from_event or fx.event > end:
            continue
        view = fixture_strength_view(fx, team_id, strengths)
        if view:
            out.append(view)
    out.sort(key=lambda v: (v.event, not v.is_home))
    return out
