"""
jarvis/memory/perfil_service.py — ferramenta jarvis_perfil.

    sugestoes  o que a análise das transcrições encontrou (nada é salvo)
    lembrar    salva vocabulário ou expressão — só com "sim" FALADO (portão VOZ)
    esquecer   remove do perfil (com desfazer)
    rejeitar   não sugerir mais
    listar     o que está aprovado
"""

from __future__ import annotations

from jarvis.brain import gate
from jarvis.memory import perfil

ACOES = ("sugestoes", "lembrar", "esquecer", "rejeitar", "listar")
_undo = None   # core.undo; trocável nos testes


def _pilha_undo():
    if _undo is not None:
        return _undo
    from core import undo  # noqa: PLC0415 — só existe dentro do Mark
    return undo


def _sugestoes(p: dict) -> str:
    s = perfil.sugerir()
    if not s["vocabulario"] and not s["expressoes"]:
        return ("Ainda não há nada novo nas conversas para sugerir. Diga isso "
                "em uma frase.")
    partes = []
    if s["vocabulario"]:
        partes.append("nomes/termos: " + ", ".join(f"{t} ({n}x)" for t, n in s["vocabulario"]))
    if s["expressoes"]:
        partes.append("expressões: " + ", ".join(f'"{t}" ({n}x)' for t, n in s["expressoes"]))
    return ("Sugestões tiradas das conversas (nada salvo): " + "; ".join(partes)
            + ". Apresente no máximo três ao usuário, as mais úteis. Para cada "
            "expressão, diga o que você acha que ela quer dizer e pergunte se "
            "pode lembrar. Só chame lembrar com o que ele aprovar.")


def _lembrar(p: dict) -> str:
    tipo = str(p.get("tipo") or "").strip().lower()
    out = perfil.lembrar(tipo, p.get("texto", ""), p.get("significado", ""))
    if out.startswith("Lembrado"):
        texto = str(p.get("texto")).strip()
        try:
            _pilha_undo().push_undo(f"lembrei: {texto}",
                                    lambda: f"Esquecido: {texto}." if perfil.esquecer(texto) else "")
        except Exception as e:
            print(f"[Perfil] desfazer não registrado: {e}")
        out += " Confirme ao usuário em poucas palavras."
    return out


def _esquecer(p: dict) -> str:
    item = perfil.esquecer(str(p.get("texto") or ""))
    if item is None:
        return "Isso não está no perfil. Diga ao usuário."
    try:
        _pilha_undo().push_undo(
            f"esqueci: {item['texto']}",
            lambda: perfil.lembrar(item["tipo"], item["texto"], item.get("significado", "")))
    except Exception as e:
        print(f"[Perfil] desfazer não registrado: {e}")
    return f"Esquecido: {item['texto']}. Confirme ao usuário em poucas palavras."


def _rejeitar(p: dict) -> str:
    texto = str(p.get("texto") or "").strip()
    return perfil.rejeitar(texto) if texto else "Diga o que não devo mais sugerir."


def _listar(p: dict) -> str:
    dados = perfil.carregar()
    if not dados["vocabulario"] and not dados["expressoes"]:
        return "O perfil ainda está vazio: nada foi aprovado."
    partes = []
    if dados["expressoes"]:
        partes.append("expressões: " + "; ".join(
            f'"{i["texto"]}" = {i["significado"]}' for i in dados["expressoes"]))
    if dados["vocabulario"]:
        partes.append("vocabulário: " + ", ".join(i["texto"] for i in dados["vocabulario"]))
    return "Perfil aprovado — " + " | ".join(partes) + ". Resuma para o usuário."


_HANDLERS = {"sugestoes": _sugestoes, "lembrar": _lembrar, "esquecer": _esquecer,
             "rejeitar": _rejeitar, "listar": _listar}


def handle(parameters: dict, player=None) -> str:
    try:
        p = dict(parameters or {})
        acao = str(p.get("acao") or "sugestoes").strip().lower()
        p["acao"] = acao
        if acao not in _HANDLERS:
            return f"Ação '{acao}' desconhecida. Use uma destas: {', '.join(ACOES)}."
        pendente = gate.guard("jarvis_perfil", p, lambda: _HANDLERS[acao](p))
        if pendente is not None:
            return pendente
        return _HANDLERS[acao](p)
    except Exception as e:
        return f"Falha na ferramenta de perfil: {e}. Nada foi alterado."
