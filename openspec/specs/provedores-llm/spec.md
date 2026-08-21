# provedores-llm

## Purpose

Isolar a comunicação com os modelos de linguagem atrás de uma interface única, com implementações para Gemini, OpenAI e modelos locais servidos por Ollama.

Existe porque o eixo "modelo" da matriz experimental só é variável independente se trocar de provedor não mudar mais nada: o código das fases 3/4 e da auditoria tem que permanecer igual. A camada também concentra três correções que afetam a validade dos resultados — a chave de API sai da URL e vai para header, a repetição passa a usar backoff exponencial com jitter respeitando `Retry-After`, e a resposta do modelo passa por validação de schema antes de ser aceita, para que uma falha de esteira nunca seja contada como veredito.

## Requirements

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

### Requirement: Repetição com backoff exponencial e jitter
O sistema SHALL repetir requisições que falham com códigos transitórios usando backoff exponencial com jitter e teto de espera, e SHALL respeitar o cabeçalho `Retry-After` quando presente.

#### Scenario: Retry-After é respeitado
- **WHEN** a API responde 429 com `Retry-After: 30`
- **THEN** a próxima tentativa ocorre após pelo menos 30 segundos

#### Scenario: Backoff cresce com jitter
- **WHEN** três falhas transitórias consecutivas ocorrem sem `Retry-After`
- **THEN** as esperas crescem exponencialmente, variam por jitter e não excedem o teto configurado

#### Scenario: Erro permanente não é repetido
- **WHEN** a API responde com código de erro não transitório, como 401
- **THEN** o resultado é `ERROR` imediatamente, sem novas tentativas

#### Scenario: Esgotamento vira erro registrado
- **WHEN** todas as tentativas se esgotam
- **THEN** o resultado é `ERROR`, o caso é registrado em categoria de erro e não é checkpointado

#### Scenario: Intervalo mínimo entre chamadas
- **WHEN** o intervalo mínimo por provedor está configurado
- **THEN** chamadas consecutivas ao mesmo provedor respeitam esse intervalo, e a primeira chamada não espera

#### Scenario: Intervalo zero desativa o throttle
- **WHEN** o intervalo mínimo é configurado explicitamente como zero
- **THEN** nenhuma espera é imposta entre chamadas

### Requirement: Validação de schema da resposta
O sistema SHALL validar a estrutura da resposta do modelo antes de aceitá-la, exigindo veredito no conjunto `{VP, FP}` e justificativa presente, e SHALL NOT interpretar resposta malformada como veredito válido.

#### Scenario: Veredito fora do domínio
- **WHEN** o modelo responde com veredito `"TALVEZ"` ou texto livre
- **THEN** o resultado é `ERROR` com a resposta bruta truncada na justificativa, e nunca é contado como `FP`

#### Scenario: JSON inválido
- **WHEN** a resposta não é JSON parseável
- **THEN** o resultado é `ERROR` e o caso entra em categoria de erro de esteira, fora das duas matrizes

#### Scenario: Justificativa vazia
- **WHEN** o modelo responde com veredito válido e justificativa ausente ou em branco
- **THEN** o resultado é `ERROR`

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
