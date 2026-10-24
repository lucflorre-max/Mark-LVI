"""M3 tarefa 1: motor de prioridade (jarvis/brain/prioridade.py)."""

from datetime import datetime, timedelta, timezone

import pytest

from jarvis.brain import prioridade as pr
from jarvis.tasks.repository import TaskRepository, Tarefa

BRT = timezone(timedelta(hours=-3), "BRT")
AGORA = datetime(2026, 10, 23, 9, 30, tzinfo=BRT)   # sexta
_ids = iter(range(1, 10_000))


def tarefa(titulo="x", prazo=None, prioridade=None, duracao_min=None,
           projeto_id=None, descricao=None, status="aberta", id=None):
    return Tarefa(id=id or next(_ids), titulo=titulo, descricao=descricao, prazo=prazo,
                  prioridade=prioridade, duracao_min=duracao_min, projeto_id=projeto_id,
                  status=status, origem="voz", criado_em="", atualizado_em="")


# ── Fatores ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("prazo, esperado", [
    ("2026-10-22", 1.0),                          # ontem: atrasada
    ("2026-10-23T08:00:00-03:00", 1.0),           # hoje, hora já passou
    ("2026-10-23T11:00:00-03:00", 0.95),          # daqui a 1h30
    ("2026-10-23T17:00:00-03:00", 0.85),          # hoje, mais tarde
    ("2026-10-23", 0.8),                          # hoje, sem hora
    ("2026-10-24", 0.6),                          # amanhã
    ("2026-10-26", 0.45),                         # em 3 dias
    ("2026-10-30", 0.3),                          # em 7 dias
    ("2026-11-20", 0.15),                         # longe
    (None, 0.1),                                  # sem prazo
])
def test_fator_prazo(prazo, esperado):
    assert pr.fator_prazo(tarefa(prazo=prazo), AGORA) == esperado


def test_fator_impacto_usa_a_prioridade_dita():
    assert [pr.fator_impacto(tarefa(prioridade=p)) for p in ("alta", "media", "baixa", None)] \
        == [1.0, 0.6, 0.25, 0.6]


@pytest.mark.parametrize("minutos, esperado", [(10, 1.0), (30, 0.85), (None, 0.85),
                                               (45, 0.65), (90, 0.45), (240, 0.25)])
def test_fator_esforco_favorece_tarefa_curta(minutos, esperado):
    assert pr.fator_esforco(tarefa(duracao_min=minutos)) == esperado


def test_fator_contexto():
    t = tarefa(titulo="Relatório", projeto_id=1)
    assert pr.fator_contexto(t, None, "Trabalho") == 0.5            # nada dito: neutro
    assert pr.fator_contexto(t, "trabalho", "Trabalho") == 1.0      # combina
    assert pr.fator_contexto(t, "casa", "Trabalho") == 0.2          # outro projeto
    assert pr.fator_contexto(tarefa(titulo="Lavar louça"), "casa", None) == 0.5
    assert pr.fator_contexto(tarefa(descricao="coisa de casa"), "casa", None) == 1.0


def test_concluida_nao_conta_como_atrasada():
    assert not pr.atrasada(tarefa(prazo="2026-10-01", status="concluida"), AGORA)


def test_dias_de_atraso():
    assert pr.dias_de_atraso(tarefa(prazo="2026-10-20"), AGORA) == 3
    assert pr.dias_de_atraso(tarefa(prazo="2026-10-23T08:00:00-03:00"), AGORA) == 0
    assert pr.dias_de_atraso(tarefa(prazo="2026-10-24"), AGORA) == 0


# ── Combinação ──────────────────────────────────────────────────────────────

def test_total_e_a_soma_ponderada():
    p = pr.pontuar(tarefa(prazo="2026-10-23", prioridade="alta", duracao_min=15), AGORA)
    assert p.total == pytest.approx(0.4 * 0.8 + 0.35 * 1.0 + 0.15 * 1.0 + 0.1 * 0.5)
    assert sum(pr.PESOS.values()) == pytest.approx(1.0)


