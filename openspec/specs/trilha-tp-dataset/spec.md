# trilha-tp-dataset

## Purpose

Carregar as entradas `ground_truth="true_positive"` de `data/dataset_go_limpo.json` como casos de gabarito vulnerável, complementando as trilhas `TP_ouro` e `TP_prata`.

Existe porque o eixo de verdadeiros positivos da pipeline era pequeno demais para dar poder ao teste de McNemar: das 50 amostras vulneráveis dos pares TP, apenas 4 sobreviviam à Fase 1. As 36 entradas `true_positive` do dataset nunca eram carregadas — `construir_casos_fp` descarta tudo que não é `false_positive` — e não são redundantes com a trilha ouro: esta aponta o `commit_hash` em que o SastBench de fato escaneou, com todas as suas locations, enquanto a ouro analisa o `parent_commit` do fix com um arquivo por par.

A trilha também carrega a limitação de rótulo mais importante da amostra: do lado TP o gabarito é resultado de mineração de commit de fix, não de julgamento por alerta.

## Requirements

### Requirement: Carregamento das amostras true_positive do dataset
O sistema SHALL construir casos de avaliação a partir das entradas de `data/dataset_go_limpo.json` cujo `ground_truth` é `"true_positive"`, atribuindo a elas `gabarito = "vulneravel"` e `origem = "TP_dataset"`, sem alterar o carregamento das entradas `false_positive`.

#### Scenario: Entrada true_positive vira caso vulnerável
- **WHEN** o dataset contém uma entrada com `ground_truth == "true_positive"` e uma location `.go`
- **THEN** a lista de casos contém um caso com `gabarito == "vulneravel"`, `origem == "TP_dataset"` e `commit` igual ao `commit_hash` da entrada

#### Scenario: Entrada false_positive não é afetada
- **WHEN** `construir_casos_fp` é executada sobre o mesmo dataset
- **THEN** ela produz exatamente o mesmo conjunto de casos que produzia antes da mudança, com os mesmos IDs

#### Scenario: Trilhas TP_ouro e TP_prata permanecem
- **WHEN** a pipeline é executada em modo `--tp-only`
- **THEN** os casos das trilhas `TP_ouro` e `TP_prata` continuam presentes, somados aos de `TP_dataset`

### Requirement: Filtro de arquivos de teste
O sistema SHALL descartar locations cujo nome de arquivo termina em `_test.go` ao construir casos da trilha `TP_dataset`, alinhando-se ao filtro já aplicado pela trilha ouro em `scripts/tp_reconstruct.py`.

#### Scenario: Arquivo de teste é descartado
- **WHEN** uma entrada `true_positive` tem a location `router/middleware/header_test.go`
- **THEN** nenhum caso é gerado para essa location

#### Scenario: Entrada só com arquivos de teste não gera caso
- **WHEN** todas as locations `.go` de uma entrada terminam em `_test.go`
- **THEN** a entrada não contribui com nenhum caso

### Requirement: Deduplicação de alvos repetidos
O sistema SHALL gerar no máximo um caso por combinação de repositório, commit, arquivo e CWE na trilha `TP_dataset`, mantendo a primeira ocorrência na ordem original.

As entradas `true_positive` listam uma location por **função** alterada pelo commit de fix, então o mesmo arquivo reaparece várias vezes na mesma entrada — 108 locations `.go` para 66 alvos distintos. Como a pipeline analisa o arquivo inteiro, cada repetição produziria o mesmo veredito: duplicaria a evidência na matriz de confusão e gastaria uma chamada de LLM por braço à toa.

#### Scenario: Arquivo repetido na mesma entrada gera um caso só
- **WHEN** uma entrada `true_positive` lista o mesmo arquivo em duas locations, em funções diferentes
- **THEN** apenas um caso é gerado para aquele arquivo

#### Scenario: Trilha FP não é deduplicada
- **WHEN** `construir_casos_fp` é executada
- **THEN** todas as suas locations `.go` continuam gerando um caso cada, porque ali cada location já é um alvo distinto

### Requirement: Identificadores estáveis e não colidentes
O sistema SHALL gerar IDs da trilha `TP_dataset` com prefixo distinto dos IDs já usados, e SHALL derivar o índice de location da posição original na lista, antes de qualquer filtro.

#### Scenario: ID não colide com resultados anteriores
- **WHEN** um caso da trilha `TP_dataset` é gerado a partir do `finding_id` X
- **THEN** seu ID começa por `TPD:` e não é igual a nenhum ID presente nos `resultados_tcc*.csv` existentes

#### Scenario: Filtro não renumera locations
- **WHEN** as locations de índice 0 e 2 são `.go` válidas e a de índice 1 é `_test.go`
- **THEN** os casos gerados carregam os índices originais 0 e 2, nunca 0 e 1

### Requirement: Registro de num_locations
O sistema SHALL registrar, em cada caso e em cada linha de CSV dele derivada, o número total de locations da entrada de origem, contado antes de qualquer filtro.

#### Scenario: Contagem anterior aos filtros
- **WHEN** uma entrada tem 11 locations das quais 3 são descartadas por não serem `.go` ou por serem `_test.go`
- **THEN** todas as linhas de CSV geradas por essa entrada registram `Num_Locations == 11`

#### Scenario: Coluna presente para todas as trilhas
- **WHEN** um caso de qualquer trilha é registrado no CSV
- **THEN** a coluna `Num_Locations` está presente, com valor `1` para casos que não vêm de entradas agregadas

### Requirement: Documentação da assimetria de rótulo entre trilhas
A documentação do projeto SHALL registrar explicitamente que `metadata.source` é `semgrep` nas entradas `false_positive` (julgamento por alerta) e `cvefixes` nas entradas `true_positive` (mineração de commit de fix), e que portanto o rótulo do lado TP afirma que o commit corrigiu uma CVE, não que cada arquivo é a vulnerabilidade.

#### Scenario: README corrigido
- **WHEN** um leitor consulta o `README.md`
- **THEN** a afirmação de que "cada location é um achado independente e rotulado" está qualificada como válida apenas para o lado FP

#### Scenario: Limitação registrada com evidência
- **WHEN** um leitor consulta `docs/PIPELINE.md`
- **THEN** a assimetria está descrita como limitação declarada da amostra, citando o caso de CVE-2025-27616 / CWE-290, cuja entrada tem 11 locations incluindo um arquivo `_test.go`

### Requirement: Disponibilidade dos arquivos-alvo da nova trilha
O sistema SHALL permitir preencher o cache de fontes dos alvos da trilha `TP_dataset` sem exigir clone de repositório, usando o script de preenchimento de cache existente.

#### Scenario: Alvos faltantes são baixados
- **WHEN** `scripts/preencher_cache.py` é executado para os alvos da trilha `TP_dataset`
- **THEN** os arquivos passam a existir sob `cache/<owner>__<repo>/<commit>/<caminho>.go` e a pipeline os resolve sem rede em execuções seguintes

#### Scenario: Execução offline após preenchimento
- **WHEN** a pipeline roda a trilha `TP_dataset` com o cache preenchido e sem acesso à rede na Fase 1
- **THEN** nenhum caso termina em `FETCH_FAIL`
