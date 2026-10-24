"""Fábrica de tarefas e compromissos para os testes da Meta 3."""

from datetime import datetime, timedelta, timezone
from itertools import count

from jarvis.calendar.agenda import Evento
from jarvis.tasks.repository import Tarefa

BRT = timezone(timedelta(hours=-3), "BRT")
AGORA = datetime(2026, 10, 23, 9, 30, tzinfo=BRT)   # sexta, 9h30
_ids = count(1000)


def tarefa(titulo="x", prazo=None, prioridade=None, duracao_min=None,
           projeto_id=None, descricao=None, status="aberta", id=None):
    return Tarefa(id=id or next(_ids), titulo=titulo, descricao=descricao, prazo=prazo,
                  prioridade=prioridade, duracao_min=duracao_min, projeto_id=projeto_id,
                  status=status, origem="voz", criado_em="", atualizado_em="")


def hoje(hhmm: str) -> str:
    """'14:00' → prazo ISO de hoje às 14h."""
    return f"2026-10-23T{hhmm}:00-03:00"


def as_(hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return AGORA.replace(hour=h, minute=m)


def evento(titulo, ini: str, fim: str, local=""):
    return Evento(titulo, as_(ini), as_(fim), False, local, id=titulo)
