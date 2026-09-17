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

### 3.7 Regra própria melhora pouco, e a análise de por quê é a contribuição (medido em 2026-09-17)

O §3.6 fechou a alternativa barata: nenhum ruleset público traz regra Go para
CWE-22 ou CWE-918. Restava escrever regra — com o viés de autoria declarado. Foi
escrito, medido, e o resultado é mais interessante que o número.

**A contribuição é a análise de lacunas, não as regras.** Este é o ponto que o
texto precisa deixar explícito, no modelo do Semgrep\* (EASE 2024), cuja
contribuição publicada foi a investigação dos padrões ausentes dos rulesets, não
o ruleset resultante. Apresentar "escrevemos quatro regras" como resultado seria
apresentar a evidência no lugar do achado.

**O achado.** Aberta apenas a partição de desenvolvimento (54 casos de CWE-22,
55 de CWE-918, todos vulneráveis):

| | CWE-22 | CWE-918 |
|---|---:|---:|
| Operação perigosa na forma que uma regra sintática nomeia (`os.Open`, `http.Get`, …) | 23/54 (42,6 %) | 15/55 (27,3 %) |
| Operação atrás de abstração ou método de receptor (`afero`, `billy`, `fs.FS`, `cliente.Do`) | 14/54 (25,9 %) | 24/55 (43,6 %) |
| **Nenhuma operação perigosa no arquivo rotulado** | **17/54 (31,5 %)** | **16/55 (29,1 %)** |
| Arquivo contém acessor HTTP (`r.URL.Query().Get`, `FormValue`, …) | 6/54 (11,1 %) | 13/55 (23,6 %) |
| Entrada vem de campo de struct (`args.InnerPath`, `req.Signature`, `m.state.SrcUri`) | 23/54 (42,6 %) | 37/55 (67,3 %) |
| Marcas de extração de arquivo compactado | 11/54 (20,4 %) | 0/55 |

**O que isso autoriza escrever.** *"Cerca de 30 % dos casos da classe positiva
não contêm, no arquivo rotulado, a operação que a fraqueza descreve. Para esses
casos nenhuma regra sintática — de qualquer ruleset — pode detectar a
vulnerabilidade no arquivo em que ela está anotada, porque o gabarito é por
arquivo e o arquivo que o commit de correção toca é frequentemente o da
verificação acrescentada, não o do ponto perigoso."*

Outros 26 % (CWE-22) e 44 % (CWE-918) só expõem a operação atrás de uma
abstração de sistema de arquivos ou de um método de receptor, onde regra que
nomeia a biblioteca padrão não morde. E a origem da entrada quase nunca é a que
a definição da CWE sugere: a CWE-22 desta população é, em boa parte, **zip-slip**
— a entrada externa é o nome de uma entrada de arquivo compactado.

**Isso reordena o §3.1 e o §3.5.** O teto de recall não é parâmetro mal
configurado (§3.6), não é alcance do motor (§3.5) e não é cobertura de ruleset
que alguém poderia publicar: é **granularidade do rótulo** somada a **abstração
do código real**. As três hipóteses anteriores foram testadas e rejeitadas nessa
ordem, e esta é a quarta — a primeira que explica os números.

**Os números das regras, e qual deles é reportável.**

| CWE | regras `definicao`, população inteira | todas as regras, **partição de avaliação** | partição de desenvolvimento (diagnóstico) |
|-----|--------------------------------------:|-------------------------------------------:|------------------------------------------:|
| CWE-22 | 2/114 (1,8 %) | **4/60 (6,7 %)** | 4/54 (7,4 %) |
| CWE-918 | 1/112 (0,9 %) | **1/57 (1,8 %)** | 3/55 (5,5 %) |

**O número reportado sai da partição de avaliação** sempre que houver regra de
proveniência `desenvolvimento` carregada — a coluna do meio. A primeira coluna é
reportável sobre a população inteira porque aquelas regras foram escritas apenas
a partir da definição da CWE e da documentação de Go, sem que nenhum caso fosse
inspecionado. A terceira **nunca** é resultado: é diagnóstico interno, e o script
de medição recusa somá-la às demais.

A distância entre a segunda e a terceira colunas é o que só a partição torna
visível. Em CWE-22 elas quase coincidem — a regra de zip-slip descreve um idioma
e generaliza. Em CWE-918 o desenvolvimento é **três vezes** a avaliação: ali a
regra descreve mais os casos vistos que a fraqueza. Num número único, essa
diferença desapareceria.

