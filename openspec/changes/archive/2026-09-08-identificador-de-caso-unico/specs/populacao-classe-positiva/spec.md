## ADDED Requirements

### Requirement: Identificador de caso único na população
O sistema SHALL produzir identificadores de caso únicos na população inteira — dentro de cada trilha e entre trilhas — e SHALL abortar a montagem, nomeando os identificadores repetidos, quando isso não se verificar.

Unicidade "entre trilhas" não basta, e a diferença não é teórica: o esquema derivava o identificador de `(repo, CWE, função, versão)`, sem o arquivo. Em Go o mesmo nome de método aparece em vários arquivos do mesmo pacote e um único fix os altera juntos, então três casos distintos recebiam o mesmo identificador. Medido no pool da colheita filtrada: 18 identificadores repetidos, 46 casos envolvidos, 28 que sumiriam.

Sumiriam em silêncio, que é o ponto. O checkpoint por tripla `(ID_Caso, Modelo_LLM, Tipo_Prompt)` trata o segundo caso como já gravado, e as métricas deduplicam pela primeira ocorrência — nada no CSV denuncia a perda. Por isso a colisão SHALL ser erro de montagem, e não algo a descobrir na análise: é o mesmo modo de falha do pareamento por fallback e do ruleset vazio, saída plausível e errada.

O identificador de um caso SHALL depender apenas dos atributos daquele caso, nunca de quais outros casos existem no pool, para que acrescentar um par jamais mude o identificador de um par já existente.

#### Scenario: Pares do mesmo repositório, CWE e função em arquivos distintos
- **WHEN** um pool traz pares que compartilham repositório, CWE e nome de função, mas apontam arquivos diferentes
- **THEN** cada caso recebe identificador próprio, e nenhum deles é absorvido por outro

#### Scenario: Identificador não depende dos vizinhos no pool
- **WHEN** um par novo é acrescentado a um pool já carregado antes
- **THEN** os identificadores dos pares que já estavam lá permanecem os mesmos

#### Scenario: Colisão remanescente aborta a montagem
- **WHEN** a população montada contém identificador de caso repetido
- **THEN** a execução falha antes de qualquer varredura ou chamada de LLM, e a mensagem nomeia os identificadores repetidos

#### Scenario: Trilhas já executadas mantêm seus identificadores
- **WHEN** a população é montada depois da mudança do esquema
- **THEN** os casos de `FP`, `TP_ouro`, `TP_prata` e `TP_dataset` têm exatamente os identificadores que já estão gravados nos CSVs e no checkpoint das rodadas anteriores

## MODIFIED Requirements

### Requirement: Trilha própria para os casos de CWE alcançável
O sistema SHALL carregar os pares produzidos pela colheita filtrada como uma trilha própria, identificada por rótulo de origem distinto das trilhas existentes, sem substituir nenhuma delas. Os arquivos-alvo dessa trilha SHALL ser preenchíveis no cache de fontes pela mesma ferramenta que atende as demais trilhas.

Trilha própria, e não substituição do pool da `TP_prata`, porque sobrescrever destruiria os pares inalcançáveis que sustentam o achado dos 70,1%, e porque `tp_pairs.json` é irrecuperável — só `scripts/tp_reconstruct.py` o regenera, e ele exige o histórico git completo dos repositórios, que não está mais em disco.

O preenchimento de cache entra no requisito porque a trilha ficou de fora dele quando foi criada: a ferramenta montava seu conjunto de alvos a partir dos pools antigos apenas, e a Fase 1 acabaria buscando da rede os arquivos da trilha nova — justamente o que o cache de fontes existe para evitar.

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

#### Scenario: Alvos da trilha nova entram no preenchimento de cache
- **WHEN** a ferramenta de preenchimento do cache de fontes monta seu conjunto de alvos
- **THEN** os arquivos apontados pelos pares da trilha nova estão nele, e uma rodada seguinte não busca nenhum deles da rede

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
