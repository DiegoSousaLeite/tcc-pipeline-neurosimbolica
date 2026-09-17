# Arquitetura da Pipeline Neuro-Simbólica

## Visão Geral

A pipeline combina um **motor simbólico** (Semgrep) com um **motor neural**
(LLM Gemini) para triar alertas SAST em código Go. Cada alerta é classificado
como **VP** (verdadeiro positivo — vulnerabilidade real) ou **FP** (falso
positivo — código seguro).

> **Nomenclatura.** O veredito do LLM usa `VP|FP`, em português, exatamente como
> o código grava na coluna `Veredito_LLM` do CSV. As siglas `TP`/`TN` aparecem
> apenas em nomes de trilha herdados (`TP_ouro`, `TP_prata`, `TP_dataset`,
> `TP_alcancavel`) e nos
> arquivos `tp_pairs*.json`, onde designam a *origem* da amostra, não o veredito.

```
       DATASET                TP PAIRS (tp_pairs*.json)        DATASET
  791 FP (seguro)      100 amostras vuln/corrigido (ouro+prata)  57 TP_dataset
                       + TP_alcancavel (colheita filtrada, 0 até o pool existir)
        |                            |                              |
        └────────────────────────────┼──────────────────────────────┘
                                     │ (repo, commit, arquivo, CWE)
                                     v
                            ┌─────────────────┐
                            │  FASE 1         │
                            │  fonte.py       │  cache → clone local → rede
                            │  + Semgrep      │
                            │  p/default      │
                            └────────┬────────┘
                                     │ DETECTADO (alerta) | NAO_DETECTADO
                                     v
                            ┌─────────────────┐        ┌──────────────────┐
                            │  FASE 2         │◄──────►│ cache_simbolico/ │
                            │  Middleware     │        │ (alerta+contexto)│
                            │  extrai_funcao  │        └──────────────────┘
                            │  → contexto     │   uma vez por caso, reusado
                            └────────┬────────┘   pelos 4 braços
                                     │ contexto hidratado (byte-a-byte igual)
                                     v
              ┌──────────────────────┴──────────────────────┐
              │            FASE 3/4 — matriz 2x2            │
              │  prompts/{baseline,especialista}.md         │
              │      x  src/provedores/{gemini,openai}.py   │
              │  data/catalogo_cwe.json → 3 camadas         │
              │  temperatura=0 → VP ou FP                   │
              └──────────────────────┬──────────────────────┘
                                     │ veredito + justificativa + tokens/custo
                                     v
                            ┌─────────────────┐
                            │  FASE 5         │
                            │  Auditoria      │  results/<run_id>/
                            │  CSV + matrizes │  1 CSV por braço + manifesto
                            └─────────────────┘
```

**O LLM é um filtro puro do Semgrep:** não há bypass da Fase 1. Nenhuma amostra
chega ao LLM sem que o Semgrep tenha disparado antes, o que é exatamente a
condição de uso real da ferramenta — só se tria o que foi alertado.

---

## Por que Semgrep (e não CodeQL)

Durante o piloto (~48 alertas), o CodeQL quase não casou com o gabarito do
dataset: apenas 1 alerta alinhado. O dataset é de origem Semgrep, portanto
re-rodar o Semgrep no mesmo arquivo/commit localiza o alerta exato. Além disso:

- Semgrep roda nativamente no Windows (sem build step Go).
- É *sanitizer-aware* e emite a linha exata; CodeQL emite trilhas de fluxo.

O fluxo CodeQL original vive no histórico do Git (ver `legacy/README.md`); os
resultados que ele produziu estão em `legacy/resultados_parte1/`.

### Por que o ruleset é `p/default` e não `p/golang`

O `p/golang` é enxuto e perdia ~97 dos 261 alertas do dataset por simples falta
de regra (CWE-665/79/470/400/…), que virariam `NAO_DETECTADO` artificiais. O
`p/default` é o recorte amplo do registry e reproduz as CWEs do gabarito. O
ruleset em uso entra no cache simbólico e no manifesto da rodada
(`SEMGREP_CONFIG`, padrão `p/default`).

### Modo entre-arquivos (`--entre-arquivos`) — desligado por padrão

O Semgrep CE rastreia *taint* apenas **dentro de um arquivo**. Medido: **0 de
807 alertas** do corpus trouxeram trilha de dataflow, mesmo com
`--dataflow-traces`. O Semgrep Pro acrescenta análise entre arquivos, e
`--entre-arquivos` a liga (`--pro` na invocação).

**Ligar a flag não é reversível de graça.** Ela muda o conjunto de alertas que a
camada simbólica emite, invalida o cache simbólico daquela população pelo eixo
do motor, e torna a rodada **incomparável com as Rodadas 1–3**, que mediram o
CE. Por isso ela vem desligada, e a invocação padrão monta exatamente a mesma
linha de comando de antes de o modo existir.

Pedir o modo sem um registro de viabilidade aprovado **aborta**, em vez de cair
no CE em silêncio — o modo de falha a evitar é aquele em que a rodada produz
números do CE rotulados como Pro, e nada no CSV denuncia. O registro vem de
`scripts/verificar_pro.py` (ver `docs/SCRIPTS.md`).

**O que a medição de 2026-09-15 encontrou**, com conta gratuita e Semgrep
1.167.0:

| | resultado |
|---|---|
| Disponibilidade no tier gratuito | **funciona** — projeto controlado: CE 0 trilhas entre arquivos, Pro 1 |
| Trilhas em repositórios reais | 9, em 3 de 10 repositórios |
| Custo | **4–6× mais lento** (`seaweedfs`: 124 s → 749 s) |
| Ganho nos casos do gabarito | **nenhum em 6 casos medidos** (3 de CWE-22, 3 de CWE-918): o arquivo do gabarito não muda de veredito em nenhum. No `seaweedfs`, 849 alertas no repositório e **0** nos dois arquivos do caso, nos dois modos |

Os casos continuaram `SEM_ALERTA` com `regras_nao_casadas=[]`, com o repositório
inteiro em volta: **nenhuma regra olha aqueles arquivos**. Isso é cobertura de
regra, não alcance — e alcance entre arquivos não conserta arquivo que regra
nenhuma examina. A ressalva é o tamanho da amostra: 6 casos de 226, escolhidos
por espaçamento e não por sorteio, com um sétimo (`gogs`) perdido por timeout.
O enunciado vale para os casos avaliados, não para a população.

