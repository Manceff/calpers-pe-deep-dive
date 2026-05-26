# AIM — CalPERS Private Equity Analytics

Outil d'analyse du portefeuille Private Equity de CalPERS.

## Sources

- `../calpers_pe_funds.xlsx` : 20 snapshots trimestriels (2014-12-31 → 2025-09-30), 1 onglet par date
- `../calpers_master_long.csv` : version long format pré-concaténée (référence de réconciliation)

## Structure

```
aim/
├── data/         # artefacts générés : master_long.parquet, dim_fund.parquet, aim.duckdb
├── pipeline/     # scripts d'ingestion et enrichissement
│   ├── 01_ingest.py        # xlsx → master_long.parquet (cell-exact)
│   ├── 02_dim_fund.py      # classif heuristique (themes geo/style + gp_family)
│   └── 04_gold_views.py    # vues DuckDB consommées par l'app
├── app/          # Streamlit dashboards
├── vault/        # vault Obsidian (notes contexte marché + auto-générées par fonds)
├── tests/        # tests de réconciliation cell-exact vs xlsx source
└── notebooks/    # exploration ad-hoc
```

## Règle d'or — zéro hallucination

Toute valeur affichée dans l'app doit être traçable à une cellule source ou à une formule documentée. La classification (theme_geo, theme_style, gp_family) est basée UNIQUEMENT sur le nom du fonds — aucune inférence externe, aucun LLM. Si un fonds n'a pas de marqueur thématique dans son nom, il est tagué "Généraliste".

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r aim/requirements.txt
```

## Pipeline

```bash
python aim/pipeline/01_ingest.py       # xlsx → master_long.parquet
python aim/pipeline/02_dim_fund.py     # heuristiques → dim_fund.parquet
python aim/pipeline/04_gold_views.py   # → aim.duckdb
pytest aim/tests/                       # 59 tests (classif + réconciliation)
```

## App

```bash
streamlit run aim/app/main.py
```
