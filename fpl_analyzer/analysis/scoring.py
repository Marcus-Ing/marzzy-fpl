"""Transparent per-player score combining form, fixtures, and FPL ep_*."""

from __future__ import annotations

from dataclasses import dataclass

from fpl_analyzer.analysis.fixtures import FixtureOutlook
from fpl_analyzer.analysis.form import FormMetrics, compute_form_metrics
from fpl_analyzer.data.players import Player, Position
from fpl_analyzer.data.squad import SquadPlayer

SCORE_WEIGHTS: dict[str, float] = {
    "ep": 1.00,
    "form": 0.40,
    "xgi": 0.25,
    "fixture": 0.50,
    "minutes": 0.30,
    "defcon": 0.12,
    "rotation": 0.45,
}


@dataclass(frozen=True, slots=True)
class PlayerAnalysis:
    squad_player: SquadPlayer
    player: Player
    form: FormMetrics
    fixtures: FixtureOutlook
    ep_raw: float
    xpts: float
    score: float
    target_event: int
    components: dict[str, float]


def project_xpts(
    player: Player, form: FormMetrics, *, for_next: bool
) -> tuple[float, float]:
    ep = player.ep_next if for_next else player.ep_this
    return ep, ep * form.availability


def compute_score(
    form: FormMetrics,
    fixtures: FixtureOutlook,
    xpts: float,
    position: Position,
) -> tuple[float, dict[str, float]]:
    w = SCORE_WEIGHTS
    components = {
        "ep": w["ep"] * xpts,
        "form": w["form"] * form.form,
        "xgi": w["xgi"] * (form.xgi_per_90 * 5.0),
        "fixture": w["fixture"] * fixtures.avg_ease,
        "minutes": w["minutes"] * (form.minutes_factor * 10.0),
        "defcon": 0.0,
        "rotation_penalty": -w["rotation"] * (form.rotation_risk * 10.0),
    }
    if position in (Position.GKP, Position.DEF):
        components["defcon"] = w["defcon"] * form.defcon_per_start
    total = sum(components.values())
    total *= 0.25 + 0.75 * form.availability
    return total, components


def analyze_player(
    squad_player: SquadPlayer,
    player: Player,
    fixtures: FixtureOutlook,
    *,
    gameweeks_played: int,
    target_event: int,
    for_next: bool,
) -> PlayerAnalysis:
    form = compute_form_metrics(
        player, gameweeks_played=gameweeks_played, for_next=for_next
    )
    ep_raw, xpts = project_xpts(player, form, for_next=for_next)
    score, components = compute_score(form, fixtures, xpts, player.element_type)
    return PlayerAnalysis(
        squad_player=squad_player,
        player=player,
        form=form,
        fixtures=fixtures,
        ep_raw=ep_raw,
        xpts=xpts,
        score=score,
        target_event=target_event,
        components=components,
    )