Reproduzir: `python scripts/verificar_pro.py --etapa gabarito --casos-por-cwe 3`.

---

## Os Dois Fluxos de Entrada

### Fluxo FP (791 casos do dataset)

Cada caso vem do `data/dataset_go_limpo.json`:

| Campo do dataset     | Uso na pipeline               |
|----------------------|-------------------------------|
| `finding_id`         | ID único do caso (`#i` por location) |
| `repo_name`          | Chave do cache / URL de download |
| `commit_hash`        | Commit exato do arquivo-alvo  |
| `to_analyzer.locations[].file` | Arquivo alvo (uma amostra por location `.go`) |
| `metadata.cwe_id`    | Filtro do alerta Semgrep      |
| `metadata.cwe_name`  | Enriquecimento do prompt      |
| `to_analyzer.description` | Enriquecimento do prompt |
| `ground_truth=false_positive` | `gabarito=seguro`  |

A Fase 1 re-executa o Semgrep no arquivo exato do commit marcado pelo dataset,
reproduzindo o alerta original. Se o alerta casa com a CWE → DETECTADO; caso
contrário → NAO_DETECTADO (ponto cego simbólico, entra só na matriz de cobertura).

#### Regra de pareamento: casamento explícito de CWE

Um alerta é emparelhado ao caso **somente** quando a regra que o emitiu declara a
CWE do gabarito nas suas tags. É condição necessária e suficiente: o número de
alertas no arquivo não é critério, e não há aproximação por família de CWE.

A comparação é por identificador inteiro, e não por substring — `CWE-20`,
`CWE-77` e `CWE-79` são prefixos de `CWE-200`/`CWE-209`, `CWE-770` e `CWE-798`,
todos presentes na população, e um casamento textual emparelharia o caso à regra
errada sem que nada no CSV denunciasse. Quando mais de um alerta casa, o
escolhido é o primeiro por `(linha inicial, check_id)`, e não o primeiro da saída
do Semgrep, cuja ordem é detalhe interno da ferramenta.

Existiu aqui um fallback que aceitava o alerta quando ele era o único do arquivo,
para cobrir regra sem tag de CWE explícita. Ele foi removido: não distinguia "a
regra não declara CWE" de "a regra declara OUTRA CWE", e era o segundo grupo que
dominava. O efeito era assimétrico por construção e caía sobre a trilha TP — do
lado FP o gabarito veio do próprio Semgrep, então a CWE sempre casa com alguma
regra; do lado TP o gabarito vem de CVE/CVEfixes, e não há razão para que exista
regra do `p/default` com aquela tag naquele arquivo.

#### Taxonomia da não-detecção

`NAO_DETECTADO` tem dois motivos, registrados em coluna própria do CSV:

| Motivo | Significado |
|--------|-------------|
| `SEM_ALERTA` | o Semgrep não emitiu alerta algum sobre o arquivo |
| `ALERTA_OUTRA_CWE` | emitiu alertas, mas nenhum casa com a CWE do gabarito |

Os dois continuam em `Status_Semgrep = NAO_DETECTADO` e entram na mesma célula da
matriz de cobertura — a CWE rotulada de fato não foi detectada nos dois casos. O
motivo não vira valor novo de status de propósito: o checkpoint por tripla, o
cache simbólico e as métricas comparam a string `NAO_DETECTADO` diretamente, e um
terceiro valor quebraria cada um deles em silêncio.

Em `ALERTA_OUTRA_CWE` os `check_id` das regras que dispararam sem casar vão para
`Regras_Nao_Casadas`, deduplicados e em ordem alfabética. É o que sustenta a
leitura de que "o Semgrep leu o arquivo, mas enxergou outra fraqueza" —
afirmação diferente de "o Semgrep não viu nada" — sem re-executar a pipeline.

#### Amostragem: todas as `locations`, só `.go`

O dataset agrega por `cwe_per_commit` — cada entrada reúne todos os achados
daquela CWE naquele commit, e `num_findings == len(locations)` em 259 dos 261
alertas `false_positive`. Do lado FP, portanto, cada location é **um achado
independente e rotulado**, não uma vulnerabilidade atravessando arquivos; usar só
`locations[0]` descartava amostras válidas. (Isso vale **só** para o lado FP —
ver "Assimetria de rótulo entre as trilhas", abaixo.)

Das 871 locations, 791 (91%) são `.go`; o restante são relatórios `.html` do Snyk
e front-end (`.tsx`, `.js`, `.vue`) presentes no mesmo commit. Como o CWE do
gabarito é sempre de um achado Go, esses casos só produziriam `NAO_DETECTADO` em
massa, então a pipeline filtra para Go:

| Recorte | Casos FP |
|---------|---------:|
| `locations[0]` apenas (antigo) | 261 |
| todas as locations | 871 |
| **todas, só `.go` (padrão atual)** | **791** |

`--uma-location` volta ao recorte antigo; `--todas-extensoes` inclui os arquivos
não-Go.

> O índice no ID do caso vem da posição **original** na lista de locations (antes
> de qualquer filtro), então mudar o filtro nunca renumera casos e os CSVs
> antigos continuam apontando para o mesmo arquivo.

### Fluxo TP (100 casos, de pares reconstruídos)

Cada par em `tp_pairs*.json` representa um CVE real em dois commits. O par vira
**duas amostras independentes**, que entram na Fase 1 no mesmo formato dos FPs
— o que muda é só o commit:

| Amostra     | Commit          | `gabarito`   | Significado                        |
|-------------|-----------------|--------------|------------------------------------|
| `:vuln`     | `parent_commit` | `vulneravel` | Antes do fix — o LLM deve dizer VP |
| `:fix`      | `fix_commit`    | `seguro`     | Após o fix — o LLM deve dizer FP   |

Nada é pré-hidratado: o arquivo-alvo é resolvido pelo `src/fonte.py` e o Semgrep
roda normalmente. Amostras vulneráveis que o Semgrep não reproduz viram
**Semgrep FN** na matriz de cobertura, e não chegam ao LLM — é o custo de o LLM
ser filtro puro, e é justamente o ponto cego que a matriz 1 existe para medir.

**Três pools de pares:**
- `TP_ouro` (`tp_pairs.json`): 32 amostras. CVEs do dataset com função
  explicitamente marcada.
