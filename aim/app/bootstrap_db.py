"""Rebuild aim.duckdb depuis les artefacts versionnés si la DB est absente ou stale.

Permet de NE PAS versionner aim.duckdb (fichier binaire, source de conflits de
cache sur Streamlit Cloud). Les sources versionnées suffisent :
- aim/data/master_long.parquet
- aim/data/dim_fund.parquet
- aim/data/index_tr.csv  (cache S&P 500 TR, évite yfinance au runtime)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "aim" / "data" / "aim.duckdb"
PIPELINE = ROOT / "aim" / "pipeline"


def _db_is_healthy() -> bool:
    if not DB.exists():
        return False
    try:
        import duckdb
        con = duckdb.connect(str(DB), read_only=True)
        con.execute("SELECT 1 FROM pme_fund LIMIT 1").fetchone()
        con.execute("SELECT 1 FROM v_pme_vintage LIMIT 1").fetchone()
        con.close()
        return True
    except Exception:
        return False


def ensure_db() -> None:
    """Idempotent : ne rebuild que si la DB est absente ou ne contient pas pme_fund."""
    if _db_is_healthy():
        return

    if DB.exists():
        DB.unlink()
    DB.parent.mkdir(parents=True, exist_ok=True)

    for script in ("04_gold_views.py", "05_pme.py"):
        path = PIPELINE / script
        result = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Bootstrap failed at {script}:\n{result.stderr}"
            )


if __name__ == "__main__":
    ensure_db()
    print(f"OK — {DB}")
