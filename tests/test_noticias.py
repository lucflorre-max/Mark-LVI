"""M1B: card de notícias com a foto da principal (jarvis/interface/noticias.py, ui.py)."""

import os

import pytest

from jarvis.interface import noticias

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

ITENS = [
    {"title": "Sem foto", "source": "g1", "url": "u1", "snippet": "a", "image": ""},
    {"title": "Com foto", "source": "BBC", "url": "u2", "snippet": "b",
     "image": "https://img/2.jpg"},
    {"title": "Outra com foto", "source": "CNN", "url": "u3", "snippet": "c",
     "image": "https://img/3.jpg"},
]


class _UI:
    def __init__(self, com_news=True):
        self.textos, self.news = [], []
        if not com_news:
            self.show_news = None
            del self.show_news

    def show_content(self, titulo, texto):
        self.textos.append((titulo, texto))

    def show_news(self, titulo, itens, foto, indice):
        self.news.append((titulo, [i["title"] for i in itens], foto, indice))


class _SemNews:
    def __init__(self):
        self.textos = []

    def show_content(self, titulo, texto):
        self.textos.append((titulo, texto))


def test_escolher_pega_a_primeira_com_foto_e_limita():
    itens, i = noticias.escolher(ITENS + [{"title": f"n{n}"} for n in range(10)] + [{"title": ""}])
    assert i == 1 and len(itens) == noticias.MAX_ITENS
    assert noticias.escolher([{"title": "x"}]) == ([{"title": "x"}], None)


def test_texto_primeiro_e_foto_depois(monkeypatch):
    monkeypatch.setattr(noticias, "_baixar_fn", lambda url: b"PNG" if url.endswith("2.jpg") else None)
    ui = _UI()
    noticias.mostrar(ui, "NOTÍCIAS", "texto", itens=ITENS, esperar=True)
    assert ui.news[0] == ("NOTÍCIAS", ["Sem foto", "Com foto", "Outra com foto"], None, None)
    assert ui.news[1][2:] == (b"PNG", 1)
    assert ui.textos == []


def test_foto_que_falha_tenta_a_proxima(monkeypatch):
    monkeypatch.setattr(noticias, "_baixar_fn", lambda url: b"JPG" if url.endswith("3.jpg") else None)
    ui = _UI()
    noticias.mostrar(ui, "N", "t", itens=ITENS, esperar=True)
    assert ui.news[-1][2:] == (b"JPG", 2)


def test_nenhuma_foto_baixada_fica_so_o_texto(monkeypatch):
    monkeypatch.setattr(noticias, "_baixar_fn", lambda url: None)
    ui = _UI()
    noticias.mostrar(ui, "N", "t", itens=ITENS, esperar=True)
    assert ui.news[-1][2:] == (None, None)


def test_sem_lista_ou_sem_show_news_usa_o_painel_de_texto():
    ui = _UI()
    noticias.mostrar(ui, "N", "texto do gemini", itens=[])
    assert ui.textos == [("N", "texto do gemini")] and ui.news == []
    velho = _SemNews()
    noticias.mostrar(velho, "N", "t", itens=ITENS)
    assert velho.textos == [("N", "t")]


def test_baixar_recusa_o_que_nao_e_http():
    assert noticias._baixar("file:///C:/Windows/win.ini") is None


def test_web_search_guarda_a_foto_da_ultima_busca(monkeypatch):
    from actions import web_search
    item = dict(ITENS[1], snippet="Resumo longo o bastante para o Mark aceitar a resposta do DDG.")
    monkeypatch.setattr(web_search, "_ddg_news", lambda q, max_results=8: [item])

    def sem_rede(q):
        raise AssertionError("o teste não pode chamar o Gemini")

    monkeypatch.setattr(web_search, "_gemini_search", sem_rede)
    texto = web_search._news("Brasil")
    assert "Com foto" in texto
    ultimas = web_search.ultimas_noticias()
    assert ultimas[0]["image"] == "https://img/2.jpg"
    ultimas[0]["image"] = "mexido"                       # é uma cópia
    assert web_search.ultimas_noticias()[0]["image"] == "https://img/2.jpg"


# ── O card no Qt (sem tela) ─────────────────────────────────────────────────

def test_card_desenha_foto_e_escapa_html():
    QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QUrl
    from PyQt6.QtGui import QColor, QImage, QTextDocument
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    import ui

    img = QImage(300, 150, QImage.Format.Format_RGB32)
    img.fill(QColor("blue"))
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")

    class _Hud:
        def glance(self, *a, **k):
            pass

    class _Split:
        def height(self):
            return 600

        def setSizes(self, s):
            pass

    falso = type("W", (), {})()
    falso._esc = ui.MainWindow._esc
    falso.hud, falso._center_split = _Hud(), _Split()
    falso._content_display = QtWidgets.QTextEdit()
    falso._content_display.resize(500, 400)
    falso._content_title_lbl, falso._content_ts_lbl = QtWidgets.QLabel(), QtWidgets.QLabel()
    falso._content_panel = QtWidgets.QWidget()

    itens = [{"title": "<script>x</script> Manchete", "source": "BBC", "snippet": "resumo"},
             {"title": "Segunda", "source": "g1"}]
    ui.MainWindow._show_news(falso, "Notícias — Brasil", itens, bytes(ba), 0)

    html = falso._content_display.toHtml()
    assert "jarvis://noticia/" in html
    assert "<script>" not in html and "&lt;script&gt;" in html
    url = QUrl(html.split('src="')[1].split('"')[0])
    foto = falso._content_display.document().resource(QTextDocument.ResourceType.ImageResource, url)
    assert foto is not None and not QImage(foto).isNull()
    assert falso._content_title_lbl.text() == "NOTÍCIAS — BRASIL"
    del app
