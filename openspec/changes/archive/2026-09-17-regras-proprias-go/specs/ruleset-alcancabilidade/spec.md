## MODIFIED Requirements

### Requirement: Conjunto de CWEs alcançáveis derivado do ruleset
O sistema SHALL determinar, a partir da **união dos catálogos dos rulesets em uso** **e do motor em uso**, o conjunto de CWEs que o motor simbólico é capaz de detectar numa dada linguagem. O conjunto SHALL ser derivado dos catálogos a cada consulta, e NÃO SHALL ser uma lista fixa no código.

Os rulesets são configuráveis por `SEMGREP_CONFIG`. Uma lista fixa passaria a mentir no instante em que a configuração mudasse, e mentiria em silêncio — não há como um valor embutido no código perceber que o catálogo do servidor mudou, nem que um segundo ruleset foi acrescentado.

A união é o critério correto porque o motor recebe todos os rulesets numa invocação só: uma CWE coberta por regra de qualquer um deles é alcançável naquela execução. Derivar de um só quando há vários configurados subestimaria a cobertura e recusaria, na colheita, população que o motor detectaria — o defeito exato que esta capability existe para prevenir.

O motor é o terceiro eixo pelo mesmo argumento. O catálogo do registry descreve as regras da edição aberta; o modo entre-arquivos acrescenta regras próprias, que não constam daquele catálogo, e altera o alcance das regras que constam — uma regra de taint que hoje só enxerga dentro do arquivo passa a atravessar arquivos. Uma consulta que ignore o motor subestimaria a cobertura em silêncio.

Enquanto a consulta não souber enumerar as regras próprias do modo entre-arquivos, ela SHALL declarar essa limitação em vez de omiti-la: um conjunto derivado apenas dos catálogos abertos é **limite inferior** da cobertura do motor com o modo ligado, e tratá-lo como exato recusaria população que o motor teria detectado.

O cache de catálogo SHALL ser **por ruleset**, e não pelo conjunto. Rulesets são buscados e mudam independentemente; cachear por conjunto rebuscaria o catálogo inteiro de um deles toda vez que outro fosse acrescentado ou retirado.

Regras de rulesets distintos que compartilhem o mesmo identificador SHALL ser preservadas separadamente. Rulesets publicados compartilham regras — `p/gosec` e `p/default` têm 22 em comum —, e fundir os catálogos por chave descartaria silenciosamente uma das versões; se a descartada fosse a de grau mais alto, a CWE seria rebaixada por um detalhe de nomenclatura.

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
- **THEN** o catálogo do primeiro é servido do cache, sem nova busca

#### Scenario: Identificador repetido entre rulesets não descarta regra
- **WHEN** dois rulesets configurados trazem regras de mesmo identificador com atributos diferentes
- **THEN** ambas contam para o grau da CWE, e a de grau mais alto prevalece

#### Scenario: Conjunto acompanha o motor configurado
- **WHEN** a consulta é feita para o motor com modo entre-arquivos e para o motor sem ele
- **THEN** os dois resultados são distinguíveis, e o do modo entre-arquivos nunca é subconjunto próprio do outro

#### Scenario: Cobertura do modo entre-arquivos é declarada como limite inferior
- **WHEN** a consulta é feita para o motor com modo entre-arquivos e o catálogo disponível não enumera as regras próprias desse modo
- **THEN** o conjunto é devolvido acompanhado da informação de que é limite inferior, em vez de apresentado como exato

## ADDED Requirements

### Requirement: Grau de alcançabilidade considera todos os rulesets
O sistema SHALL atribuir a cada CWE o grau da melhor regra que a cobre **em qualquer dos rulesets configurados**, mantendo a regra já vigente de que o grau da CWE é o da melhor regra.

O critério já em vigor é que basta uma regra capaz para que o motor tenha chance de alcançar a CWE. Limitar a busca dessa melhor regra a um único ruleset contradiria o critério assim que houvesse mais de um configurado.

A consequência é intencional e foi medida em 2026-09-17: CWE-22 e CWE-918, cobertas no `p/default` apenas por regras de taint e por isso em grau intermediário, passam a ser cobertas também por regra sintática que afirma detectar vulnerabilidade quando o ruleset próprio é configurado, e sobem para o grau alto.

#### Scenario: Regra de outro ruleset eleva o grau
- **WHEN** uma CWE é coberta por regra de taint num ruleset e por regra sintática de vulnerabilidade em outro
- **THEN** ela recebe o grau mais alto dos dois

#### Scenario: Grau não cai ao acrescentar ruleset
- **WHEN** um ruleset é acrescentado à configuração
- **THEN** nenhuma CWE tem seu grau rebaixado

#### Scenario: Validação do grau é refeita por conjunto de rulesets
- **WHEN** a separação empírica entre os graus é medida
- **THEN** ela é medida para o conjunto de rulesets em uso, porque a evidência colhida sob um conjunto não sustenta outro
