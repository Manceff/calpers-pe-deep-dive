"""
Construit aim/data/aim.duckdb avec :

Tables :
  master_long, dim_fund, dim_fund_geo, dim_fund_style

Vues par fonds :
  v_fund_360            métriques snapshot × fonds (dpi, tvpi, rvpi, unfunded, age)
  v_period_flows        deltas trimestriels annualisés (period_calls/distributions/net)

Vues portefeuille :
  v_snapshot_kpis       KPIs portefeuille (committed/NAV/DPI/TVPI/IRR + flux + entries/exits)
  v_generalist_split    Généraliste vs Thématique × snapshot

Vues GP :
  v_gp_stats            track record + concentration (HHI, top-N) au dernier snapshot

Vues vintage / cohort :
  v_vintage_stats       agrégats par vintage × snapshot
  v_vintage_quartiles   Q1/médiane/Q3 IRR & TVPI par vintage × snapshot
  v_cohort_same_age     courbes TVPI/DPI vs age par vintage (fonds matures)

Vues thématiques :
  v_theme_geo_evo       expo committed par theme_geo × snapshot
  v_theme_style_evo     expo committed par theme_style × snapshot

Vues marks :
  v_marks_evolution     deltas trimestriels NAV/IRR/Multiple (fonds longitudinaux)
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "aim" / "data" / "master_long.parquet"
DIM = ROOT / "aim" / "data" / "dim_fund.parquet"
DB = ROOT / "aim" / "data" / "aim.duckdb"


def build(db: Path = DB) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()

    # Explose les thèmes en tables relationnelles
    dim = pd.read_parquet(DIM)
    geo_rows, style_rows = [], []
    for _, r in dim.iterrows():
        geos = r["theme_geo"] if r["theme_geo"] is not None else []
        styles = r["theme_style"] if r["theme_style"] is not None else []
        for t in geos:
            geo_rows.append({"fund_key": r["fund_key"], "theme_geo": t})
        for t in styles:
            style_rows.append({"fund_key": r["fund_key"], "theme_style": t})
    dim_fund_geo = pd.DataFrame(geo_rows)
    dim_fund_style = pd.DataFrame(style_rows)

    con = duckdb.connect(str(db))
    con.execute(f"CREATE TABLE master_long AS SELECT * FROM read_parquet('{MASTER}')")
    con.register("_dim_fund_df", dim.drop(columns=["theme_geo", "theme_style"]))
    con.execute("CREATE TABLE dim_fund AS SELECT * FROM _dim_fund_df")
    con.unregister("_dim_fund_df")

    if len(dim_fund_geo):
        con.register("_geo_df", dim_fund_geo)
        con.execute("CREATE TABLE dim_fund_geo AS SELECT * FROM _geo_df")
        con.unregister("_geo_df")
    else:
        con.execute("CREATE TABLE dim_fund_geo (fund_key VARCHAR, theme_geo VARCHAR)")

    if len(dim_fund_style):
        con.register("_style_df", dim_fund_style)
        con.execute("CREATE TABLE dim_fund_style AS SELECT * FROM _style_df")
        con.unregister("_style_df")
    else:
        con.execute("CREATE TABLE dim_fund_style (fund_key VARCHAR, theme_style VARCHAR)")

    # ========================================================================
    # PAR FONDS — v_fund_360 enrichi
    # ========================================================================
    con.execute("""
        CREATE OR REPLACE VIEW v_fund_360 AS
        SELECT
            m.as_of_date,
            m.fund_key,
            m.fund_name,
            d.fund_name_canonical,
            m.vintage_year,
            d.gp_family,
            d.fund_series_no,
            d.is_thematic,
            d.is_liquidated,
            m.capital_committed,
            m.cash_in,
            m.cash_out,
            m.cash_out_rv,
            (m.cash_out_rv - m.cash_out) AS nav_residual,
            (m.capital_committed - m.cash_in) AS unfunded,
            m.net_irr,
            m.investment_multiple,
            CASE WHEN m.cash_in > 0 THEN m.cash_out / m.cash_in END AS dpi,
            CASE WHEN m.cash_in > 0 THEN (m.cash_out_rv - m.cash_out) / m.cash_in END AS rvpi,
            CASE WHEN m.cash_in > 0 THEN m.cash_out_rv / m.cash_in END AS tvpi,
            CASE WHEN m.capital_committed > 0 THEN m.cash_in / m.capital_committed END AS called_pct,
            -- age en années depuis le 1er jan de vintage_year
            (EXTRACT(EPOCH FROM m.as_of_date - MAKE_DATE(m.vintage_year, 1, 1)) / 86400.0 / 365.25) AS age_years
        FROM master_long m
        LEFT JOIN dim_fund d USING (fund_key)
    """)

    # ========================================================================
    # PAR FONDS — flux de période (delta entre 2 snapshots consécutifs)
    # ========================================================================
    con.execute("""
        CREATE OR REPLACE VIEW v_period_flows AS
        WITH lagged AS (
            SELECT
                fund_key,
                as_of_date,
                cash_in,
                cash_out,
                (cash_out_rv - cash_out) AS nav,
                LAG(as_of_date) OVER (PARTITION BY fund_key ORDER BY as_of_date) AS prev_date,
                LAG(cash_in)    OVER (PARTITION BY fund_key ORDER BY as_of_date) AS prev_cash_in,
                LAG(cash_out)   OVER (PARTITION BY fund_key ORDER BY as_of_date) AS prev_cash_out,
                LAG(cash_out_rv - cash_out) OVER (PARTITION BY fund_key ORDER BY as_of_date) AS prev_nav
            FROM master_long
        )
        SELECT
            fund_key,
            as_of_date,
            prev_date,
            EXTRACT(EPOCH FROM as_of_date - prev_date) / 86400.0 AS days_elapsed,
            (cash_in - prev_cash_in)   AS period_calls,
            (cash_out - prev_cash_out) AS period_distributions,
            ((cash_out - prev_cash_out) - (cash_in - prev_cash_in)) AS net_cashflow,
            (nav - prev_nav) AS nav_change,
            -- Annualisé (sur 365.25 jours)
            CASE WHEN as_of_date > prev_date
                 THEN (cash_in - prev_cash_in) / (EXTRACT(EPOCH FROM as_of_date - prev_date) / 86400.0 / 365.25)
            END AS period_calls_annualized,
            CASE WHEN as_of_date > prev_date
                 THEN (cash_out - prev_cash_out) / (EXTRACT(EPOCH FROM as_of_date - prev_date) / 86400.0 / 365.25)
            END AS period_distributions_annualized
        FROM lagged
        WHERE prev_date IS NOT NULL
    """)

    # ========================================================================
    # PORTEFEUILLE — v_snapshot_kpis enrichi
    # ========================================================================
    con.execute("""
        CREATE OR REPLACE VIEW v_snapshot_kpis AS
        WITH base AS (
            SELECT
                as_of_date,
                COUNT(*) AS n_funds,
                SUM(capital_committed) AS committed,
                SUM(cash_in) AS called,
                SUM(cash_out) AS distributed,
                SUM(cash_out_rv) AS out_rv,
                SUM(cash_out_rv - cash_out) AS nav_residual,
                SUM(capital_committed - cash_in) AS unfunded_total,
                SUM(cash_out) / NULLIF(SUM(cash_in), 0) AS dpi,
                SUM(cash_out_rv) / NULLIF(SUM(cash_in), 0) AS tvpi,
                SUM(cash_in) / NULLIF(SUM(capital_committed), 0) AS called_pct,
                MEDIAN(net_irr) FILTER (WHERE net_irr IS NOT NULL) AS median_irr,
                MEDIAN(investment_multiple) FILTER (WHERE investment_multiple IS NOT NULL) AS median_mult,
                COUNT(*) FILTER (WHERE net_irr IS NOT NULL) AS n_mature
            FROM master_long GROUP BY as_of_date
        ),
        period_agg AS (
            SELECT
                as_of_date,
                SUM(period_calls) AS new_calls_period,
                SUM(period_distributions) AS new_distributions_period,
                SUM(period_distributions - period_calls) AS net_liquidity_period
            FROM v_period_flows GROUP BY as_of_date
        ),
        entries_exits AS (
            -- Pour chaque snapshot, nb de fonds qui apparaissent vs disparaissent.
            -- On NULL-ifie les bordures : pas d'entry possible au 1er snapshot,
            -- pas d'exit possible au dernier (car on n'a pas de prev/next snapshot).
            WITH date_order AS (
                SELECT DISTINCT as_of_date,
                       ROW_NUMBER() OVER (ORDER BY as_of_date) AS sn,
                       COUNT(*) OVER () AS sn_max
                FROM (SELECT DISTINCT as_of_date FROM master_long)
            ),
            presence AS (
                SELECT m.fund_key, d.sn, d.as_of_date, d.sn_max
                FROM master_long m
                JOIN date_order d USING (as_of_date)
            )
            SELECT
                p.as_of_date,
                CASE WHEN p.sn = 1 THEN NULL ELSE
                    COUNT(DISTINCT CASE WHEN prev.fund_key IS NULL THEN p.fund_key END)
                END AS n_entries,
                CASE WHEN p.sn = p.sn_max THEN NULL ELSE
                    COUNT(DISTINCT CASE WHEN next_.fund_key IS NULL THEN p.fund_key END)
                END AS n_exits
            FROM presence p
            LEFT JOIN presence prev  ON p.fund_key = prev.fund_key  AND prev.sn = p.sn - 1
            LEFT JOIN presence next_ ON p.fund_key = next_.fund_key AND next_.sn = p.sn + 1
            GROUP BY p.as_of_date, p.sn, p.sn_max
        )
        SELECT
            b.*,
            p.new_calls_period,
            p.new_distributions_period,
            p.net_liquidity_period,
            e.n_entries,
            e.n_exits
        FROM base b
        LEFT JOIN period_agg p USING (as_of_date)
        LEFT JOIN entries_exits e USING (as_of_date)
        ORDER BY as_of_date
    """)

    # ========================================================================
    # GENERALISTE vs THEMATIQUE × snapshot
    # ========================================================================
    con.execute("""
        CREATE OR REPLACE VIEW v_generalist_split AS
        SELECT
            m.as_of_date,
            CASE WHEN d.is_thematic THEN 'Thématique' ELSE 'Généraliste' END AS kind,
            COUNT(*) AS n_funds,
            SUM(m.capital_committed) AS committed,
            SUM(m.cash_in) AS called,
            SUM(m.cash_out_rv) AS out_rv,
            SUM(m.cash_out_rv - m.cash_out) AS nav_residual,
            MEDIAN(m.net_irr) FILTER (WHERE m.net_irr IS NOT NULL) AS median_irr
        FROM master_long m
        JOIN dim_fund d USING (fund_key)
        GROUP BY m.as_of_date, kind
        ORDER BY m.as_of_date, kind
    """)

    # ========================================================================
    # GP — track record + concentration (HHI, top-N)
    # ========================================================================
    con.execute("""
        CREATE OR REPLACE VIEW v_gp_stats AS
        WITH last_snap AS (SELECT MAX(as_of_date) AS d FROM master_long),
        per_gp AS (
            SELECT
                d.gp_family,
                COUNT(DISTINCT m.fund_key) AS n_funds,
                SUM(m.capital_committed) AS committed,
                SUM(m.cash_in) AS called,
                SUM(m.cash_out) AS distributed,
                SUM(m.cash_out_rv) AS out_rv,
                SUM(m.cash_out_rv - m.cash_out) AS nav_residual,
                SUM(m.capital_committed - m.cash_in) AS unfunded,
                SUM(m.cash_out) / NULLIF(SUM(m.cash_in), 0) AS dpi,
                SUM(m.cash_out_rv) / NULLIF(SUM(m.cash_in), 0) AS tvpi,
                MEDIAN(m.net_irr) FILTER (WHERE m.net_irr IS NOT NULL) AS median_irr,
                MEDIAN(m.investment_multiple) FILTER (WHERE m.investment_multiple IS NOT NULL) AS median_mult
            FROM master_long m
            JOIN dim_fund d USING (fund_key)
            CROSS JOIN last_snap ls
            WHERE m.as_of_date = ls.d
            GROUP BY d.gp_family
        ),
        with_pct AS (
            SELECT
                *,
                100.0 * committed / NULLIF(SUM(committed) OVER (), 0) AS pct_of_total
            FROM per_gp
        ),
        ranked AS (
            SELECT
                *,
                ROW_NUMBER() OVER (ORDER BY committed DESC NULLS LAST) AS rank_committed,
                SUM(pct_of_total) OVER (ORDER BY committed DESC NULLS LAST
                                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_pct
            FROM with_pct
        )
        SELECT * FROM ranked
        ORDER BY rank_committed
    """)

    # Concentration globale (1 ligne)
    con.execute("""
        CREATE OR REPLACE VIEW v_gp_concentration AS
        WITH ls AS (SELECT MAX(as_of_date) AS d FROM master_long)
        SELECT
            (SELECT d FROM ls) AS as_of_date,
            COUNT(*) AS n_gps,
            SUM(CASE WHEN rank_committed <= 5  THEN pct_of_total END) AS pct_top5,
            SUM(CASE WHEN rank_committed <= 10 THEN pct_of_total END) AS pct_top10,
            SUM(CASE WHEN rank_committed <= 20 THEN pct_of_total END) AS pct_top20,
            -- HHI : Σ (pct_of_total)^2, normalisé ∈ [0, 10 000]
            SUM(pct_of_total * pct_of_total) AS hhi
        FROM v_gp_stats
    """)

    # ========================================================================
    # VINTAGE — quartiles + cohorte same-age
    # ========================================================================
    con.execute("""
        CREATE OR REPLACE VIEW v_vintage_stats AS
        SELECT
            as_of_date,
            vintage_year,
            COUNT(*) AS n_funds,
            SUM(capital_committed) AS committed,
            SUM(cash_in) AS called,
            SUM(cash_out_rv) AS out_rv,
            SUM(capital_committed - cash_in) AS unfunded,
            SUM(cash_out) / NULLIF(SUM(cash_in), 0) AS dpi,
            SUM(cash_out_rv) / NULLIF(SUM(cash_in), 0) AS tvpi,
            MEDIAN(net_irr) FILTER (WHERE net_irr IS NOT NULL) AS median_irr,
            MEDIAN(investment_multiple) FILTER (WHERE investment_multiple IS NOT NULL) AS median_mult,
            COUNT(*) FILTER (WHERE net_irr IS NOT NULL) AS n_mature
        FROM master_long
        WHERE vintage_year IS NOT NULL
        GROUP BY as_of_date, vintage_year
        ORDER BY as_of_date, vintage_year
    """)

    con.execute("""
        CREATE OR REPLACE VIEW v_vintage_quartiles AS
        SELECT
            as_of_date,
            vintage_year,
            COUNT(*) FILTER (WHERE net_irr IS NOT NULL) AS n_mature,
            QUANTILE_CONT(net_irr, 0.25) FILTER (WHERE net_irr IS NOT NULL) AS irr_q1,
            MEDIAN(net_irr) FILTER (WHERE net_irr IS NOT NULL) AS irr_med,
            QUANTILE_CONT(net_irr, 0.75) FILTER (WHERE net_irr IS NOT NULL) AS irr_q3,
            QUANTILE_CONT(investment_multiple, 0.25) FILTER (WHERE investment_multiple IS NOT NULL) AS mult_q1,
            MEDIAN(investment_multiple) FILTER (WHERE investment_multiple IS NOT NULL) AS mult_med,
            QUANTILE_CONT(investment_multiple, 0.75) FILTER (WHERE investment_multiple IS NOT NULL) AS mult_q3
        FROM master_long
        WHERE vintage_year IS NOT NULL
        GROUP BY as_of_date, vintage_year
        ORDER BY as_of_date, vintage_year
    """)

    # Cohorte same-age : TVPI/DPI vs age (en années entières) par vintage
    con.execute("""
        CREATE OR REPLACE VIEW v_cohort_same_age AS
        SELECT
            vintage_year,
            CAST(FLOOR(age_years) AS INTEGER) AS age_floor,
            COUNT(*) AS n_obs,
            MEDIAN(tvpi) AS median_tvpi,
            MEDIAN(dpi) AS median_dpi,
            MEDIAN(net_irr) FILTER (WHERE net_irr IS NOT NULL) AS median_irr
        FROM v_fund_360
        WHERE vintage_year IS NOT NULL AND age_years >= 0
        GROUP BY vintage_year, age_floor
        ORDER BY vintage_year, age_floor
    """)

    # ========================================================================
    # THEMES × snapshot
    # ========================================================================
    con.execute("""
        CREATE OR REPLACE VIEW v_theme_geo_evo AS
        SELECT
            m.as_of_date,
            g.theme_geo,
            COUNT(DISTINCT m.fund_key) AS n_funds,
            SUM(m.capital_committed) AS committed,
            SUM(m.cash_in) AS called,
            SUM(m.cash_out_rv) AS out_rv,
            SUM(m.cash_out_rv - m.cash_out) AS nav_residual,
            MEDIAN(m.net_irr) FILTER (WHERE m.net_irr IS NOT NULL) AS median_irr
        FROM master_long m
        JOIN dim_fund_geo g USING (fund_key)
        GROUP BY m.as_of_date, g.theme_geo
        ORDER BY m.as_of_date, committed DESC
    """)

    con.execute("""
        CREATE OR REPLACE VIEW v_theme_style_evo AS
        SELECT
            m.as_of_date,
            s.theme_style,
            COUNT(DISTINCT m.fund_key) AS n_funds,
            SUM(m.capital_committed) AS committed,
            SUM(m.cash_in) AS called,
            SUM(m.cash_out_rv) AS out_rv,
            SUM(m.cash_out_rv - m.cash_out) AS nav_residual,
            MEDIAN(m.net_irr) FILTER (WHERE m.net_irr IS NOT NULL) AS median_irr
        FROM master_long m
        JOIN dim_fund_style s USING (fund_key)
        GROUP BY m.as_of_date, s.theme_style
        ORDER BY m.as_of_date, committed DESC
    """)

    # ========================================================================
    # MARKS EVOLUTION
    # ========================================================================
    con.execute("""
        CREATE OR REPLACE VIEW v_marks_evolution AS
        WITH ranked AS (
            SELECT
                fund_key, as_of_date, cash_out_rv, cash_out, net_irr, investment_multiple,
                LAG(cash_out_rv) OVER (PARTITION BY fund_key ORDER BY as_of_date) AS prev_out_rv,
                LAG(cash_out)    OVER (PARTITION BY fund_key ORDER BY as_of_date) AS prev_cash_out,
                LAG(net_irr)     OVER (PARTITION BY fund_key ORDER BY as_of_date) AS prev_irr,
                LAG(investment_multiple) OVER (PARTITION BY fund_key ORDER BY as_of_date) AS prev_mult,
                LAG(as_of_date)  OVER (PARTITION BY fund_key ORDER BY as_of_date) AS prev_date
            FROM master_long
        )
        SELECT
            r.as_of_date, r.fund_key, d.fund_name_canonical, d.gp_family, d.is_thematic,
            r.prev_date,
            r.cash_out_rv, r.prev_out_rv,
            (r.cash_out_rv - r.prev_out_rv) AS delta_out_rv,
            CASE WHEN r.prev_out_rv > 0
                 THEN (r.cash_out_rv - r.prev_out_rv) / r.prev_out_rv END AS pct_change_out_rv,
            ((r.cash_out_rv - r.cash_out) - (r.prev_out_rv - r.prev_cash_out)) AS delta_nav,
            r.net_irr, r.prev_irr, (r.net_irr - r.prev_irr) AS delta_irr,
            r.investment_multiple, r.prev_mult, (r.investment_multiple - r.prev_mult) AS delta_mult
        FROM ranked r
        LEFT JOIN dim_fund d USING (fund_key)
        WHERE r.prev_date IS NOT NULL
    """)

    # --- Sanity check ---
    views = ["v_fund_360", "v_period_flows", "v_snapshot_kpis", "v_generalist_split",
             "v_gp_stats", "v_gp_concentration", "v_vintage_stats", "v_vintage_quartiles",
             "v_cohort_same_age", "v_theme_geo_evo", "v_theme_style_evo", "v_marks_evolution"]
    for v in views:
        n = con.execute(f"SELECT COUNT(*) FROM {v}").fetchone()[0]
        print(f"  {v:25s}  rows={n:,}", file=sys.stderr)
    con.close()


def main() -> int:
    print(f"Building {DB} …", file=sys.stderr)
    build()
    print(f"OK — {DB}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
