"""
Plugin fino do JARVIS: tarefas por voz.

Toda a lógica fica em jarvis/tasks/service.py; este arquivo só declara a
ferramenta para o Gemini e repassa a chamada. Baseado em plugins/_template.py.
"""

from jarvis.tasks import service

PLUGIN = {
    "name": "jarvis_tarefas",
    "description": (
        "Tarefas e pendências do usuário: anotar uma tarefa nova, listar as de "
        "hoje, concluir ou desfazer a última alteração. Use quando ele disser "
        "'anota aí', 'me lembra de', 'tenho que', 'o que tenho hoje', "
        "'terminei', 'desfaz'. Para avisos com hora marcada no Windows use "
        "`reminder`, não esta ferramenta. Extraia os campos da fala; deixe "
        "vazio o que ele não disse, nunca invente prazo, prioridade ou duração."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "acao": {
                "type": "STRING",
                "description": "criar | listar_hoje | concluir | desfazer (padrão: criar)",
            },
            "titulo": {"type": "STRING", "description": "O que precisa ser feito, curto"},
            "prazo": {
                "type": "STRING",
                "description": "Data e hora no formato ISO 8601 (AAAA-MM-DDTHH:MM), se dita",
            },
            "prioridade": {"type": "STRING", "description": "alta | media | baixa, se dita"},
            "duracao_min": {"type": "INTEGER", "description": "Duração estimada em minutos, se dita"},
            "projeto": {"type": "STRING", "description": "Projeto ou área, se dito"},
            "contexto": {"type": "STRING", "description": "Detalhes extras da fala"},
            "confirmado": {
                "type": "BOOLEAN",
                "description": "true só depois que o usuário disse 'sim' ao resumo",
            },
            "tarefa_id": {"type": "INTEGER", "description": "Id da tarefa, para concluir"},
        },
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    return service.handle(parameters, player=player)
