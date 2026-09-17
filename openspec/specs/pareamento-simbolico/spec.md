# pareamento-simbolico

## Purpose

Decidir, para cada caso do gabarito, qual alerta do Semgrep — se algum — fala da mesma fraqueza que o gabarito rotulou, e registrar o porquê quando nenhum fala.

É a fronteira entre o motor simbólico e o neural: o alerta emparelhado é a única entrada que a Fase 2 hidrata e que o LLM julga, de modo que emparelhar errado não produz um erro visível no CSV — produz um caso em que o LLM opina sobre uma fraqueza diferente da que o gabarito afirma. Por isso o critério é o casamento explícito de CWE e nada mais: nem o número de alertas no arquivo, nem a coincidência textual de prefixo entre identificadores.

O motivo da não-detecção fica aqui pelo mesmo motivo. `SEM_ALERTA` e `ALERTA_OUTRA_CWE` compartilham o mesmo `Status_Semgrep` e a mesma célula da matriz de cobertura, mas sustentam afirmações diferentes sobre o ponto cego do motor, e só o pareamento sabe distingui-los.

## Requirements

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

### Requirement: Motivo da não-detecção
O sistema SHALL distinguir dois motivos de não-detecção, antes fundidos num único `NAO_DETECTADO`: `SEM_ALERTA`, quando o Semgrep não emitiu alerta algum sobre o arquivo, e `ALERTA_OUTRA_CWE`, quando emitiu alertas mas nenhum casa com a CWE do gabarito.

O valor de `Status_Semgrep` SHALL permanecer `NAO_DETECTADO` nos dois motivos. O motivo é informação adicional, não um estado novo: o checkpoint por tripla, o cache simbólico e a leitura de métricas comparam esse valor diretamente, e introduzir um terceiro valor os quebraria em silêncio.

Os dois motivos SHALL entrar na matriz de cobertura simbólica pela mesma célula, porque nos dois a CWE rotulada de fato não foi detectada — é ponto cego do motor simbólico, não falha de esteira.

#### Scenario: Arquivo sem alerta nenhum
- **WHEN** o Semgrep termina sem emitir alerta algum sobre o arquivo
- **THEN** o motivo registrado é `SEM_ALERTA`

#### Scenario: Arquivo com alerta de outra fraqueza
- **WHEN** o Semgrep emite um ou mais alertas e nenhum casa com a CWE do gabarito
- **THEN** o motivo registrado é `ALERTA_OUTRA_CWE`

#### Scenario: Status permanece NAO_DETECTADO
- **WHEN** um caso termina em qualquer um dos dois motivos
- **THEN** `Status_Semgrep` é `NAO_DETECTADO`, e o checkpoint por tripla continua tratando o caso como resolvido sem consultar o LLM

#### Scenario: Ambos os motivos contam como ponto cego
- **WHEN** um caso de gabarito vulnerável termina em qualquer um dos dois motivos
- **THEN** ele é classificado como `Semgrep FN (ponto cego simbólico)` na matriz de cobertura, e fica fora da matriz de acerto do LLM

#### Scenario: Caso emparelhado não tem motivo
- **WHEN** um alerta é emparelhado ao caso
- **THEN** o campo de motivo sai como `N/A`, porque não houve não-detecção

#### Scenario: Saída inválida do motor não vira SEM_ALERTA
- **WHEN** a execução do Semgrep termina sem produzir um documento SARIF legível — saída vazia, ilegível ou sem a chave `runs`
- **THEN** o caso é tratado como falha de esteira e nenhum motivo de não-detecção é registrado, porque `SEM_ALERTA` seria gravado no cache e viraria ponto cego permanente do motor, enquanto a falha de esteira não é cacheada e o caso é recomputado

#### Scenario: Ausência legítima de achados continua sendo SEM_ALERTA
- **WHEN** o Semgrep produz um SARIF bem formado com zero achados
- **THEN** o motivo é `SEM_ALERTA`, para que a proteção contra saída inválida não mascare o silêncio real do motor

### Requirement: Registro das regras que dispararam sem casar
O sistema SHALL registrar, quando o motivo é `ALERTA_OUTRA_CWE`, os identificadores das regras (`check_id`) que dispararam sobre o arquivo sem casar com a CWE do gabarito. O registro SHALL ir para o CSV de resultados e para o cache simbólico, e a ordem SHALL ser determinística.

Isso é o que sustenta a análise de cobertura simbólica do capítulo de resultados — "o Semgrep leu o arquivo, mas enxergou outra fraqueza" é uma afirmação diferente de "o Semgrep não viu nada" — e permite reconstruir a tabela de diagnóstico sem re-executar a pipeline.

#### Scenario: Regras concorrentes registradas
- **WHEN** um caso termina em `ALERTA_OUTRA_CWE`
- **THEN** o CSV traz os `check_id` das regras que dispararam sem casar

#### Scenario: Sem alerta, sem regras
- **WHEN** um caso termina em `SEM_ALERTA`
- **THEN** o campo de regras sai vazio, e não é confundido com ausência de informação sobre um caso `ALERTA_OUTRA_CWE`

#### Scenario: Ordem determinística
- **WHEN** várias regras dispararam sem casar
- **THEN** todas são registradas numa ordem estável entre execuções, de modo que dois CSVs da mesma população sejam comparáveis linha a linha

#### Scenario: Diagnóstico sobrevive ao cache
- **WHEN** um caso não detectado é servido do cache simbólico numa rodada posterior
- **THEN** o motivo e as regras concorrentes vêm do cache junto com o status, sem nova execução do Semgrep
