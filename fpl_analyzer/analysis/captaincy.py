"""Captain / vice suggestions from Phase 2 scores."""

from __future__ import annotations

from dataclasses import dataclass

from fpl_analyzer.analysis.scoring import PlayerAnalysis


@dataclass(frozen=True, slots=True)
class CaptaincyAdvice:
    captain: PlayerAnalysis
    vice: PlayerAnalysis
    target_event: int
    rationale: str
    current_captain_name: str | None
    current_vice_name: str | None
    agrees_with_current: bool


def suggest_captaincy(
    analyses: list[PlayerAnalysis], *, min_availability: float = 0.50
) -> CaptaincyAdvice | None:
    if not analyses:
        return None
    target = analyses[0].target_event
    current_c = next((a for a in analyses if a.squad_player.is_captain), None)
    current_v = next(
        (a for a in analyses if a.squad_player.is_vice_captain), None
    )
    ranked = sorted(analyses, key=lambda a: a.score, reverse=True)
    eligible = [a for a in ranked if a.form.availability >= min_availability]
    pool = eligible if len(eligible) >= 2 else ranked
    captain, vice = pool[0], pool[1] if len(pool) > 1 else pool[0]
    agrees = (
        current_c is not None
        and current_c.squad_player.element_id == captain.squad_player.element_id
    )
    rationale = (
        f"{captain.squad_player.web_name} leads on score "
        f"({captain.score:.1f}); vice {vice.squad_player.web_name}."
    )
    return CaptaincyAdvice(
        captain=captain,
        vice=vice,
        target_event=target,
        rationale=rationale,
        current_captain_name=(
            current_c.squad_player.web_name if current_c else None
        ),
        current_vice_name=current_v.squad_player.web_name if current_v else None,
        agrees_with_current=agrees,
    )
