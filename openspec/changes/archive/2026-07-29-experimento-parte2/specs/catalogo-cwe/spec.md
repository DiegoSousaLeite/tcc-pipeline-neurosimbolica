## ADDED Requirements

### Requirement: Catálogo de triagem por CWE versionado
O sistema SHALL manter um catálogo versionado no repositório com uma ficha por CWE, contendo definição formal, heurística semântica de Go e um par mínimo de exemplos VP/FP.

#### Scenario: Ficha completa
- **WHEN** o catálogo é consultado para uma CWE coberta
- **THEN** a ficha devolvida tem definição, heurística de Go, exemplo VP e exemplo FP, todos não vazios

#### Scenario: Catálogo é a fonte única
- **WHEN** o prompt especialista é montado
- **THEN** tanto a camada de heurística quanto a camada de few-shot vêm da mesma ficha do catálogo

### Requirement: Exemplos escritos à mão a partir de fontes externas
Os exemplos do catálogo SHALL ser escritos manualmente a partir da definição da CWE e da documentação da biblioteca padrão de Go, e SHALL NOT ser extraídos das amostras avaliadas.

#### Scenario: Nenhum trecho vem das amostras
- **WHEN** os exemplos do catálogo são comparados com o conteúdo do dataset e do cache de fontes
- **THEN** nenhum exemplo reproduz trecho de código de uma amostra avaliada

#### Scenario: Par contrastante pela mesma API
- **WHEN** a ficha de CWE-327 é consultada
- **THEN** o exemplo VP e o exemplo FP usam a mesma API (`md5.Sum`) em contextos opostos — hash de senha versus chave de cache/ETag

#### Scenario: Contraste também nas demais fichas
- **WHEN** a ficha de CWE-338 é consultada
- **THEN** o exemplo VP usa `math/rand` para token de sessão e o exemplo FP usa `math/rand` para jitter de backoff

### Requirement: Cobertura do catálogo e fallback
O catálogo SHALL conter fichas específicas para as 15 CWEs de maior volume, cobrindo pelo menos 85% das amostras avaliadas, e SHALL oferecer uma ficha genérica de fallback para as demais.

#### Scenario: Cobertura verificada contra o dataset
- **WHEN** a cobertura do catálogo é medida sobre as locations `.go` do dataset, excluindo arquivos `_test.go`
- **THEN** as CWEs com ficha específica respondem por pelo menos 85% das amostras

#### Scenario: CWE sem ficha específica
- **WHEN** um caso tem uma CWE ausente do catálogo
- **THEN** a ficha genérica de fallback é usada e o caso é executado normalmente

#### Scenario: Origem da ficha registrada
- **WHEN** um caso `DETECTADO` é registrado no CSV
- **THEN** a linha indica se a ficha usada foi específica ou fallback, permitindo estratificar os resultados

### Requirement: Congelamento e rastreabilidade do catálogo
O catálogo SHALL ser congelado antes da primeira rodada do experimento e seu hash criptográfico SHALL ser gravado em cada linha do CSV e no manifesto da rodada.

#### Scenario: Hash em cada linha
- **WHEN** qualquer caso é registrado no CSV
- **THEN** a linha contém o hash do catálogo vigente no momento da execução

#### Scenario: Divergência de hash é detectável
- **WHEN** linhas com hashes de catálogo diferentes existem
- **THEN** a análise comparativa as identifica como pertencentes a versões distintas e não as agrega na mesma tabela sem sinalizar

#### Scenario: Protocolo declarado
- **WHEN** a documentação do projeto é consultada
- **THEN** o protocolo anti-viés está declarado: exemplos escritos a partir da definição da CWE e da documentação da stdlib de Go, sem consulta às amostras, congelados antes da primeira rodada e rastreados por hash
