"""
jarvis/pesquisa/fontes.py — de onde vêm os resultados e o texto das páginas.

- Tavily: busca feita para agentes, já devolve o texto das páginas. Só com
  "tavily_api_key" em config/api_keys.json (grátis: 1.000 buscas por mês).
- DuckDuckGo: o mesmo do Mark (actions/web_search.py); só título e trecho.
- ler(url): baixa a página direto (requests + BeautifulSoup, menos de 1 s nos
  testes) e, se ela bloquear ou vier vazia, tenta o Jina Reader (5 a 7 s).

Nada aqui chama modelo. Tudo que sai daqui é texto de terceiros.
"""

from __future__ import annotations

import re

import requests

TAVILY_URL = "https://api.tavily.com/search"
JINA_URL = "https://r.jina.ai/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JARVIS/1.0"}

TIMEOUT_TAVILY = 6
TIMEOUT_PAGINA = 5
TIMEOUT_JINA = 8
MIN_TEXTO = 300        # menos que isso é página vazia, login ou desafio anti-robô

# Páginas que não têm texto para ler (vídeo, rede social) ou que sempre
# devolvem desafio anti-robô. O título e o trecho da busca continuam valendo.
NAO_LER = ("youtube.com", "youtu.be", "instagram.com", "facebook.com",
           "tiktok.com", "x.com", "twitter.com", "scribd.com")

# Testes trocam a rede: get(url, **kw) e post(url, **kw) → objeto com
# .status_code, .text e .json().
_get = requests.get
_post = requests.post


def _limpar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def tavily(consulta: str, chave: str, max_resultados: int = 5) -> tuple[str, list[dict]]:
    """(resposta curta do Tavily, resultados com texto). Levanta em erro."""
    r = _post(TAVILY_URL, timeout=TIMEOUT_TAVILY,
              headers={"Authorization": f"Bearer {chave}"},
              json={"query": consulta, "search_depth": "basic",
                    "max_results": max_resultados, "include_answer": "basic",
                    "include_raw_content": "text"})
    if r.status_code != 200:
        raise RuntimeError(f"Tavily HTTP {r.status_code}")
    dados = r.json()
    itens = [{"title": _limpar(i.get("title")),
              "url": i.get("url") or "",
              "snippet": _limpar(i.get("content")),
              "texto": _limpar(i.get("raw_content"))}
             for i in dados.get("results") or []]
    return _limpar(dados.get("answer")), itens


def ddg(consulta: str, max_resultados: int = 6) -> list[dict]:
    from actions.web_search import _ddg_search
    return [dict(i, texto="") for i in _ddg_search(consulta, max_results=max_resultados)]


def pode_ler(url: str) -> bool:
    return url.startswith("http") and not any(d in url for d in NAO_LER)


def _direto(url: str) -> str:
    from bs4 import BeautifulSoup
    r = _get(url, headers=UA, timeout=TIMEOUT_PAGINA)
    if r.status_code != 200:
        return ""
    sopa = BeautifulSoup(r.text, "html.parser")
    for el in sopa(["script", "style", "nav", "header", "footer", "aside",
                    "form", "noscript", "svg"]):
        el.decompose()
    return _limpar(sopa.get_text(" "))


def _jina(url: str) -> str:
    r = _get(JINA_URL + url, headers={"X-Return-Format": "text"}, timeout=TIMEOUT_JINA)
    return _limpar(r.text) if r.status_code == 200 else ""


def ler(url: str) -> str:
    """Texto da página, ou '' quando nenhum dos dois caminhos conseguiu."""
    texto = ""
    try:
        texto = _direto(url)
    except Exception as e:
        print(f"[Pesquisa] leitura direta falhou ({type(e).__name__}): {url[:80]}")
    if len(texto) >= MIN_TEXTO and "Client Challenge" not in texto[:200]:
        return texto
    try:
        return _jina(url)
    except Exception as e:
        print(f"[Pesquisa] Jina falhou ({type(e).__name__}): {url[:80]}")
        return texto if len(texto) >= MIN_TEXTO else ""
