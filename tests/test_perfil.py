"""Perfil de comunicação (jarvis/memory/perfil.py e perfil_service.py)."""

import json

import pytest

from jarvis.brain import gate, policy
from jarvis.memory import perfil, perfil_service


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    conversas = tmp_path / "conversas"
    conversas.mkdir()
    (conversas / "2026-10-23.md").write_text(
        "# Conversas de 23/10/2026\n\n"
        "- `15:37:55` **Você:** Faz sentido. Vamos para outra pergunta, então.\n"
        "- `15:38:00` **JARVIS:** Vamos para outra, senhor.\n"     # fala dele: ignorada
        "- `15:40:56` **Você:** Vamos para outra tarefa no Colégio Anchieta.\n"
        "- `15:41:10` **Você:** Liga para a Dona Neusa da secretaria do Colégio Anchieta.\n"
        "- `15:41:30` **Você:** Abre o SIGE e depois fala com a Dona Neusa.\n"
        "- `15:42:00` 🔧 `open_app` {'app_name': 'SIGE'}\n",
        encoding="utf-8")
    arquivo = tmp_path / "perfil.json"
    monkeypatch.setattr(perfil, "CONVERSAS", conversas)
    monkeypatch.setattr(perfil, "ARQUIVO", arquivo)
    gate.reset()
    yield arquivo
    gate.reset()


# ── Análise ────────────────────────────────────────────────────────────────

def test_so_le_as_falas_do_usuario(ambiente):
    falas = perfil.falas_do_usuario()
    assert len(falas) == 4
    assert not any("senhor" in f for f in falas)


def test_sugere_nomes_siglas_e_expressoes(ambiente):
    s = perfil.sugerir()
    vocab = [t for t, _ in s["vocabulario"]]
    assert "Neusa" in vocab and "Anchieta" in vocab
    assert "SIGE" in vocab
    expr = dict(s["expressoes"])
    assert expr.get("vamos para outra") == 2
    assert "vamos para" not in expr          # dentro da maior, mesma frequência


def test_mantem_acento_como_foi_dito(tmp_path, monkeypatch):
    conversas = tmp_path / "c"
    conversas.mkdir()
    (conversas / "d.md").write_text(
        "- `1` **Você:** não precisa ler\n- `2` **Você:** Não precisa agora\n",
        encoding="utf-8")
    monkeypatch.setattr(perfil, "CONVERSAS", conversas)
    monkeypatch.setattr(perfil, "ARQUIVO", tmp_path / "p.json")
    assert ("não precisa", 2) in perfil.sugerir()["expressoes"]


def test_nao_sugere_o_que_ja_foi_aprovado_ou_rejeitado(ambiente):
    perfil.lembrar("vocabulario", "Neusa")
    perfil.rejeitar("Anchieta")
    vocab = [t for t, _ in perfil.sugerir()["vocabulario"]]
    assert "Neusa" not in vocab and "Anchieta" not in vocab


def test_sem_conversas(tmp_path, monkeypatch):
    monkeypatch.setattr(perfil, "CONVERSAS", tmp_path / "nao_existe")
    monkeypatch.setattr(perfil, "ARQUIVO", tmp_path / "p.json")
    assert perfil.sugerir() == {"vocabulario": [], "expressoes": []}


# ── Arquivo ────────────────────────────────────────────────────────────────

def test_lembrar_esquecer(ambiente):
    assert perfil.lembrar("expressao", "vamos para outra", "quer mudar de assunto").startswith("Lembrado")
    perfil.lembrar("vocabulario", "SIGE")
    dados = json.loads(ambiente.read_text(encoding="utf-8"))
    assert dados["expressoes"][0]["significado"] == "quer mudar de assunto"
    assert perfil.vocabulario_aprovado() == ["SIGE"]
    assert perfil.esquecer("Vamos para outra")["tipo"] == "expressao"
    assert perfil.esquecer("nada") is None


def test_expressao_sem_significado_pede_o_significado(ambiente):
    assert "Falta o que a expressão quer dizer" in perfil.lembrar("expressao", "tá bem?")
    assert not ambiente.exists()


