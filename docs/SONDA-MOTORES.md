# Sonda de motores — o gargalo é do Semgrep ou da análise estática?

## 1. A pergunta

A Rodada 3 (`docs/ANALISE-RODADA-3.md`) fechou com 19 amostras vulneráveis
chegando ao LLM, contra as 30 do critério de aceite, e com um diagnóstico: *"o
gargalo não é a colheita, nem o LLM, nem o tamanho do corpus — é a análise
sintática não reconhecer, no código real, as fraquezas que seu próprio catálogo
diz cobrir."*

Esse diagnóstico é sobre **o Semgrep**. Resta a pergunta natural, que uma banca
faz em dez segundos:

> **E se vocês tivessem usado CodeQL? Ou SonarQube?**

Esta sonda responde com medição, não com argumento.

Ela também testa uma **hipótese específica** levantada em `ANALISE-RODADA-3.md`
§8, que atribui a não-detecção de CWE-22 e CWE-918 à ausência de análise de fluxo
entre arquivos. O CodeQL tem exatamente essa capacidade — logo, serve de
experimento controlado para a hipótese.

## 2. Desenho

**População-alvo.** Os 778 casos de gabarito vulnerável que o Semgrep não
emparelhou na rodada `20260908T094808Z-9a00cb2`.

**Amostra.** 81 casos em 14 repositórios, no *commit vulnerável exato*
(`parent_commit`), restritos às CWEs de fluxo de dados — 22, 918, 79, 94 e 78.

> **A amostra é deliberadamente enviesada a favor do CodeQL.** Escolher só CWEs de
> taint e repositórios pequenos coloca o concorrente no seu melhor cenário. Se
> ainda assim o ganho for pequeno, a conclusão é conservadora — que é o que
> interessa numa decisão de "vale trocar de ferramenta?".

**Critério de emparelhamento — idêntico ao da Fase 1** (`versao_pareamento` 2):

1. alerta no **mesmo arquivo** do caso (o gabarito do projeto é por arquivo);
2. a regra que emitiu o alerta **declara explicitamente a CWE do gabarito**, por
   identificador completo (`CWE-77` não casa com `CWE-770`).

Afrouxar isso — aceitar qualquer alerta no arquivo — seria exatamente o *fallback
de alerta único* removido da pipeline na mudança `pareamento-cwe-estrito`, por
emparelhar o caso a uma fraqueza diferente. Mantê-lo é o que torna a comparação
justa: os três motores são medidos pela mesma régua.

**Duas unidades de contagem.** O gabarito é por arquivo, então um único alerta
credita todos os casos daquele arquivo. Contar só casos infla o resultado quando
várias funções rotuladas moram no mesmo arquivo — e foi o que aconteceu. As duas
contagens aparecem lado a lado; **a de arquivos é a conservadora**.

### Configuração

| | |
|---|---|
| Semgrep | 1.167.0, `p/default` — é a linha de base: 0 detecções por construção |
| CodeQL | 2.27.0, suíte `go-security-extended.qls`, banco por autobuild (Go 1.25.6) |
| SonarQube | 26.9.0 Community, scanner CLI via Docker |

## 3. Resultado

| motor | arquivos recuperados (de 47) | casos recuperados (de 81) |
|---|---|---|
| Semgrep OSS | — (linha de base) | — |
| **CodeQL** | **3 — 6,4 %** | 11 — 13,6 % |
| **SonarQube Community** | **0 — 0 %** | 0 — 0 % |

Veredito do CodeQL sobre os 81 casos:

| | casos | |
|---|---|---|
| `DETECTADO` | 11 | 13,6 % |
| `ALERTA_OUTRA_CWE` | 11 | 13,6 % |
| `SEM_ALERTA` | 59 | 72,8 % |

### Por CWE

| CWE | arquivos | CodeQL recuperou | casos | CodeQL recuperou |
|---|---|---|---|---|
| CWE-918 SSRF | 29 | **1** — 3,4 % | 43 | 1 — 2,3 % |
| CWE-22 Path Traversal | 8 | **2** — 25 % | 23 | 10 — 43,5 % |
| CWE-94 Code Injection | 5 | 0 | 6 | 0 |
| CWE-79 XSS | 1 | 0 | 5 | 0 |
| CWE-78 OS Command | 4 | 0 | 4 | 0 |

### Por repositório

