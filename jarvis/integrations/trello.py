"""
jarvis/integrations/trello.py — acesso ao Trello (chave + token do usuário).

Arquivo (fora do Git): config/trello.json
    {"key": "...", "token": "...", "quadro_id": "...", "quadro_nome": "...",
     "listas": {"a_fazer": "<id>", "feito": "<id>"},
     "nomes": {"a_fazer": "A fazer", "feito": "Feito"}}

A chave e o token vão no cabeçalho Authorization, nunca na URL: assim não
aparecem em logs nem nas mensagens de erro do `requests`. Nada aqui imprime
segredos. Ver docs/integracoes-trello.md.

Configurar (uma vez, no terminal do projeto):
    python -m jarvis.integrations.trello chave           # pede chave e token
    python -m jarvis.integrations.trello quadros         # lista os quadros
    python -m jarvis.integrations.trello usar "Nome do quadro"
Ver a situação:
    python -m jarvis.integrations.trello status
"""

from __future__ import annotations

import json
import os
import sys
import unicodedata
from pathlib import Path

from jarvis import config

ARQUIVO = config.ROOT / "config" / "trello.json"
API = "https://api.trello.com/1"
TIMEOUT = 15

# Nomes de lista reconhecidos ao escolher o quadro (sem acento, minúsculas).
_A_FAZER = ("a fazer", "fazer", "to do", "todo", "tarefas", "pendente", "pendentes", "backlog")
_FEITO = ("feito", "feitos", "concluido", "concluidos", "concluida", "concluidas", "done", "pronto")
LISTAS_NOVAS = {"a_fazer": "A fazer", "feito": "Feito"}


class NaoConfigurado(RuntimeError):
    """Falta chave, token ou quadro. A mensagem diz o comando para resolver."""


class ErroTrello(RuntimeError):
    """O Trello respondeu com erro. Só o código HTTP; nada de segredos."""


def _sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower().strip())
    return "".join(c for c in t if not unicodedata.combining(c))


# ── Configuração ─────────────────────────────────────────────────────────────

def ler(arquivo: Path | None = None) -> dict:
    arquivo = arquivo or ARQUIVO
    try:
        return json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def salvar(dados: dict, arquivo: Path | None = None) -> None:
    arquivo = arquivo or ARQUIVO
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    tmp = arquivo.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(arquivo)


def configurado(arquivo: Path | None = None) -> bool:
    d = ler(arquivo)
    return bool(d.get("key") and d.get("token") and (d.get("listas") or {}).get("a_fazer"))


def escolher_listas(listas: list[dict]) -> dict[str, str]:
    """{'a_fazer': id, 'feito': id} a partir das listas abertas do quadro,
    pelo nome. Falta uma → fica de fora (quem chama cria)."""
    achadas: dict[str, str] = {}
    for lista in listas:
        nome = _sem_acento(lista.get("name") or "")
        if "a_fazer" not in achadas and nome in _A_FAZER:
            achadas["a_fazer"] = lista["id"]
        elif "feito" not in achadas and nome in _FEITO:
            achadas["feito"] = lista["id"]
    return achadas


# ── Cliente ──────────────────────────────────────────────────────────────────

