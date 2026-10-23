"""Correções de segurança feitas no código do Mark (docs/mudancas-no-mark.md)."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("path", [
    "config/api_keys.json",
    "config/certs/key.pem",
    "config/whatsapp_web/session",
    "plugins/token_gmail.json",
    "config/client_secret_123.json",
    "data/jarvis.db",
])
def test_gitignore_ignora_segredos_e_dados(path):
    # --no-index: testa o .gitignore do repositório, não o .git/info/exclude local
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-v", path],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"{path} não está ignorado"
    assert result.stdout.startswith(".gitignore:"), result.stdout


def test_close_app_nunca_fecha_o_shell_do_windows():
    from core import appidentity
    for cls in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
        assert cls in appidentity.SHELL_WINDOW_CLASSES
    # Janelas de pasta do Explorador continuam podendo ser fechadas.
    assert "CabinetWClass" not in appidentity.SHELL_WINDOW_CLASSES


def test_painel_desligado_por_padrao(monkeypatch):
    from jarvis import config
    monkeypatch.setattr(config, "_keys", lambda: {})
    assert config.dashboard_enabled() is False
    monkeypatch.setattr(config, "_keys", lambda: {"dashboard_enabled": "true"})
    assert config.dashboard_enabled() is False   # só o booleano true liga
    monkeypatch.setattr(config, "_keys", lambda: {"dashboard_enabled": True})
    assert config.dashboard_enabled() is True
