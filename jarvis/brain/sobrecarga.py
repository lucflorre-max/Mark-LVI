"""
jarvis/brain/sobrecarga.py — dia cheio demais (M3 tarefa 3).

Documento-mestre §5.2: em sobrecarga, avisar, classificar em Essencial /
Importante / Pode esperar e propor uma linha do tempo mais realista.

    Sobrecarga    alguma tarefa com prazo até hoje não coube no tempo livre.
    Essencial     prazo até hoje e prioridade alta, ou hora marcada hoje
                  (que não seja de prioridade baixa).
    Pode esperar  prioridade baixa, ou prazo depois de hoje / sem prazo
                  (a não ser que seja alta).
    Importante    o resto.

A proposta encaixa na ordem das classes e sugere adiar para amanhã o que
sobrar. É só proposta: nada é gravado (mudança de prioridade e de agenda
exige aceite do usuário, §2 e §11).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from jarvis.brain import plano as pl
from jarvis.brain import prioridade as pr
from jarvis.brain.plano import Bloco, Plano
from jarvis.brain.prioridade import Pontuacao
from jarvis.calendar.agenda import Evento

ESSENCIAL, IMPORTANTE, PODE_ESPERAR = "essencial", "importante", "pode_esperar"
CLASSES = (ESSENCIAL, IMPORTANTE, PODE_ESPERAR)
NOMES = {ESSENCIAL: "Essencial", IMPORTANTE: "Importante", PODE_ESPERAR: "Pode esperar"}


def classificar(p: Pontuacao, agora: datetime) -> str:
    t = p.tarefa
    hoje = pl.obrigatoria(p, agora)
    if t.prioridade == "baixa":
        return PODE_ESPERAR
    if hoje and (t.prioridade == "alta" or pl.hora_fixa(p, agora) is not None):
        return ESSENCIAL
    if not hoje and t.prioridade != "alta":
        return PODE_ESPERAR
    return IMPORTANTE


def excesso_min(plano: Plano) -> int:
    """Minutos de tarefas com prazo até hoje que não couberam."""
    return sum(pr.duracao(p.tarefa) for p in plano.sem_espaco
               if pl.obrigatoria(p, plano.agora))


def em_sobrecarga(plano: Plano) -> bool:
    return excesso_min(plano) > 0


@dataclass(frozen=True)
class Item:
    pont: Pontuacao
    classe: str
    bloco: Bloco | None          # horário proposto hoje
    adiar_para: date | None      # sugestão quando não cabe hoje


@dataclass
class Proposta:
    plano: Plano                 # o dia realista
    excesso_min: int             # quanto faltava no plano original
    itens: list[Item] = field(default_factory=list)

    def da_classe(self, classe: str) -> list[Item]:
        return [i for i in self.itens if i.classe == classe]

    @property
    def adiar(self) -> list[Item]:
        return [i for i in self.itens if i.bloco is None]

    @property
    def essencial_sem_espaco(self) -> list[Item]:
        return [i for i in self.adiar if i.classe == ESSENCIAL]


def propor(pontuadas: list[Pontuacao], eventos: list[Evento], agora: datetime,
           original: Plano | None = None) -> Proposta:
    """1. Escolhe o que fica: na ordem das classes, cada tarefa no menor espaço
          onde cabe (aproveita as brechas; uma classe acima nunca perde lugar
          para uma abaixo enquanto houver espaço para ela).
       2. Horários: as escolhidas de novo no primeiro espaço, na ordem das
          classes; se assim alguma não couber, das mais longas para as mais
          curtas; se nem assim, ficam onde a escolha pôs."""
    original = original or pl.montar(pontuadas, eventos, agora)
    classe = {p.tarefa.id: classificar(p, agora) for p in pontuadas}
    ordem = sorted(pontuadas, key=lambda p: CLASSES.index(classe[p.tarefa.id]))  # estável
    escolha = pl.montar(ordem, eventos, agora, obrigatorias_primeiro=False, menor_espaco=True)
    ficam = {b.pont.tarefa.id for b in escolha.tarefas}
    escolhidas = [p for p in ordem if p.tarefa.id in ficam]
    realista = escolha
    for tentativa in (escolhidas,
                      sorted(escolhidas, key=lambda p: -pr.duracao(p.tarefa))):
        plano = pl.montar(tentativa, eventos, agora, obrigatorias_primeiro=False)
        if not plano.sem_espaco:
            realista = plano
            break
    amanha = agora.date() + timedelta(days=1)
    itens = []
    for p in ordem:
        bloco = realista.bloco_de(p.tarefa.id)
        itens.append(Item(p, classe[p.tarefa.id], bloco, None if bloco else amanha))
    return Proposta(realista, excesso_min(original), itens)


def _horas(minutos: int) -> str:
    h, m = divmod(max(0, minutos), 60)
    if not h:
        return f"{m} min"
    return f"{h}h{m:02d}" if m else f"{h}h"


def card(prop: Proposta) -> tuple[str, str]:
    partes = [f"⚠ Faltam {_horas(prop.excesso_min)} para caber tudo hoje."]
    for c in CLASSES:
        itens = prop.da_classe(c)
        if not itens:
            continue
        partes.append(NOMES[c].upper())
        for i in itens:
            if i.bloco:
                partes.append(f"  {i.bloco.ini:%H:%M}–{i.bloco.fim:%H:%M}  {i.pont.tarefa.titulo}")
            else:
                partes.append(f"  → {i.adiar_para:%d/%m}  {i.pont.tarefa.titulo} (sugestão: adiar)")
    hoje = [i for i in prop.itens if i.bloco]
    partes.append(f"\nPROPOSTA: {len(hoje)} hoje ({_horas(sum(i.bloco.minutos for i in hoje))}), "
                  f"{len(prop.adiar)} para amanhã.")
    if prop.essencial_sem_espaco:
        partes.append("Nem o essencial cabe: dá para encurtar ou trocar algo de lugar?")
    partes.append("Nada foi alterado.")
    return "DIA — sobrecarga", "\n".join(partes)


def para_fala(prop: Proposta) -> str:
    def nomes(itens):
        return ", ".join(i.pont.tarefa.titulo for i in itens) or "nada"
    texto = (f"Sobrecarga: faltam {_horas(prop.excesso_min)} para caber tudo hoje. "
             f"Essencial: {nomes(prop.da_classe(ESSENCIAL))}. "
             f"Importante: {nomes(prop.da_classe(IMPORTANTE))}. "
             f"Pode esperar: {nomes(prop.da_classe(PODE_ESPERAR))}. "
             f"Proposta: adiar para amanhã {nomes(prop.adiar)}.")
    if prop.essencial_sem_espaco:
        texto += f" Nem o essencial cabe: {nomes(prop.essencial_sem_espaco)}."
    return texto
