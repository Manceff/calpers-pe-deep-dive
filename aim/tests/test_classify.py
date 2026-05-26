"""Tests de la classification : themes (geo + style) et gp_family."""
import pytest

from aim.pipeline._classify import detect_themes, extract_fund_series, extract_gp_family


# ============================================================================
# THEMES — la règle clé : Généraliste sauf si nom contient un marqueur explicite
# ============================================================================

@pytest.mark.parametrize("name,exp_geo,exp_style", [
    # --- Pure Généraliste ---
    ("Advent International GPE V-D, L.P.", [], []),
    ("Clearlake Capital Partners V, L.P.", [], []),
    ("Tiger Global Private Investment Partners XV, L.P.", [], []),
    ("Hellman & Friedman Capital Partners X, L.P.", [], []),
    ("Blackstone Tactical Opportunities Fund III-C L.P.", [], []),
    ("57 Stars Global Opportunities Fund, LLC", [], []),  # 'Global' seul ne tagge pas
    # --- Thématique géographique ---
    ("AACP China Growth Investors", ["China"], ["Growth"]),
    ("AACP India Investors B", ["India"], []),
    ("KKR Asian Fund IV", ["Asia"], []),
    ("Carlyle Asia Partners V", ["Asia"], []),
    ("CVC European Equity Partners III LP", ["Europe"], []),
    ("HongShan Capital Venture Fund IX, L.P.", ["China"], ["Venture Capital"]),
    # --- Thématique sectorielle ---
    ("Riverstone Global Energy and Power Fund V, L.P.", [], ["Energy"]),
    ("CalPERS Clean Energy & Technology Fund, LLC", [], ["Cleantech", "Energy", "Technology"]),
    ("Advent Global Technology II Limited Partnership", [], ["Technology"]),
    # --- Thématique style ---
    ("AlpInvest Secondaries VII", [], ["Secondaries"]),
    ("New Mountain CAS Continuation Fund, L.P.", [], ["Continuation"]),
    ("KKR Co-Investment Fund III, L.P.", [], ["Co-Investment"]),
    ("Khosla Ventures Seed, L.P.", [], ["Venture Capital"]),
    ("Arsenal Capital Partners Growth LP", [], ["Growth"]),
    ("Apollo Credit Opportunity Fund I", [], ["Credit"]),
    # --- Multi-thèmes ---
    ("AACP China Growth Investors", ["China"], ["Growth"]),
    ("HongShan Capital Venture Fund IX, L.P.", ["China"], ["Venture Capital"]),
])
def test_detect_themes(name, exp_geo, exp_style):
    r = detect_themes(name)
    assert r.geo == exp_geo, f"{name}: geo {r.geo} != {exp_geo}"
    assert r.style == exp_style, f"{name}: style {r.style} != {exp_style}"


def test_is_thematic():
    """Généraliste = pas de thème ; Thématique = au moins un thème."""
    assert detect_themes("Advent International GPE V-D, L.P.").is_thematic is False
    assert detect_themes("AACP China Growth Investors").is_thematic is True
    assert detect_themes("AlpInvest Secondaries VII").is_thematic is True
    assert detect_themes("Khosla Ventures Seed").is_thematic is True


# ============================================================================
# GP FAMILY — table d'alias prioritaire, fallback heuristique
# ============================================================================

@pytest.mark.parametrize("name,expected", [
    # Table d'alias
    ("Blackstone Tactical Opportunities Fund III-C L.P.", "Blackstone"),
    ("Blackstone Capital Partners VII L.P.", "Blackstone"),
    ("KKR Asian Fund IV", "KKR"),
    ("KKR Co-Investment Fund III, L.P.", "KKR"),
    ("Carlyle Asia Partners V", "Carlyle"),
    ("Carlyle Europe Partners V", "Carlyle"),
    ("Apollo Credit Opportunity Fund I", "Apollo"),
    ("Advent International GPE V-D, L.P.", "Advent"),
    ("CVC European Equity Partners III LP", "CVC"),
    ("Clearlake Capital Partners V", "Clearlake"),
    ("Hellman & Friedman Capital Partners X, L.P.", "Hellman & Friedman"),
    ("Silver Lake Partners V, L.P.", "Silver Lake"),
    ("Riverstone Global Energy and Power Fund V, L.P.", "Riverstone"),
    ("Tiger Global Private Investment Partners XV, L.P.", "Tiger Global"),
    ("HongShan Capital Venture Fund IX, L.P.", "HongShan (ex-Sequoia China)"),
    ("AlpInvest Secondaries VII", "AlpInvest"),
    ("AACP China Growth Investors", "Asia Alternatives (AACP)"),
    ("57 Stars Global Opportunities Fund, LLC", "57 Stars"),
    # Fallback heuristique
    ("Generic Boutique LLC", "Generic Boutique"),
    ("Trident Maritime Fund", "Trident"),
])
def test_extract_gp_family(name, expected):
    assert extract_gp_family(name) == expected


# ============================================================================
# FUND SERIES
# ============================================================================

@pytest.mark.parametrize("name,expected", [
    ("Advent International GPE V-D, L.P.", "V-D"),
    ("Clearlake Capital Partners V, L.P.", "V"),
    ("CVC European Equity Partners III LP", "III"),
    ("KKR Asian Fund IV", "IV"),
    ("AACP India Investors B", "B"),
    ("Apollo Credit Opportunity Fund I", "I"),
    ("Blackstone Tactical Opportunities Fund III-C L.P.", "III-C"),
    ("Tiger Global Private Investment Partners XV, L.P.", "XV"),
    ("2024 Golden Bay, L.P.", "2024"),  # vintage utilisé comme nom
])
def test_extract_fund_series(name, expected):
    assert extract_fund_series(name) == expected
