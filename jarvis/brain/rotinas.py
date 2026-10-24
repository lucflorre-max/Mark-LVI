"""
jarvis/brain/rotinas.py — tarefas recorrentes e hábitos no banco (M3 tarefa 6).

Documento-mestre §5.3: tarefas recorrentes são criadas automaticamente e podem
ter horário adaptado; mudanças reais exigem confirmação.

    Regra        "diaria" | "dias_uteis" | "semanal:0,2,4" (0 = segunda) | "mensal:15"
    Geração      `gerar(dia)` cria a tarefa do dia de cada rotina ativa que vale
                 naquele dia. Uma vez só por rotina e dia (tabela de vínculos),
                 então chamar de novo não duplica. Dias passados não são
                 recriados: rotina esquecida não vira avalanche de atrasadas.
    Horário      se a hora da rotina bate com um compromisso do dia, a tarefa
                 daquele dia vai para o próximo horário livre e diz de onde
                 veio. A regra não muda: mudar a regra é "mudança real" e passa
                 pelo "sim" falado (jarvis/brain/policy.py).

Hábitos ficam aqui também (nome, meta semanal e os dias feitos); a conta de
progresso está em jarvis/brain/habitos.py.

Mesmo banco das tarefas (data/jarvis.db), tabelas próprias. Nada aqui guarda
foco, pausas ou interrupções (§5.2).
"""

from __future__ import annotations

