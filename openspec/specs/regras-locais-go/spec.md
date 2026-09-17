# regras-locais-go

## Purpose

Manter, neste repositório, um ruleset próprio para fraquezas que nenhum ruleset
público alcança em Go — e cercá-lo do protocolo que torna o número dele
defensável.

Regra escrita por quem mede levanta uma objeção que regra de terceiros não
levanta: ela pode ter sido escrita olhando os casos em que vai ser medida, e o
número resultante mediria a capacidade de descrever arquivos já vistos, não a
capacidade da análise sintática. A separação entre o que informa a escrita e o
que sustenta a medida precisa ser **estrutural, não disciplinar** — a esteira
tem que impedir, não bastando pretender não olhar.

Em troca, é o único ruleset do projeto imune à deriva do lado do servidor:
muda apenas por commit, e o manifesto permite dizer, meses depois, exatamente
quais regras produziram cada número.

## Requirements

### Requirement: Partição fixada antes de qualquer regra ser escrita
O sistema SHALL particionar os casos de cada CWE alvo em partição de
desenvolvimento e partição de avaliação, de forma determinística a partir do
identificador do caso, e SHALL gravar a partição em disco **antes** de a primeira
regra ser escrita.

A ordem não é burocracia. Uma partição derivada depois que as regras existem pode
ser escolhida, conscientemente ou não, para favorecer o número — e nada no
artefato final denunciaria. Gravar antes torna a separação verificável por
qualquer pessoa que leia o histórico do repositório: o commit da partição precede
o commit da primeira regra.

A partição SHALL ser derivada do identificador do caso, e NÃO de sorteio com
semente arbitrária. O identificador já é único e estável na população; derivar
dele torna a partição reproduzível por quem tiver a população, sem precisar
confiar numa semente que só nós temos.

A partição SHALL ser estratificada por CWE, de modo que cada CWE alvo tenha
casos nas duas partições. Uma CWE inteira de um lado só tornaria o número da
avaliação inútil para ela.

#### Scenario: Partição precede a primeira regra
- **WHEN** o histórico do repositório é inspecionado
- **THEN** o commit que grava a partição é anterior ao commit que introduz a primeira regra local

#### Scenario: Partição é determinística
- **WHEN** a partição é derivada duas vezes sobre a mesma população
- **THEN** o resultado é idêntico

#### Scenario: Partição é estratificada por CWE
- **WHEN** a partição é derivada para um conjunto de CWEs alvo
- **THEN** cada CWE alvo tem ao menos um caso em cada partição

#### Scenario: Repartição é recusada
- **WHEN** a partição já existe em disco e é pedida novamente sobre a mesma população
- **THEN** a operação falha com erro explícito, em vez de sobrescrever — reparticionar depois de escrever regra anula a separação

### Requirement: Proveniência declarada por regra
O sistema SHALL exigir que cada regra local declare, em seus metadados, sob qual
protocolo foi escrita:

- `definicao`: derivada da definição da CWE e do idioma de Go, sem que nenhum
  caso da população tenha sido inspecionado;
- `desenvolvimento`: derivada da inspeção da partição de desenvolvimento.

Regra sem proveniência declarada NÃO SHALL ser carregada.

Os dois protocolos produzem números com força diferente. Uma regra `definicao`
pode ser medida sobre a população inteira, porque nenhum caso a informou. Uma
regra `desenvolvimento` só pode ser medida sobre a partição de avaliação. Sem o
selo, o relatório não tem como aplicar a regra certa a cada uma, e o caminho de
menor resistência seria reportar tudo junto.

#### Scenario: Regra sem proveniência não carrega
- **WHEN** uma regra local não declara proveniência
- **THEN** o carregamento falha com erro explícito nomeando a regra

#### Scenario: Proveniência desconhecida não carrega
- **WHEN** uma regra declara proveniência com vocabulário fora do definido
- **THEN** o carregamento falha, em vez de tratar como um dos valores válidos

#### Scenario: Proveniência chega ao manifesto
- **WHEN** uma rodada usa o ruleset local
- **THEN** o manifesto registra cada regra local usada e sua proveniência

