"""Modo pesquisador (jarvis/pesquisa/): busca, lê as páginas, com prazo, sem loop."""

import time
from pathlib import Path

import pytest

from jarvis import config
from jarvis.pesquisa import fontes, pesquisador

ROOT = Path(__file__).resolve().parent.parent


class _Resp:
    def __init__(self, status=200, text="", dados=None):
        self.status_code, self.text, self._dados = status, text, dados

    def json(self):
        return self._dados


PAGINA = ("<html><nav>Menu Home Login</nav><body><p>Devocionais de sexta-feira, "
          "23 de outubro de 2026.</p><p>Grande alegria com a notícia da "
          "ressurreição. Mateus 28:8. E, retirando-se elas apressadamente do "
          "sepulcro, com temor e grande alegria, correram a anunciá-lo.</p>"
          + "<p>Texto de enchimento sem relação nenhuma com a pergunta.</p>" * 20
          + "<script>alert(1)</script></body></html>")


@pytest.fixture(autouse=True)
def _limpo(monkeypatch):
    pesquisador._cache.clear()
    monkeypatch.setattr(config, "tavily_api_key", lambda: "")
    yield
    pesquisador._cache.clear()


def _ddg(monkeypatch, itens):
    monkeypatch.setattr(fontes, "ddg", lambda q, max_resultados=6: [dict(i, texto="") for i in itens])


def test_ddg_e_le_a_pagina(monkeypatch):
    _ddg(monkeypatch, [
        {"title": "Vídeo", "url": "https://www.youtube.com/watch?v=x", "snippet": "vídeo"},
        {"title": "Devocionais 23/10", "url": "https://devocional.exemplo/23", "snippet": "curto"},
    ])
    lidas = []
    monkeypatch.setattr(fontes, "_get", lambda url, **kw: lidas.append(url) or _Resp(text=PAGINA))

    texto = pesquisador.pesquisar("meditação 23 de outubro ressurreição")

    assert lidas == ["https://devocional.exemplo/23"]          # vídeo não é lido
    assert "Mateus 28:8" in texto
    assert "alert(1)" not in texto and "Menu Home Login" not in texto
    assert texto.index("Devocionais 23/10") < texto.index("Vídeo")   # página lida primeiro
    assert len(texto) <= pesquisador.TOTAL + 1


def test_tavily_quando_tem_chave(monkeypatch):
    monkeypatch.setattr(config, "tavily_api_key", lambda: "tvly-teste")
    enviado = {}

    def post(url, **kw):
        enviado.update(kw)
        return _Resp(dados={"answer": "O tema é a ressurreição.", "results": [
            {"title": "Devocional", "url": "https://d.exemplo", "content": "trecho",
             "raw_content": "Grande alegria com a notícia da ressurreição."}]})

    monkeypatch.setattr(fontes, "_post", post)
    monkeypatch.setattr(fontes, "_get", lambda *a, **k: pytest.fail("não devia ler página"))

    texto = pesquisador.pesquisar("tema da meditação")

    assert enviado["headers"]["Authorization"] == "Bearer tvly-teste"
    assert enviado["json"]["search_depth"] == "basic"          # 1 crédito por busca
    assert "Quick answer: O tema é a ressurreição." in texto
    assert "Grande alegria" in texto


def test_tavily_falha_cai_no_ddg(monkeypatch):
    monkeypatch.setattr(config, "tavily_api_key", lambda: "tvly-teste")
    monkeypatch.setattr(fontes, "_post", lambda *a, **k: _Resp(status=432))
    _ddg(monkeypatch, [{"title": "Reserva", "url": "https://www.youtube.com/v", "snippet": "ok"}])
    assert "Reserva" in pesquisador.pesquisar("qualquer coisa")


def test_sem_resultado_levanta(monkeypatch):
    _ddg(monkeypatch, [])
    with pytest.raises(RuntimeError):
        pesquisador.pesquisar("nada")


def test_pagina_lenta_nao_segura_a_resposta(monkeypatch):
    monkeypatch.setattr(pesquisador, "PRAZO", 0.3)
    _ddg(monkeypatch, [{"title": "Lenta", "url": "https://lenta.exemplo", "snippet": "trecho da busca"}])
    monkeypatch.setattr(fontes, "ler", lambda url: time.sleep(2) or "tarde demais")

    inicio = time.monotonic()
    texto = pesquisador.pesquisar("pergunta")

    assert time.monotonic() - inicio < 1.5
    assert "trecho da busca" in texto and "tarde demais" not in texto


def test_mesma_pergunta_vem_da_memoria(monkeypatch):
    chamadas = []
    monkeypatch.setattr(fontes, "ddg", lambda q, max_resultados=6: chamadas.append(q)
                        or [{"title": "T", "url": "https://youtu.be/x", "snippet": "s", "texto": ""}])
    pesquisador.pesquisar("Meditação de hoje")
    pesquisador.pesquisar("meditacao de hoje")
    assert len(chamadas) == 1


def test_bloqueio_anti_robo_tenta_o_jina(monkeypatch):
    def get(url, **kw):
        if url.startswith(fontes.JINA_URL):
            return _Resp(text="Texto completo lido pelo Jina. " * 20)
        return _Resp(text="<html><body>Client Challenge</body></html>")

    monkeypatch.setattr(fontes, "_get", get)
    assert fontes.ler("https://bloqueado.exemplo").startswith("Texto completo lido pelo Jina.")


def test_trechos_guarda_o_que_importa():
    texto = "Nada aqui. " * 200 + "A meditação de hoje fala da ressurreição. Fim da ideia. " + "Nada aqui. " * 200
    t = pesquisador.trechos(texto, "meditação ressurreição", limite=200)
    assert "meditação de hoje fala da ressurreição" in t
    assert len(t) <= 200


def test_web_search_usa_o_pesquisador_e_poe_a_nota_fora_do_embrulho(monkeypatch):
    from actions import web_search
    monkeypatch.setattr(pesquisador, "pesquisar", lambda q: f"Search results for: {q}")
    monkeypatch.setattr(web_search, "_gemini_search", lambda q: pytest.fail("não devia usar o Gemini"))

    r = web_search.web_search({"query": "tema de hoje"})

    assert "<<<UNTRUSTED source=web>>>" in r
    assert r.rstrip().endswith(pesquisador.NOTA)
    assert r.index("<<<END UNTRUSTED>>>") < r.index("[RESEARCH_DONE]")


def test_web_search_volta_ao_mark_se_o_pesquisador_falhar(monkeypatch):
    from actions import web_search
    monkeypatch.setattr(pesquisador, "pesquisar", lambda q: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(web_search, "_search", lambda q: "resultado do Mark")
    r = web_search.web_search({"query": "tema"})
    assert "resultado do Mark" in r and "[RESEARCH_DONE]" not in r


def test_prompt_proibe_o_loop():
    prompt = (ROOT / "core" / "prompt.txt").read_text(encoding="utf-8")
    assert "[RESEARCH_DONE]" in prompt
    assert "Call it ONCE per question" in prompt
