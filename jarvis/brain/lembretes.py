"""
jarvis/brain/lembretes.py — quando lembrar, conforme a prioridade (M3 tarefa 6).

Documento-mestre §5.3: lembretes antecipados, repetidos quando necessário e
adaptados à prioridade e ao contexto; tarefa importante ignorada: lembrar de
novo, perguntar se deve reagendar e sugerir novo horário. §2 e §12.3: sem
excesso de notificações; agrupadas e inteligentes.

    Prioridade  antes                na hora   se ignorado
    alta        60 e 15 min antes    sim       repete a cada 30 min, 2 vezes;
                                               depois pergunta se reagenda
    média       15 min antes         sim       repete 1 vez depois de 60 min
    baixa       —                    sim       não repete

    Sem hora    só a de prioridade alta, uma vez às 14h do dia do prazo.
    Hábito      um aviso por dia às 19h, juntando os hábitos que precisam de
                hoje para bater a meta (jarvis/brain/habitos.py).

Contexto:
    Silêncio 22h–7h: o lembrete vai para as 7h se a tarefa for depois disso;
    senão é antecipado para 21h45.
    Durante um compromisso: o aviso de antecedência vai para 5 min antes do
    compromisso começar (ou para o fim dele, se ainda der tempo). O "na hora"
    de prioridade alta não muda.

Sem excesso: avisos a menos de 10 min um do outro viram um só; no máximo 3
por hora e 12 por dia. Quando passa disso, saem primeiro os de prioridade
mais baixa; os de prioridade alta sempre ficam.

Só planeja. Quem mostra os avisos e conta quantas vezes um foi ignorado é a
camada de entrega (rotina diária, Meta 4); nada aqui é gravado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from jarvis.brain import prioridade as pr
from jarvis.calendar import agenda
from jarvis.calendar.agenda import Evento
from jarvis.tasks.repository import Tarefa


@dataclass(frozen=True)
class Regra:
    antes: tuple[int, ...]
    na_hora: bool
    repetir_cada: int
    repeticoes: int


REGRAS = {
    "alta": Regra(antes=(60, 15), na_hora=True, repetir_cada=30, repeticoes=2),
    "media": Regra(antes=(15,), na_hora=True, repetir_cada=60, repeticoes=1),
    "baixa": Regra(antes=(), na_hora=True, repetir_cada=0, repeticoes=0),
}
REGRA_SEM_PRIORIDADE = REGRAS["media"]
_PESO = {"alta": 0, "media": 1, "baixa": 2, "habito": 3}

SILENCIO_INI, SILENCIO_FIM = time(22, 0), time(7, 0)
ANTES_DO_SILENCIO = time(21, 45)
SEM_HORA_AS = time(14, 0)
HABITO_AS = time(19, 0)
AGRUPAR = timedelta(minutes=10)
MAX_POR_HORA, MAX_POR_DIA = 3, 12


def regra(t: Tarefa) -> Regra:
    return REGRAS.get(t.prioridade, REGRA_SEM_PRIORIDADE)


@dataclass
class Lembrete:
    quando: datetime
    itens: list[str]                    # títulos
    tipo: str                           # antes | na_hora | sem_hora | habito
    prioridade: str                     # alta | media | baixa | habito
    tarefa_ids: list[int] = field(default_factory=list)

    def texto(self) -> str:
        nomes = ", ".join(self.itens)
        if self.tipo == "habito":
            return f"Hábito de hoje: {nomes}"
        if self.tipo == "sem_hora":
            return f"Ainda para hoje: {nomes}"
        return nomes


# ── Contexto ────────────────────────────────────────────────────────────────

def em_silencio(dt: datetime) -> bool:
    return dt.time() >= SILENCIO_INI or dt.time() < SILENCIO_FIM


def _fora_do_silencio(quando: datetime, alvo: datetime) -> datetime | None:
    if not em_silencio(quando):
        return quando
    manha = datetime.combine(quando.date() if quando.time() < SILENCIO_FIM
                             else quando.date() + timedelta(days=1), SILENCIO_FIM,
                             tzinfo=quando.tzinfo)
    if manha <= alvo:
        return manha
    noite = datetime.combine(alvo.date() if alvo.time() >= SILENCIO_INI
                             else alvo.date() - timedelta(days=1), ANTES_DO_SILENCIO,
                             tzinfo=quando.tzinfo)
    return noite


def _fora_de_compromisso(quando: datetime, alvo: datetime, eventos: list[Evento],
                         agora: datetime) -> datetime | None:
    batem = agenda.conflitos(eventos, quando, quando + timedelta(minutes=1))
    if not batem:
        return quando
    e = batem[0]
    antes = e.inicio - timedelta(minutes=5)
    if antes >= agora:
        return antes
    return e.fim if e.fim <= alvo else None


# ── Plano do dia ────────────────────────────────────────────────────────────

def _brutos(tarefas: list[Tarefa], agora: datetime, eventos: list[Evento]) -> list[Lembrete]:
    saida = []
    for t in tarefas:
        if t.status != "aberta" or not t.prazo:
            continue
        prio = t.prioridade or "media"
        quando = pr.momento_do_prazo(t)
        if not isinstance(quando, datetime):
            if t.prioridade == "alta" and quando == agora.date():
                hora = datetime.combine(quando, SEM_HORA_AS, tzinfo=agora.tzinfo)
                if hora >= agora:
                    saida.append(Lembrete(hora, [t.titulo], "sem_hora", "alta", [t.id]))
            continue
        if quando.date() != agora.date() or quando < agora:
            continue
        r = regra(t)
        momentos = [(quando - timedelta(minutes=m), "antes") for m in r.antes]
        if r.na_hora:
            momentos.append((quando, "na_hora"))
        for m, tipo in momentos:
            m = _fora_do_silencio(m, quando)
            if m is not None and not (tipo == "na_hora" and prio == "alta"):
                m = _fora_de_compromisso(m, quando, eventos, agora)
            if m is None or m < agora or m > quando:
                continue
            saida.append(Lembrete(m, [t.titulo], tipo, prio, [t.id]))
    return saida


def _agrupar(lembretes: list[Lembrete]) -> list[Lembrete]:
    grupos: list[Lembrete] = []
    for lb in sorted(lembretes, key=lambda x: (x.quando, _PESO[x.prioridade])):
        ultimo = grupos[-1] if grupos else None
        if ultimo and lb.quando - ultimo.quando < AGRUPAR and lb.tipo != "habito" \
                and ultimo.tipo != "habito":
            for titulo in lb.itens:
                if titulo not in ultimo.itens:
                    ultimo.itens.append(titulo)
            ultimo.tarefa_ids += [i for i in lb.tarefa_ids if i not in ultimo.tarefa_ids]
            if _PESO[lb.prioridade] < _PESO[ultimo.prioridade]:
                ultimo.prioridade = lb.prioridade
            if lb.tipo == "na_hora":
                ultimo.tipo = "na_hora"
        else:
            grupos.append(Lembrete(lb.quando, list(lb.itens), lb.tipo, lb.prioridade,
                                   list(lb.tarefa_ids)))
    return grupos


def _limitar(lembretes: list[Lembrete]) -> list[Lembrete]:
    aceitos: list[Lembrete] = []
    for lb in sorted(lembretes, key=lambda x: (_PESO[x.prioridade], x.quando)):
        if lb.prioridade != "alta":
            na_hora = [a for a in aceitos if abs(a.quando - lb.quando) < timedelta(hours=1)]
            if len(na_hora) >= MAX_POR_HORA or len(aceitos) >= MAX_POR_DIA:
                continue
        aceitos.append(lb)
    return sorted(aceitos, key=lambda x: x.quando)


def planejar(tarefas: list[Tarefa], agora: datetime, eventos: list[Evento] | None = None,
             habitos_hoje: list[str] | None = None) -> list[Lembrete]:
    """Os avisos do resto de hoje, já agrupados e dentro do limite."""
    eventos = eventos or []
    brutos = _brutos(tarefas, agora, eventos)
    if habitos_hoje:
        hora = datetime.combine(agora.date(), HABITO_AS, tzinfo=agora.tzinfo)
        if hora >= agora:
            brutos.append(Lembrete(hora, list(habitos_hoje), "habito", "habito"))
    return _limitar(_agrupar(brutos))


# ── Ignorado ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Proximo:
    acao: str                          # repetir | perguntar_reagendar | parar
    quando: datetime | None = None     # repetir: a hora do próximo aviso
    sugestao: datetime | None = None   # perguntar_reagendar: novo horário livre (None = amanhã)


def depois_de_ignorado(t: Tarefa, vezes: int, ultimo: datetime, agora: datetime,
                       eventos: list[Evento] | None = None) -> Proximo:
    """`vezes`: quantos avisos já foram ignorados (quem conta é a entrega)."""
    r = regra(t)
    if vezes <= r.repeticoes and r.repetir_cada:
        quando = _fora_do_silencio(ultimo + timedelta(minutes=r.repetir_cada),
                                   datetime.max.replace(tzinfo=agora.tzinfo))
        return Proximo("repetir", quando)
    if t.prioridade == "alta":
        livre = agenda.proximo_livre(eventos or [], agenda._arredondar(agora),
                                     timedelta(minutes=pr.duracao(t)))
        return Proximo("perguntar_reagendar", sugestao=livre)
    return Proximo("parar")


def card(lembretes: list[Lembrete], hoje: date) -> tuple[str, str]:
    if not lembretes:
        return "LEMBRETES — hoje", "Nenhum aviso planejado para o resto do dia."
    linhas = [f"{lb.quando:%H:%M}  {lb.texto()}" for lb in lembretes]
    linhas.append(f"\n{len(lembretes)} aviso(s); no máximo {MAX_POR_HORA} por hora, "
                  "nada entre 22h e 7h.")
    return "LEMBRETES — hoje", "\n".join(linhas)
