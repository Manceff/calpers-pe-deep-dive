"""T6 Data — consultation brute de chacun des 20 snapshots."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from aim.app.format_utils import fmt_pct, fmt_usd
from aim.app.loaders import all_snapshots, q


def _fmt_long_date(d) -> str:
    mois = ["janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    dt = pd.Timestamp(d)
    return f"{dt.day} {mois[dt.month - 1]} {dt.year}"


def render() -> None:
    st.markdown("## Données brutes — consultation par snapshot")
    st.markdown(
        "*Cette page donne accès à l'intégralité de la donnée consolidée. "
        "Pour chacun des 20 snapshots trimestriels publiés par CalPERS entre décembre 2014 "
        "et septembre 2025, vous pouvez consulter la ligne complète de chaque fonds : capital "
        "engagé, flux cumulés (cash in / cash out), valeur résiduelle, IRR et multiple reportés. "
        "Les colonnes Cash in, Cash out et Cash out + Valeur résiduelle sont **cumulatives** "
        "(pas des flux de période). Les valeurs N/M signifient Not Meaningful (fonds trop jeune "
        "pour qu'un IRR soit matériel).*"
    )

    snapshots = all_snapshots()
    snapshot = st.selectbox(
        "Snapshot à consulter",
        options=snapshots,
        index=len(snapshots) - 1,
        format_func=_fmt_long_date,
    )

    data = q(
        """
        SELECT fund_name, vintage_year,
               capital_committed, cash_in, cash_out, cash_out_rv,
               net_irr, investment_multiple
        FROM master_long
        WHERE as_of_date = ?
        ORDER BY fund_name
        """,
        params=(snapshot,),
    )

    summary = q(
        """
        SELECT COUNT(*) AS n_funds,
               SUM(capital_committed) AS committed,
               SUM(cash_in) AS called,
               SUM(cash_out) AS distributed,
               SUM(cash_out_rv) AS out_rv,
               COUNT(*) FILTER (WHERE net_irr IS NOT NULL) AS n_mature
        FROM master_long WHERE as_of_date = ?
        """,
        params=(snapshot,),
    ).iloc[0]

    c = st.columns(5)
    c[0].metric("Fonds reportés", f"{int(summary['n_funds'])}")
    c[1].metric("Capital engagé", fmt_usd(summary["committed"]))
    c[2].metric("Cash in cumulé", fmt_usd(summary["called"]))
    c[3].metric("Cash out cumulé", fmt_usd(summary["distributed"]))
    c[4].metric("Fonds matures (IRR)", f"{int(summary['n_mature'])}")

    st.divider()

    # Affichage formaté
    disp = data.copy()
    for col in ["capital_committed", "cash_in", "cash_out", "cash_out_rv"]:
        disp[col] = disp[col].apply(fmt_usd)
    disp["net_irr"] = disp["net_irr"].apply(lambda x: fmt_pct(x) if pd.notna(x) else "N/M")
    disp["investment_multiple"] = disp["investment_multiple"].apply(
        lambda x: f"{x:.2f}×" if pd.notna(x) else "N/M"
    )
    disp = disp.rename(columns={
        "fund_name": "Nom du fonds",
        "vintage_year": "Vintage",
        "capital_committed": "Capital engagé",
        "cash_in": "Cash in (cumulé)",
        "cash_out": "Cash out (cumulé)",
        "cash_out_rv": "Cash out + RV",
        "net_irr": "Net IRR",
        "investment_multiple": "Multiple",
    })
    st.dataframe(disp, hide_index=True, use_container_width=True, height=620)

    # Téléchargement CSV (données brutes non formatées)
    csv = data.to_csv(index=False).encode("utf-8")
    st.download_button(
        label=f"Télécharger ce snapshot (CSV)",
        data=csv,
        file_name=f"calpers_pe_{str(snapshot)[:10]}.csv",
        mime="text/csv",
    )

    st.markdown(
        "<div style='font-size:0.78rem;color:#9a9a9a;margin-top:0.8rem'>"
        "Source : rapports trimestriels publiés par CalPERS sur calpers.ca.gov, "
        "consolidés et nettoyés. Le fichier CSV contient les valeurs numériques brutes "
        "(non formatées) pour ré-utilisation analytique."
        "</div>",
        unsafe_allow_html=True,
    )
