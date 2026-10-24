"""
jarvis/brain/ler_sem_abrir.py — pesquisar e ler sem abrir o navegador.

No teste por voz (24/10/2026), "fala mais do jogo contra o Botafogo" virou
`browser_control` search — que abre o navegador e pede o clique — mesmo com a
regra no prompt. Saber de algo é só leitura; abrir o navegador é para quando
o usuário quer VER.

Então o portão (jarvis/brain/gate.py) troca, antes do banner:

    browser_control search  →  pesquisador (busca e lê as páginas por dentro)
    browser_control go_to   →  lê a página por dentro

…a não ser que o usuário tenha falado, nos últimos segundos, em abrir,
mostrar, navegador ou tela. Aí o pedido segue como sempre, com o clique.

O que volta para o modelo vem no envelope de conteúdo não confiável.
"""

from __future__ import annotations

import re
import unicodedata

from jarvis.brain import policy

JANELA_SEG = 30.0          # quanto da fala recente conta
MAX_PAGINA = 3000

# Palavras que mostram que ele quer VER a página, não só saber.
_QUER_VER = re.compile(
    r"\b(abre|abra|abrir|abrindo|abri|navegador|browser|chrome|edge|firefox|"
    r"mostra|mostre|mostrar|na tela|ver no site|ver a pagina|quero ver)\b")

_pesquisar = None          # testes trocam: consulta -> texto
_ler_pagina = None         # testes trocam: url -> texto


def _sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def quer_ver(falas: list[str]) -> bool:
    return any(_QUER_VER.search(_sem_acento(f)) for f in falas)


def _pesquisa(consulta: str) -> tuple[str, str]:
    """(achado, nota fora do envelope)."""
    if _pesquisar is not None:
        return _pesquisar(consulta), ""
    from jarvis.pesquisa import pesquisador  # noqa: PLC0415
    return pesquisador.pesquisar(consulta), "\n" + pesquisador.NOTA


def _pagina(url: str) -> str:
    if _ler_pagina is not None:
        return _ler_pagina(url)
    from jarvis.pesquisa import fontes  # noqa: PLC0415
    return fontes.ler(url) if fontes.pode_ler(url) else ""


def _untrusted(texto: str) -> str:
    from core import outcome  # noqa: PLC0415 — só existe dentro do Mark
    return outcome.untrusted("web", texto)


_AVISO = ("[READ_WITHOUT_BROWSER] The browser was NOT opened: the user only "
          "asked to know about this, so I searched and read the pages silently. "
          "Answer from this now, in a few sentences, citing the source. Do not "
          "ask for confirmation. If they want to see it on screen they will say "
          "so (\"abre no navegador\").\n")


def substituir(name: str, args: dict, falas: list[str]) -> str | None:
    """O resultado da leitura, ou None para seguir o caminho de sempre."""
    if name != "browser_control" or quer_ver(falas):
        return None
    acao = policy.sub_action(args)
    try:
        if acao == "search" and str(args.get("query") or "").strip():
            achado, nota = _pesquisa(str(args["query"]).strip())
        elif acao == "go_to" and str(args.get("url") or "").strip():
            achado, nota = _pagina(str(args["url"]).strip())[:MAX_PAGINA], ""
        else:
            return None
    except Exception as e:
        print(f"[JARVIS] leitura sem navegador falhou ({type(e).__name__}); segue o pedido normal")
        return None
    if not achado:
        return None
    print(f"[JARVIS] {acao} sem abrir o navegador (só leitura)")
    return _AVISO + _untrusted(achado) + nota
