"""Marzzy FPL Helper — clean Streamlit UI over live squad + optimiser."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Allow `streamlit run fpl_analyzer/ui/app.py` without an editable install.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fpl_analyzer.api.fpl_api import FplApiError  # noqa: E402
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
      .block-container { padding-top: 1.5rem; max-width: 1100px; }
      div[data-testid="stMetricValue"] { font-size: 1.35rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _money(tenths: int) -> str:
    return f"£{tenths / 10.0:.1f}m"


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


def _parse_team_id(raw: str) -> int | None:
    """Return a positive int Team ID, or None if the field is empty/invalid."""
    text = (raw or "").strip()
    if not text:
        return None
    if not text.isdigit():
        return None
    value = int(text)
    return value if value > 0 else None


def main() -> None:
    st.title("FPL Helper")
    st.caption("Squad insights, transfer ideas, and a suggested starting XI.")

    with st.sidebar:
        st.header("Your team")
        team_id_raw = st.text_input(
            "FPL Team ID",
            value="",
            placeholder="Enter team ID",
            help=(
                "The number in your FPL team URL: "
                "fantasy.premierleague.com/entry/<Team ID>/"
            ),
        )
        with st.expander("How do I find my Team ID?"):
            st.markdown(
                """
1. Go to [fantasy.premierleague.com](https://fantasy.premierleague.com) and sign in  
2. Open **Points** (or your squad / team page)  
3. Look at the browser URL — it looks like:  
   `https://fantasy.premierleague.com/entry/1234567/`  
4. The number after `/entry/` is your **Team ID** (example: `1234567`)
                """.strip()
            )
        horizon = st.slider(
            "Fixture look-ahead (gameweeks)",
            min_value=1,
            max_value=5,
            value=3,
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
            "Data comes from the official Fantasy Premier League API. "
            "Free transfers are estimated from public history."
        )

    if not load and "result" not in st.session_state:
        st.info(
            "Enter your **Team ID** in the sidebar, then click **Load team** "
            "to get started. Use the help tip if you’re not sure where to find it."
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
                st.session_state["team_id"] = parsed_id
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

    # --- Header ---
    st.subheader(squad.team_name)
    st.write(f"Manager · {squad.manager_name}")
    for note in analysis.notes:
        st.caption(note)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Gameweek", f"GW{analysis.target_event}")
    c2.metric("Bank", _money(squad.bank))
    c3.metric("Squad value", _money(squad.team_value))
    c4.metric(
        "Free transfers",
        "—" if squad.free_transfers is None else str(squad.free_transfers),
    )
    c5.metric("Transfers this GW", str(squad.event_transfers))

    tab_rec, tab_squad, tab_xi, tab_alts = st.tabs(
        ["Recommendation", "Squad", "Suggested XI", "Other options"]
    )

    # --- Recommendation ---
    with tab_rec:
        st.markdown("### What to do")
        if rec.is_roll:
            st.success("**Hold your free transfer** — no moves beat standing still.")
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
                    f"  Sell {_money(move.sell_price)} · "
                    f"Buy {_money(move.buy_price)}"
                )
            if rec.hits:
                st.warning(
                    f"This uses a **{rec.hits}-point hit** (−{rec.hit_cost} pts). "
                    "Only take it if the upgrade feels worth it."
                )
            else:
                st.info("No hit — within your free transfers.")

        m1, m2, m3 = st.columns(3)
        m1.metric("Gain vs hold", f"{rec.gain_vs_roll:+.1f}")
        m2.metric("Next-GW xPts vs hold", f"{rec.xpts_gain_vs_roll:+.1f}")
        m3.metric("Bank after", _money(rec.bank_after))

        lu = rec.lineup
        st.markdown("### Captain & vice")
        st.markdown(
            f"**Captain:** {lu.captain.web_name} ({lu.captain.club_short})  \n"
            f"**Vice:** {lu.vice.web_name} ({lu.vice.club_short})"
        )

        # Quick compare cards
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
                    f"Gain: {plan.gain_vs_roll:+.1f} · "
                    f"xPts: {plan.xpts_gain_vs_roll:+.1f}"
                )

    # --- Squad ---
    with tab_squad:
        st.markdown("### Current squad")
        score_by_id = {a.squad_player.element_id: a for a in analysis.players}
        rows = []
        for p in squad.players:
            a = score_by_id.get(p.element_id)
            flag = ""
            if p.is_captain:
                flag = "C"
            elif p.is_vice_captain:
                flag = "VC"
            status = ""
            if a and a.form.status and a.form.status != "a":
                status = a.form.status.upper()
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
                    "xPts": round(a.xpts, 1) if a else None,
                    "Score": round(a.score, 1) if a else None,
                    "Avail": (
                        f"{a.form.availability * 100:.0f}%" if a else None
                    ),
                    "Status": status,
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)

        st.markdown("### Player rankings")
        rank_rows = []
        for i, a in enumerate(analysis.ranked, start=1):
            sp = a.squad_player
            rank_rows.append(
                {
                    "Rank": i,
                    "Player": sp.web_name,
                    "Pos": sp.position.short_name,
                    "Club": sp.club_short,
                    "xPts": round(a.xpts, 1),
                    "Form": round(a.form.form, 1),
                    "Fixtures": a.fixtures.summary,
                    "Score": round(a.score, 1),
                }
            )
        st.dataframe(rank_rows, use_container_width=True, hide_index=True)

    # --- Suggested XI ---
    with tab_xi:
        lu = rec.lineup
        st.markdown(
            f"### Starting XI · {lu.formation_label}  \n"
            f"Captain **{lu.captain.web_name}** · "
            f"Vice **{lu.vice.web_name}**"
        )
        xi_rows = []
        for p in lu.xi:
            tag = ""
            if p.element_id == lu.captain.element_id:
                tag = "C"
            elif p.element_id == lu.vice.element_id:
                tag = "VC"
            xi_rows.append(
                {
                    "Pos": p.position.short_name,
                    "Club": p.club_short,
                    "Player": p.web_name,
                    "xPts": round(p.xpts, 1),
                    "Score": round(p.score, 1),
                    "C/VC": tag,
                }
            )
        st.dataframe(xi_rows, use_container_width=True, hide_index=True)

        st.markdown("### Bench order")
        bench_rows = [
            {
                "Order": i,
                "Pos": p.position.short_name,
                "Club": p.club_short,
                "Player": p.web_name,
                "Score": round(p.score, 1),
            }
            for i, p in enumerate(lu.bench, start=1)
        ]
        st.dataframe(bench_rows, use_container_width=True, hide_index=True)

    # --- Alternatives ---
    with tab_alts:
        st.markdown("### Other strong plans")
        alt_rows = []
        for i, plan in enumerate(search.top_plans[:6], start=1):
            alt_rows.append(
                {
                    "#": i,
                    "Plan": _plan_title(plan),
                    "Hits": plan.hits,
                    "Gain": round(plan.gain_vs_roll, 1),
                    "xPts gain": round(plan.xpts_gain_vs_roll, 1),
                    "Bank after": _money(plan.bank_after),
                }
            )
        st.dataframe(alt_rows, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
