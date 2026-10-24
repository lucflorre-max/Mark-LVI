"""M3 tarefa 4: tarefa que estourou — impacto e sugestões, sem alterar nada."""

import pytest

from jarvis.brain import dia_service, policy
from jarvis.brain import prioridade as pr
from jarvis.brain import replanejar as rpl
from jarvis.tasks.repository import TaskRepository
from tests._fabrica import AGORA, BRT, as_, evento, hoje, tarefa


def _analisar(atual, restante, outras, eventos=()):
    pts = pr.ordenar([atual, *outras], AGORA)
    return rpl.analisar(atual, restante, pts, list(eventos), AGORA)


def _sug(rp):
    return [(s.tipo, s.titulo) for s in rp.sugestoes]


ATUAL = tarefa("Relatório", prazo="2026-10-23", prioridade="alta", duracao_min=60)


@pytest.mark.parametrize("duracao, esperado", [(60, 30), (50, 30), (20, 15), (None, 15), (240, 120)])
def test_estimar_restante_metade_em_passos_de_15(duracao, esperado):
    assert rpl.estimar_restante(tarefa(duracao_min=duracao)) == esperado


def test_sem_impacto():
    rp = _analisar(ATUAL, 30, [])
    assert rp.sem_impacto and rp.sugestoes == []
    assert rp.fim_previsto == as_("10:00")
    assert rpl.card(rp)[1].endswith("O resto do dia não muda.")


def test_conflito_com_compromisso_sugere_encurtar_ou_mover_com_confirmacao():
    rp = _analisar(ATUAL, 60, [], [evento("Reunião", "10:00", "11:00")])
    assert [b.titulo for b in rp.conflitos] == ["Reunião"]
    assert rp.sugestoes[0] == rpl.Sugestao("encurtar", "Relatório",
                                           "parar às 10h para não bater com “Reunião”")
    assert rp.sugestoes[1] == rpl.Sugestao("mover", "Reunião",
                                           "para 10h30 (mudança de agenda: pede confirmação)")


def test_conflito_com_tarefa_de_hora_marcada_sugere_mover():
    ligar = tarefa("Ligar banco", prazo=hoje("10:00"), duracao_min=15)
    rp = _analisar(ATUAL, 45, [ligar])
    assert [b.titulo for b in rp.conflitos] == ["Ligar banco"]
    assert ("mover", "Ligar banco") in _sug(rp)
    mover = next(s for s in rp.sugestoes if s.tipo == "mover")
    assert mover.detalhe == "para 10h15"                      # sem aviso de agenda


def test_empurradas():
    planilha = tarefa("Planilha", prazo="2026-10-23", duracao_min=60)
    rp = _analisar(ATUAL, 30, [planilha])
    assert rp.empurradas == [("Planilha", as_("09:30"), as_("10:00"))]
    assert not rp.perdidas and not rp.conflitos


def test_perdida_que_pode_esperar_sugere_adiar():
    planilha = tarefa("Planilha", prazo="2026-10-23", prioridade="media", duracao_min=600)
    fotos = tarefa("Fotos", prazo="2026-10-23", prioridade="baixa", duracao_min=60)
    rp = _analisar(ATUAL, 60, [planilha, fotos])
    assert [p.tarefa.titulo for p in rp.perdidas] == ["Fotos"]
    assert _sug(rp) == [("adiar", "Fotos")]


def test_perdida_importante_sugere_encurtar_uma_de_classe_abaixo():
    # Fotos (baixa, mas atrasada e curta: pontua mais) entra antes; com 15 min
    # a mais no Relatório, a Planilha deixa de caber por 15 min.
    fotos = tarefa("Fotos", prazo="2026-10-22", prioridade="baixa", duracao_min=30)
    planilha = tarefa("Planilha", prazo="2026-10-23", prioridade="media", duracao_min=660)
    rp = _analisar(ATUAL, 15, [fotos, planilha])
    assert [p.tarefa.titulo for p in rp.perdidas] == ["Planilha"]
    assert rp.sugestoes == [rpl.Sugestao("encurtar", "Fotos", "em 15 min para caber “Planilha”")]


def test_perdida_importante_sugere_adiar_uma_curta_de_classe_abaixo():
    fotos = tarefa("Fotos", prazo="2026-10-22", prioridade="baixa", duracao_min=20)
    planilha = tarefa("Planilha", prazo="2026-10-23", prioridade="media", duracao_min=670)
    rp = _analisar(ATUAL, 15, [fotos, planilha])
    assert rp.sugestoes == [rpl.Sugestao("adiar", "Fotos",
                                         "para amanhã, abrindo espaço para “Planilha”")]


