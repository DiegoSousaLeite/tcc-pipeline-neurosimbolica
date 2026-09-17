## MODIFIED Requirements

### Requirement: Emparelhamento por casamento explícito de CWE
O sistema SHALL emparelhar um alerta do Semgrep ao caso somente quando a regra que emitiu o alerta declarar explicitamente a CWE do gabarito em suas tags. Nenhuma outra condição SHALL produzir emparelhamento — em particular, o número de alertas no arquivo não SHALL ser critério de emparelhamento.

O casamento SHALL ser por identificador completo de CWE, e não por prefixo textual: `CWE-20`, `CWE-77` e `CWE-79` são prefixos de `CWE-200`/`CWE-209`, `CWE-770` e `CWE-798`, todos presentes na população, e uma comparação por substring emparelharia um caso à regra errada sem que nada no CSV denunciasse.

Quando mais de um alerta casa com a CWE do gabarito, o sistema SHALL escolher de forma determinística, para que duas execuções sobre o mesmo arquivo e o mesmo ruleset produzam o mesmo alerta.

A ausência de emparelhamento SHALL continuar determinando o status `NAO_DETECTADO` e SHALL continuar impedindo a chamada de LLM **no modo de montagem `filtro`**. No modo `triagem`, a ausência de emparelhamento continua produzindo `NAO_DETECTADO` — é verdade sobre o motor simbólico e não é sobrescrita —, mas deixa de ser o que decide se o caso chega ao LLM: para caso de gabarito vulnerável, o candidato passa a ser montado a partir do gabarito. A regra de emparelhamento em si não muda; muda apenas o que a sua ausência implica a jusante.

#### Scenario: Alerta com a CWE do gabarito é emparelhado
- **WHEN** o arquivo produz um alerta cuja regra traz a tag da CWE do gabarito
- **THEN** esse alerta é emparelhado ao caso e o status é `DETECTADO`

#### Scenario: Alerta único de outra CWE não é emparelhado
- **WHEN** o arquivo produz exatamente um alerta e a regra que o emitiu não traz a tag da CWE do gabarito
- **THEN** nenhum alerta é emparelhado e o status é `NAO_DETECTADO`

#### Scenario: Vários alertas, um deles casa
- **WHEN** o arquivo produz vários alertas e apenas um vem de regra com a tag da CWE do gabarito
- **THEN** esse alerta é o emparelhado, independentemente da posição em que aparece na saída do Semgrep

#### Scenario: Vários alertas, nenhum casa
- **WHEN** o arquivo produz vários alertas e nenhuma das regras traz a tag da CWE do gabarito
- **THEN** nenhum alerta é emparelhado e o status é `NAO_DETECTADO`

#### Scenario: Regra sem tag de CWE não emparelha
- **WHEN** o arquivo produz alertas cujas regras não declaram CWE alguma nas tags
- **THEN** nenhum alerta é emparelhado, mesmo que haja um único alerta no arquivo

#### Scenario: Prefixo de CWE não é casamento
- **WHEN** o gabarito é `CWE-77` e a única regra que disparou traz a tag `CWE-770`
- **THEN** não há emparelhamento, e o mesmo vale para os demais pares em que um identificador é prefixo do outro

#### Scenario: Escolha determinística entre alertas casados
- **WHEN** mais de um alerta vem de regra com a tag da CWE do gabarito
- **THEN** o alerta escolhido é o mesmo em execuções repetidas sobre o mesmo arquivo e ruleset

#### Scenario: Sem emparelhamento, o LLM não é consultado no modo filtro
- **WHEN** nenhum alerta é emparelhado ao caso e o modo de montagem é `filtro`
- **THEN** nenhum braço da matriz faz chamada de LLM para esse caso, preservando o desenho em que o LLM é filtro puro do Semgrep

#### Scenario: Sem emparelhamento, o status permanece NAO_DETECTADO em qualquer modo
- **WHEN** nenhum alerta é emparelhado ao caso e o modo de montagem é `triagem`
- **THEN** o status registrado continua sendo `NAO_DETECTADO` com o motivo preservado, ainda que o caso receba veredito de LLM

#### Scenario: Emparelhamento tem precedência sobre injeção
- **WHEN** um caso de gabarito vulnerável tem alerta emparelhado e o modo de montagem é `triagem`
- **THEN** o candidato vem do alerta, com procedência `alerta`, e nenhum candidato é montado a partir do gabarito para o mesmo caso
