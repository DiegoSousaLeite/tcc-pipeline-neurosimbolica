## ADDED Requirements

### Requirement: Comparação lado a lado dos braços
O sistema SHALL calcular as métricas de acerto do LLM (Precisão, Recall, F1, MCC, TRA, TFN) para cada braço da matriz e apresentá-las em tabela única lado a lado, a partir dos resultados de uma rodada.

#### Scenario: Tabela com os quatro braços
- **WHEN** as métricas são geradas para uma rodada completa
- **THEN** a saída contém uma linha por braço `(modelo, tipo de prompt)` com todas as métricas

#### Scenario: Duas matrizes permanecem separadas
- **WHEN** as métricas são geradas
- **THEN** a matriz de cobertura simbólica do Semgrep continua reportada separadamente da matriz de acerto neural do LLM

#### Scenario: Estratificação disponível
- **WHEN** as métricas são geradas
- **THEN** é possível estratificar por trilha de origem, por `Num_Locations` e por origem da ficha de CWE, sem reexecutar a pipeline

### Requirement: Teste de McNemar entre braços
O sistema SHALL aplicar o teste de McNemar sobre pares de braços, restrito às amostras que ambos classificaram com veredito válido, reportando a tabela de discordâncias e o p-valor.

#### Scenario: Amostras pareadas
- **WHEN** dois braços são comparados
- **THEN** apenas os `ID_Caso` com veredito válido nos dois braços entram no teste, e a contagem usada é reportada

#### Scenario: Escolha do teste por volume de discordâncias
- **WHEN** o total de discordâncias é menor que 25
- **THEN** o p-valor vem do teste binomial exato; caso contrário vem do qui-quadrado com correção de continuidade

#### Scenario: Saída interpretável
- **WHEN** o teste é executado
- **THEN** a saída reporta a tabela 2x2 de discordâncias, a estatística, o p-valor e o número de amostras pareadas

#### Scenario: Poder limitado é sinalizado
- **WHEN** o número de amostras vulneráveis efetivamente avaliadas é pequeno
- **THEN** a saída sinaliza a limitação de poder estatístico em vez de reportar apenas o p-valor

### Requirement: Export de tabelas em LaTeX
O sistema SHALL exportar as tabelas comparativa e de McNemar em arquivos LaTeX prontos para inclusão no capítulo de resultados da monografia.

#### Scenario: Arquivos gerados
- **WHEN** o export é executado para uma rodada
- **THEN** arquivos `.tex` com ambientes `tabular` completos são gravados no diretório da rodada

#### Scenario: Inclusão direta
- **WHEN** um arquivo exportado é incluído via `\input{}` num documento LaTeX
- **THEN** ele compila sem edição manual

### Requirement: Leitura de múltiplas rodadas e compatibilidade
O sistema SHALL ler os resultados de uma rodada a partir de `results/<run_id>/` e SHALL continuar processando os CSVs da Parte 1 sem as colunas novas.

#### Scenario: Rodada indicada por run_id
- **WHEN** o cálculo de métricas é invocado para um `run_id`
- **THEN** ele consolida todos os CSVs daquela rodada, sem misturar rodadas diferentes

#### Scenario: CSV antigo ainda é legível
- **WHEN** um CSV da Parte 1 é analisado
- **THEN** as métricas de acerto e cobertura são calculadas normalmente e as colunas ausentes são reportadas como indisponíveis, não como erro

#### Scenario: Catálogos divergentes não são agregados em silêncio
- **WHEN** os resultados analisados contêm hashes de catálogo distintos
- **THEN** a saída sinaliza a divergência