- `TP_prata` (`tp_pairs_osv.json`): 68 amostras. CVEs da OSV harvest, sem
  filtragem pelo dataset.
- `TP_alcancavel` (`tp_pairs_osv_alcancavel.json`): a colheita da OSV já
  filtrada pelas CWEs que o ruleset alcança. Fica vazia enquanto o pool não
  existe em disco, e a contagem 0 aparece no cabeçalho da execução — trilha
  vazia não pode passar despercebida antes de uma rodada.

**Por que trilha própria, e não sobrescrita do pool da `TP_prata`.** Sobrescrever
`tp_pairs_osv.json` apagaria os pares inalcançáveis que sustentam o achado dos
70,1 %, e `tp_pairs.json` é irrecuperável — só `scripts/tp_reconstruct.py` o
regenera, e ele exige o histórico git completo dos repositórios, que não está
mais em disco. Separar as duas trilhas é também o que permite dizer, depois da
rodada, se o ganho de amostra veio da colheita filtrada ou apenas do
reaproveitamento de pares antigos: sem essa distinção não há como avaliar se o
filtro funcionou. A coluna `Origem` do CSV já carrega o rótulo da trilha, então a
contagem por procedência é um agrupamento, sem código de auditoria novo.

Os 17 pares já alcançáveis dos pools antigos **continuam contando como `TP_ouro`
e `TP_prata`**: aproveitá-los significa não descartá-los, não movê-los de trilha.
Os IDs da trilha nova levam o prefixo `TPA:` para que, se a colheita reencontrar
um par já presente num pool antigo, o identificador colidido não faça dois casos
distintos virarem o mesmo na tripla de checkpoint.

**Por que os casos de CWE inalcançável permanecem na população.** Eles são
resultado, não ruído: sustentam a afirmação de que 70,1 % das fraquezas do corpus
estão fora do alcance da análise sintática. E não contaminam a matriz de acerto
do LLM, porque nunca chegam a ela — sem emparelhamento na Fase 1 não há chamada
de LLM. Entram na matriz de **cobertura**, onde são ponto cego, que é o que de
fato são. O custo aceito é que o recall do Semgrep continua baixo, porque o
denominador inclui os inalcançáveis: é a realidade sendo medida.

CVEs cujo advisory da OSV não traz CWE são descartados na geração
(`tp_reconstruct.py`): sem tag de CWE a Fase 1 não tem como casar o alerta, e o
caso viraria ponto cego artificial — lacuna de metadado, não falha do Semgrep.

### Fluxo TP_dataset (57 casos, do próprio dataset)

As 36 entradas com `ground_truth="true_positive"` do
`data/dataset_go_limpo.json` nunca eram carregadas: `construir_casos_fp`
descarta tudo que não é `false_positive`. `construir_casos_tp_dataset` as carrega
com `gabarito=vulneravel` e `origem=TP_dataset`.

Não é redundante com a trilha ouro: a trilha ouro analisa o `parent_commit` do
fix, com um arquivo por par; aqui vale o `commit_hash` **em que o SastBench de
fato escaneou**, com todas as locations. A interseção é de 10 alvos, e só 11 dos
36 CVEs viraram par.

| Passo | Alvos |
|---|---:|
| locations `.go` das 36 entradas | 108 |
| alvos distintos `(repo, commit, arquivo, CWE)` | 66 |
| menos arquivos `_test.go` | −9 |
| **casos da trilha** | **57** |

IDs levam o prefixo `TPD:` para não colidir com nada gravado nos CSVs da Parte 1.
O índice de location vem da posição original na lista, antes de qualquer filtro.

### Assimetria de rótulo entre as trilhas (limitação declarada)

`metadata.source` é **`semgrep`** nas 261 entradas `false_positive` e
**`cvefixes`** nas 36 `true_positive`. As duas metades não foram rotuladas do
mesmo jeito:

- Do lado **FP**, o rótulo é um julgamento *por alerta*: aquele achado, naquele
  arquivo, é falso positivo. Cada location é um alvo distinto (791 locations,
  791 alvos).
- Do lado **TP**, o rótulo vem de mineração de commit de fix: ele afirma que o
  *commit* corrigiu uma CVE, **não** que cada arquivo listado é a
  vulnerabilidade. As locations são as **funções** tocadas pelo commit, então o
  mesmo arquivo se repete (108 locations para 66 alvos).

Evidência concreta: a entrada de **CVE-2025-27616 / CWE-290** (`go-vela/server`)
tem **11 locations**, uma delas `router/middleware/header_test.go` — um arquivo
de teste, que por construção não é a vulnerabilidade.

Mitigações aplicadas (nenhuma elimina a assimetria, que exigiria reanotação
manual, fora de escopo):

1. Descarte de `_test.go` na trilha `TP_dataset` — 9 dos 66 alvos.
2. Deduplicação por `(repo, commit, arquivo, CWE)`, a mesma chave do cache
   simbólico: a pipeline analisa o arquivo inteiro, então duas locations no
   mesmo arquivo dariam o mesmo veredito duas vezes.
3. Coluna `Num_Locations` no CSV, contada **antes** de qualquer filtro, para
   permitir restringir a análise a entradas de location única — rótulo mais
   confiável — sem reexecutar o experimento.

### População total

| Origem | Casos | Gabarito |
|---|---:|---|
| FP (dataset) | 791 | seguro |
| TP_ouro (`tp_pairs.json`) | 32 | 16 vuln + 16 seguro |
| TP_prata (`tp_pairs_osv.json`) | 68 | 34 vuln + 34 seguro |
| TP_dataset (dataset) | 57 | vulnerável |
| TP_alcancavel (`tp_pairs_osv_alcancavel.json`) | **1380** | 690 vuln + 690 seguro |
| **Total** | **2328** | **797 vulneráveis / 1531 seguros** |

> **Atualizado em 2026-09-08.** O pool da colheita filtrada existe: 810
> candidatas → **690 pares** → 1380 casos, e a população foi de 948 para **2328**
> (rodada `20260908T094808Z-9a00cb2`, ver `docs/ANALISE-RODADA-3.md`). Sem o pool
> em disco a trilha entra com 0 e o total volta a 948, que é o das rodadas
> anteriores.

