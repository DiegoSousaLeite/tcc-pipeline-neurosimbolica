## Context

Aberta pela tarefa 7.1 de `envio-em-lote-comercial`, antes do arquivamento
dela, para que a capacidade construída lá não fique sem consumidor. Os insumos:

- o modo de envio em lote, pronto (`--modo-envio lote`), com provedores Gemini e
  — desde 2026-09-30, change `provedor-lote-openai` — OpenAI;
- `docs/ESCOLHA-MODELO-COMERCIAL.md`, com preços, limites e a recomendação
  (`claude-sonnet-5`), consultados em 2026-09-17;
- os quatro pontos de `editaveis/resultados.tex` marcados `RODADA COMERCIAL`.

Correção registrada em 2026-09-28, ao implementar o lote: o teto de
enfileiramento do **Tier 1 para o `gemini-2.5-flash-lite` é 10.000.000 de
tokens**, e não 3.000.000 (esse é o do 2.5 Flash e do 3.8 Flash). Uma rodada de
dois braços — ~3,2 M tokens de entrada — cabe inteira num lote do Flash-Lite. O
teto soma todos os lotes ativos do modelo, e por isso a pipeline submete as
partições uma de cada vez.

## Goals / Non-Goals

**Goals:**

- Produzir vereditos comerciais sobre a população de referência, comparáveis às
  rodadas locais braço a braço.
- Fechar os pontos da monografia que só esta rodada fecha.

**Non-Goals:**

- Reabrir prompt, população, catálogo ou modo de montagem.
- Matriz comercial completa quando o orçamento não a cobrir.

## Decisions

### D1 — O braço de filtro primeiro; o de triagem é extensão opcional

**Decisão:** se o orçamento só cobrir parte, roda o braço de **filtro** (modo de
montagem `filtro`, `baseline` × `especialista`). O braço de **triagem** só roda
depois, e só se houver orçamento.

**Por quê:** é no braço de filtro que moram Q1, Q2 e Q3 — o sistema como ele
opera, com o LLM como filtro puro do Semgrep. E é a metade mais barata: ~1.654
chamadas, contra ~3.200 do braço de triagem, que soma aos alertas os positivos
injetados do gabarito. O braço de triagem mede o componente neural isolado; é
resultado interessante, mas não é o que a objeção de escopo pergunta.

### D2 — Um modelo comercial, da OpenAI; Gemini descartado

**Revisão de 2026-09-30.** A versão de 2026-09-28 restringia a matriz ao Gemini
por falta de `OPENAI_API_KEY`. Desde então a situação se inverteu: a chave da
OpenAI existe, com crédito, e o lote do `gpt-6-luna` foi validado contra o
fornecedor real; o projeto do Gemini não tem billing, e o lote dele é recusado
(`FAILED_PRECONDITION`). **Os autores descartaram o Gemini.**

**Decisão:** a matriz comercial tem um modelo, da OpenAI. **A conclusão continua
sendo "três modelos, um comercial"** — `qwen2.5-coder:7b`, `gemma2:9b` e o
modelo da OpenAI —, e não "quatro, dois comerciais", como o desenho original da
matriz 2x2 previa.

**Por quê:** declarar o escopo que de fato se mede, e não o planejado.

### D3 — Piloto e rodada no mesmo modo de envio

**Decisão:** se houver piloto de decisão de modelo, ele roda no mesmo modo de
envio da rodada (`lote`).

**Por quê:** a spec `matriz-experimental` proíbe modos de envio diferentes
dentro de uma rodada; entre piloto e rodada a proibição não é formal, mas o
argumento é o mesmo — um piloto síncrono e uma rodada em lote não são
comparáveis entre si, e o piloto deixaria de prever a rodada.

### D4 — Modelo: `gpt-6-luna`, sem raciocínio e com temperatura 0

**Decisão dos autores (2026-09-30):** o modelo comercial da rodada é o
**`gpt-6-luna`**, com `reasoning_effort: "none"` e temperatura 0. A recomendação
anterior de `docs/ESCOLHA-MODELO-COMERCIAL.md` §4, `claude-sonnet-5`, fica
registrada e não seguida.

**Justificativa** (argumentos para o texto; redação final dos autores):

- **Realismo de uso.** Triagem de alertas de SAST acontece em volume, a cada
  commit; um modelo comercial econômico é o que uma equipe usaria em operação.
- **A pergunta é de escopo, não de teto.** A limitação atual restringe as
  conclusões a modelos locais de 7 a 9 B. O Luna é de outra natureza —
  comercial, geração corrente, janela de 1,05 M tokens, sem quantização — e
  testa se o observado é artefato de modelo local pequeno: resultado igual
  reforça a conclusão, diferente a delimita.
