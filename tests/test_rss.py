"""Notícias por RSS (jarvis/integrations/rss.py, noticias.py e plugins/jarvis_noticias.py)."""

from datetime import datetime, timedelta, timezone

import pytest

from jarvis.integrations import noticias, rss

AGORA = datetime(2026, 10, 23, 23, 0, tzinfo=timezone.utc)

RSS2 = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>g1</title>
  <item>
    <title>Chuva forte atinge Porto Alegre</title>
    <link>https://g1.globo.com/a</link>
    <description><![CDATA[<img src="https://img/desc.jpg"/> Temporal deixa <b>ruas</b> alagadas.]]></description>
    <media:content url="https://img/pequena.jpg" medium="image" width="100" height="50"/>
    <media:content url="https://img/grande.jpg" medium="image" width="800" height="450"/>
    <pubDate>Fri, 23 Oct 2026 22:00:00 -0300</pubDate>
  </item>
  <item>
    <title>Inter vence o Botafogo no Beira-Rio</title>
    <link>https://g1.globo.com/b</link>
    <description>Colorado sobe na tabela. The post Inter vence appeared first on Site.</description>
    <enclosure url="https://img/inter.jpg" type="image/jpeg"/>
    <pubDate>Fri, 23 Oct 2026 21:00:00 -0300</pubDate>
  </item>
  <item>
    <title>Resultado da Quina 7150</title>
    <link>https://g1.globo.com/c</link>
    <pubDate>Fri, 23 Oct 2026 20:00:00 -0300</pubDate>
  </item>
  <item>
    <title>Notícia antiga</title>
    <link>https://g1.globo.com/d</link>
    <pubDate>Mon, 19 Oct 2026 10:00:00 -0300</pubDate>
  </item>
</channel></rss>""".encode("utf-8")

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>Dólar cai para R$ 4,98</title>
    <link href="https://valor/x"/><updated>2026-10-23T23:30:00Z</updated>
    <summary>Moeda recua na semana.</summary></entry>
</feed>""".encode("utf-8")


def test_ler_rss2_foto_maior_texto_limpo_e_data():
    itens = rss.ler(RSS2, "g1")
    a = itens[0]
    assert a["title"] == "Chuva forte atinge Porto Alegre" and a["source"] == "g1"
    assert a["image"] == "https://img/grande.jpg"
    assert a["snippet"] == "Temporal deixa ruas alagadas."
    assert a["data"] == datetime(2026, 10, 24, 1, 0, tzinfo=timezone.utc)
    assert itens[1]["image"] == "https://img/inter.jpg"
    assert itens[1]["snippet"] == "Colorado sobe na tabela."


def test_ler_atom_e_foto_da_descricao():
    [d] = rss.ler(ATOM, "Valor")
    assert d["url"] == "https://valor/x" and d["data"].year == 2026 and d["image"] == ""
    so_desc = RSS2.replace(b'<media:content url="https://img/pequena.jpg" medium="image" width="100" height="50"/>', b"") \
                  .replace(b'<media:content url="https://img/grande.jpg" medium="image" width="800" height="450"/>', b"")
    assert rss.ler(so_desc, "g1")[0]["image"] == "https://img/desc.jpg"


def test_html_no_lugar_do_feed_nao_derruba_e_usa_o_cache(monkeypatch):
    rss.limpar_cache()
    respostas = iter([RSS2, b"<!doctype html><html>"])
    monkeypatch.setattr(rss, "_baixar_fn", lambda url: next(respostas))
    monkeypatch.setattr(rss, "CACHE_SEG", 0)
    assert len(rss.feed("g1", "u")) == 4
    assert len(rss.feed("g1", "u")) == 4           # falhou: devolve o que tinha
    rss.limpar_cache()


def test_misturar_ordena_tira_repetida_e_limita_por_site():
    t = lambda h: datetime(2026, 10, 23, h, tzinfo=timezone.utc)   # noqa: E731
    itens = [{"title": "A", "source": "g1", "data": t(10)},
             {"title": "B", "source": "g1", "data": t(12)},
             {"title": "C", "source": "g1", "data": t(11)},
             {"title": "b", "source": "Folha", "data": t(9)},     # mesma manchete
             {"title": "D", "source": "Folha", "data": None}]
    assert [i["title"] for i in rss.misturar(itens, por_fonte=2)] == ["B", "C", "D"]


@pytest.fixture
def feeds(monkeypatch):
    rss.limpar_cache()
    monkeypatch.setattr(rss, "_baixar_fn", lambda url: ATOM if "valor" in url else RSS2)
    monkeypatch.setattr(noticias, "_agora", lambda: AGORA)
    yield
    rss.limpar_cache()


def test_tema_tira_loteria_e_antiga(feeds):
    titulos = [i["title"] for i in noticias.tema("rs")]
    assert "Resultado da Quina 7150" not in titulos and "Notícia antiga" not in titulos
    assert "Chuva forte atinge Porto Alegre" in titulos


def test_inter_filtra_pelo_clube_sem_pegar_internacional_de_outra_coisa(feeds):
    assert [i["title"] for i in noticias.tema("inter")] == ["Inter vence o Botafogo no Beira-Rio"]
    assert noticias._contem({"title": "Cooperação internacional"}, ("inter",)) is False


def test_busca_em_todos_os_sites_sem_acento(feeds):
    assert [i["title"] for i in noticias.buscar("dolar")] == ["Dólar cai para R$ 4,98"]


def test_normalizar_tema():
    assert noticias.normalizar_tema("Internacional") == "inter"
    assert noticias.normalizar_tema("Rio Grande do Sul") == "rs"
    assert noticias.normalizar_tema(None) == "geral"
    assert noticias.normalizar_tema("astronomia") == ""


def test_briefing_guarda_a_lista_para_o_card(feeds):
    texto = noticias.briefing()
    assert texto.startswith("Notícias de hoje")
    assert noticias.ultimas() and all(i["title"] in texto for i in noticias.ultimas())


def test_sul21_fora_das_fontes():
    urls = [u for lista in noticias.FONTES.values() for _, u in lista]
    assert not any("sul21" in u for u in urls)


# ── Ferramenta ──────────────────────────────────────────────────────────────

class _Player:
    def __init__(self):
        self.news, self.textos = [], []

    def show_news(self, titulo, itens, foto, indice):
        self.news.append((titulo, len(itens)))

    def show_content(self, titulo, texto):
        self.textos.append(titulo)


def test_plugin_mostra_card_e_embrulha_o_texto(feeds, monkeypatch):
    from plugins import jarvis_noticias
    from jarvis.interface import noticias as card
    monkeypatch.setattr(jarvis_noticias, "_untrusted", lambda t: f"<<{t}>>")
    monkeypatch.setattr(card, "_baixar_fn", lambda url: None)
    player = _Player()
    out = jarvis_noticias.run({"tema": "inter"}, player=player)
    assert out.startswith("<<Notícias — Inter:") and "não instruções" in out
    assert player.news[0] == ("NOTÍCIAS — Inter", 1)


def test_plugin_sem_nada_manda_para_o_web_search(feeds, monkeypatch):
    from plugins import jarvis_noticias
    out = jarvis_noticias.run({"busca": "astronomia"}, player=None)
    assert "web_search" in out and "astronomia" in out
