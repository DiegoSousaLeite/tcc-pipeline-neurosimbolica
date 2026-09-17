# Mapa: o que mudou na pipeline e o que isso exige do LaTeX

**Documento de acumulação, não de execução.** Serve para registrar o que já está
decidido e medido, para que a redação seja feita de uma vez quando o experimento
estiver fechado. Nada aqui foi escrito no `.tex`.

Última atualização: 2026-09-08, após a Rodada 3 (`20260908T094808Z-9a00cb2`).

Caminho base: `TCC2___Diego_Sousa_e_João_Artur_Leles/editaveis/`

---

## 0. Estado atual do LaTeX

Verificado por varredura dos 13 arquivos `.tex` (1.062 linhas):

- **Nenhum número das Rodadas 1, 2 ou 3 está no texto.** Não há ocorrência de
  `948`, `107`, `0,9874`, `70,1`, `823` ou `McNemar` em arquivo algum.
- O capítulo `provadeconceito.tex` documenta o **piloto da Parte 1** (Gemini,
  `gemini-2.5-flash-lite`), não a bateria da Parte 2.
- **Não existe capítulo de resultados.** A ordem em `tcc.tex` é
  `introducao` → `referencialteorico` → `metodologia` → `provadeconceito` →
  `consideracoes`.

Ou seja: o trabalho de redação é majoritariamente **acrescentar**, não corrigir.
As exceções estão na §1.

---

## 1. Correções — afirmações hoje factualmente erradas

Estas não dependem de nenhuma decisão pendente. São afirmações que a medição já
contradisse e que ficariam incorretas em qualquer versão do trabalho.

### 1.1 As três frases sobre *taint* (PRIORIDADE)

**Medição:** dos 807 alertas emitidos pelo Semgrep OSS sobre o corpus, **zero**
traziam trilha de *taint*, mesmo com `--dataflow-traces`. Nas CWEs deste corpus
não há fluxo a rastrear que a ferramenta OSS registre no SARIF.

| arquivo | linha | o que diz hoje | problema |
|---|---|---|---|
| `metodologia.tex` | 73 | *"o SARIF conterá [...] o rastreio do fluxo de dados desde a origem (source) até o sink, por meio do taint mode"* | O SARIF produzido **não** contém isso. Afirmação sobre o artefato de saída, verificável e falsa. |
| `referencialteorico.tex` | 50 | *"Por meio do taint mode, o Semgrep acompanha o trânsito [...] Esse achado localizado [...] constitui o insumo primário consumido pelos modelos"* | Descreve corretamente o Semgrep **Pro**; o insumo real da pipeline é o alerta pontual mais o contexto hidratado pelo middleware, sem trilha. |
| `referencialteorico.tex` | 54-55 | Figura `fig:taint` — *"Análise de taint: o trânsito de dados não confiáveis da origem ao ponto crítico"* | A figura ilustra um mecanismo que não opera nesta pipeline. |

**Encaminhamento sugerido:** manter a explicação de *taint* no referencial como
**capacidade da categoria de ferramentas** (é conteúdo teórico legítimo), e
separar explicitamente o que a edição OSS usada entrega. A distinção
OSS × Pro vira material de discussão, não erro a esconder.

> O slide 8 da apresentação já está correto neste ponto — usar como referência
> de redação.

### 1.2 O braço neural não é "modelo de fronteira via API"

`introducao.tex:65` descreve a inferência como *"processados via API por modelos
de linguagem de fronteira"*. A bateria da Parte 2 rodou em
**`ollama:qwen2.5-coder:7b`, local, quantizado Q4\_K\_M, 100 % GPU, sem API e sem
custo**. Precisa refletir o arranjo real — e isso resolve de passagem o
apontamento **G3** da banca (Ollama).

### 1.3 A meta "TFN próxima a zero" não se sustenta como escrita

`metodologia.tex:309` fixa como objetivo empírico *"maximizar o VN mantendo a TFN
próxima a zero"*. **TFN medida no braço especialista: 0,8421** (16 FN em 19
amostras). O texto precisa ou reformular a meta, ou declarar que ela não foi
atingida e por quê — sobre 19 amostras, a TFN não é conclusiva de todo modo.

---

