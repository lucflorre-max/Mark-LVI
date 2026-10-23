"""
jarvis/brain/gate.py — portão de confirmação para as ações do Mark.

Chamado em main.py antes de rodar uma ação. Se jarvis/brain/policy.py disser
que a chamada é perigosa, a execução vai para core/confirm.py (banner
CONFIRM/CANCEL que o modelo não consegue forjar) em vez de rodar na hora.
"""

from __future__ import annotations

from typing import Callable, Optional

from jarvis.brain import policy


def guard(name: str, args: dict, run: Callable[[], str],
          confirm=None) -> Optional[str]:
    """None: pode rodar já. String: resposta para o modelo; nada foi executado.

    `confirm` é o módulo core.confirm; os testes passam um falso.
    """
    if not policy.requires_confirm(name, args):
        return None

    if confirm is None:
        from core import confirm as confirm  # noqa: PLC0415 — só no Mark

    # core.confirm guarda só UMA pendência; um segundo pedido apagaria o
    # primeiro banner sem avisar. Melhor recusar e dizer o porquê.
    waiting = confirm.pending_title()
    if waiting:
        return (
            f"[CONFIRMATION_BUSY] Nothing was done. Another action is still "
            f"waiting for the user's confirmation on screen: {waiting}. Tell "
            f"the user in one short sentence, in their language, to confirm or "
            f"cancel that one first, then ask again."
        )

    title, detail = policy.describe(name, args)
    return confirm.request(f"jarvis:{name}", title, detail, run)
