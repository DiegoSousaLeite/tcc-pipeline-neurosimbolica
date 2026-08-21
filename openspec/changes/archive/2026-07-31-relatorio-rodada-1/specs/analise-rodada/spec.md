## ADDED Requirements

### Requirement: Relatório de análise vinculado a uma rodada
O projeto SHALL manter um relatório de análise em markdown, versionado no
repositório, que analisa uma rodada completa identificada pelo seu `run_id`, e
que declara no cabeçalho a configuração exata daquela rodada: modelo,
quantização, `num_ctx`, semente, versão do Semgrep, ruleset, hash do catálogo
de CWE e versões dos prompts.

O relatório é documento de leitura humana, endereçado aos autores e à banca,
não saída de máquina. Ele existe porque as métricas cruas da rodada induzem
leitura errada quando lidas sem a base amostral que as sustenta.

#### Scenario: Rodada identificada sem ambiguidade
- **WHEN** um leitor abre o relatório
- **THEN** o `run_id` analisado aparece no cabeçalho e coincide com um
  diretório existente sob `results/`

#### Scenario: Configuração declarada bate com o manifesto
- **WHEN** o cabeçalho do relatório é confrontado com
  `results/<run_id>/manifesto.json`
- **THEN** modelo, versão do Semgrep, ruleset, hash do catálogo e versões dos
  prompts são os mesmos

#### Scenario: Relatório não depende de artefato ausente
- **WHEN** o relatório é lido num clone que tem `results/`, `data/`,
  `tp_pairs.json` e `tp_pairs_osv.json`, mas não tem os repositórios clonados
- **THEN** todos os comandos de reprodução citados nele executam sem erro

### Requirement: Rastreabilidade de cada número citado
O relatório SHALL acompanhar cada valor numérico que apresenta do comando ou
script que o reproduz a partir de artefatos versionados, e SHALL não conter
número derivado de inspeção manual não reproduzível.

#### Scenario: Número de tabela tem comando
- **WHEN** uma tabela do relatório apresenta contagens ou métricas
- **THEN** a tabela é precedida ou seguida do comando exato que a regenera

#### Scenario: Comando citado produz o valor citado
- **WHEN** qualquer comando de reprodução do relatório é executado sobre o
  `run_id` declarado
- **THEN** sua saída contém o valor que o relatório afirma

#### Scenario: Contagem sem comando é rejeitada
- **WHEN** um número aparece no texto sem comando associado nem referência a
  outra seção que o reproduz
- **THEN** isso conta como defeito do relatório, a ser corrigido antes de
  fechar a mudança

### Requirement: Ferramenta somente-leitura de números derivados
O sistema SHALL oferecer um script que imprime, a partir dos CSVs de uma
rodada e dos artefatos de dados, os números derivados que `src/metricas.py`
não produz: degraus do funil de recall, relações de conjunto entre braços,
distribuição dos casos `NAO_DETECTADO` por CWE e por trilha de origem, taxa de
ERROR por braço e estatísticas de tokens.

O script SHALL ser somente-leitura: não escreve, move nem regenera nenhum
artefato de dados, e não faz chamada a LLM nem à rede.

#### Scenario: Execução sobre uma rodada
- **WHEN** o script é invocado com o diretório de uma rodada como argumento
- **THEN** ele imprime todas as seções de números derivados e termina com
  código de saída 0

#### Scenario: Nenhum artefato é alterado
- **WHEN** o script é executado com a árvore de trabalho limpa
- **THEN** `git status --porcelain` continua sem apontar modificação em
  `results/`, `data/`, `tp_pairs.json` ou `tp_pairs_osv.json`

#### Scenario: Execução offline
- **WHEN** o script é executado sem acesso à rede
- **THEN** ele conclui normalmente, porque toda a entrada já está em disco

#### Scenario: Determinismo
- **WHEN** o script é executado duas vezes sobre a mesma rodada
- **THEN** a saída é idêntica nas duas execuções

#### Scenario: Rodada inexistente falha alto
- **WHEN** o script recebe um diretório que não contém CSVs de rodada
- **THEN** ele encerra com mensagem explícita, em vez de imprimir tabelas
  vazias

