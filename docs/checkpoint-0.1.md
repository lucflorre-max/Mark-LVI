# Checkpoint 0.1 — Mark LVI rodando

Data: 23/10/2026 · Windows 11, Python 3.12.10, chave Gemini do plano grátis · Modelo de voz: `gemini-3.1-flash-live-preview`

## Resultado

| Item | Resultado |
| --- | --- |
| `python main.py` abre | ✅ |
| Ouve (microfone) | ✅ depois de reativar o microfone interno no Windows (estava desativado) |
| Responde por voz | ✅ |
| Português do Brasil | ✅ conversa e voz em pt-BR |
| Abre um aplicativo | ✅ "abra o Bloco de Notas" → `open_app` |

**Checkpoint aprovado**, com as falhas abaixo.

## Falhas e observações

| # | O quê | Gravidade | Onde resolver |
| --- | --- | --- | --- |
| 1 | **"Fechar o Explorer" abriu a caixa "Desligar o Windows"**, com OK como padrão | **Alta** | Auditoria, achado 10 → M1 tarefa 0 |
| 2 | Digitou e salvou um arquivo no Bloco de Notas sem pedir confirmação | Alta | Auditoria, achado 2 → M1 tarefa 0 |
| 3 | Salvou "torcedor do Internacional" na memória permanente sem perguntar | Média | Auditoria, achado 5 → M5 (persona na M1 tarefa 2) |
| 4 | Acento ao digitar: "Nós" saiu como "NS" pelo `computer_control type`; o Jarvis viu na tela e digitou de novo por `computer_settings type_text` | Média | Investigar na M1 (a digitação deveria usar a área de transferência) |
| 5 | Atraso para responder | Média | Ver abaixo |
| 6 | Sem microfone ativo, a sessão entra em loop de reconexão | Média | Auditoria, achado 6 → M1B |
| 7 | Cota grátis: modelos de texto em segundo plano esgotaram na primeira sessão | Baixa | Auditoria, achado 7 |

### Atraso

O Jarvis usa ~150 MB, e não havia instâncias duplicadas. As causas medidas:
- **RAM esgotada:** 0,1 GB livres de 7,7 GB (VS Code ~1 GB, Brave ~0,5 GB, Claude ~0,5 GB). Com o Windows usando disco como memória, o áudio e as respostas atrasam. Fechar o navegador e o que não estiver em uso ajuda.
- **Pedidos em várias etapas:** um único pedido gerou 7 chamadas de ferramenta (digitar, print da tela, digitar de novo, salvar, status do sistema). Cada uma é uma ida e volta ao Gemini, e o print da tela é a mais lenta.
- O briefing de notícias na inicialização também consome tempo e cota.

## Ambiente preparado

- Fork `lucflorre-max/Mark-LVI`, `upstream` = `FatihMakes/Mark-LVI`, branch `develop`.
- `.venv` com Python 3.12; `setup.py` instalou as dependências e os navegadores do Playwright.
- Segredos protegidos localmente em `.git/info/exclude` (o `.gitignore` do Mark está quebrado).
- O painel do celular abriu as portas 8000/8001 no firewall (aprovado pelo usuário).
