## MODIFIED Requirements

### Requirement: Modelo de raciocínio roda sem raciocínio e com temperatura zero
O provedor OpenAI SHALL enviar `reasoning_effort: "none"` aos modelos de
raciocínio que aceitam esse valor, mantendo `temperature: 0`, e NÃO SHALL enviar
o parâmetro a modelos que não o conhecem. Quando o modelo é pedido como variante
`<modelo>@<esforço>`, com esforço em `low`, `medium` ou `high`, o provedor SHALL
enviar à API o nome base com `reasoning_effort: "<esforço>"` e sem
`temperature`, e SHALL recusar a variante em modelo que não aceita esforço
configurável ou com esforço fora desse conjunto.

Temperatura 0 e resposta direta são a condição de todos os braços da matriz; um
raciocínio escondido entraria como variável do experimento sem ser a estudada.
A variante existe para estudá-la de propósito, com o nome completo identificando
o braço em todo registro.

#### Scenario: Luna
- **WHEN** o modelo é `gpt-6-luna`
- **THEN** a requisição leva `reasoning_effort: "none"` e `temperature: 0`

#### Scenario: Modelo sem raciocínio
- **WHEN** o modelo é `gpt-4o-mini`
- **THEN** a requisição não leva `reasoning_effort`

#### Scenario: Luna com raciocínio
- **WHEN** o modelo é `gpt-6-luna@low`
- **THEN** a requisição leva `model: "gpt-6-luna"`, `reasoning_effort: "low"` e nenhum `temperature`
- **AND** custo e teto de fila são os do `gpt-6-luna`

#### Scenario: Variante inválida
- **WHEN** o modelo é `gpt-4o-mini@low` ou `gpt-6-luna@turbo`
- **THEN** o provedor é recusado antes de qualquer chamada
