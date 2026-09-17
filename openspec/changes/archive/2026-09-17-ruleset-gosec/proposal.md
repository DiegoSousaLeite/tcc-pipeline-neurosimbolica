## Why

As duas maiores CWEs da classe positiva não produzem alerta:

| CWE | Pares | Detecções | O que o `p/default` oferece |
|---|---|---|---|
| CWE-22 | 114 | 0 | 2 regras estreitas |
| CWE-918 | 112 | 1 | 1 regra de taint, intra-arquivo |

O registry do Semgrep publica o ruleset **`p/gosec`**: regras do gosec — o
analisador de segurança para Go — reescritas como regras Semgrep. Entre elas,
`gosec.G304-1`, que dispara sobre caminho de arquivo construído a partir de
variável (CWE-22), e `gosec.G107-1`, que dispara sobre URL vinda de variável em
requisição HTTP (CWE-918).

São regras **sintáticas**: não exigem rastro de fluxo, reconhecem a forma do
código. É por isso que alcançam onde as regras de taint do `p/default` falham —
e é por isso que são ruidosas. Sobre
`os.Open(filepath.Join(base, input))`, o caso canônico que hoje é invisível, o
`G304` dispara; vai disparar também sobre dezenas de usos seguros.

**Ruído não é defeito aqui: é o insumo para o qual a camada neural existe.** Uma
regra ruidosa converte 114 pares de *invisíveis* em *candidatos*, e separar
candidato de vulnerabilidade é a função declarada do braço neural.

Comparado com as alternativas para o mesmo problema, este é o caminho mais
barato e o menos arriscado: mesmo motor, mesma CLI, offline, sem custo, sem
login, e **sem viés de autoria** — as regras são de terceiros, publicadas, e não
foram escritas olhando para a nossa população.

**Pergunta de pesquisa atendida:** **Q3** diretamente, e a metade não respondida
da **Q2** de forma indireta. Parte 2.

## What Changes

- **A Fase 1 passa a aceitar mais de um ruleset.** `SEMGREP_CONFIG` deixa de ser
  um valor e passa a ser uma lista, materializada como `--config` repetido na
  invocação. O padrão continua sendo `p/default` sozinho.
- **Deduplicação declarada.** Um mesmo achado pode vir de regra do `p/default` e
  de regra do `p/gosec`. A política de deduplicação passa a ser decisão
  registrada, não efeito colateral da ordem de leitura do SARIF.
- **Catálogo de alcançabilidade vira união.** `src/ruleset.py` carrega e funde os
  catálogos dos rulesets configurados; hoje cacheia um por nome de configuração.
- **Versão do ruleset no cache simbólico vira composta**, para que acrescentar um
  ruleset invalide o cache daquela população em vez de servir silenciosamente o
  resultado do conjunto antigo.
- **Medição antes de adoção:** rodar sobre CWE-22 e CWE-918 e medir o ganho antes
  de repopular o resto.

## Capabilities

### New Capabilities

- `ruleset-composto`: configuração de mais de um ruleset simultâneo, união dos
  catálogos, deduplicação de achados e identidade composta do conjunto.

### Modified Capabilities

- `cache-simbolico`: a versão do ruleset registrada na entrada passa a
  identificar o **conjunto** de rulesets, não um só.
- `ruleset-alcancabilidade`: o conjunto alcançável passa a ser derivado da união
  dos catálogos configurados.

## Impact

**Código:** `src/fase1_semgrep.py` (invocação e deduplicação), `src/ruleset.py`
(carregamento e união de catálogos), `src/cache_simbolico.py` (identidade
composta), `scripts/` (o que consome `SEMGREP_CONFIG`).

**Fases 2 a 5 não mudam.** A hidratação recebe um alerta; a origem do alerta é
indiferente a ela.

**Custo de LLM:** zero nesta change. A medição de ganho é simbólica. Se o
`p/gosec` funcionar, a rodada seguinte terá mais casos `DETECTADO` e portanto
mais chamadas — decisão separada, a ser dimensionada com o número em mãos.

**Tempo de execução:** dois rulesets custam mais que um, mas ambos são
intra-arquivo. Não há mudança de ordem de grandeza como haveria na análise entre
arquivos.

**Rede:** uma busca a mais no registry, na primeira execução, pelo mesmo caminho
que `src/ruleset.py` já usa para o `p/default`. Depois, cache — a esteira
continua offline sem qualificação nova.

**Resultados invalidados:** nenhum, desde que o ruleset composto entre como
configuração explícita e o padrão continue `p/default` sozinho. As Rodadas 1–3
descrevem o `p/default` e continuam citáveis como tal.

**Conflito com `semgrep-pro-entre-arquivos`:** as duas changes modificam as
mesmas duas capabilities — `cache-simbolico` e `ruleset-alcancabilidade` — em
eixos diferentes (conjunto de rulesets aqui, identidade do motor lá). **Quem
aplicar por segundo precisa fundir as duas deltas, não substituir.**
Recomenda-se aplicar **esta primeiro**: é mais barata, offline, sem portão de
viabilidade, e se resolver CWE-22 pode tornar a outra desnecessária.

## Não-objetivos

- **Não** trocar o `p/default`. A change acrescenta; trocar já foi avaliado e
  recusado (`p/golang` perdia 97 casos).
- **Não** tornar o ruleset composto o padrão. Entra por configuração explícita.
- **Não** escrever regra própria. Isso é `regras-proprias-go`, e só faz sentido
  depois de saber o que o `p/gosec` já cobre.
- **Não** reexecutar as Rodadas 1–3.
- **Não** decidir sobre a rodada completa com o ruleset composto; esta change
  mede o ganho simbólico e para.
