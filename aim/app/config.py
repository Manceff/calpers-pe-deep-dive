"""Constantes globales de l'app — palette institutionnelle neutre."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "aim" / "data" / "aim.duckdb"
VAULT_DIR = ROOT / "aim" / "vault" / "market_context"

APP_TITLE = "CalPERS Private Equity"
APP_SUBTITLE = "Analyse du portefeuille — snapshot du 30 septembre 2025"
FIXED_SNAPSHOT = "2025-09-30"

# Palette neutre, type institutionnel
COLORS = {
    "primary": "#1a3a5c",      # navy
    "primary_light": "#4a6a8c",
    "accent": "#a67c3e",        # or sobre
    "positive": "#2e6b3f",
    "negative": "#9c2a2a",
    "neutral_dark": "#1a1a1a",
    "neutral": "#5a5a5a",
    "neutral_light": "#9a9a9a",
    "border": "#dad6cf",
    "surface": "#ffffff",
    "background": "#fafaf9",
    "generalist": "#5a6470",
    "thematic": "#a67c3e",
}

# Palette catégorielle pour les graphes (monochrome navy + or accent)
CATEGORICAL = [
    "#1a3a5c", "#4a6a8c", "#7a8aaa", "#b5a574",
    "#5a5a5a", "#8a7050", "#3a5a7a", "#6a4a3a",
    "#2a4a6a", "#9aaabe", "#c5a584", "#404a55",
    "#7a6040", "#a8b4c0", "#605040", "#5a7090",
    "#3a3a3a", "#cab490",
]

# Mapping themes_style → couleur
STYLE_COLOR_MAP = {
    "Buyout": "#1a3a5c",
    "Growth": "#4a6a8c",
    "Venture Capital": "#3a5a7a",
    "Credit": "#7a8aaa",
    "Secondaries": "#a67c3e",
    "Continuation": "#b5a574",
    "Co-Investment": "#2a4a6a",
    "Fund of Funds": "#5a7090",
    "Energy": "#8a7050",
    "Cleantech": "#7a6040",
    "Real Estate": "#605040",
    "Infrastructure": "#404a55",
    "Technology": "#6a4a3a",
    "Healthcare": "#9c2a2a",
    "Biotech": "#7a3a4a",
    "Consumer": "#cab490",
    "Industrial": "#5a5a5a",
    "Distressed": "#3a3a3a",
}

# Layout Plotly commun — legend volontairement absent (chaque tab peut l'override).
PLOTLY_LAYOUT = dict(
    font=dict(family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", size=12, color="#1a1a1a"),
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    colorway=CATEGORICAL,
    xaxis=dict(showgrid=True, gridcolor="#e8e4dd", linecolor="#dad6cf", zerolinecolor="#dad6cf"),
    yaxis=dict(showgrid=True, gridcolor="#e8e4dd", linecolor="#dad6cf", zerolinecolor="#dad6cf"),
    margin=dict(l=20, r=20, t=60, b=20),
    hoverlabel=dict(font=dict(family="-apple-system, BlinkMacSystemFont, sans-serif", size=12)),
)


def chart_layout(**overrides):
    """Fusionne PLOTLY_LAYOUT avec overrides (gère les dicts imbriqués xaxis/yaxis)."""
    out = {k: dict(v) if isinstance(v, dict) else v for k, v in PLOTLY_LAYOUT.items()}
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out

# CSS global injecté dans l'app
GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=EB+Garamond:wght@500;600&display=swap');

html, body, [class*="css"], .stApp {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background-color: #fafaf9;
  color: #1a1a1a;
}

h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
  font-family: 'EB Garamond', Georgia, serif;
  font-weight: 600;
  color: #1a1a1a;
  letter-spacing: -0.01em;
}

h1 { font-size: 2.4rem; line-height: 1.15; margin-bottom: 0.2rem; }
h2 { font-size: 1.6rem; line-height: 1.25; margin-top: 1.5rem; margin-bottom: 0.6rem; }
h3 { font-size: 1.25rem; line-height: 1.3; margin-top: 1.2rem; margin-bottom: 0.5rem; font-weight: 600; }

/* Title hero */
.aim-hero {
  border-bottom: 1px solid #dad6cf;
  padding: 0.4rem 0 1.4rem 0;
  margin-bottom: 1.8rem;
}
.aim-hero-title {
  font-family: 'EB Garamond', Georgia, serif;
  font-size: 2.6rem;
  font-weight: 600;
  color: #1a1a1a;
  letter-spacing: -0.01em;
  margin: 0;
  padding: 0.15em 0;
  line-height: 1.35;
  overflow: visible;
  display: block;
}
.aim-hero-subtitle {
  font-family: 'Inter', sans-serif;
  font-size: 0.95rem;
  color: #5a5a5a;
  margin-top: 0.4rem;
  letter-spacing: 0.01em;
}

/* Subtle dividers */
hr { border-color: #e8e4dd; margin: 1.8rem 0; }

/* Metric cards plus sobres */
div[data-testid="stMetric"] {
  background-color: #ffffff;
  border: 1px solid #e8e4dd;
  padding: 0.9rem 1rem;
  border-radius: 4px;
}
div[data-testid="stMetricLabel"] {
  font-size: 0.78rem !important;
  color: #5a5a5a !important;
  font-weight: 500;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
div[data-testid="stMetricValue"] {
  font-family: 'EB Garamond', Georgia, serif !important;
  font-size: 1.75rem !important;
  font-weight: 600 !important;
  color: #1a1a1a !important;
  line-height: 1.2 !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 0;
  border-bottom: 1px solid #dad6cf;
}
.stTabs [data-baseweb="tab"] {
  background-color: transparent;
  padding: 0.7rem 1.4rem;
  font-family: 'Inter', sans-serif;
  font-weight: 500;
  font-size: 0.95rem;
  color: #5a5a5a;
  border: none;
  border-bottom: 2px solid transparent;
  transition: color 150ms ease-out, border-color 150ms ease-out;
}
.stTabs [data-baseweb="tab"]:hover {
  color: #1a3a5c;
}
.stTabs [aria-selected="true"] {
  color: #1a3a5c !important;
  border-bottom: 2px solid #1a3a5c !important;
  font-weight: 600;
}

/* Hide Streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header [data-testid="stToolbar"] {visibility: hidden;}

/* Tighter top padding */
.block-container {
  padding-top: 1.5rem;
  padding-bottom: 3rem;
  max-width: 1400px;
}

/* Dataframe */
.stDataFrame {
  border: 1px solid #e8e4dd;
  border-radius: 4px;
}

/* Selectbox subtler */
.stSelectbox label { color: #5a5a5a; font-size: 0.85rem; }
</style>
"""
