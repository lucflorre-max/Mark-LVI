"""
jarvis/brain/rotinas_service.py — regras da ferramenta jarvis_rotinas (M3 tarefa 6).

O plugin plugins/jarvis_rotinas.py só repassa a chamada para `handle()`.

    rotinas, habitos, lembretes   consulta                        direto
    habito_registrar              marca o dia como feito          direto
    rotina_criar, rotina_alterar,
    rotina_pausar, habito_criar   mudança permanente ("real")     "sim" falado

Os campos são conferidos ANTES do pedido de "sim": o que estiver errado volta
como pergunta, e o usuário só confirma algo que vai mesmo funcionar.
"""

from __future__ import annotations

import unicodedata
from datetime import date, datetime, timedelta

from jarvis import config
from jarvis.brain import gate
from jarvis.brain import habitos as hb
from jarvis.brain import lembretes as lb
from jarvis.brain import rotinas as rt
from jarvis.tasks.repository import TaskRepository

# Dependências trocáveis nos testes.
_tarefas: TaskRepository | None = None
_rotinas: rt.RotinasRepo | None = None
_agora = None              # () -> datetime com fuso
_eventos = None            # (agora) -> (eventos, aviso); padrão: o do plano do dia

_NOME_PRIO = {"alta": "alta", "media": "média", "baixa": "baixa"}


def _repo_tarefas() -> TaskRepository:
    global _tarefas
    if _tarefas is None:
        _tarefas = TaskRepository()
    return _tarefas


def _repo_rotinas() -> rt.RotinasRepo:
    """No mesmo banco das tarefas (refeito se o banco das tarefas mudar)."""
    global _rotinas
    if _rotinas is None or _rotinas.path != _repo_tarefas().path:
        _rotinas = rt.RotinasRepo(_repo_tarefas().path)
    return _rotinas


def _agora_sp() -> datetime:
    return _agora() if _agora else datetime.now(config.fuso())


def _eventos_hoje(agora: datetime):
    if _eventos is not None:
        return _eventos(agora)
    from jarvis.brain import dia_service  # noqa: PLC0415 — evita import circular
    return dia_service._eventos(agora)


def _mostrar(player, card: tuple[str, str]) -> None:
    if player is not None:
        try:
            player.show_content(*card)
        except Exception:
            pass


def _vazio(v) -> bool:
    return v is None or str(v).strip() == ""


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", str(texto).lower()).encode("ascii", "ignore").decode()


def _resumo(titulo, regra, hora, prioridade, duracao) -> str:
    partes = [f"“{titulo}” {rt.descrever_regra(regra, hora)}"]
    if prioridade:
        partes.append(f"prioridade {_NOME_PRIO[prioridade]}")
    if duracao:
        partes.append(f"{duracao} min")
    return " · ".join(partes)


# ── Rotinas ─────────────────────────────────────────────────────────────────

def _campos_rotina(p: dict, base: rt.Rotina | None = None) -> dict | str:
    """Campos normalizados, ou a pergunta a fazer."""
    try:
        if not _vazio(p.get("frequencia")):
            regra = rt.montar_regra(p["frequencia"], p.get("dias"), p.get("dia_do_mes"))
        elif base:
            regra = base.regra
        else:
            return ("Nada foi criado. Falta a frequência: todo dia, dias úteis, "
                    "semanal (quais dias) ou mensal (que dia). Pergunte só isso.")
        hora = rt.normalizar_hora(p["hora"]) if not _vazio(p.get("hora")) else (base.hora if base else None)
        prio = (rt.normalizar_prioridade(p["prioridade"]) if not _vazio(p.get("prioridade"))
                else (base.prioridade if base else None))
        dur = (rt.normalizar_duracao(p["duracao_min"]) if not _vazio(p.get("duracao_min"))
               else (base.duracao_min if base else None))
    except ValueError as e:
        return f"Nada foi alterado: {e}. Pergunte o valor certo ao usuário."
    return {"regra": regra, "hora": hora, "prioridade": prio, "duracao_min": dur}


def _rotina_criar(p: dict, player=None) -> str:
    titulo = str(p.get("titulo") or "").strip()
    if not titulo:
        return "Nada foi criado. Falta o nome da rotina. Pergunte só isso."
    campos = _campos_rotina(p)
    if isinstance(campos, str):
        return campos
    resumo = _resumo(titulo, campos["regra"], campos["hora"], campos["prioridade"],
                     campos["duracao_min"])

    def criar() -> str:
        r = _repo_rotinas().criar(titulo, campos["regra"], hora=campos["hora"],
                                  prioridade=campos["prioridade"],
                                  duracao_min=campos["duracao_min"], projeto=p.get("projeto"))
        geradas = rt.gerar(_agora_sp().date(), _repo_tarefas(), _repo_rotinas(),
                           agora=_agora_sp())
        hoje = " A de hoje já está nas tarefas." if any(g.rotina.id == r.id for g in geradas) else ""
        _mostrar(player, ("ROTINA — criada", resumo))
        return (f"Rotina criada: {resumo}. As tarefas aparecem sozinhas nos dias certos."
                f"{hoje} Confirme em poucas palavras.")

    pendente = gate.guard("jarvis_rotinas", p, criar, descricao=("Criar rotina", resumo))
    return pendente if pendente is not None else criar()


