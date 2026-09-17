# cache-simbolico

## Purpose

Persistir em disco o resultado das Fases 1 e 2 por caso — alerta do Semgrep, status de detecção e contexto hidratado — para que os braços da matriz experimental executem apenas a chamada de LLM.

Atende a dois objetivos distintos. O de custo: sem o cache, cada braço reexecutaria o Semgrep sobre a população inteira, inclusive nos casos `NAO_DETECTADO`, que são a maioria e onde o motor simbólico gasta tempo sem produzir chamada de LLM. O de validade interna, que é o mais importante: o contexto hidratado gravado é a string que alimenta todos os braços, o que garante entrada byte-a-byte idêntica na comparação pareada — sem isso, uma diferença de veredito poderia vir de uma diferença de entrada, não do braço.

Fica separado do cache de fontes (`cache/`) porque este é imutável por construção — a chave é um SHA de commit — enquanto o resultado simbólico depende da versão do ruleset do Semgrep, da versão da regra de pareamento e da identidade do motor que o produziu, que mudam.

## Requirements

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

### Requirement: Contexto idêntico entre braços
O sistema SHALL fornecer aos quatro braços o mesmo contexto hidratado byte-a-byte para um dado caso, garantindo validade interna da comparação pareada.

#### Scenario: Byte-a-byte igual
- **WHEN** o mesmo caso é avaliado nos quatro braços
- **THEN** a string de contexto passada ao montador de prompt é idêntica em todos, byte a byte

#### Scenario: Fases 1 e 2 rodam uma vez por caso
- **WHEN** um caso é processado numa rodada com N braços
- **THEN** o motor simbólico e a hidratação são invocados uma única vez, fora do laço de braços

### Requirement: Chave e invalidação do cache simbólico
O sistema SHALL indexar o cache simbólico pela combinação repositório, commit, arquivo e CWE, SHALL registrar na entrada a identidade do **conjunto de rulesets**, a versão da regra de pareamento e a identidade do motor simbólico, e SHALL tratar como inválida a entrada em que qualquer uma das três diverge da corrente.

Os três eixos variam por motivos independentes, e nenhum absorve o outro: o conjunto de rulesets muda quando o Semgrep passa a enxergar coisas diferentes, a regra de pareamento muda quando a pipeline passa a aceitar como do caso um conjunto diferente de alertas, e o motor muda quando o alcance da análise muda.

O eixo do ruleset SHALL identificar o **conjunto** configurado, e não um ruleset isolado. Acrescentar um segundo ruleset muda o que o motor emite tanto quanto trocar o primeiro; se a identidade registrada descrevesse apenas um deles, uma rodada composta seria servida do disco com os alertas da rodada unitária, e o experimento reportaria como resultado do conjunto novo aquilo que o conjunto antigo produziu.

A versão da regra de pareamento é um eixo de invalidação separado do ruleset porque as duas variam por motivos independentes: uma entrada gravada sob regra de pareamento anterior pode conter um alerta que a regra corrente recusaria, e servi-la do disco reintroduziria silenciosamente o emparelhamento que a regra nova elimina.

A identidade do motor é um terceiro eixo, também independente dos outros dois. O mesmo conjunto de rulesets, sob a mesma regra de pareamento, produz conjuntos de alertas diferentes conforme o motor rastreie fluxo de dados apenas dentro do arquivo ou também entre arquivos. Sem este eixo, ligar o modo entre-arquivos não invalidaria nada: a rodada seria servida do disco com os alertas do motor anterior, e o experimento reportaria como resultado do motor novo aquilo que o motor antigo produziu — em silêncio, que é o modo de falha que este cache mais precisa evitar.

A invalidação por mudança de conjunto de rulesets SHALL alcançar as entradas `NAO_DETECTADO` com mais razão ainda: é exatamente nelas que o ruleset acrescentado pode produzir resultado diferente, e aceitá-las do disco esconderia o único ganho que justifica acrescentá-lo.

A invalidação por mudança de regra de pareamento SHALL alcançar também as entradas `NAO_DETECTADO`. Elas continuariam corretas quanto ao status — endurecer o pareamento nunca transforma não-detecção em detecção —, mas não sabem informar qual dos dois motivos as produziu, e aceitá-las deixaria o diagnóstico de cobertura incompleto para a maior parte da população.

A invalidação por mudança de motor SHALL alcançar as entradas `NAO_DETECTADO` com mais razão ainda: é exatamente nelas que o motor novo pode produzir resultado diferente, e aceitá-las do disco esconderia o único ganho que justifica a troca.

#### Scenario: Conjunto de rulesets divergente invalida
- **WHEN** existe entrada de cache gravada sob identidade de conjunto de rulesets diferente da corrente
- **THEN** a entrada é ignorada e o Semgrep é reexecutado para aquele caso, inclusive quando a entrada registra `NAO_DETECTADO`

#### Scenario: Acréscimo de ruleset invalida
- **WHEN** um ruleset é acrescentado à configuração e existe entrada gravada sob a configuração anterior
- **THEN** a entrada é ignorada, ainda que o ruleset anterior continue configurado

#### Scenario: Ordem dos rulesets não invalida
- **WHEN** os mesmos rulesets são configurados em ordem diferente da que gravou a entrada
- **THEN** a entrada permanece válida, porque a ordem não altera a união dos achados

#### Scenario: Entrada com ruleset único legado
- **WHEN** existe entrada gravada quando a configuração era um ruleset só, registrada pelo nome dele
- **THEN** ela é lida como identidade do conjunto unitário correspondente, e permanece válida enquanto a configuração corrente for esse mesmo conjunto

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
- **THEN** o arquivo permanece em disco, porque continua sendo evidência do que aquele conjunto de rulesets, aquela regra de pareamento e aquele motor produziram

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

### Requirement: Medição sob conjunto de rulesets distinto não disputa o cache da rodada
O sistema SHALL manter o resultado de uma medição feita sob conjunto de rulesets diferente do da rodada em armazenamento próprio, separado do cache simbólico da rodada.

A identidade do conjunto entra no **payload** da entrada, não no caminho dela — só o motor entra no nome do arquivo. A consequência é que entradas de conjuntos diferentes **não coexistem** para o mesmo caso: a segunda gravação sobrescreve a primeira no mesmo caminho.

A sobrescrita não produz resultado errado — a entrada tem identidade divergente e é recomputada, nunca servida por engano —, mas destrói trabalho: medido em 2026-09-17, uma medição de regras locais sobre 122 casos apagou as 122 entradas de `p/default` correspondentes, e recompor a população inteira custa horas de motor simbólico.

Pôr a identidade do conjunto no caminho SHALL NOT ser a solução, porque invalidaria por caminho todas as entradas já em disco — exatamente o que a identidade do conjunto unitário existe para evitar.

#### Scenario: Medição não apaga a entrada da rodada
- **WHEN** uma medição é executada sob conjunto de rulesets diferente do configurado para a rodada
- **THEN** a entrada de cache da rodada para aquele caso permanece intacta

#### Scenario: Medição reaproveita o próprio resultado anterior
- **WHEN** a mesma medição é repetida sob o mesmo conjunto de rulesets
- **THEN** o resultado é servido do armazenamento próprio dela, sem reexecutar o motor
