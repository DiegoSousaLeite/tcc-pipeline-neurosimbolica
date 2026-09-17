## ADDED Requirements

### Requirement: Portão de viabilidade do modo entre-arquivos
O sistema SHALL oferecer uma verificação executável que determina, empiricamente, se o modo entre-arquivos do Semgrep está disponível nas condições deste projeto — conta gratuita, máquina do pesquisador, código Go. A verificação SHALL gravar o resultado em disco com a data, a versão do Semgrep e a edição obtida.

A evidência de que o Pro Engine é gratuito veio de página comercial, não de documentação técnica nem de termo de licença. Adotar o modo sem verificar seria construir sobre afirmação de marketing; e descobrir a indisponibilidade no meio da implementação custaria mais do que descobri-la no primeiro passo.

A verificação SHALL ser conclusiva nos dois sentidos: precisa distinguir "o modo rodou e produziu trilha entre arquivos" de "o modo rodou e não produziu trilha" e de "o modo foi recusado por exigir plano pago". Um resultado ambíguo NÃO SHALL ser tratado como sucesso.

O alvo da verificação SHALL conter fonte e sumidouro em arquivos diferentes. Esta é a condição sem a qual a verificação não mede nada: o cache de fontes guarda um arquivo por caso — 69 dos 226 casos de CWE-22 e CWE-918 têm um único arquivo no diretório do commit, e os vizinhos, quando existem, são arquivos vulneráveis de outros casos, não os chamadores. Rodar o modo entre-arquivos sobre um alvo desses produz zero trilhas por construção, e essa ausência descreveria a forma do cache, não o alcance do motor. Um alvo de arquivo isolado NÃO SHALL produzir a classificação `inconclusivo`; SHALL ser recusado como alvo inválido.

A verificação SHALL ser executável em duas etapas de custo crescente, e a segunda SHALL ser dispensável quando a primeira já for conclusiva pela negativa. A primeira etapa roda sobre um projeto Go mínimo de fonte conhecida, escrito para este fim, e responde se o motor está sequer disponível; a segunda roda sobre checkouts reais dos repositórios da população e responde se ele alcança os casos deste experimento. A ordem existe porque a primeira etapa custa segundos e pode devolver `indisponível` — matando a change antes de qualquer clone —, enquanto a segunda custa disco e rede que já são escassos nesta máquina.

#### Scenario: Modo disponível e eficaz
- **WHEN** a verificação roda o modo entre-arquivos sobre a amostra e ao menos um alerta traz trilha de dataflow
- **THEN** o resultado é registrado como viável, com a contagem de alertas com trilha

#### Scenario: Modo disponível e ineficaz
- **WHEN** o modo executa sem erro mas nenhum alerta da amostra traz trilha de dataflow
- **THEN** o resultado é registrado como inconclusivo quanto ao ganho, e NÃO como viável

#### Scenario: Modo recusado por plano
- **WHEN** a execução falha com indicação de que o recurso exige plano pago
- **THEN** o resultado é registrado como indisponível, com a mensagem original preservada

#### Scenario: Alvo de arquivo isolado é recusado
- **WHEN** o alvo oferecido à verificação contém um único arquivo, ou não contém fonte e sumidouro em arquivos diferentes
- **THEN** a verificação falha com erro explícito de alvo inválido, e NÃO produz classificação alguma

#### Scenario: Primeira etapa conclusiva pela negativa dispensa a segunda
- **WHEN** a etapa sobre o projeto mínimo registra `indisponível`
- **THEN** a etapa sobre checkouts reais não é executada, e nenhum repositório é clonado

### Requirement: Autorização de troca de motor exige ganho nos casos do gabarito
O sistema SHALL oferecer uma verificação cujo critério de aprovação seja a
**detecção nos casos do gabarito**, e NÃO a capacidade da ferramenta. Uma
verificação SHALL classificar como aprovada apenas quando o motor candidato
detectar ao menos um caso que o motor corrente não detecta, aplicando a mesma
regra de pareamento da Fase 1 sobre o arquivo do gabarito.

As duas afirmações — "a ferramenta funciona" e "a ferramenta detecta os nossos
casos" — são diferentes, e divergiram na medição de 2026-09-15/16: a verificação
de capacidade aprovou o modo entre-arquivos, e a verificação sobre os casos do
gabarito devolveu **0 detecções novas em 6 casos**. Um portão que aprova quando o
ganho não chega aos casos não é portão: ele autoriza gastar a repopulação da fase
mais cara da esteira para reproduzir exatamente os mesmos vereditos.

Alerta que o motor candidato emite em OUTRO arquivo do repositório NÃO SHALL
contar como ganho. O experimento pontua o veredito contra o gabarito daquele
caso; alerta que não pertence ao caso não vira amostra avaliável.

Alvo cujo resultado não pôde ser medido — tempo esgotado, falha de clone —
SHALL ser registrado como dado ausente, e NÃO como ausência de detecção. Contar
tempo esgotado como zero transformaria limite de execução em evidência a favor
da hipótese nula.

