"""
jarvis/tasks/cards.py — cards de tarefa para a tela (Meta 1B, cards contextuais).

Só formata: devolve (título, texto) para `player.show_content`, o painel de
conteúdo do Mark, até os cards próprios da M1B existirem. Aparecem quando o
assunto surge: rascunho e resumo antes do "sim", lista do dia e conclusão.
"""

from __future__ import annotations

from datetime import datetime

from jarvis.calendar import agenda
from jarvis.tasks.repository import Tarefa

_PRIORIDADE = {"alta": "alta", "media": "média", "baixa": "baixa"}


def _linha(rotulo: str, valor: str) -> str:
    return f"{rotulo:<11} {valor}"


def rascunho(titulo: str, campos: dict[str, str | None], destinos: list[str],
             faltas: list[str]) -> tuple[str, str]:
    """Antes do "sim". `campos`: rótulo → valor já formatado (None = falta)."""
    linhas = [f"“{titulo}”"]
    for rotulo, valor in campos.items():
        linhas.append(_linha(rotulo, valor if valor else "?"))
    if destinos and not faltas:
        linhas.append(_linha("Vai para", " · ".join(destinos)))
    if faltas:
        linhas.append(f"\nFalta: {', '.join(faltas)}.")
        return "TAREFA — rascunho", "\n".join(linhas)
    linhas.append('\nDiga "sim" para salvar.')
    return "TAREFA — confirmar?", "\n".join(linhas)


def lista_do_dia(tarefas: list[Tarefa], agora: datetime, inbox: int) -> tuple[str, str]:
    titulo = f"TAREFAS — {agenda.nome_do_dia(agora.date(), agora.date())}"
    linhas = []
    for t in tarefas:
        if t.prazo and len(t.prazo) > 10:
            quando = datetime.fromisoformat(t.prazo)
            hora = f"{quando:%H:%M}"
            atrasada = quando < agora
        else:
            hora, atrasada = "—", False
        prio = f" · {_PRIORIDADE[t.prioridade]}" if t.prioridade else ""
        marca = "⚠ " if atrasada else ""
        sufixo = "  (atrasada)" if atrasada else ""
        linhas.append(f"{marca}{hora:<6} {t.titulo}{prio}{sufixo}")
    if not linhas:
        linhas.append("Nenhuma tarefa com prazo para hoje.")
    if inbox:
        linhas.append(f"\n+ {inbox} na caixa de entrada, sem prazo")
    return titulo, "\n".join(linhas)


def concluida(t: Tarefa, extra: str = "") -> tuple[str, str]:
    return "TAREFA — concluída", f"✔ {t.titulo}" + (f"\n{extra.strip()}" if extra.strip() else "")