import calendar
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from jarvis import config
from jarvis.calendar import agenda
from jarvis.calendar.agenda import Evento
from jarvis.tasks.repository import (
    TaskRepository, Tarefa, agora, normalizar_duracao, normalizar_prioridade,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS recorrencias (
    id           INTEGER PRIMARY KEY,
    titulo       TEXT NOT NULL,
    regra        TEXT NOT NULL,
    hora         TEXT,
    prioridade   TEXT CHECK (prioridade IN ('alta', 'media', 'baixa')),
    duracao_min  INTEGER CHECK (duracao_min > 0),
    projeto      TEXT,
    ativa        INTEGER NOT NULL DEFAULT 1,
    criado_em    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recorrencia_tarefas (
    recorrencia_id INTEGER NOT NULL REFERENCES recorrencias(id) ON DELETE CASCADE,
    data           TEXT NOT NULL,
    tarefa_id      INTEGER,
    UNIQUE (recorrencia_id, data)
);
CREATE TABLE IF NOT EXISTS habitos (
    id            INTEGER PRIMARY KEY,
    nome          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    meta_semanal  INTEGER NOT NULL CHECK (meta_semanal BETWEEN 1 AND 7),
    ativo         INTEGER NOT NULL DEFAULT 1,
    criado_em     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS habito_registros (
    habito_id  INTEGER NOT NULL REFERENCES habitos(id) ON DELETE CASCADE,
    data       TEXT NOT NULL,
    UNIQUE (habito_id, data)
);
"""

DIAS_CURTOS = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
_DIAS_LONGOS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
_ACENTOS = str.maketrans("áâãàéêíóôõúç", "aaaaeeiooouc")


# ── Regras ──────────────────────────────────────────────────────────────────

def _dia_semana(texto: str) -> int:
    t = texto.strip().lower().translate(_ACENTOS)[:3]
    for i, nome in enumerate(DIAS_CURTOS):
        if nome.translate(_ACENTOS) == t:
            return i
    raise ValueError(f"dia da semana inválido: {texto!r}")


def montar_regra(frequencia: str, dias=None, dia_do_mes=None) -> str:
    """Da fala para a regra guardada. Levanta ValueError com a explicação."""
    f = (frequencia or "").strip().lower().translate(_ACENTOS).replace(" ", "_")
    if f in ("diaria", "diario", "todo_dia", "todos_os_dias"):
        return "diaria"
    if f in ("dias_uteis", "util", "uteis"):
        return "dias_uteis"
    if f in ("semanal", "semana", "toda_semana"):
        if isinstance(dias, str):
            dias = [d for d in dias.replace(" e ", ",").split(",") if d.strip()]
        numeros = sorted({_dia_semana(str(d)) for d in (dias or [])})
        if not numeros:
            raise ValueError("rotina semanal precisa dos dias (ex.: seg, qua)")
        return "semanal:" + ",".join(map(str, numeros))
    if f in ("mensal", "mes", "todo_mes"):
        try:
            n = int(dia_do_mes)
        except (TypeError, ValueError):
            raise ValueError("rotina mensal precisa do dia do mês (1 a 31)") from None
        if not 1 <= n <= 31:
            raise ValueError("dia do mês vai de 1 a 31")
        return f"mensal:{n}"
    raise ValueError("frequência inválida: use diaria, dias_uteis, semanal ou mensal")


def vale_em(regra: str, dia: date) -> bool:
    tipo, _, arg = regra.partition(":")
    if tipo == "diaria":
        return True
    if tipo == "dias_uteis":
        return dia.weekday() < 5
    if tipo == "semanal":
        return dia.weekday() in {int(x) for x in arg.split(",") if x}
    if tipo == "mensal":
        ultimo = calendar.monthrange(dia.year, dia.month)[1]
        return dia.day == min(int(arg), ultimo)       # 31 em mês curto → último dia
    return False


def validar_regra(regra: str) -> str:
    """A regra como está, ou ValueError se o formato não for um dos quatro."""
    tipo, _, arg = str(regra).partition(":")
    ok = (tipo in ("diaria", "dias_uteis") and not arg) \
        or (tipo == "semanal" and re.fullmatch(r"[0-6](,[0-6])*", arg)) \
        or (tipo == "mensal" and arg.isdigit() and 1 <= int(arg) <= 31)
    if not ok:
        raise ValueError(f"regra inválida: {regra!r}")
    return regra


def descrever_regra(regra: str, hora: str | None = None) -> str:
    tipo, _, arg = regra.partition(":")
    if tipo == "diaria":
        texto = "todo dia"
    elif tipo == "dias_uteis":
        texto = "de segunda a sexta"
    elif tipo == "semanal":
        nomes = [_DIAS_LONGOS[int(x)] for x in arg.split(",")]
        texto = "toda " + (nomes[0] if len(nomes) == 1
                           else ", ".join(nomes[:-1]) + " e " + nomes[-1])
    else:
        texto = f"todo dia {arg} do mês"
    return f"{texto} às {hora}" if hora else texto


def normalizar_hora(hora) -> str | None:
    """'7', '7h', '7h30', '07:30' → '07:30'."""
    if hora in (None, ""):
        return None
    m = re.fullmatch(r"(\d{1,2})(?:[:h](\d{2})?)?", str(hora).strip().lower())
    if not m or int(m[1]) > 23 or int(m[2] or 0) > 59:
        raise ValueError(f"hora inválida: {hora!r} (use HH:MM)")
    return f"{int(m[1]):02d}:{int(m[2] or 0):02d}"


# ── Banco ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Rotina:
    id: int
    titulo: str
    regra: str
    hora: str | None
    prioridade: str | None
    duracao_min: int | None
    projeto: str | None
    ativa: bool
    criado_em: str


@dataclass(frozen=True)
class Habito:
    id: int
    nome: str
    meta_semanal: int
    ativo: bool
    criado_em: str


class RotinasRepo:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else config.DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._conn()
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _run(self, sql: str, params=()) -> sqlite3.Cursor:
        conn = self._conn()
        try:
            with conn:
                return conn.execute(sql, params)
        finally:
            conn.close()

    def _rows(self, sql: str, params=()) -> list[sqlite3.Row]:
        conn = self._conn()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    # Rotinas
    def criar(self, titulo: str, regra: str, *, hora=None, prioridade=None,
              duracao_min=None, projeto: str | None = None) -> Rotina:
        titulo = (titulo or "").strip()
        if not titulo:
            raise ValueError("a rotina precisa de um título")
        regra = validar_regra(regra)
        cur = self._run(
            "INSERT INTO recorrencias (titulo, regra, hora, prioridade, duracao_min,"
            " projeto, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (titulo, regra, normalizar_hora(hora), normalizar_prioridade(prioridade),
             normalizar_duracao(duracao_min), (projeto or "").strip() or None, agora()))
        return self.obter(cur.lastrowid)

    def obter(self, rotina_id: int) -> Rotina | None:
        rows = self._rows("SELECT * FROM recorrencias WHERE id = ?", (rotina_id,))
        return _rotina(rows[0]) if rows else None

    def listar(self, so_ativas: bool = True) -> list[Rotina]:
        sql = "SELECT * FROM recorrencias" + (" WHERE ativa = 1" if so_ativas else "")
        return [_rotina(r) for r in self._rows(sql + " ORDER BY id")]

    def alterar(self, rotina_id: int, **campos) -> Rotina | None:
        normal = {"hora": normalizar_hora, "prioridade": normalizar_prioridade,
                  "duracao_min": normalizar_duracao, "regra": validar_regra,
                  "ativa": lambda a: 1 if a else 0, "titulo": lambda t: str(t).strip()}
        estranhos = set(campos) - set(normal)
        if estranhos:
            raise ValueError(f"campo desconhecido: {', '.join(sorted(estranhos))}")
        if not campos:
            return self.obter(rotina_id)
        valores = {k: normal[k](v) for k, v in campos.items()}
        sets = ", ".join(f"{k} = ?" for k in valores)
        cur = self._run(f"UPDATE recorrencias SET {sets} WHERE id = ?",
                        (*valores.values(), rotina_id))
        return self.obter(rotina_id) if cur.rowcount else None

    def ja_gerada(self, rotina_id: int, dia: date) -> bool:
        return bool(self._rows("SELECT 1 FROM recorrencia_tarefas WHERE recorrencia_id = ?"
                               " AND data = ?", (rotina_id, dia.isoformat())))

    def marcar_gerada(self, rotina_id: int, dia: date, tarefa_id: int | None) -> bool:
        """False se outra chamada já marcou (não cria duas vezes)."""
        try:
            self._run("INSERT INTO recorrencia_tarefas (recorrencia_id, data, tarefa_id)"
                      " VALUES (?, ?, ?)", (rotina_id, dia.isoformat(), tarefa_id))
            return True
        except sqlite3.IntegrityError:
            return False

    def vincular_tarefa(self, rotina_id: int, dia: date, tarefa_id: int) -> None:
        self._run("UPDATE recorrencia_tarefas SET tarefa_id = ? WHERE recorrencia_id = ?"
                  " AND data = ?", (tarefa_id, rotina_id, dia.isoformat()))

    # Hábitos
    def criar_habito(self, nome: str, meta_semanal: int = 7) -> Habito:
        nome = (nome or "").strip()
        if not nome:
            raise ValueError("o hábito precisa de um nome")
        meta = int(meta_semanal)
        if not 1 <= meta <= 7:
            raise ValueError("a meta semanal vai de 1 a 7 dias")
        cur = self._run("INSERT INTO habitos (nome, meta_semanal, criado_em) VALUES (?, ?, ?)",
                        (nome, meta, agora()))
        return self.habito(cur.lastrowid)

    def habito(self, habito_id: int) -> Habito | None:
        rows = self._rows("SELECT * FROM habitos WHERE id = ?", (habito_id,))
        return _habito(rows[0]) if rows else None

    def habito_por_nome(self, nome: str) -> Habito | None:
        rows = self._rows("SELECT * FROM habitos WHERE nome = ?", ((nome or "").strip(),))
        return _habito(rows[0]) if rows else None

    def habitos(self) -> list[Habito]:
        return [_habito(r) for r in self._rows("SELECT * FROM habitos WHERE ativo = 1 ORDER BY id")]

    def registrar(self, habito_id: int, dia: date) -> bool:
        """Marca o dia como feito. False se já estava marcado."""
        try:
            self._run("INSERT INTO habito_registros (habito_id, data) VALUES (?, ?)",
                      (habito_id, dia.isoformat()))
            return True
        except sqlite3.IntegrityError:
            return False

    def desmarcar(self, habito_id: int, dia: date) -> bool:
        return self._run("DELETE FROM habito_registros WHERE habito_id = ? AND data = ?",
                         (habito_id, dia.isoformat())).rowcount > 0

    def registros(self, habito_id: int, desde: date | None = None) -> set[date]:
        sql, params = "SELECT data FROM habito_registros WHERE habito_id = ?", [habito_id]
        if desde:
            sql += " AND data >= ?"
            params.append(desde.isoformat())
        return {date.fromisoformat(r["data"]) for r in self._rows(sql, params)}


def _rotina(r: sqlite3.Row) -> Rotina:
    d = dict(r)
    d["ativa"] = bool(d["ativa"])
    return Rotina(**d)


def _habito(r: sqlite3.Row) -> Habito:
    d = dict(r)
    d["ativo"] = bool(d["ativo"])
    return Habito(**d)


# ── Geração automática ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class Gerada:
    rotina: Rotina
    tarefa: Tarefa
    adaptada_de: str | None = None     # hora original, quando o horário mudou


def _criada_depois_da_hora(r: Rotina, dia: date, agora: datetime | None) -> bool:
    """Rotina criada hoje cuja hora de hoje já passou: começa na próxima vez,
    em vez de nascer atrasada."""
    if agora is None or not r.hora or dia != agora.date() or r.criado_em[:10] != dia.isoformat():
        return False
    return time.fromisoformat(r.hora) < agora.time().replace(tzinfo=None)


def gerar(dia: date, tarefas: TaskRepository, rotinas: RotinasRepo,
          eventos: list[Evento] | None = None, agora: datetime | None = None) -> list[Gerada]:
    """Cria as tarefas do dia das rotinas ativas. Idempotente."""
    fuso = config.fuso()
    criadas = []
    for r in rotinas.listar():
        if not vale_em(r.regra, dia) or rotinas.ja_gerada(r.id, dia):
            continue
        if _criada_depois_da_hora(r, dia, agora):
            continue
        if not rotinas.marcar_gerada(r.id, dia, None):
            continue
        prazo, adaptada = dia.isoformat(), None
        if r.hora:
            ini = datetime.combine(dia, time.fromisoformat(r.hora), tzinfo=fuso)
            dur = timedelta(minutes=r.duracao_min or 30)
            if eventos and agenda.conflitos(eventos, ini, ini + dur):
                livre = agenda.proximo_livre(eventos, ini, dur)
                if livre is not None:
                    ini, adaptada = livre, r.hora
            prazo = ini.isoformat()
        nota = f"Rotina: {descrever_regra(r.regra, r.hora)}."
        if adaptada:
            nota += f" Hoje às {ini:%H:%M} em vez de {adaptada}: a hora de sempre batia com um compromisso."
        t = tarefas.adicionar(r.titulo, descricao=nota, prazo=prazo, prioridade=r.prioridade,
                              duracao_min=r.duracao_min, projeto=r.projeto, origem="recorrencia")
        rotinas.vincular_tarefa(r.id, dia, t.id)
        criadas.append(Gerada(r, t, adaptada))
    return criadas
