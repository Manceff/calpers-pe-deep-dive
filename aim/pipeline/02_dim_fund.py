"""
Construit aim/data/dim_fund.parquet depuis master_long.parquet.

Une ligne par fund_key. Trois dimensions de classification, basées uniquement
sur le NOM (jamais inventées) :
  - gp_family       (table d'alias + fallback heuristique)
  - theme_geo       (liste de zones géographiques détectées)
  - theme_style     (liste de styles/secteurs détectés)
  - is_thematic     (bool : au moins un thème détecté)

Plus du métadonnées dérivées :
  - fund_series_no, is_liquidated, liquidation_date
  - first_seen, last_seen, n_snapshots
  - last_committed, last_cash_in, last_cash_out, last_cash_out_rv,
    last_net_irr, last_investment_multiple
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from aim.pipeline._classify import (  # noqa: E402
    detect_themes,
    extract_fund_series,
    extract_gp_family,
)

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "aim" / "data" / "master_long.parquet"
OUT = ROOT / "aim" / "data" / "dim_fund.parquet"

LIQUIDATION_TOLERANCE = 0.005  # 0.5% écart cash_out vs cash_out_rv


def build_dim_fund(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for fund_key, g in master.sort_values("as_of_date").groupby("fund_key", sort=False):
        last = g.iloc[-1]
        name = last["fund_name"]

        themes = detect_themes(name)
        gp = extract_gp_family(name)
        series = extract_fund_series(name)

        # --- Liquidation : convergence cash_out_rv ≈ cash_out ---
        tail = g.tail(3)
        flags = []
        for _, r in tail.iterrows():
            co, rv = r["cash_out"], r["cash_out_rv"]
            if pd.isna(co) or pd.isna(rv) or co <= 0:
                flags.append(False)
            else:
                flags.append(abs(rv - co) / co < LIQUIDATION_TOLERANCE)
        is_liquidated = len(flags) >= 2 and all(flags[-2:])
        liquidation_date = None
        if is_liquidated:
            for _, r in g.iterrows():
                co, rv = r["cash_out"], r["cash_out_rv"]
                if pd.notna(co) and pd.notna(rv) and co > 0 and abs(rv - co) / co < LIQUIDATION_TOLERANCE:
                    liquidation_date = r["as_of_date"]
                    break

        rows.append({
            "fund_key": fund_key,
            "fund_name_canonical": name,
            "vintage_year": int(last["vintage_year"]) if pd.notna(last["vintage_year"]) else None,
            "gp_family": gp,
            "fund_series_no": series,
            "theme_geo": themes.geo,
            "theme_style": themes.style,
            "is_thematic": themes.is_thematic,
            "classification_source": "name_heuristic",  # 'llm_assist' après étape 03
            "is_liquidated": is_liquidated,
            "liquidation_date": liquidation_date,
            "first_seen": g["as_of_date"].min(),
            "last_seen": g["as_of_date"].max(),
            "n_snapshots": len(g),
            "last_committed": last["capital_committed"],
            "last_cash_in": last["cash_in"],
            "last_cash_out": last["cash_out"],
            "last_cash_out_rv": last["cash_out_rv"],
            "last_net_irr": last["net_irr"],
            "last_investment_multiple": last["investment_multiple"],
        })
    return pd.DataFrame(rows).sort_values("fund_key").reset_index(drop=True)


def main() -> int:
    master = pd.read_parquet(MASTER)
    print(f"Loaded {MASTER}  rows={len(master):,}  funds={master['fund_key'].nunique()}",
          file=sys.stderr)
    dim = build_dim_fund(master)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    dim.to_parquet(OUT, index=False)
    print(f"Wrote {OUT}  rows={len(dim):,}", file=sys.stderr)

    # --- Résumés ---
    print("\n=== GENERALISTE vs THEMATIQUE ===", file=sys.stderr)
    by_thematic = dim["is_thematic"].value_counts()
    n_total = len(dim)
    n_gen = (~dim["is_thematic"]).sum()
    n_them = dim["is_thematic"].sum()
    cap_gen = dim.loc[~dim["is_thematic"], "last_committed"].sum() / 1e9
    cap_them = dim.loc[dim["is_thematic"], "last_committed"].sum() / 1e9
    print(f"  Généralistes : {n_gen}/{n_total} fonds — {cap_gen:.1f} Md$ committed", file=sys.stderr)
    print(f"  Thématiques  : {n_them}/{n_total} fonds — {cap_them:.1f} Md$ committed", file=sys.stderr)

    print("\n=== TOP THEMES GEO (nb fonds × somme committed) ===", file=sys.stderr)
    geo_expand = dim.explode("theme_geo").dropna(subset=["theme_geo"])
    if len(geo_expand):
        print(geo_expand.groupby("theme_geo").agg(
            n_funds=("fund_key", "count"),
            committed_B=("last_committed", lambda s: round(s.sum() / 1e9, 2)),
        ).sort_values("committed_B", ascending=False).to_string(), file=sys.stderr)

    print("\n=== TOP THEMES STYLE ===", file=sys.stderr)
    style_expand = dim.explode("theme_style").dropna(subset=["theme_style"])
    if len(style_expand):
        print(style_expand.groupby("theme_style").agg(
            n_funds=("fund_key", "count"),
            committed_B=("last_committed", lambda s: round(s.sum() / 1e9, 2)),
        ).sort_values("committed_B", ascending=False).to_string(), file=sys.stderr)

    print("\n=== TOP 15 GP FAMILY (par committed) ===", file=sys.stderr)
    print(dim.groupby("gp_family").agg(
        n_funds=("fund_key", "count"),
        committed_B=("last_committed", lambda s: round(s.sum() / 1e9, 2)),
    ).sort_values("committed_B", ascending=False).head(15).to_string(), file=sys.stderr)

    print(f"\nLiquidés : {dim['is_liquidated'].sum()} / {len(dim)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
