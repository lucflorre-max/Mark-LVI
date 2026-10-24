"""
jarvis/brain/plano.py — encaixa as tarefas do dia no tempo livre (M3).

Base da linha do tempo, da sobrecarga e do replanejamento. Só calcula: nada
aqui grava nem mexe na agenda.

    1. Tempo livre = de agora até FIM_DO_DIA, menos os compromissos com hora.
    2. Tarefa com hora marcada hoje (ainda não passada) fica fixa na hora dela.
    3. As outras entram em ordem de prioridade no primeiro espaço onde cabem:
       primeiro as obrigatórias (prazo até hoje), depois as opcionais (sem
       prazo ou com prazo mais à frente).
    4. O que não coube fica em `sem_espaco`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from jarvis.brain import prioridade as pr
from jarvis.brain.prioridade import Pontuacao
from jarvis.calendar.agenda import FIM_DO_EXPEDIENTE, Evento

FIM_DO_DIA = FIM_DO_EXPEDIENTE      # 21h, o mesmo limite das sugestões da M2


@dataclass(frozen=True)
class Bloco:
    ini: datetime
    fim: datetime
    pont: Pontuacao | None = None    # tarefa
    evento: Evento | None = None     # compromisso da agenda
    fixa: bool = False               # hora marcada (tarefa) ou compromisso

    @property
    def titulo(self) -> str:
        return self.pont.tarefa.titulo if self.pont else self.evento.titulo

    @property
    def minutos(self) -> int:
        return int((self.fim - self.ini).total_seconds() // 60)


@dataclass
class Plano:
    agora: datetime
    limite: datetime
    blocos: list[Bloco] = field(default_factory=list)          # em ordem de horário
    sem_espaco: list[Pontuacao] = field(default_factory=list)  # em ordem de prioridade
    capacidade_min: int = 0      # livre antes de encaixar as tarefas
    livre_min: int = 0           # livre depois

    @property
    def tarefas(self) -> list[Bloco]:
        return [b for b in self.blocos if b.pont]

    def bloco_de(self, tarefa_id: int) -> Bloco | None:
        return next((b for b in self.tarefas if b.pont.tarefa.id == tarefa_id), None)


def obrigatoria(p: Pontuacao, agora: datetime) -> bool:
    """Prazo até hoje (atrasada inclusive)."""
    quando = pr.momento_do_prazo(p.tarefa)
    if quando is None:
        return False
    dia = quando.date() if isinstance(quando, datetime) else quando
    return dia <= agora.date()


def hora_fixa(p: Pontuacao, agora: datetime) -> datetime | None:
    """A hora marcada, se for hoje e ainda não tiver passado."""
    quando = pr.momento_do_prazo(p.tarefa)
    if isinstance(quando, datetime) and quando.date() == agora.date() and quando >= agora:
        return quando
    return None


def _livres(ocupado: list[tuple[datetime, datetime]], ini: datetime,
            fim: datetime) -> list[tuple[datetime, datetime]]:
    livres, cursor = [], ini
    for a, b in sorted(ocupado):
        if b <= cursor:
            continue
        if a > cursor:
            livres.append((cursor, min(a, fim)))
        cursor = max(cursor, b)
        if cursor >= fim:
            break
    if cursor < fim:
        livres.append((cursor, fim))
    return [(a, b) for a, b in livres if b > a]


def _minutos(intervalos) -> int:
    return int(sum((b - a).total_seconds() for a, b in intervalos) // 60)


def montar(pontuadas: list[Pontuacao], eventos: list[Evento], agora: datetime,
           limite: datetime | None = None,
           duracoes: dict[int, int] | None = None,
           ocupar: list[tuple[datetime, datetime]] | None = None) -> Plano:
    """`duracoes` troca a duração de uma tarefa (id → minutos), para simular
    um estouro sem alterar nada. `ocupar` reserva intervalos extras."""
    agora = agora.replace(second=0, microsecond=0)
    limite = limite or datetime.combine(agora.date(), FIM_DO_DIA, tzinfo=agora.tzinfo)
    duracoes = duracoes or {}
    plano = Plano(agora=agora, limite=limite)

    compromissos = [e for e in eventos if not e.dia_inteiro and e.inicio and e.fim
                    and e.fim > agora and e.inicio < limite]
    ocupado = [(max(e.inicio, agora), min(e.fim, limite)) for e in compromissos]
    ocupado += list(ocupar or [])
    plano.capacidade_min = _minutos(_livres(ocupado, agora, limite))
    blocos = [Bloco(e.inicio, e.fim, evento=e, fixa=True) for e in compromissos]

    def dur(p: Pontuacao) -> timedelta:
        return timedelta(minutes=duracoes.get(p.tarefa.id, pr.duracao(p.tarefa)))

    flexiveis = []
    for p in pontuadas:
        hora = hora_fixa(p, agora)
        if hora is not None and hora < limite:
            blocos.append(Bloco(hora, hora + dur(p), pont=p, fixa=True))
            ocupado.append((hora, hora + dur(p)))
        else:
            flexiveis.append(p)
    flexiveis.sort(key=lambda p: not obrigatoria(p, agora))   # estável: mantém a prioridade

    livres = _livres(ocupado, agora, limite)
    for p in flexiveis:
        d = dur(p)
        for i, (a, b) in enumerate(livres):
            if b - a >= d:
                blocos.append(Bloco(a, a + d, pont=p))
                livres[i] = (a + d, b)
                break
        else:
            plano.sem_espaco.append(p)
    plano.blocos = sorted(blocos, key=lambda b: (b.ini, b.fim))
    plano.livre_min = _minutos(livres)
    return plano
