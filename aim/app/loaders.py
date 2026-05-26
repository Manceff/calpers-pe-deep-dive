"""Chargement DuckDB avec cache Streamlit. Une connexion read-only partagée."""
from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from aim.app.config import DB_PATH


@st.cache_resource
def get_con() -> duckdb.DuckDBPyConnection:
    """Connexion read-only persistante (singleton)."""
    return duckdb.connect(str(DB_PATH), read_only=True)


@st.cache_data(ttl=3600, show_spinner=False)
def q(sql: str, params: tuple | None = None) -> pd.DataFrame:
    """Query DuckDB avec cache. Param tuple permet du paramétrage propre."""
    con = get_con()
    if params:
        return con.execute(sql, params).fetchdf()
    return con.execute(sql).fetchdf()


@st.cache_data(ttl=3600)
def all_snapshots() -> list[pd.Timestamp]:
    return sorted(q("SELECT DISTINCT as_of_date FROM master_long ORDER BY as_of_date")["as_of_date"])


@st.cache_data(ttl=3600)
def last_snapshot() -> pd.Timestamp:
    return q("SELECT MAX(as_of_date) AS d FROM master_long")["d"].iloc[0]


@st.cache_data(ttl=3600)
def all_gp_families() -> list[str]:
    df = q("SELECT DISTINCT gp_family FROM dim_fund WHERE gp_family IS NOT NULL ORDER BY gp_family")
    return df["gp_family"].tolist()


@st.cache_data(ttl=3600)
def vintage_range() -> tuple[int, int]:
    df = q("SELECT MIN(vintage_year) AS lo, MAX(vintage_year) AS hi FROM master_long WHERE vintage_year IS NOT NULL")
    return int(df["lo"].iloc[0]), int(df["hi"].iloc[0])
