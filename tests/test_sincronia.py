"""M2 tarefa 5: tarefa com horário → Trello + compromisso vinculado no Calendar."""

from datetime import datetime

import pytest

from jarvis import config
from jarvis.brain import gate
from jarvis.tasks import service, sincronia
from jarvis.tasks.repository import TaskRepository

AGORA = datetime(2026, 10, 23, 13, 0, tzinfo=config.fuso())   # sexta-feira


class _Undo:
    def __init__(self):
        self.pilha = []

    def push_undo(self, label, fn):
        self.pilha.append((label, fn))

    def undo_last(self):
        label, fn = self.pilha.pop()
        return fn()


class _Confirm:
    def __init__(self):
        self.pedido = None

    def pending_title(self):
        return ""

    def request(self, key, title, detail, run):
        self.pedido = (key, title, detail, run)
        return "[CONFIRMATION_PENDING] confirme na tela"

    def clicar(self):
        return self.pedido[3]()


class _Trello:
    def __init__(self, erro=None):
        self.cartoes, self.movidos, self.arquivados, self.anexos = [], [], [], []
        self.erro = erro

    def nome_lista(self, papel):
        return {"a_fazer": "A fazer", "feito": "Feito"}[papel]

    def criar_cartao(self, nome, desc="", due=None, papel="a_fazer"):
        if self.erro:
            raise self.erro
        self.cartoes.append({"nome": nome, "desc": desc, "due": due})
        return {"id": "c1", "shortUrl": "https://trello.com/c/abc"}

    def mover(self, cartao_id, papel):
        self.movidos.append((cartao_id, papel))

    def arquivar(self, cartao_id, arquivado=True):
        self.arquivados.append(cartao_id)

    def anexar_link(self, cartao_id, url, nome):
        self.anexos.append((cartao_id, url))


class _Calendario:
    def __init__(self):
        self.criados = []

    def criar(self, corpo):
        self.criados.append(corpo)
        return {"id": "ev9", "htmlLink": "https://calendar.google.com/event?eid=ev9"}

    def eventos(self, inicio, fim):
        return []


class _Player:
    def __init__(self):
        self.cards = []

    def show_content(self, titulo, texto):
        self.cards.append((titulo, texto))

    def write_log(self, texto):
        pass


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    repo, tr, cal, conf = TaskRepository(tmp_path / "t.db"), _Trello(), _Calendario(), _Confirm()
    undo = _Undo()
    monkeypatch.setattr(service, "_repo", repo)
    monkeypatch.setattr(service, "_undo", undo)
    monkeypatch.setattr(service, "_agora", lambda: AGORA)
    monkeypatch.setattr(sincronia, "_desligada", False)
    monkeypatch.setattr(sincronia, "_trello", tr)
    monkeypatch.setattr(sincronia, "_calendario", cal)
    monkeypatch.setattr(sincronia, "_confirm", conf)
    service.reset()
    gate.reset()
    yield repo, tr, cal, conf, undo
    service.reset()


COM_HORA = {"acao": "criar", "titulo": "Reunião com o fornecedor",
            "prazo": "2026-10-27T14:30", "prioridade": "alta", "duracao_min": 45}
SO_DIA = {"acao": "criar", "titulo": "Pagar o boleto", "prazo": "2026-10-24",
          "prioridade": "media", "duracao_min": 10}


def _salvar(campos, player=None):
    resumo = service.handle(campos, player=player)
    return resumo, service.handle({"acao": "criar", "confirmado": True}, player=player)


def test_resumo_diz_para_onde_vai_e_nada_sai_antes_do_sim(mundo):
    repo, tr, cal, conf, _ = mundo
    resumo = service.handle(COM_HORA)
    assert "Trello (lista A fazer)" in resumo and "Google Calendar" in resumo
    assert tr.cartoes == [] and cal.criados == [] and conf.pedido is None


def test_com_hora_cria_cartao_e_espera_o_clique_para_a_agenda(mundo):
    repo, tr, cal, conf, _ = mundo
    player = _Player()
    _, out = _salvar(COM_HORA, player)
    [t] = repo.listar_dia("2026-10-27")
    assert tr.cartoes[0]["nome"] == "Reunião com o fornecedor"
    assert tr.cartoes[0]["due"] == "2026-10-27T14:30:00-03:00"
    assert "tarefa #" in tr.cartoes[0]["desc"]
    assert t.trello_card_id == "c1" and t.trello_url == "https://trello.com/c/abc"
    assert "Trello: cartão na lista A fazer" in out and "CONFIRM" in out
    assert cal.criados == []                                  # ainda não
    key, title, detail, _ = conf.pedido
    assert key == "jarvis:jarvis_agenda"
    assert title == "Criar compromisso vinculado à tarefa"
    assert detail == "“Reunião com o fornecedor” · terça, 27/10, 14h30–15h15"
    assert player.cards[-1][0] == "TAREFA — salva; compromisso na agenda?"


