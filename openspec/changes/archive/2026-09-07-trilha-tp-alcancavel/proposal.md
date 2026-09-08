## Why

A colheita filtrada (`colheita-cwe-alcancavel`) produz um pool de pares novo, mas
`run_pipeline.py` não sabe lê-lo: a população é montada em `run_pipeline.py:952-953`
a partir de quatro trilhas fixas — `FP`, `TP_ouro`, `TP_prata` e `TP_dataset`.

Sobrescrever `tp_pairs_osv.json` com a colheita nova resolveria o acesso, mas
destruiria duas coisas: os 21 pares inalcançáveis da `TP_prata`, que são a
evidência do achado dos 70,1% registrado em `docs/ANALISE-RODADA-2.md`, e a
possibilidade de saber, depois da rodada, se o ganho de amostra veio da colheita
filtrada ou apenas do reaproveitamento de pares antigos.

Sem essa distinção não há como avaliar se o filtro funcionou.

**Pergunta de pesquisa atendida:** prepara a metade não respondida da **Q2**
(`introducao.tex:38`). Esta mudança dá à pipeline o caminho para os casos novos; a
resposta empírica vem em `rodada-classe-positiva`.

**Depende de:** `colheita-cwe-alcancavel` (o formato do pool novo).

## What Changes

- **Trilha `TP_alcancavel`**, lendo o pool produzido pela colheita filtrada,
  acrescentada a `TRILHAS` (`run_pipeline.py:288`) e à montagem da população
  (`run_pipeline.py:952-953`).
- **Rastreabilidade pela coluna `Origem`**, que já existe em
  `src/fase5_auditoria.py`: distinguir o que veio da colheita filtrada do que veio
  das trilhas antigas passa a sair sem código novo.
- **Preservação dos casos de CWE inalcançável.** As trilhas `TP_ouro`,
  `TP_prata` e `TP_dataset` permanecem na população como estão. Os casos que o
  motor não alcança continuam entrando na matriz de cobertura como ponto cego —
  são resultado do trabalho, não ruído a limpar.
- **Preservação da classe negativa.** Os 791 casos `FP` do SastBench mantêm os
  mesmos identificadores, sem renumeração.

## Capabilities

### New Capabilities
- `populacao-classe-positiva`: composição da população quanto ao eixo vulnerável
  — o que entra, o que permanece como evidência de ponto cego, e como a
  procedência de cada caso se mantém rastreável.

### Modified Capabilities
<!-- Nenhuma. `trilha-tp-dataset` e `matriz-experimental` continuam com os
     mesmos requisitos: esta mudança acrescenta uma trilha e não altera o
     carregamento, o checkpoint nem o manifesto existentes. -->

## Impact

**Código**
- `run_pipeline.py` — `TRILHAS` e montagem da população
- `src/fase5_auditoria.py` — **sem alteração**; `Origem` já é coluna do CSV
- `src/fase1_semgrep.py`, `src/fases3_4_llm.py` — **sem alteração**

**Dados**
- Nenhum artefato de dados é modificado. A trilha apenas **lê** o pool novo.
- Se o pool ainda não existir, a trilha fica vazia — `construir_casos_tp` já
  trata arquivo ausente.

**Resultados**
- Nenhum resultado existente é invalidado. Nenhuma rodada é executada nesta
  mudança.
- A população passa a ser maior que a das rodadas anteriores, o que torna a
  rodada futura não comparável caso a caso com elas. A comparação legítima passa
  a ser entre braços **dentro** da rodada nova.

**Custo de LLM**
- Zero. Não há chamada de LLM nesta mudança.

## Não-objetivos

- **Não executar rodada alguma.** É de `rodada-classe-positiva`.
- **Não colher nem reconstruir pares.** É de `colheita-cwe-alcancavel` e da
  execução em `rodada-classe-positiva`.
- **Não remover os casos de CWE inalcançável.** Decisão tomada: eles ficam. São a
  evidência dos 70,1%, e não contaminam a matriz de acerto do LLM porque nunca
  chegam a ela — sem emparelhamento na Fase 1, não há chamada de LLM.
- **Não mexer na classe negativa.** Os 791 casos de falso positivo permanecem
  idênticos, com os mesmos IDs.
- **Não alterar checkpoint, manifesto ou métricas.**
- **Não escrever nada no TCC.**

## Onde isto se encaixa no TCC

Parte 2 — composição da amostra. Não produz número por si só; é o que permite à
rodada seguinte produzir.
