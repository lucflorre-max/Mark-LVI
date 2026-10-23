from datetime import datetime

from jarvis import config
from jarvis.memory import transcript


def _ligar(monkeypatch, tmp_path, ligado=True):
    monkeypatch.setattr(config, "_keys", lambda: {} if ligado else {"transcript_enabled": False})
    monkeypatch.setattr(transcript, "_DIR", tmp_path)


def test_grava_conversa_do_dia(monkeypatch, tmp_path):
    _ligar(monkeypatch, tmp_path)
    transcript.user("Jarvis, abra o Bloco de Notas")
    transcript.tool("open_app", {"app_name": "Notepad"})
    transcript.result("open_app", "status=started")
    transcript.assistant("JARVIS", "Abrindo, senhor.")

    files = list(tmp_path.glob("*.md"))
    assert len(files) == 1
    assert files[0].name == f"{datetime.now():%Y-%m-%d}.md"
    text = files[0].read_text(encoding="utf-8")
    assert text.startswith("# Conversas de ")
    assert "**Você:** Jarvis, abra o Bloco de Notas" in text
    assert "🔧 `open_app` {'app_name': 'Notepad'}" in text
    assert "↳ `open_app` → status=started" in text
    assert "**JARVIS:** Abrindo, senhor." in text
    assert text.count("# Conversas") == 1


def test_desligada_nao_grava(monkeypatch, tmp_path):
    _ligar(monkeypatch, tmp_path, ligado=False)
    transcript.user("oi")
    assert list(tmp_path.iterdir()) == []


def test_corta_textos_longos_e_quebras_de_linha(monkeypatch, tmp_path):
    _ligar(monkeypatch, tmp_path)
    transcript.result("web_search", "linha1\nlinha2 " + "x" * 2000)
    line = next(tmp_path.glob("*.md")).read_text(encoding="utf-8").splitlines()[-1]
    assert "linha1 linha2" in line
    assert line.endswith("…")
    assert len(line) < 700


def test_falha_de_disco_nao_derruba(monkeypatch, tmp_path):
    _ligar(monkeypatch, tmp_path / "arquivo.txt")
    (tmp_path / "arquivo.txt").write_text("não é pasta")
    transcript.user("oi")   # não pode levantar exceção
