"""FPL Helper — visual XI, multi-GW xPts, Why?, strategies & chips."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fpl_analyzer.api.fpl_api import FplApiError  # noqa: E402
from fpl_analyzer.config import RULES  # noqa: E402
from fpl_analyzer.data.players import Position  # noqa: E402
from fpl_analyzer.optimizer import OptimizationResult, optimize_team  # noqa: E402

st.set_page_config(
    page_title="FPL Helper",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; max-width: 1180px; }
      div[data-testid="stMetricValue"] { font-size: 1.25rem; }
      .pitch {
        background: linear-gradient(180deg, #1b5e20 0%, #2e7d32 55%, #1b5e20 100%);
        border-radius: 16px; padding: 18px 12px 22px; color: #fff;
        border: 2px solid rgba(255,255,255,0.25);
      }
      .pitch-row {
        display: flex; justify-content: center; gap: 10px; flex-wrap: wrap;
        margin: 10px 0;
      }
      .shirt {
        background: rgba(0,0,0,0.35); border: 1px solid rgba(255,255,255,0.35);
        border-radius: 12px; min-width: 88px; max-width: 110px; padding: 8px 6px;
        text-align: center; backdrop-filter: blur(2px);
      }
      .shirt .name { font-weight: 700; font-size: 0.85rem; line-height: 1.2; }
      .shirt .meta { font-size: 0.72rem; opacity: 0.9; margin-top: 2px; }
      .shirt .xpts { font-size: 0.95rem; font-weight: 700; margin-top: 4px; }
      .shirt.cap { box-shadow: 0 0 0 2px #ffd54f; }
      .badge { display:inline-block; background:#ffd54f; color:#111;
               font-size:0.65rem; font-weight:800; padding:1px 5px; border-radius:6px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _money(tenths: int) -> str:
    return f"£{tenths / 10.0:.1f}m"


def _parse_team_id(raw: str) -> int | None:
    text = (raw or "").strip()
    if not text or not text.isdigit():
        return None
    value = int(text)
    return value if value > 0 else None


@st.cache_data(ttl=120, show_spinner=False)
def _load(team_id: int, horizon: int, max_transfers: int) -> OptimizationResult:
    return optimize_team(
        team_id, horizon=horizon, max_transfers=max_transfers
    )


def _plan_title(plan) -> str:
    if plan is None:
        return "—"
    if plan.is_roll:
        return "Hold (no transfers)"
    return " · ".join(
        f"{m.player_out.web_name} → {m.player_in.web_name}" for m in plan.moves
    )


def _shirt_html(p, *, captain=False, vice=False) -> str:
    badge = ""
    cls = "shirt"
    if captain:
        badge = '<div class="badge">C</div>'
        cls += " cap"
    elif vice:
        badge = '<div class="badge">VC</div>'
    return (
        f'<div class="{cls}">{badge}'
        f'<div class="name">{p.web_name}</div>'
        f'<div class="meta">{p.club_short} · {p.position.short_name}</div>'
        f'<div class="xpts">{p.xpts_horizon:.1f} xPts</div>'
        f'<div class="meta">P(start) {p.p_start:.0%}</div>'
        f"</div>"
    )


def render_pitch(lineup) -> None:
    by_pos: dict[Position, list] = {
        Position.GKP: [],
        Position.DEF: [],
        Position.MID: [],
        Position.FWD: [],
    }
    for p in lineup.xi:
        by_pos[p.position].append(p)

    rows_html = []
    for pos in (Position.GKP, Position.DEF, Position.MID, Position.FWD):
        cells = "".join(
            _shirt_html(
                p,
                captain=p.element_id == lineup.captain.element_id,
                vice=p.element_id == lineup.vice.element_id,
            )
            for p in by_pos[pos]
        )
        rows_html.append(f'<div class="pitch-row">{cells}</div>')
    st.markdown(
        f'<div class="pitch">'
        f'<div style="text-align:center;opacity:.9;font-size:.85rem;margin-bottom:6px">'
        f"Suggested XI · {lineup.formation_label} · "
        f"Σ {lineup.xi_xpts:.1f} horizon xPts</div>"
        + "".join(rows_html)
        + "</div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.title("FPL Helper")
    st.caption("Projected points, clear transfers, and a suggested starting XI.")

    with st.sidebar:
        st.header("Your team")
        team_id_raw = st.text_input(
            "FPL Team ID",
            value="",
            placeholder="Enter team ID",
            help=(
                "Number in your FPL URL: "
                "fantasy.premierleague.com/entry/<Team ID>/"
            ),
        )
        with st.expander("How do I find my Team ID?"):
            st.markdown(
                """
