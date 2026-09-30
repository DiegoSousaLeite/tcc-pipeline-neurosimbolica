## ADDED Requirements

### Requirement: Modo de envio como eixo de execução
A matriz SHALL ganhar um eixo de execução independente dos de modelo, de prompt
e de modo de montagem: o **modo de envio**, com dois valores — `sincrono` e
`lote`. O valor `sincrono` SHALL ser o padrão e SHALL preservar exatamente o
comportamento anterior a esta mudança.

O eixo é independente porque uma rodada em lote continua cruzando os mesmos
modelos com os mesmos tipos de prompt sobre a mesma população; muda apenas como
as requisições trafegam.

#### Scenario: Modo de envio é padrão síncrono
- **WHEN** o runner é invocado sem nomear o modo de envio
- **THEN** o modo `sincrono` é usado, e a rodada é indistinguível de uma rodada anterior a esta mudança

#### Scenario: Modo de envio não altera a população
- **WHEN** a mesma rodada é executada em `sincrono` e em `lote`
- **THEN** as duas cobrem exatamente o mesmo conjunto de `ID_Caso`, com as mesmas combinações de modelo e prompt

### Requirement: Modo de envio é uniforme na rodada
O modo de envio NÃO SHALL variar entre os braços de uma mesma rodada.

É o mesmo argumento que já vale para o modo de montagem, por um motivo mais
forte ainda: a comparação pareada entre braços é o que sustenta o McNemar, e um
braço síncrono contra um braço em lote introduziria o modo de envio como
variável do experimento. A diferença medida entre os prompts passaria a incluir
qualquer diferença de tratamento entre as duas formas de entrega — e como o
lote tem desfechos que o síncrono não tem (expiração), a assimetria não seria
nem sequer simétrica.

#### Scenario: Braços de uma rodada compartilham o modo de envio
- **WHEN** uma rodada é executada
- **THEN** todos os seus braços usam o mesmo modo de envio

#### Scenario: Rodada com modos mistos é recusada
- **WHEN** uma execução pediria braços em modos de envio diferentes
- **THEN** a execução é recusada antes de qualquer chamada

### Requirement: Modo de envio e identificador do lote constam do manifesto
O manifesto de cada rodada SHALL registrar o modo de envio usado e, quando for
`lote`, o identificador de cada lote submetido e o fornecedor.

Pelo mesmo motivo que o manifesto já registra o modo de montagem, o hash do
catálogo e a versão da tabela de preços: meses depois, permitir dizer de qual
execução saiu cada número. Um lote é rastreável no painel do fornecedor pelo
identificador, e sem ele no manifesto essa rastreabilidade se perde.

#### Scenario: Manifesto de rodada em lote registra a procedência
- **WHEN** uma rodada é executada no modo de envio `lote`
- **THEN** o manifesto registra `lote` como modo de envio, o fornecedor e o identificador de cada lote submetido
