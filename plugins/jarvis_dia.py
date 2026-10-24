"""
Plugin fino do JARVIS: plano do dia e prioridades.

Toda a lógica fica em jarvis/brain/dia_service.py; este arquivo só declara a
ferramenta para o Gemini e repassa a chamada. Baseado em plugins/_template.py.
"""

from jarvis.brain import dia_service

PLUGIN = {
    "name": "jarvis_dia",
    "description": (
        "Plano do dia do usuário, com prioridade calculada por prazo, impacto, "
        "contexto e esforço. 'linha_do_tempo' mostra no card o Agora, o Depois "
        "e o Se der tempo, juntando tarefas e compromissos. Use quando ele "
        "perguntar 'o que faço agora', 'como está meu dia', 'qual a "
        "prioridade'. Só sugere: nada é alterado sem ele pedir."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "acao": {"type": "STRING", "description": "linha_do_tempo (padrão)"},
            "contexto": {
                "type": "STRING",
                "description": "Onde ele está ou o que está fazendo, se disse (ex.: trabalho, casa)",
            },
        },
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    return dia_service.handle(parameters, player=player)
