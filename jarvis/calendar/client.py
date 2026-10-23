"""
jarvis/calendar/client.py — acesso ao Google Calendar (agenda principal).

Só leitura e criação nesta etapa; nada aqui pede confirmação: quem decide se
uma alteração pode acontecer é o serviço que chama (regra §11 do
documento-mestre: alteração de agenda mostra a mudança e pede confirmação).
"""

from __future__ import annotations

from datetime import datetime

from jarvis.integrations import google_auth

AGENDA = "primary"


class CalendarClient:
    def __init__(self, service=None):
        self._service = service          # testes passam um falso

    def _api(self):
        if self._service is None:
            from googleapiclient.discovery import build
            creds = google_auth.credenciais()   # NaoAutorizado se faltar
            self._service = build("calendar", "v3", credentials=creds,
                                  cache_discovery=False)
        return self._service

    def eventos(self, inicio: datetime, fim: datetime) -> list[dict]:
        """Eventos da agenda principal que tocam [inicio, fim), já expandidos
        (recorrentes viram ocorrências) e em ordem de início."""
        itens, pagina = [], None
        while True:
            r = self._api().events().list(
                calendarId=AGENDA, timeMin=inicio.isoformat(),
                timeMax=fim.isoformat(), singleEvents=True,
                orderBy="startTime", maxResults=250, pageToken=pagina,
            ).execute()
            itens.extend(r.get("items", []))
            pagina = r.get("nextPageToken")
            if not pagina:
                return itens

    def criar(self, corpo: dict) -> dict:
        """Insere um evento na agenda principal. Só o serviço chama, e só
        depois da confirmação do usuário."""
        return self._api().events().insert(calendarId=AGENDA, body=corpo).execute()

    def verificar(self) -> str:
        """Confirma que o escopo dá acesso à agenda principal (1 evento lido)."""
        self._api().events().list(calendarId=AGENDA, maxResults=1,
                                  singleEvents=True).execute()
        return "Google Calendar conectado: leitura da agenda principal ok."
