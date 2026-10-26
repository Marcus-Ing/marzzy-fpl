"""Lineup + transfer legality tests with synthetic scored players."""

from __future__ import annotations

from fpl_analyzer.analysis.fixtures import FixtureOutlook
from fpl_analyzer.analysis.form import FormMetrics
from fpl_analyzer.analysis.minutes import MinutesProjection
from fpl_analyzer.analysis.xpts import FixtureXPts, HorizonXPts
from fpl_analyzer.config import RULES
from fpl_analyzer.data.players import Player, Position
from fpl_analyzer.optimizer.candidates import ScoredPlayer
from fpl_analyzer.optimizer.starting_xi import select_starting_xi
from fpl_analyzer.optimizer.transfers import _hits


def _player(eid: int, pos: Position, team: int, name: str) -> Player:
    return Player(
        id=eid,
        web_name=name,
        first_name=name,
        second_name="",
        team_id=team,
        element_type=pos,
        now_cost=50,
        cost_change_start=0,
        status="a",
        news="",
        form=5.0,
        points_per_game=4.0,
        total_points=40,
        minutes=600,
        starts=7,
        expected_goals=1.0,
        expected_assists=0.5,
        expected_goal_involvements=1.5,
        ep_this=4.0,
        ep_next=4.0,
        chance_of_playing_this_round=100,
        chance_of_playing_next_round=100,
        defensive_contribution=10,
        selected_by_percent=5.0,
    )


def _scored(
    eid: int, pos: Position, team: int, name: str, xpts_h: float
) -> ScoredPlayer:
    p = _player(eid, pos, team, name)
    form = FormMetrics(
        form=5.0,
        points_per_game=4.0,
        minutes=600,
        starts=7,
        minutes_factor=1.0,
        availability=1.0,
        rotation_risk=0.0,
        status="a",
        news="",
        chance_of_playing=100,
        xgi=1.5,
        xgi_per_90=0.2,
        defcon=10,
        defcon_per_start=1.0,
    )
    outlook = FixtureOutlook(
        team_id=team, fixtures=(), avg_fdr=3.0, avg_ease=3.0, horizon=3
    )
    minutes = MinutesProjection(
        p_start=0.9,
        xmins=75,
        start_rate=0.9,
        availability=1.0,
        congestion_factor=1.0,
        notes=("ok",),
    )
    hz = HorizonXPts(
        by_event=(
            FixtureXPts(1, xpts_h / 3, 0.9, 0.2, "H FDR3"),
            FixtureXPts(2, xpts_h / 3, 0.9, 0.2, "A FDR3"),
            FixtureXPts(3, xpts_h / 3, 0.9, 0.2, "H FDR2"),
        ),
        total=xpts_h,
        per_gw_avg=xpts_h / 3,
    )
    return ScoredPlayer(
        player=p,
        club_short=f"T{team}",
        form=form,
        fixtures=outlook,
        minutes=minutes,
        horizon_xpts=hz,
        ep_raw=4.0,
        xpts=xpts_h / 3,
        score=xpts_h,
        risk=0.1,
        target_event=1,
        horizon=3,
    )


def _full_squad() -> list[ScoredPlayer]:
    squad: list[ScoredPlayer] = []
    eid = 1
    # 2 GKP
    for i in range(2):
        squad.append(_scored(eid, Position.GKP, 10 + i, f"GK{i}", 8 - i))
        eid += 1
    # 5 DEF different clubs
    for i in range(5):
        squad.append(_scored(eid, Position.DEF, 20 + i, f"DF{i}", 10 - i * 0.5))
        eid += 1
    # 5 MID
    for i in range(5):
        squad.append(_scored(eid, Position.MID, 30 + i, f"MF{i}", 12 - i * 0.4))
        eid += 1
    # 3 FWD
    for i in range(3):
        squad.append(_scored(eid, Position.FWD, 40 + i, f"FW{i}", 14 - i))
        eid += 1
    assert len(squad) == 15
    return squad


def test_select_starting_xi_legal_and_bench_order():
    squad = _full_squad()
    lu = select_starting_xi(squad)
    assert len(lu.xi) == 11
    assert len(lu.bench) == 4
    assert lu.bench[0].position == Position.GKP
    # Bench outfield sorted by xPts descending
    outfield = [p for p in lu.bench[1:]]
    assert outfield == sorted(
        outfield, key=lambda p: p.xpts_horizon, reverse=True
    )
    d, m, f = lu.formation
    assert (d, m, f) in RULES.valid_formations()


def test_captain_is_top_available_xpts():
    squad = _full_squad()
    lu = select_starting_xi(squad)
    assert lu.captain.element_id in {p.element_id for p in lu.xi}
    assert lu.captain.xpts_horizon >= lu.vice.xpts_horizon


def test_one_and_two_transfer_hit_math():
    assert _hits(1, 1) == (0, 0)
    assert _hits(2, 1) == (1, RULES.hit_points)
    assert _hits(2, 2) == (0, 0)
