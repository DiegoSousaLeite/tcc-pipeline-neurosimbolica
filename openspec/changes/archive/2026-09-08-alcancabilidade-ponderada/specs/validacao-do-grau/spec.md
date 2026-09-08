## ADDED Requirements

### Requirement: Separação entre graus medida sobre uma rodada
O sistema SHALL calcular, a partir dos CSVs de uma rodada, a taxa de detecção observada em cada grau de alcançabilidade, agregando pares e detecções por grupo.

A agregação SHALL ser por grupo — pares somados e detecções somadas — e NÃO a média das taxas por CWE. Uma CWE com 3 pares não pode pesar como uma com 124; a média por CWE deixaria a escala à mercê das caudas pequenas.

Sem essa medição o grau seria afirmação não verificada. Com ela, qualquer rodada existente ou futura devolve a separação real, e o número citado no texto tem procedência.

#### Scenario: Taxa por grau sobre uma rodada
- **WHEN** a validação é executada sobre o diretório de uma rodada
- **THEN** cada grau aparece com o número de CWEs, de pares, de detecções e a taxa agregada

#### Scenario: Agregação, não média de taxas
- **WHEN** um grau contém CWEs com contagens muito diferentes de pares
- **THEN** a taxa do grau é a razão entre detecções somadas e pares somados

#### Scenario: Rodada sem a trilha filtrada não quebra
- **WHEN** a rodada analisada não contém casos da trilha de colheita filtrada
- **THEN** a saída informa a ausência, em vez de falhar ou reportar taxa sobre zero

### Requirement: Validação fora da amostra que gerou o critério
O sistema SHALL permitir aplicar a medição a uma rodada distinta daquela em que o critério foi derivado, e a documentação SHALL declarar que a separação é observada até que isso ocorra.

O critério foi escolhido entre candidatos **olhando** a taxa observada na Rodada 3. Isso gera hipótese, não a valida: ajustar um critério ao resultado e depois apresentá-lo como previsão é circular. A distinção entre "observado nesta amostra" e "previsto para a próxima" precisa sobreviver na ferramenta, não apenas na intenção de quem escreve.

#### Scenario: Medição aplicável a qualquer rodada
- **WHEN** a validação recebe uma rodada que não foi usada para derivar o critério
- **THEN** ela calcula a separação normalmente, permitindo comparar com a observada originalmente

#### Scenario: Robustez à CWE mais influente
- **WHEN** a medição é solicitada excluindo a CWE que mais contribui com detecções
- **THEN** a separação recalculada é reportada, evidenciando se depende de uma única fraqueza
