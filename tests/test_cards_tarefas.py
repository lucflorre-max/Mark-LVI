"""M1B: cards de tarefa na tela quando o assunto surge (jarvis/tasks/cards.py)."""

from datetime import datetime

import pytest

from jarvis import config
from jarvis.tasks import service
from jarvis.tasks.repository import TaskRepository

AGORA = datetime(2026, 10, 23, 13, 0, tzinfo=config.fuso())   # sexta-feira


class _Player:
    def __init__(self):
        self.cards = []

    def show_content(self, titulo, texto):
        self.cards.append((titulo, texto))

    def write_log(self, texto):
        pass


class _Undo:
    def push_undo(self, label, fn):
        pass


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    repo = TaskRepository(tmp_path / "t.db")
    monkeypatch.setattr(service, "_repo", repo)
    monkeypatch.setattr(service, "_undo", _Undo())
    monkeypatch.setattr(service, "_agora", lambda: AGORA)
    service.reset()
    yield repo, _Player()
    service.reset()


def test_rascunho_mostra_o_que_falta(ctx):
    _, player = ctx
    service.handle({"acao": "criar", "titulo": "Ligar para o banco",
                    "prazo": "2026-10-24T10:00"}, player=player)
    titulo, texto = player.cards[-1]
    assert titulo == "TAREFA — rascunho"
    assert "“Ligar para o banco”" in texto and "amanhã às 10h" in texto
    assert "Prioridade  ?" in texto and "Falta: prioridade, duração." in texto


def test_resumo_pede_o_sim_no_card(ctx):
    _, player = ctx
    service.handle({"acao": "criar", "titulo": "Ligar para o banco",
                    "prazo": "2026-10-24T10:00", "prioridade": "alta",
                    "duracao_min": 15}, player=player)
    titulo, texto = player.cards[-1]
    assert titulo == "TAREFA — confirmar?"
    assert "Prioridade  alta" in texto and "Duração     15 minutos" in texto
    assert texto.endswith('Diga "sim" para salvar.')


def test_lista_do_dia_em_ordem_com_atrasada_e_inbox(ctx):
    repo, player = ctx
    repo.adicionar("Reunião", prazo="2026-10-23T15:00", prioridade="alta")
    repo.adicionar("Mandar relatório", prazo="2026-10-23T09:00", prioridade="media")
    repo.adicionar("Comprar pão", prazo="2026-10-23")
    repo.adicionar_inbox("ver curso de inglês")
    out = service.handle({"acao": "listar_hoje"}, player=player)
    titulo, texto = player.cards[-1]
    assert titulo == "TAREFAS — hoje, sexta, 23/10"
    linhas = texto.splitlines()
    assert linhas[0] == "⚠ 09:00  Mandar relatório · média  (atrasada)"
    assert linhas[1] == "15:00  Reunião · alta"
    assert linhas[2] == "—      Comprar pão"
    assert linhas[-1] == "+ 1 na caixa de entrada, sem prazo"
    assert "O card está na tela" in out


def test_lista_vazia(ctx):
    _, player = ctx
    service.handle({"acao": "listar_hoje"}, player=player)
    assert player.cards[-1][1] == "Nenhuma tarefa com prazo para hoje."


def test_concluir_mostra_card(ctx):
    repo, player = ctx
    t = repo.adicionar("Pagar boleto", prazo="2026-10-23")
    service.handle({"acao": "concluir", "tarefa_id": t.id}, player=player)
    assert player.cards[-1] == ("TAREFA — concluída", "✔ Pagar boleto")


def test_tela_com_erro_nao_atrapalha_a_voz(ctx):
    class _Quebrado:
        def show_content(self, *a):
            raise RuntimeError("sem tela")

        def write_log(self, texto):
            pass

    out = service.handle({"acao": "listar_hoje"}, player=_Quebrado())
    assert "Nenhuma tarefa" in out