def test_perdida_importante_sugere_encurtar_a_tarefa_atual():
    planilha = tarefa("Planilha", prazo="2026-10-23", prioridade="media", duracao_min=310)
    rp = _analisar(ATUAL, 30, [planilha], [evento("Almoço", "15:00", "16:00"),
                                           evento("Aula", "16:00", "21:00")])
    assert rp.sugestoes == [rpl.Sugestao("encurtar", "Relatório",
                                         "parar às 9h45 para caber “Planilha”")]


def test_sem_saida_sugere_adiar_a_perdida():
    planilha = tarefa("Planilha", prazo="2026-10-23", prioridade="media", duracao_min=320)
    rp = _analisar(ATUAL, 60, [planilha], [evento("Almoço", "15:00", "16:00"),
                                           evento("Aula", "16:00", "21:00")])
    assert rp.sugestoes == [rpl.Sugestao("adiar", "Planilha", "para amanhã")]


def test_card_e_fala():
    planilha = tarefa("Planilha", prazo="2026-10-23", prioridade="media", duracao_min=600)
    fotos = tarefa("Fotos", prazo="2026-10-23", prioridade="baixa", duracao_min=60)
    rp = _analisar(ATUAL, 60, [planilha, fotos])
    titulo, texto = rpl.card(rp)
    assert titulo == "DIA — tarefa estourou"
    linhas = texto.splitlines()
    assert linhas[0] == "“Relatório” vai até 10:30."
    assert "  ✗ Fotos não cabe mais hoje" in linhas
    assert "  → Planilha passa de 09:30 para 10:30" in linhas
    assert "  Adiar Fotos: para amanhã" in linhas
    assert linhas[-1] == "Nada foi alterado."
    assert rpl.para_fala(rp).startswith("Relatório vai até 10h30. Deixa de caber hoje: Fotos.")


def test_estimativa_aparece():
    rp = _analisar(ATUAL, None, [])
    assert rp.estimado and rp.restante_min == 30
    assert "(estimativa)" in rpl.card(rp)[1]


# ── Serviço ─────────────────────────────────────────────────────────────────

class _Player:
    def __init__(self):
        self.cards = []

    def show_content(self, titulo, texto):
        self.cards.append((titulo, texto))

    def write_log(self, _):
        pass


class _SemAgenda:
    def eventos(self, ini, fim):
        return []


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = TaskRepository(tmp_path / "t.db")
    monkeypatch.setattr(dia_service, "_repo", r)
    monkeypatch.setattr(dia_service, "_cliente", _SemAgenda())
    monkeypatch.setattr(dia_service, "_agora", lambda: AGORA)
    monkeypatch.setattr("jarvis.config.fuso", lambda: BRT)
    return r


def test_sem_minutos_pergunta_quanto_falta(repo):
    repo.adicionar("Relatório mensal", prazo="2026-10-23", duracao_min=60)
    player = _Player()
    r = dia_service.handle({"acao": "estourou", "titulo": "relatorio"}, player=player)
    assert "quanto falta" in r and player.cards == []


def test_nao_sei_estima(repo):
    repo.adicionar("Relatório mensal", prazo="2026-10-23", duracao_min=60)
    player = _Player()
    r = dia_service.handle({"acao": "estourou", "titulo": "Relatório", "nao_sei": True},
                           player=player)
    assert "pela estimativa" in r and player.cards[0][0] == "DIA — tarefa estourou"


def test_com_minutos_mostra_impacto_e_nao_altera(repo):
    atual = repo.adicionar("Relatório", prazo="2026-10-23", duracao_min=60)
    outra = repo.adicionar("Planilha", prazo="2026-10-23", duracao_min=60)
    r = dia_service.handle({"acao": "estourou", "tarefa_id": atual.id,
                            "minutos_restantes": 45}, player=_Player())
    assert "<<<UNTRUSTED source=plano_do_dia>>>" in r and "nada foi alterado" in r
    assert repo.obter(atual.id) == atual and repo.obter(outra.id) == outra


def test_nome_ambiguo_pergunta_qual(repo):
    repo.adicionar("Relatório mensal")
    repo.adicionar("Relatório anual")
    r = dia_service.handle({"acao": "estourou", "titulo": "relatório", "minutos_restantes": 30})
    assert "Mais de uma tarefa" in r and "tarefa_id" in r


def test_tarefa_inexistente(repo):
    r = dia_service.handle({"acao": "estourou", "titulo": "nada disso", "minutos_restantes": 30})
    assert "Não achei" in r


def test_politica_estourou_direta():
    assert policy.nivel("jarvis_dia", {"acao": "estourou"}) == policy.DIRETO