Com a trilha nova a população cresce e deixa de ser comparável **caso a caso** com
as rodadas antigas — a comparação legítima passa a ser entre braços dentro da
rodada nova. As rodadas anteriores permanecem em disco, comparáveis entre si.

---

## As Duas Matrizes

### Matriz 1 — Cobertura do Semgrep

Avalia o motor simbólico vs. o gabarito. Responde: *o Semgrep está detectando
corretamente?*

|                    | Semgrep DETECTOU | Semgrep NÃO DETECTOU |
|--------------------|-----------------|----------------------|
| `gabarito=seguro`  | **Semgrep FP** (ruído) | **Semgrep VN** (silêncio correto) |
| `gabarito=vulneravel` | **Semgrep VP** (acerto) | **Semgrep FN** (ponto cego) |

Aplica-se a **todos** os casos, FP e TP. As amostras vulneráveis dos pares TP
são a única fonte de `gabarito=vulneravel`, portanto sem elas as células
**Semgrep VP** e **Semgrep FN** ficariam vazias e a linha de baixo da matriz não
existiria.

### Matriz 2 — Acerto do LLM

Avalia o motor neural vs. o gabarito. Responde: *o LLM está triando corretamente?*

|                    | LLM disse VP     | LLM disse FP          |
|--------------------|-----------------|----------------------|
| `gabarito=vulneravel` | **VP (Acerto)** | **FN (Falha Crítica)** |
| `gabarito=seguro`  | **FP (Ruído Mantido)** | **VN (Acerto)** |

Aplica-se aos casos em que o LLM foi chamado — ou seja, `Status_Semgrep =
DETECTADO`. Casos `NAO_DETECTADO` só aparecem na matriz 1.

---

## Métricas (Seção 3.5 do TCC)

Calculadas pelo `src/metricas.py`, sobre uma rodada (`results/<run_id>/`) ou
sobre um CSV avulso:

| Métrica | Fórmula | Significado |
|---|---|---|
| Precisão | VP / (VP + FP_LLM) | dos alertas que o LLM manteve, quantos eram reais |
| Recall | VP / (VP + FN_LLM) | das vulnerabilidades reais, quantas o LLM manteve |
| F1 | 2·P·R / (P + R) | média harmônica Precisão/Recall |
| MCC | (VP·VN − FP·FN) / √((VP+FP)(VP+FN)(VN+FP)(VN+FN)) | correlação de Matthews |
| TRA | (VN + FN_LLM) / total | taxa de redução de alertas: fração da pilha que o LLM descartou |
| Prop. FP filtrados | VN / (VN + FP_LLM) | especificidade: dos alertas seguros, quantos foram descartados |
| TFN | FN_LLM / (VP + FN_LLM) | taxa de falsos negativos (= 1 − Recall) |

**TRA e TFN andam juntas.** A TRA mede quanto volume saiu da fila do
desenvolvedor; sozinha, ela é maximizada por um filtro que descarta tudo. A TFN
é o preço disso — a fração de vulnerabilidades reais jogadas fora. Reportar uma
sem a outra é enganoso.

### Comparação entre braços

`python src/metricas.py results/<run_id> --mcnemar --estratificar --latex`

- **Tabela lado a lado**: uma linha por braço, com matriz de confusão, as sete
  métricas e o custo em USD. A matriz de cobertura do Semgrep é reportada
  **separadamente** e uma vez só — ela não depende do braço.
- **Estratificação** por trilha de origem, por `Num_Locations`
  (1 / 2-6 / 7+) e por origem da ficha de CWE (`especifica` / `fallback`),
  sem reexecutar a pipeline.
- **McNemar pareado** entre cada par de braços, restrito aos `ID_Caso` que
  ambos classificaram com veredito válido — um caso que virou erro de esteira
  em um dos braços não é evidência sobre nenhum dos dois. Com `b + c < 25`
  discordâncias usa-se o binomial exato; acima, qui-quadrado com correção de
  continuidade de Yates. Implementado em Python puro (`math.comb`,
  `math.erfc`), coerente com a decisão de não depender de scipy.
- **Export LaTeX**: `tabela_bracos.tex` e `tabela_mcnemar.tex` no diretório da
  rodada, com ambientes `tabular` prontos para `\input{}`.

### Avisos que saem antes dos números

- **Poder estatístico limitado**, quando menos de 30 amostras vulneráveis
  chegaram ao LLM com veredito válido. É esse número — não o total de casos —
  que determina o poder do teste: as células VP e FN saem só dele.
- **Divergência de hash de catálogo**, quando o conjunto analisado tem linhas
  produzidas por versões diferentes de `catalogo_cwe.json`. Elas não são
  comparáveis entre si e não podem ser agregadas na mesma tabela sem
  sinalização.

---

## Catálogo de Triagem por CWE

`data/catalogo_cwe.json` é a fonte **única** das duas camadas do prompt
especialista que dependem da CWE: a heurística semântica e o par few-shot
VP/FP. Uma ficha por CWE, com quatro campos:

| Campo | Conteúdo |
|---|---|
| `definicao` | 1 a 3 frases derivadas da descrição do MITRE |
| `heuristica_go` | o sinal concreto a procurar em Go (pacote, função, padrão de chamada) **e** a condição que separa VP de FP |
| `exemplo_vp` | `{codigo, porque}` — Go válido, ~5 a 15 linhas |
| `exemplo_fp` | `{codigo, porque}` — a **mesma API**, em contexto oposto |

**Cobertura.** 15 fichas específicas mais `__fallback__`. Medido por
`scripts/ranking_cwe.py` sobre as locations `.go` do dataset, excluindo
`_test.go`: 878 amostras em 49 CWEs, e as 15 fichas cobrem **85,4%** delas. Uma
CWE fora do catálogo usa a ficha genérica e roda normalmente; o CSV grava
`Ficha_CWE ∈ {especifica, fallback}` para permitir estratificar os resultados.

**Par contrastante pela mesma API.** É o ponto central do catálogo: se o par
contrastasse APIs diferentes, o modelo aprenderia a reconhecer a API em vez de
julgar o contexto. Exemplos: `md5.Sum` para hash de senha (VP) versus `md5.Sum`
para chave de cache (FP); `math/rand` para token de sessão (VP) versus
`math/rand` para jitter de backoff (FP).

### Protocolo anti-viés

As fichas são escritas **à mão**, exclusivamente a partir de:

