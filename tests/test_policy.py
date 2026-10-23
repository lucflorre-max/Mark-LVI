import pytest

from jarvis.brain.policy import describe, requires_confirm


@pytest.mark.parametrize("name, args", [
    ("send_message", {"receiver": "Ana", "message_text": "oi", "platform": "whatsapp"}),
    ("dev_agent", {"description": "site", "project_name": "x"}),
    ("reminder", {"date": "2026-10-24", "time": "14:00", "message": "x"}),
    ("computer_control", {"action": "type", "text": "Nós somos colorados"}),
    ("computer_control", {"action": "close_app", "app_name": "Explorer"}),
    ("computer_control", {"action": "hotkey", "keys": "alt+f4"}),
    ("computer_settings", {"action": "type_text", "value": "x"}),
    ("computer_settings", {"action": "save"}),
    ("computer_settings", {"action": "close_window"}),
    ("browser_control", {"action": "go_to", "url": "https://example.com"}),
    ("browser_control", {"action": "fill_form"}),
    ("desktop_control", {"action": "clean"}),
    ("file_controller", {"action": "delete", "path": "desktop", "name": "a.txt"}),
    ("file_controller", {"action": "write", "path": "desktop", "name": "a.txt"}),
    ("file_controller", {"action": "organize_desktop"}),
    ("code_helper", {"action": "run", "file_path": "a.py"}),
    ("code_helper", {"description": "faça um script"}),   # padrão = auto
    ("game_updater", {"action": "install"}),
])
def test_perigosas_pedem_confirmacao(name, args):
    assert requires_confirm(name, args) is True


@pytest.mark.parametrize("name, args", [
    ("open_app", {"app_name": "Notepad"}),
    ("web_search", {"query": "Internacional", "mode": "news"}),
    ("weather_report", {"city": "Porto Alegre"}),
    ("computer_control", {"action": "screenshot"}),
    ("computer_control", {"action": "scroll"}),
    ("computer_settings", {"action": "volume_down"}),
    ("browser_control", {"action": "get_text"}),
    ("desktop_control", {"action": "list"}),
    ("file_controller", {"action": "read", "path": "desktop"}),
    ("file_controller", {"action": "move", "path": "a", "destination": "b"}),
    ("code_helper", {"action": "explain", "file_path": "a.py"}),
    ("game_updater", {"action": "list"}),
])
def test_seguras_rodam_direto(name, args):
    assert requires_confirm(name, args) is False


@pytest.mark.parametrize("action", ["restart", "shutdown", "toggle_wifi"])
def test_nao_duplica_confirmacao_que_o_mark_ja_faz(action):
    assert requires_confirm("computer_settings", {"action": action}) is False


@pytest.mark.parametrize("name", ["computer_control", "computer_settings",
                                  "browser_control", "file_controller"])
def test_acao_ausente_ou_inventada_pede_confirmacao(name):
    assert requires_confirm(name, {}) is True
    assert requires_confirm(name, {"action": "faz_qualquer_coisa"}) is True
    assert requires_confirm(name, None) is True


def test_acao_com_maiusculas_e_espacos():
    assert requires_confirm("computer_control", {"action": "  Screenshot "}) is False
    assert requires_confirm("computer_control", {"action": "TYPE"}) is True


def test_describe_em_portugues_e_curto():
    title, detail = describe("send_message", {
        "receiver": "Ana", "message_text": "x" * 500, "platform": "whatsapp",
    })
    assert title == "Enviar mensagem"
    assert "receiver: Ana" in detail
    assert len(detail) <= 160 and detail.endswith("…")


def test_describe_inclui_subacao_e_ignora_vazios():
    title, detail = describe("computer_control", {"action": "type", "text": "oi", "x": ""})
    assert title == "Controlar o computador: type"
    assert detail == "text: oi"
