## MODIFIED Requirements

### Requirement: Conjunto de CWEs alcançáveis derivado do ruleset
O sistema SHALL determinar, a partir **da união dos catálogos dos rulesets em
uso**, o conjunto de CWEs que o motor simbólico é capaz de detectar numa dada
linguagem. O conjunto SHALL ser derivado dos catálogos a cada consulta, e NÃO
SHALL ser uma lista fixa no código.

Os rulesets são configuráveis. Uma lista fixa passaria a mentir no instante em
que a configuração mudasse, e mentiria em silêncio — não há como um valor
embutido no código perceber que o catálogo do servidor mudou, nem que um segundo
ruleset foi acrescentado.

A união é o critério correto porque o motor recebe todos os rulesets numa
invocação só: uma CWE coberta por regra de qualquer um deles é alcançável
naquela execução. Derivar de um só ruleset quando há vários configurados
subestimaria a cobertura e recusaria, na colheita, população que o motor
detectaria — o defeito exato que esta capability existe para prevenir.

O cache de catálogo SHALL ser por ruleset, e não pelo conjunto. Rulesets são
buscados e mudam independentemente; cachear por conjunto rebuscaria o
`p/default` inteiro toda vez que um segundo ruleset fosse acrescentado ou
retirado.

#### Scenario: CWE declarada por regra da linguagem é alcançável
- **WHEN** alguma regra de algum ruleset configurado declara a CWE e tem a linguagem consultada em `languages`
- **THEN** a CWE consta do conjunto alcançável

#### Scenario: CWE ausente de todos os rulesets não é alcançável
- **WHEN** nenhuma regra de nenhum ruleset configurado declara a CWE
- **THEN** a CWE não consta do conjunto alcançável

#### Scenario: Conjunto acompanha o ruleset configurado
- **WHEN** o conjunto de rulesets configurado muda
- **THEN** o conjunto alcançável é recalculado a partir dos novos catálogos, sem edição de código

#### Scenario: Acréscimo de ruleset só amplia
- **WHEN** um ruleset é acrescentado a uma configuração existente
- **THEN** o conjunto alcançável resultante contém o anterior, e nenhuma CWE antes alcançável deixa de sê-lo

#### Scenario: Catálogo é cacheado por ruleset
- **WHEN** um segundo ruleset é acrescentado à configuração
- **THEN** o catálogo do primeiro é servido do cache, sem nova busca no registry

## ADDED Requirements

### Requirement: Grau de alcançabilidade considera todos os rulesets
O sistema SHALL atribuir a cada CWE o grau da melhor regra que a cobre **em
qualquer dos rulesets configurados**, mantendo a regra já vigente de que o grau
da CWE é o da melhor regra.

O critério já em vigor é que basta uma regra capaz para que o motor tenha chance
de alcançar a CWE. Limitar a busca dessa melhor regra a um único ruleset
contradiria o critério assim que houvesse mais de um configurado.

A consequência é intencional e é metade do motivo desta change: CWE-22, hoje
coberta apenas por regras de taint e por isso em grau intermediário, passa a ser
coberta também por regra sintática que afirma detectar vulnerabilidade, e sobe
de grau.

#### Scenario: Regra de outro ruleset eleva o grau
- **WHEN** uma CWE é coberta por regra de taint num ruleset e por regra sintática de vulnerabilidade em outro
- **THEN** ela recebe o grau mais alto dos dois

#### Scenario: Grau não cai ao acrescentar ruleset
- **WHEN** um ruleset é acrescentado à configuração
- **THEN** nenhuma CWE tem seu grau rebaixado

#### Scenario: Validação do grau é refeita por conjunto de rulesets
- **WHEN** a separação empírica entre os graus é medida
- **THEN** ela é medida para o conjunto de rulesets em uso, porque a evidência colhida sob um conjunto não sustenta outro
