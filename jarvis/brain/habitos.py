"""
jarvis/brain/habitos.py — progresso de hábitos e metas semanais (M3 tarefa 6).

Documento-mestre §5.3: hábitos pessoais, metas semanais e sequências podem
ser acompanhados sem excesso de notificações (§2: sem sensação de vigilância).

    Semana        de segunda a domingo.
    Meta          dias por semana (1 a 7). Diário = 7.
    Sequência     semanas seguidas batendo a meta (a atual conta quando já bateu).
    Dias seguidos dias marcados em sequência até hoje (ou até ontem, se hoje
                  ainda não foi marcado: o dia não acabou).
    Precisa hoje  só quando, sem fazer hoje, a meta da semana fica impossível.
                  É o único caso em que um hábito pode virar lembrete
                  (jarvis/brain/lembretes.py), no máximo um por dia.

Só conta o que o usuário marcou. Nada aqui mede tempo, foco ou pausas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from jarvis.brain.rotinas import Habito


def inicio_da_semana(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


@dataclass(frozen=True)
class Progresso:
    habito: Habito
    feitos_semana: int
    meta: int
    feito_hoje: bool
    dias_restantes: int          # contando hoje
    sequencia_semanas: int
    dias_seguidos: int

    @property
    def faltam(self) -> int:
        return max(0, self.meta - self.feitos_semana)

    @property
    def meta_batida(self) -> bool:
        return self.faltam == 0

    @property
    def precisa_hoje(self) -> bool:
        return not self.feito_hoje and self.faltam > 0 and self.faltam >= self.dias_restantes


def _na_semana(registros: set[date], inicio: date) -> int:
    return sum(1 for d in registros if inicio <= d < inicio + timedelta(days=7))


def calcular(h: Habito, registros: set[date], hoje: date) -> Progresso:
    inicio = inicio_da_semana(hoje)
    feitos = _na_semana(registros, inicio)
    restantes = 7 - hoje.weekday()

    seq, semana = 0, inicio - timedelta(days=7)
    while _na_semana(registros, semana) >= h.meta_semanal:
        seq += 1
        semana -= timedelta(days=7)
    if feitos >= h.meta_semanal:
        seq += 1

    dia = hoje if hoje in registros else hoje - timedelta(days=1)
    seguidos = 0
    while dia in registros:
        seguidos += 1
        dia -= timedelta(days=1)
    return Progresso(h, feitos, h.meta_semanal, hoje in registros, restantes, seq, seguidos)


def linha(p: Progresso) -> str:
    marca = "✔" if p.feito_hoje else "·"
    meta = "meta batida" if p.meta_batida else f"faltam {p.faltam}"
    extras = []
    if p.sequencia_semanas:
        extras.append(f"{p.sequencia_semanas} semana{'s' if p.sequencia_semanas > 1 else ''} seguida"
                      f"{'s' if p.sequencia_semanas > 1 else ''}")
    if p.dias_seguidos > 1:
        extras.append(f"{p.dias_seguidos} dias seguidos")
    extra = f" · {', '.join(extras)}" if extras else ""
    return f"{marca} {p.habito.nome}: {p.feitos_semana}/{p.meta} na semana ({meta}){extra}"


def card(progressos: list[Progresso]) -> tuple[str, str]:
    if not progressos:
        return "HÁBITOS", "Nenhum hábito acompanhado ainda."
    return "HÁBITOS — semana", "\n".join(linha(p) for p in progressos)
