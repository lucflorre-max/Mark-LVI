"""
jarvis/memory/perfil.py — como o usuário se comunica (base da Meta 5).

Duas coisas, ambas só com aprovação do usuário (CLAUDE.md: preferência
permanente só depois de um "sim"):

    vocabulário — nomes, lugares e termos dele. Entram nas dicas do
                  reconhecimento de voz (jarvis/config.transcricao_entrada).
    expressões  — jeitos de falar e o que querem dizer ("vamos para outra" =
                  mudar de assunto). Entram num bloco do prompt de cada sessão.

As sugestões saem de uma análise LOCAL das transcrições em data/conversas/
(sem modelo, sem cota). O aprovado fica em data/perfil.json, fora do Git.
"""

from __future__ import annotations

import json
import re
import threading
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

from jarvis import config

ARQUIVO = config.DATA_DIR / "perfil.json"
CONVERSAS = config.DATA_DIR / "conversas"
TIPOS = ("vocabulario", "expressao")

_lock = threading.Lock()

# Palavras comuns demais para serem "vocabulário dele" ou formarem sozinhas
# uma expressão.
_COMUNS = set("""
a ao aos as à às com como da das de do dos e é ela ele em então essa esse
esta este eu isso isto já la lá mais mas me meu minha muito na nas não no nos
o os ou para pela pelo por pra que quê se sem ser seu sua só também te tem
tu um uma uns você vocês vou vai tá ta né aí ai ah eh hum bem bom sim ok
jarvis jervis hey
""".split())
_RE_FALA = re.compile(r"\*\*Você:\*\*\s*(.+)$")
_RE_PALAVRA = re.compile(r"[A-Za-zÀ-ÿ]+(?:-[A-Za-zÀ-ÿ]+)?")


def _hoje() -> str:
    return datetime.now(config.fuso()).date().isoformat()


