"""
jarvis/brain/gate.py — portão de confirmação para as ações do Mark e do JARVIS.

Chamado antes de rodar uma ação. jarvis/brain/policy.py decide o nível:

    DIRETO  roda na hora.
    CLIQUE  vai para core/confirm.py (banner CONFIRM/CANCEL que o modelo não
            consegue forjar).
    VOZ     espera um "sim" FALADO. O pedido fica guardado e o modelo é
            instruído a perguntar; a ação só roda quando a mesma chamada volta
            depois que a transcrição da voz do usuário (main.py chama `ouvir`)
            registrou uma resposta afirmativa. O "sim" não é um parâmetro que
            o modelo preenche: vem do microfone.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Optional

from jarvis.brain import policy

VOZ_TIMEOUT = 60.0     # segundos para o usuário responder
# O fim da transcrição do PEDIDO pode chegar logo depois de ele ser guardado
# ("…pode escrever teste"). Uma resposta de verdade só vem depois de o modelo
# falar a pergunta, então o que chega antes disto não conta como "sim".
VOZ_IGNORA_INICIO = 1.5

_SIM = {"sim", "pode", "podes", "confirma", "confirmo", "confirmado", "isso",
        "ok", "okay", "claro", "manda", "faz", "faca", "vai", "positivo",
        "beleza", "certo", "fechado", "autorizo", "yes"}
_NAO = {"nao", "cancela", "cancelar", "cancele", "pare", "espera", "espere",
        "negativo", "nunca", "no", "aguarda", "aguarde"}


@dataclass
class _PedidoVoz:
    nome: str
    args: dict
    em: float
    ouvido: list[tuple[float, str]] = field(default_factory=list)

    def resposta(self) -> str:
        return " ".join(t for quando, t in self.ouvido
                        if quando - self.em >= VOZ_IGNORA_INICIO)


_pedido: Optional[_PedidoVoz] = None
_lock = threading.Lock()
_relogio: Callable[[], float] = time.monotonic   # trocável nos testes


def _normalizar(texto: str) -> list[str]:
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.findall(r"[a-z]+", sem_acento)


def resposta_afirmativa(texto: str) -> bool:
    """True para "sim", "pode", "pode sim, manda"…; False se houver um "não",
    "cancela", "espera"… em qualquer parte."""
    palavras = _normalizar(texto)
    if any(p in _NAO for p in palavras):
        return False
    return any(p in _SIM for p in palavras)


def ouvir(texto: str) -> None:
    """Chamado pelo main.py a cada trecho transcrito da voz do usuário."""
    with _lock:
        if _pedido is not None and texto:
            _pedido.ouvido.append((_relogio(), texto))


def _mesma_chamada(a: dict, b: dict) -> bool:
    def limpo(d):
        return {k: str(v).strip() for k, v in (d or {}).items()
                if v not in (None, "", [], {}) and k != "confirmado"}
    return limpo(a) == limpo(b)


def _guarda_voz(name: str, args: dict) -> Optional[str]:
    global _pedido
    agora = _relogio()
    with _lock:
        p = _pedido
        if (p is not None and p.nome == name and _mesma_chamada(p.args, args)
                and agora - p.em <= VOZ_TIMEOUT and p.resposta()):
            _pedido = None
            if resposta_afirmativa(p.resposta()):
                return None                                # liberado
            return ("[VOICE_DECLINED] Nothing was done: the user did not say "
                    "yes. Acknowledge in one short sentence and drop it.")
        _pedido = _PedidoVoz(nome=name, args=dict(args), em=agora)

    title, detail = policy.describe(name, args)
    return (f"[VOICE_CONFIRM] Nothing was done yet. In one short sentence, in "
            f"the user's language, say exactly what you are about to do "
            f"({title}; {detail}) and ask if you may. If the user says yes, call "
            f"{name} again with exactly the same arguments. If they say no, drop "
            f"it.")


def guard(name: str, args: dict, run: Callable[[], str],
          confirm=None) -> Optional[str]:
    """None: pode rodar já. String: resposta para o modelo; nada foi executado.

    `confirm` é o módulo core.confirm; os testes passam um falso.
    """
    nivel = policy.nivel(name, args)
    if nivel == policy.DIRETO:
        return None
    if nivel == policy.VOZ:
        return _guarda_voz(name, args)

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


def reset() -> None:
    """Esquece o pedido por voz pendente (testes)."""
    global _pedido
    with _lock:
        _pedido = None
