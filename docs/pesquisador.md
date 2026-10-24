# Modo pesquisador

Código: `jarvis/pesquisa/` (fontes.py, pesquisador.py). Entra pelo `web_search` do Mark, nos modos `search` e `research`. Notícias, preço e comparação continuam no caminho do Mark.

## Como funciona

1. **Busca:** Tavily, se houver chave. Senão, DuckDuckGo.
2. **Leitura:** as 3 melhores páginas que vieram sem texto são lidas em paralelo. Primeiro a leitura direta (menos de 1 s); se a página bloquear ou vier vazia, o Jina Reader (5 a 7 s). Vídeos e redes sociais não são lidos.
3. **Trechos:** de cada página ficam só as frases que citam o que foi perguntado (até 1.200 caracteres por página, 4.500 no total).
4. **Prazo:** 10 s para tudo. O que não chegar a tempo fica de fora.
5. **Memória curta:** a mesma pergunta em menos de 10 min não busca de novo.
6. **Sem loop:** o resultado termina com `[RESEARCH_DONE]`, e o prompt manda responder na hora, sem pesquisar de novo.

Quem responde é o modelo de voz, lendo os trechos. Não há um segundo modelo resumindo, então não há mais uma espera nem mais cota gasta. Por isso o Groq do plano inicial não foi necessário. Se um dia fizer falta, o Mark já aceita Groq em ⚙ → ENGINE & PROVIDERS.

Medido em 23/10/2026: "texto da meditação do pôr do sol de 23 de outubro de 2026" voltou em 3,1 s, com 3 páginas lidas (antes: 6 buscas e nenhuma resposta).

## Ligar o Tavily (opcional, recomendado)

Grátis: 1.000 buscas por mês, sem cartão. Cada busca do Jarvis gasta 1 crédito.

1. Crie a conta em https://app.tavily.com e copie a chave (começa com `tvly-`).
2. Em `config/api_keys.json` (fora do Git), acrescente:
   ```json
   "tavily_api_key": "tvly-..."
   ```
3. Reinicie o Jarvis. No terminal aparece `[Pesquisa] tavily: ...` em vez de `[Pesquisa] ddg: ...`.

Se o Tavily falhar ou a cota acabar, a pesquisa volta sozinha para o DuckDuckGo.

## Testes

`pytest tests/test_pesquisador.py`
