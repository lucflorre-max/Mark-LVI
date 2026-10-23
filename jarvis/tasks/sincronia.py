"""
jarvis/tasks/sincronia.py — leva a tarefa salva para o Trello e o Calendar.

M2 tarefa 5 (documento-mestre §5.1 e §18):
    1. Depois do "sim" ao resumo, a tarefa é salva no banco local e ganha um
       cartão na lista "A fazer" do Trello (o resumo já disse para onde ia).
    2. Tarefa com hora marcada ganha também um compromisso vinculado no Google
       Calendar. Agenda é da lista do clique (CLAUDE.md), então o compromisso
       espera o CONFIRM no banner; depois do clique, o evento guarda o id da
       tarefa e o link do cartão, o cartão recebe o link do evento, e o card
       da tela diz onde cada coisa ficou.
    3. Concluir move o cartão para "Feito"; desfazer arquiva o cartão ou o
       devolve para "A fazer". O compromisso na agenda nunca é apagado
       sozinho: apagar é alteração de agenda e pede confirmação.

Nada aqui levanta exceção para fora: falhou o Trello ou o Google, a tarefa
continua salva no JARVIS e a resposta diz o que ficou faltando.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from jarvis import config
from jarvis.brain import gate
from jarvis.integrations import google_auth, trello
from jarvis.tasks.repository import Tarefa, TaskRepository

# Dependências trocáveis nos testes. `_desligada` vale True nos testes que não
# tratam de sincronia (tests/conftest.py), para não tocar nas contas reais.
_trello = None        # TrelloClient
_calendario = None    # CalendarClient
_confirm = None       # módulo core.confirm (usado pelo portão)
_desligada = False


# ── Dependências ─────────────────────────────────────────────────────────────

def _cliente_trello():
    if _trello is not None:
        return _trello
    if not trello.configurado():
        return None
    return trello.TrelloClient()


def _cliente_calendario():
    if _calendario is not None:
        return _calendario
    if not google_auth.TOKEN_CALENDAR.exists():
        return None
    from jarvis.calendar.client import CalendarClient
    return CalendarClient()


def trello_ativo() -> bool:
    return not _desligada and _cliente_trello() is not None


def calendario_ativo() -> bool:
    return not _desligada and _cliente_calendario() is not None


def tem_hora(prazo: str | None) -> bool:
    return bool(prazo) and len(prazo) > 10


def _mostrar(player, titulo: str, texto: str) -> None:
    if player is not None:
        try:
            player.show_content(titulo, texto)
        except Exception:
            pass


# ── Texto ────────────────────────────────────────────────────────────────────

def destino(prazo: str | None) -> str:
    """Para o resumo antes do "sim": onde a tarefa vai ficar."""
    if _desligada:
        return ""
    lugares = ["JARVIS"]
    if trello_ativo():
        lugares.append(f"Trello (lista {_cliente_trello().nome_lista('a_fazer')})")
    if tem_hora(prazo) and calendario_ativo():
        lugares.append("compromisso vinculado no Google Calendar, que o usuário "
                       "confirma na tela")
    return " Vai ficar em: " + ", ".join(lugares) + "."


def _due(prazo: str | None) -> str | None:
    """Prazo do banco → `due` do Trello. Só com dia: fim do dia."""
    if not prazo:
        return None
    if tem_hora(prazo):
        return prazo
    return datetime.combine(date.fromisoformat(prazo), time(23, 59),
                            tzinfo=config.fuso()).isoformat()


def _desc_cartao(t: Tarefa) -> str:
    linhas = [t.descricao] if t.descricao else []
    detalhes = [f"Prioridade: {t.prioridade}" if t.prioridade else "",
                f"Duração: {t.duracao_min} min" if t.duracao_min else ""]
    linhas.append(" · ".join(d for d in detalhes if d))
    linhas.append(f"Criada pelo JARVIS (tarefa #{t.id}).")
    return "\n".join(l for l in linhas if l)


# ── Salvar nos destinos ──────────────────────────────────────────────────────

def _criar_cartao(repo: TaskRepository, t: Tarefa) -> tuple[Tarefa, str]:
    """(tarefa atualizada, frase sobre o Trello)."""
    cli = _cliente_trello()
    try:
        cartao = cli.criar_cartao(t.titulo, desc=_desc_cartao(t), due=_due(t.prazo))
    except trello.NaoConfigurado as e:
        return t, f"Não foi para o Trello: {e}"
    except Exception as e:
        return t, f"Não foi para o Trello ({type(e).__name__}); ficou só no JARVIS."
    t = repo.vincular(t.id, trello_card_id=cartao.get("id"),
                      trello_url=cartao.get("shortUrl") or cartao.get("url")) or t
    return t, f"Trello: cartão na lista {cli.nome_lista('a_fazer')}."


def _corpo_evento(t: Tarefa) -> dict:
    ini = datetime.fromisoformat(t.prazo)
    fim = ini + timedelta(minutes=t.duracao_min or 60)
    desc = [t.descricao or "", f"Tarefa do JARVIS #{t.id}."]
    if t.trello_url:
        desc.append(f"Trello: {t.trello_url}")
    privado = {"jarvis_tarefa_id": str(t.id)}
    if t.trello_card_id:
        privado["trello_card_id"] = t.trello_card_id
    return {
        "summary": t.titulo,
        "description": "\n".join(d for d in desc if d),
        "start": {"dateTime": ini.isoformat(), "timeZone": config.FUSO_NOME},
        "end": {"dateTime": fim.isoformat(), "timeZone": config.FUSO_NOME},
        "extendedProperties": {"private": privado},
    }


def linha_compromisso(t: Tarefa, hoje: date) -> str:
    from jarvis.calendar import agenda
    ini = datetime.fromisoformat(t.prazo)
    ev = agenda.Evento(t.titulo, ini, ini + timedelta(minutes=t.duracao_min or 60))
    return agenda.descrever(ev, hoje)


def _onde(t: Tarefa) -> str:
    lugares = [f"JARVIS (tarefa #{t.id})"]
    if t.trello_url:
        lugares.append(f"Trello: {t.trello_url}")
    if t.calendar_url:
        lugares.append(f"Google Calendar: {t.calendar_url}")
    return "Salva em:\n" + "\n".join(f"· {l}" for l in lugares)


def _criar_evento(repo: TaskRepository, tarefa_id: int, linha: str, player) -> str:
    """Roda depois do CONFIRM, numa thread do core.confirm."""
    t = repo.obter(tarefa_id)
    if t is None:
        _mostrar(player, "TAREFA — compromisso não criado",
                 f"{linha}\nA tarefa foi desfeita antes do clique.")
        return "Não criado: a tarefa já não existe."
    try:
        ev = _cliente_calendario().criar(_corpo_evento(t))
    except google_auth.NaoAutorizado:
        _mostrar(player, "TAREFA — compromisso não criado",
                 f"{linha}\nO acesso ao Google venceu. Rode: python -m "
                 f"jarvis.integrations.google_auth autorizar\n\n{_onde(t)}")
        return "Não criado: acesso ao Google Calendar vencido."
    except Exception as e:
        _mostrar(player, "TAREFA — compromisso não criado",
                 f"{linha}\nO Google Calendar não respondeu ({type(e).__name__}).\n\n{_onde(t)}")
        return f"Não criado: {type(e).__name__}."
    t = repo.vincular(t.id, calendar_event_id=ev.get("id"),
                      calendar_url=ev.get("htmlLink")) or t
    if t.trello_card_id and t.calendar_url:
        try:
            _cliente_trello().anexar_link(t.trello_card_id, t.calendar_url, "Google Calendar")
        except Exception:
            pass                                 # o vínculo já está no evento
    _mostrar(player, "TAREFA — salva e na agenda", f"{linha}\n\n{_onde(t)}")
    return f"Compromisso vinculado criado: {linha}"


def depois_de_salvar(repo: TaskRepository, t: Tarefa, player=None,
                     hoje: date | None = None) -> str:
    """Chamado logo depois de a tarefa ir para o banco. Devolve a frase sobre
    os destinos, para o modelo dizer onde cada item ficou."""
    if _desligada:
        return ""
    frases = []
    if trello_ativo():
        t, frase = _criar_cartao(repo, t)
        frases.append(frase)
    else:
        frases.append("Trello não configurado; ficou só no JARVIS.")

    if not (tem_hora(t.prazo) and calendario_ativo()):
        _mostrar(player, "TAREFA — salva", _onde(t))
        return " " + " ".join(frases)

    hoje = hoje or datetime.now(config.fuso()).date()
    linha = linha_compromisso(t, hoje)
    extra = aviso_conflito(t, hoje)
    _mostrar(player, "TAREFA — salva; compromisso na agenda?",
             f"{linha}{extra}\nConfirme ou cancele no aviso da tela.\n\n{_onde(t)}")
    pendente = gate.guard(
        "jarvis_agenda", {"acao": "criar", "tarefa_id": t.id},
        lambda: _criar_evento(repo, t.id, linha, player), confirm=_confirm,
        descricao=("Criar compromisso vinculado à tarefa", linha + extra))
    if pendente is None:                  # a política nunca libera agenda direto
        frases.append(_criar_evento(repo, t.id, linha, player))
    else:
        frases.append("Google Calendar: o compromisso vinculado espera o "
                      f"CONFIRM na tela ({linha}).{extra} Diga isso ao usuário. "
                      f"Retorno do banner: {pendente}")
    return " " + " ".join(frases)


def aviso_conflito(t: Tarefa, hoje: date) -> str:
    """'' sem conflito. Preenchido na M2 tarefa 6."""
    return ""


# ── Concluir e desfazer ──────────────────────────────────────────────────────

def mover(t: Tarefa, papel: str) -> str:
    """Move o cartão vinculado ('feito' ao concluir, 'a_fazer' ao reabrir)."""
    if _desligada or not t.trello_card_id or not trello_ativo():
        return ""
    cli = _cliente_trello()
    try:
        cli.mover(t.trello_card_id, papel)
    except Exception as e:
        return f" O cartão do Trello não foi movido ({type(e).__name__})."
    return f" Cartão movido para {cli.nome_lista(papel)} no Trello."


def arquivar(t: Tarefa) -> str:
    """Desfazer de criar: arquiva o cartão (reversível no Trello). O
    compromisso da agenda fica: apagar pede confirmação."""
    partes = []
    if not _desligada and t.trello_card_id and trello_ativo():
        try:
            _cliente_trello().arquivar(t.trello_card_id)
            partes.append(" Cartão arquivado no Trello.")
        except Exception as e:
            partes.append(f" O cartão do Trello não foi arquivado ({type(e).__name__}).")
    if t.calendar_event_id:
        partes.append(" O compromisso no Google Calendar continua; diga ao usuário "
                      "que pode apagá-lo pela agenda.")
    return "".join(partes)
