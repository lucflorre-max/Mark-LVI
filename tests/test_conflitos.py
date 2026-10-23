"""M2 tarefa 6: detectar conflitos e sugerir ajuste, sem aplicar sozinho."""

from datetime import date, datetime, timedelta, timezone

import pytest

from jarvis.brain import gate
from jarvis.calendar import agenda, service

BRT = timezone(timedelta(hours=-3), "BRT")
AGORA = datetime(2026, 10, 23, 9, 30, tzinfo=BRT)   # sexta
DIA = date(2026, 10, 27)


def _h(hora, minuto=0):
    return datetime(2026, 10, 27, hora, minuto, tzinfo=BRT)


def _ev(titulo, ini, fim, id_=""):
    return agenda.Evento(titulo, ini, fim, id=id_ or titulo)


def _api(titulo, ini, fim):
    return {"id": titulo, "summary": titulo, "start": {"dateTime": ini.isoformat()},
            "end": {"dateTime": fim.isoformat()}}


AGENDA = [_ev("Reunião", _h(14), _h(15)), _ev("Almoço", _h(12), _h(13)),
          agenda.Evento("Feriado", None, None, dia_inteiro=True, data=DIA)]


# ── Funções puras ───────────────────────────────────────────────────────────

def test_conflitos_ignora_dia_inteiro_e_encostados():
    assert [e.titulo for e in agenda.conflitos(AGENDA, _h(14, 30), _h(15, 30))] == ["Reunião"]
    assert agenda.conflitos(AGENDA, _h(15), _h(16)) == []         # começa quando o outro acaba
    assert agenda.conflitos(AGENDA, _h(13), _h(14)) == []
    assert agenda.conflitos(AGENDA, _h(14), _h(15), ignorar_id="Reunião") == []


def test_proximo_livre_pula_compromissos_seguidos():
    eventos = AGENDA + [_ev("Call", _h(15), _h(15, 40))]
    assert agenda.proximo_livre(eventos, _h(14, 30), timedelta(minutes=45)) == _h(15, 45)
    assert agenda.proximo_livre(eventos, _h(10), timedelta(hours=1)) == _h(10)


def test_proximo_livre_nao_passa_das_21h():
    eventos = [_ev("Plantão", _h(18), _h(20, 30))]
    assert agenda.proximo_livre(eventos, _h(19), timedelta(hours=1)) is None


def test_aviso_conflito_diz_com_quem_e_sugere():
    aviso = agenda.aviso_conflito(AGENDA, _h(14, 30), _h(15, 15))
    assert aviso == " — conflita com “Reunião” (14h–15h); horário livre mais próximo: 15h–15h45"
    assert agenda.aviso_conflito(AGENDA, _h(16), _h(17)) == ""


def test_card_marca_os_que_se_sobrepoem():
    eventos = [_ev("A", _h(9), _h(10)), _ev("B", _h(9, 30), _h(11)), _ev("C", _h(14), _h(15))]
    _, texto = agenda.card(eventos, DIA, AGORA)
    linhas = texto.splitlines()
    assert linhas[0].startswith("⚠ 09:00") and linhas[1].startswith("⚠ 09:30")
    assert linhas[2].startswith("14:00")
    assert linhas[-1] == "⚠ horários que se sobrepõem"


# ── Serviço da agenda ───────────────────────────────────────────────────────

class _Confirm:
    def __init__(self):
        self.pedido = None

    def pending_title(self):
        return ""

    def request(self, key, title, detail, run):
        self.pedido = (key, title, detail, run)
        return "[CONFIRMATION_PENDING] confirme na tela"


class _Cliente:
    def __init__(self, itens):
        self.itens, self.criados = itens, []

    def eventos(self, inicio, fim):
        return self.itens

    def criar(self, corpo):
        self.criados.append(corpo)
        return {"id": "x"}


class _Player:
    def __init__(self):
        self.cards = []

    def show_content(self, titulo, texto):
        self.cards.append((titulo, texto))

    def write_log(self, texto):
        pass


@pytest.fixture
def mundo(monkeypatch):
    confirm = _Confirm()
    cliente = _Cliente([_api("Reunião", _h(14), _h(15))])
    monkeypatch.setattr(service, "_agora", lambda: AGORA)
    monkeypatch.setattr(service, "_confirm", confirm)
    monkeypatch.setattr(service, "_cliente", cliente)
    monkeypatch.setattr("jarvis.config.fuso", lambda: BRT)
    monkeypatch.setattr(service, "_untrusted", lambda t: f"<<{t}>>")
    gate.reset()
    return confirm, cliente


def test_criar_em_cima_de_outro_avisa_e_sugere_sem_mudar_nada(mundo):
    confirm, cliente = mundo
    player = _Player()
    r = service.handle({"acao": "criar", "titulo": "Dentista",
                        "inicio": "2026-10-27T14:30", "duracao_min": 45}, player=player)
    assert r.startswith("[CONFIRMATION_PENDING]")
    assert "conflita com “Reunião” (14h–15h)" in r and "15h–15h45" in r
    assert "Não mude nada sozinho" in r
    _, _, detalhe, _ = confirm.pedido
    assert detalhe.endswith("— conflita com “Reunião” (14h–15h); horário livre mais próximo: 15h–15h45")
    assert "conflita" in player.cards[-1][1]
    assert cliente.criados == []                      # nada mudou, nem o horário pedido


def test_criar_em_horario_livre_nao_fala_de_conflito(mundo):
    confirm, _ = mundo
    r = service.handle({"acao": "criar", "titulo": "Dentista",
                        "inicio": "2026-10-27T16:00", "duracao_min": 30})
    assert "conflita" not in r and "conflita" not in confirm.pedido[2]


def test_agenda_fora_do_ar_nao_impede_criar(mundo, monkeypatch):
    confirm, cliente = mundo

    def falha(*a):
        raise ConnectionError

    monkeypatch.setattr(cliente, "eventos", falha)
    r = service.handle({"acao": "criar", "titulo": "Dentista", "inicio": "2026-10-27T14:30"})
    assert r.startswith("[CONFIRMATION_PENDING]") and "conflita" not in r


def test_ver_avisa_sobreposicao_e_pede_para_nao_alterar(mundo, monkeypatch):
    _, cliente = mundo
    cliente.itens = [_api("A", _h(9), _h(10)), _api("B", _h(9, 30), _h(11))]
    r = service.handle({"acao": "ver", "data": "2026-10-27"})
    assert "Horários que se sobrepõem" in r and "não altere nada" in r
