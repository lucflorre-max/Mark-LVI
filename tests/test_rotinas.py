"""M3 tarefa 6: recorrentes automáticas, hábitos, metas semanais e lembretes."""

import sqlite3
from datetime import date, datetime, timedelta

import pytest

from jarvis.brain import dia_service, gate, policy, rotinas_service
from jarvis.brain import habitos as hb
from jarvis.brain import lembretes as lb
from jarvis.brain import rotinas as rt
from jarvis.tasks.repository import TaskRepository
from tests._fabrica import AGORA, BRT, as_, evento, hoje, tarefa

SEXTA = AGORA.date()                      # 23/10/2026
SEGUNDA = date(2026, 10, 26)


@pytest.fixture
def repos(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.config.fuso", lambda: BRT)
    tarefas = TaskRepository(tmp_path / "t.db")
    return tarefas, rt.RotinasRepo(tmp_path / "t.db")


# ── Regras ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fala, regra", [
    (("diaria",), "diaria"), (("todo dia",), "diaria"), (("dias úteis",), "dias_uteis"),
    (("semanal", "seg, qua e sex"), "semanal:0,2,4"), (("semanal", ["sábado"]), "semanal:5"),
    (("mensal", None, 5), "mensal:5"),
])
def test_montar_regra(fala, regra):
    assert rt.montar_regra(*fala) == regra


@pytest.mark.parametrize("fala", [("anual",), ("semanal",), ("semanal", "feriado"),
                                  ("mensal",), ("mensal", None, 40)])
def test_montar_regra_invalida(fala):
    with pytest.raises(ValueError):
        rt.montar_regra(*fala)


def test_vale_em():
    assert rt.vale_em("diaria", SEXTA)
    assert rt.vale_em("dias_uteis", SEXTA) and not rt.vale_em("dias_uteis", date(2026, 10, 24))
    assert rt.vale_em("semanal:0,4", SEXTA) and not rt.vale_em("semanal:0", SEXTA)
    assert rt.vale_em("mensal:23", SEXTA)
    assert rt.vale_em("mensal:31", date(2027, 2, 28))      # mês curto: último dia
    assert not rt.vale_em("mensal:31", date(2027, 2, 27))


def test_descrever_regra_e_hora():
    assert rt.descrever_regra("semanal:0,2,4", "07:00") == "toda segunda, quarta e sexta às 07:00"
    assert rt.descrever_regra("mensal:5") == "todo dia 5 do mês"
    assert [rt.normalizar_hora(h) for h in ("7", "7h", "7h30", "07:30", None)] == \
        ["07:00", "07:00", "07:30", "07:30", None]
    with pytest.raises(ValueError):
        rt.normalizar_hora("25h")


# ── Geração automática ──────────────────────────────────────────────────────

def test_gera_a_tarefa_do_dia_uma_vez_so(repos):
    tarefas, rotinas = repos
    r = rotinas.criar("Academia", "semanal:0,4", hora="18:00", prioridade="alta", duracao_min=60)
    geradas = rt.gerar(SEXTA, tarefas, rotinas)
    assert len(geradas) == 1
    t = geradas[0].tarefa
    assert (t.titulo, t.prazo, t.prioridade, t.origem) == \
        ("Academia", "2026-10-23T18:00:00-03:00", "alta", "recorrencia")
    assert "Rotina: toda segunda e sexta às 18:00." == t.descricao
    assert rt.gerar(SEXTA, tarefas, rotinas) == []                 # idempotente
    assert len(tarefas.listar_dia(SEXTA)) == 1
    assert rotinas.ja_gerada(r.id, SEXTA)


def test_nao_gera_em_dia_que_nao_vale_nem_rotina_pausada(repos):
    tarefas, rotinas = repos
    rotinas.criar("Feira", "semanal:5")
    pausada = rotinas.criar("Pausada", "diaria")
    rotinas.alterar(pausada.id, ativa=False)
    assert rt.gerar(SEXTA, tarefas, rotinas) == []


def test_nao_recria_dias_passados(repos):
    tarefas, rotinas = repos
    rotinas.criar("Remédio", "diaria", hora="08:00")
    rt.gerar(SEXTA, tarefas, rotinas)
    assert [t.prazo[:10] for t in tarefas.listar_abertas()] == ["2026-10-23"]


