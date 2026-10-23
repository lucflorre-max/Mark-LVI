"""
jarvis/config.py — configurações do JARVIS.

Os valores ficam em config/api_keys.json (fora do Git), ao lado dos do Mark.
"""

from __future__ import annotations


def _keys() -> dict:
    try:
        from memory.config_manager import load_api_keys
        return load_api_keys() or {}
    except Exception:
        return {}


def dashboard_enabled() -> bool:
    """Painel do celular. Desligado até alguém pôr "dashboard_enabled": true
    em config/api_keys.json (auditoria, achado 3)."""
    return _keys().get("dashboard_enabled") is True


def transcript_enabled() -> bool:
    """Transcrição local em data/conversas/. Ligada até alguém pôr
    "transcript_enabled": false em config/api_keys.json."""
    return _keys().get("transcript_enabled") is not False