1. a definição formal da CWE no catálogo MITRE, e
2. a documentação da biblioteca padrão de Go.

É **proibido** consultar, inspecionar ou se inspirar em qualquer amostra do
material avaliado — o dataset de alertas, os arquivos em `cache/` ou qualquer
CSV de resultados. Nenhum trecho de código de uma amostra aparece nos exemplos.
Sem essa restrição, o conjunto few-shot carregaria informação do conjunto de
avaliação e os resultados do experimento não teriam validade.

A tarefa foi especificada como briefing autocontido em
`openspec/changes/archive/2026-07-29-experimento-parte2/tasks.md`, destacável do
repositório:
quem a executa **não tem como** consultar as amostras, então o protocolo é
satisfeito por construção, não por promessa.

Por que não extrair os exemplos das próprias amostras: a interseção de CWEs
entre as trilhas FP e TP é de apenas 5 de 26 (CWE-22, 79, 352, 400, 918). Para
as CWEs que carregam quase todo o volume — 79, 327, 94, 319, 338 — **não existe
nenhum VP real disponível** no material; e os poucos que existem são escassos
demais para canibalizar sem contaminar o conjunto de avaliação.

### Congelamento e rastreabilidade

O catálogo é congelado **antes da primeira rodada** e o SHA-256 dos bytes do
arquivo vai para cada linha do CSV (`Hash_Catalogo`) e para o manifesto da
rodada. Uma linha cujo hash difere do arquivo atual foi produzida por outra
versão do catálogo e não pode ser agregada na mesma tabela sem sinalização —
`src/metricas.py` avisa quando encontra hashes distintos.

Hash da versão congelada (2026-07-29, 16 fichas, 24.581 bytes):

```
a81b6f5ca3a4f70c2cdbca1436fd138ccc84976ee981aa1726e3dff9ae4e4311  data/catalogo_cwe.json
```

Conferência: `python -c "from src.catalogo import Catalogo; print(Catalogo.carregar().sha256)"`.

Garantias verificadas por `tests/test_catalogo.py` e por `gofmt`:

- os 32 exemplos de código são Go válido (`gofmt -e`, zero erros) e estão
  formatados por `gofmt`;
- em 15 das 16 fichas o par VP/FP compartilha a API central — a exceção é
  `__fallback__`, que por ser genérica não tem API específica e contrasta a
  **origem** do dado (externa versus constante do binário);
- a prosa e os comentários dos exemplos estão em português acentuado.
  Identificadores e valores de literais ficam em ASCII, por convenção da
  linguagem.

> A rodada `results/piloto-gemini/` foi executada com uma versão anterior do
> catálogo e **não pode ser agregada** às rodadas seguintes.
> `src/metricas.py` sinaliza a divergência ao encontrar hashes distintos.

---

## Fase 0 — Preparação de Dados TP

Executada manualmente antes da pipeline principal. Ordem:

```
osv_harvest_go.py  →  tp_fetch_fixes.py  →  fetch_raso.py  →  tp_reconstruct.py
```

1. `osv_harvest_go.py` — coleta CVEs Go na OSV, gera
   `data/tp_fixes_osv_alcancavel.json`.
2. `tp_fetch_fixes.py` — preenche `fix_commit` em `data/tp_fixes.json` via OSV API.
3. `fetch_raso.py` — cria esqueletos git em `repos/` e faz `git fetch --depth 2`
   só dos commits de fix (fix + pai). Um clone de histórico inteiro custaria
   dezenas de GB para entregar os mesmos dois commits por CVE.
4. `tp_reconstruct.py` — gera `tp_pairs_osv.json` (prata) ou `tp_pairs.json` (ouro).

Depois de rodar o `preencher_cache.py`, `repos/` pode ser apagado: os
arquivos-alvo já estão no cache e a pipeline não toca mais em git.

### Por que a colheita filtra por alcançabilidade

A colheita da etapa 1 aceitava qualquer CWE. O efeito só apareceu na Rodada 2:
**70,1 % dos 107 casos vulneráveis** da rodada `20260731T140000Z-af9bc32` têm CWE
que nenhuma regra Go do `p/default` declara (`docs/ANALISE-RODADA-2.md` §3.1, que
mede o mesmo do lado do resultado: o recall sobre a CWE rotulada é 0,0093).
Esses casos são **indetectáveis por construção** — o motor não pode falhar em
achar o que não sabe procurar, e o recall medido sobre eles mede a lacuna do
catálogo de regras, não a capacidade do motor.

A causa é viés de seleção em relação ao instrumento medido. As duas classes
foram montadas por caminhos opostos: a segura veio **de achados do Semgrep**
(SastBench), então sua CWE é a CWE de alguma regra por construção — 95,8 % dela é
alcançável; a positiva veio de CVEs via OSV, sem nunca consultar o ruleset —
29,9 % alcançável.

Desde então `osv_harvest_go.py` consulta `src/ruleset.py` e recusa a candidata
cuja CWE nenhuma regra da linguagem declara, contabilizando cada recusa sob a CWE
que a causou. `scripts/pares_alcancaveis.py` aponta os 17 pares já colhidos que
são aproveitáveis sem recolheita. Os pools antigos são **preservados**: os pares
inalcançáveis são a evidência do achado, não lixo a limpar.

Alcançável não é o mesmo que detectável — a regra existir não garante que dispare
naquele código, porque ela procura um padrão sintático específico. A restrição
remove o que é impossível por construção, não o que é difícil.

**`tp_reconstruct.py` é o único componente que precisa de histórico git.** Por
isso `tp_pairs*.json` são versionados, e não gitignorados como os demais
artefatos gerados: regenerá-los custa refazer o fetch dos ~70 repos.

O dataset FP (`data/dataset_go_limpo.json`) não requer Fase 0; o `src/fonte.py`
resolve cada arquivo-alvo sozinho, sem git.

---

## Cache de Fontes (`cache/`)

A pipeline consome, por caso, **um arquivo `.go` em um commit**: a Fase 1 roda o
Semgrep sobre esse arquivo isolado (que no engine OSS é todo o escopo de análise
disponível) e a Fase 2 relê o mesmo arquivo para hidratar a função. Clonar o
histórico completo custava ~67 GB para entregar poucos MB de código.

`src/fonte.py` resolve cada arquivo nesta ordem:

