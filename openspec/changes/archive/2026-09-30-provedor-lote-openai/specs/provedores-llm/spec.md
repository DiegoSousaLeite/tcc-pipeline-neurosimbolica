## ADDED Requirements

### Requirement: Entrega em lote pela OpenAI
O provedor OpenAI SHALL implementar a entrega em lote pelo mesmo protocolo do
Gemini, correlacionando cada resultado pelo `custom_id` e nunca pela posição, e
SHALL registrar como `EXPIRADO`, sem custo, a requisição que o fornecedor
devolver com `batch_expired`.

A OpenAI declara que a ordem das linhas de saída pode não ser a da entrada; a
correlação pela chave de checkpoint é o que impede um veredito na linha errada.

#### Scenario: Resultado fora de ordem
- **WHEN** o arquivo de saída traz as respostas em ordem diferente da submissão
- **THEN** cada veredito é associado à chave com que foi submetido

#### Scenario: Requisição expirada
- **WHEN** o arquivo de erros traz uma requisição com código `batch_expired`
- **THEN** ela é registrada como `EXPIRADO`, com custo zero, e não como `ERROR`

#### Scenario: Mesma resposta nos dois modos
- **WHEN** a mesma resposta bruta chega pelo síncrono e pelo lote da OpenAI
- **THEN** as duas `RespostaLLM` são idênticas em veredito, tokens e custo

### Requirement: Modelo de raciocínio roda sem raciocínio e com temperatura zero
O provedor OpenAI SHALL enviar `reasoning_effort: "none"` aos modelos de
raciocínio que aceitam esse valor, mantendo `temperature: 0`, e NÃO SHALL enviar
o parâmetro a modelos que não o conhecem.

Temperatura 0 e resposta direta são a condição de todos os braços da matriz; um
raciocínio escondido entraria como variável do experimento sem ser a estudada.

#### Scenario: Luna
- **WHEN** o modelo é `gpt-6-luna`
- **THEN** a requisição leva `reasoning_effort: "none"` e `temperature: 0`

#### Scenario: Modelo sem raciocínio
- **WHEN** o modelo é `gpt-4o-mini`
- **THEN** a requisição não leva `reasoning_effort`
