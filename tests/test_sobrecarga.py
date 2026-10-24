"""M3 tarefa 3: sobrecarga — Essencial / Importante / Pode esperar e dia realista."""

from datetime import date

import pytest

from jarvis.brain import dia_service, policy
from jarvis.brain import plano as pl
from jarvis.brain import prioridade as pr
from jarvis.brain import sobrecarga as sc
from jarvis.tasks.repository import TaskRepository
from tests._fabrica import AGORA, BRT, evento, hoje, tarefa


def _p(t):
    return pr.pontuar(t, AGORA)


# ── Classificação ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("campos, classe", [
    ({"prazo": "2026-10-23", "prioridade": "alta"}, sc.ESSENCIAL),
    ({"prazo": "2026-10-20", "prioridade": "alta"}, sc.ESSENCIAL),        # atrasada alta
    ({"prazo": hoje("14:00")}, sc.ESSENCIAL),                             # hora marcada
    ({"prazo": hoje("14:00"), "prioridade": "baixa"}, sc.PODE_ESPERAR),
    ({"prazo": "2026-10-23", "prioridade": "media"}, sc.IMPORTANTE),
    ({"prazo": "2026-10-23"}, sc.IMPORTANTE),
    ({"prazo": "2026-10-20", "prioridade": "media"}, sc.IMPORTANTE),      # atrasada média
    ({"prioridade": "alta"}, sc.IMPORTANTE),                              # sem prazo, alta
    ({"prazo": "2026-10-23", "prioridade": "baixa"}, sc.PODE_ESPERAR),
    ({"prazo": "2026-10-30", "prioridade": "media"}, sc.PODE_ESPERAR),
    ({}, sc.PODE_ESPERAR),
])
def test_classificar(campos, classe):
    assert sc.classificar(_p(tarefa(**campos)), AGORA) == classe


# ── Detecção ────────────────────────────────────────────────────────────────

def test_sem_sobrecarga_quando_tudo_que_vence_hoje_cabe():
    plano = pl.montar([_p(tarefa(prazo="2026-10-23", duracao_min=60))], [], AGORA)
    assert not sc.em_sobrecarga(plano) and sc.excesso_min(plano) == 0


def test_opcional_que_nao_cabe_nao_e_sobrecarga():
    plano = pl.montar([_p(tarefa("Enorme", duracao_min=900))], [], AGORA)
    assert plano.sem_espaco and not sc.em_sobrecarga(plano)


def test_sobrecarga_mede_o_que_falta():
    ts = [_p(tarefa(f"T{i}", prazo="2026-10-23", duracao_min=240)) for i in range(4)]
    plano = pl.montar(ts, [evento("Reunião", "10:00", "11:00")], AGORA)
    # livre 630 min: cabem 2 de 240; faltam 2 × 240
    assert sc.em_sobrecarga(plano) and sc.excesso_min(plano) == 480


# ── Proposta ────────────────────────────────────────────────────────────────

def _dia_cheio():
    # 690 min livres (9h30–21h), 780 de demanda: sobram 90 min de excesso.
    return [
        _p(tarefa("Relatório", prazo="2026-10-23", prioridade="alta", duracao_min=180)),
        _p(tarefa("Planilha", prazo="2026-10-23", prioridade="media", duracao_min=240)),
        _p(tarefa("Fotos", prazo="2026-10-23", prioridade="baixa", duracao_min=180)),
        _p(tarefa("Revisar contrato", prazo="2026-10-22", prioridade="media", duracao_min=120)),
        _p(tarefa("Dentista", prazo=hoje("17:00"), duracao_min=60)),
    ]


def test_proposta_encaixa_por_classe_e_adia_o_que_pode_esperar():
    pts = pr.ordenar([p.tarefa for p in _dia_cheio()], AGORA)
    prop = sc.propor(pts, [], AGORA)
    kept = {i.pont.tarefa.titulo for i in prop.itens if i.bloco}
    adiar = {i.pont.tarefa.titulo: i.adiar_para for i in prop.adiar}
    assert kept == {"Relatório", "Dentista", "Planilha", "Revisar contrato"}
    assert adiar == {"Fotos": date(2026, 10, 24)}           # pode esperar sai; sugestão: amanhã
    assert prop.excesso_min > 0 and prop.essencial_sem_espaco == []
    assert all(b.fim <= prop.plano.limite for b in prop.plano.blocos)
    # Encaixar no primeiro espaço deixaria a Planilha de fora (fragmentação);
    # a escolha pelo menor espaço a mantém, e os horários seguem cedo.
    assert not prop.plano.sem_espaco
    assert min(b.ini for b in prop.plano.tarefas).hour == 9