def _achar_rotina(p: dict) -> rt.Rotina | str:
    rotinas = _repo_rotinas().listar(so_ativas=False)
    if not _vazio(p.get("rotina_id")):
        try:
            achada = next((r for r in rotinas if r.id == int(p["rotina_id"])), None)
        except (TypeError, ValueError):
            achada = None
        return achada or "Não achei essa rotina. Pergunte qual é."
    busca = _sem_acento(p.get("titulo") or "")
    cand = [r for r in rotinas if busca and busca in _sem_acento(r.titulo)]
    if len(cand) == 1:
        return cand[0]
    if len(cand) > 1:
        nomes = "; ".join(f"{r.titulo} [id {r.id}]" for r in cand[:5])
        return f"Mais de uma rotina com esse nome: {nomes}. Pergunte qual e mande rotina_id."
    return "Não achei essa rotina. Pergunte qual é."


def _rotina_alterar(p: dict, player=None) -> str:
    r = _achar_rotina(p)
    if isinstance(r, str):
        return r
    campos = _campos_rotina(p, base=r)
    if isinstance(campos, str):
        return campos
    antes = _resumo(r.titulo, r.regra, r.hora, r.prioridade, r.duracao_min)
    depois = _resumo(r.titulo, campos["regra"], campos["hora"], campos["prioridade"],
                     campos["duracao_min"])
    if antes == depois:
        return "Nada para mudar: a rotina já está assim. Diga isso em uma frase."

    def alterar() -> str:
        _repo_rotinas().alterar(r.id, **campos)
        _mostrar(player, ("ROTINA — alterada", f"Antes: {antes}\nAgora: {depois}"))
        return (f"Rotina alterada: {depois}. Vale a partir da próxima vez; a tarefa "
                "de hoje, se já existe, fica como está. Confirme em poucas palavras.")

    pendente = gate.guard("jarvis_rotinas", p, alterar,
                          descricao=("Alterar rotina", f"de {antes} para {depois}"))
    return pendente if pendente is not None else alterar()


def _rotina_pausar(p: dict, player=None) -> str:
    r = _achar_rotina(p)
    if isinstance(r, str):
        return r
    if not r.ativa:
        return f"A rotina “{r.titulo}” já está pausada. Diga isso em uma frase."

    def pausar() -> str:
        _repo_rotinas().alterar(r.id, ativa=False)
        return (f"Rotina “{r.titulo}” pausada: não cria mais tarefas. As que já existem "
                "ficam. Confirme em poucas palavras.")

    pendente = gate.guard("jarvis_rotinas", p, pausar,
                          descricao=("Pausar rotina", f"“{r.titulo}” para de criar tarefas"))
    return pendente if pendente is not None else pausar()


def _listar_rotinas(p: dict, player=None) -> str:
    rotinas = _repo_rotinas().listar()
    if not rotinas:
        _mostrar(player, ("ROTINAS", "Nenhuma rotina ativa."))
        return "Nenhuma rotina ativa. Diga isso em uma frase."
    linhas = [_resumo(r.titulo, r.regra, r.hora, r.prioridade, r.duracao_min) for r in rotinas]
    _mostrar(player, ("ROTINAS", "\n".join(linhas)))
    return (f"{len(rotinas)} rotina(s): " + "; ".join(
        f"{linha} [id {r.id}]" for linha, r in zip(linhas, rotinas))
        + ". O card está na tela. Resuma sem ler os ids.")


# ── Hábitos ─────────────────────────────────────────────────────────────────

def _habito_criar(p: dict, player=None) -> str:
    nome = str(p.get("nome") or p.get("titulo") or "").strip()
    if not nome:
        return "Nada foi criado. Falta o nome do hábito. Pergunte só isso."
    if _repo_rotinas().habito_por_nome(nome):
        return f"O hábito “{nome}” já existe. Diga isso em uma frase."
    try:
        meta = int(p.get("meta_semanal") or 7)
    except (TypeError, ValueError):
        meta = 0
    if not 1 <= meta <= 7:
        return "Nada foi criado. A meta semanal vai de 1 a 7 dias. Pergunte quantos dias por semana."
    texto = "todo dia" if meta == 7 else f"{meta}× por semana"

    def criar() -> str:
        _repo_rotinas().criar_habito(nome, meta)
        _mostrar(player, ("HÁBITO — criado", f"{nome}: {texto}"))
        return (f"Hábito criado: {nome}, {texto}. Eu só lembro se a meta da semana "
                "estiver em risco, no máximo uma vez por dia. Confirme em poucas palavras.")

    pendente = gate.guard("jarvis_rotinas", p, criar,
                          descricao=("Acompanhar hábito", f"“{nome}”, {texto}"))
    return pendente if pendente is not None else criar()


