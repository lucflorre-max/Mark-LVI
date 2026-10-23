"""
jarvis/tasks/repository.py — banco SQLite das tarefas (data/jarvis.db).

Só a biblioteca padrão. Uma conexão por operação: o plugin roda em threads do
executor do Mark, e conexões curtas evitam compartilhar uma entre threads.

Datas em ISO 8601 no fuso de São Paulo:
    prazo com hora   → "2026-10-24T14:00:00-03:00"
    prazo só com dia → "2026-10-24"
Os dez primeiros caracteres são sempre o dia, o que torna "listar por dia"
uma comparação simples.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from jarvis import config

PRIORIDADES = ("alta", "media", "baixa")
STATUS = ("aberta", "concluida")
_ACENTOS = str.maketrans("áâãàéêíóôõúç", "aaaaeeiooouc")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id         INTEGER PRIMARY KEY,
    nome       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    criado_em  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY,
    titulo        TEXT NOT NULL,
    descricao     TEXT,
    prazo         TEXT,
    prioridade    TEXT CHECK (prioridade IN ('alta', 'media', 'baixa')),
    duracao_min   INTEGER CHECK (duracao_min > 0),
    projeto_id    INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    status        TEXT NOT NULL DEFAULT 'aberta'
                  CHECK (status IN ('aberta', 'concluida')),
    origem        TEXT NOT NULL DEFAULT 'voz',
    criado_em     TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_prazo ON tasks(prazo);
CREATE TABLE IF NOT EXISTS inbox (
    id          INTEGER PRIMARY KEY,
    texto       TEXT NOT NULL,
    origem      TEXT NOT NULL DEFAULT 'voz',
    processado  INTEGER NOT NULL DEFAULT 0,
    criado_em   TEXT NOT NULL
);
PRAGMA user_version = 1;
"""


@dataclass(frozen=True)
class Tarefa:
    id: int
    titulo: str
    descricao: str | None
    prazo: str | None
    prioridade: str | None
    duracao_min: int | None
    projeto_id: int | None
    status: str
    origem: str
    criado_em: str
    atualizado_em: str


@dataclass(frozen=True)
class ItemInbox:
    id: int
    texto: str
    origem: str
    processado: bool
    criado_em: str


# ── Normalização ─────────────────────────────────────────────────────────────

def agora() -> str:
    return datetime.now(config.fuso()).isoformat(timespec="seconds")


def normalizar_prazo(prazo) -> str | None:
    """Aceita date, datetime ou texto ISO 8601 e devolve o formato do banco.
    Hora sem fuso é tratada como hora de São Paulo. Levanta ValueError se o
    texto não for uma data."""
    if prazo in (None, ""):
        return None
    if isinstance(prazo, datetime):
        dt = prazo
    elif isinstance(prazo, date):
        return prazo.isoformat()
    else:
        texto = str(prazo).strip()
        if len(texto) == 10:
            return date.fromisoformat(texto).isoformat()
        dt = datetime.fromisoformat(texto)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=config.fuso())
    return dt.astimezone(config.fuso()).isoformat(timespec="seconds")


def normalizar_prioridade(prioridade) -> str | None:
    if prioridade in (None, ""):
        return None
    valor = str(prioridade).strip().lower().translate(_ACENTOS)
    if valor not in PRIORIDADES:
        raise ValueError(f"prioridade inválida: {prioridade!r} (use alta, media ou baixa)")
    return valor


def normalizar_duracao(duracao) -> int | None:
    if duracao in (None, ""):
        return None
    valor = int(duracao)
    if valor <= 0:
        raise ValueError(f"duração inválida: {duracao!r} (minutos, maior que zero)")
    return valor


# ── Repositório ──────────────────────────────────────────────────────────────