1. **cache** — `cache/<owner>__<repo>/<commit>/<caminho>.go`;
2. **clone local** — `git show <commit>:<arquivo>`, sem checkout e sem tocar a
   working tree, se `repos/` existir;
3. **rede** — `raw.githubusercontent.com` no commit exato.

Como a chave é imutável (repo + SHA + caminho), **o cache nunca invalida**: uma
vez preenchido, a pipeline roda offline e o experimento é reproduzível a partir de
alguns MB. `repos/` deixou de ser obrigatório; se existir, é aproveitado.

**A invariante é "buscar uma vez, congelar, reexecutar offline" — e não "sem
rede".** A distinção importa porque a esteira tem três etapas que buscam: o
cache de fontes (`raw.githubusercontent.com`), o cache do ruleset
(`semgrep.dev/c/<config>`, busca anônima) e, se o modo entre-arquivos for
ligado, o Semgrep Pro (busca **autenticada**: `semgrep login` e
`semgrep install-semgrep-pro`). As três acontecem no PREENCHIMENTO. Nenhuma
acontece na reexecução: com o cache simbólico completo, a rodada fecha sem
login, sem download de binário e sem rede — verificado em 2026-09-15, 2328
casos servidos do cache em 1 s, com o Semgrep não sendo invocado uma única vez.

```bash
# Popula o cache a partir dos clones locais, sem rede (ANTES de apagar repos/)
python scripts/preencher_cache.py --somente-local

# Em outra máquina, sem os clones: baixa o que faltar
python scripts/preencher_cache.py
```

---

## Cache do Resultado Simbólico

`src/cache_simbolico.py` persiste, por caso, o resultado das Fases 1 e 2:
alerta do Semgrep, contexto hidratado, status, motivo da não-detecção e regras
não casadas, mais **três eixos de invalidação** — a versão do ruleset, a da
regra de pareamento e a identidade do motor. Chave:
`(repo, commit, arquivo, CWE)`. Arquivos em
`cache_simbolico/<owner>__<repo>/<commit>/<hash-do-caminho>__<cwe>[__pro].json`.

Os três eixos variam por motivos independentes: o ruleset muda quando o Semgrep
passa a enxergar coisas diferentes, a regra de pareamento quando a pipeline
passa a aceitar como do caso um conjunto diferente de alertas, e o motor quando
o alcance da análise muda. Espremer um dentro do outro faria o mesmo ruleset
parecer duas coisas, e perderia a capacidade de responder "este alerta veio de
qual motor?" sem reexecutar.

Entrada gravada **antes** de a identidade do motor existir é lida como
`ce, entre_arquivos=False` — é factualmente verdade, não havia outro motor
quando ela foi escrita. É o **oposto** da regra de pareamento, que trata
ausência como divergente: lá a ausência significa que o conteúdo pode estar
errado sob a regra nova; aqui significa só que o campo não existia.

Serve a dois propósitos, um de custo e um de validade:

1. **Custo.** Sem ele, cada braço da matriz reexecutaria o Semgrep nos 948
   casos — inclusive nos `NAO_DETECTADO`, que são a maioria e onde o Semgrep
   gasta tempo sem gerar chamada de LLM. Cacheado, os braços 2 a 4 fazem só a
   chamada de LLM.
2. **Validade interna.** O `contexto_hidratado` é gravado como string exata e é
   *ela* que alimenta os quatro braços. Isso garante contexto **byte-a-byte
   idêntico** entre eles: sem isso, uma diferença de veredito poderia vir de
   uma diferença de entrada, não do braço.

**Por que é separado de `cache/`.** O cache de fontes guarda o conteúdo de um
arquivo num commit: a chave é imutável por construção (um SHA não muda), então
ele nunca invalida. O resultado simbólico depende da versão do ruleset do
Semgrep, que muda. Por isso `versao_ruleset` entra no payload e uma divergência
invalida a entrada **daqui**, sem tocar em um byte de `cache/`. Uma entrada
invalidada é ignorada, não apagada: ela continua sendo evidência do que aquele
ruleset produziu.

**Dois eixos de invalidação.** `versao_pareamento` acompanha `versao_ruleset` no
payload, e divergência em qualquer um dos dois invalida a entrada — inclusive
quando o campo está ausente, que é o estado das entradas gravadas antes de ele
existir. Os eixos variam por motivos independentes: o ruleset muda quando o
Semgrep passa a enxergar coisas diferentes, a regra de pareamento muda quando a
pipeline passa a aceitar como do caso um conjunto diferente de alertas. A
invalidação por pareamento alcança também os `NAO_DETECTADO`: o status deles
continuaria correto — endurecer o pareamento nunca transforma não-detecção em
detecção —, mas eles não sabem informar qual dos dois motivos os produziu, e são
a maioria da população. É o que torna uma mudança de regra de pareamento uma
varredura completa do Semgrep, e não parcial.

Desativação: `--sem-cache-simbolico` reexecuta as Fases 1 e 2 sempre.

---

## Camada de Provedores de LLM

`src/provedores/` isola a rede do resto da pipeline. O eixo "modelo" da matriz
só é variável independente se trocar de provedor não mudar mais nada:

| Arquivo | Papel |
|---|---|
| `base.py` | `RespostaLLM`, protocolo `ProvedorLLM`, backoff, validação de schema |
| `gemini.py` | REST `generateContent`, chave em `x-goog-api-key` |
| `openai.py` | REST `/v1/chat/completions`, chave em `Authorization: Bearer` |
| `ollama.py` | REST `/api/chat` num servidor local, **sem chave** |
| `precos.py` | tabela de preços por 1M de tokens, datada e versionada |

Decisões que afetam os números:

- **Chave em header, nunca na URL.** Na Parte 1 a chave ia na query string de
  `URL_API_GEMINI`, onde vazava em log de URL, traceback e proxy.
- **Backoff exponencial com jitter** (`5s · 2ⁿ · U(0,5;1,5)`, teto de 120 s),
  respeitando `Retry-After` quando presente, no lugar dos delays fixos
  `[10, 30, 60]`. O intervalo mínimo por provedor (`GEMINI_MIN_INTERVALO`)
  continua valendo, agora por provedor e compartilhado entre os braços de
  prompt do mesmo modelo.
