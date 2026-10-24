"""
jarvis/integrations/noticias.py — notícias por tema, a partir dos feeds RSS.

Fontes testadas em 23/10/2026: todas responderam com RSS válido e notícias do
dia; quase todas trazem foto. Ficaram de fora: GZH e Correio do Povo (sem RSS
público, o endereço devolve HTML ou 404), UOL (sem data nas notícias), ge
Inter e g1 Ciência (feeds parados), Sul21 (retirado a pedido do usuário). As notícias do Inter saem do ge e do ge RS
filtradas pelo nome do clube.

Usado pelo briefing (main.py) e pela ferramenta jarvis_noticias.
"""

from __future__ import annotations

import re
import threading
import unicodedata
from datetime import datetime, timedelta, timezone

from jarvis.integrations import rss

FONTES: dict[str, list[tuple[str, str]]] = {
    "geral": [
        ("g1", "https://g1.globo.com/rss/g1/"),
        ("Folha", "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml"),
        ("Estadão", "https://www.estadao.com.br/arc/outboundfeeds/feeds/rss/sections/brasil/"),
        ("O Globo", "https://oglobo.globo.com/rss/oglobo"),
        ("CNN Brasil", "https://www.cnnbrasil.com.br/feed/"),
        ("Agência Brasil", "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml"),
        ("Poder360", "https://www.poder360.com.br/feed/"),
        ("Metrópoles", "https://www.metropoles.com/feed"),
        ("Gazeta do Povo", "https://www.gazetadopovo.com.br/feed/rss/ultimas-noticias.xml"),
        ("CartaCapital", "https://www.cartacapital.com.br/feed/"),
        ("BBC Brasil", "https://feeds.bbci.co.uk/portuguese/rss.xml"),
    ],
    "mundo": [
        ("BBC Brasil", "https://feeds.bbci.co.uk/portuguese/rss.xml"),
        ("DW Brasil", "https://rss.dw.com/rdf/rss-br-all"),
        ("RFI Brasil", "https://www.rfi.fr/br/rss"),
        ("g1 Mundo", "https://g1.globo.com/rss/g1/mundo/"),
    ],
    "rs": [
        ("g1 RS", "https://g1.globo.com/rss/g1/rs/rio-grande-do-sul/"),
    ],
    "esporte": [
        ("ge", "https://ge.globo.com/rss/ge/"),
        ("ge RS", "https://ge.globo.com/rss/ge/rs/"),
    ],
    "economia": [
        ("g1 Economia", "https://g1.globo.com/rss/g1/economia/"),
        ("Valor", "https://valor.globo.com/rss/valor"),
        ("InfoMoney", "https://www.infomoney.com.br/feed/"),
        ("Exame", "https://exame.com/feed/"),
    ],
    "tecnologia": [
        ("g1 Tecnologia", "https://g1.globo.com/rss/g1/tecnologia/"),
        ("Tecnoblog", "https://tecnoblog.net/feed/"),
        ("Tecmundo", "https://rss.tecmundo.com.br/feed"),
        ("Canaltech", "https://canaltech.com.br/rss/"),
        ("Olhar Digital", "https://olhardigital.com.br/feed/"),
    ],
}

# Temas que são um filtro sobre outro tema: tema → (base, palavras).
FILTROS = {
    "inter": ("esporte", ("inter", "internacional", "colorado", "colorados", "beira-rio")),
    "gremio": ("esporte", ("gremio", "tricolor gaucho", "arena do gremio")),
}
TEMAS = tuple(FONTES) + tuple(FILTROS)

# O briefing: o que importa no dia, sem virar um jornal inteiro.
BRIEFING = (("geral", 4), ("rs", 2), ("inter", 1), ("economia", 1), ("tecnologia", 1))

MAX_IDADE = timedelta(hours=48)

# Notícia que não é notícia: sorteio, horóscopo, palpite de aposta.
RUIDO = ("quina", "mega sena", "mega-sena", "lotofacil", "lotomania", "timemania",
         "dupla sena", "dia de sorte", "super sete", "loteria", "loterias",
         "horoscopo", "signo", "signos", "palpites")

