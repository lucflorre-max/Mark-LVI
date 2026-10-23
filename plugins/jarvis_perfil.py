"""
Plugin fino do JARVIS: como o usuário se comunica (vocabulário e expressões).

Toda a lógica fica em jarvis/memory/perfil_service.py.
"""

from jarvis.memory import perfil_service

PLUGIN = {
    "name": "jarvis_perfil",
    "description": (
        "Perfil de comunicação do usuário: nomes, termos e expressões que ele "
        "usa e o que significam. Use quando ele perguntar o que você aprendeu "
        "sobre o jeito dele de falar, pedir para lembrar ou esquecer uma "
        "expressão ou palavra, ou listar o que está aprovado. Também pode "
        "sugerir por conta própria, no máximo uma vez por conversa e só em "
        "momento tranquilo, quando notar uma expressão que ele repete. Nunca "
        "salve sem o 'sim' dele: chame acao='lembrar' e a ferramenta cuida da "
        "pergunta."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "acao": {
                "type": "STRING",
                "description": "sugestoes | lembrar | esquecer | rejeitar | listar (padrão: sugestoes)",
            },
            "tipo": {
                "type": "STRING",
                "description": "vocabulario (nome, lugar, termo) ou expressao (jeito de falar), para lembrar",
            },
            "texto": {"type": "STRING", "description": "A palavra ou expressão, em pt-BR como ele diz"},
            "significado": {
                "type": "STRING",
                "description": "Para expressao: o que ela quer dizer, em pt-BR",
            },
        },
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    return perfil_service.handle(parameters, player=player)