### Requirement: Delimitação do que a rodada mede
O relatório SHALL declarar separadamente a base amostral da classe negativa e
a da classe positiva, e SHALL concluir explicitamente, a partir desses
números, sobre a tese de que a rodada mede supressão de ruído e não mede
capacidade de detecção — defendendo-a ou refutando-a, nunca a assumindo.

#### Scenario: Base amostral por classe
- **WHEN** o leitor procura o poder da medição
- **THEN** o relatório informa quantas amostras negativas e quantas positivas
  válidas sustentam cada métrica reportada

#### Scenario: Tese confrontada com os dados
- **WHEN** o relatório trata da validade da rodada
- **THEN** ele apresenta a evidência a favor e a evidência contra a tese e
  fecha com uma conclusão declarada

#### Scenario: Aninhamento entre braços interpretado
- **WHEN** o relatório trata da comparação entre baseline e especialista
- **THEN** ele reporta a interseção dos falsos negativos, a contenção dos
  falsos positivos e a tabela de discordâncias de McNemar, e discute que a
  interpretação "o especialista aprendeu a reconhecer FP" não é separável de
  "o especialista ficou conservador" com a base positiva disponível

### Requirement: Funil de recall decomposto
O relatório SHALL apresentar o funil que vai das amostras rotuladas como
vulneráveis até as amostras positivas efetivamente avaliadas pelo LLM, em
diagrama, com o número absoluto e o percentual perdido em cada degrau, e SHALL
atribuir cada degrau à sua causa.

#### Scenario: Diagrama presente
- **WHEN** o leitor procura por que o recall da pipeline completa é o que é
- **THEN** o relatório traz o diagrama do funil com todos os degraus e o
  recall de ponta a ponta calculado sobre o topo do funil

#### Scenario: Causa de cada degrau atribuída
- **WHEN** um degrau do funil é apresentado
- **THEN** ele vem rotulado como perda por não-detecção do motor simbólico ou
  como perda por emparelhamento incorreto entre alerta e gabarito

#### Scenario: Não-detecção caracterizada por evidência
- **WHEN** o relatório afirma que a não-detecção não é lacuna de ruleset
- **THEN** ele sustenta a afirmação com a distribuição por CWE dos casos não
  detectados, com a proporção de arquivos que produzem zero alertas contra a
  dos que produzem alerta de outra CWE, e com o tamanho da amostra
  diagnosticada

#### Scenario: Origem dos casos perdidos discriminada
- **WHEN** o relatório apresenta os casos não detectados
- **THEN** eles aparecem separados por trilha de origem (`TP_ouro`,
  `TP_prata`, `TP_dataset`)

### Requirement: Orientação de reporte de métricas
O relatório SHALL classificar cada métrica produzida pela rodada em reportável
sem ressalva, reportável com ressalva ou a omitir, justificando a
classificação pela base amostral, e SHALL fornecer o texto da ressalva pronto
para uso na monografia.

#### Scenario: Cada métrica classificada
- **WHEN** o leitor procura o que levar para o capítulo de resultados
- **THEN** Precisão, Recall, F1, MCC, TRA e TFN aparecem cada uma com sua
  classificação e sua justificativa

#### Scenario: Ressalva redigida
- **WHEN** uma métrica é classificada como reportável com ressalva
- **THEN** o relatório traz a frase de ressalva pronta, transponível para o
  `.tex` sem reescrita

#### Scenario: Leitura errada antecipada
- **WHEN** o relatório trata das métricas governadas pela classe positiva
- **THEN** ele nomeia explicitamente a leitura equivocada que elas induzem e
  por que ela não se sustenta

### Requirement: Análise qualitativa da classe positiva
O relatório SHALL analisar caso a caso todas as amostras de gabarito
vulnerável que chegaram ao LLM com veredito válido, lendo a justificativa
produzida pelo modelo em cada braço, e SHALL indicar, para cada caso, se o
erro é do gabarito, do emparelhamento ou do julgamento do modelo.

#### Scenario: Falsos negativos cobertos
- **WHEN** o relatório trata dos falsos negativos da rodada
- **THEN** cada um aparece com seu `ID_Caso`, sua CWE, sua trilha de origem e
  um resumo da justificativa do LLM nos dois braços

#### Scenario: Verdadeiro positivo dissecado
- **WHEN** o relatório trata do único acerto na classe positiva
- **THEN** ele mostra o `ID_Caso`, a regra do Semgrep que disparou, a
  justificativa do LLM em cada braço, e avalia se o acerto é substantivo ou
  fortuito

