## Context

`src/fase1_semgrep.py:16` define `SEMGREP_CONFIG = os.environ.get("SEMGREP_CONFIG", "p/default")`
e a linha 140 o passa como um único `--config`. O Semgrep aceita `--config`
repetido e devolve a união num SARIF só, então a mudança de invocação é pequena.
O que não é pequeno é o que ela arrasta: `src/ruleset.py` cacheia o catálogo por
nome de configuração (`_regras_p_default.json`) e o cache simbólico registra "a
versão do ruleset" no singular.

O ganho esperado é concentrado e verificável:

| CWE | Regra do `p/gosec` | O que ela reconhece |
|---|---|---|
| CWE-22 | `gosec.G304-1` | caminho de arquivo construído a partir de variável |
| CWE-918 | `gosec.G107-1` | URL vinda de variável em requisição HTTP |

**Fases tocadas:** 1. As Fases 2 a 5 não mudam.

**Arquivos tocados:** `src/fase1_semgrep.py`, `src/ruleset.py`,
`src/cache_simbolico.py`, `docs/PIPELINE.md`, `docs/SCRIPTS.md`.

**Custo de LLM:** zero nesta change. A medição do ganho é puramente simbólica. Se
o ganho existir, a rodada seguinte terá mais casos `DETECTADO` e portanto mais
chamadas — dimensionar com o número medido em mãos, e não antes.

**Dependências novas:** nenhuma. `p/gosec` é buscado do mesmo registry, pelo
mesmo código, com a mesma dependência (`requests`) que o `p/default` já usa.

## Goals / Non-Goals

**Goals:**

- Fazer CWE-22 e CWE-918 produzirem candidatos, pelo caminho mais barato
  disponível.
- Manter a configuração composta explícita e o padrão inalterado.
- Impedir que acrescentar um ruleset seja servido do cache antigo.
- Medir o ganho antes de adotar.

**Non-Goals:**

- Trocar o `p/default`.
- Tornar o conjunto composto o padrão.
- Escrever regra própria — é `regras-proprias-go`, e depende do resultado desta.
- Reexecutar as Rodadas 1–3.

## Decisions

### D1 — União, nunca substituição

**Decisão:** os rulesets configurados são somados; o conjunto alcançável é a
união dos catálogos; acrescentar um ruleset só pode ampliar.

**Por quê:** trocar já foi avaliado e recusado — o `p/golang` perdia 97 casos que
o `p/default` detectava. A lição foi que cobertura de ruleset não é comparável
por tamanho, e que substituir arrisca perder o que não se sabia que se tinha. A
união não tem esse risco, e o cenário "acréscimo de ruleset só amplia" o fixa
como propriedade verificável em vez de intenção.

### D2 — Identidade do conjunto é insensível à ordem

**Decisão:** a identidade deriva do conjunto, não da sequência.

**Por quê:** a ordem não altera a união dos achados. Fazê-la alterar a identidade
invalidaria o cache inteiro por um detalhe sem significado — e, pior, de forma
intermitente, conforme quem invocasse escrevesse a variável de ambiente numa
ordem ou noutra.

### D3 — Cache de catálogo por ruleset, invalidação por conjunto

**Decisão:** dois níveis. `src/ruleset.py` cacheia o catálogo de cada ruleset
individualmente; o cache simbólico invalida pela identidade do conjunto.

**Por quê:** as duas coisas variam por motivos diferentes. Um catálogo muda
quando o servidor muda aquele ruleset; o conjunto muda quando nós decidimos
acrescentar ou tirar um. Cachear catálogo por conjunto rebuscaria o `p/default`
inteiro toda vez que o `p/gosec` entrasse ou saísse, sem nenhum ganho de
correção.

### D4 — Deduplicação por (arquivo, posição, CWE), e nunca rebaixando o status

**Decisão:** achados de rulesets diferentes no mesmo arquivo, mesma posição e
mesma CWE contam como um. Mesma posição com CWEs diferentes são achados
distintos.

**Por quê:** o número de alertas por arquivo alimenta o diagnóstico de cobertura
simbólica, e sem política ele passaria a medir quantos rulesets cobrem aquele
padrão. A restrição de não rebaixar status é a guarda essencial: deduplicar é
higiene de contagem e não pode, em hipótese alguma, transformar `DETECTADO` em
`NAO_DETECTADO`.

**Alternativa considerada:** não deduplicar. Recusada porque infla a contagem de
alertas de forma que depende da configuração, e a taxa de redução de alertas — a
métrica principal do trabalho — tem essa contagem no denominador.

### D5 — Procedência do ruleset é registrada desde já

**Decisão:** cada ruleset configurado é marcado como de terceiros ou próprio.

