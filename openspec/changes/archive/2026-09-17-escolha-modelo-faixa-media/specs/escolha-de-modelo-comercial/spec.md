## ADDED Requirements

### Requirement: Preço vem de fonte primária, com data
O levantamento SHALL registrar, para cada modelo considerado, o preço por milhão
de tokens de entrada e de saída **obtido da página de preços do próprio
fornecedor**, junto da **data da consulta** e do endereço consultado.

Preço de modelo muda, e preço lembrado de memória envelhece sem avisar. A tabela
que o projeto já carrega foi consultada em 2026-07-29 e é a prova do problema:
ela continua sendo usada em cálculo meses depois sem que nada sinalize a idade.
Um número de custo que vai para a monografia e para a decisão de gastar precisa
poder ser reconferido na fonte.

O levantamento NÃO SHALL registrar preço cuja fonte não pôde ser verificada. Um
modelo cujo preço não se confirmou entra na tabela com a célula marcada como não
verificada, e não com um valor plausível.

#### Scenario: Preço verificado é registrado com procedência
- **WHEN** o preço de um modelo é obtido da página do fornecedor
- **THEN** a tabela registra o valor, a data da consulta e o endereço

#### Scenario: Preço não verificável é declarado como tal
- **WHEN** o preço de um modelo não pôde ser confirmado na fonte primária
- **THEN** a célula é marcada como não verificada, e nenhum valor é estimado no lugar

### Requirement: Custo calculado sobre tokens medidos
O levantamento SHALL calcular o custo por rodada usando as **contagens de tokens
efetivamente medidas** nesta pipeline — 3.198.141 de entrada e 315.469 de saída
para uma rodada de dois braços sobre a população completa — e SHALL declarar de
qual rodada esses números vieram.

Estimativa de token erra, e erra para menos: a primeira estimativa deste projeto
usou 817 tokens de entrada por chamada, contra 1.009 medidos, porque as funções
longas dos candidatos injetados não estavam no cálculo. O custo divulgado saiu
18 % abaixo do real.

O levantamento SHALL apresentar o custo em pelo menos duas escalas: uma rodada
de dois braços e a matriz completa, para que a decisão não seja tomada sobre o
número menor.

#### Scenario: Custo por rodada sai dos tokens reais
- **WHEN** o custo de um modelo é calculado
- **THEN** ele usa as contagens medidas na pipeline, e o documento diz de qual rodada elas vieram

#### Scenario: Custo é apresentado em mais de uma escala
- **WHEN** a tabela de custo é montada
- **THEN** ela traz o custo de uma rodada de dois braços e o da matriz completa

### Requirement: Custo de integração é parte da comparação
O levantamento SHALL registrar, para cada modelo, **o que ele exige da camada
`src/provedores/`** — se fala o protocolo de um provedor já implementado, se
exige provedor novo, e o que isso significa de trabalho.

Comparar modelos só por preço de token esconde a parte cara. Um modelo US$ 2 mais
barato que exija um provedor novo, com tratamento de erro, contagem de tokens,
truncamento de contexto e testes, é mais caro que o concorrente — e o projeto já
tem um contrato de provedor definido, então a pergunta é objetiva e respondível
lendo o código.

#### Scenario: Modelo compatível com provedor existente é identificado
- **WHEN** um modelo fala o protocolo de um provedor já implementado
- **THEN** o levantamento registra qual provedor, e que a integração é de configuração

#### Scenario: Modelo que exige provedor novo é identificado
- **WHEN** um modelo não é atendido por provedor algum já implementado
- **THEN** o levantamento registra o que precisaria ser escrito, e trata isso como custo da opção

### Requirement: Limite de taxa e o tempo de parede que ele impõe
O levantamento SHALL registrar o limite de requisições do modelo no nível de
acesso considerado, e SHALL traduzi-lo em **tempo de parede estimado para uma
rodada**, respeitando o intervalo mínimo entre chamadas que a pipeline já impõe.

