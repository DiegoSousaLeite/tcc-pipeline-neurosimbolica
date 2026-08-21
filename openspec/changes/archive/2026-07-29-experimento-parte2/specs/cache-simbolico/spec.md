## ADDED Requirements

### Requirement: Persistência do resultado simbólico
O sistema SHALL persistir em disco, por caso, o resultado da Fase 1 (alerta do Semgrep e status de detecção) e o contexto hidratado da Fase 2, de forma que execuções subsequentes possam reaproveitá-los sem reexecutar o Semgrep.

#### Scenario: Primeira execução popula o cache
- **WHEN** um caso passa pelas Fases 1 e 2 pela primeira vez
- **THEN** uma entrada de cache simbólico é gravada contendo o alerta, o contexto hidratado, o status do Semgrep e a versão do ruleset

#### Scenario: Execução seguinte reaproveita
- **WHEN** o mesmo caso é executado em outro braço
- **THEN** o Semgrep não é invocado e o contexto vem do cache simbólico

#### Scenario: Casos não detectados também são cacheados
- **WHEN** um caso termina em `NAO_DETECTADO`
- **THEN** esse status é gravado no cache simbólico e reaproveitado, sem nova execução do Semgrep

### Requirement: Contexto idêntico entre braços
O sistema SHALL fornecer aos quatro braços o mesmo contexto hidratado byte-a-byte para um dado caso, garantindo validade interna da comparação pareada.

#### Scenario: Byte-a-byte igual
- **WHEN** o mesmo caso é avaliado nos quatro braços
- **THEN** a string de contexto passada ao montador de prompt é idêntica em todos, byte a byte

### Requirement: Chave e invalidação do cache simbólico
O sistema SHALL indexar o cache simbólico pela combinação repositório, commit, arquivo e CWE, SHALL registrar a versão do ruleset na entrada, e SHALL tratar como inválida a entrada cuja versão de ruleset diverge da corrente.

#### Scenario: Ruleset divergente invalida
- **WHEN** existe entrada de cache gravada com uma versão de ruleset diferente da atual
- **THEN** a entrada é ignorada e o Semgrep é reexecutado para aquele caso

#### Scenario: Separação do cache de fontes
- **WHEN** o cache simbólico é gravado ou invalidado
- **THEN** nenhum arquivo sob `cache/` é criado, alterado ou removido, preservando a invariante de que o cache de fontes nunca invalida

#### Scenario: Desativação explícita
- **WHEN** o runner é invocado com a opção que desativa o cache simbólico
- **THEN** as Fases 1 e 2 são executadas normalmente e o resultado não é lido do cache
