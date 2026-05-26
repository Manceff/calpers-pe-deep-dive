"""T3 Fonds — drill-down par fonds."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from aim.app.config import COLORS, PLOTLY_LAYOUT, chart_layout
from aim.app.format_utils import fmt_mult, fmt_pct, fmt_usd
from aim.app.loaders import last_snapshot, q

MIN_SNAPSHOTS = 10


def _fmt_long_date(d) -> str:
    mois = ["janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    dt = pd.Timestamp(d)
    return f"{dt.day} {mois[dt.month - 1]} {dt.year}"


def _pick_unit(max_value: float) -> tuple[float, str]:
    if max_value is None or max_value <= 0:
        return 1e6, "M $"
    if max_value >= 1e9:
        return 1e9, "Md $"
    if max_value >= 1e6:
        return 1e6, "M $"
    if max_value >= 1e3:
        return 1e3, "k $"
    return 1.0, "$"


def render() -> None:
    st.markdown("## Drill-down par fonds")

    last_d = last_snapshot()
    st.markdown(
        f"<div style='font-size:0.9rem;color:#5a5a5a;margin-bottom:0.8rem'>"
        f"Sélection limitée aux fonds présents au {_fmt_long_date(last_d)} et ayant au moins "
        f"{MIN_SNAPSHOTS} snapshots reportés.</div>",
        unsafe_allow_html=True,
    )

    funds = q(
        f"""
        SELECT d.fund_key, d.fund_name_canonical, d.vintage_year, d.gp_family,
               d.last_committed, d.n_snapshots
        FROM dim_fund d
        WHERE d.last_seen >= ?
          AND d.n_snapshots >= {MIN_SNAPSHOTS}
        ORDER BY d.fund_name_canonical
        """,
        params=(last_d,),
    )
    if len(funds) == 0:
        st.warning("Aucun fonds éligible.")
        return

    st.markdown(
        f"<div style='font-size:0.85rem;color:#5a5a5a'>{len(funds)} fonds dans le panel (sur 747 fonds dans l'historique complet).</div>",
        unsafe_allow_html=True,
    )

    label_map = {
        f"{r['fund_name_canonical']}  ·  vintage {r['vintage_year']}  ·  "
        f"{fmt_usd(r['last_committed'])}": r["fund_key"]
        for _, r in funds.iterrows()
    }
    label = st.selectbox("Fonds", options=list(label_map.keys()), index=0, label_visibility="collapsed")
    fund_key = label_map[label]

    info = q("SELECT * FROM dim_fund WHERE fund_key = ?", params=(fund_key,)).iloc[0]
    series = q(
        "SELECT as_of_date, capital_committed, cash_in, cash_out, cash_out_rv, "
        "nav_residual, unfunded, dpi, tvpi, rvpi, called_pct, net_irr, "
        "investment_multiple, age_years "
        "FROM v_fund_360 WHERE fund_key = ? ORDER BY as_of_date",
        params=(fund_key,),
    )
    last = series.iloc[-1]
    n_snap = len(series)
    has_irr = series["net_irr"].notna().any()
    age_max = float(series["age_years"].max()) if pd.notna(series["age_years"].max()) else None

    max_flow = max(
        series[["capital_committed", "cash_in", "cash_out", "cash_out_rv"]].max().max() or 0,
        info.get("last_committed") or 0,
    )
    div, unit = _pick_unit(max_flow)

    st.markdown(f"### {info['fund_name_canonical']}")

    c = st.columns(5)
    c[0].metric("Vintage", str(int(info["vintage_year"])) if info["vintage_year"] else "—")
    c[1].metric("GP family", info["gp_family"] or "—")
    c[2].metric("Statut", "Liquidé" if info["is_liquidated"] else "Actif")
    c[3].metric("Snapshots reportés", f"{n_snap} / 20")
    c[4].metric("Âge au dernier snapshot",
                f"{age_max:.1f} ans" if age_max is not None else "—")

    geo_list = q("SELECT theme_geo FROM dim_fund_geo WHERE fund_key = ?",
                 params=(fund_key,))["theme_geo"].tolist()
    style_list = q("SELECT theme_style FROM dim_fund_style WHERE fund_key = ?",
                   params=(fund_key,))["theme_style"].tolist()
    chips_html = ""
    if geo_list or style_list:
        chips = []
        for g in geo_list:
            chips.append(f"<span style='display:inline-block;background:#f0eeeb;border:1px solid #dad6cf;border-radius:3px;padding:0.15rem 0.5rem;margin:0 0.3rem 0.3rem 0;font-size:0.78rem;color:#1a3a5c;font-weight:500'>{g}</span>")
        for s in style_list:
            chips.append(f"<span style='display:inline-block;background:#f0eeeb;border:1px solid #dad6cf;border-radius:3px;padding:0.15rem 0.5rem;margin:0 0.3rem 0.3rem 0;font-size:0.78rem;color:#a67c3e;font-weight:500'>{s}</span>")
        chips_html = (
            "<div style='margin-top:0.6rem;font-size:0.85rem;color:#5a5a5a'>"
            "<b>Thèmes détectés (depuis le nom) :</b><br>"
            + "".join(chips) + "</div>"
        )
    else:
        chips_html = (
            "<div style='margin-top:0.6rem;font-size:0.85rem;color:#5a5a5a'>"
            "<b>Classification :</b> Généraliste (aucun marqueur thématique dans le nom).</div>"
        )
    st.markdown(chips_html, unsafe_allow_html=True)

    st.divider()

    st.markdown(f"### Snapshot du {_fmt_long_date(last['as_of_date'])}")

    c = st.columns(4)
    c[0].metric("Capital engagé", fmt_usd(last["capital_committed"]))
    c[1].metric("Capital appelé", fmt_usd(last["cash_in"]))
    c[2].metric("Distribué", fmt_usd(last["cash_out"]))
    c[3].metric("Valeur résiduelle", fmt_usd(last["nav_residual"]))

    c = st.columns(4)
    c[0].metric("DPI", fmt_mult(last["dpi"]) if pd.notna(last["dpi"]) else "—")
    c[1].metric("RVPI", fmt_mult(last["rvpi"]) if pd.notna(last["rvpi"]) else "—")
    c[2].metric("TVPI", fmt_mult(last["tvpi"]) if pd.notna(last["tvpi"]) else "—")
    c[3].metric("% appelé", fmt_pct(last["called_pct"] * 100) if pd.notna(last["called_pct"]) else "—")

    c = st.columns(3)
    c[0].metric("Net IRR (reporté CalPERS)",
                fmt_pct(last["net_irr"]) if pd.notna(last["net_irr"]) else "N/M")
    c[1].metric("Multiple (reporté CalPERS)",
                fmt_mult(last["investment_multiple"]) if pd.notna(last["investment_multiple"]) else "N/M")
    c[2].metric("Unfunded restant", fmt_usd(last["unfunded"]))

    if not has_irr:
        st.info(
            "Ce fonds est encore en J-curve (Net IRR reporté comme N/M = Not Meaningful par CalPERS). "
            "Les graphes IRR seront partiellement vides — normal pour les vintages très récents."
        )

    st.divider()

    st.markdown("### Trajectoire dans le temps")

    # Layout commun pour les 4 graphes — strictement uniforme pour alignement parfait.
    # Les marges l/r sont fixées larges pour absorber les variations de largeur des
    # labels d'axe Y (1 234 vs 1.5×) sans déformer la zone de tracé.
    CHART_HEIGHT = 420
    CHART_MARGIN = dict(l=70, r=70, t=60, b=100)
    LEGEND_BOTTOM = dict(orientation="h", yanchor="top", y=-0.22, x=0,
                         font=dict(size=10))

    c1, c2 = st.columns(2)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=series["as_of_date"], y=series["cash_in"] / div,
        mode="lines+markers", name="Cash in cumulé (appels)",
        line=dict(color=COLORS["accent"], width=2),
    ))
    fig.add_trace(go.Scatter(
        x=series["as_of_date"], y=series["cash_out"] / div,
        mode="lines+markers", name="Cash out cumulé (distributions)",
        line=dict(color=COLORS["primary_light"], width=2),
    ))
    fig.add_trace(go.Scatter(
        x=series["as_of_date"], y=series["cash_out_rv"] / div,
        mode="lines+markers", name="Cash out + Valeur résiduelle",
        line=dict(color=COLORS["primary"], width=2.5),
    ))
    fig.update_layout(
        **chart_layout(
            title=dict(text=f"Flux cumulés ({unit})", font=dict(size=13)),
            xaxis_title="", yaxis_title=unit,
            height=CHART_HEIGHT, hovermode="x unified",
            margin=CHART_MARGIN,
            legend=LEGEND_BOTTOM,
        )
    )
    c1.plotly_chart(fig, use_container_width=True)

    if series[["dpi", "rvpi", "tvpi"]].notna().any().any():
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=series["as_of_date"], y=series["dpi"],
            mode="lines+markers", name="DPI (déjà rendu)",
            line=dict(color=COLORS["accent"], width=2), connectgaps=True,
        ))
        fig.add_trace(go.Scatter(
            x=series["as_of_date"], y=series["rvpi"],
            mode="lines+markers", name="RVPI (latent)",
            line=dict(color=COLORS["primary_light"], width=2), connectgaps=True,
        ))
        fig.add_trace(go.Scatter(
            x=series["as_of_date"], y=series["tvpi"],
            mode="lines+markers", name="TVPI = DPI + RVPI",
            line=dict(color=COLORS["primary"], width=2.5), connectgaps=True,
        ))
        fig.add_hline(y=1.0, line_dash="dot", line_color=COLORS["neutral_light"])
        fig.update_layout(
            **chart_layout(
                title=dict(text="Multiples (× cash in)", font=dict(size=13)),
                xaxis_title="", yaxis_title="× cash in",
                height=CHART_HEIGHT, hovermode="x unified",
                margin=CHART_MARGIN,
                legend=LEGEND_BOTTOM,
            )
        )
        c2.plotly_chart(fig, use_container_width=True)
    else:
        c2.markdown(
            f"<div style='height:{CHART_HEIGHT}px;display:flex;align-items:center;justify-content:center;"
            f"background:#fafaf9;border:1px solid #e8e4dd;border-radius:4px;color:#5a5a5a;font-size:0.9rem'>"
            "Multiples non calculables (cash_in = 0 sur toute la série)."
            "</div>",
            unsafe_allow_html=True,
        )

    c1, c2 = st.columns(2)

    if has_irr:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=series["as_of_date"], y=series["net_irr"],
            mode="lines+markers", name="Net IRR (%)",
            line=dict(color=COLORS["primary"], width=2.5), connectgaps=True,
            marker=dict(size=7),
        ))
        fig.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral_light"])
        fig.update_layout(
            **chart_layout(
                title=dict(text="Maturation Net IRR (reporté par CalPERS)", font=dict(size=13)),
                xaxis_title="", yaxis_title="%",
                height=CHART_HEIGHT, hovermode="x unified",
                margin=CHART_MARGIN,
                showlegend=False,
            )
        )
        c1.plotly_chart(fig, use_container_width=True)
    else:
        c1.markdown(
            f"<div style='height:{CHART_HEIGHT}px;display:flex;align-items:center;justify-content:center;"
            f"background:#fafaf9;border:1px solid #e8e4dd;border-radius:4px;color:#5a5a5a;font-size:0.9rem;"
            f"text-align:center;padding:0 2rem'>"
            "Maturation Net IRR non disponible<br>CalPERS reporte N/M sur toute la série."
            "</div>",
            unsafe_allow_html=True,
        )

    period = q(
        "SELECT * FROM v_period_flows WHERE fund_key = ? ORDER BY as_of_date",
        params=(fund_key,),
    )
    if len(period):
        flow_div, flow_unit = _pick_unit(
            max(period["period_calls"].max() or 0, period["period_distributions"].max() or 0) * 4
        )
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=period["as_of_date"], y=-period["period_calls_annualized"] / flow_div,
            name=f"Appels annualisés ({flow_unit}/an)", marker_color=COLORS["accent"],
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2f} " + flow_unit + "/an<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=period["as_of_date"], y=period["period_distributions_annualized"] / flow_div,
            name=f"Distributions annualisées ({flow_unit}/an)", marker_color=COLORS["primary_light"],
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2f} " + flow_unit + "/an<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=period["as_of_date"], y=period["net_cashflow"].cumsum() / flow_div,
            mode="lines+markers", name=f"Cumul net depuis 1er snapshot ({flow_unit})",
            line=dict(color=COLORS["primary"], width=2.5), yaxis="y2",
        ))
        fig.update_layout(
            **chart_layout(
                title=dict(text="J-curve — flux annualisés + cumul net", font=dict(size=13)),
                xaxis_title="",
                yaxis=dict(title=f"Flux annualisé ({flow_unit}/an)"),
                yaxis2=dict(title=f"Cumul net ({flow_unit})", overlaying="y", side="right",
                            showgrid=False, linecolor="#dad6cf"),
                height=CHART_HEIGHT, hovermode="x unified", barmode="relative",
                margin=CHART_MARGIN,
                legend=LEGEND_BOTTOM,
            )
        )
        c2.plotly_chart(fig, use_container_width=True)
    else:
        c2.markdown(
            f"<div style='height:{CHART_HEIGHT}px;display:flex;align-items:center;justify-content:center;"
            f"background:#fafaf9;border:1px solid #e8e4dd;border-radius:4px;color:#5a5a5a;font-size:0.9rem;"
            f"text-align:center;padding:0 2rem'>"
            "J-curve non disponible<br>Fonds avec un seul snapshot."
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<div style='font-size:0.82rem;color:#5a5a5a;margin-top:0.5rem;line-height:1.5'>"
        "<b>Lecture du graphe J-curve.</b> Les barres représentent le rythme moyen "
        "d'<b>appels et de distributions sur la période entre deux snapshots</b>, ramené à une base "
        "annuelle ($ par an). C'est utile car la cadence des rapports CalPERS est irrégulière "
        "(annuelle 2014, semestrielle 2016-2023, trimestrielle 2024-2025) : sans annualisation, "
        "une barre couvrant 18 mois serait visuellement géante face à une barre couvrant 3 mois. "
        "La courbe <b>cumul net</b> additionne, snapshot après snapshot, les flux nets observés "
        "(distributions − appels). Elle <b>démarre à zéro au premier snapshot CalPERS</b> du fonds — "
        "ce n'est donc pas la J-curve historique complète depuis l'origine du fonds, mais "
        "uniquement la trajectoire visible dans la fenêtre de reporting. <i>Estimé : un trimestre "
        "mêle appels et distributions internes, FX et recyclage de capital possibles.</i>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown("### Détail snapshot par snapshot")
    disp = series.copy()
    for col in ["capital_committed", "cash_in", "cash_out", "cash_out_rv",
                "nav_residual", "unfunded"]:
        disp[col] = disp[col].apply(fmt_usd)
    for col in ["dpi", "rvpi", "tvpi"]:
        disp[col] = disp[col].apply(lambda x: f"{x:.2f}×" if pd.notna(x) else "—")
    disp["called_pct"] = disp["called_pct"].apply(
        lambda x: fmt_pct(x * 100) if pd.notna(x) else "—"
    )
    disp["net_irr"] = disp["net_irr"].apply(
        lambda x: fmt_pct(x) if pd.notna(x) else "N/M"
    )
    disp["investment_multiple"] = disp["investment_multiple"].apply(
        lambda x: f"{x:.2f}×" if pd.notna(x) else "N/M"
    )
    disp["age_years"] = disp["age_years"].apply(
        lambda x: f"{x:.1f}" if pd.notna(x) else "—"
    )
    disp["as_of_date"] = pd.to_datetime(disp["as_of_date"]).dt.strftime("%Y-%m-%d")
    disp = disp.rename(columns={
        "as_of_date": "Date",
        "capital_committed": "Engagé",
        "cash_in": "Cash in",
        "cash_out": "Cash out",
        "cash_out_rv": "Cash out + RV",
        "nav_residual": "NAV",
        "unfunded": "Unfunded",
        "called_pct": "% appelé",
        "net_irr": "Net IRR",
        "investment_multiple": "Multiple",
        "age_years": "Âge (ans)",
    })
    st.dataframe(disp, hide_index=True, use_container_width=True)
