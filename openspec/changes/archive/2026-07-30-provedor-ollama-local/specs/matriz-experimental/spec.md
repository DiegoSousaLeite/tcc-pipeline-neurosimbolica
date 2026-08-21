# matriz-experimental

## MODIFIED Requirements

### Requirement: Execução da matriz 2x2 de braços
O sistema SHALL executar a mesma população de casos sob o produto dos modelos selecionados pelos tipos de prompt (baseline e especialista), produzindo braços comparáveis, e SHALL permitir selecionar um subconjunto de braços por linha de comando. O conjunto padrão de modelos SHALL permanecer o par comercial (Gemini e GPT), formando a matriz 2x2 de referência do experimento; modelos adicionais, como os executados localmente, SHALL entrar apenas quando nomeados explicitamente.

#### Scenario: Quatro braços sobre a mesma população
- **WHEN** o runner é executado com a matriz completa
- **THEN** cada caso `DETECTADO` recebe um veredito por braço, e as quatro execuções cobrem exatamente o mesmo conjunto de `ID_Caso`

#### Scenario: Matriz padrão não inclui modelo local
- **WHEN** o runner é executado com a matriz completa, sem nomear modelos
- **THEN** apenas os dois modelos comerciais são usados, e nenhum braço local é executado sem ter sido pedido

#### Scenario: Modelo adicional amplia a matriz
- **WHEN** o runner é invocado nomeando um terceiro modelo junto dos dois tipos de prompt
- **THEN** seis braços são executados sobre a mesma população, e os dois tipos de prompt continuam cruzando com todos os modelos

#### Scenario: Seleção de braço único
- **WHEN** o runner é invocado restringindo modelo e tipo de prompt
- **THEN** apenas o braço selecionado é executado, sem afetar os resultados já gravados dos demais

#### Scenario: LLM permanece filtro puro do Semgrep
- **WHEN** um caso termina em `NAO_DETECTADO` na Fase 1
- **THEN** nenhum braço faz chamada de LLM para esse caso, em qualquer combinação de modelo e prompt

#### Scenario: Um provedor por modelo
- **WHEN** dois braços compartilham o mesmo modelo com tipos de prompt diferentes
- **THEN** ambos usam a mesma instância de provedor, para que o intervalo mínimo entre chamadas seja respeitado entre eles

### Requirement: Identidade de execução e manifesto
O sistema SHALL gravar os resultados em `results/<run_id>/` e SHALL produzir um `manifesto.json` que registre a configuração completa da rodada. O nome de arquivo derivado de um braço SHALL ser válido no sistema de arquivos, incluindo Windows, sem que o nome original do modelo se perca dos dados.

#### Scenario: Manifesto completo
- **WHEN** uma rodada termina
- **THEN** `results/<run_id>/manifesto.json` contém `run_id`, commit do repositório, versão do Semgrep e do ruleset, hash do catálogo de CWE, hashes dos prompts, modelos e tabela de preços usados, contagem de casos por trilha e horários de início e fim

#### Scenario: Nome de modelo com caractere reservado não quebra a rodada
- **WHEN** um braço usa um modelo cujo nome contém caractere inválido em nome de arquivo, como o dois-pontos das tags do Ollama
- **THEN** o CSV do braço é criado com nome saneado, e o nome original do modelo continua gravado em cada linha do CSV e no manifesto

#### Scenario: Braços distintos não colidem em arquivo
- **WHEN** dois braços têm nomes de modelo que se tornariam iguais após o saneamento
- **THEN** seus CSVs recebem nomes distintos, e nenhum braço sobrescreve o resultado do outro

#### Scenario: Manifesto de rodada interrompida
- **WHEN** uma rodada é interrompida antes de terminar
- **THEN** o manifesto é gravado de todo modo, para que os CSVs parciais não fiquem sem procedência

#### Scenario: Rodadas não se sobrescrevem
- **WHEN** duas rodadas são executadas
- **THEN** cada uma grava sob seu próprio `run_id` e nenhuma sobrescreve resultados da outra

#### Scenario: Saída sai da raiz do repositório
- **WHEN** uma rodada nova é executada
- **THEN** nenhum arquivo `resultados_tcc_N.csv` novo é criado na raiz do repositório
