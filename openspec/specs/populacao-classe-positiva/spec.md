# populacao-classe-positiva

## Purpose

Definir a composição da população quanto ao eixo vulnerável: o que entra, o que
permanece como evidência de ponto cego, e como a procedência de cada caso se
mantém rastreável.

Existe porque a classe positiva passou a vir de duas origens com propósitos
distintos. A colheita filtrada por alcançabilidade
(`colheita-cwe-alcancavel`) produz casos
que o motor simbólico pode ao menos procurar; os pools anteriores contêm casos
cuja CWE nenhuma regra declara. Os dois conjuntos precisam coexistir na mesma
população: os primeiros porque são o que torna o recall interpretável, os
segundos porque são a evidência de que 70,1% das fraquezas do corpus estão fora
do alcance da análise sintática — número que a monografia usa no capítulo de
limitações.

Manter os dois sem distinguir a procedência de cada caso tornaria a avaliação do
filtro impossível: um ganho de amostra poderia vir apenas do reaproveitamento de
pares antigos, com a colheita nova tendo rendido nada.

## Requirements

### Requirement: Trilha própria para os casos de CWE alcançável
O sistema SHALL carregar os pares produzidos pela colheita filtrada como uma trilha própria, identificada por rótulo de origem distinto das trilhas existentes, sem substituir nenhuma delas.

Trilha própria, e não substituição do pool da `TP_prata`, porque sobrescrever destruiria os pares inalcançáveis que sustentam o achado dos 70,1%, e porque `tp_pairs.json` é irrecuperável — só `scripts/tp_reconstruct.py` o regenera, e ele exige o histórico git completo dos repositórios, que não está mais em disco.

#### Scenario: Casos da trilha nova entram na população
- **WHEN** o pool da colheita filtrada existe e a pipeline monta a população
- **THEN** os casos dele aparecem com o rótulo de origem próprio da trilha nova

#### Scenario: Pool ausente não quebra a montagem
- **WHEN** o pool da colheita filtrada ainda não existe
- **THEN** a trilha fica vazia e a população é montada normalmente com as demais

#### Scenario: Trilhas existentes preservadas
- **WHEN** a população é montada com a trilha nova ativa
- **THEN** `FP`, `TP_ouro`, `TP_prata` e `TP_dataset` continuam presentes, com os mesmos casos que produziam antes

#### Scenario: Seleção por trilha continua funcionando
- **WHEN** a pipeline é executada restringindo a uma única trilha
- **THEN** a trilha nova pode ser selecionada isoladamente, como as demais

### Requirement: Rastreabilidade da procedência de cada caso vulnerável
O sistema SHALL permitir distinguir, na população e nos resultados, os casos vulneráveis vindos da colheita filtrada daqueles vindos das trilhas anteriores.

Sem essa distinção não é possível avaliar se o filtro de alcançabilidade funcionou: um ganho de amostra poderia vir apenas do reaproveitamento de pares antigos, com a colheita nova tendo rendido nada.

A coluna `Origem` do CSV de auditoria já carrega o rótulo da trilha, então a rastreabilidade decorre do rótulo próprio, sem estrutura nova.

#### Scenario: Procedência visível no CSV
- **WHEN** um caso da trilha nova é registrado no CSV de resultados
- **THEN** a coluna `Origem` traz o rótulo da trilha nova

#### Scenario: Contagem por procedência
- **WHEN** os resultados de uma rodada são analisados
- **THEN** é possível contar quantos casos vulneráveis vieram de cada trilha

### Requirement: Casos de CWE inalcançável preservados como evidência
O sistema SHALL manter na população os casos de gabarito vulnerável cuja CWE não é alcançável pelo motor simbólico. Eles SHALL continuar entrando na matriz de cobertura como ponto cego, com o motivo de não-detecção registrado.

Removê-los apagaria o achado que motiva estas mudanças — que 70,1% das fraquezas do corpus estão fora do alcance da análise sintática, predominantemente as semânticas (controle de acesso, autorização ausente, spoofing de autenticação). Esse número é resultado do trabalho.

Eles não distorcem a matriz de acerto do LLM porque nunca chegam a ela: sem emparelhamento na Fase 1, não há chamada de LLM.

#### Scenario: Caso inalcançável continua na cobertura
- **WHEN** um caso vulnerável de CWE sem regra é processado
- **THEN** ele aparece na matriz de cobertura como ponto cego simbólico, com o motivo de não-detecção registrado

#### Scenario: Caso inalcançável fica fora da matriz de acerto
- **WHEN** o mesmo caso é considerado na matriz de acerto do LLM
- **THEN** ele não aparece, porque nenhum alerta foi emparelhado e nenhum veredito foi emitido

#### Scenario: Proporção de inalcançáveis permanece calculável
- **WHEN** a população é analisada
- **THEN** é possível contar quantos casos vulneráveis têm CWE fora do alcance do motor, preservando a comparação com as rodadas anteriores

### Requirement: Classe negativa preservada
O sistema SHALL manter a classe negativa inalterada: os casos de falso positivo derivados do SastBench continuam os mesmos, com os mesmos identificadores, sem renumeração.

Alterar as duas classes ao mesmo tempo impediria atribuir qualquer movimento das métricas à mudança da classe positiva, que é o objeto do experimento. Além disso, o índice no identificador do caso vem da posição original na lista de locations, antes de qualquer filtro — renumerar quebraria os CSVs já gerados e o checkpoint entre rodadas.

#### Scenario: Identificadores da classe negativa estáveis
- **WHEN** a população nova é construída
- **THEN** os casos de origem `FP` têm exatamente os mesmos identificadores que tinham antes

#### Scenario: Nenhum identificador colide entre trilhas
- **WHEN** a população inteira é montada com a trilha nova
- **THEN** não há identificador de caso repetido

#### Scenario: Cache simbólico da classe negativa reaproveitado
- **WHEN** uma rodada executa sobre a população nova
- **THEN** os casos da classe negativa são servidos do cache simbólico sem nova varredura do Semgrep, desde que ruleset e versão de pareamento não tenham mudado
