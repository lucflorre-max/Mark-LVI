"""
jarvis/integrations/rss.py — notícias por RSS, com foto quando o feed traz.

Só a biblioteca padrão (xml.etree) e o `requests` que já vem do Mark. Lê RSS
2.0, RDF (RSS 1.0) e Atom. A foto sai, nesta ordem, de media:content,
media:thumbnail, enclosure de imagem ou do primeiro <img> da descrição.

Devolve a mesma lista genérica do card (jarvis/interface/noticias.py):
    {"title", "source", "url", "snippet", "image", "data"}

Os feeds ficam em jarvis/noticias_fontes.py. Tudo que vem daqui é texto de
terceiros: quem passa ao modelo embrulha como conteúdo não confiável.
"""

from __future__ import annotations

import html
import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

TIMEOUT = 6            # segundos por feed
CACHE_SEG = 600        # 10 minutos: abrir o Jarvis de novo não baixa tudo outra vez
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JARVIS-RSS/1.0"}

_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = threading.Lock()
_baixar_fn = None      # testes trocam o download: url -> bytes


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _texto(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def _limpar(texto: str, limite: int = 280) -> str:
    """HTML da descrição → texto curto."""
    t = re.sub(r"<[^>]+>", " ", texto or "")
    t = re.sub(r"\s+", " ", html.unescape(t)).strip()
    # Rodapé automático do WordPress: "The post X appeared first on Y."
    t = re.sub(r"\s*(The post|O post) .*?(appeared first on|apareceu primeiro em) .*$", "", t)
    return t if len(t) <= limite else t[: limite - 1].rsplit(" ", 1)[0] + "…"


def _data(texto: str) -> datetime | None:
    if not texto:
        return None
    try:
        dt = parsedate_to_datetime(texto)             # RSS: RFC 822
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(texto.strip().replace("Z", "+00:00"))  # Atom/RDF
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _foto(item) -> str:
    melhor, area = "", -1
    for el in item.iter():
        nome = _local(el.tag)
        url = el.get("url") or ""
        if nome in ("content", "thumbnail") and url:
            tipo = el.get("type") or el.get("medium") or "image"
            if "image" in tipo or nome == "thumbnail":
                try:
                    a = int(el.get("width") or 0) * int(el.get("height") or 0)
                except ValueError:
                    a = 0
                if a > area:                          # a maior das fotos oferecidas
                    melhor, area = url, a
        elif nome == "enclosure" and url and "image" in (el.get("type") or "") and not melhor:
            melhor = url
    if melhor:
        return melhor
    for el in item.iter():
        if _local(el.tag) in ("description", "encoded", "content", "summary") and el.text:
            m = re.search(r"<img[^>]+src=[\"']([^\"']+)", el.text, re.I)
            if m:
                return html.unescape(m.group(1))
    return ""


def _link(item) -> str:
    for el in item:
        if _local(el.tag) == "link":
            return (el.get("href") or el.text or "").strip()
    return ""


def ler(conteudo: bytes, fonte: str) -> list[dict]:
    """Bytes de um feed → lista de notícias. Levanta ET.ParseError se não for XML."""
    raiz = ET.fromstring(conteudo)
    itens = []
    for item in raiz.iter():
        if _local(item.tag) not in ("item", "entry"):
            continue
        campos = {_local(el.tag): el for el in item}
        titulo = _limpar(_texto(campos.get("title")), 200)
        if not titulo:
            continue
        desc = (_texto(campos.get("description")) or _texto(campos.get("summary"))
                or _texto(campos.get("encoded")))
        quando = (_texto(campos.get("pubdate")) or _texto(campos.get("published"))
                  or _texto(campos.get("updated")) or _texto(campos.get("date")))
        itens.append({"title": titulo, "source": fonte, "url": _link(item),
                      "snippet": _limpar(desc), "image": _foto(item),
                      "data": _data(quando)})
    return itens


def _baixar(url: str) -> bytes:
    if _baixar_fn is not None:
        return _baixar_fn(url)
    import requests
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content


def feed(nome: str, url: str) -> list[dict]:
    """Um feed, com cache. Falhou → lista vazia (e o cache antigo, se houver)."""
    agora = time.monotonic()
    with _lock:
        guardado = _cache.get(url)
        if guardado and agora - guardado[0] < CACHE_SEG:
            return guardado[1]
    try:
        itens = ler(_baixar(url), nome)
    except Exception as e:
        print(f"[JARVIS RSS] {nome}: {type(e).__name__}")
        return guardado[1] if guardado else []
    with _lock:
        _cache[url] = (agora, itens)
    return itens


def varios(fontes: list[tuple[str, str]]) -> list[dict]:
    """Vários feeds em paralelo, todos juntos."""
    if not fontes:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(fontes))) as ex:
        listas = list(ex.map(lambda f: feed(*f), fontes))
    return [i for lista in listas for i in lista]


def _chave(titulo: str) -> str:
    return re.sub(r"\W+", " ", titulo.lower()).strip()[:60]


def misturar(itens: list[dict], limite: int = 8, por_fonte: int = 2) -> list[dict]:
    """As mais recentes, sem repetir manchete e no máximo `por_fonte` de cada
    site, para o card não virar só g1."""
    antigo = datetime.min.replace(tzinfo=timezone.utc)
    ordem = sorted(itens, key=lambda i: i.get("data") or antigo, reverse=True)
    vistos, contagem, saida = set(), {}, []
    for i in ordem:
        chave = _chave(i["title"])
        if chave in vistos or contagem.get(i["source"], 0) >= por_fonte:
            continue
        vistos.add(chave)
        contagem[i["source"]] = contagem.get(i["source"], 0) + 1
        saida.append(i)
        if len(saida) >= limite:
            break
    return saida


def limpar_cache() -> None:
    with _lock:
        _cache.clear()
