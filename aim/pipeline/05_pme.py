"""
PME Kaplan-Schoar + Direct Alpha par fonds, agrégé par vintage.

Source indice : ^SP500TR (S&P 500 Total Return) via yfinance, cache local.

Méthodologie (à comprendre comme ESTIMÉE — flux reconstitués) :
- Flux par fonds reconstitués à partir de master_long :
  * Premier snapshot du fonds → outflow initial = cash_in à first_seen
  * Snapshots suivants → outflow = period_calls, inflow = period_distributions
  * Dernier snapshot → inflow fictif = nav_residual (valeur terminale)
- PME Kaplan-Schoar :
    PME = (Σ distrib_t × I_T/I_t + NAV_T) / (Σ calls_t × I_T/I_t)
  PME > 1 → PE bat l'indice
- Direct Alpha = IRR du flux ajusté (chaque cashflow × I_T/I_t) → surperformance annualisée.

Le timing intra-trimestre est ignoré (on date tous les flux à as_of_date = fin de
trimestre). C'est une approximation standard. À étiqueter "estimé" dans l'UI.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import yfinance as yf
from scipy.optimize import brentq

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "aim" / "data" / "aim.duckdb"
INDEX_CACHE = ROOT / "aim" / "data" / "index_tr.csv"
INDEX_TICKER = "^SP500TR"
INDEX_FALLBACK = "SPY"
MIN_SNAPSHOTS = 3


# ---------------------------------------------------------------------------
# 1. Index loading (with cache)
# ---------------------------------------------------------------------------

def load_index(start: str = "2014-01-01", end: str = "2025-12-31") -> tuple[pd.Series, str]:
    """Retourne (série indice indexée par date, ticker utilisé)."""
    if INDEX_CACHE.exists():
        df = pd.read_csv(INDEX_CACHE, parse_dates=["date"]).set_index("date")
        ticker = df["ticker"].iloc[0] if "ticker" in df.columns else INDEX_TICKER
        return df["index_close"], ticker

    for ticker in (INDEX_TICKER, INDEX_FALLBACK):
        try:
            df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
            if df.empty:
                continue
            # MultiIndex columns → flatten
            if isinstance(df.columns, pd.MultiIndex):
                col_name = "Adj Close" if ("Adj Close", ticker) in df.columns else "Close"
                s = df[(col_name, ticker)]
            else:
                s = df["Adj Close" if "Adj Close" in df.columns else "Close"]
            s = s.dropna()
            s.index = pd.to_datetime(s.index)
            out = pd.DataFrame({"index_close": s, "ticker": ticker})
            out.index.name = "date"
            INDEX_CACHE.parent.mkdir(parents=True, exist_ok=True)
            out.to_csv(INDEX_CACHE)
            print(f"  Cached {ticker} → {INDEX_CACHE}  ({len(s)} days)", file=sys.stderr)
            return s, ticker
        except Exception as e:
            print(f"  Failed {ticker}: {e}", file=sys.stderr)
    raise RuntimeError("Aucun ticker indice disponible (réseau ?)")


def index_at(idx: pd.Series, date: pd.Timestamp) -> float | None:
    """Retourne l'index au dernier jour ouvré ≤ date (asof)."""
    try:
        val = idx.asof(date)
        if pd.isna(val):
            return None
        return float(val)
    except (KeyError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 2. XIRR (Newton + bracket)
# ---------------------------------------------------------------------------

def xirr(cashflows: list[tuple[pd.Timestamp, float]]) -> float | None:
    """XIRR annualisé. Convention : outflow LP = négatif, inflow = positif.
    Retourne None si pas de solution dans [-0.99, 10.0]."""
    if len(cashflows) < 2:
        return None
    cfs = sorted(cashflows, key=lambda x: x[0])
    t0 = cfs[0][0]
    days = np.array([(d - t0).days for d, _ in cfs], dtype=float)
    amounts = np.array([a for _, a in cfs], dtype=float)
    if (amounts > 0).sum() == 0 or (amounts < 0).sum() == 0:
        return None  # besoin d'au moins un + et un -

    def npv(rate):
        return float(np.sum(amounts / (1 + rate) ** (days / 365.25)))

    try:
        return brentq(npv, -0.99, 10.0, maxiter=200)
    except (ValueError, RuntimeError):
        return None


# ---------------------------------------------------------------------------
# 3. PME per fund
# ---------------------------------------------------------------------------

def build_fund_cashflows(fund_key: str, master: pd.DataFrame) -> list[tuple[pd.Timestamp, float, str]]:
    """Reconstitue les flux datés d'un fonds.
    Returns list of (date, amount, type) where amount<0 = LP outflow, amount>0 = LP inflow.
    Le dernier flux inclut le NAV terminale en distribution fictive."""
    g = master[master["fund_key"] == fund_key].sort_values("as_of_date").reset_index(drop=True)
    if len(g) < MIN_SNAPSHOTS:
        return []
    flows = []
    prev_ci = 0.0
    prev_co = 0.0
    for i, row in g.iterrows():
        d = pd.Timestamp(row["as_of_date"])
        ci = row["cash_in"] or 0
        co = row["cash_out"] or 0
        if i == 0:
            # Premier snapshot : le cash_in cumulé est une approximation de l'appel initial
            if ci > 0:
                flows.append((d, -float(ci), "initial_call"))
            if co > 0:
                flows.append((d, float(co), "initial_distrib"))
        else:
            d_ci = ci - prev_ci
            d_co = co - prev_co
            if d_ci > 0:
                flows.append((d, -float(d_ci), "call"))
            if d_co > 0:
                flows.append((d, float(d_co), "distrib"))
            # Note : si d_ci < 0 ou d_co < 0 (récup, FX), on ignore (rare et bruité)
        prev_ci = ci
        prev_co = co
    # NAV terminale comme distribution fictive
    last = g.iloc[-1]
    nav = (last["cash_out_rv"] or 0) - (last["cash_out"] or 0)
    if nav > 0:
        flows.append((pd.Timestamp(last["as_of_date"]), float(nav), "terminal_nav"))
    return flows


def compute_pme_for_fund(flows: list[tuple[pd.Timestamp, float, str]],
                         idx: pd.Series) -> dict | None:
    """Calcule PME Kaplan-Schoar et Direct Alpha à partir des flux."""
    if not flows:
        return None
    # Date terminale = dernier flux
    t_end = max(d for d, _, _ in flows)
    i_end = index_at(idx, t_end)
    if i_end is None or i_end <= 0:
        return None

    sum_distrib_adj = 0.0  # Σ distrib_t × I_T/I_t (hors NAV terminale)
    sum_call_adj = 0.0
    nav_terminal = 0.0
    cf_adjusted = []  # pour Direct Alpha (XIRR sur flux scaled)

    for d, amt, kind in flows:
        i_t = index_at(idx, d)
        if i_t is None or i_t <= 0:
            continue
        scale = i_end / i_t
        cf_adjusted.append((d, amt * scale))
        if kind == "terminal_nav":
            nav_terminal = amt  # déjà à t_end, scale = 1
        elif amt < 0:  # call
            sum_call_adj += -amt * scale  # call en valeur absolue
        else:  # distrib
            sum_distrib_adj += amt * scale

    if sum_call_adj <= 0:
        return None

    pme_ks = (sum_distrib_adj + nav_terminal) / sum_call_adj
    direct_alpha = xirr(cf_adjusted)

    return {
        "pme_ks": pme_ks,
        "direct_alpha": direct_alpha,
        "sum_called_nominal": -sum(a for _, a, _ in flows if a < 0),
        "sum_distrib_nominal": sum(a for _, a, k in flows if a > 0 and k != "terminal_nav"),
        "nav_terminal_nominal": nav_terminal,
        "first_date": min(d for d, _, _ in flows),
        "last_date": t_end,
        "n_flows": len(flows),
    }


# ---------------------------------------------------------------------------
# 4. Main
# ---------------------------------------------------------------------------

def main() -> int:
    print(f"Loading {DB} …", file=sys.stderr)
    con = duckdb.connect(str(DB))
    master = con.execute("SELECT * FROM master_long").fetchdf()
    dim = con.execute("SELECT fund_key, fund_name_canonical, vintage_year, gp_family, "
                      "is_thematic, is_liquidated FROM dim_fund").fetchdf()

    print("Loading index …", file=sys.stderr)
    idx, ticker = load_index()
    print(f"  Index ticker = {ticker}, {len(idx)} days, "
          f"{idx.index.min().date()} → {idx.index.max().date()}", file=sys.stderr)

    print("Computing PME per fund …", file=sys.stderr)
    results = []
    n_ok, n_skip = 0, 0
    for fund_key in master["fund_key"].unique():
        flows = build_fund_cashflows(fund_key, master)
        if not flows:
            n_skip += 1
            continue
        pme = compute_pme_for_fund(flows, idx)
        if pme is None:
            n_skip += 1
            continue
        pme["fund_key"] = fund_key
        results.append(pme)
        n_ok += 1
    print(f"  OK : {n_ok}, skipped : {n_skip}", file=sys.stderr)

    pme_df = pd.DataFrame(results).merge(dim, on="fund_key", how="left")
    pme_df["index_used"] = ticker
    pme_df["notes"] = "Estimé : flux reconstitués depuis cumuls + NAV terminale, timing fin-de-trimestre"

    # Persiste dans aim.duckdb (table + vue agrégée par vintage)
    con.register("_pme_df", pme_df)
    con.execute("CREATE OR REPLACE TABLE pme_fund AS SELECT * FROM _pme_df")
    con.unregister("_pme_df")

    con.execute("""
        CREATE OR REPLACE VIEW v_pme_vintage AS
        SELECT
            vintage_year,
            COUNT(*) AS n_funds,
            AVG(pme_ks) AS pme_ks_mean,
            MEDIAN(pme_ks) AS pme_ks_median,
            AVG(direct_alpha) AS direct_alpha_mean,
            MEDIAN(direct_alpha) AS direct_alpha_median,
            -- pooled PME (poids = capital nominal called)
            SUM(pme_ks * sum_called_nominal) / NULLIF(SUM(sum_called_nominal), 0) AS pme_ks_pooled
        FROM pme_fund
        WHERE vintage_year IS NOT NULL AND pme_ks IS NOT NULL
        GROUP BY vintage_year
        ORDER BY vintage_year
    """)

    # Stats résumées
    print("\n=== STATS GLOBALES PME ===", file=sys.stderr)
    print(f"Fonds avec PME calculable : {len(pme_df)}", file=sys.stderr)
    print(con.execute("""
        SELECT
            COUNT(*) AS n,
            ROUND(MEDIAN(pme_ks), 2) AS pme_med,
            ROUND(MEDIAN(direct_alpha)*100, 1) AS direct_alpha_med_pct,
            COUNT(*) FILTER (WHERE pme_ks > 1) AS n_above_index,
            COUNT(*) FILTER (WHERE pme_ks < 1) AS n_below_index
        FROM pme_fund WHERE pme_ks IS NOT NULL
    """).fetchdf().to_string(index=False), file=sys.stderr)

    print("\n=== PME par vintage (cohorts ≥5 fonds) ===", file=sys.stderr)
    print(con.execute("""
        SELECT vintage_year, n_funds,
               ROUND(pme_ks_median, 2) AS pme_med,
               ROUND(pme_ks_pooled, 2) AS pme_pooled,
               ROUND(direct_alpha_median*100, 1) AS da_med_pct
        FROM v_pme_vintage WHERE n_funds >= 5 ORDER BY vintage_year
    """).fetchdf().to_string(index=False), file=sys.stderr)

    con.close()
    print(f"\nDone → table pme_fund + view v_pme_vintage in {DB}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