- **Validação de schema.** `veredito ∈ {VP, FP}` e justificativa não vazia.
  Resposta fora do schema vira **`ERROR`**, com o texto bruto truncado na
  justificativa — **nunca `FP`**. Contar uma falha de esteira como "o modelo
  achou seguro" inventaria um verdadeiro negativo.
- **Custo é derivado, não medido.** A API devolve contagem de tokens, não valor
  cobrado. A tabela de `precos.py` tem data de consulta e vai para o manifesto
  da rodada; sem ela o custo total não é auditável.

---

## Provedor Local (Ollama)

Terceiro ponto do eixo "modelo": um modelo aberto rodando na máquina do
pesquisador. Custo marginal zero, sem cota, e o código-fonte de terceiros nunca
sai da máquina — é a resposta à pergunta de viabilidade on-premise da abordagem.
**Não** substitui os braços comerciais nem entra em `--matriz`: só roda quando
nomeado.

### Preparação

```bash
# 1. Instalar o Ollama (https://ollama.com/download) e subir o serviço
ollama serve                       # ou o aplicativo, que já sobe o serviço

# 2. Baixar o modelo
ollama pull qwen2.5-coder:7b

# 3. Conferir que a inferência coube na GPU
ollama run qwen2.5-coder:7b "oi" && ollama ps   # coluna PROCESSOR: 100% GPU
```

Se `ollama ps` mostrar CPU, os vereditos são os mesmos, mas o throughput cai
~10x. O manifesto registra qual foi o caso — é nota de viabilidade, não
resultado.

### Escolha de modelo por VRAM

Referência para os 8 GB da RX 7600 desta máquina, em quantização Q4:

| Modelo | Peso residente | Cabe nos 8 GB? |
|---|---|---|
| `qwen2.5-coder:7b` | ~4,7 GB | sim (validado, `100% GPU`) |
| `gemma2:9b` | ~5,4 GB | sim, com menos folga de cache KV |
| `qwen2.5-coder:14b` | ~9 GB | não: offload parcial para CPU, 3–6x mais lento |
| `deepseek-coder-v2:16b` | ~8,9 GB | não: idem (mistura de especialistas ameniza) |

Trocar de modelo é só trocar o `--modelo`; não há código novo para nenhum deles.

### Uso

```bash
# Braço local, prompt especialista
python run_pipeline.py --tudo --modelo ollama:qwen2.5-coder:7b --prompt especialista

# Braço local junto de um comercial, nos dois prompts
python run_pipeline.py --tudo --modelo ollama:qwen2.5-coder:7b \
    --modelo gemini-2.5-flash-lite --prompt baseline --prompt especialista
```

O namespace `ollama:` é obrigatório e explícito. Sem ele não haveria como
distinguir `gemma2` (modelo aberto do Google, local) de `gemini` (API do mesmo
Google), e um erro de digitação cairia em "modelo sem provedor conhecido" em vez
de "modelo não instalado".

### Variáveis de ambiente

| Variável | Padrão | Para quê |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | endereço do servidor |
| `OLLAMA_NUM_CTX` | `8192` | janela de contexto pedida em toda requisição |
| `OLLAMA_TIMEOUT` | `600` | segundos por requisição (cobre o carregamento dos pesos) |

### Truncamento silencioso de contexto — o ponto de atenção

O padrão do servidor é `num_ctx = 4096` e **o excedente é descartado sem aviso**:
nenhuma exceção, nenhum campo de erro. Um veredito emitido sobre um arquivo Go
visto pela metade entraria no CSV indistinguível de um veredito legítimo. É o
modo de falha mais perigoso do braço local, e por isso a pipeline:

1. fixa `num_ctx` explicitamente em toda requisição, sem herdar o padrão;
2. **antes** da chamada, recusa prompt cuja estimativa (`len/3.5`, que
   superestima em código) passe de `num_ctx - num_predict`, sem gastar GPU;
3. **depois** da chamada, transforma em `ERROR` a resposta cujo
   `prompt_eval_count` encoste no teto, cujo `done_reason` seja `length` ou que
   venha com `done: false` (o servidor abortou a geração no meio), mesmo que o
   JSON tenha vindo bem-formado;
4. registra a janela efetiva, o digest, a quantização e a semente no manifesto.

Para escolher `num_ctx` com medida em vez de chute:

```bash
python scripts/medir_prompts.py                  # distribuição por tipo de prompt
python scripts/medir_prompts.py --num-ctx 16384  # quantos casos estourariam
```

### Verificação prévia e reprodutibilidade

Antes do primeiro caso, a rodada sonda o servidor uma vez (`/api/version`,
`/api/tags`, `/api/show`) e **aborta** se ele estiver fora do ar ou se a tag não
estiver instalada — nomeando o endereço tentado, os modelos disponíveis e o
`ollama pull` correspondente. Sem isso, um `ollama serve` esquecido produziria
uma linha `ERROR` por caso, cada uma depois de quatro tentativas com backoff.

A sondagem também é o que alimenta o bloco `modelos_locais` do manifesto:
versão do servidor, **digest**, quantização, tamanho de parâmetros, janela
máxima declarada, `num_ctx` efetivo, semente e GPU/CPU. O digest importa porque
`qwen2.5-coder:7b` é ponteiro mutável no registry, igual a `latest`: sem ele um
número do capítulo de resultados não é reatribuível aos pesos que o geraram — é
o mesmo raciocínio do `sha256` do catálogo de CWE.

Determinismo é aproximado: temperatura 0 e semente fixa (42) não garantem
reprodução bit a bit entre versões do servidor, quantizações ou divisões
GPU/CPU. O que se afirma é "geração determinística dentro da configuração
registrada".

### O que NÃO é afrouxado para o braço local

Nada. Mesma validação de schema, mesmo número de tentativas, mesmo
`format: "json"` sem enum forçado — o Ollama aceitaria um JSON Schema que
restringisse a saída a `VP`/`FP`, e usá-lo eliminaria do braço local uma
modalidade de falha ("respondeu `TALVEZ`") que Gemini e GPT continuam correndo.
A taxa de `ERROR` é um dos números comparados: se o modelo de 7B erra mais o
formato, isso é **resultado a reportar**, não defeito a corrigir.

O que muda por necessidade física: `timeout` de 600 s (contra 60 s), sem
intervalo mínimo entre chamadas (não há cota) e `keep_alive` de 30 min (sem ele
o servidor descarrega o modelo após 5 min ociosos e a chamada seguinte paga de
novo os ~15 s de carregamento).