class TrelloClient:
    def __init__(self, dados: dict | None = None, sessao=None):
        self._dados = dados            # testes passam a configuração pronta
        self._sessao = sessao          # e um falso no lugar do requests

    @property
    def dados(self) -> dict:
        if self._dados is None:
            self._dados = ler()
        return self._dados

    def _req(self, metodo: str, caminho: str, **params):
        d = self.dados
        if not (d.get("key") and d.get("token")):
            raise NaoConfigurado(
                "O Trello ainda não foi configurado. No terminal do projeto, rode: "
                "python -m jarvis.integrations.trello chave")
        if self._sessao is None:
            import requests
            self._sessao = requests
        cabecalho = {"Authorization": f'OAuth oauth_consumer_key="{d["key"]}", '
                                      f'oauth_token="{d["token"]}"',
                     "Accept": "application/json"}
        r = self._sessao.request(metodo, API + caminho, headers=cabecalho,
                                 params=params or None, timeout=TIMEOUT)
        if r.status_code == 401:
            raise NaoConfigurado(
                "O Trello recusou a chave ou o token (401). Gere um token novo e "
                "rode: python -m jarvis.integrations.trello chave")
        if r.status_code >= 400:
            raise ErroTrello(f"Trello respondeu {r.status_code}")
        return r.json() if r.content else {}

    def lista(self, papel: str) -> str:
        """Id da lista com esse papel ('a_fazer' ou 'feito')."""
        lista = (self.dados.get("listas") or {}).get(papel)
        if not lista:
            raise NaoConfigurado(
                "Falta escolher o quadro do Trello. No terminal do projeto, rode: "
                "python -m jarvis.integrations.trello quadros")
        return lista

    def nome_lista(self, papel: str) -> str:
        return (self.dados.get("nomes") or {}).get(papel) or LISTAS_NOVAS[papel]

    # Leitura
    def eu(self) -> dict:
        return self._req("GET", "/members/me", fields="username,fullName")

    def quadros(self) -> list[dict]:
        return self._req("GET", "/members/me/boards", filter="open", fields="name,url")

    def listas(self, quadro_id: str) -> list[dict]:
        return self._req("GET", f"/boards/{quadro_id}/lists", filter="open", fields="name")

    def cartao(self, cartao_id: str) -> dict:
        return self._req("GET", f"/cards/{cartao_id}", fields="name,idList,closed,url,due")

    # Escrita. Só os serviços chamam, depois da confirmação que a regra pede.
    def criar_lista(self, quadro_id: str, nome: str) -> dict:
        return self._req("POST", "/lists", name=nome, idBoard=quadro_id, pos="bottom")

    def criar_cartao(self, nome: str, *, desc: str = "", due: str | None = None,
                     papel: str = "a_fazer") -> dict:
        params = {"idList": self.lista(papel), "name": nome, "pos": "top"}
        if desc:
            params["desc"] = desc
        if due:
            params["due"] = due
        return self._req("POST", "/cards", **params)

    def mover(self, cartao_id: str, papel: str) -> dict:
        return self._req("PUT", f"/cards/{cartao_id}", idList=self.lista(papel))

    def arquivar(self, cartao_id: str, arquivado: bool = True) -> dict:
        """Arquivar no Trello é reversível (arquivado=False devolve o cartão)."""
        return self._req("PUT", f"/cards/{cartao_id}", closed="true" if arquivado else "false")

    def anexar_link(self, cartao_id: str, url: str, nome: str) -> dict:
        return self._req("POST", f"/cards/{cartao_id}/attachments", url=url, name=nome)

    def verificar(self) -> str:
        eu = self.eu()
        quadro = self.dados.get("quadro_nome") or "nenhum quadro escolhido"
        return f"Trello conectado como {eu.get('username', '?')}; quadro: {quadro}."


# ── Comandos ─────────────────────────────────────────────────────────────────

def usar_quadro(cliente: TrelloClient, alvo: str) -> str:
    """Escolhe o quadro pelo nome ou id, acha (ou cria) as listas A fazer e
    Feito e grava em config/trello.json. Devolve o resumo para imprimir."""
    alvo_n = _sem_acento(alvo)
    quadros = cliente.quadros()
    quadro = next((q for q in quadros if q["id"] == alvo), None) or next(
        (q for q in quadros if _sem_acento(q.get("name") or "") == alvo_n), None)
    if quadro is None:
        nomes = ", ".join(q.get("name", "?") for q in quadros) or "nenhum"
        raise NaoConfigurado(f"Quadro '{alvo}' não encontrado. Seus quadros: {nomes}.")
    listas = cliente.listas(quadro["id"])
    achadas = escolher_listas(listas)
    nomes = {p: next(l["name"] for l in listas if l["id"] == i) for p, i in achadas.items()}
    criadas = []
    for papel, nome in LISTAS_NOVAS.items():
        if papel not in achadas:
            nova = cliente.criar_lista(quadro["id"], nome)
            achadas[papel], nomes[papel] = nova["id"], nome
            criadas.append(nome)
    dados = dict(cliente.dados)
    dados.update(quadro_id=quadro["id"], quadro_nome=quadro.get("name", ""),
                 listas=achadas, nomes=nomes)
    salvar(dados)
    cliente._dados = dados
    extra = f" Listas criadas: {', '.join(criadas)}." if criadas else ""
    return (f"Quadro '{dados['quadro_nome']}': tarefas novas em '{nomes['a_fazer']}', "
            f"concluídas em '{nomes['feito']}'.{extra}")


def _main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "status"
    cliente = TrelloClient()
    try:
        if cmd == "chave":
            from getpass import getpass
            print("Cole a chave (API key) e o token do Trello. Nada aparece na tela.")
            key = getpass("Chave: ").strip()
            token = getpass("Token: ").strip()
            if not (key and token):
                print("Chave ou token vazio; nada foi salvo.")
                return 1
            dados = dict(cliente.dados)
            dados.update(key=key, token=token)
            cliente._dados = dados
            print(cliente.verificar())
            salvar(dados)
            print("Salvo em config/trello.json (fora do Git). Agora rode: "
                  "python -m jarvis.integrations.trello quadros")
            return 0
        if cmd == "quadros":
            for q in cliente.quadros():
                print(f"- {q.get('name')}  ({q['id']})")
            print('Escolha um com: python -m jarvis.integrations.trello usar "Nome do quadro"')
            return 0
        if cmd == "usar" and len(argv) > 2:
            print(usar_quadro(cliente, " ".join(argv[2:])))
            return 0
        print(cliente.verificar())
        if not configurado():
            print("Falta escolher o quadro: python -m jarvis.integrations.trello quadros")
            return 1
        return 0
    except (NaoConfigurado, ErroTrello) as e:
        print(e)
        return 1
    except Exception as e:
        print(f"Falha ao falar com o Trello ({type(e).__name__}).")
        return 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