def _dia(valor, hoje: date) -> date | None:
    if _vazio(valor) or str(valor).strip().lower() == "hoje":
        return hoje
    if str(valor).strip().lower() == "ontem":
        return hoje - timedelta(days=1)
    try:
        return date.fromisoformat(str(valor).strip()[:10])
    except ValueError:
        return None


def _habito_registrar(p: dict, player=None) -> str:
    nome = str(p.get("nome") or p.get("titulo") or "").strip()
    h = _repo_rotinas().habito_por_nome(nome) if nome else None
    if h is None:
        existentes = ", ".join(x.nome for x in _repo_rotinas().habitos()) or "nenhum"
        return (f"Não achei o hábito “{nome}”. Os acompanhados: {existentes}. Pergunte "
                "se ele quer criar esse (habito_criar).")
    hoje = _agora_sp().date()
    dia = _dia(p.get("data"), hoje)
    if dia is None or dia > hoje:
        return "Data inválida para marcar: use hoje, ontem ou AAAA-MM-DD até hoje."
    novo = _repo_rotinas().registrar(h.id, dia)
    prog = hb.calcular(h, _repo_rotinas().registros(h.id), hoje)
    _mostrar(player, hb.card([prog]))
    ja = "" if novo else " (já estava marcado)"
    return f"Marcado{ja}: {hb.linha(prog)}. Comente em uma frase, sem exagero."


def _progressos(hoje: date) -> list[hb.Progresso]:
    repo = _repo_rotinas()
    return [hb.calcular(h, repo.registros(h.id), hoje) for h in repo.habitos()]


def _habitos(p: dict, player=None) -> str:
    progs = _progressos(_agora_sp().date())
    _mostrar(player, hb.card(progs))
    if not progs:
        return "Nenhum hábito acompanhado ainda. Diga isso em uma frase."
    return "Hábitos da semana: " + "; ".join(hb.linha(x) for x in progs) + \
        ". O card está na tela. Resuma em poucas palavras."


# ── Lembretes ───────────────────────────────────────────────────────────────

def _lembretes(p: dict, player=None) -> str:
    agora = _agora_sp()
    rt.gerar(agora.date(), _repo_tarefas(), _repo_rotinas(), agora=agora)
    eventos, aviso = _eventos_hoje(agora)
    habitos_hoje = [x.habito.nome for x in _progressos(agora.date()) if x.precisa_hoje]
    plano = lb.planejar(_repo_tarefas().listar_abertas(ate=agora.date()), agora,
                        eventos, habitos_hoje)
    _mostrar(player, lb.card(plano, agora.date()))
    if not plano:
        return "Nenhum aviso planejado para o resto do dia. Diga isso em uma frase."
    lista = "; ".join(f"{agenda_hora(x.quando)} {x.texto()}" for x in plano)
    return (f"{len(plano)} aviso(s) planejados para hoje: {lista}." + (f" {aviso}" if aviso else "")
            + " O card está na tela. Resuma em uma frase.")


def agenda_hora(dt: datetime) -> str:
    return f"{dt.hour}h" if dt.minute == 0 else f"{dt.hour}h{dt.minute:02d}"


# ── Entrada ─────────────────────────────────────────────────────────────────

_HANDLERS = {
    "rotinas": _listar_rotinas, "rotina_criar": _rotina_criar,
    "rotina_alterar": _rotina_alterar, "rotina_pausar": _rotina_pausar,
    "habitos": _habitos, "habito_criar": _habito_criar,
    "habito_registrar": _habito_registrar, "lembretes": _lembretes,
}
ACOES = tuple(_HANDLERS)
# Estas chamam o portão por dentro, com a mudança já formatada.
_PORTAO_PROPRIO = {"rotina_criar", "rotina_alterar", "rotina_pausar", "habito_criar"}


def handle(parameters: dict, player=None) -> str:
    """Ponto de entrada da ferramenta. Devolve a frase que o modelo vai falar."""
    try:
        p = dict(parameters or {})
        acao = str(p.get("acao") or "rotinas").strip().lower()
        p["acao"] = acao
        if acao not in _HANDLERS:
            return f"Ação '{acao}' desconhecida. Use uma destas: {', '.join(ACOES)}."
        if acao not in _PORTAO_PROPRIO:
            pendente = gate.guard("jarvis_rotinas", p, lambda: _HANDLERS[acao](p, player))
            if pendente is not None:
                return pendente
        resposta = _HANDLERS[acao](p, player)
        if player is not None:
            try:
                player.write_log(f"JARVIS: rotinas/{acao}")
            except Exception:
                pass
        return resposta
    except Exception as e:
        return (f"Falha nas rotinas ({type(e).__name__}). Nada foi alterado. "
                "Diga ao usuário que não consegui agora.")
