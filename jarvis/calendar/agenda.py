"""
jarvis/calendar/agenda.py — a agenda de um dia, pronta para o card e para a fala.

Transforma os eventos crus da API do Calendar em `Evento` e formata em
português. Não fala com a rede: quem busca é `CalendarClient.eventos()`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo

_DIAS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
SEM_TITULO = "(sem título)"


@dataclass(frozen=True)
class Evento:
    titulo: str
    inicio: datetime | None      # None = dia inteiro
    fim: datetime | None
    dia_inteiro: bool = False
    local: str = ""
    link: str = ""
    id: str = ""
    data: date | None = None     # o dia, nos eventos de dia inteiro


def limites_do_dia(dia: date, fuso: tzinfo) -> tuple[datetime, datetime]:
    """00:00 do dia e 00:00 do dia seguinte, no fuso do usuário."""
    ini = datetime.combine(dia, time(0, 0), tzinfo=fuso)
    return ini, ini + timedelta(days=1)


def _quando(campo: dict, fuso: tzinfo) -> tuple[datetime | None, date | None]:
    if campo.get("dateTime"):
        return datetime.fromisoformat(campo["dateTime"].replace("Z", "+00:00")).astimezone(fuso), None
    if campo.get("date"):
        return None, date.fromisoformat(campo["date"])
    return None, None


def de_api(item: dict, fuso: tzinfo) -> Evento | None:
    """Um item de events.list → Evento. None para cancelados ou sem data."""
    if item.get("status") == "cancelled":
        return None
    ini, dia_ini = _quando(item.get("start") or {}, fuso)
    fim, _ = _quando(item.get("end") or {}, fuso)
    if ini is None and dia_ini is None:
        return None
    return Evento(
        titulo=(item.get("summary") or "").strip() or SEM_TITULO,
        inicio=ini, fim=fim, dia_inteiro=ini is None,
        local=(item.get("location") or "").strip(),
        link=item.get("htmlLink") or "", id=item.get("id") or "", data=dia_ini,
    )


def ordenar(eventos: list[Evento]) -> list[Evento]:
    """Dia inteiro primeiro, depois por horário de início."""
    return sorted(eventos, key=lambda e: (not e.dia_inteiro,
                                          e.inicio.timestamp() if e.inicio else 0))


def _hora(dt: datetime) -> str:
    return f"{dt:%H:%M}"


def _hora_fala(dt: datetime) -> str:
    return f"{dt.hour}h" if dt.minute == 0 else f"{dt.hour}h{dt.minute:02d}"


def nome_do_dia(dia: date, hoje: date) -> str:
    """'hoje, sexta 23/10', 'amanhã, sábado 24/10', 'terça, 27/10'."""
    base = f"{_DIAS[dia.weekday()]}, {dia:%d/%m}"
    delta = (dia - hoje).days
    if delta == 0:
        return f"hoje, {base}"
    if delta == 1:
        return f"amanhã, {base}"
    return base


def _faixa(e: Evento, dia: date, fala: bool) -> str:
    if e.dia_inteiro:
        return "dia inteiro"
    fmt = _hora_fala if fala else _hora
    ini = fmt(e.inicio) if e.inicio.date() == dia else "antes"
    if e.fim is None:
        return ini
    fim = fmt(e.fim) if e.fim.date() == dia else "depois"
    return f"{ini}–{fim}"


def em_andamento(e: Evento, agora: datetime) -> bool:
    return (not e.dia_inteiro and e.inicio is not None and e.fim is not None
            and e.inicio <= agora < e.fim)


def card(eventos: list[Evento], dia: date, agora: datetime) -> tuple[str, str]:
    """(título, texto) para o painel de conteúdo. Uma linha por compromisso."""
    titulo = f"AGENDA — {nome_do_dia(dia, agora.date())}"
    if not eventos:
        return titulo, "Nada marcado."
    linhas = []
    batem = sobrepostos(eventos)
    for e in ordenar(eventos):
        marca = "▶ " if em_andamento(e, agora) else ("⚠ " if e in batem else "")
        local = f" · {e.local}" if e.local else ""
        linhas.append(f"{marca}{_faixa(e, dia, fala=False):<13}{e.titulo}{local}")
    if batem:
        linhas.append("⚠ horários que se sobrepõem")
    return titulo, "\n".join(linhas)


def descrever(e: Evento, hoje: date) -> str:
    """Uma linha com tudo que vai mudar: '“Dentista” · terça, 27/10, 14h30–15h30 · Centro'."""
    if e.dia_inteiro:
        quando = f"{nome_do_dia(e.data, hoje)}, dia inteiro"
    else:
        quando = f"{nome_do_dia(e.inicio.date(), hoje)}, {_faixa(e, e.inicio.date(), fala=True)}"
    local = f" · {e.local}" if e.local else ""
    return f"“{e.titulo}” · {quando}{local}"


def para_fala(eventos: list[Evento], dia: date) -> str:
    """Lista curta para o modelo resumir em voz: '9h–10h Reunião; …'."""
    return "; ".join(f"{_faixa(e, dia, fala=True)} {e.titulo}"
                     + (f" ({e.local})" if e.local else "")
                     for e in ordenar(eventos))


# ── Conflitos (M2 tarefa 6) ──────────────────────────────────────────────────
# Só analisam e sugerem. Nada aqui altera a agenda (documento-mestre §5.1).

FIM_DO_EXPEDIENTE = time(21, 0)   # a sugestão de encaixe não passa disto
PASSO_MIN = 15                    # sugestões em múltiplos de 15 minutos


def conflitos(eventos: list[Evento], ini: datetime, fim: datetime,
              ignorar_id: str = "") -> list[Evento]:
    """Compromissos com hora que se sobrepõem a [ini, fim). Os de dia inteiro
    (feriado, aniversário) não ocupam horário."""
    return ordenar([e for e in eventos
                    if not e.dia_inteiro and e.inicio and e.fim
                    and (not ignorar_id or e.id != ignorar_id)
                    and e.inicio < fim and e.fim > ini])


def sobrepostos(eventos: list[Evento]) -> list[Evento]:
    """Os compromissos do dia que batem com algum outro."""
    com_hora = [e for e in eventos if not e.dia_inteiro and e.inicio and e.fim]
    return [e for i, e in enumerate(com_hora)
            if any(i != j and o.inicio < e.fim and o.fim > e.inicio
                   for j, o in enumerate(com_hora))]


def _arredondar(dt: datetime) -> datetime:
    """Sobe para o próximo múltiplo de 15 minutos (14h50 → 15h; 15h → 15h)."""
    cheio = dt.replace(second=0, microsecond=0)
    if cheio < dt:
        cheio += timedelta(minutes=1)
    return cheio + timedelta(minutes=-cheio.minute % PASSO_MIN)


def proximo_livre(eventos: list[Evento], ini: datetime,
                  duracao: timedelta) -> datetime | None:
    """Primeiro início a partir de `ini` em que cabe `duracao` sem conflito,
    no mesmo dia e até FIM_DO_EXPEDIENTE. None quando não cabe mais."""
    limite = datetime.combine(ini.date(), FIM_DO_EXPEDIENTE, tzinfo=ini.tzinfo)
    candidato = ini
    for _ in range(100):
        if candidato + duracao > limite:
            return None
        batem = conflitos(eventos, candidato, candidato + duracao)
        if not batem:
            return candidato
        candidato = _arredondar(max(e.fim for e in batem))
    return None


def aviso_conflito(eventos: list[Evento], ini: datetime, fim: datetime) -> str:
    """'' sem conflito; senão ' — conflita com “Reunião” (14h–15h); livre a
    partir de 15h–15h45'. Para o banner, o card e o modelo."""
    batem = conflitos(eventos, ini, fim)
    if not batem:
        return ""
    nomes = "; ".join(f"“{e.titulo}” ({_faixa(e, ini.date(), fala=True)})" for e in batem)
    livre = proximo_livre(eventos, ini, fim - ini)
    if livre is None:
        sugestao = "não há outro horário livre com essa duração até as 21h"
    else:
        sugestao = (f"horário livre mais próximo: {_hora_fala(livre)}–"
                    f"{_hora_fala(livre + (fim - ini))}")
    return f" — conflita com {nomes}; {sugestao}"
