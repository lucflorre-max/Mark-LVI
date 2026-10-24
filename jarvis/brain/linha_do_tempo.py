"""
jarvis/brain/linha_do_tempo.py — Agora / Depois / Se der tempo (M3 tarefa 2).

Separa o plano do dia (jarvis/brain/plano.py) nas três faixas da
visualização preferida do usuário (documento-mestre §5.2):

    Agora         o que está acontecendo ou começa nos próximos 15 minutos
    Depois        o resto do dia: compromissos e tarefas com prazo até hoje
    Se der tempo  tarefas sem prazo para hoje e o que não coube no dia
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from jarvis.brain import plano as pl
from jarvis.brain import prioridade as pr
from jarvis.brain.plano import Bloco, Plano
from jarvis.brain.prioridade import Pontuacao
from jarvis.calendar import agenda

JANELA_AGORA = timedelta(minutes=15)
_NOME_PRIO = {"alta": "alta", "media": "média", "baixa": "baixa"}


@dataclass(frozen=True)
class Opcional:
    pont: Pontuacao
    bloco: Bloco | None      # None: não coube no dia
    nota: str                # "sem prazo", "prazo 30/10", "não cabe hoje"


@dataclass
class Linha:
    agora: list[Bloco] = field(default_factory=list)
    depois: list[Bloco] = field(default_factory=list)
    se_der_tempo: list[Opcional] = field(default_factory=list)
    plano: Plano | None = None


def _nota(p: Pontuacao, plano: Plano, coube: bool) -> str:
    if not coube and pl.obrigatoria(p, plano.agora):
        return "não cabe hoje"
    quando = pr.momento_do_prazo(p.tarefa)
    if quando is None:
        return "sem prazo"
    dia = quando.date() if isinstance(quando, datetime) else quando
    texto = f"prazo {dia:%d/%m}"
    return texto if coube else f"{texto}, não cabe hoje"


def separar(plano: Plano) -> Linha:
    linha = Linha(plano=plano)
    corte = plano.agora + JANELA_AGORA
    for b in plano.blocos:
        if b.pont and not pl.obrigatoria(b.pont, plano.agora) and not b.fixa:
            linha.se_der_tempo.append(Opcional(b.pont, b, _nota(b.pont, plano, True)))
        elif b.ini <= corte:
            linha.agora.append(b)
        else:
            linha.depois.append(b)
    for p in plano.sem_espaco:
        linha.se_der_tempo.append(Opcional(p, None, _nota(p, plano, False)))
    # Nada obrigatório agora: a primeira opcional que já cabe sobe para Agora.
    if not linha.agora and linha.se_der_tempo:
        primeira = linha.se_der_tempo[0]
        if primeira.bloco and primeira.bloco.ini <= corte:
            linha.agora.append(primeira.bloco)
            linha.se_der_tempo.pop(0)
    return linha


def _horas(minutos: int) -> str:
    h, m = divmod(max(0, minutos), 60)
    if not h:
        return f"{m} min"
    return f"{h}h{m:02d}" if m else f"{h}h"


def _rotulo(b: Bloco) -> str:
    if b.evento:
        local = f" · {b.evento.local}" if b.evento.local else ""
        return f"{b.titulo} · agenda{local}"
    t = b.pont.tarefa
    prio = f" · {_NOME_PRIO[t.prioridade]}" if t.prioridade else ""
    atraso = " (atrasada)" if b.pont.atrasada else ""
    return f"{t.titulo}{prio}{atraso}"


def _linha_bloco(b: Bloco) -> str:
    return f"  {b.ini:%H:%M}–{b.fim:%H:%M}  {_rotulo(b)}"


def card(linha: Linha) -> tuple[str, str]:
    """(título, texto) para o painel de conteúdo."""
    plano = linha.plano
    titulo = f"DIA — {agenda.nome_do_dia(plano.agora.date(), plano.agora.date())}"
    partes = ["AGORA"]
    partes += [_linha_bloco(b) for b in linha.agora] or ["  livre"]
    partes.append("DEPOIS")
    partes += [_linha_bloco(b) for b in linha.depois] or ["  nada marcado"]
    if linha.se_der_tempo:
        partes.append("SE DER TEMPO")
        for o in linha.se_der_tempo:
            hora = f"{o.bloco.ini:%H:%M}  " if o.bloco else ""
            partes.append(f"  {hora}{o.pont.tarefa.titulo} ({o.nota})")
    partes.append(f"\nLivre depois do plano: {_horas(plano.livre_min)} até {plano.limite:%H:%M}")
    return titulo, "\n".join(partes)


def para_fala(linha: Linha) -> str:
    """Resumo curto para o modelo: 'Agora: …. Depois: …. Se der tempo: ….'"""
    def blocos(bs):
        return "; ".join(f"{agenda._hora_fala(b.ini)} {b.titulo}" for b in bs)
    partes = [f"Agora: {blocos(linha.agora) or 'livre'}."]
    if linha.depois:
        partes.append(f"Depois: {blocos(linha.depois)}.")
    if linha.se_der_tempo:
        partes.append("Se der tempo: " + "; ".join(
            f"{o.pont.tarefa.titulo} ({o.nota})" for o in linha.se_der_tempo) + ".")
    return " ".join(partes)