**Apêndice de verificabilidade (a escrever).** O protocolo depende da ordem —
partição antes de regra — e a ordem é auditável no histórico do Git. O texto
deve trazer os hashes, para que o leitor confirme sem depender da nossa palavra:

| artefato | commit |
|---|---|
| Partição de desenvolvimento/avaliação, sozinha, sem nenhuma regra | `cc87274` |
| Primeiras regras locais (`definicao`) | `ec37322` |
| Regras informadas pela partição (`desenvolvimento`) | `fa7eb31` |

`cc87274` não contém um único arquivo sob `regras/go/` — é o que torna a
afirmação "as regras não informaram a partição" verificável em vez de assertiva.

**Ameaça à validade residual, e ela não é pequena.** A separação estrutural
impede que o *número* seja contaminado; não impede que a *escolha do problema*
seja. As CWEs alvo foram escolhidas por serem onde a classe positiva se perde, e
essa escolha veio de olhar a população agregada. O que a partição protege é a
medida, não a agenda. Some-se a isso o tamanho: 60 e 57 casos na avaliação, com
4 e 1 detecções — intervalos de confiança largos o bastante para que a diferença
entre 6,7 % e 3,3 % não suporte teste de hipótese. Os números servem para
descrever ordem de grandeza e sustentar a análise de lacunas; não para afirmar
superioridade de uma configuração sobre outra.

**A redação do `.tex` acontece em branch separada, e não na branch desta
change.** Nenhum arquivo `.tex` foi tocado por `regras-proprias-go`.

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
| **Granularidade do rótulo** | O gabarito é por ARQUIVO, e ~30 % dos arquivos rotulados de CWE-22/918 não contêm a operação perigosa (§3.7). Para esses casos a não-detecção não informa nada sobre o motor: a fraqueza não está onde o rótulo aponta. |
| **Escolha do problema, não da medida** | A separação desenvolvimento/avaliação protege o número das regras locais, mas as CWEs alvo foram escolhidas por olhar a população agregada. O viés de agenda permanece e precisa ser declarado (§3.7). |

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

## 4b. MUDANÇA DE DESENHO: o braço de triagem (change `braco-triagem-classe-positiva`)

> **A redação correspondente do `.tex` acontece em BRANCH SEPARADA, e não nesta
> change.** Vale a decisão vigente de não mexer na monografia antes de fechar o
> experimento. Esta seção é o registro de acumulação; a branch do LaTeX a
> consome. **Nenhum arquivo `.tex` foi tocado.**

A pipeline ganhou um eixo: **o modo de montagem do candidato**, com dois valores,
`filtro` (padrão, o desenho de sempre) e `triagem`. No modo `triagem`, caso de
gabarito vulnerável que o Semgrep não detectou passa a ser submetido ao LLM, com
o candidato montado a partir da localização declarada no gabarito. O negativo
continua vindo só do Semgrep, e `Status_Semgrep` não muda.

Isso obriga quatro alterações no texto.

### 4b.1 A arquitetura deixa de ser descrita como "o LLM é filtro puro"

A redação atual descreve uma arquitetura em que o componente neural só opina
sobre o que o motor simbólico emitiu. **Isso deixa de ser a descrição completa** e
passa a ser propriedade do braço `filtro`. O texto precisa descrever **dois
braços**, com o mesmo componente neural e formas diferentes de montar o
candidato — e dizer qual dos dois produziu cada número.

As Rodadas 1-3 são rodadas do braço `filtro` e continuam válidas e citáveis como
tal. O braço novo produz uma série nova; nenhum resultado foi invalidado.

### 4b.2 Os números da triagem NÃO são desempenho do sistema em operação

**É o risco principal desta mudança, e é de redação, não de código.** Num uso
real os positivos não seriam injetados: viriam do Semgrep, que perde 97,4 %
deles. O Recall, o F1 e o MCC do braço de triagem medem **o componente neural
isolado**, não a pipeline implantada.

A declaração é obrigatória em qualquer lugar onde esses números aparecerem. A
coluna `Procedencia` no CSV torna o recálculo possível para quem quiser conferir.

### 4b.3 A distância entre os dois braços é a medida do teto de filtro puro

