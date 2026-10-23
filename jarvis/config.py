"""
jarvis/config.py — configurações do JARVIS.

Valores fixos ficam aqui. Os que o usuário pode mudar ficam em
config/api_keys.json (fora do Git), ao lado dos do Mark.
"""

from __future__ import annotations

from datetime import timedelta, timezone, tzinfo
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "jarvis.db"

IDIOMA = "pt-BR"
FUSO_NOME = "America/Sao_Paulo"

# Busca de notícias do briefing inicial. Em inglês, o buscador devolvia as
# manchetes dos EUA; esta foi a que trouxe g1/Reuters Brasil no teste por voz.
BRIEFING_NOTICIAS = "manchetes notícias Brasil hoje"


def _keys() -> dict:
    try:
        from memory.config_manager import load_api_keys
        return load_api_keys() or {}
    except Exception:
        return {}


def nome_assistente() -> str:
    """O nome configurado no Mark (⚙), ou JARVIS."""
    return str(_keys().get("assistant_name") or "JARVIS").strip() or "JARVIS"


def fuso() -> tzinfo:
    """America/Sao_Paulo quando o Windows tem a base de fusos (pacote tzdata);
    senão UTC−3 fixo, que é o mesmo desde que o Brasil acabou com o horário de
    verão (Decreto 9.772/2019)."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(FUSO_NOME)
    except Exception:
        return timezone(timedelta(hours=-3), "BRT")


# Palavras que o reconhecimento de voz costuma errar. Ajudam a transcrição.
VOCABULARIO = [
    "Jarvis", "Mestre Luc", "Internacional", "Inter", "Colorado", "GZH",
    "Bloco de Notas", "WhatsApp", "Trello", "anota aí", "desfaz",
]


def transcricao_entrada() -> dict:
    """Configuração da transcrição da voz do usuário no Gemini Live.

    Sem isto o Live adivinha o idioma a cada frase, e no teste por voz
    transcreveu português como inglês ("The price is for you"). Aceito pelo
    servidor em 23/10/2026 (teste de conexão com gemini-3.1-flash-live-preview).
    """
    vocab = list(VOCABULARIO)
    try:
        from jarvis.memory import perfil   # vocabulário que o usuário aprovou
        vocab += [v for v in perfil.vocabulario_aprovado() if v not in vocab]
    except Exception as e:
        print(f"[Config] perfil indisponível: {e}")
    return {"language_codes": [IDIOMA], "custom_vocabulary": vocab}


def dashboard_enabled() -> bool:
    """Painel do celular. Desligado até alguém pôr "dashboard_enabled": true
    em config/api_keys.json (auditoria, achado 3)."""
    return _keys().get("dashboard_enabled") is True


def transcript_enabled() -> bool:
    """Transcrição local em data/conversas/. Ligada até alguém pôr
    "transcript_enabled": false em config/api_keys.json."""
    return _keys().get("transcript_enabled") is not False
