# provedores-llm

## MODIFIED Requirements

### Requirement: Abstração de provedor de LLM
O sistema SHALL expor uma interface única de provedor que recebe um prompt e devolve veredito, justificativa, contagem de tokens, custo estimado e identificação do modelo, com implementações para Gemini, OpenAI e modelos locais servidos por Ollama.

#### Scenario: Troca de provedor sem mudar o chamador
- **WHEN** o runner é configurado para usar OpenAI em vez de Gemini
- **THEN** o código das fases 3/4 e da auditoria permanece inalterado e apenas a implementação de provedor muda

#### Scenario: Troca para provedor local sem mudar o chamador
- **WHEN** o runner é configurado para usar um modelo local servido por Ollama
- **THEN** o código das fases 3/4 e da auditoria permanece inalterado e apenas a implementação de provedor muda

#### Scenario: Resposta normalizada
- **WHEN** qualquer provedor responde com sucesso
- **THEN** o objeto devolvido tem `veredito` em `{VP, FP}`, `justificativa` não vazia, tokens de entrada e saída, custo em USD e nome do modelo

#### Scenario: Provedor escolhido pelo nome do modelo
- **WHEN** um braço é definido por um nome de modelo
- **THEN** a implementação correspondente é instanciada sem que o chamador precise nomear o provedor

#### Scenario: Modelo local é resolvido sem ambiguidade
- **WHEN** um braço é definido por um nome de modelo local, que não segue a convenção de nomes dos provedores comerciais
- **THEN** o provedor local é instanciado, e a resolução não depende de adivinhar a família a partir de prefixos de nomes de modelos abertos

#### Scenario: Modelo desconhecido falha na configuração
- **WHEN** um braço é definido por um nome de modelo que não corresponde a nenhum provedor conhecido
- **THEN** a rodada falha ao definir os braços, com mensagem nomeando o modelo, em vez de tentar a chamada

### Requirement: Autenticação por cabeçalho HTTP
O sistema SHALL enviar a chave de API em cabeçalho HTTP (`x-goog-api-key` para Gemini, `Authorization: Bearer` para OpenAI) e SHALL NOT incluí-la na URL da requisição. A exigência de credencial SHALL valer por provedor: um provedor que não autentica, como o servidor local, SHALL executar sem chave.

#### Scenario: Chave ausente da URL
- **WHEN** uma requisição é montada para qualquer provedor
- **THEN** a URL não contém a chave de API em nenhum parâmetro de query

#### Scenario: Chave ausente dos logs
- **WHEN** uma falha de rede produz log ou traceback contendo a URL
- **THEN** a chave de API não aparece na saída

#### Scenario: Chave ausente vira erro sem tocar a rede
- **WHEN** um provedor que exige credencial é invocado sem chave configurada
- **THEN** o resultado é `ERROR` e nenhuma requisição HTTP é feita

#### Scenario: Provedor sem credencial não é bloqueado
- **WHEN** um provedor declarado como não autenticado é invocado sem chave
- **THEN** a requisição é feita normalmente e a ausência de chave não produz erro

### Requirement: Contabilidade de tokens e custo
O sistema SHALL registrar, por chamada, os tokens de entrada e saída e o custo estimado em USD, gravando-os no CSV de resultados, com a tabela de preços versionada e datada. O sistema SHALL distinguir custo zero por execução local de custo zero por ausência de preço tabelado.

#### Scenario: Colunas de custo no CSV
- **WHEN** um caso `DETECTADO` é registrado
- **THEN** a linha contém tokens de entrada, tokens de saída e custo estimado em USD

#### Scenario: Preços versionados
- **WHEN** o custo é calculado
- **THEN** ele deriva de uma tabela de preços versionada no repositório com a data de consulta registrada, e essa tabela consta do manifesto da rodada

#### Scenario: Modelo fora da tabela não tem preço chutado
- **WHEN** o custo é calculado para um modelo comercial ausente da tabela de preços
- **THEN** o custo é zero e o modelo é listado no manifesto como sem preço, em vez de receber o preço de um modelo de nome parecido

#### Scenario: Modelo local tem custo zero declarado
- **WHEN** o custo é calculado para um modelo executado localmente
- **THEN** o custo é zero e o modelo é listado no manifesto como execução local sem custo monetário, e não como modelo sem preço tabelado

#### Scenario: Tokens continuam sendo contados localmente
- **WHEN** um caso é triado por um provedor local
- **THEN** os tokens de entrada e saída informados pelo servidor são gravados no CSV, ainda que o custo seja zero
