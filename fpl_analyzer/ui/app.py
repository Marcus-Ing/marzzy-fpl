"""FPL Helper — compact header, top tabs, one focused view each."""

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
      .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1120px; }
      div[data-testid="stMetricValue"] { font-size: 1.15rem; }
      div[data-testid="stMetricLabel"] { font-size: 0.8rem; }
      /* Make tabs more obvious */
      button[data-baseweb="tab"] {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        padding: 0.55rem 1rem !important;
      }
      div[data-testid="stTabs"] { margin-top: 0.35rem; margin-bottom: 0.5rem; }
      .pitch {
        background: linear-gradient(180deg, #1b5e20 0%, #2e7d32 55%, #1b5e20 100%);
        border-radius: 14px; padding: 14px 10px 16px; color: #fff;
        border: 1px solid rgba(255,255,255,0.22);
      }
      .pitch-row {
        display: flex; justify-content: center; gap: 8px; flex-wrap: wrap;
        margin: 8px 0;
      }
      .shirt {
        background: rgba(0,0,0,0.32); border: 1px solid rgba(255,255,255,0.3);
        border-radius: 10px; min-width: 82px; max-width: 100px; padding: 7px 5px;
        text-align: center;
      }
      .shirt .name { font-weight: 700; font-size: 0.8rem; line-height: 1.15; }
      .shirt .meta { font-size: 0.68rem; opacity: 0.9; margin-top: 2px; }
      .shirt .xpts { font-size: 0.88rem; font-weight: 700; margin-top: 3px; }
      .shirt.cap { box-shadow: 0 0 0 2px #ffd54f; }
      .badge { display:inline-block; background:#ffd54f; color:#111;
               font-size:0.62rem; font-weight:800; padding:1px 5px; border-radius:6px; }
      .move-line { font-size: 1.02rem; margin: 0.25rem 0 0.5rem; }
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
        f'<div class="meta">{p.club_short}</div>'
        f'<div class="xpts">{p.xpts_horizon:.1f}</div>'
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
        f'<div style="text-align:center;opacity:.85;font-size:.8rem;margin-bottom:4px">'
        f"{lineup.formation_label} · Σ {lineup.xi_xpts:.1f} xPts · "
        f"C {lineup.captain.web_name} / VC {lineup.vice.web_name}"
        f"</div>"
        + "".join(rows_html)
        + "</div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.title("FPL Helper")

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
            st.caption("Enter a valid numeric Team ID.")
        st.caption("Data from the official FPL API.")

    if not load and "result" not in st.session_state:
        st.info(
            "Enter your **Team ID** in the sidebar, then click **Load team**."
        )
        st.stop()

    if load:
        if parsed_id is None:
            st.warning("Enter a valid numeric Team ID first.")
            st.stop()
        with st.spinner("Loading…"):
            try:
                st.session_state["result"] = _load(
                    parsed_id, int(horizon), int(max_transfers)
                )
            except FplApiError as exc:
                st.error(str(exc))
                st.stop()
            except Exception:
                st.error("Could not load that team. Check the Team ID and try again.")
                st.stop()

    result: OptimizationResult = st.session_state["result"]
    analysis = result.analysis
    squad = analysis.squad
    search = result.search
    rec = search.recommendation
    lu = rec.lineup

    # --- Compact header only (no wall of content) ---
    st.subheader(squad.team_name)
    st.caption(
        f"{squad.manager_name} · GW{analysis.target_event}"
        + (f" · {analysis.notes[0]}" if analysis.notes else "")
    )
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Bank", _money(squad.bank))
    h2.metric(
        "Free transfers",
        "—" if squad.free_transfers is None else str(squad.free_transfers),
    )
    h3.metric("Squad value", _money(squad.team_value))
    h4.metric("XI xPts", f"{lu.xi_xpts:.1f}")

    # --- Tabs at top of main content ---
    tab_overview, tab_plans, tab_xpts, tab_squad, tab_alts, tab_chips = st.tabs(
        [
            "Overview",
            "Plans & strategy",
            "xPts table",
            "Squad",
            "Other options",
            "Chips",
        ]
    )

    with tab_overview:
        left, right = st.columns((1.35, 1), gap="large")
        with left:
            render_pitch(lu)
        with right:
            st.markdown("#### Recommended move")
            if rec.is_roll:
                st.markdown(
                    '<p class="move-line"><strong>Hold</strong> your free transfer.</p>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<p class="move-line"><strong>'
                    f"{rec.n_transfers} transfer"
                    f"{'s' if rec.n_transfers != 1 else ''}"
                    f"</strong>"
                    f"{' · hit −' + str(rec.hit_cost) if rec.hits else ' · no hit'}"
                    f"</p>",
                    unsafe_allow_html=True,
                )
                for move in rec.moves:
                    st.markdown(
                        f"- {move.player_out.web_name} → "
                        f"**{move.player_in.web_name}** "
                        f"({_money(move.sell_price)} → {_money(move.buy_price)})"
                    )
            a, b = st.columns(2)
            a.metric("ΔxPts vs hold", f"{rec.xpts_gain_vs_roll:+.1f}")
            b.metric("Bank after", _money(rec.bank_after))

            if result.why:
                with st.expander("Why?", expanded=False):
                    for bullet in result.why.bullets:
                        st.markdown(f"- {bullet}")
                    st.markdown("**Risks**")
                    for risk in result.why.risks:
                        st.markdown(f"- {risk}")

    with tab_plans:
        st.markdown("##### Hold vs 1 vs 2 transfers")
        cols = st.columns(3)
        for col, label, plan in (
            (cols[0], "Hold", search.roll),
            (cols[1], "Best 1 transfer", search.best_one),
            (cols[2], "Best 2 transfers", search.best_two),
        ):
            with col:
                st.markdown(f"**{label}**")
                if plan is None:
                    st.caption("None")
                    continue
                st.write(_plan_title(plan))
                st.caption(
                    f"Hits {plan.hits} · ΔxPts {plan.xpts_gain_vs_roll:+.1f}"
                )

        if result.strategy:
            st.markdown(
                f"##### Across ~{result.strategy.horizon} gameweeks"
            )
            st.markdown(
                f"**Preferred:** {result.strategy.preferred.title} "
                f"({result.strategy.preferred.horizon_gain:+.1f})"
            )
            for opt in result.strategy.options:
                st.markdown(
                    f"- **{opt.title}** — gain {opt.horizon_gain:+.1f}"
                )

    with tab_xpts:
        scored_map = {p.element_id: p for p in result.owned_scored}
        rows = []
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
                    "xPts": round(p.xpts_horizon, 1),
                    "Risk": f"{p.risk:.0%}",
                }
            )
        rows.sort(key=lambda r: r["xPts"], reverse=True)
        st.dataframe(rows, use_container_width=True, hide_index=True)
        with st.expander("Fixture breakdown (top player)"):
            if result.owned_scored:
                top = max(result.owned_scored, key=lambda p: p.xpts_horizon)
                st.caption(top.web_name)
                st.dataframe(
                    top.horizon_xpts.as_table(),
                    use_container_width=True,
                    hide_index=True,
                )

    with tab_squad:
        scored_map = {p.element_id: p for p in result.owned_scored}
        rows = []
        for p in squad.players:
            s = scored_map.get(p.element_id)
            rows.append(
                {
                    "#": p.squad_slot,
                    "Pos": p.position.short_name,
                    "Club": p.club_short,
                    "Player": p.web_name,
                    "Role": "XI" if p.is_starter else "BN",
                    "Sell": _money(p.selling_price),
                    "xPts": round(s.xpts_horizon, 1) if s else None,
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)
        with st.expander("Suggested bench order"):
            for i, p in enumerate(lu.bench, start=1):
                st.write(
                    f"{i}. {p.web_name} ({p.club_short}) — {p.xpts_horizon:.1f}"
                )

    with tab_alts:
        alt_rows = [
            {
                "#": i,
                "Plan": _plan_title(plan),
                "Hits": plan.hits,
                "ΔxPts": round(plan.xpts_gain_vs_roll, 1),
            }
            for i, plan in enumerate(search.top_plans[:6], start=1)
        ]
        st.dataframe(alt_rows, use_container_width=True, hide_index=True)

    with tab_chips:
        if not result.chips:
            st.write("No chip advice available.")
        for chip in result.chips:
            mark = "Worth a look" if chip.worth_considering else "Probably wait"
            st.markdown(
                f"**{chip.label}** — {mark} (~{chip.estimated_gain:.1f})  \n"
                f"{chip.rationale}"
            )


if __name__ == "__main__":
    main()