## 2. Números prontos para entrar

Todos de `results/20260908T094808Z-9a00cb2`, detalhados em
`docs/ANALISE-RODADA-3.md`. Reprodução:
`python src/metricas.py results/20260908T094808Z-9a00cb2 --mcnemar`

### 2.1 Configuração experimental (vai para `metodologia.tex`)

| campo | valor |
|---|---|
| modelo | `ollama:qwen2.5-coder:7b`, digest `dae161e27b0e` |
| quantização | Q4\_K\_M, 7,6 B parâmetros, 100 % GPU |
| `num_ctx` / `num_predict` / semente | 8192 / 512 / 42 |
| Semgrep | 1.167.0, ruleset `p/default` |
| catálogo de CWE | sha256 `e5db7d400842…`, 15 fichas |
| prompts | `baseline:597fcfa9`, `especialista:d1145f8b` |
| custo | **zero** (execução local) |

### 2.2 População (vai para `metodologia.tex` ou capítulo novo)

| trilha | casos | vulneráveis | seguros |
|---|---|---|---|
| `FP` (SastBench) | 791 | 0 | 791 |
| `TP_ouro` | 32 | 16 | 16 |
| `TP_prata` | 68 | 34 | 34 |
| `TP_dataset` | 57 | 57 | 0 |
| `TP_alcancavel` | 1380 | 690 | 690 |
| **total** | **2328** | **797** | **1531** |

### 2.3 Resultado principal (capítulo de resultados)

| braço | n | VP | VN | FP | FN | **TRA** |
|---|---|---|---|---|---|---|
| baseline | 825 | 8 | 690 | 116 | 11 | 0,8497 |
| especialista | 827 | 3 | 796 | 12 | 16 | **0,9819** |

Estabilidade da TRA do especialista entre rodadas — **é o argumento mais forte do
trabalho**, porque atravessa três populações diferentes:

| | Rodada 1 | Rodada 2 | Rodada 3 |
|---|---|---|---|
| população | 948 | 948 | **2328** |
| TRA especialista | 0,9851 | 0,9874 | **0,9819** |

### 2.4 McNemar (capítulo de resultados)

| | Rodada 2 | Rodada 3 |
|---|---|---|
| n pareado | 789 | **825** |
| só especialista acerta | 100 | **104** |
| só baseline acerta | 0 | **5** |
| χ² (Yates) | 98,01 | **88,11** |
| p-valor | < 0,0001 | **< 0,0001** |

### 2.5 Cobertura simbólica (capítulo de resultados + limitações)

`n = 2326` · VP 19 · VN 723 · FP 806 · FN 778 · Recall **0,0238** · TFN 0,9762

> **Cuidado ao comparar com rodadas anteriores.** TRA simbólica e proporção de FP
> filtrados dependem da composição da população, que mudou. A TRA simbólica salta
> de 0,1660 para 0,6453 sem que o motor tenha mudado — é diluição. Ver
> `ANALISE-RODADA-3.md` §4.3.

### 2.6 O que NÃO pode ser reportado

`Recall`, `F1`, `MCC` e `TFN` do **eixo neural**: descansam sobre 19 amostras
vulneráveis, contra o mínimo de 30. O próprio `src/metricas.py` emite o aviso de
poder estatístico limitado. Isso precisa aparecer no texto como decisão
metodológica declarada, não como omissão.

---

## 3. Achados novos que pedem espaço no texto

Estes não existem no LaTeX em forma alguma e são o que o trabalho ganhou de
substância desde o TCC 1.

### 3.1 O funil não abre, e escalar piora a taxa (RESULTADO CENTRAL NOVO)

| | 257 pares | 690 pares |
|---|---|---|
| vulneráveis detectados | 11 | 18 |
| taxa de detecção | **4,28 %** | **2,61 %** |

Triplicar a colheita multiplicou as detecções por 1,6 **e piorou a taxa**. Somado
a que o corpus Go inteiro da OSV (9.113 entradas) foi varrido com teto de
repositório frouxo, a afirmação publicável é:

> *Nem varrendo o corpus Go inteiro da OSV, restrito às fraquezas que o catálogo
> de regras declara cobrir, se obtém amostra de 30 vulnerabilidades reais que a
> análise sintática detecte.*

