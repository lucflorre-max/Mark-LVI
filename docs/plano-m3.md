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
| 1 | Motor de prioridade: prazo + impacto + contexto + esforço | |
| 2 | Linha do tempo Agora / Depois / Se der tempo no card | |
| 3 | Sobrecarga: Essencial / Importante / Pode esperar e proposta de dia realista | |
| 4 | Tarefa que estourou: impacto e sugestão de mover, encurtar ou adiar, sem aplicar | |
| 5 | Espaço livre: sugerir a pendência atrasada que couber | |
| 6 | Recorrentes automáticas, hábitos e metas semanais, lembretes conforme a prioridade sem excesso | |

## Decisões

- **Impacto = prioridade dita pelo usuário** (alta / média / baixa). Sem prioridade conta como média.
- **Contexto = onde o usuário está ou o que está fazendo** ("trabalho", "casa", nome de projeto), dito na conversa. A tarefa combina quando o projeto ou a descrição dela tem essa palavra. Sem contexto dito, o fator fica neutro para todas.
- **Esforço = duração estimada.** Tarefa curta sobe um pouco (cabe em brechas); sem duração conta como 30 min.
- **Pesos:** prazo 40 %, impacto 35 %, esforço 15 %, contexto 10 %. Atrasada tem o fator de prazo máximo.
