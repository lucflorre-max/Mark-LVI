"""
Plugin fino do JARVIS: rotinas recorrentes, hábitos e lembretes.

Toda a lógica fica em jarvis/brain/rotinas_service.py; este arquivo só declara
a ferramenta para o Gemini e repassa a chamada. Baseado em plugins/_template.py.
"""

from jarvis.brain import rotinas_service

PLUGIN = {
    "name": "jarvis_rotinas",
    "description": (
        "Rotinas e hábitos do usuário. 'rotina_criar' cria uma tarefa recorrente "
        "('toda segunda academia às 7h', 'pagar aluguel todo dia 5'); as tarefas "
        "aparecem sozinhas nos dias certos. 'rotinas' lista; 'rotina_alterar' e "
        "'rotina_pausar' mudam uma. 'habito_criar' acompanha um hábito com meta "
        "semanal; 'habito_registrar' marca o dia ('fiz a leitura hoje'); "
        "'habitos' mostra o progresso. 'lembretes' mostra os avisos planejados "
        "para hoje. Criar, alterar e pausar pedem um 'sim' falado: diga o que "
        "vai mudar e espere a resposta. Para tarefa única use jarvis_tarefas."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "acao": {
                "type": "STRING",
                "description": ("rotinas (padrão) | rotina_criar | rotina_alterar | "
                                "rotina_pausar | habitos | habito_criar | "
                                "habito_registrar | lembretes"),
            },
            "titulo": {"type": "STRING", "description": "Nome da rotina (ou do hábito)"},
            "rotina_id": {"type": "INTEGER", "description": "Id da rotina, quando houver mais de uma"},
            "frequencia": {"type": "STRING", "description": "diaria | dias_uteis | semanal | mensal"},
            "dias": {"type": "STRING", "description": "semanal: dias, ex.: 'seg, qua, sex'"},
            "dia_do_mes": {"type": "INTEGER", "description": "mensal: dia do mês (1 a 31)"},
            "hora": {"type": "STRING", "description": "HH:MM, se dita"},
            "prioridade": {"type": "STRING", "description": "alta | media | baixa, se dita"},
            "duracao_min": {"type": "INTEGER", "description": "Duração em minutos, se dita"},
            "projeto": {"type": "STRING", "description": "Projeto ou área, se dito"},
            "nome": {"type": "STRING", "description": "Hábito: nome, como ele disse"},
            "meta_semanal": {"type": "INTEGER", "description": "habito_criar: dias por semana (1 a 7; padrão 7)"},
            "data": {"type": "STRING", "description": "habito_registrar: hoje | ontem | AAAA-MM-DD"},
        },
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    return rotinas_service.handle(parameters, player=player)