Isso **confirma empiricamente** o que `metodologia.tex:344` já afirmava em tese
(o teto de recall herdado do analisador) — agora com número: 97,6 %.

### 3.2 Por que umas CWEs detectam e outras não (§8 da análise)

Das 1.074 regras do `p/default`, **apenas 84 rodam em Go**.

| CWE | regras Go | pares | detecções | taxa |
|---|---|---|---|---|
| 89 SQL Injection | 8 | 18 | 7 | 38,9 % |
| 601 Open Redirect | 1 | 10 | 3 | 30,0 % |
| 79 XSS | 12 | 57 | 5 | 8,8 % |
| **22 Path Traversal** | **2** | **114** | **0** | **0,0 %** |
| 400 / 200 / 345 / 78 | 1 cada | 285 | 0 | 0,0 % |

O mecanismo, e não só o número, é material de discussão:

- **CWE-89 detecta** porque injeção de SQL em Go tem forma canônica local —
  `db.Query(fmt.Sprintf(...))`. O defeito cabe numa linha.
- **CWE-22 não detecta** porque `os.Open(filepath.Join(base, entrada))` é
  **sintaticamente idêntico ao código seguro**. Depende de a entrada ser
  controlável e não validada — pergunta semântica, não sintática.
- **CWE-918 não detecta** porque sua única regra é de *taint* intraarquivo, e
  SSRF real atravessa camadas.

Isto liga diretamente à §1.1: é a mesma limitação vista por outro ângulo.

### 3.3 `p/golang` seria pior que `p/default`

Serve para **G1** (justificativa do Semgrep) e para a seção de ameaças:
`p/golang` tem 42 regras contra as 84 de Go do `p/default`; 11 CWEs existem só no
`p/default` e apenas 2 só no `p/golang`, nenhuma presente no corpus. Confirma a
escolha do `p/default` já registrada em `provadeconceito.tex:247`.

### 3.5 O alcance entre arquivos não era o limitante (RESULTADO NEGATIVO, 2026-09-15)

**O que se testou.** As duas maiores CWEs da classe positiva são baldes secos
(CWE-22: 114 pares, 0 detecções; CWE-918: 112 pares, 1), e a hipótese era que a
causa fosse o alcance do motor: o Semgrep CE rastreia *taint* só dentro de um
arquivo, e **0 de 807 alertas** do corpus trouxeram trilha de dataflow. O
Semgrep Pro analisa entre arquivos. Portão: `scripts/verificar_pro.py`.

**O que se mediu**, com conta gratuita e Semgrep 1.167.0:

| pergunta | resposta |
|---|---|
| O tier gratuito entrega o modo entre-arquivos? | **Sim.** Projeto controlado: CE 0 trilhas entre arquivos, Pro 1. |
| Ele produz trilha em repositórios reais? | **Sim.** 9 trilhas, em 3 de 10 repositórios, atravessando até 3 arquivos. |
| Quanto custa? | **4–6× mais lento.** `seaweedfs` 124 s → 749 s; `mattermost` estourou 20 min por modo. |
| **As trilhas alcançam os casos do gabarito?** | **Não, em nenhum dos 6 casos medidos.** Ver tabela abaixo. |

**A medição por caso** (`--etapa gabarito`, 2026-09-15/16), aplicando a mesma
regra de pareamento da Fase 1 sobre o arquivo do gabarito, com o repositório
inteiro em escopo nos dois modos:

| caso | CWE | CE | Pro | ganho |
|---|---|---|---|---|
| `seaweedfs/seaweedfs@4f8af455bf` | 22 | NAO_DETECTADO | NAO_DETECTADO | nenhum |
| `1panel-dev/1panel@278a562320` | 22 | NAO_DETECTADO | NAO_DETECTADO | nenhum |
| `getarcaneapp/arcane@67fae1255d` | 22 | NAO_DETECTADO | NAO_DETECTADO | nenhum |
| `openlistteam/openlist@5a5d8d6e0e` | 22 | NAO_DETECTADO | NAO_DETECTADO | nenhum |
| `abhinavxd/libredesk@f7aa1ef2eb` | 918 | NAO_DETECTADO | NAO_DETECTADO | nenhum |
| `oasdiff/oasdiff@c01d48dae4` | 918 | NAO_DETECTADO | NAO_DETECTADO | nenhum |
| `gogs/gogs@0089c4c8e5` | 918 | NAO_DETECTADO | *timeout 900 s* | sem dado |