O roteiro da apresentação hoje anuncia esse teto **sem quantificar**. Com as duas
rodadas ele passa a ter número: a diferença de recall (e de taxa de redução de
alertas) entre o braço de filtro e o de triagem é exatamente quanto o desenho de
filtro puro deixa na mesa. Ver a tarefa 5b.5 da change — a tabela lado a lado.

Cuidado ao redigir: essa distância **mistura dois efeitos** — quais casos chegam
ao LLM, e quanto contexto cada um traz (ver 4b.4). Atribuí-la inteira ao primeiro
seria exagerar.

### 4b.4 Ameaça à validade: a natureza das localizações, e o que responde a ela

Os positivos injetados e os alertas do Semgrep podem diferir **sistematicamente
na natureza da localização apontada**. O alerta aponta a linha que casou com a
regra; o injetado aponta o início da função declarada vulnerável pela CVE. A
hidratação recorta a função que contém a linha, então os dois recebem uma função
Go recortada pelo mesmo algoritmo — mas não necessariamente funções de mesma
natureza.

**O que responde a isso é o grupo de controle**, não uma afirmação: os casos
vulneráveis que o Semgrep *achou* rodam na mesma rodada de triagem, com
procedência `alerta`, sob o mesmo prompt e o mesmo modelo. Se o acerto divergir
muito entre procedências, o número da triagem não pode ser reportado como está.

Duas ressalvas a declarar junto:

- **O controle é pequeno.** São os mesmos 19 casos. Um controle fraco que acusa
  diferença grande ainda é informativo; a ausência de diferença nele não
  demonstra ausência de artefato. As métricas emitem esse aviso sozinhas.
- **O contexto do braço de triagem é mais pobre.** Para que a procedência não
  vazasse para o prompt, o modo `triagem` remove do contexto o identificador da
  regra, a mensagem do motor e a linha apontada — para as duas procedências. O
  braço de triagem entrega ao LLM estritamente menos que o de filtro, e isso é
  parte da diferença medida em 4b.3.
- **O enquadramento do prompt continua o de sempre.** Os dois templates abrem com
  "abaixo está um alerta emitido por uma ferramenta de análise estática". No
  braço de triagem a frase é falsa para o candidato injetado — e, por uniforme,
  o grupo de controle **não** a detecta. Não foi alterada de propósito: mexer no
  template muda `Versao_Prompt` e o eixo experimental do prompt. Ou se declara a
  limitação, ou se decide trocar o texto — decisão do autor, ainda em aberto em
  `openspec/changes/braco-triagem-classe-positiva/design.md`.

### 4b.5 ACHADO NOVO: o baseline das Rodadas 1-3 nunca foi um controle limpo

**Este é o achado mais forte da Rodada 4, e ele não estava previsto.**

O grupo de controle permite um experimento que nenhuma rodada anterior permitia:
os positivos que o Semgrep detectou aparecem nas **duas** rodadas — no braço de
filtro porque o alerta existia, no de triagem porque o emparelhamento tem
precedência sobre a injeção. São os mesmos `ID_Caso`, o mesmo modelo
(`qwen2.5-coder:7b`, digest `dae161e27b0e`), o mesmo template (hashes
`baseline:597fcfa9` e `especialista:d1145f8b`), `num_ctx` 8192, **semente 42 e
temperatura 0**. A única variável entre as duas é o contexto.

| braço | n | VP com contexto do alerta (Rodada 3) | VP com contexto só de código (Rodada 4) | delta |
|---|---|---|---|---|
| baseline | 19 | **8** | **0** | **−8** |
| especialista | 19 | 3 | 3 | 0 |

Oito VPs viraram zero; nenhum caso foi ganho. O especialista não se move.

**A leitura é direta.** O prompt baseline não recebe CWE, nem definição, nem
heurística — por desenho, ele é a condição de controle. Mas no modo filtro o
contexto hidratado começava com `Alerta Semgrep: go.lang.security.audit.<nome>`
e `Mensagem: <texto do Semgrep>`, e esse texto **nomeia a fraqueza**. O baseline
estava lendo a resposta no enunciado. Removida essa parte — que é o que a
normalização do modo triagem faz, para que a procedência não vaze —, o baseline
vai a zero. O especialista não muda porque o sinal dele vem do catálogo, que
continua lá.

**O que isso obriga a escrever:**

1. A comparação baseline × especialista das Rodadas 1-3 **não mede só a
   contribuição da engenharia de prompt**. Parte do que o baseline acertava vinha
   do identificador da regra e da mensagem do motor, não da análise do código. A
   diferença medida entre os dois braços é, nessa medida, um limite inferior
   subestimado — e precisa ser declarada como tal, não corrigida em silêncio.
