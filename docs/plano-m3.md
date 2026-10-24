# Meta 3: Prioridades

Fonte: pedido do usuário em 23/10/2026 e o documento-mestre (seções 5.2 e 5.3, mais §2, §11, §12.3 e §19 item 2). Não havia um "plano da Meta 3" escrito; este arquivo é ele.

**Entrega:** Agora / Depois / Se der tempo, sobrecarga, replanejamento e rotinas. Código em `jarvis/brain/`. Uma tarefa por vez, com testes e commit.

## Regras do documento-mestre

- Prioridade combina **prazo, impacto, contexto e esforço** (§5.2).
- Visualização preferida: linha do tempo **Agora / Depois / Se der tempo** (§5.2).
- Sobrecarga: avisar, classificar em **Essencial / Importante / Pode esperar** e propor um dia mais realista (§5.2).
- Tarefa que estourou: avisar o impacto e sugerir **mover, encurtar ou adiar**, **sem alterar sozinho** (§5.2). Começou e não terminou: perguntar quanto falta (§5.2).
- Espaço livre: priorizar a **pendência atrasada que couber**, combinando importância, prazo e tempo disponível (§5.2).
- Recorrentes criadas automaticamente; **mudança real exige confirmação** (§5.3).
- Hábitos, metas semanais e sequências **sem excesso de notificações** (§5.3, §2, §12.3).
- Lembretes antecipados, repetidos quando preciso e adaptados à prioridade; tarefa importante ignorada: lembrar de novo e sugerir novo horário (§5.3).
- **Não rastrear foco, pausas nem interrupções** (§5.2, §20). Nada no banco guarda isso; o replanejamento pergunta ao usuário quanto falta em vez de medir.

## Tarefas

| # | Tarefa | Situação |
| --- | --- | --- |
| 1 | Motor de prioridade: prazo + impacto + contexto + esforço | **feita** (23/10/2026): `jarvis/brain/prioridade.py` |
| 2 | Linha do tempo Agora / Depois / Se der tempo no card | **código e testes prontos** (23/10/2026): `plano.py` encaixa no tempo livre, `linha_do_tempo.py` separa as faixas e faz o card; ferramenta `jarvis_dia` ação `linha_do_tempo`; falta o teste por voz |
| 3 | Sobrecarga: Essencial / Importante / Pode esperar e proposta de dia realista | **código e testes prontos** (23/10/2026): `jarvis/brain/sobrecarga.py`; a linha do tempo já avisa e propõe; ação `sobrecarga`; falta o teste por voz |
| 4 | Tarefa que estourou: impacto e sugestão de mover, encurtar ou adiar, sem aplicar | **código e testes prontos** (23/10/2026): `jarvis/brain/replanejar.py`; ação `estourou` pergunta quanto falta (ou estima com `nao_sei`); falta o teste por voz |
| 5 | Espaço livre: sugerir a pendência atrasada que couber | **código e testes prontos** (23/10/2026): `jarvis/brain/espaco_livre.py`; ação `espaco_livre` (minutos ditos ou até o próximo compromisso); falta o teste por voz |
| 6 | Recorrentes automáticas, hábitos e metas semanais, lembretes conforme a prioridade sem excesso | **código e testes prontos** (23/10/2026): `rotinas.py`, `habitos.py`, `lembretes.py`; ferramenta `jarvis_rotinas`; falta o teste por voz e a entrega dos avisos na tela (Meta 4) |

## Decisões

