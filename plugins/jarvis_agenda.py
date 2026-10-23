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
        "'criar' marca um compromisso: extraia título, início e, se dito, fim "
        "ou duração e local; nunca invente horário. A ferramenta mostra a "
        "mudança e o usuário confirma na tela; não diga que foi criado antes "
        "disso. Para tarefas e pendências use jarvis_tarefas."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "acao": {"type": "STRING", "description": "ver | criar (padrão: ver)"},
            "data": {
                "type": "STRING",
                "description": "ver: dia em AAAA-MM-DD, 'hoje' ou 'amanhã' (padrão: hoje)",
            },
            "titulo": {"type": "STRING", "description": "criar: nome do compromisso, curto"},
            "inicio": {
                "type": "STRING",
                "description": "criar: AAAA-MM-DDTHH:MM, ou AAAA-MM-DD para o dia inteiro",
            },
            "fim": {"type": "STRING", "description": "criar: AAAA-MM-DDTHH:MM, se dito"},
            "duracao_min": {"type": "INTEGER", "description": "criar: duração em minutos, se dita"},
            "local": {"type": "STRING", "description": "criar: lugar ou link, se dito"},
            "descricao": {"type": "STRING", "description": "criar: detalhes extras da fala"},
        },
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    return service.handle(parameters, player=player)