def test_lembrar_de_novo_atualiza_sem_duplicar(ambiente):
    perfil.lembrar("expressao", "tá bem?", "pede confirmação")
    perfil.lembrar("expressao", "Tá bem?", "só fecha a frase")
    dados = perfil.carregar()
    assert len(dados["expressoes"]) == 1
    assert dados["expressoes"][0]["significado"] == "só fecha a frase"


def test_arquivo_estragado_nao_derruba(ambiente):
    ambiente.write_text("{ isto não é json", encoding="utf-8")
    assert perfil.carregar()["expressoes"] == []
    assert perfil.bloco_prompt() == ""
    ambiente.write_text('{"expressoes": [{"sem_texto": 1}]}', encoding="utf-8")
    assert perfil.bloco_prompt() == ""


def test_bloco_prompt(ambiente):
    assert perfil.bloco_prompt() == ""
    perfil.lembrar("expressao", "vamos para outra", "quer mudar de assunto")
    perfil.lembrar("vocabulario", "Dona Neusa")
    bloco = perfil.bloco_prompt()
    assert bloco.startswith("[HOW THE USER COMMUNICATES]")
    assert '"vamos para outra": quer mudar de assunto' in bloco
    assert "Dona Neusa" in bloco


def test_vocabulario_aprovado_vai_para_o_reconhecimento_de_voz(ambiente):
    from jarvis import config
    perfil.lembrar("vocabulario", "SIGE")
    vocab = config.transcricao_entrada()["custom_vocabulary"]
    assert "SIGE" in vocab and "Jarvis" in vocab


# ── Ferramenta por voz ─────────────────────────────────────────────────────

class Relogio:
    t = 1000.0

    def __call__(self):
        return self.t


def test_lembrar_exige_sim_falado(ambiente, monkeypatch):
    rel = Relogio()
    monkeypatch.setattr(gate, "_relogio", rel)
    monkeypatch.setattr(perfil_service, "_undo",
                        type("U", (), {"push_undo": lambda *a: None})())
    pedido = {"acao": "lembrar", "tipo": "expressao", "texto": "vamos para outra",
              "significado": "quer mudar de assunto"}
    assert perfil_service.handle(pedido).startswith("[VOICE_CONFIRM]")
    assert perfil.carregar()["expressoes"] == []             # nada salvo
    rel.t += 5
    gate.ouvir("pode lembrar sim")
    assert perfil_service.handle(pedido).startswith("Lembrado")
    assert perfil.carregar()["expressoes"][0]["texto"] == "vamos para outra"


def test_sugestoes_e_listar_nao_salvam(ambiente):
    out = perfil_service.handle({"acao": "sugestoes"})
    assert "nada salvo" in out and "vamos para outra" in out
    assert "vazio" in perfil_service.handle({"acao": "listar"})
    assert not ambiente.exists()


def test_esquecer_tem_desfazer(ambiente, monkeypatch):
    pilha = []
    monkeypatch.setattr(perfil_service, "_undo",
                        type("U", (), {"push_undo": lambda self, l, f: pilha.append(f)})())
    perfil.lembrar("vocabulario", "SIGE")
    assert perfil_service.handle({"acao": "esquecer", "texto": "SIGE"}).startswith("Esquecido")
    assert perfil.vocabulario_aprovado() == []
    pilha[-1]()                                               # "desfaz"
    assert perfil.vocabulario_aprovado() == ["SIGE"]


def test_politica_do_perfil():
    assert policy.nivel("jarvis_perfil", {"acao": "lembrar"}) == policy.VOZ
    for acao in ("sugestoes", "listar", "esquecer", "rejeitar"):
        assert policy.nivel("jarvis_perfil", {"acao": acao}) == policy.DIRETO
    assert policy.nivel("jarvis_perfil", {}) == policy.DIRETO          # padrão: sugestoes
    assert policy.nivel("jarvis_perfil", {"acao": "apagar_tudo"}) == policy.CLIQUE


def test_main_injeta_o_bloco():
    from pathlib import Path
    main_py = (Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
    assert "parts.append(jarvis_perfil.bloco_prompt())" in main_py
