from datetime import date, datetime, timedelta

import pytest

from jarvis import config
from jarvis.tasks.repository import (
    TaskRepository, normalizar_duracao, normalizar_prazo, normalizar_prioridade,
)


@pytest.fixture
def repo(tmp_path):
    return TaskRepository(tmp_path / "teste.db")


# ── Normalização ─────────────────────────────────────────────────────────────

def test_prazo_sem_fuso_vira_sao_paulo():
    assert normalizar_prazo("2026-10-24T14:00") == "2026-10-24T14:00:00-03:00"


def test_prazo_com_outro_fuso_e_convertido():
    assert normalizar_prazo("2026-10-24T17:00:00+00:00") == "2026-10-24T14:00:00-03:00"


def test_prazo_so_com_data():
    assert normalizar_prazo("2026-10-24") == "2026-10-24"
    assert normalizar_prazo(date(2026, 10, 24)) == "2026-10-24"


def test_prazo_vazio_e_invalido():
    assert normalizar_prazo(None) is None
    assert normalizar_prazo("") is None
    with pytest.raises(ValueError):
        normalizar_prazo("amanhã às duas")


@pytest.mark.parametrize("entrada, saida", [
    ("Alta", "alta"), ("média", "media"), ("MEDIA", "media"), (" baixa ", "baixa"),
    (None, None), ("", None),
])
def test_prioridade(entrada, saida):
    assert normalizar_prioridade(entrada) == saida


def test_prioridade_invalida():
    with pytest.raises(ValueError):
        normalizar_prioridade("urgente")


def test_duracao():
    assert normalizar_duracao("60") == 60
    assert normalizar_duracao(None) is None
    with pytest.raises(ValueError):
        normalizar_duracao(0)


# ── adicionar / obter ───────────────────────────────────────────────────────

def test_adicionar_completa(repo):
    t = repo.adicionar("Configurar o roteador da secretaria",
                       prazo="2026-10-24T14:00", prioridade="média",
                       duracao_min=60, projeto="Escola")
    assert t.id == 1
    assert t.titulo == "Configurar o roteador da secretaria"
    assert t.prazo == "2026-10-24T14:00:00-03:00"
    assert t.prioridade == "media"
    assert t.duracao_min == 60
    assert t.status == "aberta"
    assert t.origem == "voz"
    assert t.criado_em.endswith("-03:00")
    assert repo.obter(t.id) == t


def test_adicionar_sem_titulo_falha(repo):
    with pytest.raises(ValueError):
        repo.adicionar("   ")


def test_projeto_reaproveitado_sem_diferenciar_maiusculas(repo):
    a = repo.adicionar("A", projeto="Escola")
    b = repo.adicionar("B", projeto="escola")
    assert a.projeto_id == b.projeto_id is not None
    assert repo.projeto_id("ESCOLA", criar=False) == a.projeto_id
    assert repo.projeto_id("Outro", criar=False) is None


def test_obter_inexistente(repo):
    assert repo.obter(999) is None


# ── listar por dia ──────────────────────────────────────────────────────────

def test_listar_dia_ordem_e_filtro(repo):
    repo.adicionar("Só data", prazo="2026-10-24")
    repo.adicionar("Tarde", prazo="2026-10-24T15:00")
    repo.adicionar("Manhã", prazo="2026-10-24T09:00")
    repo.adicionar("Outro dia", prazo="2026-10-25T09:00")
    repo.adicionar("Sem prazo")
    titulos = [t.titulo for t in repo.listar_dia(date(2026, 10, 24))]
    assert titulos == ["Manhã", "Tarde", "Só data"]


def test_listar_dia_padrao_e_hoje(repo):
    hoje = datetime.now(config.fuso()).date()
    repo.adicionar("Hoje", prazo=hoje)
    repo.adicionar("Amanhã", prazo=hoje + timedelta(days=1))
    assert [t.titulo for t in repo.listar_dia()] == ["Hoje"]


def test_listar_dia_esconde_concluidas(repo):
    t = repo.adicionar("Feita", prazo="2026-10-24")
    repo.concluir(t.id)
    assert repo.listar_dia("2026-10-24") == []
    assert len(repo.listar_dia("2026-10-24", incluir_concluidas=True)) == 1


# ── concluir / reabrir ──────────────────────────────────────────────────────

def test_concluir_e_reabrir(repo):
    t = repo.adicionar("Tarefa")
    assert repo.concluir(t.id).status == "concluida"
    assert repo.reabrir(t.id).status == "aberta"


def test_concluir_inexistente(repo):
    assert repo.concluir(42) is None


# ── adiar ───────────────────────────────────────────────────────────────────

def test_adiar(repo):
    t = repo.adicionar("Tarefa", prazo="2026-10-24T14:00")
    adiada = repo.adiar(t.id, "2026-10-27T10:00")
    assert adiada.prazo == "2026-10-27T10:00:00-03:00"
    assert repo.listar_dia("2026-10-24") == []
    assert [x.id for x in repo.listar_dia("2026-10-27")] == [t.id]


def test_adiar_inexistente(repo):
    assert repo.adiar(42, "2026-10-27") is None


# ── apagar ──────────────────────────────────────────────────────────────────

def test_apagar_devolve_a_tarefa(repo):
    t = repo.adicionar("Tarefa", prioridade="alta")
    assert repo.apagar(t.id) == t
    assert repo.obter(t.id) is None
    assert repo.apagar(t.id) is None


# ── caixa de entrada ────────────────────────────────────────────────────────

def test_inbox(repo):
    item = repo.adicionar_inbox("Ver isso do roteador depois")
    assert item.texto == "Ver isso do roteador depois"
    assert item.processado is False
    assert [i.id for i in repo.listar_inbox()] == [item.id]
    with pytest.raises(ValueError):
        repo.adicionar_inbox("")


# ── persistência ────────────────────────────────────────────────────────────

def test_dados_sobrevivem_a_nova_conexao(tmp_path):
    caminho = tmp_path / "teste.db"
    TaskRepository(caminho).adicionar("Persistente", prazo="2026-10-24")
    assert TaskRepository(caminho).obter(1).titulo == "Persistente"


def test_banco_padrao_fica_em_data():
    assert config.DB_PATH.parent.name == "data"


def test_nenhuma_conexao_fica_aberta(tmp_path):
    caminho = tmp_path / "teste.db"
    repo = TaskRepository(caminho)
    t = repo.adicionar("A", prazo="2026-10-24")
    repo.listar_dia("2026-10-24")
    repo.apagar(t.id)
    caminho.unlink()   # no Windows falha se alguma conexão ficou aberta
    assert not caminho.exists()
