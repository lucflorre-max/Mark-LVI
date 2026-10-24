# Mudanças no código do Mark

Registro de toda alteração feita em `main.py`, `ui.py`, `core/` ou outros arquivos do Mark LVI. Cada mudança no código leva um comentário `# JARVIS:`.

Use isto ao atualizar o `upstream`: são os pontos onde pode haver conflito.

| Data | Arquivo:linha | O quê | Por quê | Meta |
| --- | --- | --- | --- | --- |
| 23/10/2026 | `.gitignore:7-28` | Comentários em linha própria; `data/` ignorado | Comentário no fim da linha anulava os padrões: segredos não eram ignorados (achado 1) | M1 tarefa 0 |
| 23/10/2026 | `main.py:83-84` | Importa `jarvis.brain.gate` e `jarvis.config` | Necessário para as duas mudanças abaixo | M1 tarefa 0 |
| 23/10/2026 | `main.py:1407-1410` | Ações passam por `jarvis_gate.guard(...)` antes de rodar | Só desligar/reiniciar/Wi-Fi pediam CONFIRM; a política fica em `jarvis/brain/policy.py` (achado 2) | M1 tarefa 0 |
| 23/10/2026 | `main.py:2376-2378` | Painel do celular só liga com `"dashboard_enabled": true` | Ligava sozinho e aceitava comandos da rede local (achado 3) | M1 tarefa 0 |
| 23/10/2026 | `core/appidentity.py:614-619, 652-656` | `close_app` pula janelas do shell (`Progman`, `WorkerW`, `Shell_TrayWnd`, `Shell_SecondaryTrayWnd`) | "Fechar o Explorer" mandava WM_CLOSE para a área de trabalho e abria "Desligar o Windows" (achado 10) | M1 tarefa 0 |
| 23/10/2026 | `core/prompt.txt` ([SELF]) | Remove "my face"/"I look"; descreve o núcleo circular sem rosto | Interface do JARVIS não tem rosto | M1 tarefa 2 |
| 23/10/2026 | `core/prompt.txt` ([PERSONA], nova) | pt-BR, "senhor"/"Mestre Luc", tom, Confirmado/Provável/Incerto, sugerir antes de alterar, não pesquisar na web sobre si mesmo | Persona do CLAUDE.md; no checkpoint 0.1 ele pesquisou na web "is JARVIS connected to my Google account" | M1 tarefa 2 |
| 23/10/2026 | `core/prompt.txt` ([JUDGEMENT], [SPEED]) | Pedido ambíguo que muda algo → uma pergunta antes | "act rather than asking" conflitava com "sugere antes de alterar" (achado 4) | M1 tarefa 2 |
| 23/10/2026 | `core/prompt.txt` ([EXECUTION]) | Ferramentas `jarvis_*` recebem texto em pt-BR; preferência permanente só depois de um "sim"; portão cobre mais ações e `[CONFIRMATION_BUSY]` | Títulos de tarefa sairiam em inglês; memória silenciosa (achado 5) | M1 tarefa 2 |
| 23/10/2026 | `main.py:1934-1935` | Briefing busca `jarvis_config.BRIEFING_NOTICIAS` ("manchetes notícias Brasil hoje") | Com "top world news today" vinham manchetes dos EUA (teste por voz, checkpoint 1.0) | M1 tarefa 2 |
| 23/10/2026 | `main.py:1185-1186` | `input_audio_transcription` com `language_codes=["pt-BR"]` e vocabulário (`jarvis_config.transcricao_entrada()`) | O Live transcrevia português como inglês ("The price is for you"); aceito pelo servidor em teste de conexão | M1 |
| 23/10/2026 | `main.py` (input_transcription) | `jarvis_gate.ouvir(txt)` a cada trecho da voz do usuário | "Sim" por voz para digitar/teclar/clicar vem do microfone, não de um parâmetro do modelo | M1 |
| 23/10/2026 | `core/prompt.txt` ([EXECUTION]) | Explica `[VOICE_CONFIRM]` e `[VOICE_DECLINED]`; digitar/clicar saem do botão | Nova regra de confirmação escolhida pelo usuário | M1 |
| 23/10/2026 | `main.py` (import + `parts`) | `parts.append(jarvis_perfil.bloco_prompt())` antes do prompt | Expressões aprovadas pelo usuário entram em cada sessão ('' quando vazio) | M1 → base da M5 |
| 23/10/2026 | `config/api_keys.json` (local) | `"hud_style": "core"` | Núcleo circular em vez do rosto (configuração, sem código) | M1 tarefa 2 |
| 23/10/2026 | `main.py:85, 1289, 1443, 1720, 1740` | Transcrição local: fala do usuário, resposta, ferramenta e resultado vão para `jarvis/memory/transcript.py` | Analisar conversas reais para melhorar o JARVIS; desligar com `"transcript_enabled": false` | M1 (extra) |
| 23/10/2026 | `.gitignore` (Secrets) | `config/google/` ignorado | Credenciais e token do Google Calendar do JARVIS | M2 tarefa 1 |
| 23/10/2026 | `memory/config_manager.py:144-151` | `hud_style` padrão `"core"` (era `"face"`) | Núcleo sem rosto por padrão | M1B |
| 23/10/2026 | `ui.py:418-433` | `hud_style` lido antes; `HoloAvatar` só é criado no estilo `"face"` | Tirar o rosto da vista e não gastar memória com a malha 3D | M1B |
| 23/10/2026 | `ui.py:5649` | Botão "HUD: ANIMATED FACE / REACTOR CORE" escondido | Sem opção de voltar ao rosto pela interface | M1B |
| 23/10/2026 | `ui.py:843-860, 915-919` | Repouso (ouvindo, sem falar, sem mudo): só núcleo, hora e "Como posso ajudar, senhor?"; sem status em inglês e sem barra de áudio | Meta 1B, tarefa 1 | M1B tarefa 1 |
| 23/10/2026 | `.gitignore` (Secrets) | `config/trello.json` ignorado | Chave e token do Trello do JARVIS | M2 tarefa 4 |
| 23/10/2026 | `actions/web_search.py` (`_ddg_news`, `_news`, `ultimas_noticias`) | Guarda o campo `image` do DDG e a lista da última busca de notícias | Card de notícias com foto; o Mark jogava a foto fora | M1B |
| 23/10/2026 | `ui.py` (`_news_sig`, `_show_news`, `show_news`) | Card de notícias em HTML no painel de conteúdo, com a foto da principal como recurso do documento | Mostrar a foto da notícia relevante; a foto é baixada pelo JARVIS, o QTextEdit não acessa a rede | M1B |
| 23/10/2026 | `main.py` (briefing e espelho do `web_search`) | Notícias vão para `jarvis_noticias.mostrar` em vez de `show_content`; sem foto, o texto de antes | Card com foto no briefing e quando o usuário pede notícias | M1B |
| 23/10/2026 | `main.py` (briefing, `_jarvis_briefing_noticias`) | Notícias do briefing vêm dos feeds RSS (`jarvis/integrations/noticias.py`: Brasil, RS, Inter, economia, tecnologia); sem nenhum feed, a busca do Mark como antes | Fontes brasileiras escolhidas, com foto e sem gastar a cota do Gemini | M1B |

As mudanças previstas que ainda faltam estão em `docs/auditoria-mark.md`. Sugerir ao upstream: achados 1 e 10.