**6 casos com dado, 0 detecções novas.** Em 5 deles o arquivo do gabarito não
recebeu **alerta nenhum** em nenhum dos dois motores; no `gogs` o CE emitiu 1
alerta, de outra CWE. O `seaweedfs` é o caso mais ilustrativo: 849 alertas no
repositório e **0** nos dois arquivos do gabarito, com as 6 trilhas entre
arquivos caindo em `webdav_server.go`, `filer_server_handlers.go` e
`file_browser_handlers.go`.

**A interpretação.** `regras_nao_casadas=[]` com o repositório inteiro em escopo
significa que **nenhuma regra olha aqueles arquivos**. Isso é cobertura de
regra, não alcance — e alcance entre arquivos não conserta arquivo que regra
nenhuma examina.

**O que isso autoriza escrever.** *"A análise entre arquivos do Semgrep Pro foi
verificada como disponível e funcional no tier gratuito, e não produziu nenhuma
detecção adicional em 6 casos da população (3 de CWE-22, 3 de CWE-918)
avaliados sob os dois motores sobre o repositório completo."* A medição está em
`data/viabilidade_pro_2026091{5,6}.json`.

**O que ainda não autoriza.** Afirmar que o ganho é zero na população inteira:
6 casos de 226 é amostra pequena, escolhida por espaçamento uniforme e não
aleatória, e o timeout do `gogs` mostra que repositórios grandes ficam
sub-representados — justamente os que teriam mais camadas para atravessar. O
enunciado honesto é sobre os casos avaliados, não sobre a população.

**Encaminhamento.** A hipótese era `p/gosec` — regras sintáticas (`G304` para
CWE-22, `G107` para CWE-918) que não dependeriam de rastro de fluxo. **Ela foi
medida e refutada em 2026-09-16: essas regras não existem.** Ver §3.6.

---

### 3.6 Os rulesets públicos não cobrem CWE-22 nem CWE-918 em Go (RESULTADO NEGATIVO, medido em 2026-09-16)

O §3.5 encaminhava para o `p/gosec`, supondo que o registry do Semgrep publica
as regras do gosec reescritas — `G304` para CWE-22 e `G107` para CWE-918 —, que
seriam sintáticas e por isso alcançariam onde as regras de taint falham. **A
suposição era falsa.**

| medida | valor |
|---|---|
| Regras no `p/gosec` | 23 (todas rodam em Go; `missed: 0`) |
| Já presentes no `p/default` | **22 de 23** |
| Exclusivas | 1 — `use-of-unsafe-block`, CWE-242, ausente da população |
| `gosec.G304-1` / `gosec.G107-1` | **não existem**, em nenhum ruleset alcançável |

O `p/gosec` publicado não é o gosec reescrito: é um recorte das regras
`go.lang.security.*` do próprio Semgrep. Nenhum identificador contém `gosec`,
`G304` ou `G107`.

Regras Go **novas** para as duas CWEs alvo, por ruleset consultado:

| ruleset | CWE-22 | CWE-918 |
|---|---|---|
| `p/gosec` (23 regras) | 0 | 0 |
| `p/trailofbits` (120 regras) | 0 | 0 |
| `p/security-audit` (225 regras) | 0 | 0 |

A única regra de CWE-22 do `p/gosec` é a mesma
`path-traversal-inside-zip-extraction` que o `p/default` já tem. Confirmado
também na execução: `semgrep --config p/default [--config p/gosec]` sobre 5
arquivos de CWE-22 do cache deu **0 alertas nos dois casos**.

**O que isso autoriza escrever.** *"A hipótese de que a não-detecção de CWE-22 e
CWE-918 decorresse da ausência de regras sintáticas no ruleset configurado foi
testada e rejeitada: nenhum dos rulesets públicos do registry do Semgrep
consultados acrescenta regra Go para essas fraquezas além das já presentes no
`p/default`."*

