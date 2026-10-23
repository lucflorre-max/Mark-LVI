"""Tarefa 4: captura de tarefa por voz (jarvis/tasks/service.py)."""

from datetime import datetime

import pytest

from jarvis import config
from jarvis.tasks import service
from jarvis.tasks.repository import TaskRepository

AGORA = datetime(2026, 10, 23, 13, 0, tzinfo=config.fuso())   # sexta-feira


class FakeUndo:
    """Imita core.undo: pilha simples."""

    def __init__(self):
        self.pilha = []

    def push_undo(self, label, fn):
        self.pilha.append((label, fn))

    def undo_last(self):
        if not self.pilha:
            return "There is nothing to undo."
        label, fn = self.pilha.pop()
        return f"Undone: {label}. {fn()}"


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    repo = TaskRepository(tmp_path / "t.db")
    undo = FakeUndo()
    monkeypatch.setattr(service, "_repo", repo)
    monkeypatch.setattr(service, "_undo", undo)
    monkeypatch.setattr(service, "_agora", lambda: AGORA)
    service.reset()
    yield repo, undo
    service.reset()


COMPLETA = {"acao": "criar", "titulo": "Configurar o roteador da secretaria",
            "prazo": "2026-10-24T14:00", "prioridade": "média", "duracao_min": 60}


# ── criar ───────────────────────────────────────────────────────────────────

def test_completa_mostra_resumo_e_nao_salva(ctx):
    repo, _ = ctx
    out = service.handle(COMPLETA)
    assert "Resumo" in out and "NÃO foi salva" in out
    assert "amanhã às 14h" in out
    assert "prioridade média" in out and "1 hora" in out
    assert repo.listar_dia("2026-10-24") == []


def test_sim_salva_e_registra_desfazer(ctx):
    repo, undo = ctx
    service.handle(COMPLETA)
    out = service.handle({"acao": "criar", "confirmado": True})
    assert out.startswith("Salva:")
    [t] = repo.listar_dia("2026-10-24")
    assert t.titulo == "Configurar o roteador da secretaria"
    assert t.prazo == "2026-10-24T14:00:00-03:00"
    assert t.prioridade == "media" and t.duracao_min == 60
    assert undo.pilha[-1][0] == "criei a tarefa: Configurar o roteador da secretaria"


def test_confirmado_de_primeira_nao_pula_o_resumo(ctx):
    repo, _ = ctx
    out = service.handle({**COMPLETA, "confirmado": True})
    assert "Resumo" in out
    assert repo.listar_dia("2026-10-24") == []


def test_pergunta_so_o_que_falta(ctx):
    repo, _ = ctx
    out = service.handle({"acao": "criar", "titulo": "Ligar para o técnico",
                          "prioridade": "alta"})
    assert "prazo" in out and "duração" in out
    assert "prioridade" not in out.split("só:")[1]
    # A resposta seguinte traz só o que faltava; o resto vem do rascunho.
    out = service.handle({"acao": "criar", "prazo": "2026-10-23T16:00",
                          "duracao_min": 15})
    assert "Resumo" in out and "hoje às 16h" in out and "prioridade alta" in out
    out = service.handle({"acao": "criar", "confirmado": True})
    assert out.startswith("Salva:")
    assert [t.titulo for t in repo.listar_dia("2026-10-23")] == ["Ligar para o técnico"]


def test_sem_titulo_pergunta_o_que_e(ctx):
    assert "o que é a tarefa" in service.handle({"acao": "criar"})


def test_valor_invalido_e_pedido_de_novo(ctx):
    out = service.handle({**COMPLETA, "prioridade": "urgentíssima"})
    assert "prioridade (alta, média ou baixa)" in out
    out = service.handle({**COMPLETA, "prazo": "amanhã às duas"})
    assert "não entendi a data" in out


def test_mudanca_no_resumo_exige_novo_sim(ctx):
    repo, _ = ctx
    service.handle(COMPLETA)
    # Mudou o horário junto com o "sim": o usuário não ouviu esse resumo.
    out = service.handle({"acao": "criar", "prazo": "2026-10-24T15:00",
                          "confirmado": True})
    assert "Resumo" in out and "amanhã às 15h" in out
    assert repo.listar_dia("2026-10-24") == []
    out = service.handle({"acao": "criar", "confirmado": True})
    assert out.startswith("Salva:")
    assert repo.listar_dia("2026-10-24")[0].prazo.startswith("2026-10-24T15:00")


def test_repetir_os_mesmos_campos_com_sim_salva(ctx):
    repo, _ = ctx
    service.handle(COMPLETA)
    # O modelo costuma reenviar tudo junto com confirmado=true.
    assert service.handle({**COMPLETA, "confirmado": True}).startswith("Salva:")
    assert len(repo.listar_dia("2026-10-24")) == 1


def test_titulo_novo_comeca_outro_rascunho(ctx):
    service.handle(COMPLETA)
    out = service.handle({"acao": "criar", "titulo": "Outra coisa"})
    assert "Outra coisa" in out and "prazo" in out


