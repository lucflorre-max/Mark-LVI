"""
jarvis/brain/espaco_livre.py — espaço livre inesperado (M3 tarefa 5).

Documento-mestre §5.2: quando surgir espaço livre inesperado, priorizar as
pendências atrasadas que caibam no intervalo; entre várias, combinar
importância, prazo e tempo disponível.

    importância    a prioridade dita (fator de impacto do motor)          45 %
    prazo          há quanto tempo está atrasada (satura em 7 dias)        30 %
    aproveitamento quanto do intervalo a tarefa usa (cabe certinho = 1)    25 %

Nenhuma atrasada cabe: sugere a de hoje que couber, avisando. Só sugere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from jarvis.brain import prioridade as pr
from jarvis.brain.plano import Plano
from jarvis.brain.prioridade import Pontuacao

PESOS = {"importancia": 0.45, "prazo": 0.30, "aproveitamento": 0.25}
ALTERNATIVAS = 2


@dataclass(frozen=True)
class Candidata:
    pont: Pontuacao
    nota: float
    minutos: int
    sem_duracao: bool


@dataclass
class Encaixe:
    minutos: int
    escolha: Candidata | None = None
    alternativas: list[Candidata] = field(default_factory=list)
    so_de_hoje: bool = False             # nenhuma atrasada coube
    menor_atrasada: Candidata | None = None   # quando nada cabe


def janela_agora(plano: Plano) -> int:
    """Minutos livres de agora até o próximo compromisso ou hora marcada."""
    fixos = [b.ini for b in plano.blocos if b.fixa and b.fim > plano.agora]
    if any(i <= plano.agora for i in fixos):
        return 0
    fim = min([i for i in fixos] + [plano.limite])
    return max(0, int((fim - plano.agora).total_seconds() // 60))


def _candidata(p: Pontuacao, minutos: int, agora: datetime) -> Candidata:
    d = pr.duracao(p.tarefa)
    atraso = min(1.0, (pr.dias_de_atraso(p.tarefa, agora) + 1) / 8) if p.atrasada else 0.0
    nota = (PESOS["importancia"] * pr.fator_impacto(p.tarefa)
            + PESOS["prazo"] * atraso
            + PESOS["aproveitamento"] * (d / minutos))
    return Candidata(p, round(nota, 4), d, p.tarefa.duracao_min is None)


def sugerir(minutos: int, pontuadas: list[Pontuacao], agora: datetime) -> Encaixe:
    enc = Encaixe(minutos)
    if minutos <= 0:
        return enc
    atrasadas = [p for p in pontuadas if p.atrasada]
    cabem = [p for p in atrasadas if pr.duracao(p.tarefa) <= minutos]
    if not cabem:
        hoje = [p for p in pontuadas if not p.atrasada and p.tarefa.prazo
                and p.tarefa.prazo[:10] == agora.date().isoformat()]
        cabem = [p for p in hoje if pr.duracao(p.tarefa) <= minutos]
        enc.so_de_hoje = bool(cabem)
    if not cabem:
        if atrasadas:
            menor = min(atrasadas, key=lambda p: pr.duracao(p.tarefa))
            enc.menor_atrasada = _candidata(menor, max(minutos, pr.duracao(menor.tarefa)), agora)
        return enc
    ordem = sorted((_candidata(p, minutos, agora) for p in cabem),
                   key=lambda c: (-c.nota, c.pont.tarefa.prazo or "", c.pont.tarefa.id))
    enc.escolha, enc.alternativas = ordem[0], ordem[1:1 + ALTERNATIVAS]
    return enc


def _descrever(c: Candidata, agora: datetime) -> str:
    t = c.pont.tarefa
    partes = [f"{c.minutos} min" + (" estimados" if c.sem_duracao else "")]
    if c.pont.atrasada:
        dias = pr.dias_de_atraso(t, agora)
        partes.append(f"atrasada há {dias} dia{'s' if dias > 1 else ''}" if dias else "atrasada")
    if t.prioridade:
        partes.append(f"prioridade {pr._NOME_PRIO[t.prioridade]}")
    return f"{t.titulo} ({', '.join(partes)})"


def card(enc: Encaixe, agora: datetime) -> tuple[str, str]:
    titulo = f"LIVRE — {enc.minutos} min"
    if enc.escolha is None:
        if enc.menor_atrasada:
            texto = (f"Nenhuma pendência cabe em {enc.minutos} min.\n"
                     f"A atrasada mais curta: {_descrever(enc.menor_atrasada, agora)}.")
        else:
            texto = f"Nenhuma pendência cabe em {enc.minutos} min."
        return titulo, texto
    partes = []
    if enc.so_de_hoje:
        partes.append("Nenhuma atrasada cabe; esta é de hoje.")
    partes.append(f"Sugestão: {_descrever(enc.escolha, agora)}")
    partes += [f"  ou {_descrever(c, agora)}" for c in enc.alternativas]
    partes.append("Nada foi alterado.")
    return titulo, "\n".join(partes)


def para_fala(enc: Encaixe, agora: datetime) -> str:
    if enc.escolha is None:
        texto = f"Nenhuma pendência cabe em {enc.minutos} minutos."
        if enc.menor_atrasada:
            texto += f" A atrasada mais curta: {_descrever(enc.menor_atrasada, agora)}."
        return texto
    texto = f"Com {enc.minutos} minutos livres: {_descrever(enc.escolha, agora)}."
    if enc.so_de_hoje:
        texto = "Nenhuma atrasada cabe. " + texto
    if enc.alternativas:
        texto += " Outras: " + "; ".join(_descrever(c, agora) for c in enc.alternativas) + "."
    return texto