**Por quê:** é barato agora e caro depois. `regras-proprias-go` vai introduzir
ruleset mantido neste repositório, e a distinção é metodológica: regra de
terceiros não foi escrita olhando para a nossa população e não levanta a objeção
de ajuste ao conjunto de teste; regra nossa pode ter sido. O manifesto precisa
permitir separar os dois casos sem arqueologia.

## Risks / Trade-offs

**[Ruído demais]** → O `G304` vai disparar em muito código seguro. Isso é o
propósito, não um efeito colateral: o braço neural existe para filtrar. Mas tem
consequência mensurável — a taxa de redução de alertas é calculada sobre um
denominador maior, e o número não será comparável com o das Rodadas 1–3.
Mitigação: reportar a taxa por conjunto de rulesets, nunca fundindo as séries.

**[O ganho não aparecer]** → Plausível. As regras do `p/gosec` podem não casar
com os padrões específicos da nossa população, ou podem declarar CWEs que não
casam com as do gabarito pela regra estrita de identificador completo.
Mitigação: a medição é a Tarefa 4, antes de qualquer repopulação ampla; e o
resultado negativo é informativo — diz que o problema de CWE-22 não é
sintático, o que reforça o caminho do modo entre-arquivos.

**[Colisão com `semgrep-pro-entre-arquivos`]** → As duas changes modificam
`cache-simbolico` e `ruleset-alcancabilidade`. Mitigação: aplicar esta primeiro
— é mais barata e offline — e, na segunda, **fundir** as deltas em vez de
substituir. Os dois eixos são independentes e o requisito final deve registrar
os três: conjunto de rulesets, regra de pareamento e identidade do motor.

**[Invalidação do cache existente]** → Ligar o `p/gosec` invalida o cache
daquela população e força reexecução da Fase 1 nela. É o comportamento correto,
mas é custo de parede. Mitigação: repopular por CWE, começando por CWE-22 e
CWE-918.

## Migration Plan

1. Suporte a múltiplos rulesets com configuração unitária — sem efeito
   observável. Verificar que uma rodada produz alertas idênticos.
2. Identidade composta e invalidação, ainda com configuração unitária.
3. Medição sobre CWE-22 e CWE-918 com `p/default + p/gosec`.
4. Decidir, com o número em mãos, se vale repopular o resto.

**Rollback:** voltar a configuração para `p/default` sozinho. As entradas de
cache do conjunto unitário permanecem em disco e válidas.

## Open Questions

- As regras do `p/gosec` declaram `metadata.cwe` em formato compatível com o
  casamento por identificador completo? Se declararem CWE em texto livre ou com
  identificador diferente do gabarito, o emparelhamento falha e o ganho não
  aparece mesmo com a regra disparando. **Verificar isto na Tarefa 1, antes de
  tudo.**
- As regras do `p/gosec` declaram `metadata.subcategory`? Sem ele,
  `src/ruleset.py` as trata como auditoria e o grau de CWE-22 não sobe, ainda que
  a detecção melhore.
- Quantas regras do `p/gosec` rodam em Go? O `p/default` tem 84 de 1.074; a
  proporção do `p/gosec` é desconhecida e determina o custo de tempo.
- Há sobreposição de identificadores de regra entre os dois rulesets que quebre
  alguma suposição de unicidade em `src/fase1_semgrep.py`?

## Reconhecimento — respostas medidas (Tarefa 1, 2026-09-16)

O reconhecimento foi feito antes de qualquer código, como a Tarefa 1 exige, e
**refuta a premissa da change**. O registro fica aqui porque um resultado
negativo medido vale mais que a suposição que ele substitui.

### O que o `p/gosec` realmente é

Buscado pelo mesmo caminho de `src/ruleset.py`
(`https://semgrep.dev/c/p/gosec` → `cache_simbolico/_regras_p_gosec.json`,
`missed: 0`, então nada foi omitido pelo servidor):

| Medida | Valor |
|---|---|
| Regras no ruleset | **23** |
| Rodam em Go | **23 de 23** (100 %) |
| Declaram `metadata.cwe` | **23 de 23**, no formato `CWE-<n>: <descrição>` |
| Declaram `metadata.subcategory` | **23 de 23** (`vuln` ou `audit`) |
| Regras em modo `taint` | **0** |

O formato de `metadata.cwe` é idêntico ao do `p/default` e o casamento por
identificador completo (`fase1_semgrep._numero_cwe`) o aceita sem adaptação.
As duas primeiras questões em aberto estão respondidas, e favoravelmente — mas
elas deixaram de importar, pelo motivo abaixo.

### As regras que motivaram a change não existem (Tarefa 1.2)