**O que ainda não autoriza.** Afirmar que o Semgrep não detecta CWE-22 em Go. O
medido é mais estreito e é sobre o **catálogo**, não sobre a ferramenta: os
rulesets públicos alcançáveis não trazem regra nova. Uma regra escrita à mão
poderia detectar — ao custo do viés de autoria, já que seria escrita olhando
para esta população.

**Consequência metodológica.** Fecha uma alternativa e reforça o §3.1: o teto de
recall não é um parâmetro mal configurado, é cobertura de regra que não existe
publicada para Go. Restam dois caminhos, ambos com custo próprio — regra própria
(`regras-proprias-go`, assume o viés) ou mais alcance no motor
(`semgrep-pro-entre-arquivos`, que o §3.5 já mediu como sem ganho em 6 casos).

Medições em `openspec/changes/archive/2026-09-17-ruleset-gosec/design.md`.

---

### 3.4 Ameaças à validade a acrescentar

| ameaça | evidência |
|---|---|
| Ruleset não fixado | `p/default` muda do lado do servidor; o cache grava só a string. Revalidado nesta rodada (1.074 regras, mesmas 34 CWEs), mas não fixado. |
| **Motor não fixado** (se o modo entre-arquivos for adotado) | O Semgrep Pro é binário proprietário (301,8 MB) baixado de servidor de terceiros, sem versionamento sob nosso controle. **Agrava a ameaça acima**: não é só o ruleset que muda do lado do servidor — o motor também. Medido: instalar o binário alterou o comportamento do CE nesta máquina (com `--dataflow-traces`, 0→1 trilha e ~6 s→~16 s no mesmo alvo), mesmo sem `--pro` e mesmo com `--oss-only`. A Fase 1 não passa `--dataflow-traces` e 25 casos reexecutados do cache deram 25 resultados idênticos, então as Rodadas 1–3 continuam reproduzíveis — mas "CE" deixou de ser um estado único na máquina. |
| "Alcançável" binário superestima cobertura | CWE-918 entrou com 112 pares tendo **uma** regra de taint; CWE-22 com 114 e duas regras estreitas. |
| Concorrência de memória em máquina única | Semgrep e `llama-server` disputam RAM; 488 casos falharam com `STATUS_DLL_INIT_FAILED`. Contornado separando Fase 1 das fases neurais. |
| Falha de esteira reprodutível | 2 casos (`harness/harness`, CWE-79) em laço degenerativo do modelo quantizado, em todas as rodadas. |
| Classe positiva pequena | 19 amostras; impede Recall/F1/MCC/TFN neurais. |

---

## 4. O que a Q2 responde hoje

| metade | estado |
|---|---|
| *"reduzir o volume de falsos positivos"* | **Respondida.** TRA 0,9819; McNemar p < 0,0001; 104 × 5; estável em três populações. |
| *"sem introduzir falsos negativos"* | **Não respondida.** 19 amostras < 30. |

**Mas a segunda metade rendeu um resultado próprio:** o motivo pelo qual ela não
pode ser respondida com esta arquitetura e este corpus. Ver §3.1.

Q1 (precisão) e Q3 (por categoria de CWE) herdam a mesma limitação: qualquer
métrica que dependa da célula VP repousa sobre 19 casos.

---

## 5. Estrutura: falta um capítulo

`tcc.tex` não tem capítulo de resultados. `provadeconceito.tex` é o piloto da
Parte 1 e **não deve ser sobrescrito** — ele documenta uma etapa legítima do
trabalho.

Proposta a decidir:

```
introducao → referencialteorico → metodologia → provadeconceito
           → [NOVO] resultados  → [NOVO ou dentro de resultados] discussão
           → consideracoes
```

O capítulo novo absorveria: configuração (§2.1), população (§2.2), resultados
(§2.3-2.5), achados (§3.1-3.3) e ameaças (§3.4). É também onde entra a
**discussão do ponto crítico e da contingência** que o apontamento **A3** pede.

---

## 6. Situação dos apontamentos da banca

