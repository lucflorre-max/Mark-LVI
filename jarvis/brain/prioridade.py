"""
jarvis/brain/prioridade.py — motor de prioridade (M3 tarefa 1).

Combina quatro fatores, cada um de 0 a 1 (documento-mestre §5.2):

    prazo     quanto falta: atrasada = 1; hoje com hora perto = 0,95; …; sem prazo = 0,1
    impacto   a prioridade que o usuário deu: alta 1; média 0,6; baixa 0,25
    esforço   tarefa curta sobe um pouco, porque cabe em qualquer brecha
    contexto  combina com o que o usuário disse que está fazendo agora

Só calcula. Nada aqui grava, lembra horário de foco ou mede pausas (§5.2:
não rastrear foco, pausas nem interrupções).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from jarvis.tasks.repository import Tarefa

PESOS = {"prazo": 0.40, "impacto": 0.35, "esforco": 0.15, "contexto": 0.10}
IMPACTO = {"alta": 1.0, "media": 0.6, "baixa": 0.25}
IMPACTO_SEM = 0.6          # sem prioridade dita conta como média
DURACAO_PADRAO = 30        # minutos, quando a tarefa não tem duração
_NOME_PRIO = {"alta": "alta", "media": "média", "baixa": "baixa"}


@dataclass(frozen=True)
class Pontuacao:
    tarefa: Tarefa
    total: float
    prazo: float
    impacto: float
    esforco: float
    contexto: float
    atrasada: bool
    motivo: str


def duracao(t: Tarefa) -> int:
    return t.duracao_min or DURACAO_PADRAO


def momento_do_prazo(t: Tarefa) -> datetime | date | None:
    if not t.prazo:
        return None
    return datetime.fromisoformat(t.prazo) if len(t.prazo) > 10 else date.fromisoformat(t.prazo)


def atrasada(t: Tarefa, agora: datetime) -> bool:
    quando = momento_do_prazo(t)
    if quando is None or t.status != "aberta":
        return False
    if isinstance(quando, datetime):
        return quando < agora
    return quando < agora.date()


def dias_de_atraso(t: Tarefa, agora: datetime) -> int:
    """0 para quem não está atrasada ou venceu hoje."""
    quando = momento_do_prazo(t)
    if quando is None or not atrasada(t, agora):
        return 0
    dia = quando.date() if isinstance(quando, datetime) else quando
    return max(0, (agora.date() - dia).days)


def fator_prazo(t: Tarefa, agora: datetime) -> float:
    quando = momento_do_prazo(t)
    if quando is None:
        return 0.1
    if atrasada(t, agora):
        return 1.0
    dia = quando.date() if isinstance(quando, datetime) else quando
    dias = (dia - agora.date()).days
    if dias == 0:
        if isinstance(quando, datetime):
            return 0.95 if (quando - agora).total_seconds() <= 2 * 3600 else 0.85
        return 0.8
    if dias == 1:
        return 0.6
    if dias <= 3:
        return 0.45
    if dias <= 7:
        return 0.3
    return 0.15


def fator_impacto(t: Tarefa) -> float:
    return IMPACTO.get(t.prioridade, IMPACTO_SEM)


def fator_esforco(t: Tarefa) -> float:
    d = duracao(t)
    for limite, fator in ((15, 1.0), (30, 0.85), (60, 0.65), (120, 0.45)):
        if d <= limite:
            return fator
    return 0.25


def _palavras(texto: str | None) -> set[str]:
    return {p for p in (texto or "").lower().replace(",", " ").split() if p}


def fator_contexto(t: Tarefa, contexto: str | None, projeto: str | None) -> float:
    """Neutro (0,5) sem contexto dito. Com contexto: 1 se o projeto ou a
    descrição da tarefa tiver a palavra; 0,2 se a tarefa é de outro projeto."""
    alvo = _palavras(contexto)
    if not alvo:
        return 0.5
    if alvo & (_palavras(projeto) | _palavras(t.descricao) | _palavras(t.titulo)):
        return 1.0
    return 0.2 if projeto else 0.5


def _motivo(t: Tarefa, agora: datetime, p: dict[str, float], atr: bool) -> str:
    partes = []
    if atr:
        dias = dias_de_atraso(t, agora)
        partes.append("atrasada" + (f" há {dias} dia{'s' if dias > 1 else ''}" if dias else ""))
    elif p["prazo"] >= 0.8:
        quando = momento_do_prazo(t)
        partes.append(f"prazo hoje às {quando:%H:%M}" if isinstance(quando, datetime) else "prazo hoje")
    elif p["prazo"] >= 0.6:
        partes.append("prazo amanhã")
    if t.prioridade:
        partes.append(f"prioridade {_NOME_PRIO[t.prioridade]}")
    if p["esforco"] >= 0.85:
        partes.append(f"rápida ({duracao(t)} min)")
    if p["contexto"] == 1.0:
        partes.append("combina com o momento")
    return ", ".join(partes) or "sem urgência"


def pontuar(t: Tarefa, agora: datetime, contexto: str | None = None,
            projeto: str | None = None) -> Pontuacao:
    fatores = {
        "prazo": fator_prazo(t, agora),
        "impacto": fator_impacto(t),
        "esforco": fator_esforco(t),
        "contexto": fator_contexto(t, contexto, projeto),
    }
    total = round(sum(PESOS[k] * v for k, v in fatores.items()), 4)
    atr = atrasada(t, agora)
    return Pontuacao(t, total, fatores["prazo"], fatores["impacto"], fatores["esforco"],
                     fatores["contexto"], atr, _motivo(t, agora, fatores, atr))


def ordenar(tarefas: list[Tarefa], agora: datetime, contexto: str | None = None,
            projetos: dict[int, str] | None = None) -> list[Pontuacao]:
    """Da mais para a menos prioritária. Empate: prazo mais cedo, depois a mais antiga."""
    projetos = projetos or {}
    pts = [pontuar(t, agora, contexto, projetos.get(t.projeto_id))
           for t in tarefas if t.status == "aberta"]
    return sorted(pts, key=lambda p: (-p.total, p.tarefa.prazo or "9999", p.tarefa.id))