`gosec.G304-1` e `gosec.G107-1` **não constam do `p/gosec`**, e não constam de
nenhum ruleset alcançável do registry. O `p/gosec` publicado não é o gosec
reescrito como regra Semgrep: é um recorte das regras `go.lang.security.*` do
próprio Semgrep. Nenhum identificador contém `gosec`, `G304` ou `G107`.

Verificado também em `p/trailofbits` (120 regras), `p/security-audit`
(225 regras) e `p/go` (404). `p/golang` e `r/go` respondem YAML, não JSON, e
por isso não passam pelo carregamento atual — irrelevante aqui, porque o
`p/golang` já foi avaliado e recusado antes (perdia 97 casos).

### O `p/gosec` é quase inteiramente um subconjunto do `p/default` (Tarefa 1.5)

| Medida | Valor |
|---|---|
| Identificadores em comum com o `p/default` | **22 de 23** |
| Exclusivas do `p/gosec` | **1** — `go.lang.security.audit.unsafe.use-of-unsafe-block` |
| CWEs Go novas que a união traria | **1** — CWE-242 |

A colisão de identificadores é quase total, mas não quebra suposição de
unicidade: o Semgrep desduplica regra de mesmo `id` entre `--config` na própria
invocação, e o mapa `ruleId -> tags` de `fase1_semgrep` é indexado por `id`, de
modo que a colisão o sobrescreve com valor idêntico.

CWE-242 não está na população. **A união não acrescenta uma única regra Go
aplicável ao dataset.**

### Cobertura de CWE-22 e CWE-918: nada muda

Regras Go para as duas CWEs alvo, por ruleset:

| Ruleset | CWE-22 (Go) | CWE-918 (Go) | Novas vs. `p/default` |
|---|---|---|---|
| `p/default` | 2 (`path-traversal-inside-zip-extraction` `audit`; `filepath-clean-misuse` `vuln`/`taint`) | 1 (`tainted-url-host` `vuln`/`taint`) | — |
| `p/gosec` | 1 | 0 | **0** |
| `p/trailofbits` | 0 | 0 | **0** |
| `p/security-audit` | 1 | 0 | **0** |

A única regra de CWE-22 do `p/gosec` é a mesma
`path-traversal-inside-zip-extraction` que o `p/default` já tem.

### Consequência para o grau (Tarefa 1.3)

Não se aplica: a questão do `subcategory` pressupunha uma regra nova cobrindo
CWE-22. Como não há regra nova, o grau de CWE-22 e CWE-918 permanece exatamente
o que é hoje — e permaneceria mesmo que a união fosse implementada.

### Execução real sobre 5 arquivos de CWE-22 (Tarefa 1.4)

`semgrep --config p/default [--config p/gosec] --sarif --quiet` sobre os cinco
primeiros arquivos de CWE-22 com fonte no `cache/`, cada um invocado duas vezes:

| Arquivo | `p/default` | `p/default + p/gosec` | Regras novas |
|---|---|---|---|
| `backend/app/service/database_mysql.go` (`278a56232054`) | 0 | 0 | — |
| `backend/app/service/database_mysql.go` (`39d8b0d98c56`) | 0 | 0 | — |
| `internal/archive/iso9660/iso9660.go` (`84ce6728cb2b`) | 0 | 0 | — |
| `internal/archive/iso9660/utils.go` (`84ce6728cb2b`) | 0 | 0 | — |
| `internal/archive/iso9660/iso9660.go` (`875b27f1d032`) | 0 | 0 | — |
| **TOTAL** | **0** | **0** | **0** |

Zero alertas novos, e zero alertas de qualquer origem — consistente com o
`SEM_ALERTA` que as cinco entradas já registravam no cache simbólico. A medição
confirma o que o catálogo previa: o conjunto composto produz exatamente a mesma
saída que o `p/default` sozinho nestes arquivos.

### Veredito

A Tarefa 1.4 manda **parar e reavaliar antes da seção 2** se não houver alertas
novos. Não há: nem no catálogo, nem por construção. O caminho barato que esta
change propunha não existe da forma como foi descrito.

O resultado é informativo e não neutro, porque fecha uma alternativa: o
problema de CWE-22 e CWE-918 **não se resolve trocando ou somando ruleset
público**. O que falta não é um ruleset que ninguém tinha ligado — é regra que
não existe publicada para Go. Isso empurra a decisão para `regras-proprias-go`
(escrever a regra, assumindo o viés de autoria) ou para
`semgrep-pro-entre-arquivos` (mais alcance no motor, não mais regras), e
**contradiz a recomendação de ordem registrada em `proposal.md`**, que dizia
aplicar esta primeiro por ser mais barata e poder tornar a outra desnecessária.
