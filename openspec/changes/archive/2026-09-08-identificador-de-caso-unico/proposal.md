## Why

A montagem da população produz **18 identificadores repetidos**, todos na trilha
`TP_alcancavel`. São **46 casos envolvidos e 28 que desapareceriam em silêncio**:
o checkpoint por tripla `(ID_Caso, Modelo_LLM, Tipo_Prompt)` trata o segundo
como já gravado, e `src/metricas.py` deduplica pela primeira ocorrência.

A causa é o esquema de identificador de `run_pipeline.construir_casos_tp`:

```python
base_id = f"{prefixo_id}{repo_dir}:{cwe}:{funcao}"     # run_pipeline.py:354
```

O **arquivo não entra**. Em Go o mesmo nome de método aparece em vários arquivos
do mesmo pacote, e um único fix os altera juntos:

```
TPA:go-git:CWE-345:Decode:vuln  →  plumbing/object/commit.go
                                   plumbing/object/tag.go
                                   plumbing/object/tree.go
```

Três casos distintos, um identificador. `tp_pairs.json` (16 pares) e
`tp_pairs_osv.json` (34 pares) nunca expuseram isso — no máximo um fix por repo.
O pool da colheita filtrada tem 257 pares em 83 repositórios, com até 5 fixes por
repo, e expõe.

Metade dos 28 casos perdidos é da classe vulnerável, ou seja, o dano cai
exatamente sobre a classe que `rodada-classe-positiva` existe para aumentar.

**Descoberto durante** a tarefa 3.1 de `rodada-classe-positiva`, que exige 0 IDs
duplicados. Aquela mudança declara não alterar código de produto e mandar o
defeito virar mudança própria — é esta.

## What Changes

- **Identificador de caso único dentro da trilha, não só entre trilhas.** O
  esquema passa a incluir um discriminador derivado do caminho do arquivo, nos
  pools carregados sob prefixo próprio.
- **Identificadores das trilhas antigas congelados.** `TP_ouro` e `TP_prata`
  continuam byte a byte iguais aos gravados nos CSVs e no checkpoint das rodadas
  anteriores. É a razão de `prefixo_id` existir, e ela não muda.
- **Colisão passa a falhar alto.** A montagem da população recusa-se a seguir com
  identificador repetido, em vez de deixar o checkpoint engolir o caso.
- **Lacuna de cache fechada.** `scripts/preencher_cache.py` monta `casos_unicos()`
  só com `TP_PAIRS_OURO` e `TP_PAIRS_PRATA`; a trilha nova ficou de fora, e a
  Fase 1 dependeria de rede nos 360 alvos dela.

## Capabilities

### Modified Capabilities
- `populacao-classe-positiva`: a unicidade do identificador passa a ser exigida
  **dentro** de cada trilha, não apenas entre trilhas, e a violação passa a ser
  ruidosa. Acrescenta-se que os alvos da trilha nova são preenchíveis pela
  ferramenta padrão de cache.

## Impact

**Código**
- `run_pipeline.py` — esquema de identificador e guarda de colisão
- `scripts/preencher_cache.py` — inclui a trilha `TP_alcancavel`
- `tests/test_populacao.py` — o teste de unicidade hoje usa um pool de **um** par,
  e por isso nunca exercitou a colisão dentro do pool

**Dados**
- Nenhum artefato regenerado. O pool `tp_pairs_osv_alcancavel.json` não muda; o
  que muda é o identificador que a montagem deriva dele.

**Resultados**
- Nenhuma rodada existente é afetada: a trilha `TP_alcancavel` nunca rodou, então
  nenhum CSV ou checkpoint carrega os identificadores que mudam.

**Custo**
- Zero em rede, LLM e cota. Alteração local com suíte.

## Não-objetivos

- **Não renumerar `FP`, `TP_ouro`, `TP_prata` nem `TP_dataset`.**
- **Não executar rodada.** Esta mudança desbloqueia a tarefa 3.1 de
  `rodada-classe-positiva`; a execução continua lá.
- **Não tocar em arquivo `.tex`.**
