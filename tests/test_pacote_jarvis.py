import importlib
from pathlib import Path

import pytest

from core.plugin_loader import discover_plugins
from jarvis import config
from jarvis.tasks import service

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("sub", ["brain", "tasks", "calendar", "projects",
                                 "memory", "integrations", "interface"])
def test_subpacotes_existem(sub):
    importlib.import_module(f"jarvis.{sub}")


def test_config_basica():
    assert config.IDIOMA == "pt-BR"
    assert config.DB_PATH == ROOT / "data" / "jarvis.db"
    from datetime import datetime
    agora = datetime(2026, 10, 23, 12, 0, tzinfo=config.fuso())
    assert agora.utcoffset().total_seconds() == -3 * 3600


def test_nome_assistente(monkeypatch):
    monkeypatch.setattr(config, "_keys", lambda: {})
    assert config.nome_assistente() == "JARVIS"
    monkeypatch.setattr(config, "_keys", lambda: {"assistant_name": "Sexta-Feira"})
    assert config.nome_assistente() == "Sexta-Feira"


def test_plugin_e_descoberto_pelo_mark():
    logs = []
    registry = discover_plugins(ROOT / "plugins", core_tool_names=set(), logger=logs.append)
    assert registry.has("jarvis_tarefas"), logs
    decl = {d["name"]: d for d in registry.get_tool_declarations()}["jarvis_tarefas"]
    props = decl["parameters"]["properties"]
    for campo in ("acao", "titulo", "prazo", "prioridade", "duracao_min",
                  "projeto", "contexto", "confirmado"):
        assert campo in props


def test_plugin_so_repassa_para_o_servico(monkeypatch):
    plugin = importlib.import_module("plugins.jarvis_tarefas")
    chamadas = []
    monkeypatch.setattr(service, "handle", lambda p, player=None: chamadas.append(p) or "ok")
    assert plugin.run({"acao": "listar_hoje"}) == "ok"
    assert chamadas == [{"acao": "listar_hoje"}]


def test_servico_nunca_finge_que_salvou():
    out = service.handle({"acao": "criar", "titulo": "x"})
    assert "Nada foi salvo" in out
    assert "desconhecida" in service.handle({"acao": "voar"})