Os 11 casos recuperados vêm de **3 arquivos em 2 repositórios**. Onze dos catorze
repositórios deram zero.

| repositório | casos | recuperados |
|---|---|---|
| rclone/rclone | 8 | 7 (todos em `backend/local/local.go`) |
| goshs-labs/goshs | 6 | 3 (todos em `httpserver/updown.go`) |
| jon4hz/jellysweep | 7 | 1 (`internal/cache/image_cache.go`) |
| outros 11 repositórios | 60 | 0 |

A regra que faz quase todo o trabalho é uma só: **`go/path-injection`**.

## 4. O teste da hipótese do §8

`ANALISE-RODADA-3.md` §8 atribui a não-detecção de duas CWEs à mesma causa —
ausência de fluxo entre arquivos:

> **CWE-22** — *"o caso geral é `os.Open(filepath.Join(base, entradaDoUsuario))` —
> sintaticamente idêntico à versão segura. Se é vulnerável depende de a entrada ser
> controlável: pergunta semântica, sobre fluxo de dados."*
>
> **CWE-918** — *"sua única regra é de taint e exige origem e destino no mesmo
> arquivo. SSRF real atravessa camadas."*

O CodeQL tem fluxo interprocedural e entre arquivos. O resultado separa as duas:

| CWE | Semgrep (Rodada 3) | CodeQL (sonda) | hipótese |
|---|---|---|---|
| **CWE-22** | 0 de 114 — **0,0 %** | 10 de 23 casos — **43,5 %** | ✅ **confirmada** |
| **CWE-918** | 1 de 112 — **0,9 %** | 1 de 43 casos — **2,3 %** | ❌ **refutada** |

**Para CWE-22 o diagnóstico está certo.** Dar fluxo de dados interprocedural tira
a detecção de zero.

**Para CWE-918 está incompleto.** A limitação intra-arquivo não é o gargalo: a
capacidade apontada como faltante foi fornecida, sobre 29 arquivos de 6
repositórios distintos, e o SSRF continuou invisível.

A explicação provável é a mesma que o §8 dá para o CWE-22, e que não foi estendida
ao CWE-918: uma URL montada a partir de configuração, de campo de struct ou de
valor vindo do banco é **sintaticamente indistinguível** de uma URL controlada
pelo atacante. A pergunta que decide o caso não é *"este dado flui até aqui?"* —
que o taint responde — mas *"esta entrada é do usuário?"*, que nenhum analisador
responde sem especificação externa.

## 5. SonarQube — zero, por motivo estrutural

O SonarQube Community não recuperou nenhum caso, e a causa não é profundidade de
análise:

| | |
|---|---|
| Regras de Go no catálogo | **36** — 29 `CODE_SMELL` + 7 `BUG` |
| Regras de Go de segurança | **0** |
| Regras de taint (S2076, S2083, S5131, S5144) | não existem na instância |

Para dimensionar o abandono do Go na Community: Java tem 768 regras, TypeScript
546, JavaScript 528, Python 444. Go tem 36.

Ele processou **62.724 issues** nos 14 repositórios, 2.138 de regras `go:`. Nos
arquivos-alvo, o que disparou foi:

| regra | o que é | ocorrências |
|---|---|---|
| `go:S3776` | complexidade cognitiva alta | 34 |
| `go:S1135` | há um comentário TODO | 20 |
| `go:S1192` | string literal duplicada | 13 |
| `go:S1871` | branches duplicados | 4 |

Sobre 61,7 % dos arquivos-alvo ele tinha algo a dizer — e o que tinha a dizer era
que a função está complexa e há um TODO pendente.

**Ressalva de precisão:** o SonarQube *emitiu* 66 issues de segurança nos 14
repositórios. Todas em **Dockerfile e YAML de Kubernetes** (`docker:S6470/S6471`,
`kubernetes:S6428/S6431/S6864/S6865`). Nenhuma em código Go. A afirmação correta é
*"não possui regras de segurança para Go"*, não *"não possui regras de segurança"*.

Comparação de catálogo:

| | regras Go | de segurança |
|---|---|---|
| Semgrep OSS `p/default` | 84 | 84 |
| SonarQube Community | 36 | **0** |

Trocar Semgrep por SonarQube Community seria **regressão**, não alternativa.

## 6. Conclusão