def test_horario_adaptado_quando_bate_com_compromisso_e_a_regra_nao_muda(repos):
    tarefas, rotinas = repos
    r = rotinas.criar("Academia", "diaria", hora="10:00", duracao_min=60)
    g = rt.gerar(SEXTA, tarefas, rotinas, [evento("Reunião", "09:30", "11:00")])[0]
    assert g.tarefa.prazo == "2026-10-23T11:00:00-03:00" and g.adaptada_de == "10:00"
    assert "Hoje às 11:00 em vez de 10:00" in g.tarefa.descricao
    assert rotinas.obter(r.id).hora == "10:00"


def test_rotina_criada_depois_da_hora_comeca_na_proxima_vez(repos):
    tarefas, rotinas = repos
    rotinas.criar("Café", "diaria", hora="08:00")       # criada "agora", e 8h já passou
    hoje_real = datetime.now(BRT)
    agora = hoje_real.replace(hour=23, minute=0)
    assert rt.gerar(hoje_real.date(), tarefas, rotinas, agora=agora) == []
    assert rt.gerar(hoje_real.date() + timedelta(days=1), tarefas, rotinas, agora=agora)


def test_plano_do_dia_ja_traz_a_recorrente(repos, monkeypatch):
    tarefas, rotinas = repos
    rotinas.criar("Responder e-mails", "dias_uteis", hora="14:00", duracao_min=30)
    monkeypatch.setattr(dia_service, "_repo", tarefas)
    monkeypatch.setattr(dia_service, "_cliente", type("C", (), {"eventos": lambda s, a, b: []})())
    monkeypatch.setattr(dia_service, "_agora", lambda: AGORA)
    r = dia_service.handle({})
    assert "14h Responder e-mails" in r
    dia_service.handle({})
    assert len(tarefas.listar_dia(SEXTA)) == 1                      # não duplicou


# ── Hábitos ─────────────────────────────────────────────────────────────────

def _habito(meta=7):
    return rt.Habito(1, "Leitura", meta, True, "")


def test_progresso_da_semana():
    feitos = {date(2026, 10, 19), date(2026, 10, 21), SEXTA}        # seg, qua, sex
    p = hb.calcular(_habito(4), feitos, SEXTA)
    assert (p.feitos_semana, p.faltam, p.feito_hoje, p.dias_restantes) == (3, 1, True, 3)
    assert not p.precisa_hoje


def test_precisa_hoje_so_quando_a_meta_fica_em_risco():
    # meta 5, feitos 2 até sexta, sem marcar hoje: faltam 3 e restam 3 dias (sex, sáb, dom)
    p = hb.calcular(_habito(5), {date(2026, 10, 19), date(2026, 10, 20)}, SEXTA)
    assert p.precisa_hoje
    # meta 3 com os mesmos 2: falta 1 e restam 3 dias → sem cobrança
    assert not hb.calcular(_habito(3), {date(2026, 10, 19), date(2026, 10, 20)}, SEXTA).precisa_hoje


def test_sequencia_de_semanas_e_dias_seguidos():
    feitos = set()
    for semana in (date(2026, 10, 5), date(2026, 10, 12)):            # 2 semanas com 3 dias
        feitos |= {semana + timedelta(days=i) for i in range(3)}
    feitos |= {date(2026, 10, 21), date(2026, 10, 22)}               # qua e qui desta semana
    p = hb.calcular(_habito(3), feitos, SEXTA)
    assert p.sequencia_semanas == 2              # as duas passadas; a atual ainda não bateu
    assert p.dias_seguidos == 2                  # qua + qui (hoje ainda não acabou)
    assert hb.calcular(_habito(3), feitos | {SEXTA}, SEXTA).sequencia_semanas == 3
    assert hb.calcular(_habito(3), feitos | {SEXTA}, SEXTA).dias_seguidos == 3


def test_sequencia_conta_semanas_seguidas_batidas():
    feitos = {date(2026, 10, d) for d in (6, 7, 13, 14, 20, 21)}     # 2 por semana, 3 semanas
    assert hb.calcular(_habito(2), feitos, SEXTA).sequencia_semanas == 3   # 2 passadas + a atual
    assert hb.calcular(_habito(2), feitos - {date(2026, 10, 14)}, SEXTA).sequencia_semanas == 1