#### Scenario: Atribuição de causa por caso
- **WHEN** um caso da classe positiva é analisado
- **THEN** ele é rotulado como erro de gabarito, erro de emparelhamento ou
  erro de julgamento do modelo

#### Scenario: Citação ancorada no CSV
- **WHEN** o relatório cita uma justificativa do LLM
- **THEN** o `ID_Caso` e o CSV de origem são indicados, de modo que a citação
  seja localizável

### Requirement: Separação entre defeito corrigível e limite estrutural
O relatório SHALL separar os problemas observados na rodada em defeitos
corrigíveis por engenharia e limites estruturais da abordagem, e SHALL
registrar também o que funcionou, para que o capítulo de limitações não
apague os resultados positivos.

#### Scenario: Defeito corrigível dimensionado
- **WHEN** o relatório aponta o emparelhamento incorreto entre alerta e
  gabarito
- **THEN** ele localiza o código responsável por arquivo e linha, quantifica
  quantos casos foram afetados e diz o que precisa ser reexecutado após a
  correção

#### Scenario: Limite estrutural argumentado
- **WHEN** o relatório afirma que casamento sintático não alcança
  vulnerabilidade que depende de intenção
- **THEN** a afirmação vem sustentada pela distribuição de CWEs observada e
  declarada como limite da classe de ferramenta, não como defeito de
  configuração

#### Scenario: Resultados positivos registrados
- **WHEN** o relatório trata do que deu certo
- **THEN** a calibragem de `num_ctx` sem estouros de contexto, a taxa de ERROR
  do modelo local e a redução de ruído entre os braços aparecem com seus
  números

### Requirement: Avaliação de viabilidade de conjunto de verdadeiros positivos detectáveis
O relatório SHALL avaliar a hipótese de inverter o funil — partir das regras
que o motor simbólico de fato possui e minerar casos em que um achado daquela
regra foi corrigido, em vez de partir de CVEs e torcer para o motor disparar —
e SHALL emitir recomendação fundamentada de seguir ou não seguir.

#### Scenario: Fontes candidatas avaliadas
- **WHEN** o relatório trata de como obter os casos
- **THEN** cada fonte candidata aparece com o que ela oferece, o custo de
  extração e o motivo de ser viável ou inviável neste projeto

#### Scenario: Custo estimado em unidades verificáveis
- **WHEN** o relatório estima o esforço de construir o conjunto
- **THEN** a estimativa vem em unidades concretas — horas, chamadas de API,
  volume de download, casos por hora — e não em adjetivos

#### Scenario: Viés declarado
- **WHEN** o relatório recomenda construir o conjunto a partir das regras do
  detector
- **THEN** ele declara explicitamente que um conjunto assim favorece o
  detector, argumenta por que isso é aceitável para medir triagem e não para
  medir detecção, e propõe a redação dessa declaração na monografia

#### Scenario: n necessário confrontado com n alcançável
- **WHEN** o relatório discute se Recall e F1 se tornam reportáveis
- **THEN** ele apresenta o tamanho de classe positiva necessário, o alcançável
  pela via proposta, e conclui se o alvo é atingível

#### Scenario: Restrições conhecidas respeitadas
- **WHEN** o relatório propõe qualquer caminho de construção de dados
- **THEN** ele respeita que `tp_pairs.json` e `tp_pairs_osv.json` não são
  regeneráveis sem reclonar os repositórios, e que trocar ruleset ou engine
  invalidaria o gabarito de falsos positivos herdado do SastBench

### Requirement: Recomendações ordenadas por retorno sobre esforço
O relatório SHALL encerrar com uma lista ordenada de próximos passos, cada um
com o ganho esperado, o custo estimado e a dependência que o bloqueia,
ordenada por retorno sobre esforço.

#### Scenario: Lista ordenada e justificada
- **WHEN** o leitor chega ao fim do relatório
- **THEN** encontra os próximos passos numerados em ordem de retorno sobre
  esforço, cada um com ganho, custo e dependência

#### Scenario: Passo acionável
- **WHEN** um próximo passo é lido
- **THEN** ele nomeia o artefato ou comando por onde começar, em vez de
  descrever uma intenção genérica