class TaskRepository:
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

    # Projetos
    def projeto_id(self, nome: str | None, criar: bool = True) -> int | None:
        """Id do projeto pelo nome (sem diferenciar maiúsculas); cria se não existir."""
        nome = (nome or "").strip()
        if not nome:
            return None
        rows = self._rows("SELECT id FROM projects WHERE nome = ?", (nome,))
        if rows:
            return rows[0]["id"]
        if not criar:
            return None
        return self._run("INSERT INTO projects (nome, criado_em) VALUES (?, ?)",
                         (nome, agora())).lastrowid

    # Tarefas
    def adicionar(self, titulo: str, *, descricao: str | None = None, prazo=None,
                  prioridade=None, duracao_min=None, projeto: str | None = None,
                  origem: str = "voz") -> Tarefa:
        titulo = (titulo or "").strip()
        if not titulo:
            raise ValueError("a tarefa precisa de um título")
        momento = agora()
        cur = self._run(
            "INSERT INTO tasks (titulo, descricao, prazo, prioridade, duracao_min,"
            " projeto_id, origem, criado_em, atualizado_em)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (titulo, descricao, normalizar_prazo(prazo),
             normalizar_prioridade(prioridade), normalizar_duracao(duracao_min),
             self.projeto_id(projeto), origem, momento, momento),
        )
        return self.obter(cur.lastrowid)

    def obter(self, tarefa_id: int) -> Tarefa | None:
        rows = self._rows("SELECT * FROM tasks WHERE id = ?", (tarefa_id,))
        return Tarefa(**dict(rows[0])) if rows else None

    def listar_dia(self, dia=None, incluir_concluidas: bool = False) -> list[Tarefa]:
        """Tarefas com prazo no dia (padrão: hoje), as com hora primeiro na
        ordem do horário, depois as só com data."""
        if dia is None:
            dia = datetime.now(config.fuso()).date()
        dia = dia.isoformat() if isinstance(dia, date) else str(dia)[:10]
        sql = "SELECT * FROM tasks WHERE substr(prazo, 1, 10) = ?"
        if not incluir_concluidas:
            sql += " AND status = 'aberta'"
        sql += " ORDER BY length(prazo) = 10, prazo, id"
        return [Tarefa(**dict(r)) for r in self._rows(sql, (dia,))]

    def _status(self, tarefa_id: int, status: str) -> Tarefa | None:
        cur = self._run("UPDATE tasks SET status = ?, atualizado_em = ? WHERE id = ?",
                        (status, agora(), tarefa_id))
        return self.obter(tarefa_id) if cur.rowcount else None

    def concluir(self, tarefa_id: int) -> Tarefa | None:
        return self._status(tarefa_id, "concluida")

    def reabrir(self, tarefa_id: int) -> Tarefa | None:
        """Desfaz `concluir`."""
        return self._status(tarefa_id, "aberta")

    def adiar(self, tarefa_id: int, novo_prazo) -> Tarefa | None:
        cur = self._run("UPDATE tasks SET prazo = ?, atualizado_em = ? WHERE id = ?",
                        (normalizar_prazo(novo_prazo), agora(), tarefa_id))
        return self.obter(tarefa_id) if cur.rowcount else None

    def apagar(self, tarefa_id: int) -> Tarefa | None:
        """Apaga e devolve a tarefa como era, para quem quiser desfazer."""
        antes = self.obter(tarefa_id)
        if antes:
            self._run("DELETE FROM tasks WHERE id = ?", (tarefa_id,))
        return antes

    # Caixa de entrada
    def adicionar_inbox(self, texto: str, origem: str = "voz") -> ItemInbox:
        texto = (texto or "").strip()
        if not texto:
            raise ValueError("o item da caixa de entrada precisa de texto")
        cur = self._run("INSERT INTO inbox (texto, origem, criado_em) VALUES (?, ?, ?)",
                        (texto, origem, agora()))
        return self.listar_inbox(incluir_processados=True, ids=[cur.lastrowid])[0]

    def listar_inbox(self, incluir_processados: bool = False,
                     ids: list[int] | None = None) -> list[ItemInbox]:
        sql, params = "SELECT * FROM inbox WHERE 1 = 1", []
        if not incluir_processados:
            sql += " AND processado = 0"
        if ids:
            sql += f" AND id IN ({', '.join('?' * len(ids))})"
            params += ids
        rows = self._rows(sql + " ORDER BY id", params)
        return [ItemInbox(r["id"], r["texto"], r["origem"], bool(r["processado"]),
                          r["criado_em"]) for r in rows]
