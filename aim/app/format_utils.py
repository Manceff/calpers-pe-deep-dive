"""Helpers de formatage pour l'UI (USD, %, dates…)."""
from __future__ import annotations


def fmt_usd(v, scale: str = "auto", decimals: int | None = None) -> str:
    """Format USD avec auto-scaling : k / M / Md."""
    if v is None:
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    if scale == "auto":
        absv = abs(v)
        if absv >= 1e9:
            d = decimals if decimals is not None else 2
            return f"{v/1e9:,.{d}f} Md $"
        elif absv >= 1e6:
            d = decimals if decimals is not None else 1
            return f"{v/1e6:,.{d}f} M $"
        elif absv >= 1e3:
            d = decimals if decimals is not None else 0
            return f"{v/1e3:,.{d}f} k $"
        else:
            d = decimals if decimals is not None else 0
            return f"{v:,.{d}f} $"
    elif scale == "B":
        d = decimals if decimals is not None else 2
        return f"{v/1e9:,.{d}f} Md $"
    elif scale == "M":
        d = decimals if decimals is not None else 1
        return f"{v/1e6:,.{d}f} M $"
    return f"{v:,.0f} $"


def fmt_pct(v, decimals: int = 1) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.{decimals}f} %"
    except (TypeError, ValueError):
        return "—"


def fmt_mult(v, decimals: int = 2) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.{decimals}f}×"
    except (TypeError, ValueError):
        return "—"


def fmt_int(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return "—"


def winsorize_irr(v: float, cap: float = 100.0) -> float:
    """Écrête les IRR extrêmes pour l'affichage (pas pour le calcul)."""
    if v is None:
        return None
    if v > cap:
        return cap
    if v < -cap:
        return -cap
    return v
