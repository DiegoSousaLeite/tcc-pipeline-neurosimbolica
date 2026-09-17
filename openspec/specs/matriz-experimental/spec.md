# matriz-experimental

## Purpose

Executar a mesma população de casos sob a combinação de modelos e tipos de prompt, produzindo braços comparáveis, com identidade de execução e manifesto por rodada.

A comparação pareada entre braços só é válida se todos virem exatamente a mesma população, então o checkpoint precisa distinguir "este caso já foi triado" de "este caso já foi triado **neste braço**" — indexar apenas pelo `ID_Caso` faria o segundo braço achar tudo pronto e sair vazio, que é a pior forma de falha possível aqui, porque é silenciosa.

A identidade de execução existe para o mesmo fim que o hash do catálogo: meses depois, permitir dizer de qual código, ruleset, catálogo e tabela de preços saiu cada número do capítulo de resultados.

## Requirements

### Requirement: Execução da matriz 2x2 de braços
O sistema SHALL executar a mesma população de casos sob o produto dos modelos selecionados pelos tipos de prompt (baseline e especialista), produzindo braços comparáveis, e SHALL permitir selecionar um subconjunto de braços por linha de comando. O conjunto padrão de modelos SHALL permanecer o par comercial (Gemini e GPT), formando a matriz 2x2 de referência do experimento; modelos adicionais, como os executados localmente, SHALL entrar apenas quando nomeados explicitamente.

A matriz SHALL ganhar um eixo adicional, independente dos de modelo e prompt: o **modo de montagem do candidato**, com dois valores — `filtro` e `triagem`. O modo `filtro` é o padrão e preserva o desenho anterior a esta mudança. O eixo é independente porque uma rodada de triagem continua cruzando os mesmos modelos com os mesmos tipos de prompt; muda apenas quais casos têm candidato a submeter.

O modo de montagem NÃO SHALL variar dentro de uma mesma rodada. Braços de modos diferentes cobrem conjuntos de `ID_Caso` diferentes, e a comparação pareada entre braços — que é o que sustenta o McNemar — exige que todos vejam exatamente o mesmo conjunto.

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

#### Scenario: LLM permanece filtro puro do Semgrep no modo filtro
- **WHEN** o runner executa no modo de montagem `filtro` e um caso termina em `NAO_DETECTADO` na Fase 1
- **THEN** nenhum braço faz chamada de LLM para esse caso, em qualquer combinação de modelo e prompt

#### Scenario: Modo de montagem é padrão filtro
- **WHEN** o runner é invocado sem nomear o modo de montagem
- **THEN** o modo `filtro` é usado, e a rodada é indistinguível de uma rodada anterior a esta mudança

#### Scenario: Modo de triagem submete positivo não detectado
- **WHEN** o runner executa no modo de montagem `triagem` e um caso de gabarito vulnerável termina em `NAO_DETECTADO`
- **THEN** todos os braços da matriz fazem chamada de LLM para esse caso, sobre o candidato montado a partir do gabarito

#### Scenario: Modo de montagem é uniforme na rodada
- **WHEN** uma rodada é executada
- **THEN** todos os seus braços usam o mesmo modo de montagem, e o modo consta do manifesto

#### Scenario: Um provedor por modelo
- **WHEN** dois braços compartilham o mesmo modelo com tipos de prompt diferentes
- **THEN** ambos usam a mesma instância de provedor, para que o intervalo mínimo entre chamadas seja respeitado entre eles

### Requirement: Checkpoint por chave composta
O sistema SHALL considerar um caso já processado apenas quando existe resultado válido para a tripla `(ID_Caso, Modelo_LLM, Tipo_Prompt)`, e não apenas para o `ID_Caso`.

#### Scenario: Braço novo não é pulado
- **WHEN** o braço `(gemini, especialista)` já está completo e o braço `(gpt, baseline)` é iniciado
- **THEN** todos os casos são executados no braço novo, nenhum é marcado como já processado

#### Scenario: Retomada dentro do mesmo braço
- **WHEN** um braço é interrompido e reiniciado
- **THEN** apenas os casos sem resultado válido daquele braço são reexecutados

#### Scenario: Erros não são checkpointados
- **WHEN** uma linha existente tem `Status_Semgrep` em uma categoria de erro
- **THEN** o caso correspondente é reexecutado em vez de pulado

#### Scenario: Caso detectado sem veredito continua pendente
- **WHEN** uma linha tem `Status_Semgrep == DETECTADO` e `Veredito_LLM` fora de `{VP, FP}` — o que a medição de cobertura simbólica produz, por não consultar o LLM
- **THEN** o caso não é considerado processado naquele braço, de modo que medir a cobertura de um conjunto não impede de triá-lo depois

#### Scenario: CSVs antigos são reconhecidos
- **WHEN** um CSV da Parte 1, sem as colunas novas, é lido pelo checkpoint
- **THEN** suas linhas são atribuídas ao braço `(gemini-2.5-flash-lite, especialista)` e nenhum arquivo antigo é modificado ou removido

### Requirement: Escopo do checkpoint entre rodadas
O sistema SHALL restringir o checkpoint, por padrão, aos resultados da própria rodada corrente, e SHALL exigir opção explícita para considerar rodadas anteriores e os CSVs da Parte 1.

O motivo é a comparabilidade dos braços: as linhas da Parte 1 pertencem ao braço `(gemini-2.5-flash-lite, especialista)`, e deixá-las satisfazer o checkpoint faria esse braço vir com menos casos que os outros três, quebrando a premissa de população idêntica em que o teste de McNemar pareado se apoia.

#### Scenario: Rodada nova começa do zero
- **WHEN** uma rodada é iniciada com um `run_id` novo e existem resultados de rodadas anteriores para os mesmos casos e braços
- **THEN** todos os casos são executados, e nenhum braço herda cobertura de outra rodada

#### Scenario: Rodada interrompida retoma
- **WHEN** uma rodada é reiniciada com o `run_id` que já possui resultados parciais
- **THEN** apenas os casos sem resultado válido daquele braço são reexecutados, e os resultados já gravados são preservados, não truncados

#### Scenario: Reaproveitamento é opt-in
- **WHEN** o runner é invocado com a opção que estende o checkpoint às rodadas anteriores e aos CSVs da Parte 1
- **THEN** os resultados daquelas fontes passam a ser considerados, sem que nenhum arquivo antigo seja modificado ou removido

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
