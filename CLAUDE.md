# JARVIS — instruções para o Claude Code

Projeto pessoal: um assistente estilo J.A.R.V.I.S em português do Brasil, construído sobre o fork do **FatihMakes/Mark-LVI (Mark LVI, 56)**. Licença do projeto base: CC BY-NC 4.0, uso pessoal e não comercial.

Objetivo central: **reduzir atrito, não criar mais trabalho.** A pergunta que o Jarvis responde é "o que eu preciso fazer agora?".

## Como trabalhar

- Faça **uma tarefa do plano por sessão**, em uma branch `feature/<meta>-<tarefa>` criada a partir de `develop`. Ao terminar, rode os testes, faça o commit e diga o que mudou.
- Antes de começar uma meta, leia o plano (JARVIS — Plano de Implementação) e confirme qual tarefa está sendo feita. Marque como concluída só depois de testada.
- Em dúvida técnica incerta, pesquise primeiro (documentação oficial, GitHub e issues) e diga o nível de confiança: Confirmado, Provável ou Incerto.

## Onde fica o código

- Código **nosso** vai em `jarvis/` (brain, tasks, calendar, projects, memory, integrations, interface) e em `plugins/`.
- `main.py` (~2.400 linhas), `ui.py` (~6.350 linhas) e `core/` são do Mark. Só altere o necessário, com mudanças pequenas e comentadas com `# JARVIS:`; registre cada alteração em `docs/mudancas-no-mark.md`.
- Não reescreva nem reorganize o núcleo do Mark sem passar pela auditoria da Meta 0.2 (`docs/auditoria-0.2.md`).
- Mantenha o remoto `upstream` (FatihMakes/Mark-LVI) para receber melhorias; atualize uma vez por mês, em uma branch separada.

## Regras de segurança

- Nada que **envie mensagem, altere agenda, mude prioridade ou execute comando/arquivo/navegador no PC** roda sem confirmação do usuário. Reaproveite `core/confirm.py`.
- Chaves e tokens (Gemini, Google, Trello) **nunca** vão para o Git. `config/` continua no `.gitignore`. Nunca imprima chaves em logs.
- Ações destrutivas precisam de confirmação e, quando possível, de desfazer (`core/undo.py`).
- Não instale pacotes novos sem avisar o motivo.

## Comportamento do Jarvis

- Idioma: português do Brasil. Tratamento padrão "senhor"; em momentos descontraídos, "Mestre Luc".
- Tom: elegante, calmo e direto, com humor leve só em assuntos casuais. Em assunto sério, urgente ou de risco, sem humor.
- Pergunta o mínimo: para criar uma tarefa, infere o contexto e pergunta só prazo, prioridade e duração quando faltarem.
- Sugere antes de alterar. Aprende, mas só cria preferência permanente depois da confirmação do usuário.
- Evita excesso de notificações e sensação de vigilância.

## Interface (estilo definido)

- Núcleo circular **sem rosto**, com anéis, partículas e anel de áudio. Referência visual: `docs/jarvis_visual_demo.html`.
- Estados: repouso, ouvindo, analisando, falando e alerta, cada um com cor e velocidade própria.
- Tela de repouso quase vazia: núcleo, hora e "Como posso ajudar, senhor?".
- Cards contextuais (agenda, tarefa encontrada com Confirmar e Ajustar, alerta) aparecem só quando o assunto surge e recolhem sozinhos.
- O Mark já tem o HUD "Reactor Core" em `ui.py` (opção `hud_style` = `core`); use como ponto de partida.

## Ambiente (Windows)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python setup.py
python main.py
```

Testes: `pytest` na raiz (a partir da Meta 1).

## Metas e prazos (≈10 h por semana)

| Meta | Período | Entrega |
| --- | --- | --- |
| M0 Base Mark LVI | 26/10 a 01/11/2026 | Mark funcionando, português testado, auditoria 0.2 |
| M1 Núcleo Jarvis | 02/11 a 15/11 | Pacote `jarvis/`, persona, SQLite, tarefa por voz |
| M1B Interface contextual | 16/11 a 29/11 | Núcleo limpo, estados e cards |
| M2 Calendar + Trello | 30/11 a 13/12 | Agenda e tarefas sincronizadas, com confirmação |
| M3 Prioridades | 14/12 a 20/12 | Agora / Depois / Se der tempo, sobrecarga |
| M4 Rotina diária | 21/12 a 03/01/2027 | Briefing 07h30, fechamentos 16h45 e 21h, resumo semanal |
| M5 Projetos + Memória | 04/01 a 17/01 | **MVP v0.1** |
| M6 Comunicação e pesquisa | 18/01 a 31/01 | Gmail leitura, rascunhos, follow-ups |
| M7 Controle do PC e segurança | 01/02 a 14/02 | Revisão de ações, chaves seguras, início com o Windows |
| M8 Celular e nuvem | 15/02 a 07/03 | Painel no celular, sincronia, backup |

## Prompt para começar a Meta 0 (cole no Claude Code)

> Leia este CLAUDE.md. Estamos na Meta 0 do plano. Confirme que o ambiente Python 3.12 está pronto, que o `upstream` aponta para FatihMakes/Mark-LVI e que a branch `develop` existe. Depois rode `python main.py`, descreva qualquer erro e pare. Não altere nenhum arquivo do Mark nesta tarefa.
