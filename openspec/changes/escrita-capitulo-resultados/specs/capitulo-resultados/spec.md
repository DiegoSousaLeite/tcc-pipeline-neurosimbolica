## ADDED Requirements

### Requirement: Nenhuma edição é commitada sem pedido explícito
O sistema SHALL deixar toda edição de texto da monografia na árvore de trabalho,
sem criar \textit{commit}, até que o autor peça explicitamente o contrário. A
regra alcança `editaveis/*.tex`, `fixos/*`, `tcc.tex` e os documentos de
planejamento em `docs/`.

O texto da monografia está em revisão ativa e simultânea. Uma edição commitada
por engano é mais difícil de rastrear do que uma edição perdida: em 22/09/2026
uma reversão de `metodologia.tex` levou junto trabalho não commitado, e o
prejuízo foi refazer quinze minutos de edição. O prejuízo simétrico — um
\textit{commit} indevido no meio de uma revisão do autor — custaria mais.

#### Scenario: Edição concluída sem commit
- **WHEN** uma tarefa de redação desta change é concluída
- **THEN** o arquivo está alterado na árvore de trabalho e nenhum `commit` foi criado

#### Scenario: Pedido explícito libera o commit
- **WHEN** o autor pede para commitar um conjunto específico de arquivos
- **THEN** apenas os arquivos nomeados são incluídos

### Requirement: Toda pergunta declarada na metodologia tem seção no capítulo
O capítulo de resultados SHALL conter uma seção por pergunta declarada na Seção
de métricas da metodologia: a Questão Geral, Q1, Q2, Q3 e Q4. Cada seção SHALL
reportar as métricas que a metodologia associa àquela pergunta.

Hoje o rascunho cobre Q1, Q2 e Q3. A Questão Geral está diluída na Q2 e a Q4 não
existe. Um capítulo que não responde a uma pergunta que o próprio documento
declarou é a lacuna mais fácil de uma banca encontrar.

Quando uma pergunta não puder ser respondida, o capítulo SHALL declarar isso
explicitamente e dizer por quê, em vez de omitir a seção.

#### Scenario: Cada pergunta tem seção própria
- **WHEN** o capítulo é lido
- **THEN** existe seção identificável para a Questão Geral, Q1, Q2, Q3 e Q4

#### Scenario: Métrica declarada é reportada
- **WHEN** a metodologia associa uma métrica a uma pergunta
- **THEN** essa métrica aparece na seção correspondente, ou a sua ausência é justificada no texto

#### Scenario: Pergunta sem resposta é declarada, não omitida
- **WHEN** uma pergunta não pôde ser respondida pelos dados coletados
- **THEN** a seção existe e explica a razão, como ocorre com as categorias de concorrência da Q3

### Requirement: Todo número é acompanhado da ressalva que o limita
O capítulo SHALL apresentar, no mesmo parágrafo de cada número reportado, a
ressalva que delimita a sua validade — tamanho de amostra, denominador, ou
condição de medição.

É o padrão que o capítulo de Prova de Conceito já pratica, e é o que sustenta a
credibilidade do texto. Os números deste trabalho têm bases muito desiguais: o
lado negativo repousa em 827 alertas e é sólido; o lado positivo repousa em 19
casos, e a diferença entre 3 e 6 verdadeiros positivos são três casos.

#### Scenario: Número da classe positiva traz o tamanho da amostra
- **WHEN** um valor de Recall, F1 ou MCC do braço de filtro é reportado
- **THEN** o mesmo parágrafo informa que ele repousa em 19 casos vulneráveis

#### Scenario: Número de fonte externa traz a condição de medição
- **WHEN** um número de trabalho correlato é citado para comparação
- **THEN** o texto informa a linguagem, o corpus e o motor sobre os quais foi medido

### Requirement: Denominadores distintos nunca são apresentados como o mesmo
O capítulo SHALL explicitar o denominador de cada taxa de detecção reportada, e
NÃO SHALL apresentar taxas de denominadores diferentes como se fossem
comparáveis.

Duas taxas convivem no trabalho e medem coisas diferentes: 19/797 = 2,38 % sobre
a classe positiva inteira, e 18/690 = 2,61 % sobre a trilha de CWE alcançável.
As duas estão corretas. Trocá-las uma pela outra, ou citá-las lado a lado sem
qualificar, é erro fácil de cometer e impossível de defender.