- **População completa.** Pelo custo (D6), roda sobre os 2.328 casos, duas
  vezes, e ainda o braço de triagem — um modelo caro, no mesmo orçamento,
  forçaria amostragem e tiraria poder do McNemar pareado.
- **Literatura.** O `gemini-2.5-pro`, de fronteira, suprimiu demais no conjunto
  real do ZeroFalse (já citado no capítulo): escala sozinha não resolve a
  supressão, e presumir "maior = melhor" não é premissa segura.

**Delimitação que o texto passa a carregar** (substitui "modelos de fronteira"):
"um modelo comercial econômico, sem raciocínio; o comportamento de modelos de
topo e do mesmo modelo com raciocínio não foi medido".

Duas consequências que o texto precisa carregar:

- **O Luna roda sem raciocínio** (`reasoning_effort: "none"`, temperatura 0 —
  D1 de `provedor-lote-openai`). É a condição dos modelos locais; o resultado
  descreve o Luna respondendo direto, não o Luna com raciocínio.
- **O Luna é o modelo econômico da linha GPT-6.** A objeção "vocês testaram um
  modelo bom?", que recusou os "mini" na §4.3 do documento de escolha, vale
  para ele — e é respondida pela justificativa e pela delimitação acima.

### D5 — Medir a variação do modelo comercial entre execuções

**Achado de 2026-09-30** (`provedor-lote-openai`, tarefa 3.1): o `gpt-6-luna`,
com temperatura 0 e raciocínio `none`, mudou 3 de 20 vereditos entre duas
execuções idênticas. Os modelos locais rodaram com semente fixa; o comercial
não tem essa garantia.

**Decisão dos autores (2026-09-30):** **os dois braços** — filtro e triagem —
rodam **duas vezes** cada, e a concordância entre as execuções é reportada, como
as Rodadas 4–6 já fizeram com a reexecução. Sem isso, uma diferença entre
`baseline` e `especialista` no McNemar não se distingue da variação do próprio
modelo.

A triagem entrou depois do filtro, pelo mesmo argumento e por um mais forte:
das 3 trocas de veredito da validação, 2 foram em casos **vulneráveis**
(CWE-601 `vuln`, CWE-79 do `TP_dataset`), e é sobre os positivos que o braço de
triagem mede o componente neural. Com uma execução só, o recall dos injetados
sairia sem a variação ao lado — e a comparação com a Rodada 4, a triagem local,
que foi reexecutada, ficaria desigual justamente nesse braço.

### D6 — Orçamento e plano de execução

**Decisão dos autores (2026-09-30):** teto de **US$ 2**. Plano, nesta ordem:
filtro (execução 1), filtro (execução 2), triagem (execução 1), triagem
(execução 2) — o braço de triagem deixa de ser só condicional (D1) e entra no
plano, depois do filtro.

**Uma execução de cada vez.** A fila do Luna (5 M tokens no Tier 1) soma todos
os lotes ativos do modelo; duas execuções da triagem juntas (~6,2 M) a
estourariam. A pipeline já submete as partições de uma execução em sequência,
mas não coordena execuções diferentes: a próxima só começa quando a anterior
terminou.

**Estimativa** (2026-09-30), com os prompts reais montados pela própria
pipeline (`processar_caso` com coletor, sem rede) e tokens calibrados em 59
medições reais do Luna (tokens ≈ 0,261 × caracteres + 19; erro máximo 9,9 %;
saída média 96 tokens), a preço de lote (US$ 0,05 / 0,25 por 1 M):

| execução | requisições | tokens de entrada | custo em lote |
|---|---:|---:|---:|
| filtro (cada uma) | 1.666 | ~1,57 M | ~US$ 0,12 |
| triagem (cada uma) | 3.194 | ~3,09 M | ~US$ 0,23 |
| **plano: filtro 2× + triagem 2×** | **9.720** | **~9,3 M** | **~US$ 0,70 ≈ R$ 3,60** |

Folga de ~2,9× sobre o teto; mesmo com todas as respostas no maior tamanho
observado (151 tokens), o plano fica abaixo de US$ 0,85. A maior execução (triagem, ~3,1 M tokens) cabe
inteira na fila de 5 M do Tier 1 — um lote por execução.

## Risks / Trade-offs

**[Orçamento nunca autorizado]** → os pontos da monografia ficam com a
delimitação atual, que já é honesta. Mitigação: esta change não bloqueia o
capítulo (`escrita-capitulo-resultados`, tarefa 11.3).

**[Expiração parcial]** → requisições `EXPIRADO` não são reenviadas
automaticamente; um reenvio é decisão consciente de gasto, pelo procedimento de
`docs/SCRIPTS.md`, "Modo de envio em lote".

## Open Questions

(nenhuma pendente de decisão: modelo, orçamento e número de execuções
decididos em 2026-09-30 — D4, D5, D6)
