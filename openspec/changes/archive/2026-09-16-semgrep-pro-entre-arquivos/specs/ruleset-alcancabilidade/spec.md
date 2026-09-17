## MODIFIED Requirements

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

## ADDED Requirements

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
