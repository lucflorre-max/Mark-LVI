# Meta 1: Núcleo Jarvis (29/10 a 04/11/2026)

## Ajustes da auditoria (23/10/2026)

O plano diz que, se a auditoria mandar substituir algo, a auditoria vence. Conferido contra o código do Mark LVI:

**Confirmado no código:**
- Plugin = `.py` em `plugins/` com `PLUGIN` (nome, descrição, parâmetros) e `run(parameters, player, session_memory)`. Arquivos começando com `_` são ignorados (`core/plugin_loader.py:304`). Nome que colide com ferramenta do Mark é rejeitado.
- `core.gemini.text(...)` e `core.gemini.as_json(...)` existem, com `tier=gemini.FAST` ou `gemini.SMART`.
- Plugins rodam por um caminho próprio (`main.py:1418`), separado das actions (`main.py:1403`). O plugin aplica a política sozinho (tarefa 5).

**Ajustes:**
1. **Nova tarefa 0 — segurança da auditoria (antes da tarefa 1).** Achados 1, 2 e 3 da auditoria, todos de gravidade alta ou média e marcados para a M1:
   - `.gitignore`: comentários em linha própria (hoje os segredos não são ignorados; mitigado só localmente em `.git/info/exclude`). Já incluir `data/` (tarefa 3).
   - Portão de confirmação central em `main.py:1403` para as ações do Mark que mandam mensagem, mexem no PC ou executam código (`send_message`, `computer_control`, `browser_control`, `desktop_control`, `dev_agent`, `code_helper`, `reminder`, `game_updater`). A lista fica em `jarvis/brain/policy.py`, que nasce aqui e é ampliada na tarefa 5.
   - Painel do celular desligado por padrão (flag em `config/api_keys.json`).
   - **Achado 10 (checkpoint 0.1):** `close_app` não pode mandar `WM_CLOSE` para a área de trabalho e a barra de tarefas (`explorer.exe`); hoje isso abre "Desligar o Windows". `close_app` também entra na lista com CONFIRM.
2. **Tarefa 2 (persona) — completar.** Além do idioma, tratamento e rosto, o `core/prompt.txt` manda "act rather than asking" (`[JUDGEMENT]`, `[SPEED]`) e "save_memory… silently". Isso conflita com "sugere antes de alterar" e "preferência permanente só com confirmação". Ajustar esses trechos também, com `# JARVIS:`.
   - O tratamento "senhor" pode vir da configuração existente `"user_name": "senhor"` em `config/api_keys.json` (o Mark injeta `ADDRESS: Always call the user '...'`). "Mestre Luc" nos momentos descontraídos continua no prompt.
   - As linhas `#` do `prompt.txt` são enviadas ao modelo como texto (não são removidas). Isso é inofensivo, mas mantenha as marcas `# JARVIS:` curtas.
3. **Tarefa 6 — antes do checkpoint, trocar `hud_style` para `core`** por configuração (sem código), já que o prompt deixa de falar em rosto.
4. **Datas:** valem as deste plano (29/10 a 04/11). O usuário prefere o prazo mais curto; o CLAUDE.md foi atualizado.

**Andamento (23/10/2026):**
- Tarefa 0 — código e testes prontos; falta o teste por voz do banner.
- Extra — transcrição local em `data/conversas/`.
- Tarefa 1 — concluída. Descoberta do plugin conferida com o carregador do Mark, sem abrir o app (pedido do usuário).
- Tarefa 3 — concluída. Além das 5 funções, `obter`, `reabrir` (desfazer de concluir), caixa de entrada e projeto por nome, que a tarefa 4 vai usar. Fuso: `America/Sao_Paulo` se houver `tzdata`, senão UTC−3 fixo (sem dependência nova).
- Tarefa 4 — código e testes prontos (fluxo completo simulado em `tests/test_service.py`, incluindo a frase do plano); falta o teste por voz.
  - `confirmado=true` só vale depois de o resumo ser mostrado, e qualquer mudança de campo exige novo resumo.
  - "Desfazer" usa a pilha de `core/undo.py`, então o `undo` do Mark também desfaz tarefas.
- Tarefa 5 — concluída. `jarvis_tarefas` está na política; ação nova pede CONFIRM até ser classificada; `CATEGORIAS_CONFIRM` testa as categorias do CLAUDE.md.
- Extra (pedido do usuário) — "sim" por voz para digitar/teclar/clicar (`feature/m1-confirmacao-voz`) e transcrição da voz com dica pt-BR.
- Extra (pedido do usuário, **adianta a M5**) — perfil de comunicação (`feature/m1-perfil`): análise local das transcrições sugere vocabulário e expressões; plugin `jarvis_perfil` salva só com "sim" falado em `data/perfil.json`; vocabulário vai para o reconhecimento de voz e expressões para o prompt. Na M5: migrar para o SQLite da memória e somar preferências.
- **Testes por voz pendentes** (quando o usuário puder falar): banner da tarefa 0, tarefa 2 (persona) e roteiro da tarefa 4. Depois, tarefa 6 (checkpoint 1.0).

