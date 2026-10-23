"""M2 tarefa 1: acesso ao Google Calendar (jarvis/integrations/google_auth.py)."""

import json
import subprocess
from pathlib import Path

import pytest

from jarvis.calendar.client import CalendarClient
from jarvis.integrations import google_auth

ROOT = Path(__file__).resolve().parent.parent
ESCOPO = "https://www.googleapis.com/auth/calendar.events.owned"


def _token(path: Path, scopes=(ESCOPO,), expirado=False):
    dados = {
        "token": "tok-ACESSO-falso", "refresh_token": "tok-REFRESH-falso",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "id.apps.googleusercontent.com", "client_secret": "seg-falso",
        "scopes": list(scopes),
        "expiry": "2000-01-01T00:00:00Z" if expirado else "2999-01-01T00:00:00Z",
    }
    path.write_text(json.dumps(dados), encoding="utf-8")


def test_menor_escopo():
    assert google_auth.SCOPES_CALENDAR == [ESCOPO]


@pytest.mark.parametrize("arquivo", ["config/google/client_secret.json",
                                     "config/google/token_calendar.json"])
def test_credenciais_fora_do_git(arquivo):
    r = subprocess.run(["git", "check-ignore", "--no-index", "-v", arquivo],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.startswith(".gitignore:")


def test_sem_token_nao_abre_navegador(tmp_path, monkeypatch):
    monkeypatch.setattr(google_auth, "CLIENT_SECRET", tmp_path / "client_secret.json")
    with pytest.raises(google_auth.NaoAutorizado, match="client_secret.json"):
        google_auth.credenciais(token_path=tmp_path / "token.json")
    (tmp_path / "client_secret.json").write_text("{}")
    with pytest.raises(google_auth.NaoAutorizado, match="autorizar"):
        google_auth.credenciais(token_path=tmp_path / "token.json")


def test_token_valido(tmp_path):
    _token(tmp_path / "t.json")
    creds = google_auth.credenciais(token_path=tmp_path / "t.json")
    assert creds.valid


def test_token_de_outro_escopo_e_recusado(tmp_path):
    _token(tmp_path / "t.json", scopes=("https://www.googleapis.com/auth/drive",))
    with pytest.raises(google_auth.NaoAutorizado):
        google_auth.credenciais(token_path=tmp_path / "t.json")


def test_token_expirado_e_renovado_e_salvo(tmp_path, monkeypatch):
    from google.oauth2.credentials import Credentials
    _token(tmp_path / "t.json", expirado=True)

    def renovar(self, request):
        self.token = "tok-NOVO"
        import datetime
        self.expiry = datetime.datetime(2999, 1, 1)
    monkeypatch.setattr(Credentials, "refresh", renovar)
    creds = google_auth.credenciais(token_path=tmp_path / "t.json")
    assert creds.valid
    assert json.loads((tmp_path / "t.json").read_text())["token"] == "tok-NOVO"


def test_renovacao_recusada_pede_nova_autorizacao(tmp_path, monkeypatch):
    from google.auth.exceptions import RefreshError
    from google.oauth2.credentials import Credentials
    _token(tmp_path / "t.json", expirado=True)
    monkeypatch.setattr(Credentials, "refresh",
                        lambda self, r: (_ for _ in ()).throw(RefreshError("invalid_grant")))
    monkeypatch.setattr(google_auth, "CLIENT_SECRET", tmp_path / "cs.json")
    (tmp_path / "cs.json").write_text("{}")
    with pytest.raises(google_auth.NaoAutorizado, match="autorizar"):
        google_auth.credenciais(token_path=tmp_path / "t.json")


def test_status_nunca_mostra_segredos(tmp_path, capsys):
    _token(tmp_path / "t.json")
    info = google_auth.status(token_path=tmp_path / "t.json")
    assert info["autorizado"] is True
    texto = json.dumps(info)
    assert "tok-" not in texto and "seg-falso" not in texto


def test_cliente_verifica_agenda_principal():
    chamadas = []

    class Falso:
        def events(self):
            return self

        def list(self, **kw):
            chamadas.append(kw)
            return self

        def execute(self):
            return {"items": []}

    out = CalendarClient(service=Falso()).verificar()
    assert "conectado" in out
    assert chamadas[0]["calendarId"] == "primary"