1. Go to [fantasy.premierleague.com](https://fantasy.premierleague.com) and sign in  
2. Open **Points** (or your team page)  
3. URL looks like `https://fantasy.premierleague.com/entry/1234567/`  
4. The number after `/entry/` is your Team ID
                """.strip()
            )
        horizon = st.slider(
            "Fixture look-ahead (gameweeks)",
            min_value=1,
            max_value=5,
            value=RULES.default_fixture_horizon,
        )
        max_transfers = st.select_slider(
            "Transfers to consider",
            options=[0, 1, 2],
            value=2,
        )
        parsed_id = _parse_team_id(team_id_raw)
        load = st.button(
            "Load team",
            type="primary",
            use_container_width=True,
            disabled=parsed_id is None,
        )
        if parsed_id is None and team_id_raw.strip():
            st.caption("Enter a valid numeric Team ID to continue.")
        st.caption(
            "Official FPL API data. Free transfers estimated from public history. "
            "Projections are rules-based — not ML."
        )

    if not load and "result" not in st.session_state:
        st.info(
            "Enter your **Team ID** in the sidebar, then click **Load team**. "
            "Use the help tip if you’re not sure where to find it."
        )
        st.stop()

    if load:
        if parsed_id is None:
            st.warning("Please enter a valid numeric Team ID first.")
            st.stop()
        with st.spinner("Loading squad and building recommendations…"):
            try:
                st.session_state["result"] = _load(
                    parsed_id, int(horizon), int(max_transfers)
                )
            except FplApiError as exc:
                st.error(str(exc))
                st.stop()
            except Exception:
                st.error(
                    "Something went wrong loading that team. "
                    "Check the Team ID and try again."
                )
                st.stop()

    result: OptimizationResult = st.session_state["result"]
    analysis = result.analysis
    squad = analysis.squad
    search = result.search
    rec = search.recommendation
    lu = rec.lineup

    # --- Header metrics ---
    st.subheader(squad.team_name)
    st.write(f"Manager · {squad.manager_name}")
    for note in analysis.notes[:2]:
        st.caption(note)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Target GW", f"GW{analysis.target_event}")
    c2.metric("Bank", _money(squad.bank))
    c3.metric("Squad value", _money(squad.team_value))
    c4.metric(
        "Free transfers",
        "—" if squad.free_transfers is None else str(squad.free_transfers),
    )
    c5.metric("Horizon xPts (XI)", f"{lu.xi_xpts:.1f}")

    # --- First screen: pitch + move ---
    st.markdown("### Your gameweek XI")
    render_pitch(lu)
    st.caption(
        f"Captain **{lu.captain.web_name}** · Vice **{lu.vice.web_name}** · "
        "Shirt totals are projected xPts over the fixture look-ahead."
    )

    st.markdown("### Recommended move")
    if rec.is_roll:
        st.success("**Hold your free transfer** — no move beats standing still on Σ xPts − hits.")
    else:
        st.success(
            f"**Make {rec.n_transfers} transfer"
            f"{'s' if rec.n_transfers != 1 else ''}**"
        )
        for move in rec.moves:
            st.markdown(
                f"- **Sell** {move.player_out.web_name} "
                f"({move.player_out.club_short}) "
                f"→ **Buy** {move.player_in.web_name} "
                f"({move.player_in.club_short})  \n"
                f"  Sell {_money(move.sell_price)} · Buy {_money(move.buy_price)}"
            )
        if rec.hits:
            st.warning(
                f"Includes a **{rec.hits}-hit (−{rec.hit_cost} pts)**. "
                "Only take it if the projected gain sticks."
            )
        else:
            st.info("No hit — within your free transfers.")

    m1, m2, m3 = st.columns(3)
    m1.metric("ΔxPts vs hold", f"{rec.xpts_gain_vs_roll:+.1f}")
    m2.metric("Objective (xPts−hits)", f"{rec.objective:.1f}")
    m3.metric("Bank after", _money(rec.bank_after))

    if result.why:
        with st.expander("Why this recommendation?", expanded=True):
            for b in result.why.bullets:
                st.markdown(f"- {b}")
            st.markdown("**Risks**")
            for r in result.why.risks:
                st.markdown(f"- {r}")

    tab_rec, tab_xpts, tab_squad, tab_alts, tab_chips = st.tabs(
        [
            "Plans & strategy",
            "xPts table",
            "Squad",
            "Other options",
            "Chips",
        ]
    )

    with tab_rec:
        st.markdown("### Compare plans")
        cols = st.columns(3)
        for col, label, plan in (
            (cols[0], "Hold", search.roll),
            (cols[1], "Best single transfer", search.best_one),
            (cols[2], "Best two transfers", search.best_two),
        ):
            with col:
                st.markdown(f"**{label}**")
                if plan is None:
                    st.write("No option found")
                    continue
                st.write(_plan_title(plan))
                st.caption(
                    f"Hits: {plan.hits} · "
                    f"ΔxPts: {plan.xpts_gain_vs_roll:+.1f} · "
                    f"Obj: {plan.objective:.1f}"
                )

        if result.strategy:
            st.markdown(
                f"### Multi-GW strategy (~{result.strategy.horizon} GW look)"
            )
            st.info(
                f"**Preferred:** {result.strategy.preferred.title} "
                f"(~{result.strategy.preferred.horizon_gain:+.1f} xPts)"
            )
            for opt in result.strategy.options:
                st.markdown(
                    f"- **{opt.title}** — {opt.detail} "
                    f"(gain {opt.horizon_gain:+.1f})"
                )

    with tab_xpts:
        st.markdown("### Projected xPts by player (horizon)")
        st.caption(
            "Separate from transfer desirability. Built from P(start), xG/xA, "
            "CS proxies, DefCon, and opponent strength — rules-based V1."
        )
        rows = []
        scored_map = {p.element_id: p for p in result.owned_scored}
        for sp in squad.players:
            p = scored_map.get(sp.element_id)
            if not p:
                continue
            rows.append(
                {
                    "Player": p.web_name,
                    "Pos": p.position.short_name,
                    "Club": p.club_short,
                    "P(start)": round(p.p_start, 2),
                    "xMins": round(p.xmins, 0),
                    "xPts (horizon)": round(p.xpts_horizon, 1),
                    "Desirability": round(p.score, 1),
                    "Risk": f"{p.risk:.0%}",
                    "Fixtures": p.fixtures.summary,
                }
            )
        rows.sort(key=lambda r: r["xPts (horizon)"], reverse=True)
        st.dataframe(rows, use_container_width=True, hide_index=True)

        # Detail for top player
        if result.owned_scored:
            top = max(result.owned_scored, key=lambda p: p.xpts_horizon)
            st.markdown(f"#### Fixture breakdown — {top.web_name}")
            st.dataframe(
                top.horizon_xpts.as_table(),
                use_container_width=True,
                hide_index=True,
            )

    with tab_squad:
        st.markdown("### Current squad")
        scored_map = {p.element_id: p for p in result.owned_scored}
        rows = []
        for p in squad.players:
            s = scored_map.get(p.element_id)
            flag = "C" if p.is_captain else ("VC" if p.is_vice_captain else "")
            rows.append(
                {
                    "#": p.squad_slot,
                    "Pos": p.position.short_name,
                    "Club": p.club_short,
                    "Player": p.web_name,
                    "Role": "XI" if p.is_starter else "Bench",
                    "C/VC": flag,
                    "Buy": _money(p.purchase_price),
                    "Sell": _money(p.selling_price),
                    "Now": _money(p.now_cost),
                    "P(start)": round(s.p_start, 2) if s else None,
                    "xPts": round(s.xpts_horizon, 1) if s else None,
                    "Status": (
                        s.form.status.upper()
                        if s and s.form.status != "a"
                        else ""
                    ),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.markdown("### Bench order (suggested)")
        for i, p in enumerate(lu.bench, start=1):
            st.write(
                f"{i}. {p.position.short_name} {p.club_short} **{p.web_name}** "
                f"— {p.xpts_horizon:.1f} xPts"
            )

    with tab_alts:
        st.markdown("### Other strong plans")
        alt_rows = []
        for i, plan in enumerate(search.top_plans[:6], start=1):
            alt_rows.append(
                {
                    "#": i,
                    "Plan": _plan_title(plan),
                    "Hits": plan.hits,
                    "ΔxPts": round(plan.xpts_gain_vs_roll, 1),
                    "Objective": round(plan.objective, 1),
                    "Bank after": _money(plan.bank_after),
                }
            )
        st.dataframe(alt_rows, use_container_width=True, hide_index=True)

    with tab_chips:
        st.markdown("### Chip suggestions (simple V1)")
        st.caption(
            "Uses horizon xPts heuristics — not a full fixture-blank solver yet."
        )
        if not result.chips:
            st.write("No chip advice available.")
        for chip in result.chips:
            icon = "✅" if chip.worth_considering else "⏳"
            st.markdown(
                f"{icon} **{chip.label}** — est. gain ~{chip.estimated_gain:.1f}  \n"
                f"{chip.rationale}"
            )


if __name__ == "__main__":
    main()