def test_linha_do_habito():
    p = hb.calcular(_habito(3), {date(2026, 10, 21), date(2026, 10, 22), SEXTA}, SEXTA)
    assert hb.linha(p) == "✔ Leitura: 3/3 na semana (meta batida) · 1 semana seguida, 3 dias seguidos"


# ── Lembretes ───────────────────────────────────────────────────────────────

def _horas(lembretes):
    return [f"{x.quando:%H:%M}" for x in lembretes]


@pytest.mark.parametrize("prio, esperado", [
    ("alta", ["13:00", "13:45", "14:00"]),
    ("media", ["13:45", "14:00"]),
    (None, ["13:45", "14:00"]),
    ("baixa", ["14:00"]),
])
def test_antecedencia_conforme_a_prioridade(prio, esperado):
    assert _horas(lb.planejar([tarefa(prazo=hoje("14:00"), prioridade=prio)], AGORA)) == esperado


def test_nao_lembra_do_que_ja_passou_nem_de_outro_dia():
    ts = [tarefa(prazo=hoje("09:00"), prioridade="alta"),
          tarefa(prazo="2026-10-24T10:00:00-03:00", prioridade="alta"),
          tarefa(prazo=hoje("09:50"), prioridade="alta")]               # 8h50 já passou
    assert _horas(lb.planejar(ts, AGORA)) == ["09:35", "09:50"]


def test_silencio_de_noite_antecipa():
    t = tarefa("Remédio", prazo=hoje("22:30"), prioridade="alta")
    lembretes = lb.planejar([t], AGORA)
    assert _horas(lembretes) == ["21:30", "21:45"]
    assert not any(lb.em_silencio(x.quando) for x in lembretes)


def test_silencio_de_manha_espera_as_7():
    cedo = AGORA.replace(hour=6, minute=0)
    t = tarefa("Ônibus", prazo=hoje("07:30"), prioridade="alta")
    assert _horas(lb.planejar([t], cedo)) == ["07:00", "07:15", "07:30"]


def test_durante_compromisso_antecipa_o_aviso():
    t = tarefa("Ligar", prazo=hoje("11:00"), prioridade="media")
    lembretes = lb.planejar([t], AGORA, [evento("Reunião", "10:30", "11:00")])
    assert _horas(lembretes) == ["10:25", "11:00"]


def test_na_hora_de_prioridade_alta_nao_espera_compromisso():
    t = tarefa("Remédio", prazo=hoje("10:45"), prioridade="alta")
    lembretes = lb.planejar([t], AGORA, [evento("Reunião", "10:30", "11:00")])
    assert "10:45" in _horas(lembretes)


def test_avisos_proximos_viram_um_so():
    ts = [tarefa("A", prazo=hoje("10:00"), prioridade="baixa"),
          tarefa("B", prazo=hoje("10:05"), prioridade="baixa")]
    lembretes = lb.planejar(ts, AGORA)
    assert len(lembretes) == 1 and lembretes[0].itens == ["A", "B"]


def test_limite_por_hora_tira_primeiro_os_de_prioridade_baixa():
    ts = [tarefa(f"Baixa {m}", prazo=hoje(f"10:{m:02d}"), prioridade="baixa") for m in (0, 15, 30, 45)]
    ts.append(tarefa("Urgente", prazo=hoje("10:50"), prioridade="alta"))
    lembretes = lb.planejar(ts, AGORA)
    na_hora = [x for x in lembretes if as_("10:00") <= x.quando <= as_("10:59")]
    assert any("Urgente" in x.itens for x in lembretes)              # alta sempre fica
    assert sum(1 for x in na_hora if x.prioridade == "baixa") <= lb.MAX_POR_HORA


def test_limite_por_dia():
    ts = [tarefa(f"T{h}", prazo=hoje(f"{h:02d}:00"), prioridade="baixa") for h in range(10, 22)]
    ts += [tarefa(f"U{h}", prazo=hoje(f"{h:02d}:30"), prioridade="baixa") for h in range(10, 21)]
    assert len(lb.planejar(ts, AGORA)) <= lb.MAX_POR_DIA