2. O braço `baseline × triagem` da Rodada 4 **não é comparável** com o
   `baseline × filtro` das Rodadas 1-3. Não é "o mesmo componente sobre mais
   casos": é um tratamento mais pobre. Reportá-los lado a lado sem essa ressalva
   seria erro. O braço `especialista` não sofre disso.
3. Isto é uma **ameaça à validade que se resolveu sozinha ao ser medida**: o
   desenho do braço de triagem, criado para outro fim, produziu o controle que a
   expõe. Vale como resultado metodológico do trabalho.

### 4b.5b Enquadramento do prompt — decisão REVOGADA pela Rodada 5

> ⚠️ **A decisão anterior ("manter o template") está revogada.** Ela foi tomada
> com os dados da Rodada 4, que não permitiam enxergar o efeito. A Rodada 5
> mediu, e o efeito é grande. O que segue é a decisão vigente.

A questão era se manter o "abaixo está um alerta emitido por uma ferramenta de
análise estática" nos templates, já que no braço de triagem a frase é falsa para
os 759 injetados. Em 2026-09-16 rodou-se a Rodada 5 — **mesmo modelo, mesma
população, semente 42, temperatura 0, só o enquadramento muda** — com templates
novos que perguntam pelo código em vez de pelo alerta.

| especialista | R4 (pergunta pelo alerta) | R5 (pergunta pelo código) |
|---|---|---|
| Recall | 1,29 % | **5,13 %** |
| Precisão | 0,476 | **0,533** |
| MCC | −0,0033 | **+0,0189** |
| VP | 10 | **40** |

**O recall quadruplicou, e a precisão subiu junto** — não foi troca de um pelo
outro. A pergunta incoerente estava suprimindo vereditos positivos.

E a régua de controle confirma que a penalidade era específica dos injetados: o
enquadramento direto ajuda os casos **com alerta** em 2,0× e os **injetados** em
4,8×.

**O que o texto precisa registrar:**

1. **O número do braço de triagem é 5,13 %, não 1,29 %.** A Rodada 4 mediu o
   braço sob uma pergunta que não se aplicava a metade dos seus casos.
2. **O baseline direto vai a MCC −0,0834** — pior que chute. Sem CWE-alvo,
   "este código contém alguma vulnerabilidade?" produz ruído: +7 VP contra
   +30 FP. O baseline só funcionava porque lia a fraqueza na mensagem do Semgrep
   (§4b.5); tirada a mensagem e a pergunta fechada, ele não tem em que se apoiar.
3. **O eixo do prompt volta a ser detectável:** McNemar entre os dois prompts vai
   de p = 0,8445 (R4) para **p = 0,0090** (R5). A conclusão da Rodada 4 de que
   "os dois prompts convergiram por degeneração" era parcial — o baseline é
   degenerado, o especialista estava sendo suprimido pela pergunta.
4. **A conclusão qualitativa sobrevive:** MCC +0,0189 continua sendo ausência de
   poder discriminativo, e a TFN é de 94,87 %. Quadruplicar 1,29 % dá 5,13 %, que
   segue inutilizável. **O achado ficou mais forte por ter sobrevivido à
   tentativa de derrubá-lo.**

Os templates originais **não foram alterados** — `baseline:597fcfa9` e
`especialista:d1145f8b` continuam idênticos, com teste travando os hashes, e as
Rodadas 1 a 4 seguem reproduzíveis. Os novos são tipos próprios
(`baseline_direto`, `especialista_direto`). Detalhes em
`docs/ANALISE-RODADA-5.md`.

### 4b.5d O oráculo da CWE, e onde ele é forte

O `especialista` recebe a CWE do gabarito. **Isso não é uniforme entre os braços,
e a distinção importa:**

- **Braço de filtro:** quando há alerta, a CWE do gabarito é a que a regra do
  Semgrep declarou (é o que o pareamento exige). Um sistema implantado teria essa
  CWE, vinda do próprio alerta. **Não é oráculo — é o que a ferramenta entrega.**
- **Braço de triagem, casos injetados:** não há alerta. A CWE vem só da CVE, e em
  produção não haveria nada para preencher aquele campo. **Oráculo forte.**

Portanto os 5,13 % são um **limite superior generoso**: o modelo é informado de
qual fraqueza procurar e em qual função olhar, e ainda assim recupera 5,13 %.

