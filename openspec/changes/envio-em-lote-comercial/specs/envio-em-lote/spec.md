## ADDED Requirements

### Requirement: Correlação por chave de checkpoint
O modo de envio em lote SHALL identificar cada requisição do lote pela tripla
`(ID_Caso, Modelo_LLM, Tipo_Prompt)` — a mesma chave composta que o checkpoint
já usa — e SHALL gravar cada resposta apenas na linha cuja chave for idêntica à
recebida.

Uma resposta cuja chave não corresponda a nenhuma requisição submetida NÃO SHALL
ser gravada, e SHALL ser registrada como anomalia.

Os fornecedores não garantem que a ordem das respostas seja a das requisições —
a OpenAI declara isso explicitamente. Correlacionar por posição seria gravar
veredito no caso errado, em silêncio, e é exatamente o tipo de falha que
`matriz-experimental` chama de "a pior forma de falha possível aqui". Usar a
chave de checkpoint como identificador torna esse erro **impossível de
representar**, em vez de apenas improvável: uma resposta sem chave válida não
tem onde ser escrita.

#### Scenario: Respostas fora de ordem são gravadas no caso certo
- **WHEN** o fornecedor devolve as respostas de um lote em ordem diferente da submissão
- **THEN** cada veredito é gravado na linha da sua própria tripla, e nenhum caso recebe o veredito de outro

#### Scenario: Resposta órfã não é gravada
- **WHEN** o lote devolve uma resposta cuja chave não consta das requisições submetidas
- **THEN** nada é gravado para ela, e a ocorrência é registrada como anomalia

### Requirement: Retomada sem novo gasto
O sistema SHALL persistir o identificador do lote **antes** de submetê-lo, e
SHALL ser capaz de recuperar os resultados de um lote já submetido sem
reenviá-lo.

Um lote submetido já foi pago. Se a queda de um processo local obrigasse a
reenviar, o custo dobraria por um motivo que não tem nada a ver com o
experimento. Os fornecedores retêm os resultados por 29 a 42 dias, então a
janela de recuperação é ampla — o que falta é o identificador estar em disco
antes de a submissão acontecer, e não depois.

#### Scenario: Queda após submissão não perde o lote
- **WHEN** o processo termina anormalmente depois de submeter um lote e antes de recuperá-lo
- **THEN** uma execução seguinte encontra o identificador persistido e recupera os resultados sem submeter de novo

#### Scenario: Identificador é gravado antes da submissão
- **WHEN** um lote é submetido
- **THEN** seu identificador já está em disco no momento em que a requisição de submissão parte

### Requirement: Desfecho de expiração é distinto de erro
O sistema SHALL registrar como **`EXPIRADO`** a requisição que não foi
processada dentro da janela do lote, e NÃO SHALL confundi-la com `ERROR`.

São coisas diferentes e o texto da monografia depende da distinção: `ERROR` é
resposta do modelo que não passou na validação; `EXPIRADO` é requisição que o
modelo nunca viu. Tratar as duas como uma só inflaria a taxa de erro do modelo
com uma falha de esteira. Além disso, ao menos um fornecedor não cobra a
requisição expirada, e a contabilidade de custo precisa refletir isso.

#### Scenario: Requisição expirada é distinguível no CSV
- **WHEN** uma requisição do lote expira sem ser processada
- **THEN** o registro a marca como `EXPIRADO`, distinta de `ERROR`, e o custo dela não é somado quando o fornecedor não a cobra

### Requirement: Paridade de validação entre os modos de envio
O veredito obtido em lote SHALL passar pelas **mesmas regras de validação de
schema** do veredito obtido de forma síncrona, e a contabilidade de tokens e
custo SHALL ser derivada pelas mesmas funções.

Se as duas formas de entrega validassem diferente, a diferença entre uma rodada
em lote e uma rodada síncrona incluiria a severidade do validador, e não apenas
o modo de envio. A regra de que veredito fora de `{VP, FP}` é `ERROR` e nunca
`FP` vale igual nos dois caminhos.

#### Scenario: Mesma resposta, mesmo veredito nos dois modos
- **WHEN** a mesma resposta bruta do modelo chega pelo caminho síncrono e pelo caminho de lote
- **THEN** os dois produzem `RespostaLLM` idêntica em veredito, tokens e custo

### Requirement: Particionamento respeita o limite do fornecedor
O sistema SHALL particionar as requisições em lotes que caibam nos limites
declarados do fornecedor — de tokens enfileirados, de número de requisições e
de tamanho — e SHALL tratar o conjunto das partições como uma única rodada.

Não é hipótese: o Tier 1 do Gemini enfileira 3.000.000 de tokens e uma rodada de
dois braços tem 3.199.085 de entrada. Não cabe, por 6,6 %. Descobrir isso na
submissão seria perder a rodada; o limite precisa ser respeitado por
construção.

#### Scenario: Rodada maior que o limite é partida
- **WHEN** o total de tokens de uma rodada excede o limite de enfileiramento do fornecedor
- **THEN** o sistema submete mais de um lote, e o resultado final cobre exatamente o mesmo conjunto de casos que um lote único cobriria

#### Scenario: Partição não altera a população
- **WHEN** uma rodada é submetida em várias partições
- **THEN** a união das partições é igual ao conjunto de requisições que o modo síncrono faria, sem repetição nem omissão
