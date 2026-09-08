# cache-simbolico

## Purpose

Persistir em disco o resultado das Fases 1 e 2 por caso — alerta do Semgrep, status de detecção e contexto hidratado — para que os braços da matriz experimental executem apenas a chamada de LLM.

Atende a dois objetivos distintos. O de custo: sem o cache, cada braço reexecutaria o Semgrep sobre a população inteira, inclusive nos casos `NAO_DETECTADO`, que são a maioria e onde o motor simbólico gasta tempo sem produzir chamada de LLM. O de validade interna, que é o mais importante: o contexto hidratado gravado é a string que alimenta todos os braços, o que garante entrada byte-a-byte idêntica na comparação pareada — sem isso, uma diferença de veredito poderia vir de uma diferença de entrada, não do braço.

Fica separado do cache de fontes (`cache/`) porque este é imutável por construção — a chave é um SHA de commit — enquanto o resultado simbólico depende da versão do ruleset do Semgrep e da versão da regra de pareamento, que mudam.

## Requirements

### Requirement: Persistência do resultado simbólico
O sistema SHALL persistir em disco, por caso, o resultado da Fase 1 (alerta do Semgrep, status de detecção, motivo da não-detecção e regras que dispararam sem casar) e o contexto hidratado da Fase 2, de forma que execuções subsequentes possam reaproveitá-los sem reexecutar o Semgrep.

O motivo e as regras concorrentes entram no payload porque são produto da Fase 1 como qualquer outro: se ficassem de fora, uma rodada servida do cache perderia o diagnóstico de cobertura simbólica e só o recuperaria reexecutando o Semgrep sobre a população inteira — exatamente o custo que este cache existe para evitar.

#### Scenario: Primeira execução popula o cache
- **WHEN** um caso passa pelas Fases 1 e 2 pela primeira vez
- **THEN** uma entrada de cache simbólico é gravada contendo o alerta, o contexto hidratado, o status do Semgrep, a versão do ruleset e a versão da regra de pareamento

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
O sistema SHALL indexar o cache simbólico pela combinação repositório, commit, arquivo e CWE, SHALL registrar na entrada tanto a versão do ruleset quanto a versão da regra de pareamento, e SHALL tratar como inválida a entrada em que qualquer uma das duas diverge da corrente.

A versão da regra de pareamento é um eixo de invalidação separado do ruleset porque as duas variam por motivos independentes: o ruleset muda quando o Semgrep passa a enxergar coisas diferentes, a regra de pareamento muda quando a pipeline passa a aceitar como do caso um conjunto diferente de alertas. Uma entrada gravada sob regra de pareamento anterior pode conter um alerta que a regra corrente recusaria, e servi-la do disco reintroduziria silenciosamente o emparelhamento que a regra nova elimina.

A invalidação por mudança de regra de pareamento SHALL alcançar também as entradas `NAO_DETECTADO`. Elas continuariam corretas quanto ao status — endurecer o pareamento nunca transforma não-detecção em detecção —, mas não sabem informar qual dos dois motivos as produziu, e aceitá-las deixaria o diagnóstico de cobertura incompleto para a maior parte da população.

#### Scenario: Ruleset divergente invalida
- **WHEN** existe entrada de cache gravada com uma versão de ruleset diferente da atual
- **THEN** a entrada é ignorada e o Semgrep é reexecutado para aquele caso

#### Scenario: Regra de pareamento divergente invalida
- **WHEN** existe entrada de cache gravada sob uma versão da regra de pareamento diferente da atual
- **THEN** a entrada é ignorada e o Semgrep é reexecutado para aquele caso, inclusive quando a entrada registra `NAO_DETECTADO`

#### Scenario: Entrada sem versão de pareamento é tratada como anterior
- **WHEN** existe entrada gravada antes de a versão da regra de pareamento passar a ser registrada
- **THEN** ela é tratada como divergente e recomputada, em vez de aceita por omissão

#### Scenario: Entrada invalidada não é apagada
- **WHEN** uma entrada é ignorada por divergência de versão
- **THEN** o arquivo permanece em disco, porque continua sendo evidência do que aquele ruleset e aquela regra de pareamento produziram

#### Scenario: Separação do cache de fontes
- **WHEN** o cache simbólico é gravado ou invalidado
- **THEN** nenhum arquivo sob `cache/` é criado, alterado ou removido, preservando a invariante de que o cache de fontes nunca invalida

#### Scenario: Entrada corrompida não derruba a rodada
- **WHEN** um arquivo de cache simbólico está ilegível ou não é JSON válido
- **THEN** ele é tratado como ausente e o caso é recomputado

#### Scenario: Desativação explícita
- **WHEN** o runner é invocado com a opção que desativa o cache simbólico
- **THEN** as Fases 1 e 2 são executadas normalmente e o resultado não é lido do cache
