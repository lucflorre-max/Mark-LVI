"""M2 tarefa 3: criar compromisso só depois da confirmação (jarvis/calendar/service.py)."""

from datetime import datetime, timedelta, timezone

import pytest

from jarvis.brain import gate, policy
from jarvis.calendar import service
from jarvis.integrations.google_auth import NaoAutorizado

BRT = timezone(timedelta(hours=-3), "BRT")
AGORA = datetime(2026, 10, 23, 9, 30, tzinfo=BRT)   # sexta


class _Confirm:
    """Imita core.confirm: guarda o pedido; `clicar()` faz o papel do CONFIRM."""

    def __init__(self):
        self.pedido = None
        self.ocupado = ""

    def pending_title(self):
        return self.ocupado

    def request(self, key, title, detail, run):
        self.pedido = (key, title, detail, run)
        return "[CONFIRMATION_PENDING] confirme na tela"

    def clicar(self):
        return self.pedido[3]()


class _Cliente:
    def __init__(self, erro=None):
        self.criados, self.erro = [], erro

    def criar(self, corpo):
        if self.erro:
            raise self.erro
        self.criados.append(corpo)
        return {"id": "ev1", "htmlLink": "https://calendar.google.com/event?eid=ev1"}


class _Player:
    def __init__(self):
        self.cards = []

    def show_content(self, titulo, texto):
        self.cards.append((titulo, texto))

    def write_log(self, texto):
        pass


@pytest.fixture
def mundo(monkeypatch):
    confirm, cliente, player = _Confirm(), _Cliente(), _Player()
    monkeypatch.setattr(service, "_agora", lambda: AGORA)
    monkeypatch.setattr(service, "_confirm", confirm)
    monkeypatch.setattr(service, "_cliente", cliente)
    monkeypatch.setattr("jarvis.config.fuso", lambda: BRT)
    gate.reset()
    return confirm, cliente, player


def _criar(player, **campos):
    return service.handle({"acao": "criar", **campos}, player=player)


def test_nada_e_gravado_antes_do_clique(mundo):
    confirm, cliente, player = mundo
    r = _criar(player, titulo="Dentista", inicio="2026-10-27T14:30",
               duracao_min=45, local="Centro")
    assert r.startswith("[CONFIRMATION_PENDING]")
    assert cliente.criados == []
    key, title, detail, _ = confirm.pedido
    assert key == "jarvis:jarvis_agenda" and title == "Criar compromisso na agenda"
    assert detail == "“Dentista” · terça, 27/10, 14h30–15h15 · Centro"
    assert player.cards[-1][0] == "AGENDA — novo compromisso?"   # a mudança na tela


def test_clique_grava_e_mostra_onde_salvou(mundo):
    confirm, cliente, player = mundo
    _criar(player, titulo="Dentista", inicio="2026-10-27T14:30", fim="2026-10-27T15:00")
    assert confirm.clicar().startswith("Criado no Google Calendar")
    corpo = cliente.criados[0]
    assert corpo["summary"] == "Dentista"
    assert corpo["start"] == {"dateTime": "2026-10-27T14:30:00-03:00",
                              "timeZone": "America/Sao_Paulo"}
    assert corpo["end"]["dateTime"] == "2026-10-27T15:00:00-03:00"
    titulo, texto = player.cards[-1]
    assert titulo == "AGENDA — compromisso criado"
    assert "agenda principal" in texto and "eid=ev1" in texto


def test_cancelar_nao_grava(mundo):
    confirm, cliente, player = mundo
    _criar(player, titulo="Dentista", inicio="2026-10-27T14:30")
    confirm.pedido = None                    # CANCEL: core.confirm descarta o run
    assert cliente.criados == []


def test_duracao_padrao_aparece_no_aviso(mundo):
    confirm, cliente, player = mundo
    _criar(player, titulo="Reunião", inicio="2026-10-24T10:00")
    detail = confirm.pedido[2]
    assert "10h–11h" in detail and "duração padrão de 1h" in detail


def test_dia_inteiro(mundo):
    confirm, cliente, player = mundo
    _criar(player, titulo="Feriado", inicio="2026-11-02")
    assert "segunda, 02/11, dia inteiro" in confirm.pedido[2]
    confirm.clicar()
    assert cliente.criados[0]["start"] == {"date": "2026-11-02"}
    assert cliente.criados[0]["end"] == {"date": "2026-11-03"}


def test_horario_passado_avisa(mundo):
    confirm, _, player = mundo
    _criar(player, titulo="Café", inicio="2026-10-23T08:00")
    assert "esse horário já passou" in confirm.pedido[2]


@pytest.mark.parametrize("campos, trecho", [
    ({"inicio": "2026-10-27T14:30"}, "o título"),
    ({"titulo": "Dentista"}, "o dia e a hora"),
    ({"titulo": "Dentista", "inicio": "terça às 3"}, "inválida"),
    ({"titulo": "X", "inicio": "2026-10-27T15:00", "fim": "2026-10-27T14:00"}, "depois do início"),
])
def test_falta_ou_erro_pergunta_sem_pedir_confirmacao(mundo, campos, trecho):
    confirm, cliente, player = mundo
    r = _criar(player, **campos)
    assert trecho in r and "Nada foi criado" in r
    assert confirm.pedido is None and cliente.criados == []


def test_outro_banner_pendente_bloqueia(mundo):
    confirm, cliente, player = mundo
    confirm.ocupado = "Enviar mensagem"
    r = _criar(player, titulo="Dentista", inicio="2026-10-27T14:30")
    assert r.startswith("[CONFIRMATION_BUSY]") and confirm.pedido is None


def test_modelo_nao_pula_o_clique_com_confirmado(mundo):
    confirm, cliente, player = mundo
    r = _criar(player, titulo="Dentista", inicio="2026-10-27T14:30", confirmado=True)
    assert r.startswith("[CONFIRMATION_PENDING]") and cliente.criados == []


@pytest.mark.parametrize("erro, trecho", [(NaoAutorizado("x"), "autorizar"),
                                          (RuntimeError("token=segredo"), "RuntimeError")])
def test_falha_depois_do_clique_vai_para_o_card(mundo, monkeypatch, erro, trecho):
    confirm, _, player = mundo
    monkeypatch.setattr(service, "_cliente", _Cliente(erro=erro))
    _criar(player, titulo="Dentista", inicio="2026-10-27T14:30")
    assert confirm.clicar().startswith("Não criado")
    titulo, texto = player.cards[-1]
    assert titulo == "AGENDA — não criado" and trecho in texto and "segredo" not in texto


def test_politica_criar_pede_clique():
    assert policy.nivel("jarvis_agenda", {"acao": "criar"}) == policy.CLIQUE
    assert ("jarvis_agenda", {"acao": "criar"}) in policy.CATEGORIAS_CONFIRM["alterar agenda"]
