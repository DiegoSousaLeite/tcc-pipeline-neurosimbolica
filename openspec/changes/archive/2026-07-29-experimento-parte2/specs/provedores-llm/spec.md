## ADDED Requirements

### Requirement: Abstração de provedor de LLM
O sistema SHALL expor uma interface única de provedor que recebe um prompt e devolve veredito, justificativa, contagem de tokens, custo estimado e identificação do modelo, com implementações para Gemini e OpenAI.

#### Scenario: Troca de provedor sem mudar o chamador
- **WHEN** o runner é configurado para usar OpenAI em vez de Gemini
- **THEN** o código das fases 3/4 e da auditoria permanece inalterado e apenas a implementação de provedor muda

#### Scenario: Resposta normalizada
- **WHEN** qualquer provedor responde com sucesso
- **THEN** o objeto devolvido tem `veredito` em `{VP, FP}`, `justificativa` não vazia, tokens de entrada e saída, custo em USD e nome do modelo

### Requirement: Autenticação por cabeçalho HTTP
O sistema SHALL enviar a chave de API em cabeçalho HTTP (`x-goog-api-key` para Gemini, `Authorization: Bearer` para OpenAI) e SHALL NOT incluí-la na URL da requisição.

#### Scenario: Chave ausente da URL
- **WHEN** uma requisição é montada para qualquer provedor
- **THEN** a URL não contém a chave de API em nenhum parâmetro de query

#### Scenario: Chave ausente dos logs
- **WHEN** uma falha de rede produz log ou traceback contendo a URL
- **THEN** a chave de API não aparece na saída

### Requirement: Repetição com backoff exponencial e jitter
O sistema SHALL repetir requisições que falham com códigos transitórios usando backoff exponencial com jitter e teto de espera, e SHALL respeitar o cabeçalho `Retry-After` quando presente.

#### Scenario: Retry-After é respeitado
- **WHEN** a API responde 429 com `Retry-After: 30`
- **THEN** a próxima tentativa ocorre após pelo menos 30 segundos

#### Scenario: Backoff cresce com jitter
- **WHEN** três falhas transitórias consecutivas ocorrem sem `Retry-After`
- **THEN** as esperas crescem exponencialmente, variam por jitter e não excedem o teto configurado

#### Scenario: Esgotamento vira erro registrado
- **WHEN** todas as tentativas se esgotam
- **THEN** o resultado é `ERROR`, o caso é registrado em categoria de erro e não é checkpointado

#### Scenario: Intervalo mínimo entre chamadas
- **WHEN** o intervalo mínimo por provedor está configurado
- **THEN** chamadas consecutivas ao mesmo provedor respeitam esse intervalo

### Requirement: Validação de schema da resposta
O sistema SHALL validar a estrutura da resposta do modelo antes de aceitá-la, exigindo veredito no conjunto `{VP, FP}` e justificativa presente, e SHALL NOT interpretar resposta malformada como veredito válido.

#### Scenario: Veredito fora do domínio
- **WHEN** o modelo responde com veredito `"TALVEZ"` ou texto livre
- **THEN** o resultado é `ERROR` com a resposta bruta truncada na justificativa, e nunca é contado como `FP`

#### Scenario: JSON inválido
- **WHEN** a resposta não é JSON parseável
- **THEN** o resultado é `ERROR` e o caso entra em categoria de erro de esteira, fora das duas matrizes

### Requirement: Contabilidade de tokens e custo
O sistema SHALL registrar, por chamada, os tokens de entrada e saída e o custo estimado em USD, gravando-os no CSV de resultados, com a tabela de preços versionada e datada.

#### Scenario: Colunas de custo no CSV
- **WHEN** um caso `DETECTADO` é registrado
- **THEN** a linha contém tokens de entrada, tokens de saída e custo estimado em USD

#### Scenario: Preços versionados
- **WHEN** o custo é calculado
- **THEN** ele deriva de uma tabela de preços versionada no repositório com a data de consulta registrada, e essa tabela consta do manifesto da rodada