#### Scenario: Taxa de detecção nomeia o denominador
- **WHEN** uma taxa de detecção do motor simbólico é reportada
- **THEN** o texto nomeia sobre qual conjunto ela foi calculada

#### Scenario: Comparação entre taxas qualifica a diferença
- **WHEN** duas taxas de denominadores diferentes aparecem no mesmo trecho
- **THEN** a diferença de denominador é declarada

### Requirement: O capítulo não contradiz os demais
O capítulo SHALL ser coerente com as afirmações de `metodologia.tex` e
`referencialteorico.tex`, e quando um achado contradisser o que esses capítulos
afirmam, o texto anterior SHALL ser corrigido em vez de o resultado ser suavizado.

O caso concreto que motiva este requisito: a metodologia afirma que o relatório
SARIF traz a trilha de fluxo de dados da origem ao sumidouro por modo de taint.
Medimos 0 de 807 alertas com trilha. A discussão dos resultados usa justamente a
ausência dessa trilha para explicar a distância para trabalhos correlatos. Sem
corrigir a metodologia, o documento afirma e nega a mesma coisa.

#### Scenario: Afirmação contrariada por medição é corrigida na origem
- **WHEN** um número do capítulo de resultados contradiz afirmação de capítulo anterior
- **THEN** o capítulo anterior é corrigido, e o resultado é reportado sem atenuação

#### Scenario: Ausência de trilha de taint é coerente entre capítulos
- **WHEN** a metodologia descreve a saída da Fase 1 e a discussão explica a distância para trabalhos correlatos
- **THEN** ambas afirmam que o motor simbólico empregado não produz trilha de fluxo de dados no corpus analisado

### Requirement: Figuras carregam o mecanismo, não apenas o número
O capítulo SHALL empregar figuras para os argumentos cujo mecanismo é difícil de
sustentar em prosa, e cada figura SHALL ser referenciada no corpo do texto.

Três argumentos deste capítulo dependem de desenho para serem compreendidos: o
destino dos casos na população, a diferença entre os dois braços de análise, e a
razão pela qual o arquivo apontado pelo gabarito frequentemente não contém a
operação perigosa. A distinção entre os braços, em particular, foi mal
compreendida mais de uma vez durante o próprio desenvolvimento.

As figuras SHALL seguir o idioma já empregado no documento: TikZ desenhado,
`\caption` antes do conteúdo, e `\fonteautores` ao final.

#### Scenario: Figura de funil precede os números da população
- **WHEN** o capítulo apresenta pela primeira vez a contagem de casos que chegam ao LLM
- **THEN** uma figura já mostrou o caminho dos casos da população até essa contagem

#### Scenario: Figura dos dois braços precede qualquer métrica de braço
- **WHEN** uma métrica é atribuída ao braço de filtro ou ao de triagem
- **THEN** a figura que distingue os dois já foi apresentada

#### Scenario: Toda figura é referenciada
- **WHEN** o capítulo é compilado
- **THEN** cada figura declarada é citada por `\ref` no corpo do texto

### Requirement: A comparação entre estudos declara a não comparabilidade
Quando o capítulo apresentar números de trabalhos correlatos ao lado dos seus, a
apresentação SHALL declarar que os valores não são diretamente comparáveis, e
nomear as dimensões em que diferem.

Linguagem, motor simbólico, natureza do corpus, insumo entregue ao modelo e
escala dos modelos diferem entre este trabalho e os correlatos. Apresentar os
números lado a lado sem essa declaração sugeriria uma competição que não existe:
os desenhos respondem a perguntas diferentes.

#### Scenario: Figura comparativa traz a declaração
- **WHEN** a figura que situa o Recall entre estudos é apresentada
- **THEN** a sua legenda declara que os valores não são comparáveis entre si e serve apenas para situar ordem de grandeza

#### Scenario: A diferença de unidade de rotulagem é explicada
- **WHEN** o capítulo compara o seu desempenho ao de trabalhos que rotulam alertas em vez de casos
- **THEN** o texto explica que a unidade de rotulagem difere e qual consequência isso tem para a métrica
