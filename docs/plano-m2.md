# Meta 2: Calendar + Trello

Fonte: pedido do usuário em 23/10/2026 e o documento-mestre (seções 5.1, 11, 14, 15 e 18). Não havia um "plano da Meta 2" escrito; este arquivo é ele.

**Entrega:** agenda e tarefas sincronizadas, com confirmação. Código em `jarvis/calendar/` e `jarvis/integrations/`. Uma tarefa por vez, com testes e commit.

## Regras do documento-mestre

- **Consulta** (ler agenda, mostrar tarefas) roda sem confirmação (§11).
- **Alteração de agenda/tarefa** (criar compromisso, mover, reagendar) **mostra a mudança e pede confirmação** (§11, §14).
- Tarefa com horário pode **ficar no Trello com um compromisso vinculado no Calendar**; o Jarvis **diz onde salvou cada item** (§5.1).
- Conflitos: **analisar e sugerir**; nada é aplicado sem aprovação (§5.1, §15 "Replanejar atraso").
- A tarefa guarda os links do Calendar e do Trello; o evento guarda o vínculo com a tarefa (§18).

## Tarefas

| # | Tarefa | Situação |
| --- | --- | --- |
| 1 | Acesso ao Google Calendar com o menor escopo, credenciais fora do Git | **feita** (23/10/2026): projeto Google configurado, autorizado, leitura da agenda principal confirmada |
| 2 | Ler a agenda do dia e mostrar no card | **feita** (23/10/2026): ferramenta `jarvis_agenda` ação `ver` (hoje, amanhã ou AAAA-MM-DD); card no painel de conteúdo do Mark; títulos vão ao modelo como conteúdo não confiável |
| 3 | Criar compromisso só depois da confirmação | **código e testes prontos** (23/10/2026): `jarvis_agenda` ação `criar`; mostra a mudança no card e no banner CONFIRM/CANCEL, grava só no clique; falta o teste por voz |
| 4 | Trello com chave e token, quadro e listas | **código e testes prontos** (23/10/2026): `jarvis/integrations/trello.py` e comandos `chave`, `quadros`, `usar`, `status`; falta o usuário gerar a chave e o token (docs/integracoes-trello.md) |
| 5 | Tarefa com horário → Trello + compromisso vinculado no Calendar; dizer onde salvou | |
| 6 | Detectar conflitos e sugerir ajuste, sem aplicar sozinho | |

## Decisões

- **Escopo do Calendar:** `https://www.googleapis.com/auth/calendar.events.owned` — ver, criar, alterar e excluir eventos só nas agendas que o usuário possui. Mais estreito que `calendar.events` (todas as agendas acessíveis). Confirmado em 23/10/2026: lê a agenda principal.
- **Credenciais:** `config/google/client_secret.json` (OAuth "App para computador") e `config/google/token_calendar.json`. Ambos fora do Git (`config/google/` no `.gitignore`).
- **Tela de consentimento em "Teste" expira a autorização em 7 dias**; publicar como "Em produção" exigiria página inicial, política de privacidade e termos num domínio verificado, então o app fica em "Teste" e a cada 7 dias o usuário roda `python -m jarvis.integrations.google_auth autorizar` de novo. O Jarvis avisa quando o token expira (`NaoAutorizado`).
- **Sem dependências novas:** `google-api-python-client`, `google-auth-oauthlib` e `requests` já vêm do Mark.
- **Card da agenda (tarefa 2):** os cards da Meta 1B ainda não existem (falta o protótipo `docs/jarvis_visual_demo.html`). A tarefa 2 entrega os dados do card e usa o painel de conteúdo do Mark até lá (aprovado pelo usuário em 23/10/2026). O plugin chama `player.show_content`, então nenhum arquivo do Mark mudou.
- **Criar compromisso usa o clique**, não o "sim" falado: agenda está na lista do clique no CLAUDE.md. O banner mostra o compromisso já formatado (`gate.guard(..., descricao=)`), avisa quando usou a duração padrão de 1h ou quando o horário já passou. O banner do Mark não devolve o resultado ao modelo depois do clique, então "criado" ou "não criado" aparece no card com o link do evento.
- **Títulos da agenda são dados de terceiros** (convites): o texto para o modelo vai dentro de `core.outcome.untrusted("google_calendar", …)`; o card mostra o texto puro.
- **Trello (tarefa 4):** chave e token em `config/trello.json` (fora do Git), enviados no cabeçalho `Authorization: OAuth oauth_consumer_key=…, oauth_token=…` e nunca na URL, para não aparecerem em logs nem em mensagens de erro (confiança: Provável, pela documentação oficial da API REST do Trello). Token com `scope=read,write` e `expiration=never`. O quadro escolhido precisa de duas listas, uma de tarefas novas e uma de concluídas; o comando `usar` acha pelo nome ou cria. Sem dependências novas (`requests` já vem do Mark).
