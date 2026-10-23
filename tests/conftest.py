"""Configuração comum dos testes."""

import pytest

from jarvis.tasks import sincronia


@pytest.fixture(autouse=True)
def _sem_contas_reais(monkeypatch):
    """Nenhum teste fala com o Trello ou o Google de verdade. Os testes de
    sincronia religam com clientes falsos (tests/test_sincronia.py)."""
    monkeypatch.setattr(sincronia, "_desligada", True)
    monkeypatch.setattr(sincronia, "_trello", None)
    monkeypatch.setattr(sincronia, "_calendario", None)