def test_sem_hora_so_alta_e_uma_vez_as_14():
    ts = [tarefa("Alta", prazo="2026-10-23", prioridade="alta"),
          tarefa("Média", prazo="2026-10-23", prioridade="media")]
    lembretes = lb.planejar(ts, AGORA)
    assert _horas(lembretes) == ["14:00"] and lembretes[0].texto() == "Ainda para hoje: Alta"


def test_habito_vira_um_aviso_por_dia():
    lembretes = lb.planejar([], AGORA, habitos_hoje=["Leitura", "Alongar"])
    assert _horas(lembretes) == ["19:00"]
    assert lembretes[0].texto() == "Hábito de hoje: Leitura, Alongar"


def test_ignorado_repete_e_depois_pergunta_se_reagenda():
    t = tarefa("Relatório", prazo=hoje("10:00"), prioridade="alta", duracao_min=60)
    ultimo = as_("10:00")
    assert lb.depois_de_ignorado(t, 1, ultimo, AGORA).quando == as_("10:30")
    assert lb.depois_de_ignorado(t, 2, ultimo, AGORA).acao == "repetir"
    prox = lb.depois_de_ignorado(t, 3, ultimo, AGORA, [evento("Reunião", "09:30", "11:00")])
    assert prox.acao == "perguntar_reagendar" and prox.sugestao == as_("11:00")


@pytest.mark.parametrize("prio, vezes, acao", [("media", 1, "repetir"), ("media", 2, "parar"),
                                               ("baixa", 1, "parar")])
def test_ignorado_conforme_a_prioridade(prio, vezes, acao):
    t = tarefa(prazo=hoje("10:00"), prioridade=prio)
    assert lb.depois_de_ignorado(t, vezes, as_("10:00"), AGORA).acao == acao


def test_repeticao_nao_cai_no_silencio():
    t = tarefa(prazo=hoje("21:50"), prioridade="alta")
    prox = lb.depois_de_ignorado(t, 1, as_("21:50"), AGORA)
    assert prox.quando == datetime(2026, 10, 24, 7, 0, tzinfo=BRT)


# ── Serviço ─────────────────────────────────────────────────────────────────

class Relogio:
    t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def servico(repos, monkeypatch):
    tarefas, rotinas = repos
    monkeypatch.setattr(rotinas_service, "_tarefas", tarefas)
    monkeypatch.setattr(rotinas_service, "_rotinas", rotinas)
    monkeypatch.setattr(rotinas_service, "_agora", lambda: AGORA)
    monkeypatch.setattr(rotinas_service, "_eventos", lambda agora: ([], ""))
    rel = Relogio()
    monkeypatch.setattr(gate, "_relogio", rel)
    gate.reset()
    yield tarefas, rotinas, rel
    gate.reset()


def _sim(rel):
    rel.t += 5
    gate.ouvir("pode sim")


def test_criar_rotina_espera_o_sim_falado(servico):
    tarefas, rotinas, rel = servico
    pedido = {"acao": "rotina_criar", "titulo": "Academia", "frequencia": "semanal",
              "dias": "seg, sex", "hora": "18h", "prioridade": "alta"}
    r = rotinas_service.handle(pedido)
    assert r.startswith("[VOICE_CONFIRM]") and "toda segunda e sexta às 18:00" in r
    assert rotinas.listar() == []                                   # nada criado
    _sim(rel)
    r = rotinas_service.handle(pedido)
    assert r.startswith("Rotina criada") and "A de hoje já está nas tarefas" in r
    assert len(rotinas.listar()) == 1 and len(tarefas.listar_dia(SEXTA)) == 1


def test_criar_rotina_com_dado_faltando_pergunta_antes_do_sim(servico):
    r = rotinas_service.handle({"acao": "rotina_criar", "titulo": "Academia"})
    assert "Falta a frequência" in r and "VOICE_CONFIRM" not in r
    r = rotinas_service.handle({"acao": "rotina_criar", "titulo": "X", "frequencia": "semanal"})
    assert "precisa dos dias" in r