### Custo zero declarado

`Custo_USD` é zero em toda linha do braço local, e os tokens continuam sendo
gravados. No manifesto isso aparece em `modelos_locais_sem_custo`, separado de
`modelos_sem_preco` — os dois custam zero, mas por motivos opostos: o primeiro é
zero por construção, o segundo é anomalia (alguém esqueceu de tabelar o preço).

### Comparabilidade

Um braço local **não é comparável** aos comerciais em nada além do veredito:
latência e custo saem de regimes diferentes, e a máquina é de uso geral, sem
controle de carga. O texto da monografia precisa dizer isso ao apresentar a
tabela.

---

## Matriz Experimental 2x2

A mesma população roda sob N braços `(modelo, tipo de prompt)`. As Fases 1 e 2
rodam **uma vez por caso**, fora do laço de braços.

| | `baseline` | `especialista` |
|---|---|---|
| **`gemini-2.5-flash-lite`** | controle | metodologia completa |
| **`gpt-4o-mini`** | controle | metodologia completa |

- **Checkpoint pela tripla `(ID_Caso, Modelo_LLM, Tipo_Prompt)`.** Indexar só
  por `ID_Caso` faria o segundo braço achar tudo pronto e sair vazio — falha
  silenciosa. Linhas dos CSVs da Parte 1, sem as colunas novas, são atribuídas
  ao braço `(gemini-2.5-flash-lite, especialista)`.
- **O LLM continua filtro puro do Semgrep.** `NAO_DETECTADO` não dispara
  chamada em braço nenhum, em nenhuma combinação.
- **Saída em `results/<run_id>/`**, `run_id` = timestamp UTC + commit curto. Um
  CSV por braço (`<modelo>__<prompt>.csv`) e um `manifesto.json` com run_id,
  commit, comando, versão do Semgrep e do ruleset, hash do catálogo, hashes dos
  prompts, braços, tabela de preços, contagem por trilha e horários. Rodadas não
  se sobrescrevem, e nenhum CSV novo aparece na raiz.

### Custo da matriz

A matriz multiplica por 4 o número de chamadas de LLM sobre os casos
`DETECTADO`. O cache simbólico corta o tempo de parede (as Fases 1 e 2 rodam uma
vez por caso, não uma por braço), mas **não reduz o número de chamadas**.

O tier grátis do Gemini (20 req/dia por modelo) é inviável para a rodada final —
billing é pré-requisito. Cada linha do CSV grava `Tokens_Entrada`, `Tokens_Saida`
e `Custo_USD`, derivado da tabela datada em `src/provedores/precos.py`, então o
custo é acompanhável desde o piloto.

---

## Fluxo de Dados no CSV de Resultados

```
ID_Caso            → identificador único (finding_id[#i] para FP; TPD:<id>[#i] para
                     TP_dataset; repo:cwe:func:vuln|fix para os pares TP, com o
                     prefixo TPA: nos da TP_alcancavel)
Repositorio        → nome do repo (ex: argoproj/argo-cd)
CWE                → ex: CWE-89
Origem             → FP | TP_ouro | TP_prata | TP_dataset | TP_alcancavel
Modelo_LLM         → ex: gemini-2.5-flash-lite
Tipo_Prompt        → baseline | especialista
Gabarito           → vulneravel | seguro
Status_Semgrep     → DETECTADO | NAO_DETECTADO | <erro>
Classificacao_Semgrep → Semgrep VP/VN/FP/FN | N/A
Veredito_LLM       → VP | FP | ERROR | N/A
Classificacao_LLM  → Verdadeiro Positivo (Acerto) | Verdadeiro Negativo (Acerto)
                     | Falso Positivo (Ruído Mantido) | Falso Negativo (Falha
                     Crítica) | Erro de Inferência | N/A
Tempo_Execucao_s   → float em segundos
Justificativa      → reasoning do LLM ou mensagem de erro
--- colunas da Parte 2 ---
Num_Locations      → locations da entrada de origem, ANTES de qualquer filtro
Ficha_CWE          → especifica | fallback | N/A
Versao_Prompt      → hash curto do template (ex: especialista:d1145f8b)
Hash_Catalogo      → SHA-256 do catalogo_cwe.json vigente na execução
Tokens_Entrada     → tokens do prompt, reportados pela API
Tokens_Saida       → tokens da resposta
Custo_USD          → derivado de src/provedores/precos.py
Motivo_Nao_Deteccao → SEM_ALERTA | ALERTA_OUTRA_CWE | N/A
Regras_Nao_Casadas → check_id das regras que dispararam sem casar com a CWE do
                     gabarito, separados por ';' e em ordem alfabética; vazio
                     fora de ALERTA_OUTRA_CWE
```

`<erro>` é uma das categorias de `src/fase5_auditoria.py`: `FETCH_FAIL`,
`SEMGREP_TIMEOUT`, `SEMGREP_ERROR`, `SEMGREP_FILE_NOT_FOUND`, `API_ERROR`,
`ERRO_DESCONHECIDO` (mais `CLONE_FAIL`/`CHECKOUT_FAIL`, legado dos CSVs
anteriores ao cache). Casos em erro ficam fora das duas matrizes e são
reprocessados na execução seguinte — o checkpoint só considera concluído quem
terminou em estado válido.

> Os CSVs da Parte 1 estão em `legacy/resultados_parte1/` e **não são
> comparáveis** com os da Parte 2: a população mudou (entrou a trilha
> `TP_dataset`) e o cabeçalho ganhou sete colunas. Ver o `README.md` daquele
> diretório.

---

## Correspondência com o Texto do TCC

| Seção do TCC     | Componente da pipeline             |
|------------------|------------------------------------|
| Seção 3.1 Dataset| `data/dataset_go_limpo.json`       |
| Seção 3.2 Fase 1 | `src/fase1_semgrep.py` + `src/fonte.py` |
| Seção 3.3 Fase 2 | `src/fase2_middleware.py`          |
| Seção 3.3 Fase 3 | `src/fases3_4_llm.py`             |
| Seção 3.4 TPs    | `scripts/tp_reconstruct.py` + pares|
| Seção 3.5 Métricas| `src/metricas.py`                 |
| Seção 3.6 Auditoria| `src/fase5_auditoria.py`         |
