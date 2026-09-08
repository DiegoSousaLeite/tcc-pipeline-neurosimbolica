## ADDED Requirements

### Requirement: Não-detecção discriminada por motivo
O sistema SHALL reportar, no bloco de cobertura simbólica, a não-detecção discriminada pelos seus dois motivos — `SEM_ALERTA` e `ALERTA_OUTRA_CWE` — em vez de apenas o total de `NAO_DETECTADO`.

A distinção é o que separa duas afirmações diferentes sobre o motor simbólico: "não existe regra que alcance esta fraqueza neste arquivo" e "existem regras que dispararam, mas sobre outra fraqueza". Colapsá-las num número só descreveria como ponto cego uniforme aquilo que na verdade tem duas causas distintas, e a segunda é a que sustenta a leitura de que o alerta e o gabarito falam de coisas diferentes.

#### Scenario: Contagem por motivo na cobertura
- **WHEN** as métricas de uma rodada são geradas
- **THEN** o bloco de cobertura simbólica traz a contagem de casos em `SEM_ALERTA` e em `ALERTA_OUTRA_CWE` separadamente

#### Scenario: Motivo não é contado por braço
- **WHEN** a contagem por motivo é calculada numa rodada com vários braços
- **THEN** cada caso entra uma vez só, pela mesma razão que a matriz de cobertura não é contada por braço: o Semgrep roda uma vez por caso

#### Scenario: Total preservado
- **WHEN** a contagem por motivo é apresentada
- **THEN** a soma dos dois motivos é igual ao total de casos em `NAO_DETECTADO`, de modo que a discriminação não altere a matriz de cobertura

#### Scenario: CSV sem a coluna de motivo
- **WHEN** um CSV anterior a esta mudança, sem a coluna de motivo, é analisado
- **THEN** os casos são reportados como motivo indisponível e as demais métricas são calculadas normalmente, sem erro