def test_alterar_mostra_de_para_e_espera_o_sim(servico):
    _, rotinas, rel = servico
    r0 = rotinas.criar("Academia", "semanal:0", hora="07:00")
    pedido = {"acao": "rotina_alterar", "titulo": "academia", "hora": "08:00"}
    r = rotinas_service.handle(pedido)
    assert r.startswith("[VOICE_CONFIRM]") and "às 07:00" in r and "às 08:00" in r
    assert rotinas.obter(r0.id).hora == "07:00"
    _sim(rel)
    assert rotinas_service.handle(pedido).startswith("Rotina alterada")
    assert rotinas.obter(r0.id).hora == "08:00"


def test_dizer_nao_cancela(servico):
    _, rotinas, rel = servico
    r0 = rotinas.criar("Academia", "diaria")
    pedido = {"acao": "rotina_pausar", "rotina_id": r0.id}
    rotinas_service.handle(pedido)
    rel.t += 5
    gate.ouvir("não, deixa")
    assert rotinas_service.handle(pedido).startswith("[VOICE_DECLINED]")
    assert rotinas.obter(r0.id).ativa


def test_listar_rotinas(servico):
    _, rotinas, _ = servico
    rotinas.criar("Remédio", "diaria", hora="08:00", prioridade="alta")
    r = rotinas_service.handle({})
    assert "“Remédio” todo dia às 08:00 · prioridade alta" in r


def test_habito_criar_registrar_e_progresso(servico):
    _, rotinas, rel = servico
    pedido = {"acao": "habito_criar", "nome": "Leitura", "meta_semanal": 4}
    assert rotinas_service.handle(pedido).startswith("[VOICE_CONFIRM]")
    _sim(rel)
    assert "4× por semana" in rotinas_service.handle(pedido)
    r = rotinas_service.handle({"acao": "habito_registrar", "nome": "leitura"})  # direto
    assert r.startswith("Marcado: ✔ Leitura: 1/4")
    assert "(já estava marcado)" in rotinas_service.handle({"acao": "habito_registrar",
                                                            "nome": "Leitura", "data": "hoje"})
    assert "Leitura: 1/4" in rotinas_service.handle({"acao": "habitos"})


def test_registrar_habito_desconhecido_oferece_criar(servico):
    assert "habito_criar" in rotinas_service.handle({"acao": "habito_registrar", "nome": "Yoga"})


def test_registrar_no_futuro_recusa(servico):
    _, rotinas, _ = servico
    rotinas.criar_habito("Leitura")
    assert "Data inválida" in rotinas_service.handle({"acao": "habito_registrar",
                                                      "nome": "Leitura", "data": "2026-10-30"})


def test_lembretes_de_hoje(servico):
    tarefas, rotinas, _ = servico
    tarefas.adicionar("Dentista", prazo="2026-10-23T14:00", prioridade="alta")
    rotinas.criar_habito("Leitura", 7)        # diário, não feito hoje: meta em risco
    r = rotinas_service.handle({"acao": "lembretes"})
    assert "13h Dentista" in r and "19h Hábito de hoje: Leitura" in r


def test_politica():
    for acao in ("rotinas", "habitos", "habito_registrar", "lembretes"):
        assert policy.nivel("jarvis_rotinas", {"acao": acao}) == policy.DIRETO
    for acao in ("rotina_criar", "rotina_alterar", "rotina_pausar", "habito_criar"):
        assert policy.nivel("jarvis_rotinas", {"acao": acao}) == policy.VOZ
    assert policy.nivel("jarvis_rotinas", {"acao": "apagar_tudo"}) == policy.CLIQUE


# ── Não rastrear foco, pausas nem interrupções (§5.2) ───────────────────────

def test_banco_nao_guarda_foco_pausas_nem_interrupcoes(repos):
    tarefas, _ = repos
    conn = sqlite3.connect(tarefas.path)
    try:
        nomes = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        colunas = [c[1] for t in nomes for c in conn.execute(f"PRAGMA table_info({t})")]
    finally:
        conn.close()
    proibidas = ("foco", "focus", "pausa", "pause", "interrup", "inicio_real", "started")
    assert not [n for n in nomes + colunas if any(p in n.lower() for p in proibidas)]
