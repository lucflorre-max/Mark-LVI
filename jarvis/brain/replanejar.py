"""
jarvis/brain/replanejar.py — tarefa que estourou o tempo (M3 tarefa 4).

Documento-mestre §5.2: quando uma tarefa estourar, avisar o impacto no resto
do dia e sugerir o que mover, encurtar ou adiar — sem alterar sozinho. Quando
começou e não terminou, perguntar quanto falta e estimar o restante.

O Jarvis não mede nada (§5.2: não rastrear foco, pausas nem interrupções):
quanto falta é o usuário quem diz. Sem resposta ("não sei"), a estimativa é
metade da duração prevista, em múltiplos de 15 minutos.

Impacto = diferença entre o resto do dia sem o tempo extra e com ele:
    conflitos   compromissos e tarefas de hora marcada que batem com o extra
    perdidas    tarefas que cabiam hoje e deixam de caber
    empurradas  tarefas que continuam hoje, mas começam mais tarde
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from jarvis.brain import plano as pl
from jarvis.brain import prioridade as pr
from jarvis.brain import sobrecarga as sc
from jarvis.brain.plano import Bloco, Plano
from jarvis.brain.prioridade import Pontuacao
from jarvis.calendar import agenda
from jarvis.calendar.agenda import Evento
from jarvis.tasks.repository import Tarefa

MOVER, ENCURTAR, ADIAR = "mover", "encurtar", "adiar"
PASSO = 15
MINIMO_RESTANTE = 15      # encurtar nunca deixa uma tarefa com menos que isto


def estimar_restante(t: Tarefa) -> int:
    """'Não sei quanto falta': metade da duração prevista, em passos de 15."""
    metade = pr.duracao(t) / 2
    return max(PASSO, int(-(-metade // PASSO)) * PASSO)


@dataclass(frozen=True)
class Sugestao:
    tipo: str               # mover | encurtar | adiar
    titulo: str
    detalhe: str


@dataclass
class Replano:
    tarefa: Tarefa
    restante_min: int
    fim_previsto: datetime
    estimado: bool
    conflitos: list[Bloco] = field(default_factory=list)
    perdidas: list[Pontuacao] = field(default_factory=list)
    empurradas: list[tuple[str, datetime, datetime]] = field(default_factory=list)
    sugestoes: list[Sugestao] = field(default_factory=list)
    depois: Plano | None = None

    @property
    def sem_impacto(self) -> bool:
        return not (self.conflitos or self.perdidas or self.empurradas)


def _como_eventos(blocos: list[Bloco], fora: int | None = None) -> list[Evento]:
    """Blocos do plano como compromissos, para procurar horário livre."""
    return [b.evento or Evento(b.titulo, b.ini, b.fim, False, id=f"t{b.pont.tarefa.id}")
            for b in blocos if not (b.pont and b.pont.tarefa.id == fora)]


def _h(dt: datetime) -> str:
    return agenda._hora_fala(dt)


def analisar(atual: Tarefa, restante_min: int | None, pontuadas: list[Pontuacao],
             eventos: list[Evento], agora: datetime) -> Replano:
    agora = agora.replace(second=0, microsecond=0)
    estimado = restante_min is None
    restante = estimar_restante(atual) if estimado else max(1, int(restante_min))
    fim = agora + timedelta(minutes=restante)
    outras = [p for p in pontuadas if p.tarefa.id != atual.id]

    antes = pl.montar(outras, eventos, agora)
    depois = pl.montar(outras, eventos, agora, ocupar=[(agora, fim)])
    rp = Replano(atual, restante, fim, estimado, depois=depois)

    rp.conflitos = [b for b in depois.blocos if b.fixa and b.ini < fim and b.fim > agora]
    ids_depois = {b.pont.tarefa.id for b in depois.tarefas}
    rp.perdidas = [b.pont for b in antes.tarefas if b.pont.tarefa.id not in ids_depois]
    for b in antes.tarefas:
        novo = depois.bloco_de(b.pont.tarefa.id)
        if novo and novo.ini > b.ini and not b.fixa:
            rp.empurradas.append((b.titulo, b.ini, novo.ini))

    rp.sugestoes = _sugerir(rp, depois, agora, outras, eventos)
    return rp


def _cabe(alvo: Pontuacao, outras: list[Pontuacao], eventos: list[Evento],
          agora: datetime, fim_atual: datetime, duracoes: dict[int, int] | None = None,
          sem: int | None = None) -> bool:
    """Simula o dia (nada é gravado): `alvo` cabe se `duracoes` mudar ou `sem` sair?"""
    lista = [p for p in outras if p.tarefa.id != sem]
    plano = pl.montar(lista, eventos, agora, duracoes=duracoes, ocupar=[(agora, fim_atual)])
    return plano.bloco_de(alvo.tarefa.id) is not None


def _abrir_espaco(perdida: Pontuacao, rp: Replano, depois: Plano, agora: datetime,
                  outras: list[Pontuacao], eventos: list[Evento]) -> Sugestao:
    """Encurtar ou adiar algo de classe abaixo, ou encurtar a tarefa atual,
    o que for o primeiro a fazer `perdida` caber. Senão, adiar a perdida."""
    def ordem(p):
        return sc.CLASSES.index(sc.classificar(p, agora))
    abaixo = sorted((b for b in depois.tarefas if not b.fixa and ordem(b.pont) > ordem(perdida)),
                    key=lambda b: (-ordem(b.pont), b.pont.total))  # mais baixa primeiro
    for b in abaixo:
        for novo in range(b.minutos - PASSO, MINIMO_RESTANTE - 1, -PASSO):
            if _cabe(perdida, outras, eventos, agora, rp.fim_previsto,
                     duracoes={b.pont.tarefa.id: novo}):
                return Sugestao(ENCURTAR, b.titulo,
                                f"em {b.minutos - novo} min para caber “{perdida.tarefa.titulo}”")
        if _cabe(perdida, outras, eventos, agora, rp.fim_previsto, sem=b.pont.tarefa.id):
            return Sugestao(ADIAR, b.titulo,
                            f"para amanhã, abrindo espaço para “{perdida.tarefa.titulo}”")
    for novo in range(rp.restante_min - PASSO, MINIMO_RESTANTE - 1, -PASSO):
        if _cabe(perdida, outras, eventos, agora, agora + timedelta(minutes=novo)):
            return Sugestao(ENCURTAR, rp.tarefa.titulo,
                            f"parar às {_h(agora + timedelta(minutes=novo))} para caber "
                            f"“{perdida.tarefa.titulo}”")
    return Sugestao(ADIAR, perdida.tarefa.titulo, "para amanhã")


def _sugerir(rp: Replano, depois: Plano, agora: datetime,
             outras: list[Pontuacao], eventos: list[Evento]) -> list[Sugestao]:
    sug: list[Sugestao] = []
    ocupados = _como_eventos(depois.blocos) + [
        Evento(rp.tarefa.titulo, agora, rp.fim_previsto, False, id="atual")]

    for b in rp.conflitos:
        folga = int((b.ini - agora).total_seconds() // 60)
        if folga >= MINIMO_RESTANTE:
            sug.append(Sugestao(ENCURTAR, rp.tarefa.titulo,
                                f"parar às {_h(b.ini)} para não bater com “{b.titulo}”"))
        livre = agenda.proximo_livre([e for e in ocupados if e.id != (b.evento.id if b.evento
                                      else f"t{b.pont.tarefa.id}")],
                                     rp.fim_previsto, b.fim - b.ini)
        onde = f"para {_h(livre)}" if livre else "para amanhã"
        nota = " (mudança de agenda: pede confirmação)" if b.evento else ""
        sug.append(Sugestao(MOVER, b.titulo, f"{onde}{nota}"))

    for p in sorted(rp.perdidas, key=lambda p: sc.CLASSES.index(sc.classificar(p, agora))):
        if sc.classificar(p, agora) == sc.PODE_ESPERAR:
            sug.append(Sugestao(ADIAR, p.tarefa.titulo, "para amanhã"))
        else:
            sug.append(_abrir_espaco(p, rp, depois, agora, outras, eventos))
    return sug


def card(rp: Replano) -> tuple[str, str]:
    est = " (estimativa)" if rp.estimado else ""
    partes = [f"“{rp.tarefa.titulo}” vai até {rp.fim_previsto:%H:%M}{est}."]
    if rp.sem_impacto:
        partes.append("O resto do dia não muda.")
        return "DIA — tarefa estourou", "\n".join(partes)
    partes.append("IMPACTO")
    partes += [f"  ⚠ bate com {b.titulo} ({b.ini:%H:%M}–{b.fim:%H:%M})" for b in rp.conflitos]
    partes += [f"  ✗ {p.tarefa.titulo} não cabe mais hoje" for p in rp.perdidas]
    partes += [f"  → {t} passa de {a:%H:%M} para {d:%H:%M}" for t, a, d in rp.empurradas]
    if rp.sugestoes:
        partes.append("SUGESTÕES")
        partes += [f"  {s.tipo.capitalize()} {s.titulo}: {s.detalhe}" for s in rp.sugestoes]
    partes.append("Nada foi alterado.")
    return "DIA — tarefa estourou", "\n".join(partes)


def para_fala(rp: Replano) -> str:
    est = ", pela estimativa" if rp.estimado else ""
    texto = f"{rp.tarefa.titulo} vai até {_h(rp.fim_previsto)}{est}."
    if rp.sem_impacto:
        return texto + " O resto do dia não muda."
    if rp.conflitos:
        texto += " Bate com " + ", ".join(b.titulo for b in rp.conflitos) + "."
    if rp.perdidas:
        texto += " Deixa de caber hoje: " + ", ".join(p.tarefa.titulo for p in rp.perdidas) + "."
    if rp.empurradas:
        texto += f" {len(rp.empurradas)} tarefa(s) começam mais tarde."
    if rp.sugestoes:
        texto += " Sugestões: " + "; ".join(f"{s.tipo} {s.titulo} {s.detalhe}"
                                             for s in rp.sugestoes) + "."
    return texto
