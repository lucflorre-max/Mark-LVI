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
        link=item.get("htmlLink") or "", id=item.get("id") or "",
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
    for e in ordenar(eventos):
        marca = "▶ " if em_andamento(e, agora) else ""
        local = f" · {e.local}" if e.local else ""
        linhas.append(f"{marca}{_faixa(e, dia, fala=False):<13}{e.titulo}{local}")
    return titulo, "\n".join(linhas)


def para_fala(eventos: list[Evento], dia: date) -> str:
    """Lista curta para o modelo resumir em voz: '9h–10h Reunião; …'."""
    return "; ".join(f"{_faixa(e, dia, fala=True)} {e.titulo}"
                     + (f" ({e.local})" if e.local else "")
                     for e in ordenar(eventos))