**Trocar de motor não abre o funil.** Dos 47 arquivos vulneráveis testados, **44
são invisíveis aos três motores**.

Extrapolar os 6,4 % do CodeQL para os 778 casos perdidos levaria os 19 vulneráveis
que hoje chegam ao LLM para algo entre 60 e 70 — e isso **superestima**, porque a
amostra foi escolhida no melhor cenário do CodeQL. Sobre os outros 418 casos
perdidos, de CWE-400, CWE-200 e CWE-345, não há razão para esperar sequer isso.

O CodeQL emitiu **231 achados** nesses arquivos: ele não ficou cego, encontrou
coisas — só não *aquela* coisa. Em 13,6 % dos casos alertou **outra** CWE no
arquivo certo. É o mesmo desalinhamento entre ferramenta e gabarito já medido no
Semgrep, e a origem não é técnica: a CVE descreve a fraqueza pelo **impacto de
segurança**, enquanto a regra estática procura um **padrão sintático**.

O espelho disso explica por que a classe negativa funciona: os 791 falsos
positivos do SastBench nasceram do próprio Semgrep, então o alinhamento é
garantido por construção. Trocar de motor quebraria o lado que funciona — a
medição de 2026-06-17 registrou **6 de 43** falsos positivos reproduzidos pelo
CodeQL — para ganhar 6 % no lado que não funciona.

### Consequência para o §9 da Rodada 3

A tabela "O que ainda poderia elevar o `n`" estima que o Semgrep Pro *"atacaria
CWE-918 e CWE-22"*. A sonda sustenta a metade do CWE-22 e contradiz a do CWE-918.
Como as duas têm peso quase igual no corpus (114 e 112 pares), quem investisse na
ferramenta paga esperando os dois baldes compraria **metade** do que imagina.

## 7. Limitações desta sonda

- **81 casos de 778**, com repositórios escolhidos por conveniência (tamanho) e
  CWEs escolhidas por conveniência do concorrente (só taint). Serve para decidir
  se vale investir; **não é estimativa da população**.
- **A amostra do CWE-22 é pequena** — 8 arquivos, 2 recuperados, e os 10 casos vêm
  de 3 arquivos. A direção contra o zero do Semgrep é clara; o número 25 % é
  frágil. Ver §8 para a reamostragem aleatória.
- **`build-mode=none` não existe para Go** no CodeQL 2.27.0, então todo banco sai
  de autobuild real. Um repositório (`getarcaneapp/arcane`) exigiu apontar o
  `source-root` para o subdiretório com `go.mod`.
- **SonarQube Community**, não Developer Edition. As regras de injeção baseadas em
  taint são das edições pagas — o que é, em si, o resultado.

## 8. Reamostragem do CWE-22

Para tornar o número do CWE-22 defensável, uma segunda sonda amostrou
**aleatoriamente 40 arquivos** (semente 42) do universo de 86 arquivos distintos
com caso de CWE-22 perdido, espalhados por 46 repositórios.

<!-- RESULTADO-CWE22 -->

## 9. Como reproduzir

Artefatos em `C:\sonda\` (primeira sonda) e `C:\sonda22\` (reamostragem), fora do
repositório por volume (629 MB na primeira).

| | comando |
|---|---|
| **A** | `codeql database create <db> --language=go --source-root=<repo>` |
| **B** | `codeql database analyze <db> codeql/go-queries:codeql-suites/go-security-extended.qls --format=sarif-latest --output=<sarif>` |
| **C** | `python C:\sonda\comparar.py` — emparelha SARIF do CodeQL contra a amostra |
| **D** | `python C:\sonda\comparar_sonar.py` — idem para o SonarQube |
| **E** | `docker run -d -p 9000:9000 -e SONAR_CE_JAVAOPTS="-Xmx4g" sonarqube:community` |

**Duas armadilhas encontradas, ambas capazes de produzir zero falso:**

1. O Compute Engine do SonarQube roda com `-Xmx512m` por padrão e **falha com
   `OutOfMemoryError`** em repositórios grandes. A API de issues devolve `total=0`
   sem indicar que o processamento falhou. É preciso consultar
   `api/ce/component` até `status=SUCCESS` **antes** de ler as issues.
2. Os clones precisam de caminho curto: o `zalando/skipper` estoura o `MAX_PATH`
   do Windows por causa de `testdata/` profundo.
