from jarvis.brain.gate import guard


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
    out = guard("computer_control", {"action": "type", "text": "x"},
                lambda: "x", confirm=fake)
    assert out.startswith("[CONFIRMATION_BUSY]")
    assert "Enviar mensagem" in out
    assert fake.requests == []
