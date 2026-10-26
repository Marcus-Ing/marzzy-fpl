"""Form, minutes reliability, and availability from bootstrap-static."""

from __future__ import annotations

from dataclasses import dataclass

from fpl_analyzer.data.players import Player

STATUS_AVAILABLE = "a"
STATUS_DOUBTFUL = "d"


@dataclass(frozen=True, slots=True)
class FormMetrics:
    form: float
    points_per_game: float
    minutes: int
    starts: int
    minutes_factor: float
    availability: float
    rotation_risk: float
    status: str
    news: str
    chance_of_playing: int | None
    xgi: float
    xgi_per_90: float
    defcon: int
    defcon_per_start: float


def availability_for(player: Player, *, for_next: bool) -> tuple[float, int | None]:
    chance = (
        player.chance_of_playing_next_round
        if for_next
        else player.chance_of_playing_this_round
    )
    if chance is not None:
        return max(0.0, min(1.0, chance / 100.0)), chance
    status = (player.status or STATUS_AVAILABLE).lower()
    if status == STATUS_AVAILABLE:
        return 1.0, None
    if status == STATUS_DOUBTFUL:
        return 0.5, None
    return 0.0, None


def minutes_factor(player: Player, gameweeks_played: int) -> float:
    gws = max(1, gameweeks_played)
    expected = 70.0 * gws
    return max(0.0, min(1.0, player.minutes / expected))


def compute_form_metrics(
    player: Player, *, gameweeks_played: int, for_next: bool
) -> FormMetrics:
    avail, chance = availability_for(player, for_next=for_next)
    m_factor = minutes_factor(player, gameweeks_played)
    rotation = 1.0 if avail <= 0.0 else max(0.0, 1.0 - m_factor)
    per_90 = (
        player.expected_goal_involvements / player.minutes * 90.0
        if player.minutes
        else 0.0
    )
    defcon_ps = (
        player.defensive_contribution / player.starts if player.starts else 0.0
    )
    return FormMetrics(
        form=player.form,
        points_per_game=player.points_per_game,
        minutes=player.minutes,
        starts=player.starts,
        minutes_factor=m_factor,
        availability=avail,
        rotation_risk=rotation,
        status=player.status,
        news=player.news,
        chance_of_playing=chance,
        xgi=player.expected_goal_involvements,
        xgi_per_90=per_90,
        defcon=player.defensive_contribution,
        defcon_per_start=defcon_ps,
    )
