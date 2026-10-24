"""
jarvis/interface/noticias.py — card de notícias com a foto da principal.

Recebe uma lista genérica de notícias ({title, source, url, snippet, image}),
escolhe a primeira que tem foto, baixa a imagem numa thread (a fala não
espera) e manda tudo para `ui.show_news`. Sem foto, sem `show_news` ou com
erro, cai no painel de texto de sempre (`ui.show_content`).

Hoje as notícias vêm da busca do Mark (actions/web_search.py, DuckDuckGo).
A fonte é trocável: o RSS planejado só precisa entregar a mesma lista.
"""

from __future__ import annotations

import threading

MAX_ITENS = 6
MAX_BYTES = 3 * 1024 * 1024     # foto maior que isto não vale o download
TIMEOUT = 4                     # segundos

_baixar_fn = None               # testes trocam o download


def _baixar(url: str) -> bytes | None:
    """Bytes da imagem, ou None. Só http(s), só image/*, com limite de tamanho."""
    if _baixar_fn is not None:
        return _baixar_fn(url)
    if not url.startswith(("https://", "http://")):
        return None
    import requests
    try:
        with requests.get(url, timeout=TIMEOUT, stream=True,
                          headers={"User-Agent": "Mozilla/5.0 JARVIS"}) as r:
            if r.status_code != 200 or not r.headers.get("Content-Type", "").startswith("image/"):
                return None
            dados = b""
            for pedaco in r.iter_content(64 * 1024):
                dados += pedaco
                if len(dados) > MAX_BYTES:
                    return None
            return dados or None
    except Exception:
        return None


def escolher(itens: list[dict]) -> tuple[list[dict], int | None]:
    """(as notícias que vão para o card, índice da que tem foto ou None)."""
    itens = [i for i in itens if (i.get("title") or "").strip()][:MAX_ITENS]
    for n, item in enumerate(itens):
        if (item.get("image") or "").strip():
            return itens, n
    return itens, None


def _desenhar(ui, titulo: str, itens: list[dict], indice: int | None, texto: str) -> None:
    foto = None
    if indice is not None:
        foto = _baixar(itens[indice]["image"])
        if foto is None:                         # foto falhou: tenta a próxima
            for n in range(indice + 1, len(itens)):
                if itens[n].get("image"):
                    foto = _baixar(itens[n]["image"])
                    if foto is not None:
                        indice = n
                        break
    try:
        ui.show_news(titulo, itens, foto, indice if foto is not None else None)
    except Exception:
        ui.show_content(titulo, texto)


def mostrar(ui, titulo: str, texto: str, itens: list[dict] | None = None,
            esperar: bool = False) -> None:
    """Mostra o card. `texto` é o que já ia para o painel; vira o plano B.
    `esperar=True` só nos testes; no app o download corre em segundo plano."""
    if itens is None:
        try:
            from actions import web_search
            itens = web_search.ultimas_noticias()
        except Exception:
            itens = []
    itens, indice = escolher(itens or [])
    if not itens or not hasattr(ui, "show_news"):
        ui.show_content(titulo, texto)
        return
    # O texto aparece já; a foto chega quando o download terminar.
    ui.show_news(titulo, itens, None, None)
    if indice is None:
        return
    t = threading.Thread(target=_desenhar, args=(ui, titulo, itens, indice, texto),
                         daemon=True, name="jarvis-foto-noticia")
    t.start()
    if esperar:
        t.join()