Custo não é o gargalo deste projeto; vazão é. O tier grátis do Gemini permite 20
requisições por dia, o que torna 3.210 chamadas impossíveis por um motivo que
não tem nada a ver com dinheiro. Um modelo barato que leve uma semana de parede
é pior que um caro que feche numa noite, e a tabela precisa deixar isso visível.

#### Scenario: Limite de taxa vira estimativa de parede
- **WHEN** um modelo é avaliado
- **THEN** o documento registra o limite de requisições e o tempo de parede estimado para uma rodada

### Requirement: Recomendação com critério explícito e recusas registradas
O levantamento SHALL terminar em **uma recomendação**, com o critério que a
produziu declarado, e SHALL registrar as alternativas consideradas e **o motivo
de cada recusa**.

Um levantamento que lista opções e não escolhe empurra a decisão de volta sem
ter reduzido nada. E uma escolha sem as recusas registradas não é auditável:
meses depois, ninguém sabe se a opção B foi descartada por um motivo ou por
esquecimento — que é exatamente o problema que este projeto já teve com decisões
tomadas e depois revogadas sem rastro.

A recomendação SHALL declarar explicitamente se o modelo escolhido é capaz o
bastante para **falsificar** a conclusão atual. Um modelo na mesma banda dos que
já rodaram produziria confirmação fraca, e isso precisa ser dito antes de gastar.

#### Scenario: Documento termina em uma escolha
- **WHEN** o levantamento é concluído
- **THEN** ele nomeia um modelo recomendado e o critério que o selecionou

#### Scenario: Cada alternativa recusada tem motivo
- **WHEN** um modelo considerado não é o recomendado
- **THEN** o documento registra por que ele foi recusado

#### Scenario: O poder de falsificação é declarado
- **WHEN** a recomendação é escrita
- **THEN** ela diz se o modelo escolhido é capaz o bastante para derrubar a conclusão atual, ou se apenas a confirmaria

### Requirement: Nenhuma cota é gasta e nenhum provedor é implementado
O levantamento NÃO SHALL fazer chamada de API a fornecedor algum, NÃO SHALL
implementar provedor em `src/provedores/`, NÃO SHALL alterar a tabela de preços
do projeto e NÃO SHALL assumir que existe billing, chave ou conta ativa.

A separação é deliberada: decidir qual modelo usar e gastar dinheiro com ele são
decisões diferentes, tomadas por pessoas diferentes em momentos diferentes.
Misturá-las faria a investigação carregar um compromisso que ela não deveria
tomar sozinha.

Alterar a tabela de preços sem rodada seria ruído: ela é lida no manifesto de
cada execução, e mexer nela sem execução alguma sujaria a rastreabilidade que
ela existe para dar.

#### Scenario: Nenhuma chamada de API é feita
- **WHEN** a change é implementada por completo
- **THEN** nenhuma requisição foi feita a fornecedor de LLM, e nenhuma cota foi consumida

#### Scenario: A camada de provedores não é tocada
- **WHEN** a change é implementada por completo
- **THEN** `src/provedores/` e a tabela de preços do projeto estão inalteradas

#### Scenario: Acesso não é pressuposto
- **WHEN** um modelo é avaliado
- **THEN** o documento registra o que seria preciso ativar para usá-lo, em vez de supor que já está ativo

### Requirement: Registro de que a matriz comercial nunca foi executada
O levantamento SHALL registrar em `docs/MAPA-TCC-O-QUE-REESCREVER.md` que
**nenhuma rodada comercial foi executada** neste trabalho, e que todas as
medições publicáveis vêm de modelos locais.

É limitação do trabalho independentemente do que se decida rodar depois, e hoje
não está declarada em lugar nenhum. A `matriz-experimental` descreve o par
comercial como a matriz de referência do experimento, o que induz a leitura de
que ela foi usada.

O registro SHALL nomear o que existe de fato: 17 vereditos comerciais de um
piloto, mais 5 erros de API, contra dezenas de milhares de vereditos locais.

#### Scenario: A limitação vai para o mapa do LaTeX
- **WHEN** o levantamento é concluído
- **THEN** o mapa registra que a matriz comercial nunca foi executada e quantos vereditos comerciais existem de fato
