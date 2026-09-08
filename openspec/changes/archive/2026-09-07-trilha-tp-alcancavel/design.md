## Context

A população é montada em `run_pipeline.py:952-953` somando quatro trilhas:

| trilha | fonte | casos | vulneráveis |
|---|---|---|---|
| `FP` | `data/dataset_go_limpo.json` (SastBench) | 791 | 0 |
| `TP_ouro` | `tp_pairs.json` | 32 | 16 |
| `TP_prata` | `tp_pairs_osv.json` | 68 | 34 |
| `TP_dataset` | `data/dataset_go_limpo.json` (`true_positive`) | 57 | 57 |

`TRILHAS` está em `run_pipeline.py:288`; `construir_casos_tp(arquivo, rotulo,
cwe_meta)` carrega um pool de pares e já trata arquivo ausente devolvendo lista
vazia. `Origem` é coluna do CSV desde `src/fase5_auditoria.py:16`.

Esta mudança depende de `colheita-cwe-alcancavel`, que define o formato e o
caminho do pool novo.

## Goals / Non-Goals

**Goals:**
- Dar à pipeline um caminho para os pares da colheita filtrada
- Manter a procedência de cada caso rastreável nos resultados
- Preservar as trilhas existentes, a classe negativa e os identificadores

**Non-Goals:**
- Executar rodada, colher ou reconstruir pares
- Alterar checkpoint, manifesto, métricas ou prompts
- Remover os casos de CWE inalcançável
- Escrever qualquer coisa no TCC

## Decisions

### D1 — Trilha nova, não substituição do pool da `TP_prata`

*Por quê:* três motivos convergem.

1. Sobrescrever `tp_pairs_osv.json` destruiria os 21 pares inalcançáveis, que são
   a evidência do achado dos 70,1%.
2. `tp_pairs.json` (`TP_ouro`) é irrecuperável: exige histórico git completo, que
   não está mais em disco.
3. A rastreabilidade sai de graça — ver D2.

*Alternativa descartada:* acrescentar um campo "alcançável" a cada par nos pools
existentes. Exigiria reescrever os pools (arriscado, ver motivo 2) e ainda assim
não distinguiria colheita nova de reaproveitamento.

### D2 — A rastreabilidade vem da coluna `Origem`, sem estrutura nova

*Por quê:* `Origem` já existe no CSV e já carrega o rótulo da trilha. Um rótulo
próprio para a trilha nova entrega o requisito de rastreabilidade sem uma linha
de código de auditoria. Contar por procedência vira um agrupamento no CSV.

### D3 — Casos de CWE inalcançável permanecem na população

*Decisão do autor, questão em aberto resolvida.*

*Por quê:* eles são resultado, não ruído. Sustentam a afirmação de que 70,1% das
fraquezas do corpus estão fora do alcance da análise sintática — número que a
monografia vai usar no capítulo de limitações.

*Por que não contaminam as métricas do LLM:* sem emparelhamento na Fase 1, não há
chamada de LLM. Eles entram na matriz de **cobertura** (onde são ponto cego, que
é o que de fato são) e ficam fora da matriz de **acerto** por construção. As duas
matrizes são separadas justamente para isso.

*Custo aceito:* o recall do Semgrep na população nova continuará baixo, porque o
denominador inclui os inalcançáveis. Isso é a realidade sendo medida, e a
comparação com as rodadas anteriores é preservada.

### D4 — Reaproveitamento sem duplicar caso

Os 17 pares já alcançáveis dos pools atuais **já estão** na população pelas
trilhas `TP_ouro` e `TP_prata`. Eles não devem ser recarregados pela trilha nova.

*Por quê:* carregá-los duas vezes criaria identificadores duplicados, e
`metricas.py` deduplica pela **primeira** ocorrência — o caso apareceria uma vez
só, mas com procedência ambígua, destruindo justamente a rastreabilidade que D2
entrega. A trilha nova carrega apenas o que a colheita filtrada produziu.

*Consequência:* "aproveitar os 17 pares" significa **não descartá-los**, não
movê-los de trilha. Eles continuam contando como `TP_ouro` e `TP_prata`.

### D5 — Fases e arquivos tocados

| fase | arquivo | o que muda |
|---|---|---|
| — | `run_pipeline.py` | `TRILHAS` (:288) e montagem (:952-953) |
| 1 | `src/fase1_semgrep.py` | **sem alteração** |
| 3/4 | `src/fases3_4_llm.py` | **sem alteração** |
| 5 | `src/fase5_auditoria.py` | **sem alteração** — `Origem` já existe |
| doc | `docs/PIPELINE.md` | composição da população |

**Custo de LLM:** zero.
**Tempo:** desprezível; a verificação é por `--dry-run`.

## Risks / Trade-offs

**[Identificadores colidirem entre trilhas]** → o checkpoint é por tripla
`(ID_Caso, Modelo_LLM, Tipo_Prompt)`, e IDs repetidos fariam casos distintos
serem tratados como o mesmo. **Mitigação:** o rótulo de origem entra no
identificador, como nas demais trilhas; a tarefa de verificação confere 0 IDs
duplicados sobre a população inteira antes de qualquer rodada.

**[Renumeração acidental da classe negativa]** → o índice no ID do caso vem da
posição **original** na lista de locations, antes de qualquer filtro. Um ajuste
descuidado na montagem quebraria os CSVs já gerados e o checkpoint entre rodadas.
**Mitigação:** teste que compara os IDs de origem `FP` com os do CSV de
`results/20260731T140000Z-af9bc32`.

**[População nova não comparável caso a caso com as anteriores]** → acrescentar
trilha muda a população. **Mitigação:** é consequência aceita e declarada; a
comparação legítima passa a ser entre braços dentro da rodada nova, e as rodadas
antigas permanecem em disco, comparáveis entre si. Nada é invalidado.

**[Trilha vazia passar despercebida]** → se o pool não existir, a trilha carrega
zero casos silenciosamente, e uma rodada poderia ser executada sem os casos
novos. **Mitigação:** a verificação por `--dry-run` da tarefa 1.3 conta os casos
da trilha antes de qualquer execução real.
