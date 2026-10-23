# Auditoria 0.2 — núcleo do Mark LVI

Data: 23/10/2026 · Base: `FatihMakes/Mark-LVI@main` (commit `4d4035c`) · Branch: `feature/m0-auditoria`

Objetivo: entender o que o Mark já faz, o que conflita com as regras do JARVIS (CLAUDE.md) e onde mexer com o menor impacto possível. **Nenhum arquivo do Mark foi alterado nesta auditoria.**

## Resumo

| # | Achado | Gravidade | Meta sugerida |
| --- | --- | --- | --- |
| 1 | `.gitignore` com comentários na mesma linha não ignora segredos | **Alta** | Já mitigado localmente; corrigir na M1 |
| 2 | Portão de confirmação cobre só desligar, reiniciar e Wi-Fi | **Alta** | M1 (antes de qualquer integração) |
| 3 | Painel do celular liga sozinho, em HTTP, e aceita comandos que disparam ferramentas | Média | M1 (desligar por padrão) / M7 |
| 4 | `prompt.txt` manda agir sem perguntar e salvar memória em silêncio | Média | M1 (persona) |
| 5 | `save_memory` grava memória permanente sem confirmação | Média | M5 |
| 6 | Sem microfone, a sessão cai e reconecta em loop | Média | M1B |
| 7 | Cota grátis do Gemini esgota nas tarefas de texto | Baixa | M1 |
| 8 | `pynvml` obsoleto | Baixa | Quando atualizar o upstream |
| 9 | `hud_style` padrão é `face`; o JARVIS quer `core` | Baixa | M1B |
| 10 | "Fechar o Explorer" abre a caixa "Desligar o Windows" (OK como padrão) | **Alta** | M1 tarefa 0 |

## Mapa do código

| Área | Arquivos | Linhas | Papel |
| --- | --- | --- | --- |
| Orquestração | `main.py` | 2.387 | Sessão Gemini Live, áudio, despacho de ferramentas, briefing, painel |
| Interface | `ui.py` | 6.346 | HUD PyQt6, estilos `face` e `core`, banner de confirmação |
| Núcleo | `core/` | ~5.300 | `confirm`, `undo`, `gemini` (lista de modelos), `action_loader`, `plugin_loader`, áudio, TTS/STT, avatar |
| Ações | `actions/` | ~10.200 | 21 arquivos, 17 ações ativas carregadas automaticamente pelo `TOOL = {...}` |
| Memória | `memory/` | ~840 | `long_term.json` (ignorado no Git), `config_manager` (lê `config/api_keys.json`) |
| Painel remoto | `dashboard/` | ~1.900 | FastAPI + WebSocket, pareamento por QR, AES |
| Provedores | `providers/` | ~4.400 | Opcional: Whisper, Piper, OpenAI/Ollama, ElevenLabs |
| Plugins | `plugins/` | — | Vazio (só `_template.py`) |

Pontos de extensão que o JARVIS deve usar em vez de editar o Mark:

- **Novas ferramentas:** um arquivo com `TOOL = {...}` em `actions/` ou `plugins/` é descoberto automaticamente (`core/action_loader.py`, `core/plugin_loader.py`). O pacote `jarvis/` pode expor suas ferramentas por um plugin fino em `plugins/`.
- **Despacho único:** toda ação passa por `self._action_registry.run(...)` em `main.py:1403`. É o melhor lugar para um portão de confirmação central (ver achado 2).
- **Confirmação e desfazer:** `core/confirm.request(key, title, detail, run)` e `core/undo.push_undo(label, fn)` já são bem feitos e devem ser reaproveitados.

## Achados

### 1. `.gitignore` não protege segredos — Alta

```
config/api_keys.json          # your Gemini API key, plus per-plugin credentials
```

O Git não aceita comentário no fim da linha: o padrão vira o caminho inteiro, comentário incluído, e nada é ignorado. Afeta `config/api_keys.json`, `config/certs/`, `config/whatsapp_web/`, `**/token*.json` e `**/client_secret*.json`. Confiança: **Confirmado** (`git check-ignore` não encontrou regra antes da mitigação).

- **Mitigação feita:** os cinco padrões foram adicionados em `.git/info/exclude`, que é local e não vai para o repositório.
- **Correção definitiva (M1):** mover os comentários para a linha de cima no `.gitignore`. É uma mudança de 5 linhas no Mark: registrar em `docs/mudancas-no-mark.md` e sugerir ao autor por issue/PR.

### 2. Confirmação cobre quase nada — Alta