_ultimas: list[dict] = []
_lock = threading.Lock()
_agora = None        # testes: () -> datetime com fuso


def _sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _contem(item: dict, palavras) -> bool:
    texto = f" {_sem_acento(item['title'])} {_sem_acento(item.get('snippet', ''))} "
    return any(re.search(rf"\b{re.escape(_sem_acento(p))}\b", texto) for p in palavras)


def _recentes(itens: list[dict]) -> list[dict]:
    """Das últimas 48 h e sem ruído (loteria, horóscopo)."""
    agora = _agora() if _agora else datetime.now(timezone.utc)
    return [i for i in itens
            if (i.get("data") is None or agora - i["data"] <= MAX_IDADE)
            and not _contem({"title": i["title"]}, RUIDO)]


def normalizar_tema(tema: str | None) -> str:
    t = _sem_acento(tema or "geral").strip()
    apelidos = {"": "geral", "brasil": "geral", "gerais": "geral", "politica": "geral",
                "rio grande do sul": "rs", "porto alegre": "rs", "gaucho": "rs",
                "internacional": "inter", "colorado": "inter", "futebol": "esporte",
                "esportes": "esporte", "tech": "tecnologia", "ti": "tecnologia",
                "internacionais": "mundo", "exterior": "mundo", "mercado": "economia",
                "financas": "economia"}
    t = apelidos.get(t, t)
    return t if t in TEMAS else ""


def tema(nome: str, limite: int = 8, busca: str = "") -> list[dict]:
    """Notícias recentes de um tema, misturadas entre os sites. `busca`
    filtra por palavra (sem acento, palavra inteira)."""
    base, palavras = FILTROS.get(nome, (nome, ()))
    itens = _recentes(rss.varios(FONTES[base]))
    if palavras:
        itens = [i for i in itens if _contem(i, palavras)]
    if busca:
        itens = [i for i in itens if _contem(i, busca.split())]
    por_fonte = 3 if palavras or busca else 2
    return rss.misturar(itens, limite=limite, por_fonte=por_fonte)


def buscar(busca: str, limite: int = 8) -> list[dict]:
    """Procura uma palavra em todos os feeds."""
    todas = {url: (n, url) for lista in FONTES.values() for n, url in lista}
    itens = [i for i in _recentes(rss.varios(list(todas.values())))
             if _contem(i, busca.split())]
    return rss.misturar(itens, limite=limite, por_fonte=3)


def guardar(itens: list[dict]) -> list[dict]:
    global _ultimas
    with _lock:
        _ultimas = [dict(i) for i in itens]
    return itens


def ultimas() -> list[dict]:
    with _lock:
        return [dict(i) for i in _ultimas]


def formatar(itens: list[dict], cabecalho: str) -> str:
    """Texto para o modelo (e plano B do painel), no formato do Mark."""
    linhas = [cabecalho, ""]
    for n, i in enumerate(itens, 1):
        linhas.append(f"{n}. {i['title']}  [{i['source']}]")
        if i.get("snippet"):
            linhas.append(f"   {i['snippet'][:160]}")
    return "\n".join(linhas).strip()


def briefing() -> str:
    """As notícias do briefing de abertura. '' se nenhum feed respondeu (o
    main.py então usa a busca antiga do Mark)."""
    # Baixa todos os feeds do briefing de uma vez; os temas leem do cache.
    fontes = {url: (n, url) for nome, _ in BRIEFING
              for n, url in FONTES[FILTROS.get(nome, (nome,))[0]]}
    rss.varios(list(fontes.values()))
    vistos, itens = set(), []
    for nome, qtd in BRIEFING:
        for i in tema(nome, limite=qtd + 2):
            if i["url"] not in vistos and qtd > 0:
                vistos.add(i["url"])
                itens.append(i)
                qtd -= 1
    guardar(itens)
    if not itens:
        return ""
    return formatar(itens, "Notícias de hoje (Brasil, RS, Inter, economia e tecnologia):")