Resta um oráculo fraco no braço de filtro, a declarar: quando várias regras
disparam com CWEs diferentes no mesmo arquivo, o experimento usa o gabarito para
escolher **qual** alerta avaliar; em produção se triaria todos, e a carga real de
falsos positivos seria maior que a medida.

### 4b.5c O que a Rodada 4 responde da Q2, e o que ela responde mal

A metade *"sem introduzir falsos negativos"* passa a ter número: o braço
`especialista × triagem` avalia **778 vulneráveis** (contra 19), e Recall, F1,
MCC e TFN ficam calculáveis. **A resposta é ruim, e é resultado:** recall do
componente de **1,29 %**, TFN de **98,71 %**, **MCC de −0,0033**. O sistema em
modo triagem recobra 10 dos 797 positivos (recall de sistema 1,25 %) contra 3 no
modo filtro (0,38 %).

**Dois números da rodada fechada que o texto vai precisar, e que mudam a §4:**

1. **O MCC dos dois braços é ≈ 0** (`baseline` +0,0121, `especialista` −0,0033).
   Zero é o valor de quem não discrimina nada. Ambos dizem "não é
   vulnerabilidade" para quase tudo: 5 vereditos positivos em 1.585 casos no
   baseline, 21 em 1.586 no especialista.
2. **O McNemar entre os prompts deixa de ser significativo dentro do braço de
   triagem**: 14 × 12 discordâncias, p = **0,8445**, contra 104 × 5 e p < 0,0001
   na Rodada 3. Isso **não** é "os prompts são equivalentes" — é que, sem os
   campos do alerta, os dois convergem para o mesmo comportamento quase
   constante, e dois classificadores degenerados concordam trivialmente. Escrever
   "não houve diferença entre os prompts" inverteria o sentido do achado.

E uma armadilha de leitura a declarar: **a TRA do baseline SOBE** de 0,8497 para
0,9976 na pilha de alertas. Não é ganho — é o sintoma da degeneração acima, e é o
caso didático de por que a TRA só pode ser lida junto da TFN.

O teto do desenho de filtro puro, portanto, existe mas é **pequeno em valor
absoluto**: +0,88 ponto percentual de recall de sistema no especialista. No
baseline ele é **negativo** (−0,63 p.p.), pelo motivo da §4b.5 — a perda de
contexto supera o ganho de casos. Nenhum dos dois sustenta a leitura de que
"bastaria deixar o LLM ver tudo".

### 4b.5e CORREÇÃO DE LEITURA: o MCC agregado do braço de triagem é artefato de composição

> **Isto revisa como os MCC das Rodadas 4 e 5 devem ser lidos, e é favorável à
> arquitetura.** Descoberto na Rodada 6, ao separar as métricas por procedência.

O braço de triagem mistura dois conjuntos de naturezas opostas:

| conjunto | n | vulneráveis | o que é |
|---|---|---|---|
| procedência `alerta` | ~823 | 18 (**2,2 %**) | a pilha de alertas real — a tarefa de **filtro** |
| procedência `gabarito` | ~760 | 760 (**100 %**) | os injetados — **sem nenhum negativo** |

Somados, produzem uma taxa-base artificial de ~49 % que **não corresponde a
cenário algum**: em produção os injetados não existem. O MCC agregado descreve
uma população impossível — mesma família de erro já pega na TRA.

**Separando por procedência, na tarefa de filtro (taxa-base 2,2 %):**

| braço | recall | precisão | MCC |
|---|---|---|---|
| qwen + `especialista_direto` | 27,78 % | 12,50 % | **+0,1593** |
| gemma + `especialista_direto` | 38,89 % | 6,14 % | +0,1083 |
| qwen + `baseline_direto` | 11,11 % | 5,88 % | +0,0524 |
| gemma + `baseline_direto` | 44,44 % | 2,30 % | +0,0065 |

**Os quatro braços são positivamente informativos na tarefa para a qual o sistema
foi desenhado.** E o melhor deles replica a Rodada 3 do braço de filtro, que deu
MCC +0,1606 sobre os mesmos casos e o mesmo modelo — dois caminhos independentes,
mesmo número.

**Sobre os injetados o MCC é INDEFINIDO**, e não por falha de cálculo: o conjunto
não tem um único negativo, as células VN e FP são estruturalmente vazias e o
denominador zera. Ali só existe recall — 4,31 % (qwen) e 7,41 % (gemma) com o
especialista.

