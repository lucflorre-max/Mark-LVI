import pytest

from jarvis.brain import policy
from jarvis.brain.policy import CATEGORIAS_CONFIRM, describe, requires_confirm


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
    ("computer_settings", {"action": "new_tab"}),      # teste por voz: só atrapalhava
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


# ── Três níveis: direto, voz, clique ───────────────────────────────────────

@pytest.mark.parametrize("name, args", [
    ("computer_control", {"action": "type", "text": "x"}),
    ("computer_control", {"action": "click"}),
    ("computer_control", {"action": "close_app", "app_name": "Notepad"}),
    ("computer_settings", {"action": "type_text", "value": "x"}),
    ("computer_settings", {"action": "save"}),
    ("computer_settings", {"action": "press_key", "value": "enter"}),
])
def test_digitar_teclar_clicar_e_por_voz(name, args):
    assert policy.nivel(name, args) == policy.VOZ


@pytest.mark.parametrize("name, args", [
    ("send_message", {"receiver": "Ana"}),
    ("browser_control", {"action": "go_to"}),
    ("file_controller", {"action": "delete"}),
    ("code_helper", {"action": "run"}),
    ("desktop_control", {"action": "clean"}),
    ("computer_settings", {"action": "open_run"}),   # abre o Executar do Windows
    ("computer_control", {}),                       # ação ausente: clique
    ("computer_control", {"action": "inventada"}),
])
def test_o_resto_continua_no_clique(name, args):
    assert policy.nivel(name, args) == policy.CLIQUE


def test_direto():
    assert policy.nivel("open_app", {"app_name": "x"}) == policy.DIRETO
    assert policy.nivel("computer_settings", {"action": "volume_up"}) == policy.DIRETO


# ── Tarefa 5: ações do JARVIS ───────────────────────────────────────────────

@pytest.mark.parametrize("acao", ["criar", "listar_hoje", "concluir", "desfazer"])
def test_tarefas_reversiveis_nao_pedem_clique(acao):
    assert requires_confirm("jarvis_tarefas", {"acao": acao}) is False


def test_tarefas_sem_acao_e_criar():
    assert requires_confirm("jarvis_tarefas", {"titulo": "x"}) is False


def test_acao_nova_do_jarvis_pede_clique_ate_ser_classificada():
    assert requires_confirm("jarvis_tarefas", {"acao": "apagar_todas"}) is True


@pytest.mark.parametrize("categoria", sorted(CATEGORIAS_CONFIRM))
def test_categorias_do_claude_md_pedem_confirmacao(categoria):
    for nome, args in CATEGORIAS_CONFIRM[categoria]:
        assert requires_confirm(nome, args), f"{categoria}: {nome} {args}"


def test_service_respeita_a_politica(monkeypatch, tmp_path):
    """Se a política mudar 'concluir' para irreversível, o plugin passa a
    esperar o CONFIRM sem nenhuma mudança no serviço."""
    from jarvis.tasks import service
    from jarvis.tasks.repository import TaskRepository
    from tests.test_gate import FakeConfirm

    repo = TaskRepository(tmp_path / "t.db")
    t = repo.adicionar("Roteador", prazo="2026-10-23")
    fake = FakeConfirm()
    monkeypatch.setattr(service, "_repo", repo)
    monkeypatch.setattr(service, "_confirm", fake)
    monkeypatch.setitem(policy._SAFE, "jarvis_tarefas",
                        frozenset({"criar", "listar_hoje", "desfazer"}))

    out = service.handle({"acao": "concluir", "tarefa_id": t.id})
    assert out.startswith("[CONFIRMATION_PENDING]")
    assert repo.obter(t.id).status == "aberta"        # nada antes do clique
    key, title, _detail, run = fake.requests[0]
    assert key == "jarvis:jarvis_tarefas" and title == "Tarefas: concluir"
    monkeypatch.setattr(service, "_undo", type("U", (), {"push_undo": lambda *a: None})())
    run()                                             # o clique em CONFIRM
    assert repo.obter(t.id).status == "concluida"


def test_describe_inclui_subacao_e_ignora_vazios():
    title, detail = describe("computer_control", {"action": "type", "text": "oi", "x": ""})
    assert title == "Controlar o computador: type"
    assert detail == "text: oi"
