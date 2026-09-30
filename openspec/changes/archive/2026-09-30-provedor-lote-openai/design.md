## Context

O protocolo `ProvedorLote`, a partição, o `lote.json`, a retomada, o desfecho
`EXPIRADO` e as métricas de custo faturado já existem
(`envio-em-lote-comercial`). Aqui entra só o que é próprio da OpenAI. Fontes,
consultadas em 2026-09-30: `developers.openai.com/api/docs/models/gpt-6-luna`,
`/guides/batch` e `/guides/latest-model`.

## Decisions

### D1 — Raciocínio `none` e temperatura 0, e não raciocínio padrão sem temperatura

A OpenAI diz: "When reasoning effort is not `none`, remove `temperature`,
`top_p`, and `top_logprobs`", e o padrão do Luna é `medium`. Havia duas saídas:
manter o raciocínio e tirar a temperatura, ou desligar o raciocínio e manter a
temperatura 0.

**Decisão:** `reasoning_effort: "none"` com `temperature: 0`.

**Por quê:** é a condição dos outros braços — temperatura 0, resposta direta. Um
raciocínio escondido, que o prompt não controla, entraria como variável do
experimento sem ser a variável estudada, e seria cobrado como saída. A lista de
modelos é explícita (`MODELOS_RACIOCINIO_NONE`), e não por prefixo, porque o
GPT-6 Astra e o GPT-6.1 Sol não aceitam `none`, e o `gpt-4o-mini` não conhece o
parâmetro.

**Consequência a declarar no texto:** o Luna é avaliado **sem** raciocínio. Um
resultado ruim dele não diz nada sobre o Luna com raciocínio.

### D2 — Rótulo do cliente em `metadata.rotulo`

A retomada (D3 de `envio-em-lote-comercial`) precisa achar um lote cuja criação
pode ter ocorrido sem que o identificador chegasse ao disco. No Gemini o rótulo
vai em `display_name`; na OpenAI, em `metadata`, e `localizar` percorre
`GET /v1/batches` paginado comparando `metadata.rotulo`. Um arquivo subido sem
lote criado não custa nada.

### D3 — Expirada não é cobrada

"You will be charged for tokens consumed from any completed requests": o lote
que expira devolve as concluídas no arquivo de saída e as demais no de erro com
`batch_expired`. Estas viram `EXPIRADO`, sem custo (`cobra_expirada = False`).

### D4 — Limites

Fila do `gpt-6-luna` no Tier 1: 5.000.000 tokens (Tier 2: 20.000.000),
sobrescrevível por `OPENAI_LOTE_TOKENS_ENFILEIRADOS`. Por lote: 50.000
requisições e 200 MB. Modelo sem fila verificada cai em 2.000.000. Uma rodada de
dois braços (~3,2 M tokens) cabe num lote só no Luna.

## Risks / Trade-offs

**[Formato só verificado em dublê]** → os testes seguem a documentação, e não
uma resposta real. Mitigação: `scripts/validar_lote.py --modelo gpt-6-luna`
antes de qualquer rodada (tarefa 3.1).

**[Luna é o modelo econômico da linha GPT-6]** → a pergunta "vocês testaram um
modelo bom?" que recusou os "mini" em `docs/ESCOLHA-MODELO-COMERCIAL.md` §4.3
vale aqui também. A decisão de modelo é da `rodada-comercial`, e precisa estar
escrita lá.
