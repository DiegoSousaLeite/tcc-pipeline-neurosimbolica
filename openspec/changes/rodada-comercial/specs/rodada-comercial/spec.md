## ADDED Requirements

### Requirement: Gasto comercial só com orçamento autorizado
O sistema SHALL executar chamadas pagas a modelo comercial apenas depois que os
autores autorizarem explicitamente o orçamento da rodada, e o custo observado
SHALL ser registrado ao fim, ao lado do estimado.

Rodada comercial gasta dinheiro que não volta. A decisão de gastar é dos autores,
não da esteira, e o registro do observado contra o estimado é o que torna o
número de custo citável.

#### Scenario: Rodada sem autorização não parte
- **WHEN** não há autorização registrada de orçamento para a rodada
- **THEN** nenhuma requisição paga é submetida

#### Scenario: Custo observado é registrado
- **WHEN** a rodada termina
- **THEN** o custo observado consta do registro da change ao lado da estimativa de `docs/ESCOLHA-MODELO-COMERCIAL.md`

### Requirement: Braço de filtro tem prioridade sobre o de triagem
Quando o orçamento não cobrir os dois modos de montagem, a rodada comercial SHALL
executar o braço de **filtro** e SHALL tratar o braço de triagem como extensão
opcional.

É no braço de filtro que Q1, Q2 e Q3 são respondidas, e ele custa cerca de
metade do de triagem.

#### Scenario: Orçamento parcial
- **WHEN** o orçamento autorizado cobre só um dos modos de montagem
- **THEN** a rodada executada é a de modo `filtro`

### Requirement: Escopo da conclusão declarado pelo que foi medido
A monografia SHALL delimitar a conclusão comercial aos modelos efetivamente
executados, e NÃO SHALL descrevê-la pela matriz planejada.

A matriz comercial tem um único modelo, da OpenAI (o Gemini foi descartado); a
conclusão é "três modelos, um comercial", e dizer "dois comerciais" seria
afirmar o que não se mediu.

#### Scenario: Rodada com um único modelo comercial
- **WHEN** a rodada comercial executa apenas um modelo comercial
- **THEN** o texto da limitação de escopo o declara como um único modelo comercial

### Requirement: Piloto e rodada no mesmo modo de envio
Um piloto de decisão de modelo, quando houver, SHALL usar o mesmo modo de envio
da rodada que ele antecede.

#### Scenario: Piloto em lote antes de rodada em lote
- **WHEN** a rodada comercial for em modo `lote`
- **THEN** o piloto que a antecede também é executado em modo `lote`