**O que o texto precisa dizer:**

1. Nunca reportar o MCC agregado do braço de triagem como desempenho. Reportar
   por procedência.
2. **Na tarefa de filtro o componente neural É informativo** (MCC ~+0,16,
   replicado). Isso é mais favorável à arquitetura do que as §4b.5c e 4b.5b
   sugeriam isoladamente.
3. **Sobre o que o SAST perde, não é** — 4 a 7 % de recall, e o único jeito de
   subir isso foi deslocar o viés de resposta inundando a pilha de FP.
4. A frase "o LLM não discrimina nada" era **forte demais**. Ele discrimina na
   tarefa para a qual foi desenhado; não discrimina na que o braço de triagem
   inventou para testá-lo. O achado central — **pontos cegos majoritariamente
   compartilhados** — sobrevive intacto.

### 4b.5f O eixo do modelo: escalar o modelo local não levantou o teto

Rodada 6 (`gemma2:9b`, mesmo enquadramento e mesmos casos da Rodada 5, semente
42, temperatura 0 — só o modelo muda):

| braço | recall | precisão | taxa-base | MCC |
|---|---|---|---|---|
| R5 `especialista_direto` (qwen 7b) | 5,13 % | **51,4 %** | 48,6 % | **+0,0189** |
| R6 `especialista_direto` (gemma 9b) | 8,16 % | 36,7 % | 48,6 % | −0,0832 |
| R5 `baseline_direto` (qwen 7b) | 1,28 % | 23,8 % | 49,1 % | −0,0834 |
| R6 `baseline_direto` (gemma 9b) | **24,68 %** | 36,1 % | 49,1 % | **−0,1858** |

O recall do baseline salta 19×, e o MCC **piora nos dois braços**. A precisão do
gemma fica abaixo da taxa-base nas duas configurações: ele deslocou o **viés de
resposta**, não a capacidade — 340 falsos positivos contra 32 do qwen.

**Ressalva obrigatória:** `gemma2:9b` não é "o qwen maior". Outra família,
generalista em vez de especializada em código, Q4_0 em vez de Q4_K_M. Demonstra
*"este modelo maior não ajudou, e ajudou menos que um menor especializado"* —
**não** *"modelo maior não ajuda"*.

### 4b.6 O que isso muda na §4 acima

A metade não respondida da Q2 — *"sem introduzir falsos negativos"* — passa a ter
caminho: Recall, F1, MCC e TFN ficam calculáveis no braço de triagem. **Mas a
resposta é sobre o componente neural, não sobre o sistema**, e a §4 precisa
passar a distinguir as duas coisas em vez de tratar "não respondida" como estado
único.

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


## 10. LIMITAÇÃO NÃO DECLARADA: a matriz comercial nunca foi executada

> Registrado em 2026-09-17 pela change `escolha-modelo-faixa-media`. Levantamento
> completo, com preços e custo calculado, em `docs/ESCOLHA-MODELO-COMERCIAL.md`.

### 10.1 O que existe de fato (vai para limitações)

**Nenhuma rodada comercial foi executada neste trabalho.** Todas as medições
publicáveis — Rodadas 1 a 6 — vêm de modelos locais (`qwen2.5-coder:7b` e
`gemma2:9b`), servidos por Ollama.

O total de vereditos comerciais do projeto inteiro é **17**, mais **5**
`API_ERROR`. Conferível nos CSVs:

| pasta em `results/` | modelo | linhas | vereditos válidos | `API_ERROR` |
|---|---|---:|---:|---:|
| `piloto-gemini/…__baseline.csv` | `gemini-2.5-flash-lite` | 35 | **10** (4 VP, 6 FP) | 1 |
| `piloto-gemini/…__especialista.csv` | `gemini-2.5-flash-lite` | 35 | **7** (2 VP, 5 FP) | 4 |
| `sizing-fp/` | `gemini-2.5-flash-lite` | 965 | **0** — rodada `--sem-llm` | 0 |
| `cobertura-tp-dataset/` | `gemini-2.5-flash-lite` | 57 | **0** — idem | 0 |
| `20260729T181817Z-4961c9b/` | `gpt-4o-mini` | 12 | **0** — nenhuma chamada | 0 |
| **total comercial** | | | **17** | **5** |

Contra isso, só o braço de triagem local soma 3.172 chamadas por rodada, em três
rodadas. A ordem de grandeza da diferença é de **10⁴**.