`core/confirm.py` é sólido: o token vem da interface, nunca do modelo, e expira em 90 s. Mas só `actions/computer_settings.py` o usa (desligar, reiniciar, Wi-Fi). A filosofia do Mark é "fazer e permitir desfazer", o que conflita com a regra do JARVIS de não executar sem confirmação.

Ações que hoje rodam **sem** confirmação e caem na regra do CLAUDE.md:

| Ação | O que faz | Desfazer? |
| --- | --- | --- |
| `send_message` | Digita e envia mensagens (WhatsApp, Telegram, Discord, Instagram, Messenger…) via teclado simulado | Não |
| `computer_control` | Digita, clica, atalhos, fecha apps, "clica onde vê" na tela | Não |
| `browser_control` | Controla o navegador via Playwright (preenche, clica, navega) | Não |
| `desktop_control` | Troca papel de parede, organiza e limpa a área de trabalho | Não |
| `dev_agent` | Cria projetos, roda `pip install` com pacotes escolhidos pelo modelo e executa comandos | Não |
| `code_helper` | Gera, salva e executa código (`subprocess`) | Não |
| `file_controller` | Cria, move, copia, renomeia, escreve e apaga (para a Lixeira) | **Sim**, cobertura boa |
| `open_app` | Abre programas (sem shell, já corrigido pelo autor) | — |
| `reminder` | Cria lembretes agendados no sistema | Não |
| `game_updater` | Interage com o Steam | Não |

**Proposta (M1):** um portão em `main.py:1403` com uma lista em `jarvis/` de ações que exigem confirmação. Para essas, em vez de executar, chamar `confirm_gate.request(...)` com a execução real como callable. São cerca de 10 linhas comentadas com `# JARVIS:` no Mark, e a política fica toda no nosso código. `file_controller` pode continuar só com desfazer, exceto `delete` e `write` sobre arquivo existente.

Observação: o banner aparece só no HUD do PC. Um comando vindo do celular (achado 3) também cai nesse portão, e não há como confirmar remotamente. Hoje isso é desejável.

### 3. Painel do celular — Média

- Liga sozinho em toda inicialização, se as dependências estiverem instaladas (`main.py:2364`). Não há opção para desligar.
- Abre as portas 8000/8001 no firewall do Windows (pede elevação uma vez).
- Usa HTTP por padrão. O conteúdo vai cifrado com AES derivado da chave de pareamento (PBKDF2), há limite de tentativas e os tokens expiram. HTTPS opcional via `"dashboard_https": true`.
- `/api/command` e o áudio do celular entram na mesma sessão do Gemini, então qualquer ferramenta pode ser disparada da rede local por quem tiver um token válido.
- A autenticação está bem feita para um projeto pessoal; o risco está em ficar exposto sem necessidade.

**Proposta:** M1 — desligado por padrão, com uma flag em `config/api_keys.json` (mudança de 2 linhas no `main.py`). Até a M8 (celular), regra de firewall restrita ou removida. M7 — revisar HTTPS e exigir confirmação para comandos remotos.

### 4. `core/prompt.txt` conflita com a persona — Média

O prompt do Mark diz "take the most reasonable reading and act rather than asking", "Act immediately… do not ask a question" e "Save critical preferences… silently". Já o JARVIS deve: sugerir antes de alterar, perguntar só prazo, prioridade e duração quando faltarem, e só criar preferência permanente com confirmação. Também falta o tratamento "senhor".

O que **vale manter**: idioma pela última fala (o pt-BR funcionou no teste), o bloco `[UNTRUSTED CONTENT]` contra prompt injection, tom calmo sem humor em assuntos sérios e a instrução de anunciar antes de agir para fora do PC.

**Proposta (M1):** não reescrever `prompt.txt`. Acrescentar um bloco de persona do JARVIS vindo de `jarvis/brain/` no ponto em que o prompt é montado, com regras que têm prioridade sobre `[JUDGEMENT]`, `[SPEED]` e o trecho de `save_memory`.

### 5. Memória salva sem confirmação — Média

`save_memory` (`main.py:1289`) grava direto em `memory/long_term.json`, e o prompt manda fazer isso em silêncio. O idioma também é salvo assim. O arquivo está corretamente ignorado no Git.

**Proposta (M5):** a memória do JARVIS fica no SQLite de `jarvis/memory/`. Preferências permanentes passam por confirmação; fatos de contexto podem continuar automáticos.

### 6. Sem microfone, loop de reconexão — Média

