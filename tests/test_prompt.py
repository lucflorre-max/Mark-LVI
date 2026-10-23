"""Tarefa 2: persona em core/prompt.txt."""

from pathlib import Path

PROMPT = (Path(__file__).resolve().parent.parent / "core" / "prompt.txt").read_text(encoding="utf-8")


def test_sem_rosto():
    for termo in ('"my face"', '"I look"', "animated head"):
        assert termo not in PROMPT
    assert "You have no face" in PROMPT


def test_persona_pt_br():
    assert "[PERSONA]" in PROMPT
    assert "Brazilian Portuguese (pt-BR)" in PROMPT
    assert '"senhor"' in PROMPT and '"Mestre Luc"' in PROMPT
    for palavra in ('"Confirmado"', '"Provável"', '"Incerto"'):
        assert palavra in PROMPT


def test_regras_que_conflitavam_foram_trocadas():
    assert "act rather than asking" not in PROMPT
    assert "save_memory as they come up, silently" not in PROMPT
    assert "ask in one short sentence whether you may remember it" in PROMPT


def test_marcadores_do_mark_continuam():
    for token in ("{assistant_name}", "{platform}", "{capabilities}", "{limits}"):
        assert token in PROMPT


def test_cada_mudanca_marcada():
    assert PROMPT.count("# JARVIS:") >= 7
