"""
jarvis/tasks/service.py — regras da ferramenta jarvis_tarefas.

O plugin plugins/jarvis_tarefas.py só repassa a chamada para `handle()`.

FLUXO DE `criar` (docs/plano-m1.md, tarefa 4)
    1. Faltando prazo, prioridade ou duração → pergunta curta só pelo que
       falta. O rascunho fica guardado, então a próxima chamada pode trazer só
       o que o usuário respondeu.
    2. Completo → resumo de uma frase e pedido de "sim". Nada salvo ainda.
    3. Nova chamada com confirmado=true → salva e registra o desfazer.
       `confirmado` só vale depois que o resumo foi mostrado: o modelo não
       consegue pular o passo 2 mandando confirmado=true de primeira.
    "Depois eu vejo isso" → pergunta o prazo; se o usuário mantiver o prazo
    indefinido (prazo="indefinido"), a tarefa vai para a caixa de entrada.

M2 tarefa 5: o resumo diz para onde a tarefa vai, e depois de salva ela ganha
um cartão no Trello e, se tiver hora, um compromisso vinculado no Calendar
(que espera o clique). Detalhes em jarvis/tasks/sincronia.py.

As respostas são instruções para o modelo, em português; ele fala com as
próprias palavras. Nada aqui levanta exceção para fora.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta

from jarvis import config
from jarvis.brain import gate
from jarvis.tasks import cards, sincronia
from jarvis.tasks.repository import (
    TaskRepository, Tarefa, normalizar_duracao, normalizar_prazo,
    normalizar_prioridade,
)

ACOES = ("criar", "listar_hoje", "concluir", "desfazer")
_INDEFINIDO = {"indefinido", "sem prazo", "sem_prazo", "depois", "nao sei", "não sei"}
_DIAS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")

# Dependências trocáveis nos testes.
_repo: TaskRepository | None = None
_undo = None        # módulo core.undo
_confirm = None     # módulo core.confirm (usado pelo portão)
_agora = None       # () -> datetime com fuso


@dataclass
class _Rascunho:
    titulo: str
    prazo: str | None = None
    prioridade: str | None = None
    duracao_min: int | None = None
    projeto: str | None = None
    contexto: str | None = None
    prazo_indefinido: bool = False
    resumo_mostrado: bool = False
    faltas: list[str] = field(default_factory=list)


_rascunho: _Rascunho | None = None
_lock = threading.Lock()


# ── Dependências ─────────────────────────────────────────────────────────────

def _repositorio() -> TaskRepository:
    global _repo
    if _repo is None:
        _repo = TaskRepository()
    return _repo


def _pilha_undo():
    if _undo is not None:
        return _undo
    from core import undo  # noqa: PLC0415 — só existe dentro do Mark
    return undo


def _agora_sp() -> datetime:
    return _agora() if _agora else datetime.now(config.fuso())


def reset() -> None:
    """Esquece o rascunho (testes e troca de assunto)."""
    global _rascunho
    with _lock:
        _rascunho = None


# ── Texto em português ──────────────────────────────────────────────────────

def _fmt_hora(dt: datetime) -> str:
    return f"{dt.hour}h" if dt.minute == 0 else f"{dt.hour}h{dt.minute:02d}"


def fmt_prazo(prazo: str | None, hoje: date | None = None) -> str:
    """'hoje às 14h', 'amanhã', 'sexta, 31/10 às 9h30', 'sem prazo'."""
    if not prazo:
        return "sem prazo"
    hoje = hoje or _agora_sp().date()
    tem_hora = len(prazo) > 10
    dt = datetime.fromisoformat(prazo) if tem_hora else None
    dia = dt.date() if dt else date.fromisoformat(prazo)
    delta = (dia - hoje).days
    if delta == 0:
        texto = "hoje"
    elif delta == 1:
        texto = "amanhã"
    elif delta == -1:
        texto = "ontem"
    elif 1 < delta < 7:
        texto = f"{_DIAS[dia.weekday()]}, {dia:%d/%m}"
    else:
        texto = f"{dia:%d/%m/%Y}" if dia.year != hoje.year else f"{dia:%d/%m}"
    return f"{texto} às {_fmt_hora(dt)}" if dt else texto


def fmt_duracao(minutos: int | None) -> str:
    if not minutos:
        return "duração não definida"
    h, m = divmod(int(minutos), 60)
    if h and m:
        return f"{h}h{m:02d}"
    if h:
        return "1 hora" if h == 1 else f"{h} horas"
    return f"{m} minutos"


def _fmt_prioridade(p: str | None) -> str:
    return {"alta": "prioridade alta", "media": "prioridade média",
            "baixa": "prioridade baixa"}.get(p or "", "sem prioridade")


def _resumo(r: _Rascunho) -> str:
    partes = [f"“{r.titulo}”", fmt_prazo(r.prazo), _fmt_prioridade(r.prioridade),
              fmt_duracao(r.duracao_min)]
    if r.projeto:
        partes.append(f"projeto {r.projeto}")
    return ", ".join(partes)


def _mostrar(player, card: tuple[str, str]) -> None:
    """Card na tela (M1B). Sem tela, ou se ela falhar, a voz segue igual."""
    if player is not None:
        try:
            player.show_content(*card)
        except Exception:
            pass


def _card_rascunho(r: _Rascunho, faltas: list[str] | None = None):
    campos = {"Prazo": fmt_prazo(r.prazo) if r.prazo else None,
              "Prioridade": _fmt_prioridade(r.prioridade).removeprefix("prioridade ")
              if r.prioridade else None,
              "Duração": fmt_duracao(r.duracao_min) if r.duracao_min else None}
    if r.projeto:
        campos["Projeto"] = r.projeto
    return cards.rascunho(r.titulo, campos, sincronia.destinos(r.prazo), faltas or [])


def _fmt_tarefa(t: Tarefa) -> str:
    return f"{t.titulo} ({fmt_prazo(t.prazo)}, {_fmt_prioridade(t.prioridade)})"


# ── Ações ────────────────────────────────────────────────────────────────────

def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _criar(p: dict, player=None) -> str:
    global _rascunho
    titulo = (p.get("titulo") or "").strip()

    with _lock:
        r = _rascunho
        if titulo and (r is None or titulo.lower() != r.titulo.lower()):
            r = _Rascunho(titulo=titulo)          # assunto novo
        if r is None:
            return ("Falta o principal: o que é a tarefa? Pergunte ao usuário "
                    "em uma frase curta.")
        antes = r

        # campo -> como pedir de novo, quando o valor veio mas não serve
        erros: dict[str, str] = {}
        prazo = p.get("prazo")
        if not _vazio(prazo):
            if str(prazo).strip().lower() in _INDEFINIDO:
                r = replace(r, prazo=None, prazo_indefinido=True)
            else:
                try:
                    r = replace(r, prazo=normalizar_prazo(prazo), prazo_indefinido=False)
                except ValueError:
                    erros["prazo"] = "prazo (não entendi a data; peça dia e hora)"
        if not _vazio(p.get("prioridade")):
            try:
                r = replace(r, prioridade=normalizar_prioridade(p["prioridade"]))
            except ValueError:
                erros["prioridade"] = "prioridade (alta, média ou baixa)"
        if not _vazio(p.get("duracao_min")):
            try:
                r = replace(r, duracao_min=normalizar_duracao(p["duracao_min"]))
            except (TypeError, ValueError):
                erros["duração"] = "duração (em minutos)"
        for campo in ("projeto", "contexto"):
            if not _vazio(p.get(campo)):
                r = replace(r, **{campo: str(p[campo]).strip()})

        # O "sim" vale para o resumo que o usuário ouviu. Mudou algo, novo resumo.
        if any(getattr(r, c) != getattr(antes, c) for c in
               ("prazo", "prioridade", "duracao_min", "projeto", "contexto")):
            r = replace(r, resumo_mostrado=False)

        # Prazo indefinido de novo, depois de já termos perguntado: caixa de entrada.
        if r.prazo_indefinido and "prazo" in r.faltas:
            _rascunho = None
            texto = r.titulo + (f" — {r.contexto}" if r.contexto else "")
            item = _repositorio().adicionar_inbox(texto)
            _registrar_undo(f"anotei na caixa de entrada: {r.titulo}",
                            lambda: _desfazer_inbox(item.id))
            return (f"Sem prazo definido, “{r.titulo}” foi para a caixa de "
                    f"entrada para decidir depois. Diga isso ao usuário em uma "
                    f"frase.")

        # Valor que veio e não serve também é pedido de novo, mesmo que o
        # rascunho já tivesse um válido: o usuário quis mudar.
        faltas = [n for n, v in (("prazo", r.prazo), ("prioridade", r.prioridade),
                                 ("duração", r.duracao_min)) if v is None or n in erros]
        if faltas:
            pedir = [erros.get(f, f) for f in faltas]
            r = replace(r, faltas=faltas, resumo_mostrado=False)
            _rascunho = r
            _mostrar(player, _card_rascunho(r, faltas))
            extra = (" O usuário adiou o prazo; pergunte quando ele quer fazer, "
                     "e se ele mantiver indefinido chame de novo com "
                     "prazo='indefinido'.") if r.prazo_indefinido else ""
            return (f"Tarefa “{r.titulo}” anotada como rascunho, ainda não salva. "
                    f"Pergunte ao usuário, em uma frase curta, só: "
                    f"{', '.join(pedir)}.{extra} Depois chame de novo com o que "
                    f"ele responder.")

        if not (p.get("confirmado") is True and r.resumo_mostrado):
            _rascunho = replace(r, resumo_mostrado=True, faltas=[])
            _mostrar(player, _card_rascunho(r))
            return (f"Resumo para o usuário aprovar: {_resumo(r)}. Ainda NÃO foi "
                    f"salva.{sincronia.destino(r.prazo)} Diga o resumo em uma "
                    f"frase e pergunte se pode salvar. Se ele disser sim, chame "
                    f"de novo com confirmado=true.")

        _rascunho = None

    t = _repositorio().adicionar(
        r.titulo, descricao=r.contexto, prazo=r.prazo, prioridade=r.prioridade,
        duracao_min=r.duracao_min, projeto=r.projeto,
    )
    _registrar_undo(f"criei a tarefa: {t.titulo}", lambda: _desfazer_criar(t.id))
    destinos = sincronia.depois_de_salvar(_repositorio(), t, player,
                                          hoje=_agora_sp().date())
    return (f"Salva: {_fmt_tarefa(t)}.{destinos} Confirme ao usuário em poucas "
            f"palavras, dizendo onde ficou; ele pode dizer 'desfaz' para remover.")


def _listar_hoje(p: dict, player=None) -> str:
    repo = _repositorio()
    tarefas = repo.listar_dia(_agora_sp().date())
    inbox = len(repo.listar_inbox())
    _mostrar(player, cards.lista_do_dia(tarefas, _agora_sp(), inbox))
    if not tarefas:
        texto = "Nenhuma tarefa com prazo para hoje."
    else:
        linhas = "; ".join(f"{i}. {_fmt_tarefa(t)} [id {t.id}]"
                           for i, t in enumerate(tarefas, 1))
        texto = f"{len(tarefas)} tarefa(s) para hoje: {linhas}. O card está na tela."
    if inbox:
        texto += f" Há {inbox} item(ns) na caixa de entrada sem prazo."
    return texto + " Resuma para o usuário, sem ler os ids."


def _concluir(p: dict, player=None) -> str:
    repo = _repositorio()
    alvo = None
    if not _vazio(p.get("tarefa_id")):
        try:
            alvo = repo.obter(int(p["tarefa_id"]))
        except (TypeError, ValueError):
            alvo = None
    if alvo is None and not _vazio(p.get("titulo")):
        busca = str(p["titulo"]).strip().lower()
        hoje = repo.listar_dia(_agora_sp().date())
        candidatas = [t for t in hoje if busca in t.titulo.lower()]
        if len(candidatas) > 1:
            nomes = "; ".join(f"{t.titulo} [id {t.id}]" for t in candidatas)
            return (f"Mais de uma tarefa combina: {nomes}. Pergunte ao usuário "
                    f"qual delas.")
        alvo = candidatas[0] if candidatas else None
    if alvo is None or alvo.status != "aberta":
        return ("Não encontrei essa tarefa aberta para hoje. Pergunte ao "
                "usuário qual é, ou liste as de hoje.")
    feita = repo.concluir(alvo.id)
    _registrar_undo(f"concluí a tarefa: {feita.titulo}",
                    lambda: _desfazer_concluir(feita.id))
    trello_txt = sincronia.mover(feita, "feito")
    _mostrar(player, cards.concluida(feita, trello_txt.replace(" no Trello", "")))
    return (f"Concluída: {feita.titulo}.{trello_txt} Confirme ao usuário em "
            f"poucas palavras.")


def _desfazer(p: dict, player=None) -> str:
    try:
        return _pilha_undo().undo_last()
    except Exception as e:
        return f"Não consegui desfazer: {e}"


# ── Desfazer ────────────────────────────────────────────────────────────────

def _registrar_undo(rotulo: str, fn) -> None:
    try:
        _pilha_undo().push_undo(rotulo, fn)
    except Exception as e:     # sem desfazer, mas a ação já aconteceu
        print(f"[JarvisTarefas] desfazer não registrado: {e}")


def _desfazer_criar(tarefa_id: int) -> str:
    t = _repositorio().apagar(tarefa_id)
    if not t:
        return "A tarefa já não existia."
    return f"Tarefa removida: {t.titulo}.{sincronia.arquivar(t)}"


def _desfazer_concluir(tarefa_id: int) -> str:
    t = _repositorio().reabrir(tarefa_id)
    if not t:
        return "A tarefa já não existia."
    return f"Tarefa reaberta: {t.titulo}.{sincronia.mover(t, 'a_fazer')}"


def _desfazer_inbox(item_id: int) -> str:
    ok = _repositorio().apagar_inbox(item_id)
    return "Item removido da caixa de entrada." if ok else "O item já não existia."


# ── Entrada ─────────────────────────────────────────────────────────────────

_HANDLERS = {"criar": _criar, "listar_hoje": _listar_hoje,
             "concluir": _concluir, "desfazer": _desfazer}


def handle(parameters: dict, player=None) -> str:
    """Ponto de entrada da ferramenta. Devolve a frase que o modelo vai falar."""
    try:
        p = dict(parameters or {})
        acao = str(p.get("acao") or "criar").strip().lower()
        p["acao"] = acao
        if acao not in _HANDLERS:
            return f"Ação '{acao}' desconhecida. Use uma destas: {', '.join(ACOES)}."
        # Tarefa 5: o que a política marcar como irreversível espera o CONFIRM.
        pendente = gate.guard("jarvis_tarefas", p, lambda: _HANDLERS[acao](p, player),
                              confirm=_confirm)
        if pendente is not None:
            return pendente
        resposta = _HANDLERS[acao](p, player)
        if player is not None:
            try:
                player.write_log(f"JARVIS: tarefas/{acao}")
            except Exception:
                pass
        return resposta
    except Exception as e:
        return f"Falha na ferramenta de tarefas: {e}. Nada foi salvo."
