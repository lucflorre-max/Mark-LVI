"""Ler a matéria completa de uma notícia, sem navegador nem confirmação."""

import importlib

import pytest

from jarvis.integrations import noticias
from jarvis.pesquisa import fontes

plugin = importlib.import_module("plugins.jarvis_noticias")

ITENS = [
    {"title": "Circulação é interrompida na Linha 15-Prata", "source": "Metrópoles",
     "url": "https://metropoles.com/linha-15", "snippet": "acidente com guindaste"},
    {"title": "Chances de Grêmio e Inter na Série A", "source": "ge",
     "url": "https://ge.globo.com/dupla", "snippet": "a dupla Gre-Nal precisa de campanha rara"},
    {"title": "Vídeo do acidente", "source": "g1",
     "url": "https://youtube.com/watch?v=x", "snippet": ""},
]


class _Player:
    def __init__(self):
        self.cards = []

    def show_content(self, titulo, texto):
        self.cards.append((titulo, texto))


@pytest.fixture
def lista(monkeypatch):
    noticias.guardar(ITENS)
    yield
    noticias.guardar([])


@pytest.mark.parametrize("ref, titulo", [
    ("2", "Chances de Grêmio e Inter na Série A"),
    ("Grêmio e Inter", "Chances de Grêmio e Inter na Série A"),
    ("dupla", "Chances de Grêmio e Inter na Série A"),        # acha pelo resumo
    ("guindaste", "Circulação é interrompida na Linha 15-Prata"),
])
def test_escolher(ref, titulo):
    assert noticias.escolher(ref, ITENS)["title"] == titulo


@pytest.mark.parametrize("ref", [
    "9", "0",          # fora da lista
    "eleição", "",     # nada combina
    "acidente",        # empate: resumo da 1ª e título da 3ª
])
def test_escolher_sem_certeza_devolve_none(ref):
    assert noticias.escolher(ref, ITENS) is None


def test_ler_conta_a_materia_sem_navegador(lista, monkeypatch):
    lidas = []
    corpo = ("Menu Entrar Assine. " + "Publicidade. " * 50
             + "A dupla Gre-Nal precisa de uma campanha rara para escapar. "
             + "O Inter tem 30 pontos e o Grêmio tem 28. " * 3)
    monkeypatch.setattr(fontes, "ler", lambda url: lidas.append(url) or corpo)
    player = _Player()
    r = plugin.run({"ler": "2"}, player=player)
    assert lidas == ["https://ge.globo.com/dupla"]
    assert "<<<UNTRUSTED source=rss>>>" in r and "campanha rara" in r
    assert "4 a 6 frases" in r and "CONFIRMATION" not in r
    assert player.cards[0][0] == "NOTÍCIA — ge"
    assert player.cards[0][1].startswith("Chances de Grêmio e Inter na Série A")


def test_site_que_nao_deixa_ler_sugere_web_search_e_nao_navegador(lista, monkeypatch):
    monkeypatch.setattr(fontes, "ler", lambda url: "")
    r = plugin.run({"ler": "1"})
    assert "web_search" in r and "sem abrir o" in r and "guindaste" in r


def test_video_nao_tenta_ler(lista, monkeypatch):
    monkeypatch.setattr(fontes, "ler", lambda url: pytest.fail("não devia ler o YouTube"))
    assert "não deixou ler" in plugin.run({"ler": "3"})


def test_sem_lista_pede_as_noticias_primeiro():
    noticias.guardar([])
    assert "Ainda não há lista" in plugin.run({"ler": "1"})


def test_referencia_ambigua_mostra_a_lista(lista):
    r = plugin.run({"ler": "eleição"})
    assert "Não sei qual" in r and "2. Chances de Grêmio" in r


def test_descricao_manda_usar_ler_e_nao_o_navegador():
    desc = plugin.PLUGIN["description"]
    assert "`ler`" in desc and "Nunca use browser_control" in desc
    assert "ler" in plugin.PLUGIN["parameters"]["properties"]


def test_prompt_diz_que_ler_nao_abre_navegador():
    from pathlib import Path
    prompt = (Path(__file__).resolve().parent.parent / "core" / "prompt.txt").read_text(encoding="utf-8")
    assert "Use browser_control only when the user asks to SEE or OPEN" in prompt
