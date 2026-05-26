"""T5 PME — Public Market Equivalent vs S&P 500 TR."""
from __future__ import annotations

import math

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from aim.app.config import COLORS, PLOTLY_LAYOUT
from aim.app.format_utils import fmt_int, fmt_pct
from aim.app.loaders import q


def _fmt_alpha(x: float | None) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x * 100:.1f}%"


def render() -> None:
    st.markdown("## PME — Private Market Equivalent vs S&P 500 TR")
    st.markdown(
        "*PME Kaplan-Schoar = (Σ distributions × I_T/I_t + NAV_T) / (Σ calls × I_T/I_t). "
        "PME > 1 signifie que le fonds bat l'indice.*  \n"
        "*Estimé : CalPERS publie à chaque snapshot des **flux cumulés** "
        "(cash in et cash out cumulés depuis l'origine du fonds), pas les flux unitaires datés. "
        "Les calls et distributions de chaque période sont donc **reconstitués par différence "
        "entre deux snapshots consécutifs** et datés en fin de trimestre — c'est une "
        "approximation standard mais qui lisse les flux intra-période. "
        "Indice utilisé : ^SP500TR (S&P 500 Total Return) via yfinance.*"
    )

    stats = q("""
        SELECT
            COUNT(*) AS n,
            MEDIAN(pme_ks) AS pme_med,
            AVG(pme_ks) AS pme_mean,
            COUNT(*) FILTER (WHERE pme_ks > 1) AS n_above,
            COUNT(*) FILTER (WHERE pme_ks < 1) AS n_below,
            MEDIAN(direct_alpha)*100 AS da_med
        FROM pme_fund WHERE pme_ks IS NOT NULL
    """).iloc[0]

    c = st.columns(5)
    c[0].metric("Fonds avec PME calculable", fmt_int(stats["n"]))
    c[1].metric("PME médian", f"{stats['pme_med']:.2f}")
    c[2].metric("Fonds > indice", fmt_int(stats["n_above"]))
    c[3].metric("Fonds < indice", fmt_int(stats["n_below"]))
    c[4].metric("Direct Alpha médian", fmt_pct(stats["da_med"]))

    if stats["pme_med"] >= 1.0:
        st.markdown(
            f"<div style='background:#f0f4f8;border-left:3px solid #1a3a5c;padding:0.7rem 1rem;"
            f"margin:0.8rem 0;color:#1a3a5c;font-size:0.9rem'>"
            f"Médiane PME = <b>{stats['pme_med']:.2f}</b> → portefeuille <b>au-dessus</b> du S&P 500 TR"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div style='background:#f8f0f0;border-left:3px solid #9c2a2a;padding:0.7rem 1rem;"
            f"margin:0.8rem 0;color:#9c2a2a;font-size:0.9rem'>"
            f"Médiane PME = <b>{stats['pme_med']:.2f}</b> → portefeuille <b>sous</b> le S&P 500 TR"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    st.markdown("### PME par millésime")

    vintage = q("""
        SELECT vintage_year, n_funds, pme_ks_median, pme_ks_mean, pme_ks_pooled,
               direct_alpha_median
        FROM v_pme_vintage WHERE n_funds >= 3 ORDER BY vintage_year
    """)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=vintage["vintage_year"], y=vintage["pme_ks_median"],
        name="PME médian", marker_color=COLORS["primary"],
        text=vintage["pme_ks_median"].apply(lambda x: f"{x:.2f}"),
        textposition="outside",
        textfont=dict(size=10),
    ))
    fig.add_trace(go.Scatter(
        x=vintage["vintage_year"], y=vintage["pme_ks_pooled"],
        mode="lines+markers", name="PME pondéré (par capital appelé)",
        line=dict(color=COLORS["accent"], width=2),
        marker=dict(size=7),
    ))
    fig.add_hline(y=1.0, line_dash="dash", line_color=COLORS["neutral_light"],
                  annotation_text="Indice = 1.0", annotation_position="right",
                  annotation_font=dict(size=10, color=COLORS["neutral"]))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="PME par vintage — médiane et pondéré", font=dict(size=14)),
        xaxis_title="Vintage year", yaxis_title="PME (×)",
        height=450, hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        "<div style='font-size:0.85rem;color:#5a5a5a;margin-top:0.5rem'>"
        "Lecture analytique : les vintages antérieurs à 2014 affichent un PME ≥ 1.2 — le PE a "
        "clairement battu le coté pendant cette période. Depuis le vintage 2015-2016, le PME flotte "
        "autour de 1.0 — le PE a perdu son edge face à un S&P 500 TR boosté par le QE puis le ZIRP. "
        "Les vintages 2023-2024 sont encore très immatures (NAV terminale = mark courant)."
        "</div>",
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown("### Distribution des PME individuels")

    pme_all = q("""
        SELECT fund_key, fund_name_canonical, vintage_year, gp_family,
               pme_ks, direct_alpha, sum_called_nominal, nav_terminal_nominal,
               is_thematic
        FROM pme_fund WHERE pme_ks IS NOT NULL
    """)

    fig = px.histogram(
        pme_all, x="pme_ks", nbins=40,
        color_discrete_sequence=[COLORS["primary"]],
    )
    fig.add_vline(x=1.0, line_dash="dash", line_color=COLORS["negative"],
                  annotation_text="Indice = 1.0", annotation_position="top",
                  annotation_font=dict(size=10))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Distribution des PME (fonds individuels)", font=dict(size=14)),
        xaxis_title="PME Kaplan-Schoar", yaxis_title="Nombre de fonds",
        height=400, bargap=0.05,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.markdown("### Meilleurs et moins bons PME")
    c1, c2 = st.columns(2)
    top = pme_all.nlargest(15, "pme_ks")[["fund_name_canonical", "vintage_year", "gp_family", "pme_ks"]]
    top["pme_ks"] = top["pme_ks"].apply(lambda x: f"{x:.2f}")
    top = top.rename(columns={"fund_name_canonical": "Fonds", "vintage_year": "Vintage",
                              "gp_family": "GP", "pme_ks": "PME"})
    c1.markdown("**Top 15 PME**")
    c1.dataframe(top, hide_index=True, use_container_width=True)

    bot = pme_all.nsmallest(15, "pme_ks")[["fund_name_canonical", "vintage_year", "gp_family", "pme_ks"]]
    bot["pme_ks"] = bot["pme_ks"].apply(lambda x: f"{x:.2f}")
    bot = bot.rename(columns={"fund_name_canonical": "Fonds", "vintage_year": "Vintage",
                              "gp_family": "GP", "pme_ks": "PME"})
    c2.markdown("**Bottom 15 PME**")
    c2.dataframe(bot, hide_index=True, use_container_width=True)
