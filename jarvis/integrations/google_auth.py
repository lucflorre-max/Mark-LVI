"""
jarvis/integrations/google_auth.py — credenciais do Google (OAuth para app de computador).

Arquivos (todos fora do Git, em config/google/):
    client_secret.json   baixado do Google Cloud (ID do cliente OAuth, tipo
                         "App para computador"). Ver docs/integracoes-google.md.
    token_calendar.json  criado na primeira autorização; renovado sozinho.

Nunca imprime nem registra tokens ou segredos.

Autorizar (uma vez, abre o navegador):
    python -m jarvis.integrations.google_auth autorizar
Ver a situação:
    python -m jarvis.integrations.google_auth status
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from jarvis import config

PASTA = config.ROOT / "config" / "google"
CLIENT_SECRET = PASTA / "client_secret.json"
TOKEN_CALENDAR = PASTA / "token_calendar.json"

# Menor escopo que lê e cria eventos: só nas agendas que o usuário POSSUI.
# (calendar.events valeria para todas as agendas acessíveis.)
SCOPES_CALENDAR = ["https://www.googleapis.com/auth/calendar.events.owned"]


class NaoAutorizado(RuntimeError):
    """Falta autorizar (ou reautorizar) o acesso. A mensagem diz como."""


def _instrucoes() -> str:
    if not CLIENT_SECRET.exists():
        return ("O Google Calendar ainda não foi configurado: falta "
                "config/google/client_secret.json. Veja docs/integracoes-google.md.")
    return ("O Google Calendar ainda não foi autorizado. No terminal do projeto, "
            "rode: python -m jarvis.integrations.google_auth autorizar")


def _salvar(creds, token_path: Path) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = token_path.with_suffix(".tmp")
    tmp.write_text(creds.to_json(), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(token_path)


def credenciais(scopes: list[str] | None = None, token_path: Path | None = None,
                interativo: bool = False):
    """Credenciais válidas, renovando se preciso.

    interativo=False (uso pelo Jarvis): nunca abre navegador; sem autorização
    levanta NaoAutorizado com a instrução. interativo=True (o comando
    `autorizar`): abre o navegador para o usuário consentir.
    """
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    scopes = scopes or SCOPES_CALENDAR
    token_path = token_path or TOKEN_CALENDAR
    creds = None
    if token_path.exists():
        try:
            # Os escopos vêm do arquivo: from_authorized_user_file(…, scopes)
            # troca os do arquivo pelos pedidos e esconderia um token antigo.
            gravados = json.loads(token_path.read_text(encoding="utf-8")).get("scopes") or []
            if set(scopes) <= set(gravados):
                creds = Credentials.from_authorized_user_file(str(token_path), gravados)
        except Exception:
            creds = None                      # ilegível ou de outro escopo: refazer

    if creds is not None and not creds.valid and creds.refresh_token:
        try:
            creds.refresh(Request())
            _salvar(creds, token_path)
        except RefreshError:
            # Revogado, ou o app em modo "Teste" expirou o token (7 dias).
            creds = None

    if creds is not None and creds.valid:
        return creds

    if not interativo:
        raise NaoAutorizado(_instrucoes())
    if not CLIENT_SECRET.exists():
        raise NaoAutorizado(_instrucoes())

    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), scopes)
    creds = flow.run_local_server(port=0, open_browser=True,
                                  authorization_prompt_message="",
                                  success_message="JARVIS autorizado. Pode fechar esta aba.")
    _salvar(creds, token_path)
    return creds


def status(token_path: Path | None = None) -> dict:
    """Situação sem segredos: o que existe e se o token serve."""
    token_path = token_path or TOKEN_CALENDAR
    info = {"client_secret": CLIENT_SECRET.exists(), "token": token_path.exists(),
            "autorizado": False, "escopos": SCOPES_CALENDAR, "erro": ""}
    try:
        credenciais(token_path=token_path)
        info["autorizado"] = True
    except NaoAutorizado as e:
        info["erro"] = str(e)
    except Exception as e:
        info["erro"] = f"{type(e).__name__}"
    return info


def _main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "autorizar":
        try:
            credenciais(interativo=True)
        except NaoAutorizado as e:
            print(e)
            return 1
        print("Pronto: Google Calendar autorizado. Token salvo em config/google/ (fora do Git).")
        return 0
    info = status()
    print(f"client_secret.json: {'ok' if info['client_secret'] else 'falta'}")
    print(f"token:              {'ok' if info['token'] else 'falta'}")
    print(f"autorizado:         {'sim' if info['autorizado'] else 'não'}")
    print(f"escopo:             {', '.join(info['escopos'])}")
    if info["erro"]:
        print(info["erro"])
    return 0 if info["autorizado"] else 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
