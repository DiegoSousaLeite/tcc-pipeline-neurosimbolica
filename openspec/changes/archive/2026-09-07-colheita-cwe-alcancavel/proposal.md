## Why

`scripts/osv_harvest_go.py` colhe verdadeiros positivos da OSV sem nunca
consultar o ruleset. O cabeçalho é explícito: *"Todos os tipos de CWE. Filtros:
precisa de commit de fix + repo GitHub."*

O resultado, medido em `docs/ANALISE-RODADA-2.md`: **70,1% dos 107 casos
vulneráveis têm CWE que nenhuma regra Go do `p/default` declara.** São
indetectáveis por construção — o motor não pode falhar em achar o que não sabe
procurar. Apenas 1 caso vulnerável chegou ao LLM na última rodada.

A causa é viés de seleção em relação ao instrumento medido. As duas classes foram
montadas por caminhos opostos:

| classe | como foi selecionada | CWE alcançável |
|---|---|---|
| segura (841) | **a partir de achados do Semgrep** (SastBench) | 95,8% |
| vulnerável (107) | de CVEs via OSV, sem consultar o ruleset | **29,9%** |

A classe segura não poderia conter CWE desconhecida ao motor — ele não teria
alertado. A positiva nunca foi confrontada com essa restrição.

**Pergunta de pesquisa atendida:** prepara a metade não respondida da **Q2** —
*"reduzir falsos positivos **sem introduzir falsos negativos**"*
(`introducao.tex:38`). Esta mudança entrega a matéria-prima; a resposta empírica
vem em `rodada-classe-positiva`.

**Depende de:** `ruleset-alcancabilidade` (o módulo `src/ruleset.py`).

## What Changes

- **Filtro de alcançabilidade na colheita.** Candidata cuja CWE não é declarada
  por regra alguma da linguagem analisada é recusada.
- **Leitura de todas as CWEs da vulnerabilidade.** `extrai()` hoje lê
  `database_specific.cwe_ids` e fica com `cwes[0]`; passa a percorrer todas,
  aceitando se qualquer uma for alcançável e registrando **qual casou** — é essa
  que a Fase 1 vai procurar.
- **Relatório de colheita**: distribuição das aceitas, recusadas discriminadas por
  CWE, e a data do snapshot do ruleset. Serve para decidir prosseguir antes de
  investir na reconstrução de pares, que é a etapa cara.
- **Script `scripts/pares_alcancaveis.py`**, que identifica nos pools já colhidos
  os pares aproveitáveis — há 17 (4 em `tp_pairs.json`, 13 em
  `tp_pairs_osv.json`) — sem escrever nos pools de origem.
- **Saída em arquivo próprio**, sem sobrescrever `tp_fixes_osv.json` nem
  `tp_pairs_osv.json`.

## Capabilities

### New Capabilities
- `colheita-cwe-alcancavel`: seleção de candidatas a verdadeiro positivo restrita
  às CWEs que o motor cobre, com relatório de recusa e reaproveitamento dos pares
  já colhidos.

### Modified Capabilities
<!-- Nenhuma. `trilha-tp-dataset` continua carregando as entradas
     `true_positive` do dataset exatamente como hoje; esta mudança atua na
     colheita da OSV, que alimenta outra trilha. -->

## Impact

**Código**
- `scripts/osv_harvest_go.py` — filtro, relatório, CWE que casou
- `scripts/pares_alcancaveis.py` — novo
- `src/ruleset.py` — apenas consumido

**Dados** (artefatos de fase 0, não versionados)
- Saída da colheita em arquivo próprio
- `tp_pairs.json` — **preservado**. É irrecuperável: só
  `scripts/tp_reconstruct.py` o regenera, e ele exige o histórico git completo
  dos repositórios, que não está mais em disco
- `tp_pairs_osv.json` — **preservado**, com seus 34 pares originais

**Rede**
- A colheita consulta a API da OSV. Com `time.sleep(0.15)` e até 2 requisições
  por entrada, varrer alguns milhares leva dezenas de minutos.

**Resultados**
- Nenhum resultado existente é invalidado. Nenhuma rodada é reexecutada nesta
  mudança.

**Custo de LLM**
- Zero. Não há chamada de LLM nesta mudança.

## Não-objetivos

- **Não executar a colheita de verdade.** Esta mudança entrega a ferramenta e a
  cobre com testes; a execução com alvo definido é de `rodada-classe-positiva`.
- **Não montar população nem tocar em `run_pipeline.py`.** Isso é de
  `trilha-tp-alcancavel`.
- **Não escrever nada no TCC.**
- **Não sobrescrever os pools existentes.** Os pares inalcançáveis são evidência
  do achado dos 70%, não lixo a limpar.

## Onde isto se encaixa no TCC

Parte 2 — Fase 0 (preparação de dados). Não produz número para a monografia por
si só; habilita a rodada que produzirá.
