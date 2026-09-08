# colheita-cwe-alcancavel

## Purpose

Selecionar candidatas a verdadeiro positivo restritas às CWEs que o motor simbólico cobre, com relatório de recusa e reaproveitamento dos pares já colhidos.

Existe porque colher sem essa restrição produz população indetectável por construção: 70,1% dos 107 casos vulneráveis da rodada `20260731T140000Z-af9bc32` têm CWE que nenhuma regra Go do `p/default` declara (`docs/ANALISE-RODADA-2.md` §3.1, que mede o mesmo pelo lado do resultado — recall de 0,0093 sobre a CWE rotulada). O motor não pode falhar em achar o que não sabe procurar, e o recall medido sobre essa população mede a lacuna do catálogo de regras, não a capacidade do motor.

A causa é viés de seleção em relação ao instrumento medido. As duas classes foram montadas por caminhos opostos: a segura veio de achados do Semgrep (SastBench), então sua CWE é a CWE de alguma regra por construção — 95,8% dela é alcançável; a positiva veio de CVEs via OSV, sem nunca consultar o ruleset — 29,9% alcançável.

Alcançável não é o mesmo que detectável: a regra existir não garante que dispare naquele código, porque ela procura um padrão sintático específico. A restrição remove o que é impossível por construção, não o que é difícil.

## Requirements

### Requirement: Colheita restrita às CWEs alcançáveis pelo motor
O sistema SHALL aceitar como candidata a verdadeiro positivo apenas a vulnerabilidade cuja CWE seja alcançável pelo motor simbólico na linguagem analisada. Candidata cuja CWE não é coberta por regra alguma SHALL ser recusada na colheita.

A restrição existe porque colher sem ela produz população indetectável por construção: 70,1% dos casos vulneráveis da rodada `20260731T140000Z-af9bc32` têm CWE que nenhuma regra Go do `p/default` declara. Sem a restrição, a métrica de recall mede a lacuna do catálogo de regras, não a capacidade do motor.

#### Scenario: CWE alcançável é aceita
- **WHEN** a colheita avalia uma vulnerabilidade cuja CWE é alcançável na linguagem analisada
- **THEN** ela entra no conjunto de candidatas

#### Scenario: CWE inalcançável é recusada
- **WHEN** a colheita avalia uma vulnerabilidade cuja CWE não é alcançável
- **THEN** ela é recusada, e a recusa é contabilizada sob a CWE que a causou

#### Scenario: Demais filtros continuam valendo
- **WHEN** uma candidata tem CWE alcançável mas não tem commit de fix ou não está no GitHub
- **THEN** ela continua sendo recusada pelos filtros que já existiam, sem alteração de comportamento

### Requirement: Todas as CWEs declaradas são consideradas
O sistema SHALL avaliar todas as CWEs declaradas pela vulnerabilidade, e não apenas a primeira. A candidata SHALL ser aceita se qualquer uma delas for alcançável, e a CWE registrada SHALL ser a que casou.

A extração ficava com o primeiro elemento de `database_specific.cwe_ids`. A ordem dessa lista é arbitrária, então uma candidata legítima pode ser recusada só porque a CWE alcançável não era a primeira. E registrar a CWE errada faria a Fase 1 procurar por uma fraqueza que não é a que o motor cobre.

#### Scenario: Segunda CWE alcançável faz a candidata ser aceita
- **WHEN** a vulnerabilidade declara `["CWE-284", "CWE-338"]`, com apenas a segunda alcançável
- **THEN** a candidata é aceita e a CWE registrada é `CWE-338`

#### Scenario: Nenhuma CWE alcançável faz a candidata ser recusada
- **WHEN** a vulnerabilidade declara várias CWEs e nenhuma é alcançável
- **THEN** a candidata é recusada

#### Scenario: Vulnerabilidade sem CWE declarada
- **WHEN** a vulnerabilidade não declara CWE alguma
- **THEN** ela é recusada, porque não há como afirmar que o motor a alcança

### Requirement: Relatório da colheita
O sistema SHALL reportar, ao fim da colheita, a distribuição de CWEs das candidatas aceitas, a contagem de recusadas por inalcançabilidade discriminada por CWE, e a data de obtenção do snapshot do ruleset usado no filtro.

O relatório existe para que a decisão de prosseguir para a reconstrução de pares — cara em rede e em tempo — seja tomada com número na mão. A discriminação por CWE é o que distingue "a OSV tem pouca coisa nessas fraquezas" de "o filtro está recusando tudo por defeito".

A data do snapshot entra porque o filtro consulta o registry enquanto a pipeline executa o Semgrep instalado, e os dois podem divergir.

#### Scenario: Distribuição das aceitas é reportada
- **WHEN** a colheita termina
- **THEN** a saída lista quantas candidatas foram aceitas por CWE

#### Scenario: Recusas são discriminadas por CWE
- **WHEN** a colheita termina
- **THEN** a saída informa quantas candidatas foram recusadas por inalcançabilidade, por CWE

#### Scenario: Data do snapshot é reportada
- **WHEN** a colheita termina
- **THEN** a saída informa quando o ruleset usado no filtro foi obtido

#### Scenario: Colheita vazia é explícita
- **WHEN** nenhuma candidata sobrevive ao filtro
- **THEN** a saída diz isso claramente, em vez de gravar um arquivo vazio em silêncio

### Requirement: Saída sem destruição dos pools existentes
O sistema SHALL gravar o resultado da colheita em arquivo próprio, sem sobrescrever os pools de pares já colhidos.

`tp_pairs.json` é irrecuperável: apenas `scripts/tp_reconstruct.py` o regenera, e ele exige o histórico git completo dos repositórios, que não está mais em disco. Os pares inalcançáveis de `tp_pairs_osv.json` são a evidência do achado dos 70% e não devem ser apagados.

#### Scenario: Pools de origem intactos
- **WHEN** a colheita é executada
- **THEN** `tp_pairs.json` e `tp_pairs_osv.json` permanecem inalterados em disco

### Requirement: Identificação dos pares já alcançáveis
O sistema SHALL permitir identificar, entre os pares de verdadeiro positivo já colhidos, aqueles cuja CWE é alcançável, para que entrem na população sem recolheita.

Há 17 pares nessa condição nos pools atuais — 4 em `tp_pairs.json` e 13 em `tp_pairs_osv.json`. Descartá-los e recolher do zero gastaria rede para reobter o que já está em disco.

#### Scenario: Pares alcançáveis são listados
- **WHEN** os pools existentes são avaliados contra o conjunto de CWEs alcançáveis
- **THEN** os pares alcançáveis são listados, com a CWE que os torna alcançáveis

#### Scenario: Identificação não escreve nos pools
- **WHEN** a identificação é executada
- **THEN** nenhum pool de origem é modificado