**Meta 0 fechada em 23/10/2026:** checkpoint 0.1 aprovado, falhas em `docs/checkpoint-0.1.md`.

---

**Objetivo:** você diz uma tarefa por voz, o Jarvis mostra um resumo curto, pergunta só o que falta e salva em um banco local depois do seu aceite. Todo o código novo fica em `jarvis/` e entra no Mark por um plugin fino em `plugins/`.

## Antes de começar (Meta 0 precisa estar fechada)

- [x] Fork clonado, `upstream` e branch `develop` criados, `CLAUDE.md` na raiz.
- [x] Checkpoint 0.1: `python main.py` abre, ouve, responde e abre um aplicativo.
- [x] Português testado (conversa e voz) e falhas anotadas em `docs/checkpoint-0.1.md`.
- [x] Auditoria 0.2 salva em `docs/auditoria-mark.md`. As tarefas abaixo devem respeitá-la; se ela mandar substituir algo daqui, a auditoria vence.

## O que o código do Mark já nos dá

Conferi no código do Mark LVI (56). Os prompts abaixo se apoiam nisto:

- **Plugin:** um arquivo `.py` em `plugins/` com um dicionário `PLUGIN` (nome, descrição, parâmetros) e uma função `run(parameters, player, session_memory)` que devolve a frase falada. Cada arquivo é uma ferramenta. Para ter várias ações, usamos um parâmetro `acao` ou vários arquivos finos.
- **Modelo de texto:** plugins que precisam de um LLM usam `core.gemini` (`text`, `as_json`), nunca um cliente próprio.
- **Confirmação:** `core/confirm.py` mostra um banner CONFIRM/CANCEL que o modelo não consegue forjar. Só para o que é irreversível; o que dá para desfazer vai para `core/undo.py`.
- **Persona:** `core/prompt.txt` é o prompt do assistente, hoje em inglês e falando em "my face" (o rosto animado). Isso entra em conflito com o núcleo sem rosto e precisa mudar.

## Decisões padrão (mude se quiser)

1. **Tarefa nova é reversível.** Salva depois de um "sim" por voz e pode ser desfeita. Já enviar mensagem, alterar agenda ou rodar comando no PC exigem o clique em CONFIRM. Assim o fluxo por voz fica fluido sem enfraquecer a segurança.
2. **O modelo infere os campos.** A ferramenta recebe título, prazo, prioridade, duração, projeto e contexto já extraídos pelo Gemini Live. O código só valida e, se faltar prazo, prioridade ou duração, devolve a pergunta curta.
3. **Banco SQLite em `data/jarvis.db`**, fora do Git.
4. **Nada de interface nova nesta meta.** Usamos o log e o banner do Mark; os cards chegam na Meta 1B.

## Tarefas e prompts para o Claude Code

Uma tarefa por sessão, em uma branch `feature/m1-<tarefa>`.

### 0. Segurança da auditoria (antes da tarefa 1) — *adicionada pela auditoria*

> Leia o CLAUDE.md e docs/auditoria-mark.md (achados 1, 2 e 3). Corrija o `.gitignore` do Mark movendo os comentários para linhas próprias e acrescente `data/`. Crie `jarvis/brain/policy.py` com a lista de ações do Mark que exigem CONFIRM por clique e, em `main.py:1403`, encaminhe essas ações para `core.confirm.request(...)` em vez de executá-las direto (mudança pequena, comentada com `# JARVIS:`). Desligue o painel do celular por padrão com uma flag em `config/api_keys.json`. Corrija o achado 10: `close_app` nunca fecha janelas de shell do `explorer.exe` (área de trabalho, barra de tarefas), e "fechar o Explorer" fecha só as janelas de pasta. Registre tudo em `docs/mudancas-no-mark.md`, escreva testes para a política, rode `python main.py` e confirme que "mande uma mensagem para X" mostra o banner.

### 1. Pacote `jarvis/` e plugin de entrada (até 29/10)

> Leia o CLAUDE.md e docs/auditoria-mark.md. Crie o pacote `jarvis/` com os subpacotes brain, tasks, calendar, projects, memory, integrations e interface (cada um com `__init__.py`), um `jarvis/config.py` (caminho do banco, idioma pt-BR, nome do assistente) e um plugin fino `plugins/jarvis_tarefas.py` baseado em `plugins/_template.py`. O plugin deve só chamar `jarvis.tasks.service`. Não altere main.py, ui.py nem core/. Ao final, rode `python main.py`, confirme que o plugin é descoberto sem erro e faça o commit.

