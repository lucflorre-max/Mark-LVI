"""
jarvis/pesquisa/pesquisador.py — uma pesquisa, uma resposta, com prazo.

Antes, o web_search do Mark tentava a busca do Gemini (cota esgotada → quatro
recusas seguidas), caía no DuckDuckGo, que só traz título e trecho, e o modelo
de voz pesquisava de novo até seis vezes sem achar o conteúdo.

Agora:
  1. Tavily, se houver chave; senão DuckDuckGo.
  2. Lê as melhores páginas em paralelo (fontes.ler) quando a busca não trouxe
     o texto.
  3. Dos textos, guarda só os trechos que falam do que foi perguntado.
  4. Tudo dentro de PRAZO segundos: o que não chegou a tempo fica de fora.

Quem responde é o próprio modelo de voz, lendo os trechos: sem um segundo
modelo para resumir, sem gastar mais cota e sem mais uma espera.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, wait

from jarvis import config
from jarvis.pesquisa import fontes

PRAZO = 10.0           # segundos para a pesquisa inteira
PAGINAS = 3            # quantas páginas ler
TRECHO_POR_PAGINA = 1200
TOTAL = 4500           # tamanho máximo do que volta para o modelo
CACHE_SEG = 600

# Fica FORA do embrulho de conteúdo não confiável (actions/web_search.py).
NOTA = ("[RESEARCH_DONE] This is everything the search found. Answer the user "
        "now from it, in one go. Do not call web_search again for the same "
        "question. If the answer is not in it, say so briefly and name the best "
        "source to open.")

_PARADAS = set("""a o as os de da do das dos e em no na nos nas um uma uns umas
para por com sem que qual quais como onde quando the of and in on for to is are
what how hoje sobre ser foi""".split())

_cache: dict[str, tuple[float, str]] = {}
_lock = threading.Lock()
_relogio = time.monotonic


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower())
                   if unicodedata.category(c) != "Mn")


def termos(consulta: str) -> list[str]:
    return [p for p in re.findall(r"\w+", _sem_acento(consulta))
            if len(p) >= 2 and p not in _PARADAS]


def trechos(texto: str, consulta: str, limite: int = TRECHO_POR_PAGINA) -> str:
    """As frases que mais citam os termos da pergunta, na ordem da página."""
    if len(texto) <= limite:
        return texto
    frases = re.split(r"(?<=[.!?…])\s+", texto)
    chave = termos(consulta)
    notas = []
    for i, f in enumerate(frases):
        f_norm = _sem_acento(f)
        notas.append((sum(f_norm.count(t) for t in chave), i))
    escolhidas, total = set(), 0
    for nota, i in sorted(notas, key=lambda n: (-n[0], n[1])):
        if nota == 0 and escolhidas:
            break
        # a frase seguinte costuma completar a ideia
        for j in (i, i + 1):
            if j < len(frases) and j not in escolhidas and total + len(frases[j]) <= limite:
                escolhidas.add(j)
                total += len(frases[j]) + 1
        if total >= limite * 0.9:
            break
    return " ".join(frases[j] for j in sorted(escolhidas)) or texto[:limite]


def _buscar(consulta: str) -> tuple[str, list[dict], str]:
    chave = config.tavily_api_key()
    if chave:
        try:
            resposta, itens = fontes.tavily(consulta, chave)
            if itens:
                return resposta, itens, "tavily"
        except Exception as e:
            print(f"[Pesquisa] Tavily falhou ({e}) — usando DuckDuckGo")
    return "", fontes.ddg(consulta), "ddg"


def _formatar(consulta: str, resposta: str, itens: list[dict]) -> str:
    linhas = [f"Search results for: {consulta}"]
    if resposta:
        linhas.append(f"Quick answer: {resposta}")
    linhas.append("")
    for n, i in enumerate(itens, 1):
        linhas.append(f"{n}. {i.get('title') or i.get('url')}")
        if i.get("url"):
            linhas.append(f"   Source: {i['url']}")
        corpo = i.get("trecho") or i.get("snippet")
        if corpo:
            linhas.append(f"   {corpo}")
        linhas.append("")
    texto = "\n".join(linhas).strip()
    return texto if len(texto) <= TOTAL else texto[:TOTAL].rsplit(" ", 1)[0] + "…"


def pesquisar(consulta: str) -> str:
    """Resultado em texto para o modelo. Levanta só se a busca não trouxe nada."""
    consulta = (consulta or "").strip()
    chave_cache = _sem_acento(consulta)
    agora = _relogio()
    with _lock:
        guardado = _cache.get(chave_cache)
        if guardado and agora - guardado[0] < CACHE_SEG:
            print("[Pesquisa] da memória (mesma pergunta há pouco)")
            return guardado[1]

    inicio = _relogio()
    resposta, itens, origem = _buscar(consulta)
    if not itens:
        raise RuntimeError(f"no results for: {consulta}")

    # Lê em paralelo as melhores páginas que vieram sem texto.
    para_ler = [i for i in itens if not i.get("texto") and fontes.pode_ler(i.get("url", ""))][:PAGINAS]
    if para_ler:
        restante = max(1.0, PRAZO - (_relogio() - inicio))
        pool = ThreadPoolExecutor(max_workers=len(para_ler))
        tarefas = {pool.submit(fontes.ler, i["url"]): i for i in para_ler}
        feitas, _ = wait(tarefas, timeout=restante)
        pool.shutdown(wait=False, cancel_futures=True)
        for t in feitas:
            try:
                tarefas[t]["texto"] = t.result() or ""
            except Exception:
                pass

    lidas = 0
    for i in itens:
        if i.get("texto"):
            i["trecho"] = trechos(i["texto"], consulta)
            lidas += 1

    # Páginas lidas primeiro: são as que têm o conteúdo de verdade.
    itens.sort(key=lambda i: 0 if i.get("trecho") else 1)
    texto = _formatar(consulta, resposta, itens)
    print(f"[Pesquisa] {origem}: {len(itens)} resultados, {lidas} páginas lidas, "
          f"{_relogio() - inicio:.1f}s")
    with _lock:
        _cache[chave_cache] = (_relogio(), texto)
    return texto
