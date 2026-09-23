# catalogo-cwe

## Purpose

Manter um catálogo versionado por CWE — definição formal, heurística semântica de Go e par mínimo de exemplos VP/FP — que é a fonte **única** das duas camadas do prompt especialista que dependem da CWE.

Desde a change `ficha-por-regra-semgrep` (2026-09-22) o catálogo pode trazer também fichas por regra do Semgrep, resolvidas antes das de CWE. A Rodada 7 mostrou esse desenho pior que o por CWE (mesmo recall, mais falsos alarmes; `docs/ANALISE-RODADA-7.md`), e por isso o padrão continua o catálogo por CWE; o por regra fica em arquivo próprio, escolhido por rodada com `--catalogo`.

Fonte única porque duas fontes de verdade permitiriam que a heurística e os exemplos discordassem, e o braço "especialista" deixaria de ser uma condição experimental bem definida.

Os exemplos são escritos à mão, e não extraídos das amostras, por necessidade e por método. Por necessidade: a interseção de CWEs entre as trilhas FP e TP é de apenas 5 de 26, então para as CWEs que carregam quase todo o volume não existe nenhum VP real disponível no material. Por método: um conjunto few-shot derivado do conjunto de avaliação carregaria informação dele e invalidaria os resultados.

## Requirements

### Requirement: Catálogo de triagem por CWE versionado
O sistema SHALL manter um catálogo versionado no repositório com uma ficha por CWE e, opcionalmente, fichas por regra do Semgrep, cada uma contendo definição formal, heurística semântica de Go e um par mínimo de exemplos VP/FP.

#### Scenario: Ficha completa
- **WHEN** o catálogo é consultado para uma CWE coberta ou para uma regra coberta
- **THEN** a ficha devolvida tem definição, heurística de Go, exemplo VP e exemplo FP, todos não vazios

#### Scenario: Catálogo é a fonte única
- **WHEN** o prompt especialista é montado
- **THEN** tanto a camada de heurística quanto a camada de few-shot vêm da mesma ficha do catálogo

#### Scenario: Catálogo malformado é recusado
- **WHEN** o catálogo não é JSON válido, não tem a ficha genérica de fallback, ou tem alguma ficha, de CWE ou de regra, com campo obrigatório vazio
- **THEN** o carregamento falha com erro explícito, em vez de a rodada prosseguir com camada de prompt vazia

### Requirement: Exemplos escritos à mão a partir de fontes externas
Os exemplos do catálogo SHALL ser escritos manualmente a partir da definição da CWE, da documentação da regra do Semgrep (para fichas de regra) e da documentação da biblioteca padrão de Go, e SHALL NOT ser extraídos das amostras avaliadas.

#### Scenario: Nenhum trecho vem das amostras
- **WHEN** os exemplos do catálogo são comparados com o conteúdo do dataset e do cache de fontes
- **THEN** nenhum exemplo reproduz trecho de código de uma amostra avaliada

#### Scenario: Par contrastante pela mesma API
- **WHEN** a ficha de CWE-327 é consultada
- **THEN** o exemplo VP e o exemplo FP usam a mesma API (`md5.Sum`) em contextos opostos — hash de senha versus chave de cache/ETag

#### Scenario: Contraste também nas demais fichas
- **WHEN** a ficha de CWE-338 é consultada
- **THEN** o exemplo VP usa `math/rand` para token de sessão e o exemplo FP usa `math/rand` para jitter de backoff

#### Scenario: Contraste pela API em todas as fichas específicas
- **WHEN** qualquer ficha específica, de CWE ou de regra, é consultada
- **THEN** os exemplos VP e FP compartilham a API central, para que o modelo decida pelo contexto em vez de reconhecer a API. A ficha genérica de fallback é a única exceção, por não ter API específica

#### Scenario: Exemplos são Go válido
- **WHEN** os trechos de código do catálogo são submetidos ao analisador da linguagem
- **THEN** todos são sintaticamente válidos

#### Scenario: Conteúdo textual em português
- **WHEN** as definições, heurísticas, justificativas e comentários dos exemplos são inspecionados
- **THEN** estão em português do Brasil, acentuados. Identificadores de código permanecem em ASCII, por convenção da linguagem

### Requirement: Cobertura do catálogo e fallback
O catálogo SHALL conter fichas específicas para as 15 CWEs de maior volume, cobrindo pelo menos 85% das amostras avaliadas, e SHALL oferecer uma ficha genérica de fallback para as demais.

#### Scenario: Cobertura verificada contra o dataset
- **WHEN** a cobertura do catálogo é medida sobre as locations `.go` do dataset, excluindo arquivos `_test.go`
- **THEN** as CWEs com ficha específica respondem por pelo menos 85% das amostras

#### Scenario: CWE sem ficha específica
- **WHEN** um caso tem uma CWE ausente do catálogo e a regra do candidato também não tem ficha
- **THEN** a ficha genérica de fallback é usada e o caso é executado normalmente

#### Scenario: Fallback preserva a CWE do caso
- **WHEN** a ficha de fallback é usada
- **THEN** o identificador da CWE do caso é preservado na ficha resolvida, e não substituído pela chave da ficha genérica

#### Scenario: Origem da ficha registrada
- **WHEN** um caso `DETECTADO` é registrado no CSV
- **THEN** a linha indica se a ficha usada foi de regra, específica de CWE ou fallback (`regra`, `especifica`, `fallback`), permitindo estratificar os resultados

### Requirement: Congelamento e rastreabilidade do catálogo
O catálogo SHALL ser congelado antes da primeira rodada do experimento e seu hash criptográfico SHALL ser gravado em cada linha do CSV e no manifesto da rodada.

