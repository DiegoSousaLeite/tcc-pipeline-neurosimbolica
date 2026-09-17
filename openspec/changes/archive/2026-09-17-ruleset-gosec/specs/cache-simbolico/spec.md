## MODIFIED Requirements

### Requirement: Chave e invalidação do cache simbólico
O sistema SHALL indexar o cache simbólico pela combinação repositório, commit, arquivo e CWE, SHALL registrar na entrada tanto a identidade do **conjunto de rulesets** quanto a versão da regra de pareamento, e SHALL tratar como inválida a entrada em que qualquer uma das duas diverge da corrente.

A versão da regra de pareamento é um eixo de invalidação separado do ruleset porque as duas variam por motivos independentes: o ruleset muda quando o Semgrep passa a enxergar coisas diferentes, a regra de pareamento muda quando a pipeline passa a aceitar como do caso um conjunto diferente de alertas. Uma entrada gravada sob regra de pareamento anterior pode conter um alerta que a regra corrente recusaria, e servi-la do disco reintroduziria silenciosamente o emparelhamento que a regra nova elimina.

O eixo do ruleset SHALL identificar o **conjunto** configurado, e não um ruleset isolado. Acrescentar um segundo ruleset muda o que o motor emite tanto quanto trocar o primeiro; se a identidade registrada descrevesse apenas um deles, uma rodada composta seria servida do disco com os alertas da rodada unitária, e o experimento reportaria como resultado do conjunto novo aquilo que o conjunto antigo produziu.

A invalidação por mudança de conjunto de rulesets SHALL alcançar as entradas `NAO_DETECTADO` com mais razão ainda: é exatamente nelas que o ruleset acrescentado pode produzir resultado diferente, e aceitá-las do disco esconderia o único ganho que justifica acrescentá-lo.

A invalidação por mudança de regra de pareamento SHALL alcançar também as entradas `NAO_DETECTADO`. Elas continuariam corretas quanto ao status — endurecer o pareamento nunca transforma não-detecção em detecção —, mas não sabem informar qual dos dois motivos as produziu, e aceitá-las deixaria o diagnóstico de cobertura incompleto para a maior parte da população.

#### Scenario: Conjunto de rulesets divergente invalida
- **WHEN** existe entrada de cache gravada sob identidade de conjunto de rulesets diferente da corrente
- **THEN** a entrada é ignorada e o Semgrep é reexecutado para aquele caso, inclusive quando a entrada registra `NAO_DETECTADO`

#### Scenario: Acréscimo de ruleset invalida
- **WHEN** um ruleset é acrescentado à configuração e existe entrada gravada sob a configuração anterior
- **THEN** a entrada é ignorada, ainda que o ruleset anterior continue configurado

#### Scenario: Ordem dos rulesets não invalida
- **WHEN** os mesmos rulesets são configurados em ordem diferente da que gravou a entrada
- **THEN** a entrada permanece válida, porque a ordem não altera a união dos achados

#### Scenario: Regra de pareamento divergente invalida
- **WHEN** existe entrada de cache gravada sob uma versão da regra de pareamento diferente da atual
- **THEN** a entrada é ignorada e o Semgrep é reexecutado para aquele caso, inclusive quando a entrada registra `NAO_DETECTADO`

#### Scenario: Entrada sem versão de pareamento é tratada como anterior
- **WHEN** existe entrada gravada antes de a versão da regra de pareamento passar a ser registrada
- **THEN** ela é tratada como divergente e recomputada, em vez de aceita por omissão

#### Scenario: Entrada com ruleset único legado
- **WHEN** existe entrada gravada quando a configuração era um ruleset só, registrada pelo nome dele
- **THEN** ela é lida como identidade do conjunto unitário correspondente, e permanece válida enquanto a configuração corrente for esse mesmo conjunto

#### Scenario: Entrada invalidada não é apagada
- **WHEN** uma entrada é ignorada por divergência de versão
- **THEN** o arquivo permanece em disco, porque continua sendo evidência do que aquele conjunto de rulesets e aquela regra de pareamento produziram

#### Scenario: Separação do cache de fontes
- **WHEN** o cache simbólico é gravado ou invalidado
- **THEN** nenhum arquivo sob `cache/` é criado, alterado ou removido, preservando a invariante de que o cache de fontes nunca invalida

#### Scenario: Entrada corrompida não derruba a rodada
- **WHEN** um arquivo de cache simbólico está ilegível ou não é JSON válido
- **THEN** ele é tratado como ausente e o caso é recomputado

#### Scenario: Desativação explícita
- **WHEN** o runner é invocado com a opção que desativa o cache simbólico
- **THEN** as Fases 1 e 2 são executadas normalmente e o resultado não é lido do cache
