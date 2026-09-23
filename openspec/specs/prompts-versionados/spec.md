# prompts-versionados

## Purpose

Armazenar os prompts como templates em arquivo, versionados e rastreados por hash, em vez de f-string embutido no código das fases 3/4.

O prompt é a variável experimental do eixo horizontal da matriz, e um f-string embutido não tem versão: qualquer ajuste no texto altera silenciosamente o experimento e nenhum resultado já gravado sabe disso. Em arquivo, o hash do template vai para cada linha do CSV e a alteração fica detectável.

São dois templates com papéis assimétricos. O `baseline` é a **condição de controle** e por isso não pode ver nenhuma camada da metodologia — nem o identificador da CWE. O `especialista` recebe as três camadas, todas vindas do catálogo de CWE. Ambos exigem o mesmo contrato de saída, para que a diferença medida entre os braços esteja no conteúdo e não na dificuldade de acertar o formato.

## Requirements

### Requirement: Prompts armazenados como templates em arquivo
O sistema SHALL armazenar os prompts em arquivos versionados sob `prompts/` e SHALL NOT manter texto de prompt embutido em f-string no código das fases 3/4.

#### Scenario: Prompt vem de arquivo
- **WHEN** um prompt é montado
- **THEN** seu texto é lido de um arquivo em `prompts/` e preenchido por substituição de placeholders nomeados

#### Scenario: Código sem prompt embutido
- **WHEN** `src/fases3_4_llm.py` é inspecionado
- **THEN** ele não contém o corpo textual do prompt, apenas a lógica de montagem

#### Scenario: Tipo de prompt desconhecido é recusado
- **WHEN** a montagem é pedida para um tipo de prompt que não existe
- **THEN** a operação falha com erro explícito, em vez de produzir prompt vazio

#### Scenario: Nenhum placeholder sobra no texto renderizado
- **WHEN** qualquer prompt é renderizado
- **THEN** o texto resultante não contém placeholder não preenchido

### Requirement: Prompt baseline zero-shot como condição de controle
O prompt baseline SHALL conter apenas instrução genérica de análise de segurança, o código e o alerta, e SHALL NOT conter definição de CWE, heurística de Go ou exemplos few-shot.

#### Scenario: Baseline sem camadas da metodologia
- **WHEN** o prompt baseline é renderizado para um caso
- **THEN** o texto resultante não contém definição formal da CWE, heurística semântica nem exemplos VP/FP

#### Scenario: Baseline não recebe nem o identificador da CWE
- **WHEN** o prompt baseline é renderizado para um caso de CWE conhecida
- **THEN** o identificador da CWE não aparece no texto, que julga apenas o que a ferramenta reportou

#### Scenario: Baseline contém código e alerta
- **WHEN** o prompt baseline é renderizado
- **THEN** ele contém o contexto hidratado do caso e a identificação do alerta emitido pelo Semgrep

### Requirement: Prompt especialista com as três camadas
O prompt especialista (e suas variantes `especialista_direto`, `especialista_v2` e `especialista_direto_v2`) SHALL incluir as três camadas da metodologia — definição formal, heurística semântica de Go e par de exemplos VP/FP — todas obtidas da ficha do catálogo resolvida para o candidato, com precedência regra > CWE > fallback.

#### Scenario: Três camadas presentes
- **WHEN** o prompt especialista é renderizado para uma CWE com ficha específica e um alerta cuja regra não tem ficha própria
- **THEN** o texto contém a definição, a heurística e os dois exemplos da ficha da CWE

#### Scenario: Ficha da regra tem precedência
- **WHEN** o prompt especialista é renderizado para um alerta cuja regra tem ficha própria
- **THEN** as três camadas vêm da ficha da regra, e o cabeçalho continua identificando a CWE do caso

#### Scenario: Fallback preenche as camadas
- **WHEN** o prompt especialista é renderizado para uma CWE sem ficha específica e uma regra sem ficha própria
- **THEN** as camadas são preenchidas a partir da ficha genérica de fallback, sem seções vazias

### Requirement: Contrato de saída idêntico entre prompts
Ambos os prompts SHALL exigir a mesma estrutura de resposta JSON com veredito em `{VP, FP}` e justificativa, de modo que a diferença entre braços esteja no conteúdo e não no formato exigido.

#### Scenario: Mesmo contrato de saída
- **WHEN** os prompts baseline e especialista são comparados
- **THEN** ambos exigem a mesma estrutura de resposta, com as mesmas chaves e o mesmo domínio de veredito

### Requirement: Versão do prompt rastreada no resultado
O sistema SHALL gravar no CSV a identificação da versão do template de prompt usado em cada chamada.

#### Scenario: Coluna de versão preenchida
- **WHEN** um caso `DETECTADO` é registrado
- **THEN** a linha contém o identificador de versão (hash) do arquivo de prompt utilizado

#### Scenario: Alteração de prompt é detectável
- **WHEN** um arquivo de prompt é editado entre duas rodadas
- **THEN** as linhas das duas rodadas carregam identificadores de versão diferentes

### Requirement: Variantes v2 com instrução sobre mitigação ausente
O sistema SHALL oferecer os tipos de prompt `especialista_v2` e `especialista_direto_v2`, cada um em arquivo próprio, com as mesmas três camadas, o mesmo enquadramento e o mesmo contrato de saída do seu original (`especialista` e `especialista_direto`, respectivamente), acrescidos de uma instrução para não presumir validação, sanitização ou mitigação que não aparece no trecho. Os arquivos originais SHALL NOT ser editados por esta mudança.

#### Scenario: Instrução presente só na variante
- **WHEN** um tipo original e sua variante v2 são renderizados para o mesmo caso e a mesma ficha
- **THEN** o texto da v2 contém a instrução sobre mitigação ausente e o do original não; as três camadas, o enquadramento e o contexto são idênticos nos dois

#### Scenario: Variante direta pergunta pelo código
- **WHEN** o `especialista_direto_v2` é renderizado
- **THEN** ele pergunta pelo código, como o `especialista_direto`, e não pressupõe alerta de ferramenta

#### Scenario: Templates originais preservados
- **WHEN** as versões (`Versao_Prompt`) de `especialista` e `especialista_direto` são calculadas depois desta mudança
- **THEN** elas são iguais às gravadas nas rodadas anteriores (`especialista:d1145f8b`, `especialista_direto:f537598a`)

#### Scenario: Mesmo contrato de saída
- **WHEN** a seção de contrato de cada variante v2 é comparada com a dos demais tipos
- **THEN** ela é idêntica