### Requirement: Relatório separa as partições e recusa fundi-las
O sistema SHALL emitir a detecção das regras locais discriminada por partição, e
NÃO SHALL emitir um número único de detecção sobre a população inteira quando
houver qualquer regra de proveniência `desenvolvimento` carregada.

O número da partição de desenvolvimento é diagnóstico interno: diz se a regra
faz o que se pretendia. O número da partição de avaliação é o resultado. Emitir
a soma dos dois produziria exatamente a estatística que não se pode defender, e
a experiência com métricas é que o número mais fácil de citar é o que acaba no
texto.

O relatório SHALL nomear, junto de cada número, a partição e o protocolo que o
sustentam, de modo que copiar o número sem a ressalva seja desconfortável.

#### Scenario: Números emitidos por partição
- **WHEN** a detecção das regras locais é medida
- **THEN** a saída traz um número para a partição de desenvolvimento e outro para a de avaliação, rotulados

#### Scenario: Número agregado é recusado
- **WHEN** há regra de proveniência `desenvolvimento` carregada e um número sobre a população inteira é pedido
- **THEN** a operação falha com mensagem explicando que o agregado não é reportável

#### Scenario: Ruleset só de regras derivadas da definição permite agregado
- **WHEN** todas as regras locais carregadas têm proveniência `definicao`
- **THEN** o número sobre a população inteira é emitido, porque nenhum caso informou a escrita das regras

#### Scenario: Cada número carrega a sua ressalva
- **WHEN** um número de detecção de regra local é emitido
- **THEN** a partição e o protocolo constam da mesma linha do relatório

### Requirement: Metadados obrigatórios das regras locais
O sistema SHALL exigir que cada regra local declare `metadata.cwe` num formato
aceito pelo casamento por identificador completo, e `metadata.subcategory`
declarando se a regra afirma detectar vulnerabilidade ou apenas sinalizar
auditoria.

Sem `metadata.cwe` no formato certo, a regra dispara e o alerta não é emparelhado
ao caso — a Fase 1 registra `ALERTA_OUTRA_CWE` e o esforço se perde de um jeito
particularmente difícil de diagnosticar, porque a regra *funcionou*.

Sem `metadata.subcategory`, a regra é tratada como auditoria pelo grau de
alcançabilidade, e a CWE não sobe de grau ainda que a detecção melhore.

#### Scenario: Regra sem metadata.cwe não carrega
- **WHEN** uma regra local não declara `metadata.cwe`
- **THEN** o carregamento falha com erro explícito nomeando a regra

#### Scenario: CWE em formato não casável não carrega
- **WHEN** `metadata.cwe` de uma regra local não é aceito pela comparação por identificador completo já vigente
- **THEN** o carregamento falha, em vez de a regra disparar sem emparelhar

#### Scenario: Subcategoria ausente não carrega
- **WHEN** uma regra local não declara `metadata.subcategory`
- **THEN** o carregamento falha — o padrão conservador de tratar ausência como auditoria vale para ruleset de terceiros, sobre o qual não temos controle, e não para regra nossa

### Requirement: Ruleset local é versionado e congelado por construção
O sistema SHALL manter as regras locais como arquivos versionados neste
repositório, carregados por caminho local, e SHALL registrar no manifesto o
commit que as define.

É o único ruleset do projeto imune à ameaça de mudança do lado do servidor.
Qualquer ruleset do registry — o `p/default` inclusive — pode mudar sem que nada
no código perceba; o ruleset local muda apenas por commit, e o manifesto permite dizer, meses depois,
exatamente quais regras produziram cada número.

#### Scenario: Regras carregadas por caminho local
- **WHEN** o ruleset local é configurado
- **THEN** ele é carregado do diretório do repositório, sem busca no registry

#### Scenario: Commit das regras no manifesto
- **WHEN** uma rodada usa o ruleset local
- **THEN** o manifesto registra o commit corrente do repositório

#### Scenario: Ruleset local funciona offline
- **WHEN** o ruleset local é configurado e não há rede
- **THEN** a execução prossegue normalmente