#### Scenario: Motor candidato detecta caso que o corrente perde
- **WHEN** a verificação mede os dois motores sobre os mesmos casos e o candidato emparelha um alerta à CWE do gabarito num caso em que o corrente não emparelha
- **THEN** o resultado é registrado como aprovado, com a contagem de casos ganhos sobre casos medidos

#### Scenario: Nenhuma detecção nova apesar de a ferramenta funcionar
- **WHEN** o motor candidato executa, produz alertas no repositório, e nenhum caso do gabarito muda de veredito
- **THEN** o resultado é registrado como inconclusivo, e NÃO autoriza a repopulação

#### Scenario: Ganho fora do arquivo do caso não conta
- **WHEN** o motor candidato emite alertas novos em arquivos que não são o do gabarito
- **THEN** esses alertas não entram na contagem de ganho

#### Scenario: Alvo não medido não conta como ausência de detecção
- **WHEN** a medição de um alvo falha por tempo esgotado ou erro de esteira
- **THEN** o caso é registrado como dado ausente, e a classificação declara sobre quantos casos efetivamente medidos ela se apoia

#### Scenario: Verificação não altera o estado do experimento
- **WHEN** a verificação é executada com qualquer resultado
- **THEN** nenhuma entrada de cache simbólico é gravada ou invalidada e nenhum CSV de rodada é produzido

### Requirement: Identidade declarada do motor simbólico
O sistema SHALL registrar, junto de cada resultado simbólico produzido, a identidade do motor que o produziu: a edição (`ce` ou `pro`), a versão do Semgrep e se o modo entre-arquivos estava ativo.

Hoje a identidade do motor é pressuposta. Enquanto houve um motor só, pressupor era inofensivo; a partir do momento em que existem dois que produzem SARIF de formas diferentes sobre o mesmo arquivo, um resultado sem identidade não sabe dizer o que o gerou — e a auditoria não tem como recuperar a informação depois.

A identidade SHALL chegar ao manifesto da rodada, pelo mesmo motivo que a identidade do modelo local já chega: permitir dizer, meses depois, qual motor produziu cada número.

#### Scenario: Identidade acompanha o resultado
- **WHEN** a Fase 1 produz um resultado simbólico
- **THEN** a edição, a versão do Semgrep e o estado do modo entre-arquivos constam do resultado

#### Scenario: Identidade chega ao manifesto
- **WHEN** uma rodada termina e grava seu manifesto
- **THEN** a identidade do motor usado consta dele

#### Scenario: Resultado sem identidade é tratado como anterior
- **WHEN** existe resultado gravado antes de a identidade passar a ser registrada
- **THEN** ele é tratado como produzido pelo motor CE sem modo entre-arquivos, e não como identidade desconhecida aceita por omissão

### Requirement: Modo entre-arquivos desligado por padrão
O sistema SHALL manter o modo entre-arquivos desativado por padrão, ativável apenas por opção explícita de invocação.

Ligar o modo muda o conjunto de alertas que a camada simbólica emite, e portanto muda o objeto que o braço neural tria. As Rodadas 1–3 mediram o motor CE; uma rodada com o modo ligado mede outro motor, e as duas não são comparáveis. Deixá-lo desligado por padrão garante que a comparabilidade só se perca quando alguém decidir perdê-la.

#### Scenario: Invocação padrão preserva o motor anterior
- **WHEN** a pipeline é executada sem pedir o modo entre-arquivos
- **THEN** o Semgrep é invocado exatamente como antes desta mudança e os alertas produzidos são os mesmos

#### Scenario: Ativação é explícita e registrada
- **WHEN** a pipeline é executada pedindo o modo entre-arquivos
- **THEN** o modo é ativado e o fato fica registrado no manifesto da rodada

#### Scenario: Ativação sem viabilidade confirmada falha cedo
- **WHEN** o modo entre-arquivos é pedido e não há registro de verificação de viabilidade bem-sucedida
- **THEN** a execução falha com mensagem explícita, em vez de cair silenciosamente no motor CE

### Requirement: Esteira offline preservada após a busca autenticada
O sistema SHALL preservar a invariante de execução offline: depois de o resultado simbólico estar em cache, nenhuma execução subsequente SHALL exigir rede ou autenticação, independentemente do motor que o produziu.

A invariante do projeto nunca foi "não usar rede" — é "buscar uma vez, congelar, reexecutar offline", que é como o cache de ruleset e o cache de fontes já funcionam. O modo entre-arquivos acrescenta uma busca autenticada à etapa de preenchimento; não pode acrescentar nada à etapa de reexecução.

#### Scenario: Rodada servida do cache dispensa autenticação
- **WHEN** todos os casos de uma rodada têm entrada de cache simbólico válida
- **THEN** a rodada completa sem login, sem download de binário e sem rede

#### Scenario: Falta de autenticação não degrada silenciosamente
- **WHEN** o modo entre-arquivos é pedido, falta cache para um caso e não há autenticação disponível
- **THEN** a falha é reportada como erro de esteira, e o caso NÃO é gravado como `NAO_DETECTADO`
