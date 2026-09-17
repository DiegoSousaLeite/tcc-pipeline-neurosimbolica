## ADDED Requirements

### Requirement: Mais de um ruleset por execução
O sistema SHALL aceitar a configuração de mais de um ruleset simultâneo e SHALL
invocar o motor simbólico com todos eles, produzindo a união dos achados. A
configuração padrão SHALL permanecer um único ruleset, `p/default`.

Acrescentar cobertura não pode custar a cobertura existente. A troca de ruleset
já foi avaliada e recusada — o `p/golang`, mais enxuto, perdia 97 casos que o
`p/default` detectava. A união preserva o que já se detecta e é a única forma de
somar sem subtrair.

O padrão permanece unitário porque ligar o segundo ruleset muda o conjunto de
alertas e, portanto, o objeto que o braço neural tria. As Rodadas 1–3 mediram o
`p/default`; a comparabilidade só pode se perder por decisão explícita.

#### Scenario: Configuração unitária preserva o comportamento anterior
- **WHEN** a pipeline é executada sem configurar ruleset adicional
- **THEN** o motor é invocado exatamente como antes desta mudança e os alertas produzidos são os mesmos

#### Scenario: Configuração composta produz a união
- **WHEN** dois rulesets são configurados
- **THEN** o motor é invocado com ambos e o conjunto de achados contém os de cada um

#### Scenario: Nenhum ruleset configurado é erro explícito
- **WHEN** a configuração de rulesets está vazia
- **THEN** a falha é reportada claramente, em vez de o motor ser invocado sem regras — uma execução sem regras produziria zero alertas e toda a população pareceria não detectada

### Requirement: Identidade composta do conjunto de rulesets
O sistema SHALL derivar uma identidade única do conjunto de rulesets configurado,
estável para o mesmo conjunto e distinta para conjuntos distintos, incluindo
quando um conjunto é subconjunto do outro.

Sem identidade própria, `p/default` e `p/default + p/gosec` seriam
indistinguíveis para todo consumidor que hoje registra "a versão do ruleset" — e
o cache serviria, para uma rodada composta, o resultado da rodada unitária.

A identidade NÃO SHALL depender da ordem em que os rulesets foram configurados.
A ordem não altera a união dos achados, e fazê-la alterar a identidade
invalidaria cache por um detalhe sem significado.

#### Scenario: Mesmo conjunto, mesma identidade
- **WHEN** o mesmo conjunto de rulesets é configurado em duas execuções
- **THEN** a identidade derivada é a mesma

#### Scenario: Ordem não altera a identidade
- **WHEN** os mesmos rulesets são configurados em ordens diferentes
- **THEN** a identidade derivada é a mesma

#### Scenario: Subconjunto tem identidade distinta
- **WHEN** um conjunto é comparado com outro que o contém
- **THEN** as identidades são distintas

### Requirement: Deduplicação declarada de achados
O sistema SHALL aplicar uma política declarada de deduplicação quando rulesets
diferentes produzirem achados equivalentes para o mesmo caso, e a política SHALL
ser determinística.

Dois rulesets podem cobrir a mesma CWE no mesmo ponto do código. Sem política, o
número de alertas por arquivo passaria a depender de quantos rulesets cobrem
aquele padrão — e esse número alimenta o diagnóstico de cobertura simbólica.

A deduplicação NÃO SHALL alterar o resultado do emparelhamento por CWE. Se
qualquer um dos achados equivalentes casa com a CWE do gabarito, o caso é
`DETECTADO`; deduplicar não pode transformar detecção em não-detecção.

#### Scenario: Achados equivalentes são deduplicados
- **WHEN** dois rulesets produzem achado no mesmo arquivo, na mesma posição e com a mesma CWE
- **THEN** eles contam como um só achado

#### Scenario: Mesma posição, CWEs diferentes não são duplicata
- **WHEN** dois rulesets produzem achado na mesma posição com CWEs diferentes
- **THEN** ambos são preservados, porque descrevem fraquezas distintas

#### Scenario: Deduplicação é determinística
- **WHEN** a mesma execução é repetida sobre o mesmo arquivo e o mesmo conjunto de rulesets
- **THEN** o achado preservado é o mesmo

#### Scenario: Deduplicação não altera o status
- **WHEN** achados equivalentes de rulesets diferentes casam com a CWE do gabarito
- **THEN** o status continua sendo `DETECTADO`

### Requirement: Regras de terceiros não são regras próprias
O sistema SHALL registrar, junto da identidade do conjunto, a procedência de cada
ruleset configurado como publicado por terceiros ou mantido neste repositório.

A distinção é metodológica, não organizacional. Um ruleset publicado por
terceiros não foi escrito olhando para a nossa população, e medir com ele não
levanta a objeção de ajuste ao conjunto de teste. Um ruleset mantido aqui pode
ter sido, e o texto da monografia precisa tratar os dois casos de forma
diferente.

#### Scenario: Ruleset do registry é marcado como de terceiros
- **WHEN** um ruleset é configurado por identificador do registry
- **THEN** a procedência registrada é de terceiros

#### Scenario: Ruleset local é marcado como próprio
- **WHEN** um ruleset é configurado por caminho dentro deste repositório
- **THEN** a procedência registrada é própria

#### Scenario: Procedência chega ao manifesto
- **WHEN** uma rodada termina
- **THEN** o manifesto registra cada ruleset usado e sua procedência
