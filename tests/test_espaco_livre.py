"""M3 tarefa 5: espaço livre — a pendência atrasada que couber."""

import pytest

from jarvis.brain import dia_service, policy
from jarvis.brain import espaco_livre as el
from jarvis.brain import plano as pl
from jarvis.brain import prioridade as pr
from jarvis.tasks.repository import TaskRepository
from tests._fabrica import AGORA, BRT, evento, hoje, tarefa


def _sugerir(minutos, tarefas):
    return el.sugerir(minutos, pr.ordenar(tarefas, AGORA), AGORA)


def _titulo(c):
    return c.pont.tarefa.titulo if c else None


def test_so_atrasada_que_cabe():
    longa = tarefa("Longa", prazo="2026-10-20", prioridade="alta", duracao_min=60)
    curta = tarefa("Curta", prazo="2026-10-21", prioridade="baixa", duracao_min=30)
    hoje_ = tarefa("De hoje", prazo="2026-10-23", prioridade="alta", duracao_min=20)
    enc = _sugerir(40, [longa, curta, hoje_])
    assert _titulo(enc.escolha) == "Curta" and enc.alternativas == []
    assert not enc.so_de_hoje


def test_importancia_pesa():
    alta = tarefa("Alta", prazo="2026-10-21", prioridade="alta", duracao_min=30)
    baixa = tarefa("Baixa", prazo="2026-10-21", prioridade="baixa", duracao_min=30)
    assert _titulo(_sugerir(40, [baixa, alta]).escolha) == "Alta"


def test_atraso_pesa():
    recente = tarefa("Recente", prazo="2026-10-22", prioridade="media", duracao_min=30)
    antiga = tarefa("Antiga", prazo="2026-10-17", prioridade="media", duracao_min=30)
    assert _titulo(_sugerir(40, [recente, antiga]).escolha) == "Antiga"


def test_aproveitar_o_tempo_pesa():
    curtinha = tarefa("Curtinha", prazo="2026-10-21", prioridade="media", duracao_min=10)
    certinha = tarefa("Certinha", prazo="2026-10-21", prioridade="media", duracao_min=35)
    enc = _sugerir(40, [curtinha, certinha])
    assert _titulo(enc.escolha) == "Certinha"
    assert [_titulo(c) for c in enc.alternativas] == ["Curtinha"]


def test_combina_os_tres():
    # alta + 2 dias + 30/40  =  .45 + .1125 + .1875 = .75
    # média + 5 dias + 40/40 =  .27 + .225  + .25   = .745
    a = tarefa("A", prazo="2026-10-21", prioridade="alta", duracao_min=30)
    b = tarefa("B", prazo="2026-10-18", prioridade="media", duracao_min=40)
    enc = _sugerir(40, [a, b])
    assert _titulo(enc.escolha) == "A" and enc.escolha.nota == pytest.approx(0.75)
    assert enc.alternativas[0].nota == pytest.approx(0.745)


def test_no_maximo_duas_alternativas():
    ts = [tarefa(f"T{i}", prazo="2026-10-21", duracao_min=15) for i in range(5)]
    assert len(_sugerir(40, ts).alternativas) == el.ALTERNATIVAS


def test_sem_duracao_conta_30_e_avisa():
    enc = _sugerir(40, [tarefa("Sem duração", prazo="2026-10-21")])
    assert enc.escolha.minutos == 30 and enc.escolha.sem_duracao
    assert "30 min estimados" in el.card(enc, AGORA)[1]


def test_nenhuma_atrasada_cabe_sugere_a_de_hoje():
    enc = _sugerir(40, [tarefa("Atrasada longa", prazo="2026-10-21", duracao_min=90),
                        tarefa("De hoje", prazo="2026-10-23", duracao_min=30)])
    assert _titulo(enc.escolha) == "De hoje" and enc.so_de_hoje
    assert el.card(enc, AGORA)[1].startswith("Nenhuma atrasada cabe; esta é de hoje.")


