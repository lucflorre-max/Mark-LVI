import pytest

from jarvis.brain import gate
from jarvis.brain.gate import guard, ouvir, resposta_afirmativa


class FakeConfirm:
    """Imita core.confirm: guarda o pedido em vez de mostrar banner."""

    def __init__(self, pending=""):
        self.pending = pending
        self.requests = []

    def pending_title(self):
        return self.pending

    def request(self, key, title, detail, run):
        self.requests.append((key, title, detail, run))
        return "[CONFIRMATION_PENDING] ..."


class Relogio:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture(autouse=True)
def limpo(monkeypatch):
    rel = Relogio()
    monkeypatch.setattr(gate, "_relogio", rel)
    gate.reset()
    yield rel
    gate.reset()


# ── Clique ──────────────────────────────────────────────────────────────────

def test_acao_segura_roda_direto():
    fake = FakeConfirm()
    assert guard("open_app", {"app_name": "Notepad"}, lambda: "ok", confirm=fake) is None
    assert fake.requests == []


def test_acao_perigosa_vai_para_o_banner_sem_executar():
    fake = FakeConfirm()
    ran = []
    out = guard("send_message", {"receiver": "Ana", "message_text": "oi"},
                lambda: ran.append(1) or "enviado", confirm=fake)
    assert out.startswith("[CONFIRMATION_PENDING]")
    assert ran == []                       # nada rodou antes do clique
    key, title, detail, run = fake.requests[0]
    assert key == "jarvis:send_message"
    assert title == "Enviar mensagem"
    assert run() == "enviado"              # o clique em CONFIRM roda isto


def test_nao_substitui_banner_pendente():
    fake = FakeConfirm(pending="Enviar mensagem")
    out = guard("browser_control", {"action": "go_to", "url": "x"},
                lambda: "x", confirm=fake)
    assert out.startswith("[CONFIRMATION_BUSY]")
    assert "Enviar mensagem" in out
    assert fake.requests == []


# ── "Sim" por voz ───────────────────────────────────────────────────────────

DIGITAR = ("computer_control", {"action": "type", "text": "Teste do JARVIS"})


def test_voz_primeira_chamada_pergunta_e_nao_executa(limpo):
    fake = FakeConfirm()
    out = guard(*DIGITAR, lambda: "x", confirm=fake)
    assert out.startswith("[VOICE_CONFIRM]")
    assert "Teste do JARVIS" in out
    assert fake.requests == []             # voz não usa banner


def test_voz_sim_falado_libera(limpo):
    guard(*DIGITAR, lambda: "x")
    limpo.t += 4
    ouvir("Pode sim,")
    ouvir(" manda.")
    assert guard(*DIGITAR, lambda: "x") is None


def test_voz_modelo_nao_consegue_pular_a_resposta(limpo):
    guard(*DIGITAR, lambda: "x")
    limpo.t += 4
    # Chamou de novo sem o usuário ter falado nada: pergunta outra vez.
    assert guard(*DIGITAR, lambda: "x").startswith("[VOICE_CONFIRM]")


def test_voz_parametro_confirmado_nao_vale(limpo):
    guard(*DIGITAR, lambda: "x")
    nome, args = DIGITAR
    assert guard(nome, {**args, "confirmado": True}, lambda: "x").startswith("[VOICE_CONFIRM]")


def test_voz_nao_cancela(limpo):
    guard(*DIGITAR, lambda: "x")
    limpo.t += 4
    ouvir("não, espera")
    assert guard(*DIGITAR, lambda: "x").startswith("[VOICE_DECLINED]")
    # O pedido foi descartado: chamar de novo recomeça a pergunta.
    assert guard(*DIGITAR, lambda: "x").startswith("[VOICE_CONFIRM]")


def test_voz_fim_do_pedido_original_nao_conta_como_sim(limpo):
    guard(*DIGITAR, lambda: "x")
    limpo.t += 0.3
    ouvir("pode escrever teste")           # cauda da transcrição do pedido
    assert guard(*DIGITAR, lambda: "x").startswith("[VOICE_CONFIRM]")


def test_voz_argumentos_diferentes_perguntam_de_novo(limpo):
    guard(*DIGITAR, lambda: "x")
    limpo.t += 4
    ouvir("sim")
    out = guard("computer_control", {"action": "type", "text": "outra coisa"}, lambda: "x")
    assert out.startswith("[VOICE_CONFIRM]")


def test_voz_expira(limpo):
    guard(*DIGITAR, lambda: "x")
    limpo.t += 4
    ouvir("sim")
    limpo.t += gate.VOZ_TIMEOUT
    assert guard(*DIGITAR, lambda: "x").startswith("[VOICE_CONFIRM]")


def test_voz_nao_usa_o_banner_mesmo_com_banner_pendente(limpo):
    fake = FakeConfirm(pending="Enviar mensagem")
    assert guard(*DIGITAR, lambda: "x", confirm=fake).startswith("[VOICE_CONFIRM]")


def test_ouvir_sem_pedido_nao_faz_nada():
    ouvir("sim")                           # não levanta, não guarda
    assert gate._pedido is None


@pytest.mark.parametrize("texto", [
    "sim", "Sim.", "pode", "pode sim", "Confirma", "isso aí", "ok", "claro, faz",
    "manda ver", "Pode, pode.",
])
def test_respostas_afirmativas(texto):
    assert resposta_afirmativa(texto) is True


@pytest.mark.parametrize("texto", [
    "não", "Não, cancela", "espera", "pode cancelar", "sim, não, espera",
    "talvez", "", "the price is for you",
])
def test_respostas_que_nao_liberam(texto):
    assert resposta_afirmativa(texto) is False
