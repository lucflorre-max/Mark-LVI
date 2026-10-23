"""Meta 1B: HUD do Mark com o núcleo como padrão (ui.py, config_manager.py)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")


@pytest.fixture(scope="module")
def ui_mod():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    import ui
    yield ui
    del app


@pytest.fixture
def hud(ui_mod, monkeypatch):
    import memory.config_manager as cm
    monkeypatch.setattr(cm, "load_api_keys", lambda: {})       # config sem hud_style
    h = ui_mod.HudCanvas("", "J.A.R.V.I.S")
    h.resize(820, 560)
    return h


def test_padrao_e_o_nucleo(monkeypatch):
    import memory.config_manager as cm
    monkeypatch.setattr(cm, "load_api_keys", lambda: {})
    assert cm.get_hud_style() == "core"
    monkeypatch.setattr(cm, "load_api_keys", lambda: {"hud_style": "qualquer"})
    assert cm.get_hud_style() == "core"
    monkeypatch.setattr(cm, "load_api_keys", lambda: {"hud_style": "face"})
    assert cm.get_hud_style() == "face"                         # escolha explícita vale


def test_rosto_nao_e_carregado_no_nucleo(hud):
    assert hud.hud_style == "core"
    assert hud._avatar is None


@pytest.mark.parametrize("state, speaking, muted, esperado", [
    ("LISTENING", False, False, True),
    ("LISTENING", True, False, False),
    ("LISTENING", False, True, False),
    ("THINKING", False, False, False),
    ("INITIALISING", False, False, False),
])
def test_quando_esta_em_repouso(hud, state, speaking, muted, esperado):
    hud.state, hud.speaking, hud.muted = state, speaking, muted
    assert hud._em_repouso() is esperado


def test_frase_de_repouso(ui_mod):
    assert ui_mod.HudCanvas.REPOUSO_FRASE == "Como posso ajudar, senhor?"


@pytest.mark.parametrize("state", ["LISTENING", "THINKING", "INITIALISING"])
def test_desenha_sem_erro(hud, state):
    hud.state = state
    for _ in range(5):
        hud._step()
    img = hud.grab().toImage()
    assert not img.isNull() and img.width() == 820


def test_repouso_deixa_o_rodape_mais_limpo(hud):
    """Em repouso não há barra de áudio no rodapé: menos pixels acesos lá."""
    def acesos_no_rodape():
        img = hud.grab().toImage()
        y0 = int(img.height() * 0.97)
        return sum(1 for y in range(y0, img.height()) for x in range(0, img.width(), 2)
                   if img.pixelColor(x, y).lightness() > 40)
    hud.state = "THINKING"
    com_barra = acesos_no_rodape()
    hud.state = "LISTENING"
    assert acesos_no_rodape() < com_barra


def test_botao_do_rosto_escondido():
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "ui.py").read_text(encoding="utf-8")
    assert "self._hud_btn.hide()  # JARVIS:" in src