def test_clique_cria_evento_vinculado_nos_dois_sentidos(mundo):
    repo, tr, cal, conf, _ = mundo
    player = _Player()
    _salvar(COM_HORA, player)
    conf.clicar()
    [corpo] = cal.criados
    [t] = repo.listar_dia("2026-10-27")
    assert corpo["start"]["dateTime"] == "2026-10-27T14:30:00-03:00"
    assert corpo["end"]["dateTime"] == "2026-10-27T15:15:00-03:00"
    assert corpo["extendedProperties"]["private"] == {
        "jarvis_tarefa_id": str(t.id), "trello_card_id": "c1"}
    assert "https://trello.com/c/abc" in corpo["description"]
    assert t.calendar_event_id == "ev9"
    assert tr.anexos == [("c1", "https://calendar.google.com/event?eid=ev9")]
    titulo, texto = player.cards[-1]
    assert titulo == "TAREFA — salva e na agenda"
    assert "Trello: https://trello.com/c/abc" in texto and "Google Calendar:" in texto


def test_so_com_dia_vai_so_para_o_trello_sem_banner(mundo):
    repo, tr, cal, conf, _ = mundo
    resumo, out = _salvar(SO_DIA)
    assert "Google Calendar" not in resumo
    assert tr.cartoes[0]["due"] == "2026-10-24T23:59:00-03:00"
    assert conf.pedido is None and cal.criados == []
    assert "Trello: cartão na lista A fazer" in out


def test_trello_fora_do_ar_a_tarefa_fica_salva_no_jarvis(mundo):
    repo, tr, cal, conf, _ = mundo
    tr.erro = ConnectionError("sem rede")
    _, out = _salvar(SO_DIA)
    assert out.startswith("Salva:") and "Não foi para o Trello (ConnectionError)" in out
    [t] = repo.listar_dia("2026-10-24")
    assert t.trello_card_id is None


def test_sem_trello_configurado_diz_que_ficou_so_no_jarvis(mundo, monkeypatch):
    monkeypatch.setattr(sincronia, "_trello", None)
    monkeypatch.setattr(sincronia.trello, "configurado", lambda: False)
    _, out = _salvar(SO_DIA)
    assert "Trello não configurado; ficou só no JARVIS." in out


def test_concluir_move_cartao_e_desfazer_devolve(mundo):
    repo, tr, cal, conf, undo = mundo
    _salvar(SO_DIA)
    [t] = repo.listar_dia("2026-10-24")
    out = service.handle({"acao": "concluir", "tarefa_id": t.id})
    assert tr.movidos == [("c1", "feito")] and "movido para Feito" in out
    undo.undo_last()
    assert tr.movidos[-1] == ("c1", "a_fazer")


def test_desfazer_criar_arquiva_cartao_e_avisa_do_compromisso(mundo):
    repo, tr, cal, conf, undo = mundo
    _salvar(COM_HORA)
    conf.clicar()
    out = undo.undo_last()
    assert tr.arquivados == ["c1"]
    assert "compromisso no Google Calendar continua" in out
    assert repo.listar_dia("2026-10-27") == []


def test_clique_depois_do_desfazer_nao_cria_evento(mundo):
    repo, tr, cal, conf, undo = mundo
    _salvar(COM_HORA)
    undo.undo_last()
    assert conf.clicar() == "Não criado: a tarefa já não existe."
    assert cal.criados == []


def test_banco_antigo_ganha_as_colunas_de_vinculo(tmp_path):
    import sqlite3
    caminho = tmp_path / "v1.db"
    conn = sqlite3.connect(caminho)
    conn.executescript("""
        CREATE TABLE tasks (id INTEGER PRIMARY KEY, titulo TEXT NOT NULL, descricao TEXT,
            prazo TEXT, prioridade TEXT, duracao_min INTEGER, projeto_id INTEGER,
            status TEXT NOT NULL DEFAULT 'aberta', origem TEXT NOT NULL DEFAULT 'voz',
            criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL);
        INSERT INTO tasks (titulo, criado_em, atualizado_em) VALUES ('antiga', 'x', 'x');
        PRAGMA user_version = 1;
    """)
    conn.close()
    repo = TaskRepository(caminho)
    t = repo.vincular(1, trello_url="https://trello.com/c/x")
    assert t.titulo == "antiga" and t.trello_url == "https://trello.com/c/x"
    with pytest.raises(ValueError):
        repo.vincular(1, titulo="hack")
