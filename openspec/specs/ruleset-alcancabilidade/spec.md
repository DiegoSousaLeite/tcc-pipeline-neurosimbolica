# ruleset-alcancabilidade

## Purpose

Responder, a partir do catálogo de regras do motor simbólico, quais CWEs ele é capaz de detectar numa dada linguagem.

Existe porque a pergunta *"o motor tem regra para esta CWE neste arquivo?"* é pressuposto de tudo que se propõe a montar população para o Semgrep triar, e a resposta vinha sendo obtida de forma ad-hoc. Em `docs/ANALISE-RODADA-2.md`, 70,1% dos casos vulneráveis têm CWE que nenhuma regra Go do `p/default` declara — sem esta consulta, população assim entra na rodada e o motor não tem como detectá-la.

A alcançabilidade é por linguagem e o casamento é por identificador completo de CWE, reaproveitando a comparação vigente no pareamento. Uma segunda cópia da comparação divergiria no primeiro ajuste, e o defeito a evitar é justamente o casamento por substring que o pareamento acabou de corrigir: se a alcançabilidade aceitasse por um critério e o pareamento recusasse por outro, a colheita produziria casos que a Fase 1 descartaria.

## Requirements

### Requirement: Conjunto de CWEs alcançáveis derivado do ruleset
O sistema SHALL determinar, a partir do ruleset em uso, o conjunto de CWEs que o motor simbólico é capaz de detectar numa dada linguagem. O conjunto SHALL ser derivado do catálogo de regras a cada consulta, e NÃO SHALL ser uma lista fixa no código.

O ruleset é configurável por `SEMGREP_CONFIG`. Uma lista fixa passaria a mentir no instante em que ele mudasse, e mentiria em silêncio — não há como um valor embutido no código perceber que o catálogo do servidor mudou.

#### Scenario: CWE declarada por regra da linguagem é alcançável
- **WHEN** alguma regra do ruleset declara a CWE e tem a linguagem consultada em `languages`
- **THEN** a CWE consta do conjunto alcançável

#### Scenario: CWE ausente do ruleset não é alcançável
- **WHEN** nenhuma regra do ruleset declara a CWE
- **THEN** a CWE não consta do conjunto alcançável

#### Scenario: Conjunto acompanha o ruleset configurado
- **WHEN** o ruleset configurado muda
- **THEN** o conjunto é recalculado a partir do novo catálogo, sem edição de código

### Requirement: Alcançabilidade é por linguagem
O sistema SHALL considerar apenas as regras cuja lista `languages` inclui a linguagem consultada. Uma CWE coberta somente por regras de outras linguagens NÃO SHALL ser considerada alcançável para a linguagem consultada.

Nenhuma regra de Python ou Java dispara sobre um arquivo `.go`. Tratar a CWE como alcançável porque o ruleset a cobre "em abstrato" produziria exatamente o erro que motiva estas mudanças: população que o motor não tem como detectar.

O campo `languages` é hoje descartado no carregamento das regras e precisa ser preservado.

#### Scenario: Regra de outra linguagem não torna a CWE alcançável
- **WHEN** a CWE é declarada apenas por regras cuja `languages` não inclui a linguagem consultada
- **THEN** ela não consta do conjunto alcançável para essa linguagem

#### Scenario: Mesma CWE alcançável em uma linguagem e não em outra
- **WHEN** a CWE é declarada por regra de uma linguagem e por nenhuma de outra
- **THEN** a consulta devolve resultados diferentes conforme a linguagem consultada

### Requirement: Casamento por identificador completo de CWE
O sistema SHALL comparar identificadores de CWE pelo número inteiro, nunca por prefixo textual, reaproveitando a comparação já vigente na Fase 1 em vez de reimplementá-la.

`CWE-77` e `CWE-770` são fraquezas distintas, assim como `CWE-20` contra `CWE-200`/`CWE-209` e `CWE-79` contra `CWE-798` — todos presentes na população. O casamento por substring foi um defeito corrigido na Fase 1 (`VERSAO_PAREAMENTO` 2); reimplementá-lo aqui o reintroduziria por outra porta.

O campo `metadata.cwe` de uma regra SHALL ser aceito tanto como string única quanto como lista, porque as duas formas ocorrem no ruleset e iterar a string caminharia por caracteres.

#### Scenario: Prefixo não é casamento
- **WHEN** consulta-se `CWE-77` e o ruleset só declara `CWE-770`
- **THEN** `CWE-77` não é considerada alcançável

#### Scenario: metadata.cwe como string única
- **WHEN** uma regra declara `metadata.cwe` como string em vez de lista
- **THEN** a CWE dela é extraída corretamente, sem percorrer caracteres

#### Scenario: Zeros à esquerda são a mesma CWE
- **WHEN** a regra declara `CWE-077` e consulta-se `CWE-77`
- **THEN** há casamento

#### Scenario: Texto sem CWE não casa
- **WHEN** a tag da regra não contém identificador de CWE algum
- **THEN** ela não contribui com CWE alguma para o conjunto

### Requirement: Operação offline a partir do cache do ruleset
O sistema SHALL operar sem rede quando o ruleset já estiver em cache local, mantendo a invariante do projeto de que a pipeline roda offline a partir dos caches.

#### Scenario: Consulta servida do cache
- **WHEN** o ruleset já está em cache e não há rede
- **THEN** o conjunto de CWEs alcançáveis é calculado normalmente

#### Scenario: Ausência de cache e de rede é erro explícito
- **WHEN** não há cache do ruleset nem rede disponível
- **THEN** a falha é reportada claramente, em vez de devolver conjunto vazio — conjunto vazio faria toda CWE parecer inalcançável e recusaria a população inteira em silêncio
