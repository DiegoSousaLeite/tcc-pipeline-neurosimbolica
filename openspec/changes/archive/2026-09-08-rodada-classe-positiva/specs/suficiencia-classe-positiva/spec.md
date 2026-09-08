## ADDED Requirements

### Requirement: Suficiência medida na chegada ao LLM
O sistema SHALL considerar a classe positiva suficiente quando ao menos 30 casos de gabarito vulnerável produzirem veredito válido do LLM, e NÃO quando 30 casos vulneráveis forem colhidos ou carregados na população.

A distinção é o ponto da mudança. Entre colher e chegar ao LLM há três perdas independentes: a CWE ser alcançável não garante que a regra dispare naquele código; o alerta pode não ser emparelhado ao caso na Fase 1; e o caso pode terminar em falha de esteira. Contar na colheita superestimaria a amostra e reproduziria exatamente o problema que estas mudanças existem para resolver — a rodada `20260731T140000Z-af9bc32` tinha 107 casos vulneráveis na população e apenas 1 chegou ao LLM.

O limiar de 30 é o já adotado por `src/metricas.py` ao emitir o aviso de poder estatístico limitado.

#### Scenario: Ausência do aviso como critério de aceite
- **WHEN** as métricas da rodada são calculadas
- **THEN** a ausência do aviso de poder estatístico limitado indica que a classe positiva é suficiente, e a presença dele indica que não é

#### Scenario: Caso não emparelhado não conta
- **WHEN** um caso vulnerável termina em não-detecção na Fase 1
- **THEN** ele não conta para o limiar, porque nenhum veredito de LLM foi emitido sobre ele

#### Scenario: Falha de esteira não conta
- **WHEN** um caso vulnerável termina em categoria de erro
- **THEN** ele não conta para o limiar

#### Scenario: Colheita dimensionada com folga
- **WHEN** o alvo da colheita é definido
- **THEN** ele é maior que 30, para absorver as perdas entre colheita e chegada ao LLM

### Requirement: Rendimento isolado por procedência
O sistema SHALL permitir determinar, entre os casos vulneráveis que chegaram ao LLM, quantos vieram da colheita filtrada e quantos vieram das trilhas anteriores.

Sem essa separação não é possível avaliar se o filtro de alcançabilidade funcionou: um ganho de amostra poderia vir apenas do reaproveitamento de pares que já estavam na população, com a colheita nova tendo rendido nada.

#### Scenario: Contagem por trilha de origem
- **WHEN** os resultados da rodada são analisados
- **THEN** o número de casos vulneráveis com veredito válido é discriminado por trilha de origem

#### Scenario: Rendimento da colheita filtrada é isolável
- **WHEN** o critério de aceite é avaliado
- **THEN** é possível afirmar quantos dos casos vulneráveis que chegaram ao LLM vieram especificamente da colheita filtrada

### Requirement: Taxa de sobrevivência registrada
O sistema SHALL registrar a taxa de sobrevivência dos casos vulneráveis entre a colheita e a chegada ao LLM, para que uma eventual segunda colheita seja dimensionada com base em medição e não em estimativa.

Essa taxa é desconhecida antes da primeira rodada — é a incógnita central destas mudanças. Registrá-la é o que permite decidir o alvo de uma repetição sem repetir o erro de dimensionar no escuro.

#### Scenario: Taxa medida e registrada
- **WHEN** a rodada termina
- **THEN** a proporção entre casos vulneráveis colhidos e casos vulneráveis com veredito válido fica registrada

#### Scenario: Critério não atingido leva a nova colheita dimensionada
- **WHEN** o critério de aceite não é atingido
- **THEN** a taxa medida é usada para definir o alvo da colheita seguinte, sem refazer as etapas de código

### Requirement: Rodadas anteriores preservadas
O sistema SHALL preservar intactas em disco as rodadas anteriores, que permanecem válidas e comparáveis entre si.

A população da rodada nova é maior, o que a torna não comparável caso a caso com as anteriores — mas isso não invalida nada do que já foi medido. A comparação legítima dentro da rodada nova é entre braços.

#### Scenario: Rodadas anteriores intactas
- **WHEN** a rodada nova termina
- **THEN** os CSVs e manifestos das rodadas anteriores permanecem inalterados em disco

#### Scenario: Não comparabilidade declarada
- **WHEN** o resultado da rodada nova é registrado
- **THEN** o registro declara que a comparação caso a caso com as rodadas anteriores não é válida, e por quê