Se o Windows não tem entrada de áudio padrão, `_open_mic(None)` (`main.py:1547`) levanta `PortAudioError: Error querying device -1`. Isso derruba o `TaskGroup` da sessão, e o app reconecta a cada ~3 s para sempre, gastando sessões do Gemini Live. Foi o que aconteceu na M0 (microfone interno desativado no Windows).

**Proposta (M1B):** quando não houver microfone, manter a sessão só com texto e mostrar um card de alerta ("Microfone indisponível"). Se for mudança no Mark, sugerir também ao upstream.

### 7. Cota do Gemini — Baixa

As tarefas de texto em segundo plano percorrem uma lista de modelos (`core/gemini.py:156`). Com a chave grátis, `gemini-3.5-flash` e `gemini-flash-latest` deram "out of quota" já na primeira sessão (briefing + notícias + loop do achado 6), e `gemini-2.5-flash-lite` não estava disponível para a chave. O Live (`gemini-3.1-flash-live-preview`) funcionou.

**Proposta (M1):** medir o consumo depois de corrigir o loop. No JARVIS, evitar chamadas de fundo desnecessárias (o briefing de notícias na inicialização é candidato a desligar até a M4).

### 8. `pynvml` obsoleto — Baixa

`ui.py:324` importa `pynvml`, que emite `FutureWarning` pedindo `nvidia-ml-py`. Só afeta o medidor de GPU. Deixar para o upstream.

### 9. Interface — Baixa

`HUD_STYLES = ("face", "core")` (`memory/config_manager.py:133`), com padrão `face` (cabeça holográfica). O JARVIS quer `core`, sem rosto. Dá para trocar por configuração (`hud_style: "core"`), sem mexer no código. O prompt também diz ao modelo que "o rosto é seu corpo", o que deve sair no bloco de persona da M1.

### 10. "Fechar o Explorer" quase desliga o PC — Alta

*Encontrado no teste do checkpoint 0.1, em 23/10/2026.*

O usuário pediu para fechar o Explorador de Arquivos, e o Jarvis chamou `computer_control(action="close_app", app_name="Explorer")`. O `_close_app` (`actions/computer_control.py:332`) procura o processo `explorer.exe` e `core/appidentity.py:645` manda `WM_CLOSE` para **todas as janelas visíveis desse processo**. Só que o `explorer.exe` também é o shell do Windows: área de trabalho ("Program Manager"/`Progman`) e barra de tarefas. Um `WM_CLOSE` na área de trabalho faz o Windows abrir a caixa **"Desligar o Windows"**, com **OK como botão padrão**. Um Enter, do usuário ou de uma ação `press enter` do próprio Jarvis, desliga o PC sem passar por `core/confirm.py`. Confiança: **Confirmado** (reproduzido; o resultado da ferramenta foi `status=failed`, mas o diálogo apareceu).

**Correção (M1, tarefa 0):**
- Em `core/appidentity.py`, nunca mandar `WM_CLOSE` para janelas de shell (`Progman`, `WorkerW`, `Shell_TrayWnd`, `Shell_SecondaryTrayWnd`). Para o Explorer, fechar só as janelas de pasta (classe `CabinetWClass`).
- Tratar `explorer.exe` como protegido: "fechar o Explorer" fecha as janelas de pasta, nunca o processo.
- `close_app` entra na lista de ações com CONFIRM da `jarvis/brain/policy.py`, já que fechar um app pode perder trabalho não salvo.
- Sugerir a correção ao upstream (issue no FatihMakes/Mark-LVI).

## O que o Mark já faz bem (reaproveitar)

- `core/confirm.py`: confirmação que o modelo não consegue forjar.
- `core/undo.py`: pilha de desfazer com 10 níveis; `file_controller` registra desfazer em tudo e apaga para a Lixeira.
- `open_app` sem shell (o autor corrigiu uma injeção de comando).
- Conteúdo externo marcado como `<<<UNTRUSTED>>>` no prompt.
- Ações e plugins descobertos automaticamente, sem editar `main.py`.
- Verificação honesta de resultado (`core/outcome.py`): "não confirmado" em vez de "feito".

## Mudanças no Mark previstas (todas pequenas, com `# JARVIS:`)

1. `.gitignore`: comentários em linha própria (achado 1).
2. `main.py:1403`: portão de confirmação central (achado 2).
3. `main.py:2364`: painel desligado por padrão (achado 3).
4. Montagem do prompt: injetar bloco de persona do JARVIS (achado 4).
5. `main.py:1547`: modo sem microfone (achado 6).

Cada uma vai em `docs/mudancas-no-mark.md` quando for feita.
