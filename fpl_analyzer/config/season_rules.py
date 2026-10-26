"""Official FPL season constraints — single source of truth (no buried magic numbers)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SeasonRules:
    """2025/26-style FPL rules used across squad reconstruction and optimiser."""

    squad_size: int = 15
    starting_xi_size: int = 11
    max_per_club: int = 3
    hit_points: int = 4
    max_free_transfers_bank: int = 2
    free_transfers_per_gw: int = 1
    # Squad composition (element_type ids: 1 GKP, 2 DEF, 3 MID, 4 FWD)
    squad_gkp: int = 2
    squad_def: int = 5
    squad_mid: int = 5
    squad_fwd: int = 3
    # Legal XI ranges
    xi_gkp: int = 1
    xi_def_min: int = 3
    xi_def_max: int = 5
    xi_mid_min: int = 2
    xi_mid_max: int = 5
    xi_fwd_min: int = 1
    xi_fwd_max: int = 3
    # Chip API names (bootstrap / history)
    chip_wildcard: str = "wildcard"
    chip_freehit: str = "freehit"
    chip_bboost: str = "bboost"
    chip_3xc: str = "3xc"
    # Search defaults
    transfer_out_candidates: int = 8
    transfer_in_per_pos: int = 25
    default_fixture_horizon: int = 3
    strategy_horizon: int = 5

    @property
    def squad_counts(self) -> dict:
        """Map Position enum → count (import Position lazily to avoid cycles)."""
        from fpl_analyzer.data.players import Position

        return {
            Position.GKP: self.squad_gkp,
            Position.DEF: self.squad_def,
            Position.MID: self.squad_mid,
            Position.FWD: self.squad_fwd,
        }

    def hit_cost(self, n_transfers: int, free_transfers: int) -> tuple[int, int]:
        """Return (hits, point_cost)."""
        hits = max(0, n_transfers - max(0, free_transfers))
        return hits, hits * self.hit_points

    def valid_formations(self) -> tuple[tuple[int, int, int], ...]:
        """(def, mid, fwd) tuples with GKP fixed at 1."""
        out: list[tuple[int, int, int]] = []
        for d in range(self.xi_def_min, self.xi_def_max + 1):
            for m in range(self.xi_mid_min, self.xi_mid_max + 1):
                for f in range(self.xi_fwd_min, self.xi_fwd_max + 1):
                    if d + m + f == self.starting_xi_size - self.xi_gkp:
                        out.append((d, m, f))
        return tuple(out)


# Singleton used by the package
RULES = SeasonRules()
