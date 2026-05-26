"""Charge les notes de contexte marché et expose l'index pour insertion."""
from __future__ import annotations

import json
from datetime import date

import streamlit as st

from aim.app.config import VAULT_DIR


@st.cache_data(ttl=3600)
def load_index() -> list[dict]:
    """Charge index.json — liste des notes avec snapshots associés."""
    path = VAULT_DIR / "index.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("notes", [])


@st.cache_data(ttl=3600)
def load_note(note_id: str) -> str:
    """Charge le markdown d'une note."""
    path = VAULT_DIR / f"{note_id}.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def notes_for_snapshot(snapshot: date | str) -> list[dict]:
    """Retourne les notes pertinentes pour un snapshot donné (date ISO)."""
    snap_str = str(snapshot)[:10]
    out = []
    for note in load_index():
        if snap_str in note.get("snapshots", []):
            out.append(note)
    return out


def notes_for_tag(tag: str) -> list[dict]:
    """Retourne les notes avec un tag particulier (ex: 'calpers-specific', 'energy')."""
    return [n for n in load_index() if tag in n.get("tags", [])]


def render_context_banner(snapshot: date | str) -> None:
    """Insère un bandeau Streamlit avec les notes pertinentes du snapshot."""
    notes = notes_for_snapshot(snapshot)
    if not notes:
        return
    for note in notes:
        with st.expander(f"Contexte macro — {note['title']}"):
            md = load_note(note["id"])
            # Strip frontmatter YAML pour affichage propre
            if md.startswith("---"):
                _, _, body = md.partition("---\n")
                _, _, body = body.partition("---\n")
                md = body
            st.markdown(md)
