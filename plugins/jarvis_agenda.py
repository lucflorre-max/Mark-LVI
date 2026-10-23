"""
Plugin fino do JARVIS: agenda do Google Calendar.

Toda a lógica fica em jarvis/calendar/service.py; este arquivo só declara a
ferramenta para o Gemini e repassa a chamada. Baseado em plugins/_template.py.
"""

from jarvis.calendar import service

PLUGIN = {
    "name": "jarvis_agenda",
    "description": (
        "Agenda do usuário no Google Calendar. 'ver' lê os compromissos de um "
        "dia e mostra o card na tela. Use quando ele perguntar 'o que tenho "
        "hoje na agenda', 'minha agenda de amanhã', 'tenho reunião sexta'. "
        "Para tarefas e pendências use jarvis_tarefas."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "acao": {"type": "STRING", "description": "ver (padrão: ver)"},
            "data": {
                "type": "STRING",
                "description": "Dia em AAAA-MM-DD, 'hoje' ou 'amanhã' (padrão: hoje)",
            },
        },
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    return service.handle(parameters, player=player)