### 2. Persona em português (até 30/10)

> Edite `core/prompt.txt` com mudanças pequenas e marque cada uma com `# JARVIS:`. Acrescente uma seção de idioma e persona: responder sempre em português do Brasil, chamar o usuário de "senhor" (em momentos descontraídos, "Mestre Luc"), tom elegante, calmo e direto, humor leve só em assuntos casuais e nunca em assunto sério ou urgente; usar "Confirmado", "Provável" e "Incerto" quando relevante. Remova as referências ao rosto animado ("my face", "I look"): a interface passará a ser um núcleo circular sem rosto. Registre o que mudou em `docs/mudancas-no-mark.md`. Teste por voz três frases e diga se o tom está certo.
>
> *Ajuste da auditoria:* ajuste também `[JUDGEMENT]`, `[SPEED]` e o trecho de `save_memory` em `[EXECUTION]` para "sugere antes de alterar" e "preferência permanente só com confirmação". Considere `"user_name": "senhor"` na configuração.

### 3. Banco SQLite (até 30/10)

> Crie em `jarvis/tasks/` o repositório SQLite (`sqlite3` da biblioteca padrão): tabelas `tasks` (id, titulo, descricao, prazo, prioridade, duracao_min, projeto_id, status, origem, criado_em, atualizado_em), `projects` e `inbox`. Banco em `data/jarvis.db`, e `data/` no `.gitignore`. Funções: adicionar, listar por dia, concluir, adiar, apagar. Datas em ISO 8601 com fuso America/Sao_Paulo. Sem dependências novas. Escreva testes em `tests/` para cada função.

### 4. Captura de tarefa por voz (até 03/11)

> Em `jarvis/tasks/service.py`, implemente a ação `criar` da ferramenta `jarvis_tarefas` com os parâmetros titulo, prazo, prioridade, duracao_min, projeto e contexto. Regras: se faltar prazo, prioridade ou duração, devolva uma pergunta curta em português pedindo só o que falta; se estiver completo, devolva um resumo de uma frase e guarde a tarefa como pendente; só salve depois de uma segunda chamada com `confirmado=true` (o usuário disse "sim"). "Depois eu vejo isso" vira pergunta de prazo; se continuar indefinido, vai para a caixa de entrada. Adicione ações `listar_hoje`, `concluir` e `desfazer` (usando `core/undo.py`). Teste por voz: "Anota aí: configurar o roteador da secretaria amanhã às duas, prioridade média, uma hora."

### 5. Regra "sugere antes de alterar" (até 03/11)

> Leia `core/confirm.py` e o padrão de uso nas actions. Defina em `jarvis/brain/policy.py` uma lista do que é reversível (criar tarefa, concluir tarefa) e do que exige CONFIRM por clique (enviar mensagem, alterar agenda, apagar em lote, comandos no PC). Faça o plugin respeitar essa lista e escreva testes. Não mude `core/confirm.py`.
>
> *Ajuste da auditoria:* `jarvis/brain/policy.py` já existe desde a tarefa 0 (ações do Mark); aqui ela ganha as ações do Jarvis.

### 6. Testes e checkpoint 1.0 (até 04/11)

> Rode `pytest` e corrija falhas. Faça um roteiro de teste por voz com cinco casos: tarefa completa, tarefa sem prazo, "depois eu vejo isso", listar o dia e desfazer. Escreva o resultado em `docs/checkpoint-1.0.md`, atualize o CHANGELOG, faça merge em `develop` e crie a tag `v0.1.0-m1`.

## Critério de pronto

Você diz "Anota aí..." e recebe um resumo curto; confirma por voz; a tarefa aparece em "o que tenho hoje?"; "desfaz" a remove. Testes passam e nada do núcleo do Mark foi reescrito.

## Riscos desta meta

- A auditoria pode mudar o plano de `core/prompt.txt`. Se mexer demais, mantemos a persona em um arquivo à parte e carregamos por plugin.
- O português por voz depende do Gemini Live; falhas de reconhecimento em nomes próprios são esperadas e não são bug nosso.
- O Gemini Live pode chamar a ferramenta com campos inventados. Por isso o código valida e pede o que falta, em vez de confiar.
- *(auditoria)* Cota grátis do Gemini: as tarefas de texto em segundo plano esgotaram na primeira sessão. Se `core.gemini.text` for usado no plugin, prever a falha e responder sem ele.
