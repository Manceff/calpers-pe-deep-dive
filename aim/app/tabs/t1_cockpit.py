"""T1 Cockpit — KPIs portefeuille + évolution 2014-2025."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from aim.app.config import COLORS, PLOTLY_LAYOUT
from aim.app.format_utils import fmt_int, fmt_mult, fmt_pct, fmt_usd
from aim.app.loaders import q


def _fmt_long_date(d) -> str:
    mois = ["janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    dt = pd.Timestamp(d)
    return f"{dt.day} {mois[dt.month - 1]} {dt.year}"


def render() -> None:
    snapshot = st.session_state["snapshot"]

    st.markdown(
        "Ceci est un projet réalisé avec des données open source, fait par Mancef FERRAH. "
        "CalPERS (California Public Employees' Retirement System) est en effet le plus grand "
        "fonds de pension public américain. Il publie trimestriellement, conformément à la "
        "réglementation, la performance de chacun des fonds de Private Equity dans lesquels il "
        "a investi. Les 20 rapports trimestriels publiés entre décembre 2014 et septembre 2025 "
        "ont été consolidés pour analyser l'évolution du portefeuille, des engagements, des "
        "performances et de l'exposition par gérant, millésime et thématique."
    )
    st.divider()

    st.markdown(f"## État du portefeuille au {_fmt_long_date(snapshot)}")

    kpis = q(
        "SELECT * FROM v_snapshot_kpis WHERE as_of_date = ?",
        params=(snapshot,),
    ).iloc[0]

    c = st.columns(4)
    c[0].metric("Capital engagé", fmt_usd(kpis["committed"]))
    c[1].metric("Valeur résiduelle (NAV)", fmt_usd(kpis["nav_residual"]))
    c[2].metric("Distribué cumulé", fmt_usd(kpis["distributed"]))
    c[3].metric("Unfunded total", fmt_usd(kpis["unfunded_total"]))

    c = st.columns(4)
    c[0].metric("DPI portefeuille", fmt_mult(kpis["dpi"]))
    c[1].metric("TVPI portefeuille", fmt_mult(kpis["tvpi"]))
    c[2].metric("IRR médian", fmt_pct(kpis["median_irr"]))
    c[3].metric("Capital appelé", fmt_pct(kpis["called_pct"] * 100 if kpis["called_pct"] else None))

    c = st.columns(3)
    c[0].metric("Nombre de fonds actifs", fmt_int(kpis["n_funds"]))
    c[1].metric("Fonds matures (IRR reporté)", fmt_int(kpis["n_mature"]))
    c[2].metric("Nouveaux fonds (depuis le snapshot précédent)", fmt_int(kpis["n_entries"]))

    st.divider()

    st.markdown("## Évolution du portefeuille — décembre 2014 à septembre 2025")

    evo = q("""
        SELECT as_of_date, committed, called, distributed, out_rv, nav_residual,
               dpi, tvpi, median_irr
        FROM v_snapshot_kpis ORDER BY as_of_date
    """)

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=evo["as_of_date"], y=evo["committed"] / 1e9,
        mode="lines+markers", name="Capital engagé",
        line=dict(color=COLORS["primary"], width=2.5),
        marker=dict(size=6),
    ))
    fig1.add_trace(go.Scatter(
        x=evo["as_of_date"], y=evo["nav_residual"] / 1e9,
        mode="lines+markers", name="Valeur résiduelle (NAV)",
        line=dict(color=COLORS["primary_light"], width=2.5),
        marker=dict(size=6),
    ))
    fig1.add_trace(go.Scatter(
        x=evo["as_of_date"], y=evo["distributed"] / 1e9,
        mode="lines+markers", name="Distribué cumulé",
        line=dict(color=COLORS["accent"], width=2.5),
        marker=dict(size=6),
    ))
    fig1.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Capital engagé · NAV · Distribué (Md $)", font=dict(size=14)),
        xaxis_title="", yaxis_title="Md $",
        hovermode="x unified", height=400,
    )
    st.plotly_chart(fig1, width='stretch')

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=evo["as_of_date"], y=evo["dpi"], mode="lines+markers",
        name="DPI", line=dict(color=COLORS["accent"], width=2),
        marker=dict(size=5), yaxis="y1",
    ))
    fig2.add_trace(go.Scatter(
        x=evo["as_of_date"], y=evo["tvpi"], mode="lines+markers",
        name="TVPI", line=dict(color=COLORS["primary"], width=2.5),
        marker=dict(size=5), yaxis="y1",
    ))
    fig2.add_trace(go.Scatter(
        x=evo["as_of_date"], y=evo["median_irr"], mode="lines+markers",
        name="IRR médian (%)", line=dict(color=COLORS["neutral"], width=1.5, dash="dot"),
        marker=dict(size=4), yaxis="y2",
    ))
    layout2 = {**PLOTLY_LAYOUT}
    layout2["yaxis"] = {**PLOTLY_LAYOUT["yaxis"], "title": "Multiple", "side": "left"}
    fig2.update_layout(
        **layout2,
        title=dict(text="Performance · DPI · TVPI · IRR médian", font=dict(size=14)),
        xaxis_title="", height=400, hovermode="x unified",
        yaxis2=dict(title="IRR médian (%)", overlaying="y", side="right",
                    showgrid=False, linecolor="#dad6cf"),
    )
    st.plotly_chart(fig2, width='stretch')
