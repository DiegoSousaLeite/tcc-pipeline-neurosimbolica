## ADDED Requirements

### Requirement: Procedência do candidato é declarada
O sistema SHALL registrar, para cada caso que recebe veredito de LLM, como o
candidato foi montado: `alerta`, quando veio de um alerta emparelhado do
Semgrep, ou `gabarito`, quando veio da localização declarada no gabarito sem
exigir alerta.

Sem esse campo, um CSV do braço de triagem não sabe dizer quais vereditos
descrevem a capacidade do sistema implantado e quais descrevem a capacidade do
componente neural isolado. As duas afirmações são diferentes e a diferença é o
resultado que esta change existe para produzir; fundi-las num CSV que não
distingue as tornaria irrecuperáveis.

A procedência SHALL chegar ao CSV da rodada e às métricas, de forma que qualquer
número possa ser recalculado por procedência.

#### Scenario: Candidato de alerta é marcado
- **WHEN** um caso é `DETECTADO` e o candidato vem do alerta emparelhado
- **THEN** a procedência registrada é `alerta`

#### Scenario: Candidato de gabarito é marcado
- **WHEN** um caso vulnerável é `NAO_DETECTADO` e o braço de triagem monta o candidato a partir da localização do gabarito
- **THEN** a procedência registrada é `gabarito`

#### Scenario: Métricas recalculáveis por procedência
- **WHEN** as métricas de uma rodada de triagem são calculadas
- **THEN** elas podem ser produzidas para o conjunto completo e, separadamente, para cada procedência

### Requirement: Braço de triagem monta candidato a partir do gabarito
O sistema SHALL, quando o braço de triagem estiver selecionado, montar candidato
para os casos de gabarito vulnerável que terminaram em `NAO_DETECTADO`, usando a
localização do gabarito e a CWE da CVE, e SHALL submetê-los ao LLM.

A classe negativa NÃO SHALL ser afetada: negativo continua chegando ao LLM
somente por alerta emparelhado do Semgrep. Injetar negativos não faria sentido —
eles existem justamente porque o Semgrep os emitiu, e é o ruído do Semgrep que o
braço neural precisa filtrar.

O status `Status_Semgrep` do caso NÃO SHALL ser alterado. Um caso injetado
permanece `NAO_DETECTADO`: é verdade sobre o motor simbólico, e sobrescrevê-la
apagaria a medição de cobertura que a Rodada 3 produziu.

#### Scenario: Positivo não detectado chega ao LLM no braço de triagem
- **WHEN** o braço de triagem executa sobre um caso de gabarito vulnerável com status `NAO_DETECTADO`
- **THEN** um candidato é montado a partir do gabarito e o LLM emite veredito sobre ele

#### Scenario: Status simbólico preservado
- **WHEN** um caso injetado recebe veredito
- **THEN** `Status_Semgrep` continua registrando `NAO_DETECTADO` e o motivo da não-detecção permanece legível

#### Scenario: Negativo nunca é injetado
- **WHEN** um caso de gabarito seguro termina em `NAO_DETECTADO`
- **THEN** nenhum candidato é montado para ele, em qualquer braço

#### Scenario: Falha de esteira não vira candidato
- **WHEN** um caso vulnerável termina em categoria de erro de esteira
- **THEN** nenhum candidato é montado a partir do gabarito, porque não há garantia de que o arquivo-alvo foi resolvido

### Requirement: Candidato injetado é indistinguível do candidato de alerta
O sistema SHALL normalizar os dois caminhos de montagem para a mesma estrutura
antes da hidratação, de modo que o conteúdo entregue ao LLM não permita
identificar como o candidato foi montado.

Se o candidato injetado chegasse com forma distinguível — um campo a mais, uma
mensagem de formato diferente, ausência de identificador de regra —, o modelo
poderia condicionar o veredito na forma em vez do código. O experimento
mediria a pista, não o julgamento, e o resultado seria inválido sem que nada no
CSV denunciasse. O SastBench trata o mesmo risco removendo o campo de
procedência do que o agente recebe.

A procedência SHALL permanecer registrada no CSV, onde serve à análise, e NÃO
SHALL constar do prompt.

#### Scenario: Prompt não revela a procedência
- **WHEN** um candidato de cada procedência é montado para o mesmo arquivo e a mesma CWE
- **THEN** as duas strings de prompt são indistinguíveis quanto à procedência

#### Scenario: Campos ausentes são preenchidos, não omitidos
- **WHEN** o candidato de gabarito não tem identificador de regra, porque nenhuma regra disparou
- **THEN** o campo é preenchido com valor neutro de mesma forma, e não omitido da estrutura

