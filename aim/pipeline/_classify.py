"""
Classification basée uniquement sur le NOM du fonds.

Trois dimensions, jamais inventées :
- gp_family : extraction du préfixe GP (avec table d'alias pour gros GPs)
- theme_geo : liste de zones géographiques détectées (Asia, China, Europe...)
- theme_style : liste de styles/secteurs détectés (Buyout, Venture, Energy...)

is_thematic = bool(theme_geo) OR bool(theme_style)
Un fonds sans thème détecté est "Généraliste". Le LLM (étape suivante) peut
rattraper les faux-négatifs en s'appuyant sur sa connaissance du GP.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ============================================================================
# 1. THEMES GÉOGRAPHIQUES (zones explicitement mentionnées dans le nom)
# ============================================================================

GEO_RULES: list[tuple[str, str]] = [
    (r"\b(china|chinese|prc|sino|hongshan)\b", "China"),
    (r"\b(india|indian|bharat)\b", "India"),
    (r"\b(japan|japanese|nippon)\b", "Japan"),
    (r"\b(korea|korean)\b", "Korea"),
    (r"\b(southeast\s+asia|asean|vietnam|indonesia|philippines|thailand|singapore)\b", "Southeast Asia"),
    (r"\b(asia(n)?|pacific|apac|asia[\-\s]pacific)\b", "Asia"),
    (r"\b(europe(an)?|uk\b|britain|british|germany|france|french|nordic|italy|italian|iberia|spain|spanish|benelux|emea)\b", "Europe"),
    (r"\b(latin\s+america|latam|brazil|brasil|mexico|argentin|colombia|chile|peru)\b", "Latin America"),
    (r"\b(middle\s+east|mena\b|israel|israeli|gulf|gcc)\b", "Middle East"),
    (r"\b(africa(n)?|sub[\-\s]saharan)\b", "Africa"),
    (r"\b(emerging\s+markets?|frontier)\b", "Emerging Markets"),
    # 'Global' est un signal faible — un fonds 'Global Buyout' reste thématique
    # uniquement par son style, pas par la géo. Donc on ne tag PAS 'Global' ici.
]


# ============================================================================
# 2. THEMES STYLE / SECTEUR (nature explicite dans le nom)
# ============================================================================

# Ordre = priorité. Un seul match par règle, mais on collecte plusieurs styles.
STYLE_RULES: list[tuple[str, str]] = [
    # --- Stratégie d'achat / structure ---
    (r"\bcontinuation\s+(fund|vehicle)?\b", "Continuation"),
    (r"\b(secondaries?|secondary\s+fund)\b", "Secondaries"),
    (r"\bco[\-\s]?invest(ment)?s?\b", "Co-Investment"),
    (r"\b(fund\s+of\s+funds?|fof|multi[\-\s]manager)\b", "Fund of Funds"),
    (r"\b(buyout|leveraged\s+buyout|lbo)\b", "Buyout"),
    (r"\b(ventures?|seed(\s+fund)?|early[\-\s]?stage|early\s+capital)\b", "Venture Capital"),
    (r"\b(growth\s+(equity|capital|partners|fund|investors)|growth\b)\b", "Growth"),
    (r"\b(credit|debt\s+fund|mezzanine|direct\s+lending|private\s+debt|distressed\s+debt|yield)\b", "Credit"),
    (r"\b(distressed|special\s+situations?|recovery|workout|turnaround)\b", "Distressed"),
    # 'Opportunities' / 'Opportunity' tout seul → trop générique, on ne tag pas
    # (utilisé par Blackstone Tactical Opportunities = généraliste opportuniste)

    # --- Secteur (verticales explicites) ---
    (r"\b(clean\s+energy|cleantech|renewable|green\s+energy|sustainable\s+energy)\b", "Cleantech"),
    (r"\b(energy|power|oil\b|gas\b|natural\s+resources)\b", "Energy"),
    (r"\b(real\s+estate|reit\b|property\s+fund)\b", "Real Estate"),
    (r"\b(infrastructure|infra\b)\b", "Infrastructure"),
    (r"\b(tech(nology)?|software|saas|digital|internet|fintech|cyber)\b", "Technology"),
    (r"\b(health(care)?|medical|medtech)\b", "Healthcare"),
    (r"\b(bio(pharm)?|biotech(nology)?|pharma(ceutical)?|life\s+sciences)\b", "Biotech"),
    (r"\b(consumer\s+fund|retail\s+fund)\b", "Consumer"),
    (r"\b(industrial\s+fund)\b", "Industrial"),
]


# ============================================================================
# 3. GP FAMILY EXTRACTION (table d'alias + fallback heuristique)
# ============================================================================

# Table d'alias : si le nom commence par/contient un de ces patterns,
# on attribue la GP family canonique. Ordre = priorité (premier match gagne).
GP_ALIAS: list[tuple[str, str]] = [
    (r"^blackstone\b", "Blackstone"),
    (r"^kkr\b", "KKR"),
    (r"^carlyle\b", "Carlyle"),
    (r"^apollo\b", "Apollo"),
    (r"^tpg\b", "TPG"),
    (r"^bain\s+capital\b", "Bain Capital"),
    (r"^cvc\b", "CVC"),
    (r"^advent\b", "Advent"),
    (r"^clearlake\b", "Clearlake"),
    (r"^vista\b", "Vista Equity"),
    (r"^permira\b", "Permira"),
    (r"^insight\b", "Insight"),
    (r"^general\s+atlantic\b", "General Atlantic"),
    (r"^warburg\s+pincus\b", "Warburg Pincus"),
    (r"^hellman\s*&?\s*friedman\b|^h&f\b", "Hellman & Friedman"),
    (r"^silver\s+lake\b", "Silver Lake"),
    (r"^thoma\s+bravo\b", "Thoma Bravo"),
    (r"^ares\b", "Ares"),
    (r"^oaktree\b", "Oaktree"),
    (r"^coller\b", "Coller"),
    (r"^lexington\b", "Lexington"),
    (r"^alpinvest\b", "AlpInvest"),
    (r"^harbourvest\b", "HarbourVest"),
    (r"^pantheon\b", "Pantheon"),
    (r"^adams\s+street\b", "Adams Street"),
    (r"^riverstone\b", "Riverstone"),
    (r"^first\s+reserve\b", "First Reserve"),
    (r"^encap\b", "EnCap"),
    (r"^energy\s+capital\s+partners\b|^ecp\b", "Energy Capital Partners"),
    (r"^tiger\s+global\b", "Tiger Global"),
    (r"^hongshan\b|^sequoia\s+china\b", "HongShan (ex-Sequoia China)"),
    (r"^sequoia\b", "Sequoia"),
    (r"^khosla\b", "Khosla Ventures"),
    (r"^andreessen\s+horowitz\b|^a16z\b", "Andreessen Horowitz"),
    (r"^accel\b", "Accel"),
    (r"^bessemer\b", "Bessemer"),
    (r"^benchmark\b", "Benchmark"),
    (r"^new\s+enterprise\s+associates\b|^nea\b", "NEA"),
    (r"^kleiner\s+perkins\b", "Kleiner Perkins"),
    (r"^lightspeed\b", "Lightspeed"),
    (r"^index\s+ventures\b", "Index Ventures"),
    (r"^iconiq\b", "ICONIQ"),
    (r"^francisco\s+partners\b", "Francisco Partners"),
    (r"^bridgepoint\b", "Bridgepoint"),
    (r"^eqt\b", "EQT"),
    (r"^nordic\s+capital\b", "Nordic Capital"),
    (r"^cinven\b", "Cinven"),
    (r"^pai\b", "PAI"),
    (r"^bc\s+partners\b", "BC Partners"),
    (r"^charterhouse\b", "Charterhouse"),
    (r"^triton\b", "Triton"),
    (r"^ardian\b", "Ardian"),
    (r"^aac(p)?\b", "Asia Alternatives (AACP)"),
    (r"^57\s+stars\b", "57 Stars"),
    (r"^new\s+mountain\b", "New Mountain"),
    (r"^centerbridge\b", "Centerbridge"),
    (r"^cerberus\b", "Cerberus"),
    (r"^crestview\b", "Crestview"),
    (r"^arsenal\s+capital\b", "Arsenal Capital"),
    (r"^audax\b", "Audax"),
    (r"^genstar\b", "Genstar"),
    (r"^leonard\s+green\b", "Leonard Green"),
    (r"^providence\s+equity\b", "Providence Equity"),
    (r"^yucaipa\b", "Yucaipa"),
    (r"^wlr\s+recovery\b|^wl\s+ross\b", "WL Ross"),
    (r"^sl\s+spv\b|^sl\s+capital\b", "SL Capital"),
    (r"^cmea\b", "CMEA Ventures"),
    (r"^accel[\-\s]kkr\b", "Accel-KKR"),
    (r"^golden\s+gate\b", "Golden Gate Capital"),
    (r"^bridgepoint\b", "Bridgepoint"),
    (r"^trustbridge\b", "Trustbridge"),
    (r"^trident\b", "Trident"),
    (r"^stone\s+point\b", "Stone Point"),
    (r"^stonepeak\b", "Stonepeak"),
    (r"^gtcr\b", "GTCR"),
    (r"^berkshire\s+partners\b", "Berkshire Partners"),
    (r"^summit\s+partners\b", "Summit Partners"),
    (r"^ta\s+associates\b", "TA Associates"),
    (r"^jh\s+partners\b|^john\s+hancock\b", "JH Partners"),
    (r"^clayton[,\s]*dubilier\b|^cd&r\b", "Clayton Dubilier & Rice"),
    (r"^acrew\b", "Acrew Capital"),
    (r"^bdc\b|^bridges\s+direct\b", "Bridges"),
    (r"^springblue\b", "SpringBlue"),
    (r"^red\s+admiral\b", "Red Admiral"),
    (r"^bear\s+coast\b", "Bear Coast"),
    (r"^triangle\s+investment\b", "Triangle"),
]

# Suffixes "lessicaux" qui terminent un nom de GP — utiles pour le fallback
GP_STOP_TOKENS = {
    "fund", "funds", "capital", "partners", "partner", "equity", "growth",
    "venture", "ventures", "credit", "debt", "investments", "investment",
    "advisors", "international", "global", "associates", "holdings",
    "secondaries", "secondary", "buyout", "lp", "llc", "ltd", "limited",
    "partnership", "inc", "inc.", "corp", "co", "co.",
    "private", "asia", "europe", "european", "asian", "china", "india",
    "opportunities", "opportunity", "technology", "tech", "energy",
    "real", "estate", "infrastructure", "infra", "healthcare", "health",
    "bio", "biopharm", "biotech", "pharma", "consumer", "industrial",
    "co-invest", "coinvest", "co-investment", "continuation",
    "gpe", "spv", "vehicle", "annex", "tactical",
}

ROMAN_OR_NUM_RE = re.compile(
    r"^("
    r"[ivxlcdm]+(?:[\-]?[a-z])?"  # roman + sleeve optionnel (V, V-D, VIIc)
    r"|[0-9]+(?:[\-]?[a-z])?"      # arabic + sleeve optionnel (2, 3-A)
    r"|[a-f]"                       # single sleeve letter (A, B, C, D, E, F)
    r")$",
    re.IGNORECASE,
)


# ============================================================================
# 4. FUND SERIES NUMBER EXTRACTION
# ============================================================================

# Détecte un numéro de série en fin de nom (avant suffixes juridiques) :
# "Fund III", "Partners X", "II-C", "Fund 2", "Fund IV-A", etc.
SERIES_RE = re.compile(
    r"\b("
    r"[IVX]+(?:[\-\s]?[A-Z](?:\s*\(\w+\))?)?"  # roman + sleeve
    r"|\d{1,2}(?:[\-\s]?[A-Z])?"                # arabic + sleeve
    r")"
    r"(?:[\s,\.]|$|\s*L\.?P\.?|\s*LLC|\s*Ltd)",
    re.IGNORECASE,
)


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass(frozen=True)
class ThemesResult:
    geo: list[str] = field(default_factory=list)
    style: list[str] = field(default_factory=list)

    @property
    def is_thematic(self) -> bool:
        return bool(self.geo or self.style)


# ============================================================================
# API
# ============================================================================

def detect_themes(name: str) -> ThemesResult:
    """Retourne {geo: [...], style: [...]} depuis le nom du fonds."""
    name_l = name.lower()
    geo = []
    seen_geo = set()
    for pattern, label in GEO_RULES:
        if re.search(pattern, name_l) and label not in seen_geo:
            geo.append(label)
            seen_geo.add(label)
    style = []
    seen_style = set()
    for pattern, label in STYLE_RULES:
        if re.search(pattern, name_l) and label not in seen_style:
            style.append(label)
            seen_style.add(label)
    return ThemesResult(geo=geo, style=style)


def extract_gp_family(name: str) -> str:
    """Retourne la GP family — table d'alias d'abord, fallback heuristique sinon."""
    name_l = name.lower().strip()
    # 1. Table d'alias (priorité)
    for pattern, canonical in GP_ALIAS:
        if re.search(pattern, name_l):
            return canonical
    # 2. Fallback : préfixe significatif jusqu'à stop token / numéro
    cleaned = re.sub(r"[^\w\s\-&]", " ", name)
    tokens = cleaned.split()
    out = []
    for tok in tokens:
        low = tok.lower().rstrip(",.").lstrip("-")
        if low in GP_STOP_TOKENS:
            break
        if ROMAN_OR_NUM_RE.fullmatch(tok) and out:
            break
        out.append(tok)
        if len(out) >= 3:
            break
    if not out:
        return name.split(",")[0].strip()
    return " ".join(out).strip()


def extract_fund_series(name: str) -> str | None:
    """Extrait le numéro de série (ex: 'V-D', 'III', '2', 'VII-C')."""
    # On retire d'abord les suffixes juridiques pour faciliter la détection
    cleaned = re.sub(r",?\s*(L\.?P\.?|LLC|Ltd|Limited|Inc\.?|Corp\.?)\b.*$", "", name, flags=re.IGNORECASE)
    # Le numéro est typiquement à la fin
    tokens = re.split(r"[\s,]+", cleaned.strip())
    if not tokens:
        return None
    # Cherche le dernier token qui ressemble à un numéro
    for tok in reversed(tokens):
        if ROMAN_OR_NUM_RE.fullmatch(tok):
            return tok.upper()
    return None