def test_prazo_e_impacto_pesam_mais_que_esforco():
    urgente_longa = tarefa("Proposta", prazo="2026-10-23T11:00:00-03:00",
                           prioridade="alta", duracao_min=180)
    rapida_sem_pressa = tarefa("Responder e-mail", prazo="2026-11-20",
                               prioridade="baixa", duracao_min=10)
    ordem = [p.tarefa.titulo for p in pr.ordenar([rapida_sem_pressa, urgente_longa], AGORA)]
    assert ordem == ["Proposta", "Responder e-mail"]


def test_atrasada_passa_na_frente_de_mesma_prioridade():
    hoje = tarefa("Hoje", prazo="2026-10-23", prioridade="media")
    atr = tarefa("Atrasada", prazo="2026-10-21", prioridade="media")
    assert pr.ordenar([hoje, atr], AGORA)[0].tarefa.titulo == "Atrasada"


def test_esforco_desempata_tarefas_parecidas():
    longa = tarefa("Longa", prazo="2026-10-24", prioridade="media", duracao_min=120)
    curta = tarefa("Curta", prazo="2026-10-24", prioridade="media", duracao_min=15)
    assert pr.ordenar([longa, curta], AGORA)[0].tarefa.titulo == "Curta"


def test_contexto_muda_a_ordem():
    trab = tarefa("Planilha", prazo="2026-10-24", prioridade="media", projeto_id=1)
    casa = tarefa("Mercado", prazo="2026-10-24", prioridade="media", projeto_id=2)
    nomes = {1: "Trabalho", 2: "Casa"}
    assert pr.ordenar([trab, casa], AGORA, "casa", nomes)[0].tarefa.titulo == "Mercado"
    assert pr.ordenar([trab, casa], AGORA, "trabalho", nomes)[0].tarefa.titulo == "Planilha"


def test_empate_total_vai_pelo_prazo_e_depois_pela_mais_antiga():
    a = tarefa("A", prazo="2026-10-24", id=20)
    b = tarefa("B", prazo="2026-10-24", id=10)
    assert [p.tarefa.id for p in pr.ordenar([a, b], AGORA)] == [10, 20]


def test_ordenar_ignora_concluidas():
    assert pr.ordenar([tarefa(status="concluida")], AGORA) == []


def test_motivo_explica_em_portugues():
    p = pr.pontuar(tarefa(prazo="2026-10-20", prioridade="alta", duracao_min=15), AGORA)
    assert p.motivo == "atrasada há 3 dias, prioridade alta, rápida (15 min)"
    p = pr.pontuar(tarefa(prazo="2026-10-23T14:00:00-03:00", duracao_min=60), AGORA)
    assert p.motivo == "prazo hoje às 14:00"
    assert pr.pontuar(tarefa(prazo="2026-11-20", duracao_min=60), AGORA).motivo == "sem urgência"


# ── Repositório ─────────────────────────────────────────────────────────────

def test_listar_abertas_inclui_atrasadas_e_sem_prazo(tmp_path):
    repo = TaskRepository(tmp_path / "t.db")
    repo.adicionar("Atrasada", prazo="2026-10-20")
    repo.adicionar("Hoje", prazo="2026-10-23T14:00")
    repo.adicionar("Sem prazo")
    repo.adicionar("Semana que vem", prazo="2026-10-30")
    feita = repo.adicionar("Feita", prazo="2026-10-23")
    repo.concluir(feita.id)
    assert [t.titulo for t in repo.listar_abertas(ate=AGORA.date())] == \
        ["Atrasada", "Hoje", "Sem prazo"]
    assert len(repo.listar_abertas()) == 4


def test_nomes_projetos(tmp_path):
    repo = TaskRepository(tmp_path / "t.db")
    t = repo.adicionar("x", projeto="Trabalho")
    assert repo.nomes_projetos() == {t.projeto_id: "Trabalho"}
