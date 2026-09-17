# ruleset-alcancabilidade

## Purpose

Responder, a partir do catálogo de regras do motor simbólico, quais CWEs ele é capaz de detectar numa dada linguagem.

Existe porque a pergunta *"o motor tem regra para esta CWE neste arquivo?"* é pressuposto de tudo que se propõe a montar população para o Semgrep triar, e a resposta vinha sendo obtida de forma ad-hoc. Em `docs/ANALISE-RODADA-2.md`, 70,1% dos casos vulneráveis têm CWE que nenhuma regra Go do `p/default` declara — sem esta consulta, população assim entra na rodada e o motor não tem como detectá-la.

A alcançabilidade é por linguagem e o casamento é por identificador completo de CWE, reaproveitando a comparação vigente no pareamento. Uma segunda cópia da comparação divergiria no primeiro ajuste, e o defeito a evitar é justamente o casamento por substring que o pareamento acabou de corrigir: se a alcançabilidade aceitasse por um critério e o pareamento recusasse por outro, a colheita produziria casos que a Fase 1 descartaria.
## Requirements

### Requirement: Conjunto de CWEs alcançáveis derivado do ruleset
O sistema SHALL determinar, a partir do ruleset em uso **e do motor em uso**, o conjunto de CWEs que o motor simbólico é capaz de detectar numa dada linguagem. O conjunto SHALL ser derivado do catálogo de regras a cada consulta, e NÃO SHALL ser uma lista fixa no código.

O ruleset é configurável por `SEMGREP_CONFIG`. Uma lista fixa passaria a mentir no instante em que ele mudasse, e mentiria em silêncio — não há como um valor embutido no código perceber que o catálogo do servidor mudou.

O motor é o segundo eixo pelo mesmo argumento. O catálogo do registry descreve as regras da edição aberta; o modo entre-arquivos acrescenta regras próprias, que não constam daquele catálogo, e altera o alcance das regras que constam — uma regra de taint que hoje só enxerga dentro do arquivo passa a atravessar arquivos. Uma consulta que ignore o motor subestimaria a cobertura em silêncio, que é exatamente o defeito que esta capability foi criada para evitar.

Enquanto a consulta não souber enumerar as regras próprias do modo entre-arquivos, ela SHALL declarar essa limitação em vez de omiti-la: um conjunto derivado apenas do catálogo aberto é **limite inferior** da cobertura do motor com o modo ligado, e tratá-lo como exato recusaria população que o motor teria detectado.

#### Scenario: CWE declarada por regra da linguagem é alcançável
- **WHEN** alguma regra do ruleset declara a CWE e tem a linguagem consultada em `languages`
- **THEN** a CWE consta do conjunto alcançável

#### Scenario: CWE ausente do ruleset não é alcançável
- **WHEN** nenhuma regra do ruleset declara a CWE
- **THEN** a CWE não consta do conjunto alcançável

#### Scenario: Conjunto acompanha o ruleset configurado
- **WHEN** o ruleset configurado muda
- **THEN** o conjunto é recalculado a partir do novo catálogo, sem edição de código

#### Scenario: Conjunto acompanha o motor configurado
- **WHEN** a consulta é feita para o motor com modo entre-arquivos e para o motor sem ele
- **THEN** os dois resultados são distinguíveis, e o do modo entre-arquivos nunca é subconjunto próprio do outro

#### Scenario: Cobertura do modo entre-arquivos é declarada como limite inferior
- **WHEN** a consulta é feita para o motor com modo entre-arquivos e o catálogo disponível não enumera as regras próprias desse modo
- **THEN** o conjunto é devolvido acompanhado da informação de que é limite inferior, em vez de apresentado como exato

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

### Requirement: Grau ordinal de alcançabilidade
O sistema SHALL classificar cada CWE, por linguagem, em um grau ordinal de alcançabilidade derivado dos atributos declarados das regras que a cobrem, e SHALL preservar a consulta binária existente sem alterá-la.

A consulta binária responde "existe regra?", e a Rodada 3 mediu que essa resposta comporta realidades muito diferentes: entre os 690 pares da trilha filtrada, as CWEs cobertas apenas por regras de auditoria renderam 1 detecção em 336 pares (0,30 %), contra 17 em 354 (4,80 %) das demais. Metade do orçamento de colheita foi gasta onde a ferramenta nunca afirmou detectar vulnerabilidade.

O grau SHALL vir de campo declarado pelas regras — nunca de uma lista de CWEs embutida no código. Uma lista fixa passaria a mentir no instante em que o ruleset mudasse, e mentiria em silêncio; é a mesma razão pela qual o conjunto alcançável é derivado do catálogo em vez de fixado.

Os eixos SHALL ser dois, ambos declarados na regra:
- se a regra afirma detectar vulnerabilidade ou apenas sinalizar para auditoria;
- se a regra depende de rastreio de dados corrompidos, que o motor não resolve entre arquivos.

