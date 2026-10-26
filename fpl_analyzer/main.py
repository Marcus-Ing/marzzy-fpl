"""CLI entrypoint for squad + analysis + optimiser."""

from __future__ import annotations

import argparse
import sys

from fpl_analyzer.api.fpl_api import FplApiError
from fpl_analyzer.optimizer import optimize_team


def _money(tenths: int) -> str:
    return f"£{tenths / 10.0:.1f}m"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fpl-analyzer")
    parser.add_argument("team_id", type=int)
    parser.add_argument("--horizon", type=int, default=3)
    parser.add_argument("--max-transfers", type=int, default=2, choices=(0, 1, 2))
    args = parser.parse_args(argv)
    try:
        result = optimize_team(
            args.team_id, horizon=args.horizon, max_transfers=args.max_transfers
        )
    except FplApiError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    squad = result.analysis.squad
    rec = result.recommendation
    print(f"{squad.team_name} (ID {squad.team_id}) · {squad.manager_name}")
    print(
        f"GW{result.analysis.target_event} · bank {_money(squad.bank)} · "
        f"FTs {squad.free_transfers}"
    )
    if rec.is_roll:
        print("Recommendation: HOLD")
    else:
        print(f"Recommendation: {rec.n_transfers} transfer(s), hits={rec.hits}")
        for m in rec.moves:
            print(f"  {m.label}")
    print(
        f"Gain vs hold: {rec.gain_vs_roll:+.1f} score, "
        f"{rec.xpts_gain_vs_roll:+.1f} xPts"
    )
    print(
        f"Captain {rec.lineup.captain.web_name} / "
        f"Vice {rec.lineup.vice.web_name} · XI {rec.lineup.formation_label}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