| # | apontamento | situação |
|---|---|---|
| **G1** | Justificativa Semgrep melhor na fala que no texto | **Munição pronta** — §3.2 e §3.3 dão base empírica |
| **G2** | Qual o menor contexto? Outro LLM? | **Medido:** prompt mediano ~1,1k tokens; contexto não é gargalo. Decisão de escopo segue aberta |
| **G3** | Ollama | **Código pronto e usado na Rodada 3.** Falta o texto — ver §1.2 |
| **G4** | Termo "neuro-simbólico" | **Decisão pendente.** Bloqueia; afeta 8 arquivos e o título |
| **A1** | Acerto do LLM só se liga à 1ª coluna do detector | Matrizes já são separadas no código; falta figura + texto |
| **A2** | Classificação científica da metodologia | Não iniciado |
| **A3** | Cronograma: prazos, ponto crítico, contingência | **Munição pronta** — §3.1 é o ponto crítico e §3.4 as contingências |

---

## 6.5 Correção de método: o critério de um portão

O portão do modo entre-arquivos classificou `viavel` com o critério "≥1 trilha
entre arquivos no alvo". Isso mede a **capacidade da ferramenta**, não o **ganho
na população** — e as duas divergiram: o portão passou e o cruzamento manual
mostrou 0 detecções nos casos do gabarito.

**Um portão que passa quando o ganho não chega aos casos não é portão.** Para
`ruleset-gosec` e para qualquer troca futura de motor ou de ruleset, o critério
tem que ser **detecção nos casos do gabarito**, medida sobre a mesma população,
e não "a ferramenta funciona". Registrar isto no texto, se a seção de método
discutir como as decisões de ferramenta foram tomadas.

---

## 7. Decisões que ainda travam a redação

1. **Aceitar n = 19 ou perseguir 30?** Perseguir exigiria mudar o objeto medido
   (outra linguagem, Semgrep Pro, ou regras próprias). Recomendação registrada em
   `ANALISE-RODADA-3.md` §9: aceitar, porque a afirmação da §3.1 é mais forte que
   uma bateria de métricas com n = 30.
2. **G4 — nomenclatura.** Bloqueia título e 8 arquivos.
3. **Estrutura de capítulos** (§5).
4. **Rodar um segundo modelo?** (G2) — muda escopo e cronograma.

---

## 8. Referência rápida de artefatos

| artefato | onde |
|---|---|
| Análise da Rodada 3 | `docs/ANALISE-RODADA-3.md` |
| Análise da Rodada 2 | `docs/ANALISE-RODADA-2.md` |
| Análise da Rodada 1 | `docs/ANALISE-RODADA-1.md` |
| Apontamentos da banca | `docs/APONTAMENTOS-BANCA-TCC1.md` |
| Specs vigentes | `openspec/specs/` |
| Mudanças arquivadas | `openspec/changes/archive/` |
| CSVs da Rodada 3 | `results/20260908T094808Z-9a00cb2/` |

> `results/`, `cache_simbolico*/` e `repos/` não são versionados. `repos/` foi
> **apagado** (18 GB) após verificação de que `cache/` está completo — ver §9.

## 9. Sobre o cache (verificado em 2026-09-08)

Registrado aqui porque afeta a reprodutibilidade que o texto vai afirmar.

- **`cache/`** (fontes) — chave `(repo, commit, arquivo)`. O commit é um SHA, logo
  a chave é **imutável**: a entrada nunca invalida. 1.766 arquivos, 77,5 MB.
  **Não está no `.gitignore`** — é versionado de propósito; 810 arquivos já estão
  no git e ~956 ainda não foram commitados.
- **`cache_simbolico/`** (resultado do Semgrep) — invalida sozinho por três eixos:
  `versao_formato`, `versao_ruleset` e `versao_pareamento`. Divergiu, recomputa.
- **Determinismo verificado empiricamente:** 40 casos reprocessados do zero com
  `--sem-cache-simbolico` e comparados ao cache — **40/40 idênticos** em
  `Status_Semgrep`, `Motivo_Nao_Deteccao` e `Regras_Nao_Casadas`.
- **Persistência:** são arquivos comuns em disco; sobrevivem a desligamento.
- **Ressalva única:** o eixo `versao_ruleset` grava a string `"p/default"`, que não
  muda quando o conteúdo do ruleset muda no servidor. É a ameaça da §3.4.
