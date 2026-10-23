# Mudanças no código do Mark

Registro de toda alteração feita em `main.py`, `ui.py`, `core/` ou outros arquivos do Mark LVI. Cada mudança no código leva um comentário `# JARVIS:`.

Use isto ao atualizar o `upstream`: são os pontos onde pode haver conflito.

| Data | Arquivo:linha | O quê | Por quê | Meta |
| --- | --- | --- | --- | --- |
| 23/10/2026 | `.gitignore:7-28` | Comentários em linha própria; `data/` ignorado | Comentário no fim da linha anulava os padrões: segredos não eram ignorados (achado 1) | M1 tarefa 0 |
| 23/10/2026 | `main.py:83-84` | Importa `jarvis.brain.gate` e `jarvis.config` | Necessário para as duas mudanças abaixo | M1 tarefa 0 |
| 23/10/2026 | `main.py:1405-1408` | Ações passam por `jarvis_gate.guard(...)` antes de rodar | Só desligar/reiniciar/Wi-Fi pediam CONFIRM; a política fica em `jarvis/brain/policy.py` (achado 2) | M1 tarefa 0 |
| 23/10/2026 | `main.py:2371-2373` | Painel do celular só liga com `"dashboard_enabled": true` | Ligava sozinho e aceitava comandos da rede local (achado 3) | M1 tarefa 0 |
| 23/10/2026 | `core/appidentity.py:614-619, 652-656` | `close_app` pula janelas do shell (`Progman`, `WorkerW`, `Shell_TrayWnd`, `Shell_SecondaryTrayWnd`) | "Fechar o Explorer" mandava WM_CLOSE para a área de trabalho e abria "Desligar o Windows" (achado 10) | M1 tarefa 0 |

As mudanças previstas que ainda faltam estão em `docs/auditoria-mark.md`. Sugerir ao upstream: achados 1 e 10.
