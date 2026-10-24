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
        "prioridade'. Se o dia não couber, ela já avisa e propõe um dia "
        "realista (Essencial / Importante / Pode esperar). 'sobrecarga' faz "
        "essa análise quando ele disser 'não vou dar conta', 'estou "
        "sobrecarregado'. 'estourou' mostra o impacto de uma tarefa que passou "
        "do tempo ('ainda não terminei', 'vou demorar mais') e sugere mover, "
        "encurtar ou adiar; pergunte quanto falta se ele não disse. Só sugere: "
        "nada é alterado sem ele pedir."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "acao": {
                "type": "STRING",
                "description": "linha_do_tempo (padrão) | sobrecarga | estourou",
            },
            "titulo": {"type": "STRING", "description": "estourou: a tarefa, como ele disse"},
            "tarefa_id": {"type": "INTEGER", "description": "estourou: id, quando houver mais de uma"},
            "minutos_restantes": {
                "type": "INTEGER",
                "description": "estourou: quanto falta, em minutos, se ele disse",
            },
            "nao_sei": {
                "type": "BOOLEAN",
                "description": "estourou: true se ele não sabe quanto falta (eu estimo)",
            },
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
