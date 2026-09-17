## MODIFIED Requirements

### Requirement: Persistência do resultado simbólico
O sistema SHALL persistir em disco, por caso, o resultado da Fase 1 (alerta do Semgrep, status de detecção, motivo da não-detecção e regras que dispararam sem casar) e o contexto hidratado da Fase 2, de forma que execuções subsequentes possam reaproveitá-los sem reexecutar o Semgrep.

O motivo e as regras concorrentes entram no payload porque são produto da Fase 1 como qualquer outro: se ficassem de fora, uma rodada servida do cache perderia o diagnóstico de cobertura simbólica e só o recuperaria reexecutando o Semgrep sobre a população inteira — exatamente o custo que este cache existe para evitar.

A identidade do motor que produziu o resultado entra no payload pela mesma razão: é produto da Fase 1, não é recuperável depois, e sem ela uma entrada não sabe dizer se descreve o que o motor CE viu ou o que o motor com análise entre arquivos viu.

#### Scenario: Primeira execução popula o cache
- **WHEN** um caso passa pelas Fases 1 e 2 pela primeira vez
- **THEN** uma entrada de cache simbólico é gravada contendo o alerta, o contexto hidratado, o status do Semgrep, a versão do ruleset, a versão da regra de pareamento e a identidade do motor simbólico

#### Scenario: Execução seguinte reaproveita
- **WHEN** o mesmo caso é executado em outro braço
- **THEN** o Semgrep não é invocado e o contexto vem do cache simbólico

#### Scenario: Casos não detectados também são cacheados
- **WHEN** um caso termina em `NAO_DETECTADO`
- **THEN** esse status é gravado no cache simbólico junto com o motivo da não-detecção e as regras que dispararam sem casar, e é reaproveitado sem nova execução do Semgrep

#### Scenario: Falha de esteira não é cacheada
- **WHEN** a resolução do arquivo-alvo ou a execução do Semgrep falha com erro de esteira
- **THEN** nenhuma entrada é gravada, para que uma falha transitória de rede não se torne um `NAO_DETECTADO` permanente

### Requirement: Chave e invalidação do cache simbólico
O sistema SHALL indexar o cache simbólico pela combinação repositório, commit, arquivo e CWE, SHALL registrar na entrada a versão do ruleset, a versão da regra de pareamento e a identidade do motor simbólico, e SHALL tratar como inválida a entrada em que qualquer uma das três diverge da corrente.

A versão da regra de pareamento é um eixo de invalidação separado do ruleset porque as duas variam por motivos independentes: o ruleset muda quando o Semgrep passa a enxergar coisas diferentes, a regra de pareamento muda quando a pipeline passa a aceitar como do caso um conjunto diferente de alertas. Uma entrada gravada sob regra de pareamento anterior pode conter um alerta que a regra corrente recusaria, e servi-la do disco reintroduziria silenciosamente o emparelhamento que a regra nova elimina.

A identidade do motor é um terceiro eixo, também independente dos outros dois. O mesmo ruleset, sob a mesma regra de pareamento, produz conjuntos de alertas diferentes conforme o motor rastreie fluxo de dados apenas dentro do arquivo ou também entre arquivos. Sem este eixo, ligar o modo entre-arquivos não invalidaria nada: a rodada seria servida do disco com os alertas do motor anterior, e o experimento reportaria como resultado do motor novo aquilo que o motor antigo produziu — em silêncio, que é o modo de falha que este cache mais precisa evitar.

A invalidação por mudança de regra de pareamento SHALL alcançar também as entradas `NAO_DETECTADO`. Elas continuariam corretas quanto ao status — endurecer o pareamento nunca transforma não-detecção em detecção —, mas não sabem informar qual dos dois motivos as produziu, e aceitá-las deixaria o diagnóstico de cobertura incompleto para a maior parte da população.

A invalidação por mudança de motor SHALL alcançar as entradas `NAO_DETECTADO` com mais razão ainda: é exatamente nelas que o motor novo pode produzir resultado diferente, e aceitá-las do disco esconderia o único ganho que justifica a troca.

#### Scenario: Ruleset divergente invalida
- **WHEN** existe entrada de cache gravada com uma versão de ruleset diferente da atual
- **THEN** a entrada é ignorada e o Semgrep é reexecutado para aquele caso

#### Scenario: Regra de pareamento divergente invalida
- **WHEN** existe entrada de cache gravada sob uma versão da regra de pareamento diferente da atual
- **THEN** a entrada é ignorada e o Semgrep é reexecutado para aquele caso, inclusive quando a entrada registra `NAO_DETECTADO`

#### Scenario: Motor divergente invalida
- **WHEN** existe entrada de cache gravada sob identidade de motor diferente da corrente
- **THEN** a entrada é ignorada e o Semgrep é reexecutado para aquele caso, inclusive quando a entrada registra `NAO_DETECTADO`

#### Scenario: Entrada sem identidade de motor é tratada como CE
- **WHEN** existe entrada gravada antes de a identidade do motor passar a ser registrada
- **THEN** ela é tratada como produzida pelo motor CE sem modo entre-arquivos, e portanto é válida para execuções nesse motor e inválida para execuções com o modo ligado

#### Scenario: Entrada sem versão de pareamento é tratada como anterior
- **WHEN** existe entrada gravada antes de a versão da regra de pareamento passar a ser registrada
- **THEN** ela é tratada como divergente e recomputada, em vez de aceita por omissão

#### Scenario: Entrada invalidada não é apagada
- **WHEN** uma entrada é ignorada por divergência de versão
- **THEN** o arquivo permanece em disco, porque continua sendo evidência do que aquele ruleset, aquela regra de pareamento e aquele motor produziram

#### Scenario: Separação do cache de fontes
- **WHEN** o cache simbólico é gravado ou invalidado
- **THEN** nenhum arquivo sob `cache/` é criado, alterado ou removido, preservando a invariante de que o cache de fontes nunca invalida

#### Scenario: Entrada corrompida não derruba a rodada
- **WHEN** um arquivo de cache simbólico está ilegível ou não é JSON válido
- **THEN** ele é tratado como ausente e o caso é recomputado

#### Scenario: Desativação explícita
- **WHEN** o runner é invocado com a opção que desativa o cache simbólico
- **THEN** as Fases 1 e 2 são executadas normalmente e o resultado não é lido do cache

#### Scenario: Entradas dos dois motores coexistem
- **WHEN** o mesmo caso foi executado sob os dois motores
- **THEN** as duas entradas existem em disco simultaneamente e cada rodada recebe a que corresponde ao seu motor, sem que uma sobrescreva a outra
