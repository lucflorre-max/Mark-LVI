"""M2 tarefa 4: Trello com chave e token, quadro e listas (jarvis/integrations/trello.py)."""

import json

import pytest

from jarvis.integrations import trello

DADOS = {"key": "CHAVE123", "token": "TOKEN456", "quadro_id": "q1", "quadro_nome": "Pessoal",
         "listas": {"a_fazer": "L1", "feito": "L2"}, "nomes": {"a_fazer": "A fazer", "feito": "Feito"}}


class _Resp:
    def __init__(self, status=200, corpo=None):
        self.status_code, self._corpo = status, corpo if corpo is not None else {}
        self.content = b"x"

    def json(self):
        return self._corpo


class _Sessao:
    """Imita requests: guarda as chamadas e responde pela rota."""

    def __init__(self, rotas=None, status=200):
        self.chamadas, self.rotas, self.status = [], rotas or {}, status

    def request(self, metodo, url, headers=None, params=None, timeout=None):
        self.chamadas.append((metodo, url, headers, params or {}))
        caminho = url.removeprefix(trello.API)
        return _Resp(self.status, self.rotas.get((metodo, caminho), {"id": "novo"}))


@pytest.fixture
def arquivo(tmp_path, monkeypatch):
    caminho = tmp_path / "trello.json"
    monkeypatch.setattr(trello, "ARQUIVO", caminho)
    return caminho


def test_chave_e_token_vao_no_cabecalho_nunca_na_url():
    s = _Sessao()
    trello.TrelloClient(DADOS, s).criar_cartao("Pagar boleto", due="2026-10-24T14:00:00-03:00")
    metodo, url, headers, params = s.chamadas[0]
    assert metodo == "POST" and url == trello.API + "/cards"
    assert "CHAVE123" not in url and "TOKEN456" not in url
    assert "CHAVE123" not in json.dumps(params) and "TOKEN456" not in json.dumps(params)
    assert headers["Authorization"] == 'OAuth oauth_consumer_key="CHAVE123", oauth_token="TOKEN456"'
    assert params == {"idList": "L1", "name": "Pagar boleto", "pos": "top",
                      "due": "2026-10-24T14:00:00-03:00"}


def test_sem_chave_pede_o_comando_e_nao_chama_a_rede():
    s = _Sessao()
    with pytest.raises(trello.NaoConfigurado, match="trello chave"):
        trello.TrelloClient({}, s).quadros()
    assert s.chamadas == []


def test_sem_quadro_pede_para_escolher():
    s = _Sessao()
    with pytest.raises(trello.NaoConfigurado, match="trello quadros"):
        trello.TrelloClient({"key": "k", "token": "t"}, s).criar_cartao("x")
    assert s.chamadas == []


def test_401_vira_nao_configurado_e_erro_nao_mostra_segredo():
    with pytest.raises(trello.NaoConfigurado, match="401"):
        trello.TrelloClient(DADOS, _Sessao(status=401)).eu()
    with pytest.raises(trello.ErroTrello) as e:
        trello.TrelloClient(DADOS, _Sessao(status=500)).eu()
    assert "CHAVE123" not in str(e.value) and "TOKEN456" not in str(e.value)


def test_mover_e_arquivar():
    s = _Sessao()
    c = trello.TrelloClient(DADOS, s)
    c.mover("c1", "feito")
    c.arquivar("c1")
    c.arquivar("c1", False)
    assert [(m, u.removeprefix(trello.API), p) for m, u, _, p in s.chamadas] == [
        ("PUT", "/cards/c1", {"idList": "L2"}),
        ("PUT", "/cards/c1", {"closed": "true"}),
        ("PUT", "/cards/c1", {"closed": "false"}),
    ]


def test_escolher_listas_pelo_nome_sem_acento():
    listas = [{"id": "a", "name": "Ideias"}, {"id": "b", "name": "A Fazer"},
              {"id": "c", "name": "Concluído"}]
    assert trello.escolher_listas(listas) == {"a_fazer": "b", "feito": "c"}
    assert trello.escolher_listas([{"id": "x", "name": "To Do"}]) == {"a_fazer": "x"}


def test_usar_quadro_grava_e_cria_lista_que_falta(arquivo):
    s = _Sessao({
        ("GET", "/members/me/boards"): [{"id": "q9", "name": "Pessoal"}],
        ("GET", "/boards/q9/lists"): [{"id": "L5", "name": "Tarefas"}],
        ("POST", "/lists"): {"id": "L6", "name": "Feito"},
    })
    c = trello.TrelloClient({"key": "k", "token": "t"}, s)
    resumo = trello.usar_quadro(c, "pessoal")
    salvo = json.loads(arquivo.read_text(encoding="utf-8"))
    assert salvo["quadro_id"] == "q9" and salvo["listas"] == {"a_fazer": "L5", "feito": "L6"}
    assert salvo["nomes"] == {"a_fazer": "Tarefas", "feito": "Feito"}
    assert salvo["key"] == "k"                       # não perde a chave
    assert "Listas criadas: Feito" in resumo
    assert trello.configurado(arquivo)


def test_usar_quadro_inexistente_lista_os_nomes(arquivo):
    s = _Sessao({("GET", "/members/me/boards"): [{"id": "q1", "name": "Trabalho"}]})
    with pytest.raises(trello.NaoConfigurado, match="Trabalho"):
        trello.usar_quadro(trello.TrelloClient({"key": "k", "token": "t"}, s), "Casa")
    assert not arquivo.exists()


def test_configurado_exige_chave_token_e_lista(arquivo):
    assert not trello.configurado(arquivo)
    trello.salvar({"key": "k", "token": "t"}, arquivo)
    assert not trello.configurado(arquivo)
    trello.salvar(DADOS, arquivo)
    assert trello.configurado(arquivo)


def test_arquivo_de_credenciais_fica_fora_do_git():
    regras = (trello.config.ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "config/trello.json" in regras
