# Ligar o Trello ao JARVIS

Você faz isso uma vez, com a sua conta do Trello. Leva uns 5 minutos. A chave e o token ficam em `config/trello.json`, que está fora do Git.

## 1. Chave (API key)

1. Abra <https://trello.com/power-ups/admin> com a sua conta.
2. Clique em **Novo** (New) e crie um Power-Up chamado `JARVIS`. Escolha o seu Workspace e informe o seu e-mail. A URL do iframe pode ficar em branco.
3. Abra o Power-Up, vá em **Chave de API** (API key) e clique em **Gerar nova chave de API**.
4. Copie a **chave**. Não use o "segredo" (secret); o JARVIS não precisa dele.

## 2. Token

Na mesma página da chave, clique no link **Token** ao lado dela. Se preferir, abra este endereço trocando `SUA_CHAVE` pela chave:

```
https://trello.com/1/authorize?expiration=never&scope=read,write&response_type=token&name=JARVIS&key=SUA_CHAVE
```

Clique em **Permitir** e copie o token que aparece.

- `scope=read,write` dá leitura e escrita nos seus quadros. O JARVIS só cria, move e arquiva cartões, e só cria as listas "A fazer" e "Feito" quando elas não existem.
- `expiration=never` evita reautorizar a cada 30 dias. Para revogar, veja o fim desta página.

## 3. Salvar e escolher o quadro

No terminal do projeto, com o `.venv` ativo:

```powershell
python -m jarvis.integrations.trello chave          # cola a chave e o token (não aparecem na tela)
python -m jarvis.integrations.trello quadros        # lista os seus quadros
python -m jarvis.integrations.trello usar "Pessoal" # troque pelo nome do quadro
```

O comando `usar` procura no quadro uma lista de tarefas novas ("A fazer", "To Do", "Tarefas", "Pendentes" ou "Backlog") e uma de concluídas ("Feito", "Concluído" ou "Done"). Se alguma faltar, ele cria no fim do quadro.

Para conferir:

```powershell
python -m jarvis.integrations.trello status
```

## O que o JARVIS faz no Trello

- **Tarefa nova** (depois do seu "sim" ao resumo): cria um cartão em "A fazer", com prazo e detalhes.
- **Tarefa com horário:** o cartão recebe também o link do compromisso no Google Calendar, depois do seu clique em CONFIRM.
- **Concluir:** move o cartão para "Feito".
- **Desfazer:** arquiva o cartão (no Trello, arquivar é reversível) ou devolve o cartão para "A fazer".

## Revogar o acesso

No Trello, abra o seu perfil, vá em **Configurações → Aplicativos** (Applications), encontre o JARVIS e clique em **Revogar**. Depois apague `config/trello.json`.
