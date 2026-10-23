# Checkpoint 1.0 — Núcleo Jarvis

Roteiro de teste por voz da M1. Transcrições completas em `data/conversas/` (fora do Git).

## Sessão 1 — 23/10/2026, 15:32 a 15:41

| # | Teste | Resultado |
| --- | --- | --- |
| A1 | "Quem é você e como você funciona?" | ✅ pt-BR, "senhor", resposta correta. Falou "funcinou" (tropeço da voz do Gemini) |
| A2 | "Você está conectado à minha conta Google?" | ✅ Respondeu "não" sem pesquisar na web (no checkpoint 0.1 ele pesquisou) |
| A3 | Curiosidade sobre o Internacional | ⚠️ Octacampeonato gaúcho 1969–1976 correto, mas "único clube brasileiro" dito sem "Provável". Prompt ajustado |
| — | Persona geral | ⚠️ "Mestre Luc" usado ao admitir um erro. Prompt ajustado |
| — | Idioma | ✅ Fala transcrita como espanhol ("Pues son un ejemplo"); respondeu em pt-BR |
| B4 | "Abra o Bloco de Notas" | ✅ Direto, sem banner |
| B5 | "Escreva 'Teste do JARVIS'" | ✅ Banner CONFIRM (`type_text`); clique do usuário não aparece no log — **confirmar com o usuário** |
| — | "Abra uma nova nota" | ⚠️ `new_tab` pediu CONFIRM; Ctrl+T é inofensivo → liberado na política |
| B6 | Mensagem no WhatsApp (CANCEL) | ⏳ Não testado |
| C7–C11 | Tarefas: completa, sem prazo, "depois eu vejo", listar, desfazer | ⏳ Não testados. Só um exemplo hipotético: rascunho criado, perguntou prazo/prioridade/duração e **não salvou** ✅ |

### Outros achados

- **Briefing com notícias dos EUA** (World Series, escolas da Geórgia): a busca do Mark era "top world news today". Trocada por "manchetes notícias Brasil hoje" (`jarvis/config.py`), que trouxe g1 e Reuters Brasil no próprio teste.
- **Ação sem sentido:** pedido de "mostrar em pop-up" virou `screen_find` + mover o mouse. Inofensivo, mas é ruído; observar nas próximas sessões.
- **Reabrir por voz depois de fechar:** "fechar" (`shutdown_jarvis`) encerra o programa; a palavra de ativação só funciona com ele aberto. Precisa de modo "em espera" + início com o Windows → Meta 7.

## Sessão 2 — 23/10/2026, 15:46 a 15:48

Encerrada pelo usuário (fechou a janela); não foi queda. Os testes de mensagem e tarefas não chegaram a ser feitos.

- ✅ Briefing com notícia do Brasil (BYD), depois da troca da busca.
- ✅ Notícia do GZH sobre o Inter encontrada.
- ❌ **Transcrição de português como inglês**: "The price is for you", "My face? Okay…". Uma delas fez o modelo tirar um print da tela sem motivo. Corrigido com `language_codes=["pt-BR"]` e vocabulário na transcrição (aceito pelo servidor em teste de conexão). Efeito no entendimento do modelo: Provável, a confirmar.
- Pedido do usuário: digitar/clicar sem clique → "sim" por voz.
- Pedido do usuário: aprender o jeito de falar → perfil de comunicação (base da M5).

## Sessão 3

*(pendente: "sim" por voz, mensagem com CANCEL, C7–C11 e `jarvis_perfil`)*
