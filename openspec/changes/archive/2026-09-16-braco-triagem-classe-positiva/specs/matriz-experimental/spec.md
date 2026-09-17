## MODIFIED Requirements

### Requirement: Execução da matriz 2x2 de braços
O sistema SHALL executar a mesma população de casos sob o produto dos modelos selecionados pelos tipos de prompt (baseline e especialista), produzindo braços comparáveis, e SHALL permitir selecionar um subconjunto de braços por linha de comando. O conjunto padrão de modelos SHALL permanecer o par comercial (Gemini e GPT), formando a matriz 2x2 de referência do experimento; modelos adicionais, como os executados localmente, SHALL entrar apenas quando nomeados explicitamente.

A matriz SHALL ganhar um eixo adicional, independente dos de modelo e prompt: o **modo de montagem do candidato**, com dois valores — `filtro` e `triagem`. O modo `filtro` é o padrão e preserva o desenho anterior a esta mudança. O eixo é independente porque uma rodada de triagem continua cruzando os mesmos modelos com os mesmos tipos de prompt; muda apenas quais casos têm candidato a submeter.

O modo de montagem NÃO SHALL variar dentro de uma mesma rodada. Braços de modos diferentes cobrem conjuntos de `ID_Caso` diferentes, e a comparação pareada entre braços — que é o que sustenta o McNemar — exige que todos vejam exatamente o mesmo conjunto.

#### Scenario: Quatro braços sobre a mesma população
- **WHEN** o runner é executado com a matriz completa
- **THEN** cada caso `DETECTADO` recebe um veredito por braço, e as quatro execuções cobrem exatamente o mesmo conjunto de `ID_Caso`

#### Scenario: Matriz padrão não inclui modelo local
- **WHEN** o runner é executado com a matriz completa, sem nomear modelos
- **THEN** apenas os dois modelos comerciais são usados, e nenhum braço local é executado sem ter sido pedido

#### Scenario: Modelo adicional amplia a matriz
- **WHEN** o runner é invocado nomeando um terceiro modelo junto dos dois tipos de prompt
- **THEN** seis braços são executados sobre a mesma população, e os dois tipos de prompt continuam cruzando com todos os modelos

#### Scenario: Seleção de braço único
- **WHEN** o runner é invocado restringindo modelo e tipo de prompt
- **THEN** apenas o braço selecionado é executado, sem afetar os resultados já gravados dos demais

#### Scenario: LLM permanece filtro puro do Semgrep no modo filtro
- **WHEN** o runner executa no modo de montagem `filtro` e um caso termina em `NAO_DETECTADO` na Fase 1
- **THEN** nenhum braço faz chamada de LLM para esse caso, em qualquer combinação de modelo e prompt

#### Scenario: Modo de montagem é padrão filtro
- **WHEN** o runner é invocado sem nomear o modo de montagem
- **THEN** o modo `filtro` é usado, e a rodada é indistinguível de uma rodada anterior a esta mudança

#### Scenario: Modo de triagem submete positivo não detectado
- **WHEN** o runner executa no modo de montagem `triagem` e um caso de gabarito vulnerável termina em `NAO_DETECTADO`
- **THEN** todos os braços da matriz fazem chamada de LLM para esse caso, sobre o candidato montado a partir do gabarito

#### Scenario: Modo de montagem é uniforme na rodada
- **WHEN** uma rodada é executada
- **THEN** todos os seus braços usam o mesmo modo de montagem, e o modo consta do manifesto

#### Scenario: Um provedor por modelo
- **WHEN** dois braços compartilham o mesmo modelo com tipos de prompt diferentes
- **THEN** ambos usam a mesma instância de provedor, para que o intervalo mínimo entre chamadas seja respeitado entre eles
