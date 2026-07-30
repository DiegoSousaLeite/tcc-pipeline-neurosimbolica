# matriz-experimental

## Purpose

Executar a mesma população de casos sob a combinação de modelos e tipos de prompt, produzindo braços comparáveis, com identidade de execução e manifesto por rodada.

A comparação pareada entre braços só é válida se todos virem exatamente a mesma população, então o checkpoint precisa distinguir "este caso já foi triado" de "este caso já foi triado **neste braço**" — indexar apenas pelo `ID_Caso` faria o segundo braço achar tudo pronto e sair vazio, que é a pior forma de falha possível aqui, porque é silenciosa.

A identidade de execução existe para o mesmo fim que o hash do catálogo: meses depois, permitir dizer de qual código, ruleset, catálogo e tabela de preços saiu cada número do capítulo de resultados.

## Requirements

### Requirement: Execução da matriz 2x2 de braços
O sistema SHALL executar a mesma população de casos sob a combinação de modelos (Gemini e GPT) e tipos de prompt (baseline e especialista), produzindo quatro braços comparáveis, e SHALL permitir selecionar um subconjunto de braços por linha de comando.

#### Scenario: Quatro braços sobre a mesma população
- **WHEN** o runner é executado com a matriz completa
- **THEN** cada caso `DETECTADO` recebe um veredito por braço, e as quatro execuções cobrem exatamente o mesmo conjunto de `ID_Caso`

#### Scenario: Seleção de braço único
- **WHEN** o runner é invocado restringindo modelo e tipo de prompt
- **THEN** apenas o braço selecionado é executado, sem afetar os resultados já gravados dos demais

#### Scenario: LLM permanece filtro puro do Semgrep
- **WHEN** um caso termina em `NAO_DETECTADO` na Fase 1
- **THEN** nenhum braço faz chamada de LLM para esse caso, em qualquer combinação de modelo e prompt

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
O sistema SHALL gravar os resultados em `results/<run_id>/` e SHALL produzir um `manifesto.json` que registre a configuração completa da rodada.

#### Scenario: Manifesto completo
- **WHEN** uma rodada termina
- **THEN** `results/<run_id>/manifesto.json` contém `run_id`, commit do repositório, versão do Semgrep e do ruleset, hash do catálogo de CWE, hashes dos prompts, modelos e tabela de preços usados, contagem de casos por trilha e horários de início e fim

#### Scenario: Manifesto de rodada interrompida
- **WHEN** uma rodada é interrompida antes de terminar
- **THEN** o manifesto é gravado de todo modo, para que os CSVs parciais não fiquem sem procedência

#### Scenario: Rodadas não se sobrescrevem
- **WHEN** duas rodadas são executadas
- **THEN** cada uma grava sob seu próprio `run_id` e nenhuma sobrescreve resultados da outra

#### Scenario: Saída sai da raiz do repositório
- **WHEN** uma rodada nova é executada
- **THEN** nenhum arquivo `resultados_tcc_N.csv` novo é criado na raiz do repositório
