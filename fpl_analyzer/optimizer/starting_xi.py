"""Pick a legal starting XI + bench order from a 15-man scored squad."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from fpl_analyzer.data.players import Position
from fpl_analyzer.optimizer.candidates import ScoredPlayer

VALID_FORMATIONS: tuple[tuple[int, int, int], ...] = tuple(
    (d, m, f)
    for d in range(3, 6)
    for m in range(2, 6)
    for f in range(1, 4)
    if d + m + f == 10
)


@dataclass(frozen=True, slots=True)
class Lineup:
    formation: tuple[int, int, int]
    xi: tuple[ScoredPlayer, ...]
    bench: tuple[ScoredPlayer, ...]
    captain: ScoredPlayer
    vice: ScoredPlayer
    xi_score: float
    xi_xpts: float

    @property
    def formation_label(self) -> str:
        d, m, f = self.formation
        return f"1-{d}-{m}-{f}"


def _by_pos(squad: list[ScoredPlayer]) -> dict[Position, list[ScoredPlayer]]:
    groups: dict[Position, list[ScoredPlayer]] = {
        Position.GKP: [],
        Position.DEF: [],
        Position.MID: [],
        Position.FWD: [],
    }
    for p in squad:
        groups[p.position].append(p)
    for pos in groups:
        groups[pos].sort(key=lambda s: s.score, reverse=True)
    return groups


def _pick_captain_vice(
    xi: list[ScoredPlayer], *, min_availability: float = 0.5
) -> tuple[ScoredPlayer, ScoredPlayer]:
    ranked = sorted(xi, key=lambda s: s.score, reverse=True)
    eligible = [s for s in ranked if s.form.availability >= min_availability]
    pool = eligible if len(eligible) >= 2 else ranked
    return pool[0], pool[1] if len(pool) > 1 else pool[0]


def select_starting_xi(squad: list[ScoredPlayer]) -> Lineup:
    if len(squad) != 15:
        raise ValueError(f"Expected 15 players, got {len(squad)}")
    groups = _by_pos(squad)
    if len(groups[Position.GKP]) < 1:
        raise ValueError("Need at least one goalkeeper")

    best: Lineup | None = None
    for formation in VALID_FORMATIONS:
        n_def, n_mid, n_fwd = formation
        if (
            len(groups[Position.DEF]) < n_def
            or len(groups[Position.MID]) < n_mid
            or len(groups[Position.FWD]) < n_fwd
        ):
            continue
        gkp = groups[Position.GKP][0]
        xi = [
            gkp,
            *groups[Position.DEF][:n_def],
            *groups[Position.MID][:n_mid],
            *groups[Position.FWD][:n_fwd],
        ]
        xi_ids = {p.element_id for p in xi}
        bench_gk = next(
            p for p in groups[Position.GKP] if p.element_id not in xi_ids
        )
        outfield_bench = sorted(
            (
                p
                for p in squad
                if p.element_id not in xi_ids and p.position != Position.GKP
            ),
            key=lambda s: s.score,
            reverse=True,
        )
        captain, vice = _pick_captain_vice(xi)
        lineup = Lineup(
            formation=formation,
            xi=tuple(xi),
            bench=(bench_gk, *outfield_bench),
            captain=captain,
            vice=vice,
            xi_score=sum(p.score for p in xi),
            xi_xpts=sum(p.xpts for p in xi),
        )
        if best is None or lineup.xi_score > best.xi_score:
            best = lineup

    if best is None:
        best = _exhaustive_xi(squad)
    return best


def _exhaustive_xi(squad: list[ScoredPlayer]) -> Lineup:
    groups = _by_pos(squad)
    best: Lineup | None = None
    keepers = groups[Position.GKP]
    for formation in VALID_FORMATIONS:
        n_def, n_mid, n_fwd = formation
        if (
            len(groups[Position.DEF]) < n_def
            or len(groups[Position.MID]) < n_mid
            or len(groups[Position.FWD]) < n_fwd
            or not keepers
        ):
            continue
        for gkp in keepers:
            for defs in combinations(groups[Position.DEF], n_def):
                for mids in combinations(groups[Position.MID], n_mid):
                    for fwds in combinations(groups[Position.FWD], n_fwd):
                        xi = [gkp, *defs, *mids, *fwds]
                        xi_ids = {p.element_id for p in xi}
                        bench_gk = next(
                            (
                                p
                                for p in keepers
                                if p.element_id not in xi_ids
                            ),
                            None,
                        )
                        if bench_gk is None:
                            continue
                        outfield_bench = sorted(
                            (
                                p
                                for p in squad
                                if p.element_id not in xi_ids
                                and p.position != Position.GKP
                            ),
                            key=lambda s: s.score,
                            reverse=True,
                        )
                        captain, vice = _pick_captain_vice(xi)
                        lineup = Lineup(
                            formation=formation,
                            xi=tuple(xi),
                            bench=(bench_gk, *outfield_bench),
                            captain=captain,
                            vice=vice,
                            xi_score=sum(p.score for p in xi),
                            xi_xpts=sum(p.xpts for p in xi),
                        )
                        if best is None or lineup.xi_score > best.xi_score:
                            best = lineup
    if best is None:
        raise ValueError("No legal starting XI for this squad")
    return best
