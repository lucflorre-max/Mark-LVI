"""
jarvis/memory/transcript.py — transcrição local das conversas.

Um arquivo por dia em data/conversas/AAAA-MM-DD.md (fora do Git): o que o
usuário disse, o que o JARVIS respondeu e as ferramentas que ele chamou, com o
resultado. Serve para analisar e melhorar o assistente; nada sai do PC.

Desligar: "transcript_enabled": false em config/api_keys.json.
Nunca levanta exceção: uma falha de disco não pode derrubar a conversa.
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

from jarvis import config

_ROOT = Path(__file__).resolve().parents[2]
_DIR = _ROOT / "data" / "conversas"
_lock = threading.Lock()
_MAX = 600   # corta argumentos e resultados longos


def _short(text, limit: int = _MAX) -> str:
    text = str(text).replace("\r", " ").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _write(line: str, now: datetime | None = None, folder: Path | None = None) -> None:
    try:
        if not config.transcript_enabled():
            return
        now = now or datetime.now()
        folder = folder or _DIR
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{now:%Y-%m-%d}.md"
        with _lock:
            new = not path.exists()
            with path.open("a", encoding="utf-8") as f:
                if new:
                    f.write(f"# Conversas de {now:%d/%m/%Y}\n\n")
                f.write(f"- `{now:%H:%M:%S}` {line}\n")
    except Exception as e:
        print(f"[Transcript] falhou: {e}")


def user(text: str) -> None:
    _write(f"**Você:** {_short(text, 2000)}")


def assistant(name: str, text: str) -> None:
    _write(f"**{name}:** {_short(text, 2000)}")


def tool(name: str, args: dict) -> None:
    _write(f"🔧 `{name}` {_short(args)}")


def result(name: str, value) -> None:
    _write(f"↳ `{name}` → {_short(value)}")