#### Scenario: Procedência permanece no CSV
- **WHEN** a rodada termina
- **THEN** a procedência consta do CSV, ainda que não tenha constado de prompt algum

### Requirement: Grupo de controle de positivos detectados
O sistema SHALL incluir, no braço de triagem, os casos de gabarito vulnerável que
o Semgrep detectou, marcados com procedência `alerta`, e SHALL permitir comparar
o desempenho do LLM entre as duas procedências.

É a evidência de que a injeção não criou artefato. Se o LLM acertar
sistematicamente mais nos injetados do que nos detectados, a diferença não vem
do código — vem de alguma propriedade da montagem, e o número do braço de
triagem não pode ser reportado como está.

A comparação SHALL ser reportada junto do resultado, e não apenas ficar
disponível. Um controle que ninguém olha não controla nada.

#### Scenario: Os dois grupos convivem no mesmo braço
- **WHEN** o braço de triagem executa
- **THEN** os casos vulneráveis detectados e os injetados recebem veredito na mesma execução, sob o mesmo prompt e o mesmo modelo

#### Scenario: Comparação entre procedências é reportada
- **WHEN** as métricas da rodada de triagem são emitidas
- **THEN** o acerto do LLM aparece discriminado por procedência, lado a lado

#### Scenario: Controle pequeno é declarado como tal
- **WHEN** o grupo de procedência `alerta` tem menos casos que o limiar de poder estatístico
- **THEN** a comparação é emitida acompanhada do aviso de poder limitado, em vez de apresentada como conclusiva

### Requirement: Braço de filtro preservado e executável
O sistema SHALL manter o braço de filtro como comportamento padrão e SHALL
permitir executá-lo sem que nenhum candidato de gabarito seja montado.

O braço de filtro é o único que descreve o sistema como seria implantado, e é o
que responde à Q1 com a comparação pareada intacta. As Rodadas 1–3 são rodadas
desse braço; se ele deixasse de ser executável, elas deixariam de ser
reproduzíveis.

#### Scenario: Invocação padrão não injeta
- **WHEN** a pipeline é executada sem selecionar o braço de triagem
- **THEN** nenhum candidato de gabarito é montado e o conjunto de casos que chega ao LLM é o mesmo de antes desta change

#### Scenario: Reprodução de rodada anterior
- **WHEN** uma rodada do braço de filtro é reexecutada sobre a mesma população e o mesmo cache
- **THEN** o conjunto de `ID_Caso` que recebe veredito é idêntico ao da rodada correspondente anterior a esta change

### Requirement: Registro no mapa do LaTeX do que a mudança de desenho obriga a reescrever
O sistema SHALL registrar em `docs/MAPA-TCC-O-QUE-REESCREVER.md`, como parte
desta change, o que a existência do braço de triagem obriga a alterar na
monografia. O registro SHALL cobrir, no mínimo:

- que a descrição da arquitetura deixa de ser "o LLM é filtro puro do Semgrep" e
  passa a descrever dois braços com o mesmo componente neural e formas
  diferentes de montar o candidato;
- que os números do braço de triagem NÃO SHALL ser apresentados como desempenho
  do sistema em operação, porque num uso real os positivos não seriam injetados;
- que a distância entre os dois braços é a medida do teto de filtro puro, já
  anunciado sem quantificação no roteiro da apresentação;
- a ameaça à validade correspondente: os positivos injetados e os alertas do
  Semgrep podem diferir sistematicamente na natureza da localização apontada,
  e o grupo de controle é o que responde a isso.

A edição dos arquivos `.tex` NÃO SHALL fazer parte desta change. O mapa é o
documento de acumulação; a redação da monografia acontece em branch separada,
pela decisão vigente de não mexer no `.tex` antes de fechar o experimento. Esta
change escreve no mapa, e a branch do LaTeX o consome.

#### Scenario: Mapa atualizado antes do encerramento da change
- **WHEN** as tarefas de implementação terminam
- **THEN** `docs/MAPA-TCC-O-QUE-REESCREVER.md` contém a entrada sobre a mudança de desenho, com os quatro pontos acima

#### Scenario: Nenhum arquivo .tex é tocado
- **WHEN** a change é implementada por completo
- **THEN** nenhum arquivo `.tex` foi criado, alterado ou removido

#### Scenario: A entrada nomeia a branch separada
- **WHEN** a entrada é escrita no mapa
- **THEN** ela declara explicitamente que a redação correspondente acontece em branch própria, e não nesta