Os 17 ainda são ruins: no baseline, 4 de 5 vulneráveis viraram falso negativo e
3 de 5 seguros viraram falso positivo; no especialista, 2 de 2 vulneráveis
perdidos. Com n=17 isso é anedota — mas certamente **não** é evidência de
superioridade comercial, e o texto não pode sugerir que seja.

**Consequência para a redação:** toda conclusão do trabalho está escopada em
*"com modelos locais de 7–9 B quantizados"*. Isso precisa aparecer explicitamente
no capítulo de limitações, e não só ser inferível da tabela de configuração.

### 10.2 A frase que a banca vai cobrar

A spec `matriz-experimental` (`openspec/specs/matriz-experimental/spec.md`) diz,
textualmente:

> "O conjunto padrão de modelos SHALL permanecer o par comercial (Gemini e GPT),
> formando a **matriz 2x2 de referência do experimento**; modelos adicionais,
> como os executados localmente, SHALL entrar apenas quando nomeados
> explicitamente."

Ou seja: **o desenho declara o par comercial como a referência, e o modelo local
como o caso excepcional — e o que foi executado foi exatamente o contrário.**
Quem ler a spec ou uma descrição de metodologia derivada dela vai entender que a
matriz 2x2 comercial foi usada. Ela nunca rodou.

Isso não é erro de execução, é **descompasso entre desenho e execução que o texto
precisa assumir de frente**. Duas saídas, e a escolha é de redação:

1. Declarar a limitação e manter o desenho como está, explicando que a matriz de
   referência não foi executada por indisponibilidade de cota (o tier grátis do
   Gemini permite 20 req/dia, o que torna 3.172 chamadas impossíveis por um
   motivo que não é econômico — a rodada custaria US$ 0,45).
2. Reescrever a descrição do desenho para que o modelo local seja o padrão e o
   par comercial, o eixo adicional — o que é uma descrição honesta do que
   aconteceu, mas exige mexer na spec.

**A opção 1 é mais barata e mais defensável**, porque preserva o registro de que
o desenho original era outro e diz por que ele não foi cumprido.

### 10.3 O que mudaria se uma rodada comercial fosse executada

Ver `docs/ESCOLHA-MODELO-COMERCIAL.md` para o levantamento completo. O resumo
que interessa ao texto:

- Uma rodada de dois braços em faixa média custa entre **US$ 1,43 e US$ 12,43**,
  calculado sobre os tokens medidos da Rodada 4 com preços verificados em
  2026-09-17. **Custo não é, e nunca foi, o impedimento.**
- Rodar os dois modelos comerciais que a spec nomeia como padrão
  (`gemini-2.5-flash-lite` e `gpt-4o-mini`, US$ 1,12 os dois) **não responderia à
  pergunta de escopo**: os dois são a faixa barata de cada fornecedor e
  provavelmente estão na mesma banda de capacidade de um 7 B especializado em
  código. Seria a Rodada 6 de novo — gasto por uma confirmação que não move o
  teto.
- O modelo recomendado é `claude-sonnet-5` (US$ 12,43 por rodada, com o ajuste de
  tokenizador), com `gpt-5.6-terra` como concorrente próximo e `claude-haiku-4-5`
  como opção econômica. Critério, recusas e um conflito de interesse declarado
  estão na §4 daquele documento.
- **Ganho metodológico independente do modelo:** as 26 perdas por estouro de
  janela da Rodada 4 (prompts de até ~27.420 tokens contra um teto efetivo de
  7.680) **desaparecem** em qualquer candidato comercial, cuja janela verificada
  é de no mínimo 200k. Com elas some a perda enviesada por tamanho de função, que
  hoje está declarada como ameaça à validade.
- **Se a banca perguntar por que não usaram modo batch** (desconto de 50 % nos
  três fornecedores, verificado em 2026-09-17): a resposta está na §8 de
  `docs/ESCOLHA-MODELO-COMERCIAL.md`. Resumo: o desconto é real, mas economiza
  US$ 6 numa decisão cuja faixa inteira vai de US$ 0,22 a US$ 62 — e custa de 3 a
  5 vezes mais integração, porque batch quebra o contrato síncrono de
  `src/provedores/` e mexe na lógica de checkpoint que garante o pareamento entre
  braços. **Preço não foi o impedimento em nenhum momento deste trabalho; cota e
  vazão foram.**
