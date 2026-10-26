"""Foundation tests — prices, budget, 3/club, formations, FT/hits, legal transfers."""

from __future__ import annotations

from fpl_analyzer.config import RULES
from fpl_analyzer.data.players import Position
from fpl_analyzer.data.squad import selling_price
from fpl_analyzer.optimizer.starting_xi import VALID_FORMATIONS, select_starting_xi
from fpl_analyzer.optimizer.transfers import _club_ok, _hits


def test_selling_price_rise_half_floored():
    # Buy 55, now 60 → rise 5, sell 55+2 = 57
    assert selling_price(55, 60) == 57


def test_selling_price_fall_to_now():
    assert selling_price(80, 75) == 75


def test_selling_price_unchanged():
    assert selling_price(50, 50) == 50


def test_hit_cost_with_one_ft():
    hits, cost = RULES.hit_cost(2, 1)
    assert hits == 1 and cost == 4
    hits0, cost0 = RULES.hit_cost(1, 1)
    assert hits0 == 0 and cost0 == 0
    hits2, cost2 = RULES.hit_cost(2, 0)
    assert hits2 == 2 and cost2 == 8


def test_hits_helper_matches_rules():
    assert _hits(2, 1) == RULES.hit_cost(2, 1)


def test_squad_counts_sum_to_fifteen():
    assert sum(RULES.squad_counts.values()) == RULES.squad_size
    assert RULES.squad_counts[Position.GKP] == 2
    assert RULES.squad_counts[Position.DEF] == 5


def test_valid_formations_cover_legal_xi():
    forms = RULES.valid_formations()
    assert forms
    assert forms == VALID_FORMATIONS
    for d, m, f in forms:
        assert RULES.xi_def_min <= d <= RULES.xi_def_max
        assert RULES.xi_mid_min <= m <= RULES.xi_mid_max
        assert RULES.xi_fwd_min <= f <= RULES.xi_fwd_max
        assert d + m + f == 10


def test_max_per_club_constant():
    assert RULES.max_per_club == 3


def test_chip_names():
    assert RULES.chip_wildcard == "wildcard"
    assert RULES.chip_freehit == "freehit"
    assert RULES.chip_bboost == "bboost"
    assert RULES.chip_3xc == "3xc"


def test_ft_bank_cap():
    assert RULES.max_free_transfers_bank == 2


# --- FT estimate ---
def test_estimate_free_transfers_simple_roll():
    from fpl_analyzer.data.squad import estimate_free_transfers

    history = {
        "current": [
            {"event": 1, "event_transfers": 0},
            {"event": 2, "event_transfers": 0},
        ],
        "chips": [],
    }
    fts, _ = estimate_free_transfers(history)
    # start 1; GW1 unused → min(2,0+1)=1 then +1 → 2; GW2 unused → min(2,1+1)=2 then wait
    # After processing all rows: each unused banks toward max 2
    assert fts == 2


def test_estimate_free_transfers_after_one_transfer():
    from fpl_analyzer.data.squad import estimate_free_transfers

    history = {
        "current": [
            {"event": 1, "event_transfers": 1},
            {"event": 2, "event_transfers": 1},
        ],
        "chips": [],
    }
    fts, _ = estimate_free_transfers(history)
    # After each 1T with 1 FT: remaining 0 → next = 1
    assert fts == 1


# --- Club constraint with fake pool ---
class _Fake:
    def __init__(self, tid: int):
        self.team_id = tid


def test_club_ok_rejects_four_same_club():
    pool = {i: _Fake(1) for i in range(4)}
    assert _club_ok([0, 1, 2], pool) is True
    assert _club_ok([0, 1, 2, 3], pool) is False
