"""T2 Allocation — où l'argent est placé."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from aim.app.config import CATEGORICAL, COLORS, PLOTLY_LAYOUT, STYLE_COLOR_MAP
from aim.app.format_utils import fmt_int, fmt_pct, fmt_usd
from aim.app.loaders import q


def _fmt_long_date(d) -> str:
    mois = ["janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    dt = pd.Timestamp(d)
    return f"{dt.day} {mois[dt.month - 1]} {dt.year}"


def render() -> None:
    snapshot = st.session_state["snapshot"]

    st.markdown(f"## Allocation du portefeuille au {_fmt_long_date(snapshot)}")

    st.markdown("### Généraliste vs Thématique")
    st.markdown(
        "*Un fonds est **Thématique** si son nom contient un marqueur explicite "
        "(géographique : Asia, China, Europe… ; ou de style : Energy, Tech, Secondaries, Venture…). "
        "Sinon **Généraliste** — majoritairement des fonds buyout US (Blackstone, KKR, Carlyle, "
        "Apollo…), mais aussi quelques fonds européens et multi-régions sans focus explicite.*"
    )

    split = q(
        "SELECT kind, n_funds, committed, nav_residual, median_irr "
        "FROM v_generalist_split WHERE as_of_date = ? ORDER BY kind",
        params=(snapshot,),
    )

    c1, c2 = st.columns([1, 2])

    fig = px.pie(
        split, values="committed", names="kind",
        color="kind",
        color_discrete_map={"Généraliste": COLORS["generalist"], "Thématique": COLORS["thematic"]},
        hole=0.6,
    )
    fig.update_traces(
        texttemplate="%{label}<br>%{percent}",
        hovertemplate="<b>%{label}</b><br>"
                      "Capital engagé : %{customdata[1]:,.0f} $<br>"
                      "Nombre de fonds : %{customdata[0]}<br>"
                      "Part : %{percent}<extra></extra>",
        customdata=split[["n_funds", "committed"]],
        textfont=dict(family="Inter", size=12, color="#ffffff"),
        marker=dict(line=dict(color="#ffffff", width=2)),
    )
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Capital engagé par nature", font=dict(size=14)),
        showlegend=False, height=360,
    )
    c1.plotly_chart(fig, use_container_width=True)

    c1.markdown(
        f"<div style='font-size:0.85rem;color:#5a5a5a;margin-top:0.3rem'>"
        f"<b>Généraliste</b> · {split.loc[split['kind']=='Généraliste','n_funds'].iloc[0]} fonds · "
        f"{split.loc[split['kind']=='Généraliste','committed'].iloc[0]/1e9:.1f} Md $ engagés"
        f"<br><b>Thématique</b> · {split.loc[split['kind']=='Thématique','n_funds'].iloc[0]} fonds · "
        f"{split.loc[split['kind']=='Thématique','committed'].iloc[0]/1e9:.1f} Md $ engagés"
        f"</div>",
        unsafe_allow_html=True,
    )

    evo = q("""
        SELECT as_of_date, kind, committed, n_funds
        FROM v_generalist_split ORDER BY as_of_date, kind
    """)
    fig2 = px.area(
        evo, x="as_of_date", y="committed", color="kind",
        color_discrete_map={"Généraliste": COLORS["generalist"], "Thématique": COLORS["thematic"]},
        groupnorm="percent",
    )
    fig2.update_traces(line=dict(width=0))
    fig2.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Part Généraliste / Thématique sur 20 snapshots (% du capital engagé)",
                   font=dict(size=14)),
        xaxis_title="", yaxis_title="% du capital engagé",
        height=360, hovermode="x unified",
    )
    c2.plotly_chart(fig2, use_container_width=True)

    st.divider()

    st.markdown("### Évolution thématique — décembre 2014 à septembre 2025")

    c1, c2 = st.columns(2)

    geo_evo = q("""
        SELECT as_of_date, theme_geo, committed
        FROM v_theme_geo_evo ORDER BY as_of_date, theme_geo
    """)
    if len(geo_evo):
        fig = px.area(
            geo_evo, x="as_of_date", y="committed", color="theme_geo",
            color_discrete_sequence=CATEGORICAL,
        )
        fig.update_traces(line=dict(width=0))
        fig.update_layout(
            **PLOTLY_LAYOUT,
            title=dict(text="Capital engagé par zone géographique", font=dict(size=14)),
            xaxis_title="", yaxis_title="USD",
            height=400, hovermode="x unified",
        )
        c1.plotly_chart(fig, use_container_width=True)

    style_evo = q("""
        SELECT as_of_date, theme_style, committed
        FROM v_theme_style_evo ORDER BY as_of_date, theme_style
    """)
    if len(style_evo):
        fig = px.area(
            style_evo, x="as_of_date", y="committed", color="theme_style",
            color_discrete_map=STYLE_COLOR_MAP,
        )
        fig.update_traces(line=dict(width=0))
        fig.update_layout(
            **PLOTLY_LAYOUT,
            title=dict(text="Capital engagé par style et secteur", font=dict(size=14)),
            xaxis_title="", yaxis_title="USD",
            height=400, hovermode="x unified",
        )
        c2.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.markdown(f"### Concentration par GP family — au {_fmt_long_date(snapshot)}")
    st.markdown(
        "*La « GP family » est extraite du nom du fonds (avec une table d'alias pour les gros gérants : "
        "Blackstone, KKR, Carlyle…). Les SPVs et fonds custom dont le nom ne correspond à aucun "
        "gérant identifiable sont comptés individuellement — d'où un nombre total élevé.*"
    )

    conc = q("SELECT * FROM v_gp_concentration").iloc[0]
    c = st.columns(3)
    c[0].metric("GP families au portefeuille", fmt_int(conc["n_gps"]))
    c[1].metric("Part top-5 GPs", fmt_pct(conc["pct_top5"]))
    c[2].metric("Part top-10 GPs", fmt_pct(conc["pct_top10"]))

    st.markdown(
        f"<div style='font-size:0.85rem;color:#5a5a5a;margin:0.4rem 0 1rem 0'>"
        f"Le tableau ci-dessous affiche le <b>Top 20</b> sur les {int(conc['n_gps'])} GP families.</div>",
        unsafe_allow_html=True,
    )

    top_gps = q("""
        SELECT rank_committed, gp_family, n_funds, committed, pct_of_total, cum_pct,
               dpi, tvpi, median_irr
        FROM v_gp_stats WHERE gp_family IS NOT NULL
        ORDER BY rank_committed LIMIT 20
    """)
    top_gps_disp = top_gps.assign(
        committed=top_gps["committed"].apply(lambda x: fmt_usd(x, scale="B")),
        pct_of_total=top_gps["pct_of_total"].apply(lambda x: fmt_pct(x)),
        cum_pct=top_gps["cum_pct"].apply(lambda x: fmt_pct(x)),
        dpi=top_gps["dpi"].apply(lambda x: f"{x:.2f}×" if x else "—"),
        tvpi=top_gps["tvpi"].apply(lambda x: f"{x:.2f}×" if x else "—"),
        median_irr=top_gps["median_irr"].apply(lambda x: fmt_pct(x) if x else "—"),
    ).rename(columns={
        "rank_committed": "Rang",
        "gp_family": "GP family",
        "n_funds": "Fonds",
        "committed": "Engagé",
        "pct_of_total": "% total",
        "cum_pct": "% cumulé",
        "dpi": "DPI",
        "tvpi": "TVPI",
        "median_irr": "IRR médian",
    })
    st.dataframe(top_gps_disp, hide_index=True, use_container_width=True)