def test_nada_cabe_mostra_a_atrasada_mais_curta():
    enc = _sugerir(20, [tarefa("Grande", prazo="2026-10-21", duracao_min=90),
                        tarefa("Média", prazo="2026-10-20", duracao_min=45)])
    assert enc.escolha is None and _titulo(enc.menor_atrasada) == "Média"
    assert "A atrasada mais curta: Média (45 min" in el.card(enc, AGORA)[1]


def test_card_e_fala():
    t = tarefa("Revisar contrato", prazo="2026-10-21", prioridade="alta", duracao_min=30)
    enc = _sugerir(40, [t])
    titulo, texto = el.card(enc, AGORA)
    assert titulo == "LIVRE — 40 min"
    assert texto.splitlines()[0] == ("Sugestão: Revisar contrato (30 min, atrasada há 2 dias, "
                                     "prioridade alta)")
    assert texto.endswith("Nada foi alterado.")
    assert el.para_fala(enc, AGORA).startswith("Com 40 minutos livres: Revisar contrato")


# ── Janela até o próximo compromisso ────────────────────────────────────────

def test_janela_ate_o_proximo_compromisso():
    plano = pl.montar([], [evento("Reunião", "10:15", "11:00")], AGORA)
    assert el.janela_agora(plano) == 45


def test_janela_ate_tarefa_de_hora_marcada():
    p = pr.pontuar(tarefa("Ligar", prazo=hoje("10:00"), duracao_min=15), AGORA)
    assert el.janela_agora(pl.montar([p], [], AGORA)) == 30


def test_janela_com_compromisso_agora_e_zero():
    assert el.janela_agora(pl.montar([], [evento("Reunião", "09:00", "10:00")], AGORA)) == 0


def test_janela_sem_nada_vai_ate_o_fim_do_dia():
    assert el.janela_agora(pl.montar([], [], AGORA)) == 690


# ── Serviço ─────────────────────────────────────────────────────────────────

class _Player:
    def __init__(self):
        self.cards = []

    def show_content(self, titulo, texto):
        self.cards.append((titulo, texto))

    def write_log(self, _):
        pass


class _Agenda:
    def __init__(self, itens=()):
        self.itens = list(itens)

    def eventos(self, ini, fim):
        return self.itens


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = TaskRepository(tmp_path / "t.db")
    monkeypatch.setattr(dia_service, "_repo", r)
    monkeypatch.setattr(dia_service, "_cliente", _Agenda())
    monkeypatch.setattr(dia_service, "_agora", lambda: AGORA)
    monkeypatch.setattr("jarvis.config.fuso", lambda: BRT)
    return r


def test_servico_com_minutos(repo):
    t = repo.adicionar("Revisar contrato", prazo="2026-10-21", prioridade="alta", duracao_min=30)
    player = _Player()
    r = dia_service.handle({"acao": "espaco_livre", "minutos": 40}, player=player)
    assert player.cards[0][0] == "LIVRE — 40 min" and "Revisar contrato" in r
    assert repo.obter(t.id) == t                                  # nada alterado


def test_servico_sem_minutos_usa_a_janela_ate_o_proximo_compromisso(repo, monkeypatch):
    repo.adicionar("Revisar contrato", prazo="2026-10-21", duracao_min=30)
    monkeypatch.setattr(dia_service, "_cliente", _Agenda([{
        "summary": "Reunião", "start": {"dateTime": hoje("10:15")},
        "end": {"dateTime": hoje("11:00")}}]))
    player = _Player()
    dia_service.handle({"acao": "espaco_livre"}, player=player)
    assert player.cards[0][0] == "LIVRE — 45 min"


def test_servico_com_compromisso_agora(repo, monkeypatch):
    monkeypatch.setattr(dia_service, "_cliente", _Agenda([{
        "summary": "Reunião", "start": {"dateTime": hoje("09:00")},
        "end": {"dateTime": hoje("10:00")}}]))
    assert "não há espaço livre" in dia_service.handle({"acao": "espaco_livre"})


def test_politica_espaco_livre_direto():
    assert policy.nivel("jarvis_dia", {"acao": "espaco_livre"}) == policy.DIRETO
