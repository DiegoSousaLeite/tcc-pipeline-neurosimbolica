# higiene-repositorio

## Purpose

Definir o que entra no controle de versão e o que fica de fora, para que o repositório do TCC seja legível por quem tenta entendê-lo — a banca inclusive — e reproduzível a partir de um clone limpo.

O critério de corte é: **o que a pipeline lê, o que a monografia cita, ou o que reproduz a execução**. Fica versionado o código, os dados de entrada e gabaritos que não se recuperam sem refazer coleta de rede, a documentação e os CSVs de resultado citados. Fica fora tudo que um comando local regenera — bytecode, caches de ferramenta, SARIFs, rodadas, binários de apresentação — e esse material precisa ser *ignorado* pelo Git, não apenas estar ausente do índice: uma regra de `.gitignore` só age sobre arquivo ainda não rastreado, então bytecode que entrou num commit antigo permanece rastreado apesar da regra.

Define também `docs/` como fonte única da documentação de detalhe, com o `README.md` restrito a orientação inicial. A duplicação entre os dois não é redundância inofensiva: quando a mesma informação mora em três arquivos, a atualização é sempre parcial e a versão errada fica indistinguível da certa — o que já ocorreu neste repositório com contagens de casos e caminhos de saída.

E fixa um limite para a limpeza de comentários: nota que registra decisão de método é o que sustenta as escolhas na defesa, e vale mais preservada literalmente do que reescrita.

## Requirements

### Requirement: Classificação de artefatos entre versionado e derivado

O repositório SHALL versionar apenas quatro classes de arquivo: (a) código-fonte da pipeline, dos scripts de fase 0 e dos testes; (b) dados de entrada e gabaritos irrecuperáveis sem refazer coleta de rede (`data/*.json`, `tp_pairs*.json`); (c) documentação (`README.md`, `docs/`, `openspec/`); (d) CSVs de resultado citados pela monografia (`legacy/resultados_parte1/*.csv`).

Todo artefato que possa ser regenerado por um comando local SHALL ser ignorado pelo Git, e não apenas ausente do índice.

#### Scenario: Bytecode Python nunca é rastreado

- **WHEN** `git ls-files` é executado na raiz do repositório
- **THEN** a saída NÃO contém nenhum caminho terminado em `.pyc` nem nenhum caminho sob um diretório `__pycache__`

#### Scenario: Caches de ferramenta não aparecem como untracked

- **WHEN** `git status --short` é executado após uma execução de `pytest` e de `ruff`
- **THEN** nem `.pytest_cache/` nem `.ruff_cache/` aparecem na saída

#### Scenario: Gabaritos de entrada permanecem versionados

- **WHEN** `git ls-files` é executado
- **THEN** `tp_pairs.json`, `tp_pairs_osv.json`, `data/dataset_go_limpo.json`, `data/catalogo_cwe.json`, `data/tp_fixes.json` e `data/tp_fixes_osv.json` estão presentes na saída

#### Scenario: Resultados citados da Parte 1 permanecem versionados

- **WHEN** `git ls-files legacy/` é executado
- **THEN** os CSVs de `legacy/resultados_parte1/` e o `README.md` daquele diretório estão presentes, e nenhum arquivo `.py` está presente

#### Scenario: Regra genérica de artefato gerado não captura resultado citado

- **WHEN** uma regra do `.gitignore` que ignora artefato gerado por padrão de nome casa também com um CSV de `legacy/resultados_parte1/`
- **THEN** existe uma exceção explícita que mantém aqueles CSVs versionados, porque eles não são regeneráveis e a monografia cita seus números

#### Scenario: Binários da apresentação saem do versionamento sem sair do disco

- **WHEN** `git status --short` e `git ls-files apresentacao/` são executados
- **THEN** nenhuma das duas saídas contém caminho sob `apresentacao/`
- **AND** `apresentacao/index.html` continua existindo no disco

### Requirement: Ausência de código e rascunho órfãos

O repositório SHALL NOT conter arquivo de código, dado ou saída de ferramenta que não seja alcançável a partir de `run_pipeline.py`, dos testes, de um procedimento documentado em `docs/` ou de uma citação da monografia.

Código superado SHALL ser preservado apenas pelo histórico do Git, não por cópia em diretório de legado.

#### Scenario: Nenhum arquivo do repositório referencia caminho inexistente

- **WHEN** cada caminho de arquivo `.py`, `.json` ou `.md` mencionado em `README.md`, em `docs/*.md` e em comentário ou `print` de arquivo sob `src/`, `scripts/` e na raiz é resolvido no disco
- **THEN** todo caminho mencionado existe, exceto quando citado deliberadamente como caminho do histórico (`git show <ref>:<caminho>`)

#### Scenario: Diretório de rascunho de regra Semgrep foi removido

- **WHEN** o disco é inspecionado
- **THEN** `scripts/semgrep_test/` não existe

#### Scenario: A pipeline continua íntegra após a remoção

- **WHEN** `python -m pytest tests/ -q` e `python run_pipeline.py --tudo --dry-run` são executados
- **THEN** a suíte passa integralmente e o dry-run relata a mesma população e os mesmos braços que relatava antes da limpeza

### Requirement: `docs/` como fonte única da documentação de detalhe

Arquitetura da pipeline, semântica das trilhas e referência de módulos e scripts SHALL ser documentadas em exatamente um lugar, sob `docs/`. O `README.md` SHALL se limitar a propósito, instalação, execução, mapa de diretórios de uma linha por item e ponteiros para `docs/`.

#### Scenario: README não duplica a referência de scripts

- **WHEN** `README.md` é lido
- **THEN** ele não contém descrição de entradas, saídas e flags de script individual — apenas o ponteiro para `docs/SCRIPTS.md`
- **AND** ele tem no máximo 120 linhas

#### Scenario: Documentação reflete os arquivos existentes

- **WHEN** `docs/PIPELINE.md` e `docs/SCRIPTS.md` são lidos
- **THEN** nenhuma seção descreve script que não existe no repositório

### Requirement: Preservação do racional metodológico nos comentários

A limpeza de comentários SHALL remover apenas texto que repita o que o código já diz. Comentário ou docstring que registre decisão de método, invariante do experimento ou justificativa de escolha SHALL ser preservado literalmente.

#### Scenario: Decisões de método sobrevivem à limpeza

- **WHEN** o código é lido após a limpeza
- **THEN** continuam presentes as notas que explicam: a escolha de `p/default` sobre `p/golang`; por que `--reaproveitar-anteriores` é desligado por padrão; por que `tp_pairs*.json` não é gitignorado; por que o gabarito é por arquivo e não por linha; por que o `baseline` recebe só o contexto

#### Scenario: Nenhuma nota de autor sai da monografia

- **WHEN** `git status` e o diff da mudança são inspecionados
- **THEN** nenhum arquivo sob `TCC1___Diego_Sousa_e_João_Artur_Leles/` foi modificado
