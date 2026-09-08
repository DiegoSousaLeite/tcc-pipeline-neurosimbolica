## ADDED Requirements

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