#### Scenario: CWE coberta por regra que afirma vulnerabilidade, sem depender de taint
- **WHEN** ao menos uma regra da CWE naquela linguagem declara subcategoria de vulnerabilidade e não opera em modo de taint
- **THEN** a CWE recebe o grau mais alto

#### Scenario: CWE coberta apenas por regras de taint
- **WHEN** todas as regras de vulnerabilidade da CWE operam em modo de taint
- **THEN** a CWE recebe grau intermediário, porque o motor não rastreia fluxo entre arquivos e a vulnerabilidade real frequentemente atravessa camadas

#### Scenario: CWE coberta apenas por regras de auditoria
- **WHEN** nenhuma regra da CWE declara subcategoria de vulnerabilidade
- **THEN** a CWE recebe o grau mais baixo, ainda que seja alcançável pelo critério binário

#### Scenario: Grau é por linguagem, como a alcançabilidade
- **WHEN** a mesma CWE é coberta por regras de qualidades diferentes em duas linguagens
- **THEN** os graus consultados são independentes entre si

#### Scenario: Consulta binária permanece inalterada
- **WHEN** uma CWE de grau mais baixo é consultada pelo critério binário
- **THEN** ela continua sendo alcançável, e a Fase 1 continua respeitando a mesma fronteira de antes

#### Scenario: Metadado ausente degrada, não quebra
- **WHEN** uma regra não declara o campo de subcategoria ou o declara com vocabulário desconhecido
- **THEN** ela é tratada como regra de auditoria e nenhuma exceção é levantada, de modo que o pior caso seja o comportamento binário de hoje

### Requirement: Rendimento previsível antes da colheita
O sistema SHALL expor o grau de alcançabilidade no relatório da colheita, ao lado da contagem de candidatas por CWE.

A colheita é a etapa que compromete rede, disco e horas de varredura. Saber antes de gastar que uma CWE tem grau baixo é a diferença entre dimensionar e descobrir depois: na Rodada 3, CWE-22 e CWE-400 consumiram 238 pares e produziram zero detecções.

#### Scenario: Relatório traz o grau junto da contagem
- **WHEN** a colheita termina e imprime a distribuição por CWE
- **THEN** cada CWE aparece com seu grau de alcançabilidade

#### Scenario: Restrição por grau é opcional e registrada
- **WHEN** a colheita é executada restringindo o grau mínimo aceito
- **THEN** a restrição é aplicada e o valor usado fica registrado no relatório

#### Scenario: Sem restrição, a colheita não muda
- **WHEN** a colheita é executada sem pedir grau mínimo
- **THEN** ela aceita exatamente as mesmas candidatas que aceitaria antes desta mudança

Restringir por grau muda o denominador do recall: passa a medir o motor sobre as fraquezas em que ele afirma detectar, e não sobre as que declara cobrir. É decisão de método, não de conveniência, e por isso SHALL ser explícita na invocação em vez de padrão.

### Requirement: Grau de taint reflete o alcance do motor
O sistema SHALL considerar o alcance do motor ao atribuir o grau de alcançabilidade às CWEs cobertas apenas por regras de taint. Com o modo entre-arquivos ativo, essas CWEs NÃO SHALL ser rebaixadas ao grau intermediário pelo motivo que hoje as rebaixa.

O grau intermediário existe porque "o motor não rastreia fluxo entre arquivos e a vulnerabilidade real frequentemente atravessa camadas". Essa justificativa é uma propriedade do motor CE, não da CWE. Mantê-la sob um motor que rastreia entre arquivos faria a escala descrever uma limitação que deixou de existir, e a colheita continuaria evitando exatamente as CWEs que a troca de motor pretendia destravar.

A escala SHALL permanecer ordinal e os graus SHALL continuar derivados de campos declarados pelas regras — esta mudança altera como o eixo de taint é interpretado, não de onde ele vem.

#### Scenario: CWE de taint sob motor entre-arquivos
- **WHEN** todas as regras de vulnerabilidade da CWE operam em modo de taint e o motor com modo entre-arquivos está em uso
- **THEN** a CWE recebe o grau mais alto, e não o intermediário

#### Scenario: CWE de taint sob motor CE
- **WHEN** todas as regras de vulnerabilidade da CWE operam em modo de taint e o motor CE está em uso
- **THEN** a CWE recebe o grau intermediário, exatamente como antes desta mudança

#### Scenario: Eixo de auditoria não é afetado pelo motor
- **WHEN** nenhuma regra da CWE declara subcategoria de vulnerabilidade
- **THEN** a CWE recebe o grau mais baixo sob qualquer motor, porque nenhuma análise de fluxo transforma regra de auditoria em afirmação de vulnerabilidade

#### Scenario: Validação do grau é refeita por motor
- **WHEN** a separação empírica entre os graus é medida
- **THEN** ela é medida separadamente por motor, porque a escala passa a ter significado diferente em cada um e a evidência de um não sustenta o outro
