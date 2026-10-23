"""
jarvis/calendar/client.py — acesso ao Google Calendar (agenda principal).

Só leitura e criação nesta etapa; nada aqui pede confirmação: quem decide se
uma alteração pode acontecer é o serviço que chama (regra §11 do
documento-mestre: alteração de agenda mostra a mudança e pede confirmação).
"""

from __future__ import annotations

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

    def verificar(self) -> str:
        """Confirma que o escopo dá acesso à agenda principal (1 evento lido)."""
        self._api().events().list(calendarId=AGENDA, maxResults=1,
                                  singleEvents=True).execute()
        return "Google Calendar conectado: leitura da agenda principal ok."