def test_pode_esperar_fica_numa_brecha_que_a_importante_nao_usaria():
    # Dentista às 17h deixa 18h–21h (180 min). A Planilha (240) não cabe lá;
    # as Fotos (180) cabem, então ficam sem tirar o lugar de ninguém.
    pts = pr.ordenar([
        tarefa("Relatório", prazo="2026-10-23", prioridade="alta", duracao_min=240),
        tarefa("Revisar contrato", prazo="2026-10-22", prioridade="media", duracao_min=120),
        tarefa("Planilha", prazo="2026-10-23", prioridade="media", duracao_min=240),
        tarefa("Fotos", prazo="2026-10-23", prioridade="baixa", duracao_min=180),
        tarefa("Dentista", prazo=hoje("17:00"), duracao_min=60),
    ], AGORA)
    prop = sc.propor(pts, [], AGORA)
    assert [i.pont.tarefa.titulo for i in prop.adiar] == ["Planilha"]
    assert prop.plano.bloco_de(next(p.tarefa.id for p in pts if p.tarefa.titulo == "Fotos")).ini.hour == 18


def test_proposta_sem_espaco_nem_para_o_essencial():
    pts = pr.ordenar([tarefa(f"E{i}", prazo="2026-10-23", prioridade="alta", duracao_min=400)
                      for i in range(3)], AGORA)
    prop = sc.propor(pts, [], AGORA)
    assert len(prop.essencial_sem_espaco) == 2
    assert "Nem o essencial cabe" in sc.card(prop)[1]


def test_proposta_nao_altera_as_tarefas():
    pts = _dia_cheio()
    antes = [p.tarefa for p in pts]
    sc.propor(pts, [], AGORA)
    assert [p.tarefa for p in pts] == antes


def test_card_e_fala():
    pts = pr.ordenar([p.tarefa for p in _dia_cheio()], AGORA)
    titulo, texto = sc.card(sc.propor(pts, [], AGORA))
    linhas = texto.splitlines()
    assert titulo == "DIA — sobrecarga"
    assert linhas[0].startswith("⚠ Faltam ")
    assert linhas.index("ESSENCIAL") < linhas.index("IMPORTANTE") < linhas.index("PODE ESPERAR")
    assert any("Fotos (sugestão: adiar)" in ln and "→ 24/10" in ln for ln in linhas)
    assert linhas[-1] == "Nada foi alterado."
    fala = sc.para_fala(sc.propor(pts, [], AGORA))
    assert fala.startswith("Sobrecarga: faltam") and "Pode esperar: Fotos" in fala


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


def test_linha_do_tempo_avisa_sobrecarga_e_ja_propoe(repo):
    for i in range(4):
        repo.adicionar(f"T{i}", prazo="2026-10-23", prioridade="media", duracao_min=240)
    player = _Player()
    r = dia_service.handle({}, player=player)
    assert player.cards[0][0] == "DIA — sobrecarga"
    assert "Sobrecarga: faltam" in r and "nada foi alterado" in r


def test_acao_sobrecarga_sem_excesso_diz_que_cabe(repo):
    repo.adicionar("Leve", prazo="2026-10-23", duracao_min=30)
    player = _Player()
    r = dia_service.handle({"acao": "sobrecarga"}, player=player)
    assert "Sem sobrecarga" in r and player.cards[0][0].startswith("DIA — hoje")


def test_servico_nao_adia_nada_sozinho(repo):
    ts = [repo.adicionar(f"T{i}", prazo="2026-10-23", duracao_min=240) for i in range(4)]
    dia_service.handle({"acao": "sobrecarga"}, player=_Player())
    assert [repo.obter(t.id).prazo for t in ts] == [t.prazo for t in ts]


def test_politica_sobrecarga_direta():
    assert policy.nivel("jarvis_dia", {"acao": "sobrecarga"}) == policy.DIRETO