def _chave(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


# ── Arquivo ─────────────────────────────────────────────────────────────────

def _vazio() -> dict:
    return {"versao": 1, "vocabulario": [], "expressoes": [], "rejeitados": []}


def carregar(arquivo: Path | None = None) -> dict:
    arquivo = arquivo or ARQUIVO
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        base = _vazio()
        base.update({k: dados.get(k, v) for k, v in base.items()})
        return base
    except FileNotFoundError:
        return _vazio()
    except Exception as e:
        print(f"[Perfil] arquivo ilegível, usando perfil vazio: {e}")
        return _vazio()


def salvar(dados: dict, arquivo: Path | None = None) -> None:
    arquivo = arquivo or ARQUIVO
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    tmp = arquivo.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(arquivo)


# ── Análise das transcrições ────────────────────────────────────────────────

def falas_do_usuario(pasta: Path | None = None) -> list[str]:
    pasta = pasta or CONVERSAS
    falas = []
    for arq in sorted(pasta.glob("*.md")) if pasta.exists() else []:
        for linha in arq.read_text(encoding="utf-8").splitlines():
            m = _RE_FALA.search(linha)
            if m:
                falas.append(m.group(1).strip())
    return falas


def _ja_conhecido(dados: dict) -> set[str]:
    conhecidos = {_chave(v) for v in config.VOCABULARIO}
    conhecidos |= {_chave(i["texto"]) for i in dados["vocabulario"]}
    conhecidos |= {_chave(i["texto"]) for i in dados["expressoes"]}
    conhecidos |= {_chave(t) for t in dados["rejeitados"]}
    return conhecidos


def sugerir(limite: int = 6, pasta: Path | None = None,
            arquivo: Path | None = None) -> dict:
    """{"vocabulario": [(texto, vezes)], "expressoes": [(texto, vezes)]}."""
    falas = falas_do_usuario(pasta)
    conhecidos = _ja_conhecido(carregar(arquivo))

    # Vocabulário: nomes próprios (maiúscula fora do início da frase) e siglas.
    nomes: Counter[str] = Counter()
    for fala in falas:
        for frase in re.split(r"[.!?]\s+", fala):
            palavras = _RE_PALAVRA.findall(frase)
            for i, p in enumerate(palavras):
                sigla = p.isupper() and 2 <= len(p) <= 5
                nome = i > 0 and p[0].isupper() and len(p) >= 3
                if (sigla or nome) and _chave(p) not in _COMUNS:
                    nomes[p] += 1
    vocab = [(p, n) for p, n in nomes.most_common()
             if (n >= 2 or p.isupper()) and _chave(p) not in conhecidos]

    # Expressões: sequências de 2 a 4 palavras repetidas em falas diferentes.
    ngramas: Counter[str] = Counter()
    formas: dict[str, Counter[str]] = {}       # chave sem acento -> como foi dito
    for fala in falas:
        originais = [p.lower() for p in _RE_PALAVRA.findall(fala)]
        palavras = [_chave(p) for p in originais]
        vistos = set()
        for n in (2, 3, 4):
            for i in range(len(palavras) - n + 1):
                g = palavras[i:i + n]
                if all(w in _COMUNS or len(w) < 3 for w in g):
                    continue
                chave = " ".join(g)
                vistos.add(chave)
                formas.setdefault(chave, Counter())[" ".join(originais[i:i + n])] += 1
        ngramas.update(vistos)
    candidatas = {g: n for g, n in ngramas.items() if n >= 2 and g not in conhecidos}
    # Tira as que estão dentro de uma maior com a mesma frequência.
    expr = [(formas[g].most_common(1)[0][0], n) for g, n in candidatas.items()
            if not any(g != h and f" {g} " in f" {h} " and candidatas[h] == n
                       for h in candidatas)]
    expr.sort(key=lambda x: (-x[1], -len(x[0].split())))

    return {"vocabulario": vocab[:limite], "expressoes": expr[:limite]}


# ── Aprovar, esquecer, rejeitar ─────────────────────────────────────────────

def lembrar(tipo: str, texto: str, significado: str = "",
            arquivo: Path | None = None) -> str:
    texto = (texto or "").strip()
    if tipo not in TIPOS or not texto:
        return "Diga o tipo (vocabulario ou expressao) e o texto."
    if tipo == "expressao" and not (significado or "").strip():
        return ("Falta o que a expressão quer dizer. Pergunte ao usuário em "
                "uma frase.")
    with _lock:
        dados = carregar(arquivo)
        lista = dados["vocabulario" if tipo == "vocabulario" else "expressoes"]
        lista[:] = [i for i in lista if _chave(i["texto"]) != _chave(texto)]
        item = {"texto": texto, "aprovado_em": _hoje()}
        if tipo == "expressao":
            item["significado"] = significado.strip()
        lista.append(item)
        dados["rejeitados"] = [t for t in dados["rejeitados"] if _chave(t) != _chave(texto)]
        salvar(dados, arquivo)
    return f"Lembrado: {texto}."


def esquecer(texto: str, arquivo: Path | None = None) -> dict | None:
    """Remove do perfil. Devolve o item removido (com o tipo), ou None."""
    with _lock:
        dados = carregar(arquivo)
        for chave, tipo in (("vocabulario", "vocabulario"), ("expressoes", "expressao")):
            for item in dados[chave]:
                if _chave(item["texto"]) == _chave(texto):
                    dados[chave].remove(item)
                    salvar(dados, arquivo)
                    return {**item, "tipo": tipo}
    return None


def rejeitar(texto: str, arquivo: Path | None = None) -> str:
    """Não sugerir mais."""
    with _lock:
        dados = carregar(arquivo)
        if _chave(texto) not in {_chave(t) for t in dados["rejeitados"]}:
            dados["rejeitados"].append(texto.strip())
            salvar(dados, arquivo)
    return f"Não vou mais sugerir: {texto}."


# ── Uso pelo resto do JARVIS ────────────────────────────────────────────────

def vocabulario_aprovado(arquivo: Path | None = None) -> list[str]:
    return [i["texto"] for i in carregar(arquivo)["vocabulario"]]


def bloco_prompt(arquivo: Path | None = None) -> str:
    """Bloco para o início da sessão. '' quando não há nada aprovado ou o
    arquivo está estragado: isto roda na conexão e nunca pode derrubá-la."""
    try:
        dados = carregar(arquivo)
        linhas = [f'- "{i["texto"]}": {i.get("significado", "")}'
                  for i in dados["expressoes"]]
        if dados["vocabulario"]:
            linhas.append("- Names and terms the user uses: "
                          + ", ".join(i["texto"] for i in dados["vocabulario"]))
    except Exception as e:
        print(f"[Perfil] bloco ignorado: {e}")
        return ""
    if not linhas:
        return ""
    return ("[HOW THE USER COMMUNICATES]\n"
            "Learned with the user's approval. Use it to understand short or "
            "ambiguous requests; do not imitate it and do not mention it "
            "unless asked.\n" + "\n".join(linhas) + "\n")
