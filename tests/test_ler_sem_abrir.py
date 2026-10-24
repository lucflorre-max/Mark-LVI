"""Pesquisar e ler sem abrir o navegador, a não ser que ele peça para VER."""

import pytest

from jarvis.brain import gate, ler_sem_abrir


class Relogio:
    t = 1000.0

    def __call__(self):
        return self.t


class _Confirm:
    def __init__(self):
        self.pedidos = []

    def pending_title(self):
        return ""

    def request(self, key, title, detail, run):
        self.pedidos.append(title)
        return "[CONFIRMATION_PENDING] confirme na tela"


@pytest.fixture
def ambiente(monkeypatch):
    rel = Relogio()
    monkeypatch.setattr(gate, "_relogio", rel)
    consultas, paginas = [], []
    monkeypatch.setattr(ler_sem_abrir, "_pesquisar",
                        lambda q: consultas.append(q) or "Inter e Botafogo jogam às 16h no Beira-Rio.")
    monkeypatch.setattr(ler_sem_abrir, "_ler_pagina",
                        lambda url: paginas.append(url) or "Texto da página do ge. " * 200)
    gate.reset()
    yield rel, consultas, paginas, _Confirm()
    gate.reset()


def _guard(args, confirm):
    return gate.guard("browser_control", args, lambda: "abriu o navegador", confirm=confirm)


def test_pesquisa_no_navegador_vira_leitura_sem_clique(ambiente):
    rel, consultas, _, confirm = ambiente
    gate.ouvir("Pode falar mais sobre o jogo do Brasileirão contra o Botafogo hoje?")
    r = _guard({"action": "search", "query": "Internacional x Botafogo hoje"}, confirm)
    assert r.startswith("[READ_WITHOUT_BROWSER]")
    assert "<<<UNTRUSTED source=web>>>" in r and "Beira-Rio" in r
    assert consultas == ["Internacional x Botafogo hoje"] and confirm.pedidos == []


def test_abrir_pagina_vira_leitura_e_limita_o_tamanho(ambiente):
    rel, _, paginas, confirm = ambiente
    gate.ouvir("detalha essa notícia")
    r = _guard({"action": "go_to", "url": "https://ge.globo.com/x"}, confirm)
    assert paginas == ["https://ge.globo.com/x"] and confirm.pedidos == []
    assert r.count("Texto da página") < 200          # cortado em MAX_PAGINA


@pytest.mark.parametrize("fala", [
    "Abre no navegador a pesquisa do jogo",
    "abra o site do ge",
    "mostra na tela pra mim",
    "quero ver a página",
    "pesquisa no Chrome",
])
def test_quando_ele_quer_ver_segue_o_clique(ambiente, fala):
    rel, consultas, _, confirm = ambiente
    gate.ouvir(fala)
    r = _guard({"action": "search", "query": "Inter x Botafogo"}, confirm)
    assert r.startswith("[CONFIRMATION_PENDING]") and consultas == []
    assert confirm.pedidos == ["Controlar o navegador: search"]


def test_fala_antiga_nao_conta(ambiente):
    rel, consultas, _, confirm = ambiente
    gate.ouvir("abre o navegador")
    rel.t += ler_sem_abrir.JANELA_SEG + 1
    gate.ouvir("fala mais do jogo")
    assert _guard({"action": "search", "query": "jogo"}, confirm).startswith("[READ_WITHOUT_BROWSER]")


@pytest.mark.parametrize("fala", ["a notícia de abril", "um abraço ao time", "a pesquisa mostrou"])
def test_palavras_parecidas_nao_contam_como_ver(fala):
    assert not ler_sem_abrir.quer_ver([fala])


def test_outras_acoes_do_navegador_nao_mudam(ambiente):
    rel, consultas, _, confirm = ambiente
    gate.ouvir("fecha a aba")
    r = _guard({"action": "close_tab"}, confirm)
    assert r.startswith("[CONFIRMATION_PENDING]") and consultas == []


def test_outra_ferramenta_nao_e_afetada(ambiente):
    _, consultas, _, confirm = ambiente
    r = gate.guard("send_message", {"query": "x"}, lambda: "", confirm=confirm)
    assert r.startswith("[CONFIRMATION_PENDING]") and consultas == []


def test_falha_na_leitura_volta_ao_caminho_normal(ambiente, monkeypatch):
    _, _, _, confirm = ambiente
    monkeypatch.setattr(ler_sem_abrir, "_pesquisar", lambda q: (_ for _ in ()).throw(RuntimeError("x")))
    r = _guard({"action": "search", "query": "jogo"}, confirm)
    assert r.startswith("[CONFIRMATION_PENDING]")


def test_pesquisa_vazia_volta_ao_caminho_normal(ambiente):
    _, _, _, confirm = ambiente
    assert _guard({"action": "search", "query": " "}, confirm).startswith("[CONFIRMATION_PENDING]")
