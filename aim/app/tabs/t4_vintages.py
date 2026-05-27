"""T4 Vintages — benchmark cohort, quartiles, courbes au même âge."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from aim.app.config import COLORS, PLOTLY_LAYOUT
from aim.app.format_utils import fmt_usd
from aim.app.loaders import q


def _fmt_long_date(d) -> str:
    mois = ["janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    dt = pd.Timestamp(d)
    return f"{dt.day} {mois[dt.month - 1]} {dt.year}"


def render() -> None:
    st.markdown("## Benchmark par millésime")
    snapshot = st.session_state["snapshot"]

    st.markdown(
        "*L'IRR utilisé est la valeur Net IRR reportée trimestriellement par CalPERS dans son "
        "fichier source — ce n'est pas une valeur recalculée. C'est l'IRR officiel du fonds tel "
        "que le gérant le communique à CalPERS (méthode standard PE : XIRR sur les flux LP datés, "
        "hors fees). Les fonds notés N/M (trop jeunes pour avoir un IRR matériel) sont exclus "
        "des agrégats.*"
    )

    st.markdown(f"### Dispersion IRR par millésime — snapshot du {_fmt_long_date(snapshot)}")
    st.markdown(
        "<div style='font-size:0.85rem;color:#5a5a5a;margin-bottom:0.5rem'>"
        "Boîtes Q1 / médiane / Q3 sur les fonds matures. Filtre : vintages avec au moins 5 fonds matures.</div>",
        unsafe_allow_html=True,
    )

    q_data = q(
        "SELECT vintage_year, n_mature, irr_q1, irr_med, irr_q3, mult_q1, mult_med, mult_q3 "
        "FROM v_vintage_quartiles WHERE as_of_date = ? AND n_mature >= 5 "
        "ORDER BY vintage_year",
        params=(snapshot,),
    )

    if len(q_data) == 0:
        st.info("Aucun vintage avec assez de fonds matures.")
    else:
        fig = go.Figure()
        for _, r in q_data.iterrows():
            fig.add_trace(go.Scatter(
                x=[r["vintage_year"], r["vintage_year"]],
                y=[r["irr_q1"], r["irr_q3"]],
                mode="lines",
                line=dict(color=COLORS["primary"], width=7),
                showlegend=False,
                hovertemplate=f"Vintage {int(r['vintage_year'])}<br>"
                              f"Q1 = {r['irr_q1']:.1f}%<br>"
                              f"Médiane = {r['irr_med']:.1f}%<br>"
                              f"Q3 = {r['irr_q3']:.1f}%<br>"
                              f"n = {int(r['n_mature'])}<extra></extra>",
            ))
        fig.add_trace(go.Scatter(
            x=q_data["vintage_year"], y=q_data["irr_med"],
            mode="markers+lines",
            name="Médiane IRR",
            marker=dict(color=COLORS["accent"], size=9, symbol="diamond"),
            line=dict(color=COLORS["accent"], width=1, dash="dot"),
        ))
        fig.update_layout(
            **PLOTLY_LAYOUT,
            title=dict(text="IRR Q1 / Médiane / Q3 par vintage (fonds matures)", font=dict(size=14)),
            xaxis_title="Vintage year", yaxis_title="IRR (%)",
            height=440, hovermode="closest", showlegend=False,
        )
        st.plotly_chart(fig, width='stretch')

    st.markdown("### Évolution de l'IRR médian par vintage × snapshot")

    heatmap_df = q("""
        SELECT vintage_year, as_of_date, median_irr, n_mature
        FROM v_vintage_stats
        WHERE median_irr IS NOT NULL AND n_mature >= 3
        ORDER BY vintage_year, as_of_date
    """)
    if len(heatmap_df):
        v_keep = heatmap_df.groupby("vintage_year").size()
        v_keep = v_keep[v_keep >= 4].index.tolist()
        heatmap_df = heatmap_df[heatmap_df["vintage_year"].isin(v_keep)]
        pivot = heatmap_df.pivot(index="vintage_year", columns="as_of_date", values="median_irr")
        pivot.columns = [str(c)[:10] for c in pivot.columns]
        fig = px.imshow(
            pivot,
            color_continuous_scale=[
                [0.0, "#9c2a2a"], [0.35, "#dad6cf"], [0.5, "#f0eeeb"],
                [0.65, "#b5a574"], [1.0, "#1a3a5c"],
            ],
            zmin=-10, zmax=25,
            aspect="auto",
            labels=dict(color="IRR médian (%)"),
        )
        fig.update_layout(
            **PLOTLY_LAYOUT,
            title=dict(text="IRR médian par vintage (lignes) × snapshot (colonnes)", font=dict(size=14)),
            xaxis_title="Snapshot", yaxis_title="Vintage year",
            height=500,
        )
        st.plotly_chart(fig, width='stretch')
        st.markdown(
            "<div style='font-size:0.78rem;color:#9a9a9a;margin-top:0.3rem'>"
            "Filtre : vintages présents dans au moins 4 snapshots avec au moins 3 fonds matures. "
            "Les vintages très récents (2023-2025) sont exclus — trop de fonds en N/M."
            "</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    st.markdown("### Rythme d'engagement par millésime")

    eng = q("""
        SELECT vintage_year,
               COUNT(DISTINCT fund_key) AS n_funds,
               SUM(last_committed) AS committed
        FROM dim_fund WHERE vintage_year IS NOT NULL
        GROUP BY vintage_year ORDER BY vintage_year
    """)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=eng["vintage_year"], y=eng["committed"] / 1e9,
        name="Capital engagé (Md $)",
        marker_color=COLORS["primary"],
        text=eng["committed"].apply(lambda x: fmt_usd(x, scale="B")),
        textposition="outside",
        textfont=dict(size=10),
    ))
    fig.add_trace(go.Scatter(
        x=eng["vintage_year"], y=eng["n_funds"],
        mode="lines+markers", name="Nombre de fonds",
        line=dict(color=COLORS["accent"], width=2),
        marker=dict(size=6),
        yaxis="y2",
    ))
    layout = {**PLOTLY_LAYOUT}
    layout["yaxis"] = {**PLOTLY_LAYOUT["yaxis"], "title": "Md $"}
    fig.update_layout(
        **layout,
        title=dict(text="Capital engagé et nombre de fonds par vintage", font=dict(size=14)),
        xaxis_title="Vintage year",
        yaxis2=dict(title="Nombre de fonds", overlaying="y", side="right",
                    showgrid=False, linecolor="#dad6cf"),
        height=440, hovermode="x unified",
    )
    st.plotly_chart(fig, width='stretch')

    st.divider()

    st.markdown("### Courbes au même âge — comparaison de vintages")
    st.markdown(
        "<div style='font-size:0.85rem;color:#5a5a5a;margin-bottom:0.5rem'>"
        "Médiane TVPI/DPI par cohort de vintage, en fonction de l'âge du fonds (années depuis "
        "vintage_year). Permet de comparer les vintages à âge équivalent plutôt qu'à date équivalente.</div>",
        unsafe_allow_html=True,
    )

    cohort_df = q("""
        SELECT vintage_year, age_floor, n_obs, median_tvpi, median_dpi
        FROM v_cohort_same_age WHERE n_obs >= 3
    """)
    all_vintages = sorted(cohort_df["vintage_year"].unique())
    default_v = [v for v in [2007, 2011, 2013, 2017, 2019, 2021] if v in all_vintages]
    selected = st.multiselect(
        "Vintages à comparer",
        options=all_vintages,
        default=default_v or all_vintages[-6:],
    )
    sub = cohort_df[cohort_df["vintage_year"].isin(selected)]

    c1, c2 = st.columns(2)
    fig = px.line(
        sub, x="age_floor", y="median_tvpi", color="vintage_year",
        markers=True,
        color_discrete_sequence=["#1a3a5c", "#4a6a8c", "#7a8aaa", "#a67c3e", "#b5a574", "#8a7050"],
        labels={"age_floor": "Âge (années)", "median_tvpi": "TVPI médian"},
    )
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="TVPI médian par âge", font=dict(size=14)),
        height=400, hovermode="x unified",
    )
    c1.plotly_chart(fig, width='stretch')

    fig = px.line(
        sub, x="age_floor", y="median_dpi", color="vintage_year",
        markers=True,
        color_discrete_sequence=["#1a3a5c", "#4a6a8c", "#7a8aaa", "#a67c3e", "#b5a574", "#8a7050"],
        labels={"age_floor": "Âge (années)", "median_dpi": "DPI médian"},
    )
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="DPI médian par âge", font=dict(size=14)),
        height=400, hovermode="x unified",
    )
    c2.plotly_chart(fig, width='stretch')
