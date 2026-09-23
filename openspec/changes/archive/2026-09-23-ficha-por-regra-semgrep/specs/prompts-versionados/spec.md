## ADDED Requirements

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

## MODIFIED Requirements

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
