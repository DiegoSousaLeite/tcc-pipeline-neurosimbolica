# provedor-local-ollama

## ADDED Requirements

### Requirement: Braço de modelo local via Ollama
O sistema SHALL executar braços da matriz experimental contra um servidor Ollama na máquina local, através da mesma interface de provedor usada pelos provedores comerciais, sem alteração nas Fases 1/2, 3/4 ou na auditoria.

#### Scenario: Braço local produz veredito no mesmo formato
- **WHEN** um braço com modelo local é executado sobre um caso `DETECTADO`
- **THEN** o resultado tem `veredito` em `{VP, FP}`, justificativa não vazia, contagem de tokens de entrada e saída, e nome do modelo, exatamente como um braço comercial

#### Scenario: Braço local convive com braços comerciais na mesma rodada
- **WHEN** uma rodada seleciona um modelo local e um modelo comercial
- **THEN** ambos os braços rodam sobre a mesma população, cada um em seu CSV, e o manifesto registra os dois

#### Scenario: Modelo local não exige credencial
- **WHEN** um braço local é executado sem nenhuma variável de chave de API definida no ambiente
- **THEN** a execução prossegue normalmente e nenhum resultado é marcado como erro de credencial

#### Scenario: Troca de modelo local não exige código novo
- **WHEN** o pesquisador seleciona um modelo local diferente do padrão, entre os disponíveis no servidor Ollama
- **THEN** o braço é executado com esse modelo sem alteração de código, e o nome do modelo aparece no CSV e no manifesto

### Requirement: Verificação prévia do servidor e do modelo
O sistema SHALL verificar, antes de iniciar a triagem, que o servidor Ollama está acessível e que o modelo pedido está presente nele, e SHALL abortar com mensagem acionável quando não estiver, em vez de acumular um erro por caso.

#### Scenario: Servidor fora do ar aborta a rodada
- **WHEN** um braço local é selecionado e o servidor Ollama não está acessível no endereço configurado
- **THEN** a rodada aborta antes do primeiro caso, com mensagem indicando o endereço tentado e como subir o serviço

#### Scenario: Modelo ausente aborta a rodada
- **WHEN** o servidor está acessível mas o modelo pedido não consta entre os modelos instalados
- **THEN** a rodada aborta antes do primeiro caso, com mensagem nomeando o modelo pedido, listando os disponíveis e indicando o comando de download

#### Scenario: Ausência de Ollama não afeta rodada sem braço local
- **WHEN** uma rodada seleciona apenas modelos comerciais em uma máquina sem Ollama instalado
- **THEN** nenhuma verificação de servidor local é feita e a rodada executa normalmente

### Requirement: Janela de contexto explícita e estouro visível
O sistema SHALL definir explicitamente a janela de contexto usada pelo modelo local, e SHALL tratar um prompt que não caiba nessa janela como erro registrado, e SHALL NOT aceitar veredito derivado de prompt truncado.

O motivo é a validade dos resultados: o padrão do servidor é uma janela pequena, e o excedente é descartado em silêncio. Um veredito emitido sobre código que o modelo viu pela metade é indistinguível, no CSV, de um veredito legítimo — é contaminação silenciosa da amostra.

#### Scenario: Janela é fixada pela pipeline, não herdada do servidor
- **WHEN** um braço local é executado
- **THEN** a requisição informa explicitamente o tamanho de janela de contexto a ser usado, sem depender do padrão do servidor

#### Scenario: Prompt maior que a janela vira erro
- **WHEN** o prompt montado para um caso excede a janela de contexto configurada
- **THEN** o resultado é `ERROR`, o caso é registrado em categoria de erro fora das duas matrizes, e nenhum veredito é gravado

#### Scenario: Truncamento silencioso é detectado
- **WHEN** a resposta do servidor indica que a entrada foi truncada para caber na janela
- **THEN** o resultado é `ERROR` e a justificativa registra que houve truncamento

#### Scenario: Janela efetiva consta do manifesto
- **WHEN** uma rodada com braço local termina
- **THEN** o manifesto registra a janela de contexto efetivamente usada por aquele braço

### Requirement: Determinismo da geração local
O sistema SHALL configurar a geração local para ser o mais determinística que o servidor permita, usando temperatura zero e semente fixa, e SHALL registrar a semente no manifesto.

#### Scenario: Temperatura zero e semente fixa
- **WHEN** uma requisição é montada para o provedor local
- **THEN** ela especifica temperatura zero e uma semente fixa, para que a comparação entre braços não misture variação de amostragem com diferença de modelo

#### Scenario: Semente registrada
- **WHEN** uma rodada com braço local termina
- **THEN** o manifesto registra a semente usada

### Requirement: Tempo de espera adequado à inferência local
O sistema SHALL usar, para o provedor local, um tempo limite de requisição compatível com inferência em hardware de desktop, incluindo o carregamento inicial do modelo na memória.

O motivo é que um modelo que não cabe na memória de vídeo roda com parte das camadas na CPU e uma única resposta pode levar minutos; o limite adequado às APIs comerciais transformaria essa lentidão em uma fila de erros de rede indistinguíveis de falha real.

#### Scenario: Primeira chamada tolera carregamento do modelo
- **WHEN** a primeira chamada de um braço local dispara o carregamento do modelo na memória
- **THEN** ela não expira por tempo limite antes de o carregamento terminar

#### Scenario: Sem throttle entre chamadas locais
- **WHEN** chamadas consecutivas são feitas ao provedor local
- **THEN** nenhum intervalo mínimo é imposto entre elas, porque não há cota a respeitar

#### Scenario: Servidor que cai no meio da rodada não é confundido com lentidão
- **WHEN** o servidor local deixa de responder durante a rodada
- **THEN** o caso é registrado como `ERROR` com o motivo distinguindo indisponibilidade de tempo limite excedido

### Requirement: Identidade reprodutível do modelo local
O sistema SHALL registrar no manifesto a identidade do modelo local além do nome da tag, incluindo o digest do modelo, a quantização e a versão do servidor Ollama.

O motivo é o mesmo do hash do catálogo de CWE: uma tag como `qwen2.5-coder:7b` é mutável no registry e não identifica pesos. Sem o digest, um número do capítulo de resultados não pode ser reatribuído ao modelo que o produziu.

#### Scenario: Manifesto identifica os pesos
- **WHEN** uma rodada com braço local termina
- **THEN** o manifesto contém, para aquele braço, o nome da tag, o digest do modelo, a quantização declarada e a versão do servidor Ollama

#### Scenario: Identidade indisponível é registrada como ausente
- **WHEN** o servidor não informa algum desses campos
- **THEN** o campo consta do manifesto como ausente, em vez de ser omitido ou preenchido por suposição

### Requirement: Custo zero declarado para execução local
O sistema SHALL registrar custo zero para braços locais de forma declarada, distinguindo-a no manifesto de um modelo cujo preço simplesmente não foi tabelado.

#### Scenario: Custo zero por execução local
- **WHEN** um caso é triado por um braço local
- **THEN** a linha do CSV registra custo zero em USD, e as contagens de tokens continuam sendo gravadas

#### Scenario: Manifesto distingue gratuito de não tabelado
- **WHEN** uma rodada mistura um modelo local e um modelo comercial ausente da tabela de preços
- **THEN** o manifesto classifica o primeiro como execução local sem custo monetário e o segundo como modelo sem preço tabelado
