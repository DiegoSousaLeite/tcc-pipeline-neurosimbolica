# metricas-comparativas

## Purpose

Consolidar uma rodada inteira em métricas por braço, aplicar o teste de McNemar pareado entre braços e exportar as tabelas em LaTeX para o capítulo de resultados.

As duas matrizes permanecem separadas: a de cobertura mede o motor simbólico contra o gabarito, a de acerto mede o LLM. Misturá-las responderia a pergunta errada, porque um ponto cego do Semgrep não é erro do LLM, que sequer foi consultado.

Os avisos são parte do requisito, não enfeite. Com o eixo de verdadeiros positivos pequeno, qualquer p-valor é frágil, e reportá-lo sem essa qualificação seria enganoso; e resultados produzidos por versões diferentes do catálogo de CWE não podem ser agregados na mesma tabela.

## Requirements

### Requirement: Comparação lado a lado dos braços
O sistema SHALL calcular as métricas de acerto do LLM (Precisão, Recall, F1, MCC, TRA, TFN) para cada braço da matriz e apresentá-las em tabela única lado a lado, a partir dos resultados de uma rodada.

#### Scenario: Tabela com os quatro braços
- **WHEN** as métricas são geradas para uma rodada completa
- **THEN** a saída contém uma linha por braço `(modelo, tipo de prompt)` com todas as métricas

#### Scenario: Duas matrizes permanecem separadas
- **WHEN** as métricas são geradas
- **THEN** a matriz de cobertura simbólica do Semgrep continua reportada separadamente da matriz de acerto neural do LLM

#### Scenario: Cobertura simbólica não é contada por braço
- **WHEN** a matriz de cobertura é calculada para uma rodada com vários braços
- **THEN** cada caso entra uma vez só, porque o Semgrep roda uma vez por caso e seu resultado não depende do braço

#### Scenario: Custo por braço reportado
- **WHEN** a tabela comparativa é gerada
- **THEN** cada linha inclui o custo acumulado em USD daquele braço

#### Scenario: Estratificação disponível
- **WHEN** as métricas são geradas
- **THEN** é possível estratificar por trilha de origem, por `Num_Locations` e por origem da ficha de CWE, sem reexecutar a pipeline

### Requirement: Não-detecção discriminada por motivo
O sistema SHALL reportar, no bloco de cobertura simbólica, a não-detecção discriminada pelos seus dois motivos — `SEM_ALERTA` e `ALERTA_OUTRA_CWE` — em vez de apenas o total de `NAO_DETECTADO`.

A distinção é o que separa duas afirmações diferentes sobre o motor simbólico: "não existe regra que alcance esta fraqueza neste arquivo" e "existem regras que dispararam, mas sobre outra fraqueza". Colapsá-las num número só descreveria como ponto cego uniforme aquilo que na verdade tem duas causas distintas, e a segunda é a que sustenta a leitura de que o alerta e o gabarito falam de coisas diferentes.

#### Scenario: Contagem por motivo na cobertura
- **WHEN** as métricas de uma rodada são geradas
- **THEN** o bloco de cobertura simbólica traz a contagem de casos em `SEM_ALERTA` e em `ALERTA_OUTRA_CWE` separadamente

#### Scenario: Motivo não é contado por braço
- **WHEN** a contagem por motivo é calculada numa rodada com vários braços
- **THEN** cada caso entra uma vez só, pela mesma razão que a matriz de cobertura não é contada por braço: o Semgrep roda uma vez por caso

#### Scenario: Total preservado
- **WHEN** a contagem por motivo é apresentada
- **THEN** a soma dos dois motivos é igual ao total de casos em `NAO_DETECTADO`, de modo que a discriminação não altere a matriz de cobertura

#### Scenario: CSV sem a coluna de motivo
- **WHEN** um CSV anterior a esta mudança, sem a coluna de motivo, é analisado
- **THEN** os casos são reportados como motivo indisponível e as demais métricas são calculadas normalmente, sem erro

### Requirement: Teste de McNemar entre braços
O sistema SHALL aplicar o teste de McNemar sobre pares de braços, restrito às amostras que ambos classificaram com veredito válido, reportando a tabela de discordâncias e o p-valor.

#### Scenario: Amostras pareadas
- **WHEN** dois braços são comparados
- **THEN** apenas os `ID_Caso` com veredito válido nos dois braços entram no teste, e a contagem usada é reportada

#### Scenario: Caso com erro em um dos braços é excluído
- **WHEN** um caso tem veredito válido num braço e erro de esteira no outro
- **THEN** ele fica fora do teste, porque não é evidência sobre nenhum dos dois

#### Scenario: Escolha do teste por volume de discordâncias
- **WHEN** o total de discordâncias é menor que 25
- **THEN** o p-valor vem do teste binomial exato; caso contrário vem do qui-quadrado com correção de continuidade

#### Scenario: Saída interpretável
- **WHEN** o teste é executado
- **THEN** a saída reporta a tabela 2x2 de discordâncias, a estatística, o p-valor e o número de amostras pareadas

#### Scenario: Ausência de base é sinalizada
- **WHEN** não há amostra pareada, ou há zero discordâncias entre os braços
- **THEN** a saída diz isso explicitamente, em vez de apresentar um p-valor sem conteúdo

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

#### Scenario: Caracteres especiais escapados
- **WHEN** nomes de modelo ou de braço contêm caracteres com significado em LaTeX, como sublinhado
- **THEN** eles saem escapados no arquivo exportado

#### Scenario: Métrica indefinida sai legível
- **WHEN** uma métrica é indefinida por divisão por zero
- **THEN** a célula traz marcação explícita de indisponibilidade, não `nan`

### Requirement: Leitura de múltiplas rodadas e compatibilidade
O sistema SHALL ler os resultados de uma rodada a partir de `results/<run_id>/` e SHALL continuar processando os CSVs da Parte 1 sem as colunas novas.

#### Scenario: Rodada indicada por run_id
- **WHEN** o cálculo de métricas é invocado para um `run_id`
- **THEN** ele consolida todos os CSVs daquela rodada, sem misturar rodadas diferentes

#### Scenario: CSV antigo ainda é legível
- **WHEN** um CSV da Parte 1 é analisado
- **THEN** as métricas de acerto e cobertura são calculadas normalmente e as colunas ausentes são reportadas como indisponíveis, não como erro

#### Scenario: Rótulos de classificação legados são reconhecidos
- **WHEN** um CSV traz os rótulos de classificação em inglês, de versões anteriores da auditoria
- **THEN** eles são mapeados para as mesmas células da matriz que os rótulos em português

#### Scenario: Catálogos divergentes não são agregados em silêncio
- **WHEN** os resultados analisados contêm hashes de catálogo distintos
- **THEN** a saída sinaliza a divergência
