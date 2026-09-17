## ADDED Requirements

### Requirement: Entrega em lote como forma alternativa
A camada de provedores SHALL admitir, além da entrega síncrona existente, uma
forma de **entrega em lote**, com duas operações: submeter um conjunto de
prompts identificados e recuperar os resultados de um conjunto já submetido.

A abstração síncrona (`avaliar(prompt) -> RespostaLLM`) NÃO SHALL mudar. Um
provedor que só fale a forma síncrona continua válido, e a pipeline SHALL
continuar funcionando sem nenhum provedor de lote implementado.

A separação existe porque as duas formas têm ciclos de vida incompatíveis: a
síncrona devolve resposta na mesma chamada, a em lote devolve um identificador e
exige consulta posterior. Forçar as duas na mesma assinatura obrigaria a
síncrona a carregar um estado que ela não tem, ou a em lote a bloquear
esperando — que é justamente o que ela existe para não fazer.

#### Scenario: Provedor só síncrono continua válido
- **WHEN** um provedor implementa apenas a forma síncrona
- **THEN** a pipeline o aceita e executa normalmente no modo de envio síncrono

#### Scenario: Submissão devolve identificador, não veredito
- **WHEN** um conjunto de prompts é submetido em lote
- **THEN** a operação devolve um identificador de lote, sem bloquear à espera dos vereditos

#### Scenario: Recuperação devolve vereditos mapeados por chave
- **WHEN** os resultados de um lote submetido são recuperados
- **THEN** cada veredito vem associado à chave com que foi submetido, e não à sua posição

### Requirement: Provedor sem suporte a lote é recusado cedo
O sistema SHALL recusar a execução quando o modo de envio em lote for pedido
para um provedor que não o implementa, e SHALL fazê-lo **antes** de montar
qualquer prompt ou consumir qualquer recurso.

O provedor local (`ollama`) é o caso concreto: não existe API de lote para
inferência local. Uma rodada que descobrisse isso no meio já teria gasto tempo
de Fase 1 à toa, e o erro precisa nomear o provedor em vez de falhar em algum
ponto interno.

#### Scenario: Lote pedido para provedor local falha antes de começar
- **WHEN** o modo de envio em lote é pedido para um provedor que não o implementa
- **THEN** a execução para imediatamente com erro que nomeia o provedor, sem montar prompt nem chamar a Fase 1
