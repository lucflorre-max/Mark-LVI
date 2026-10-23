"""
jarvis/tasks/service.py — regras da ferramenta jarvis_tarefas.

O plugin plugins/jarvis_tarefas.py só repassa a chamada para `handle()`.
As ações são implementadas na tarefa 4 da M1 (docs/plano-m1.md); até lá cada
uma responde, com honestidade, que ainda não está pronta.
"""

from __future__ import annotations

ACOES = ("criar", "listar_hoje", "concluir", "desfazer")


def handle(parameters: dict, player=None) -> str:
    """Ponto de entrada da ferramenta. Devolve a frase que o modelo vai falar.
    Nunca levanta exceção."""
    try:
        acao = str((parameters or {}).get("acao") or "criar").strip().lower()
        if acao not in ACOES:
            return (f"Ação '{acao}' desconhecida. Use uma destas: "
                    f"{', '.join(ACOES)}.")
        return (f"A ação '{acao}' de tarefas ainda não está pronta: ela chega "
                f"na próxima etapa do projeto. Nada foi salvo. Diga isso ao "
                f"usuário em uma frase.")
    except Exception as e:
        return f"Falha na ferramenta de tarefas: {e}. Nada foi salvo."
