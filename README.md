# CalPERS Private Equity — Deep Dive

Dashboard d'analyse du portefeuille Private Equity de **CalPERS** (*California Public Employees' Retirement System*), le plus grand fonds de pension public américain.

CalPERS publie trimestriellement la performance de chacun des fonds de PE dans lesquels il a investi. Les **20 rapports trimestriels** publiés entre **décembre 2014 et septembre 2025** ont été consolidés pour analyser l'évolution du portefeuille, des engagements, des performances et de l'exposition par gérant, millésime et thématique.

Au snapshot le plus récent (30 septembre 2025) : **462 fonds actifs**, **147,6 Md$ engagés**, **102,2 Md$ de NAV résiduel**, **DPI portefeuille 0,64×**, **TVPI 1,52×**.

## Aperçu

L'application Streamlit propose six pages :

| Page | Contenu |
|---|---|
| **Cockpit** | KPIs portefeuille au snapshot final + évolution complète 2014-2025 (committed / NAV / distribué, DPI / TVPI / IRR médian) |
| **Allocation** | Donut Généraliste vs Thématique, évolution des thèmes (géographique, style/secteur), concentration par GP family (HHI, top-N) |
| **Fonds** | Drill-down par fonds avec trajectoire complète : flux cumulés, multiples DPI/RVPI/TVPI, maturation IRR, J-curve annualisée |
| **Millésimes** | Quartiles IRR par vintage, heatmap IRR × vintage × snapshot, rythme d'engagement, courbes au même âge |
| **PME** | Public Market Equivalent (Kaplan-Schoar) vs S&P 500 Total Return — qui bat l'indice public ? |
| **Données** | Consultation brute de chacun des 20 snapshots avec export CSV |

## Méthodologie

### Source unique de vérité
- **`calpers_pe_funds.xlsx`** : fichier officiel CalPERS, 20 onglets (un par snapshot trimestriel).

### Pipeline déterministe et traçable
```
calpers_pe_funds.xlsx
  → 01_ingest.py            → master_long.parquet     (6 370 lignes, 747 fund_keys)
  → 02_dim_fund.py          → dim_fund.parquet        (1 ligne par fonds + classif thématique)
  → 04_gold_views.py        → aim.duckdb              (12 vues SQL analytiques)
  → 05_pme.py               → table pme_fund          (PME Kaplan-Schoar via yfinance ^SP500TR)
```

### Règle d'or — zéro hallucination
Toute valeur affichée est traçable au xlsx source ou à une formule documentée. La classification thématique (`gp_family`, `theme_geo`, `theme_style`) est basée **uniquement sur le nom du fonds** — aucune inférence externe, aucun LLM. Un fonds sans marqueur thématique dans son nom est tagué « Généraliste ».

### Métriques PE implémentées
- **DPI** = Cash out / Cash in (distribution déjà rendue)
- **RVPI** = NAV / Cash in (valeur latente)
- **TVPI** = (Cash out + NAV) / Cash in = DPI + RVPI
- **Net IRR** : reporté directement par CalPERS (méthode standard XIRR sur flux LP, hors fees)
- **Investment Multiple** : reporté par CalPERS
- **PME Kaplan-Schoar** : `(Σ distrib_t × I_T/I_t + NAV_T) / (Σ calls_t × I_T/I_t)` — PME > 1 → bat l'indice
- **Direct Alpha** : IRR des flux réajustés par l'indice
- **Quartiles, médianes, pooled** : tous les agrégats utilisent les bonnes définitions PE (pas de moyenne d'IRRs, qui sont non-additifs)

### Audit & tests
- **59 tests** pytest (réconciliation cell-exact xlsx ↔ master_long, classification, identités comptables)
- Identité **TVPI = DPI + RVPI** vérifiée à `1e-15` près
- Cumul net J-curve = Δ(cash_out − cash_in) entre 1er et dernier snapshot du fonds, vérifié à 0 € près
- 0 doublons (fund_key, as_of_date), 0 fonds avec vintage ambigu (restatements CalPERS harmonisés par valeur modale)

## Stack

- **Python 3.11+**, `pandas`, `openpyxl`, `pyarrow`
- **DuckDB** pour le stockage analytique et les vues SQL
- **Streamlit** + **Plotly** pour l'UI
- **yfinance** + **scipy** pour le PME et le Direct Alpha
- **pytest** pour les tests

## Lancement local

```bash
pip install -r aim/requirements.txt

# (Optionnel) Re-générer la base depuis le xlsx source
python aim/pipeline/01_ingest.py
python aim/pipeline/02_dim_fund.py
python aim/pipeline/04_gold_views.py
python aim/pipeline/05_pme.py
pytest aim/tests/

# Lancer le dashboard
streamlit run aim/app/main.py
```

L'app est ensuite accessible sur `http://localhost:8501`.

## Structure du projet

```
.
├── aim/
│   ├── app/                    Streamlit
│   │   ├── main.py
│   │   ├── config.py           palette, layout Plotly, CSS
│   │   ├── loaders.py          accès DuckDB cached
│   │   ├── format_utils.py     helpers USD / %, etc.
│   │   └── tabs/               6 pages
│   ├── pipeline/               xlsx → parquet → DuckDB
│   │   ├── 01_ingest.py
│   │   ├── 02_dim_fund.py
│   │   ├── 04_gold_views.py
│   │   ├── 05_pme.py
│   │   └── _classify.py        règles de classification thématique
│   ├── data/                   artefacts générés (gitignored)
│   ├── vault/                  notes contextuelles
│   ├── tests/                  pytest
│   └── requirements.txt
├── .streamlit/config.toml      thème
├── calpers_pe_funds.xlsx       source officielle CalPERS
└── README.md
```

## Auteur

Projet réalisé par **Mancef FERRAH** avec des données open source publiées par CalPERS sur [calpers.ca.gov](https://www.calpers.ca.gov/).

## Licence

Données source : publication officielle CalPERS, domaine public.
Code : usage libre pour analyse non commerciale.