#### Scenario: Hash em cada linha
- **WHEN** qualquer caso é registrado no CSV
- **THEN** a linha contém o hash do catálogo vigente no momento da execução

#### Scenario: Hash é dos bytes do arquivo
- **WHEN** o hash é calculado
- **THEN** ele é o SHA-256 dos bytes do arquivo em disco, e não de uma serialização normalizada, de modo que possa ser conferido por ferramenta externa

#### Scenario: Divergência de hash é detectável
- **WHEN** linhas com hashes de catálogo diferentes existem
- **THEN** a análise comparativa as identifica como pertencentes a versões distintas e não as agrega na mesma tabela sem sinalizar

#### Scenario: Protocolo declarado
- **WHEN** a documentação do projeto é consultada
- **THEN** o protocolo anti-viés está declarado: exemplos escritos a partir da definição da CWE e da documentação da stdlib de Go, sem consulta às amostras, congelados antes da primeira rodada e rastreados por hash

### Requirement: Fichas indexadas pela regra do Semgrep
O catálogo SHALL aceitar, num bloco `regras`, fichas indexadas pelo `check_id` completo da regra do Semgrep, no mesmo formato das fichas de CWE. A resolução da ficha SHALL seguir a precedência regra > CWE > fallback.

#### Scenario: Regra com ficha própria
- **WHEN** a ficha é resolvida para um candidato cujo `check_id` é `go.lang.security.audit.crypto.missing-ssl-minversion.missing-ssl-minversion` e a CWE do caso é `CWE-327`
- **THEN** a ficha devolvida é a do bloco `regras` para esse `check_id`, e não a ficha `CWE-327`

#### Scenario: Regra sem ficha própria cai na ficha de CWE
- **WHEN** a ficha é resolvida para um candidato cujo `check_id` não está no bloco `regras` e cuja CWE tem ficha específica
- **THEN** a ficha devolvida é a da CWE, exatamente como antes desta mudança

#### Scenario: Sem regra, a ficha é a da CWE
- **WHEN** a ficha é resolvida sem `check_id`, como no candidato injetado a partir do gabarito no braço de triagem
- **THEN** a ficha devolvida é a da CWE, ou o fallback se a CWE não tiver ficha

#### Scenario: Casamento exato do identificador
- **WHEN** o `check_id` do candidato difere de uma chave do bloco `regras` apenas no prefixo (por exemplo, só o último segmento coincide)
- **THEN** a ficha de regra não é usada; o casamento é pelo `check_id` completo

#### Scenario: Ficha de regra preserva a CWE do caso
- **WHEN** uma ficha de regra é usada
- **THEN** o identificador e o nome da CWE do caso são preservados na ficha resolvida

#### Scenario: Ficha de regra malformada é recusada
- **WHEN** o bloco `regras` contém uma ficha com campo obrigatório vazio ou exemplo sem `codigo` ou `porque`
- **THEN** o carregamento falha com erro explícito que nomeia a regra

### Requirement: Catálogo selecionável por rodada
O sistema SHALL usar por padrão o catálogo por CWE (`data/catalogo_cwe.json`, o das Rodadas 1–6) e SHALL permitir escolher outro catálogo por rodada com a opção `--catalogo`, de modo que o catálogo por CWE e o catálogo com fichas por regra (`data/catalogo_cwe_por_regra.json`) rodem em rodadas separadas e distinguíveis.

#### Scenario: Padrão é o catálogo por CWE
- **WHEN** uma rodada é executada sem `--catalogo`
- **THEN** o catálogo carregado é `data/catalogo_cwe.json`, e o hash gravado nas linhas é o mesmo das Rodadas 1–6

#### Scenario: Catálogo alternativo por opção
- **WHEN** uma rodada é executada com `--catalogo data/catalogo_cwe_por_regra.json`
- **THEN** o especialista usa esse catálogo, e o hash dele vai para cada linha do CSV e para o manifesto

#### Scenario: Catálogo inexistente é recusado
- **WHEN** `--catalogo` aponta para um arquivo que não existe ou não é catálogo válido
- **THEN** a execução é recusada com erro explícito antes do primeiro caso

### Requirement: Heurísticas do catálogo por regra declaram a condição de VP
No catálogo com fichas por regra, toda heurística específica, de regra ou de CWE, SHALL enunciar explicitamente a condição sob a qual o alerta é VP, além da condição sob a qual é FP. O catálogo por CWE mantém as heurísticas congeladas em 2026-07-29.

#### Scenario: Condição de VP presente no catálogo por regra
- **WHEN** qualquer heurística específica de `data/catalogo_cwe_por_regra.json` é inspecionada
- **THEN** ela contém um enunciado da forma "É VP quando ..." e um enunciado da forma "É FP quando ..."

### Requirement: Ficha de regra alinhada ao alvo da regra
Cada ficha de regra SHALL descrever a construção que a regra de fato procura, e seus exemplos VP e FP SHALL usar essa mesma construção em contextos opostos.

#### Scenario: Exemplo usa a construção da regra
- **WHEN** a ficha de `missing-ssl-minversion` é consultada
- **THEN** os dois exemplos usam `tls.Config`, e nenhum usa `crypto/md5` ou `crypto/sha1`

#### Scenario: Regra de corretude declarada como tal
- **WHEN** a ficha de uma regra que aponta defeito de corretude e não de segurança (como `invalid-usage-of-modified-variable`) é consultada
- **THEN** a definição declara que a regra é de corretude e a heurística só admite VP quando o defeito tem consequência de segurança alcançável