def test_depois_eu_vejo_pergunta_prazo_e_vai_para_inbox(ctx):
    repo, undo = ctx
    out = service.handle({"acao": "criar", "titulo": "Ver orçamento do projetor",
                          "prazo": "indefinido", "prioridade": "baixa",
                          "duracao_min": 30})
    assert "prazo" in out and "prazo='indefinido'" in out
    assert repo.listar_inbox() == []
    out = service.handle({"acao": "criar", "prazo": "indefinido"})
    assert "caixa de entrada" in out
    [item] = repo.listar_inbox()
    assert item.texto == "Ver orçamento do projetor"
    assert undo.pilha[-1][0].startswith("anotei na caixa de entrada")


def test_depois_eu_vejo_mas_responde_um_prazo(ctx):
    repo, _ = ctx
    service.handle({"acao": "criar", "titulo": "Ver orçamento", "prazo": "depois",
                    "prioridade": "baixa", "duracao_min": 30})
    out = service.handle({"acao": "criar", "prazo": "2026-10-27"})
    assert "Resumo" in out and "terça, 27/10" in out
    assert repo.listar_inbox() == []


# ── listar_hoje ─────────────────────────────────────────────────────────────

def test_listar_hoje(ctx):
    repo, _ = ctx
    repo.adicionar("Tarde", prazo="2026-10-23T15:00", prioridade="alta")
    repo.adicionar("Manhã", prazo="2026-10-23T09:30")
    repo.adicionar("Amanhã", prazo="2026-10-24T09:00")
    repo.adicionar_inbox("solto")
    out = service.handle({"acao": "listar_hoje"})
    assert out.index("Manhã") < out.index("Tarde")
    assert "Amanhã" not in out
    assert "hoje às 9h30" in out
    assert "1 item(ns) na caixa de entrada" in out


def test_listar_hoje_vazio(ctx):
    assert "Nenhuma tarefa" in service.handle({"acao": "listar_hoje"})


# ── concluir / desfazer ─────────────────────────────────────────────────────

def test_concluir_por_titulo_e_desfazer(ctx):
    repo, _ = ctx
    t = repo.adicionar("Configurar o roteador", prazo="2026-10-23T14:00")
    out = service.handle({"acao": "concluir", "titulo": "roteador"})
    assert out.startswith("Concluída")
    assert repo.obter(t.id).status == "concluida"
    out = service.handle({"acao": "desfazer"})
    assert "reaberta" in out
    assert repo.obter(t.id).status == "aberta"


def test_concluir_por_id(ctx):
    repo, _ = ctx
    t = repo.adicionar("Qualquer", prazo="2026-10-23")
    assert service.handle({"acao": "concluir", "tarefa_id": t.id}).startswith("Concluída")


def test_concluir_ambiguo_pergunta(ctx):
    repo, _ = ctx
    repo.adicionar("Roteador da secretaria", prazo="2026-10-23")
    repo.adicionar("Roteador da biblioteca", prazo="2026-10-23")
    out = service.handle({"acao": "concluir", "titulo": "roteador"})
    assert "Mais de uma" in out
    assert all(t.status == "aberta" for t in repo.listar_dia("2026-10-23"))


def test_concluir_inexistente(ctx):
    assert "Não encontrei" in service.handle({"acao": "concluir", "titulo": "nada"})


def test_desfazer_criacao_remove_a_tarefa(ctx):
    repo, _ = ctx
    service.handle(COMPLETA)
    service.handle({"acao": "criar", "confirmado": True})
    out = service.handle({"acao": "desfazer"})
    assert "removida" in out
    assert repo.listar_dia("2026-10-24") == []


def test_desfazer_sem_nada(ctx):
    assert "nothing to undo" in service.handle({"acao": "desfazer"})


# ── texto ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("prazo, esperado", [
    (None, "sem prazo"),
    ("2026-10-23", "hoje"),
    ("2026-10-24T14:00:00-03:00", "amanhã às 14h"),
    ("2026-10-27T09:30:00-03:00", "terça, 27/10 às 9h30"),
    ("2026-11-15", "15/11"),
    ("2027-01-05", "05/01/2027"),
])
def test_fmt_prazo(prazo, esperado):
    assert service.fmt_prazo(prazo, hoje=AGORA.date()) == esperado


@pytest.mark.parametrize("minutos, esperado", [
    (None, "duração não definida"), (15, "15 minutos"), (60, "1 hora"),
    (90, "1h30"), (120, "2 horas"),
])
def test_fmt_duracao(minutos, esperado):
    assert service.fmt_duracao(minutos) == esperado


def test_erro_interno_nao_vaza_excecao(ctx, monkeypatch):
    repo, _ = ctx
    monkeypatch.setattr(repo, "listar_dia", lambda *a, **k: 1 / 0)
    assert "Falha na ferramenta" in service.handle({"acao": "listar_hoje"})