- **Impacto = prioridade dita pelo usuário** (alta / média / baixa). Sem prioridade conta como média.
- **Contexto = onde o usuário está ou o que está fazendo** ("trabalho", "casa", nome de projeto), dito na conversa. A tarefa combina quando o projeto ou a descrição dela tem essa palavra. Sem contexto dito, o fator fica neutro para todas.
- **Esforço = duração estimada.** Tarefa curta sobe um pouco (cabe em brechas); sem duração conta como 30 min.
- **Pesos:** prazo 40 %, impacto 35 %, esforço 15 %, contexto 10 %. Atrasada tem o fator de prazo máximo.
- **Plano do dia:** de agora até as 21h (o mesmo limite das sugestões da M2), menos os compromissos com hora do Google Calendar. Tarefa com hora marcada hoje fica fixa; as outras entram em ordem de prioridade no primeiro espaço onde cabem, primeiro as obrigatórias (prazo até hoje). Sem a agenda do Google, o plano sai só com as tarefas e avisa.
- **Faixas:** Agora = em andamento ou começando nos próximos 15 min; Depois = resto do dia (compromissos e tarefas com prazo até hoje); Se der tempo = sem prazo para hoje e o que não coube. Sem nada obrigatório agora, a primeira opcional sobe para Agora.
- **Sobrecarga** = alguma tarefa com prazo até hoje não coube. Essencial: prazo até hoje e prioridade alta, ou hora marcada hoje (não baixa). Pode esperar: prioridade baixa, ou sem prazo para hoje (a não ser alta). Importante: o resto.
- **Proposta realista:** escolhe o que fica encaixando na ordem das classes, cada tarefa no menor espaço onde cabe (evita que brechas sobrem e uma importante fique de fora); depois refaz os horários o mais cedo possível. O que não cabe tem sugestão de adiar para amanhã. Nada é gravado: o usuário decide.
- **Estouro:** o usuário diz quanto falta; sem resposta, estimativa de metade da duração prevista (múltiplos de 15 min). Impacto = o resto do dia sem e com o tempo extra: compromissos e horas marcadas que batem, tarefas que deixam de caber, tarefas que começam mais tarde. Sugestões: compromisso que bate → encurtar a atual até ele ou mover (agenda: avisa que pede confirmação); tarefa perdida que pode esperar → adiar; perdida importante/essencial → simula encurtar ou adiar uma de classe abaixo, ou encurtar a atual, e sugere a primeira que faz caber; senão, adiar a perdida.
- **Espaço livre:** só atrasadas que cabem; nota = importância 45 % + atraso 30 % (satura em 7 dias) + aproveitamento do intervalo 25 %. Uma sugestão e até duas alternativas. Nenhuma atrasada cabe → a de hoje que couber, avisando; nada cabe → mostra a atrasada mais curta. Sem minutos ditos, vale o tempo até o próximo compromisso ou hora marcada.
- **Recorrentes:** regra diária, dias úteis, semanal (dias) ou mensal (dia; 31 em mês curto = último dia). A tarefa do dia nasce sozinha quando o plano do dia ou os lembretes são montados, uma vez por rotina e dia; dias passados não são recriados. Se a hora bate com um compromisso, só a tarefa daquele dia vai para o próximo horário livre e diz de onde veio; a regra não muda. Criar, alterar e pausar rotina é "mudança real": pede o "sim" falado, com a mudança (de → para) dita antes. Rotina criada depois da hora de hoje começa na próxima vez.
- **Hábitos:** meta de 1 a 7 dias por semana (segunda a domingo), sequência de semanas batidas e dias seguidos. Criar pede "sim"; marcar o dia é direto. Só vira aviso quando, sem fazer hoje, a meta da semana fica impossível, e no máximo um aviso por dia (19h).
- **Lembretes:** alta = 60 e 15 min antes + na hora, repete a cada 30 min duas vezes e depois pergunta se reagenda, sugerindo horário livre; média = 15 min antes + na hora, repete uma vez; baixa = na hora. Sem hora: só alta, às 14h. Silêncio 22h–7h; durante compromisso o aviso de antecedência vem 5 min antes dele. Avisos a menos de 10 min viram um; no máximo 3 por hora e 12 por dia, saindo primeiro os de prioridade mais baixa. **A entrega na tela ainda não existe:** `lembretes.planejar` diz quando avisar, e a ação `lembretes` mostra o plano; quem dispara os avisos e conta os ignorados entra com a rotina diária (Meta 4).
- **Não rastrear:** nenhuma tabela ou coluna guarda foco, pausas, interrupções ou hora real de início (teste `test_banco_nao_guarda_foco_pausas_nem_interrupcoes`).
- **Card:** painel de conteúdo do Mark (como nas M1B/M2), com o tempo que sobra depois do plano.
