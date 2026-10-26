"""Expected minutes and start probability — transparent rules (FPL-10).

P(start) blends:
- season start rate (starts / GWs played)
- availability (chance_of_playing / status)
- recent form proxy via FPL ``form`` scaled softly
- congestion penalty when club has many fixtures in horizon (proxy)

xMins = P(start) × expected minutes if starting (~78) + (1−P(start)) × cameo (~15)
        then × availability soft-gate.
"""

from __future__ import annotations

from dataclasses import dataclass

from fpl_analyzer.data.players import Player

FULL_START_MINUTES = 78.0
CAMEO_MINUTES = 15.0


@dataclass(frozen=True, slots=True)
class MinutesProjection:
    p_start: float
    xmins: float
    start_rate: float
    availability: float
    congestion_factor: float
    notes: tuple[str, ...]


def project_minutes(
    player: Player,
    *,
    gameweeks_played: int,
    availability: float,
    fixtures_in_horizon: int = 1,
) -> MinutesProjection:
    gws = max(1, gameweeks_played)
    start_rate = min(1.0, player.starts / gws)
    # Soft form boost for regulars (form ~0–10 typical)
    form_boost = min(0.15, max(0.0, (player.form - 3.0) / 40.0))
    # Congestion: 3+ fixtures in horizon slightly lowers start certainty for fringe
    congestion = 1.0
    if fixtures_in_horizon >= 3 and start_rate < 0.85:
        congestion = 0.92
    elif fixtures_in_horizon >= 2 and start_rate < 0.6:
        congestion = 0.95

    raw = start_rate * (0.85 + form_boost) * congestion
    p_start = max(0.0, min(1.0, raw * (0.35 + 0.65 * availability)))

    # Minutes if involved
    xmins_if = FULL_START_MINUTES * p_start + CAMEO_MINUTES * (1.0 - p_start) * min(
        1.0, player.minutes / max(1.0, gws * 30.0)
    )
    xmins = xmins_if * (0.4 + 0.6 * availability)

    notes: list[str] = []
    if availability < 0.75:
        notes.append(f"Availability {availability:.0%} lowers start chance")
    if start_rate < 0.5:
        notes.append(f"Low season start rate ({start_rate:.0%})")
    if congestion < 1.0:
        notes.append("Fixture congestion trims minutes confidence")
    if not notes:
        notes.append("Solid minutes outlook from starts + availability")

    return MinutesProjection(
        p_start=p_start,
        xmins=xmins,
        start_rate=start_rate,
        availability=availability,
        congestion_factor=congestion,
        notes=tuple(notes),
    )
