# Rodada 3 — a classe positiva sob colheita filtrada por alcançabilidade

## 1. Identificação da rodada

| campo | valor |
|---|---|
| `run_id` | `20260908T094808Z-9a00cb2` |
| commit | `9a00cb2` + as mudanças `trilha-tp-alcancavel` e `identificador-de-caso-unico` |
| comando | `run_pipeline.py --tudo --modelo ollama:qwen2.5-coder:7b --prompt baseline --prompt especialista --run-id 20260908T094808Z-9a00cb2` |
| modelo | `ollama:qwen2.5-coder:7b`, digest `dae161e27b0e`, Ollama 0.32.5 |
| quantização | `Q4_K_M`, 7,6 B parâmetros, 100 % GPU |
| `num_ctx` / `num_predict` | 8192 / 512 |
| semente | 42 |
| Semgrep | 1.167.0, ruleset `p/default` (ver ressalva em §7.1) |
| catálogo de CWE | sha256 `e5db7d400842…` |
| versões de prompt | `baseline:597fcfa9`, `especialista:d1145f8b` — idênticas às das Rodadas 1 e 2 |
| população | **2328** casos — FP 791, TP_ouro 32, TP_prata 68, TP_dataset 57, **TP_alcancavel 1380** |
| `versao_pareamento` | 2 (identificador completo de CWE, sem fallback) |

Modelo, quantização, semente, prompts, catálogo e regra de pareamento são os mesmos
da Rodada 2. **A variável alterada é a população**, que cresceu de 948 para 2328
casos com a entrada da trilha `TP_alcancavel`.

> **Esta rodada NÃO é comparável caso a caso com as Rodadas 1 e 2.** A população
> difere: 1380 casos novos entraram, e nenhum deles existia antes. Métricas que
> dependem da composição — TRA simbólica, proporção de FP filtrados, contagens
> absolutas de qualquer célula — mudam por causa da composição, não do
> comportamento do motor ou do modelo. A comparação legítima nesta rodada é
> **entre braços dentro dela**, que é pareada por construção: os dois braços
> cobrem exatamente os mesmos 2328 identificadores. As Rodadas 1 e 2 continuam
> válidas e comparáveis entre si; nada nelas foi invalidado.

### Ressalva sobre a duração registrada

O `manifesto.json` registra apenas a última retomada. A execução real somou cerca
de 2 h 14 min da primeira passagem, 1 h 32 min de duas varreduras de Fase 1
isoladas, e poucos minutos de retomadas (§7.2). Nenhuma medição de tempo de
parede desta rodada deve ser usada como custo de execução.

## 2. Composição da população

| trilha | casos | vulneráveis | seguros | procedência |
|---|---|---|---|---|
| `FP` | 791 | 0 | 791 | SastBench, classe negativa |
| `TP_ouro` | 32 | 16 | 16 | pares CVE curados à mão |
| `TP_prata` | 68 | 34 | 34 | colheita OSV **sem** filtro |
| `TP_dataset` | 57 | 57 | 0 | alertas do dataset marcados como TP |
| **`TP_alcancavel`** | **1380** | **690** | **690** | **colheita OSV filtrada por alcançabilidade** |
| **total** | **2328** | **797** | **1531** | |

A classe negativa do SastBench permanece intacta: 791 casos `FP`, com os mesmos
identificadores das rodadas anteriores. Os casos de CWE inalcançável **não** foram
removidos — continuam como evidência do ponto cego (§7.4).

### Como a trilha nova foi construída, e por que ela é o teto

A colheita foi executada duas vezes, e a segunda define o limite empírico da
fonte:

| | 1ª colheita | 2ª colheita |
|---|---|---|
| `--por-repo` | 5 | **20** |
| entradas varridas | 9.113 (**dump inteiro**) | 9.113 (**dump inteiro**) |
| candidatas aceitas | 675 | **810** |
| repositórios distintos | 362 | 362 |
| repositórios no teto | 38 | **2** |

**A fonte está esgotada.** Com o teto em 20, apenas dois repositórios
(`mattermost/mattermost` e `gogs/gogs`) o alcançam — afrouxá-lo mais não
produziria candidatas relevantes. As 810 são tudo o que o corpus Go da OSV
oferece sob o critério de alcançabilidade.

Das 810 candidatas, `fetch_raso.py` obteve 799 commits de fix (11 falhas por ref
reescrita no remoto) e `tp_reconstruct.py` produziu **690 pares diferenciais** em
191 repositórios.

Distribuição das recusas na colheita (8.950 ocorrências de CWE recusadas):
`(sem CWE declarada)` 2.356 · controle de acesso (863, 284, 862, 285, 269, 306)
~1.815 · `CWE-20` 340 · cauda longa com o restante. O corte cai onde a teoria
prevê: as CWEs aceitas são as **sintaticamente expressáveis**; as recusadas são
majoritariamente **lógica de autorização**, para a qual não existe padrão de
código que diga "faltou checar permissão aqui".

## 3. O resultado principal: o funil não abre, e escalar não o abre

**Dos 690 casos vulneráveis da colheita filtrada, 18 chegaram ao LLM.**

| degrau do funil | casos | taxa |
|---|---|---|
| candidatas colhidas da OSV (CWE alcançável) | 810 | — |
| pares reconstruídos = casos vulneráveis | 690 | 85,2 % |
| detectados pelo Semgrep na CWE do gabarito | 18 | **2,61 %** |
| com veredito válido do LLM | 18 | 2,61 % |

O achado decisivo está na comparação com a colheita menor, feita antes na mesma
rodada:

| | 257 pares | 690 pares |
|---|---|---|
| vulneráveis detectados | 11 | 18 |
| taxa de detecção | **4,28 %** | **2,61 %** |

**Triplicar a colheita multiplicou as detecções por 1,6, e a taxa caiu.** Os
primeiros 257 pares eram a cabeça fácil do dump; a cauda rende menos. Isso é
evidência direta de retorno decrescente: não se trata de "faltou colher mais",
porque colher mais é justamente o que produziu uma taxa pior — e não há mais o que
colher.

### Onde as detecções se concentram

| CWE | detecções |
|---|---|
| CWE-89 (SQL Injection) | 7 |
| CWE-79 (XSS) | 5 |
| CWE-601 (Open Redirect) | 3 |
| CWE-614 (cookie sem `Secure`) | 2 |
| CWE-94 (Code Injection) | 1 |
| CWE-918 (SSRF) | 1 |

Nenhuma detecção em CWE-22 (114 pares), CWE-400 (124), CWE-200 (92), CWE-345
(45) ou CWE-78 (24) — que somam **399 pares e zero alertas na CWE certa**. A §8
explica por quê.

### Rendimento isolado por procedência

| trilha | vulneráveis | chegaram ao LLM | taxa |
|---|---|---|---|
| `TP_ouro` | 16 | 0 | 0,00 % |
| `TP_prata` | 34 | 0 | 0,00 % |
| `TP_dataset` | 57 | 1 | 1,75 % |
| **`TP_alcancavel`** | **690** | **18** | **2,61 %** |
| total | 797 | **19** | 2,38 % |

**O ganho veio inteiramente da colheita filtrada.** 18 dos 19 casos avaliados são
dela; as duas trilhas de colheita antiga contribuíram com **zero**. O filtro de
alcançabilidade funcionou no que prometia — a amostra saiu de 1 para 19 — mas 19
continua abaixo de 30.

### Critério de aceite: não atingido

`src/metricas.py` mantém o aviso nos dois braços:

```
[!] PODER ESTATÍSTICO LIMITADO: apenas 19 amostras vulneráveis chegaram ao LLM
    com veredito válido (mínimo sugerido: 30).
```

`Recall`, `F1`, `MCC` e `TFN` do eixo neural **continuam não reportáveis** como
conclusão.

### O que foi tentado para chegar a 30, e por que parou aqui

Três alavancas foram avaliadas, e o registro delas importa tanto quanto o
resultado:

1. **Aumentar a colheita** — feito. `--alvo` de 300 para 1200, varrendo o dump
   inteiro. Rendeu 810 candidatas e a taxa **caiu**.
2. **Afrouxar o teto por repositório** — feito. `--por-repo` de 5 para 20. Rendeu
   +135 candidatas, e sobraram apenas 2 repositórios no teto: a fonte acabou.
3. **Incluir pares de extração por janela** (`--incluir-janela`) — **medido e
   rejeitado**. Acrescentaria 156 pares, mas quase todos em CWEs de taxa zero
   (CWE-22 +78, CWE-200 +19, CWE-400 +17): ganho esperado de **0,6 detecção** em
   troca de degradar a precisão do pool. Não compensa.

Uma quarta alavanca foi **deliberadamente recusada**: afrouxar o guarda
anti-refactor (`--max-funcs-por-fix`), que descarta CVEs cujo fix altera mais de 8
funções. Ele descarta milhares de candidatos a par e elevaria o `n` com folga —
mas num commit que altera 30 funções em 10 arquivos a maioria dos arquivos não
carrega a vulnerabilidade. Marcá-los como vulneráveis injetaria falsos positivos
no gabarito, e uma detecção do Semgrep sobre um deles seria contada como acerto
sobre arquivo que não é vulnerável. **Isso inflaria o recall artificialmente**, que
é exatamente o vício que estas mudanças existem para não cometer. Pelo mesmo
motivo a colheita não foi enviesada para as CWEs de alta detecção: selecionar os
casos em que a ferramenta acerta mede a seleção, não a ferramenta.

## 4. Movimento nas duas classes

### 4.1 Classe positiva

| | Rodada 2 | Rodada 3 |
|---|---|---|
| casos vulneráveis na população | 107 | **797** |
| Semgrep VP (detectou a CWE rotulada) | 1 | **19** |
| Semgrep FN (ponto cego simbólico) | 106 | **778** |
| chegaram ao LLM | 1 | **19** |
| taxa de detecção | 0,93 % | **2,38 %** |

O `Recall` do Semgrep sobre a CWE rotulada vai de 0,0093 para **0,0238** e a TFN
cai de 0,9907 para 0,9762. A melhora é real, mas a leitura honesta é a do
complemento: **o motor simbólico não alcança a fraqueza rotulada em 97,6 % dos
casos vulneráveis**, mesmo com a colheita restrita às fraquezas que o catálogo de
regras declara cobrir.

### 4.2 Classe negativa

| | Rodada 2 | Rodada 3 |
|---|---|---|
| casos seguros na população | 841 | **1531** |
| Semgrep FP (ruído sobre código seguro) | 788 | 808 |
| Semgrep VN (silêncio correto) | 51 | **723** |

Os 690 casos seguros novos são as versões **corrigidas** dos pares da trilha nova.
Quase todos produzem silêncio correto, o que infla `VN`. Os 791 casos `FP` do
SastBench continuam os mesmos.

### 4.3 Por que a TRA simbólica não é comparável entre rodadas

| métrica (matriz simbólica) | Rodada 2 | Rodada 3 |
|---|---|---|
| TRA (redução de alertas) | 0,1660 | 0,6453 |
| Prop. de FP filtrados | 0,0608 | 0,4729 |
| MCC | −0,7916 | −0,4993 |
| Recall | 0,0093 | 0,0238 |

O salto da TRA de 0,1660 para 0,6453 **não é melhora do motor**. Ela mede a fração
de casos em que o Semgrep se cala, e a população ganhou 690 casos seguros sobre os
quais ele se cala corretamente. É efeito de composição, e é o motivo concreto do
aviso de não comparabilidade do §1.

## 5. TRA e proporção de FP filtrados (matriz de acerto do LLM)

| braço | n | VP | VN | FP | FN | Precisão | Recall | F1 | MCC | **TRA** | TFN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 825 | 8 | 690 | 116 | 11 | 0,0645 | 0,4211 | 0,1119 | 0,1163 | **0,8497** | 0,5789 |
| especialista | 827 | 3 | 796 | 12 | 16 | 0,2000 | 0,1579 | 0,1765 | 0,1606 | **0,9819** | 0,8421 |

**O resultado central do trabalho sobrevive.** A TRA do braço especialista é
**0,9819**, contra 0,9874 na Rodada 2 e 0,9851 na Rodada 1 — praticamente imóvel,
com a população 146 % maior. O prompt especialista filtra 98,19 % do ruído que o
motor simbólico produz.

`Precisao`, `Recall`, `F1` e `MCC` das duas linhas **não devem ser reportados**:
descansam sobre 19 amostras vulneráveis. O `Recall` de 0,4211 do baseline é
"acertou 8 de 19".

## 6. McNemar — o resultado principal é estável

| | Rodada 2 | Rodada 3 |
|---|---|---|
| n pareado | 789 | **825** |
| ambos acertam | 678 | 693 |
| só baseline acerta | 0 | **5** |
| só especialista acerta | 100 | **104** |
| ambos erram | 11 | 23 |
| χ² (Yates) | 98,01 | **88,11** |
| p-valor | < 0,0001 | **< 0,0001** |

A assimetria se mantém com folga: **104 casos em que só o especialista acerta,
contra 5 em que só o baseline acerta**. A superioridade do prompt especialista na
filtragem de falsos positivos atravessa três rodadas, duas regras de pareamento e
três populações diferentes. É a conclusão mais robusta do experimento.

## 7. Ressalvas

### 7.1 O ruleset continua não fixado, mas foi revalidado

`p/default` é nome de coleção do registry, não versão fixada, e o eixo
`versao_ruleset` do cache simbólico grava a string — que não muda quando o
conteúdo por trás dela muda (`ANALISE-RODADA-2.md` §6.1).

Nesta rodada o risco foi mitigado por medição. O snapshot usado pela colheita
tinha 39 dias (`2026-07-31T00:21:45-03:00`, 1.074 regras). Antes de reconstruir os
pares, o ruleset corrente foi buscado para caminho separado e comparado: **1.074
regras, as mesmas 34 CWEs alcançáveis em Go, zero perdidas e zero ganhas.**
Nenhuma candidata tinha CWE que houvesse saído do ruleset.

Fixar o ruleset por hash de conteúdo continua sendo candidato a mudança própria.

### 7.2 A rodada falhou por exaustão de memória e foi retomada

A primeira passagem terminou com **488 casos em `SEMGREP_ERROR`**, todos da trilha
`TP_alcancavel`, a partir do caso 908:

```
Semgrep rc=3221225794 não produziu SARIF em template.go
```

`3221225794` é `0xC0000142` — `STATUS_DLL_INIT_FAILED`. **O Semgrep não chegou a
iniciar**: o Windows não conseguiu criar o processo. Causa: o `llama-server`
mantinha 11,6 GB residentes, e a trilha nova é a única que exigia varredura fresca
— as demais vinham do cache simbólico e nunca invocaram o Semgrep. Enquanto só
havia leitura de cache não houve conflito; quando o Semgrep precisou nascer, não
havia memória. A aritmética confirma que nenhuma varredura nova teve êxito: o
resumo registrou `974 reaproveitados, 0 gravados`.

Recuperação, pelo procedimento previsto: as linhas em categoria de erro foram
removidas dos CSVs — obrigatório, porque falha de esteira **não** é checkpointada
(`run_pipeline.py:506`) e a retomada geraria identificador duplicado, que
`metricas.py` resolveria pela ocorrência errada. O modelo foi descarregado, a
Fase 1 rodou isolada com `--sem-llm` (**1380/1380, zero falhas**) e a rodada foi
retomada com o mesmo `--run-id`, já lendo a Fase 1 do cache.

**Isto não é apenas incidente operacional: é restrição real da esteira em máquina
única.** O motor simbólico e o modelo local disputam a mesma memória, e a ordem de
montagem da população esconde o conflito até o ponto em que ele custa horas.
**Recomendação: separar Fase 1 completa das fases neurais em duas invocações** —
`--sem-llm` primeiro, com o modelo descarregado, e a rodada depois.

### 7.3 Dois casos de falha de esteira, os mesmos das rodadas anteriores

O braço baseline mantém 2 casos em `API_ERROR`, do grupo `be0de1ab:CWE-79`
(`harness/harness`). É o laço degenerativo de espaços em branco descrito em
`ANALISE-RODADA-2.md` §6.2 — modo de falha conhecido de modelo pequeno quantizado.
Reapareceu em **todas** as retomadas, o que confirma a reprodutibilidade. Como
falha de esteira não é checkpointada, cada retomada gravou uma linha nova para
esses casos; as duplicatas foram removidas, mantendo uma linha por caso. Como o
McNemar é pareado, os 2 casos saem da comparação; o `n` pareado de 825 já reflete
isso.

### 7.4 Os casos de CWE inalcançável continuam na população

**75 dos 797 casos vulneráveis (9,41 %) têm CWE que nenhuma regra Go do
`p/default` declara.** Todos terminam em `NAO_DETECTADO` — 55 por `SEM_ALERTA` e
20 por `ALERTA_OUTRA_CWE` — e aparecem na matriz de cobertura como ponto cego
simbólico, fora da matriz de acerto do LLM.

São **os mesmos 75** da Rodada 2, onde representavam 70,09 % de uma população
vulnerável de 107. Nenhum foi removido. O que mudou é o denominador. **A queda de
70,1 % para 9,41 % é diluição, não correção** — e a afirmação do capítulo de
limitações, de que 70,1 % das fraquezas daquele corpus estavam fora do alcance da
análise sintática, continua verdadeira sobre aquele corpus.

## 8. Por que umas CWEs detectam e outras não

Das 1.074 regras do `p/default`, **apenas 84 rodam em Go**. A tabela cruza a
quantidade de regras por CWE com a taxa medida:

| CWE | regras Go em `p/default` | regras em `p/golang` | pares | detecções | taxa |
|---|---|---|---|---|---|
| 89 SQL Injection | 8 | 4 | 18 | 7 | **38,9 %** |
| 601 Open Redirect | 1 | 1 | 10 | 3 | 30,0 % |
| 79 XSS | 12 | 3 | 57 | 5 | 8,8 % |
| 94 Code Injection | 5 | 1 | 26 | 1 | 3,8 % |
| 918 SSRF | 1 | 1 | 112 | 1 | 0,9 % |
| **22 Path Traversal** | **2** | 1 | **114** | **0** | **0,0 %** |
| 400 Resource Exhaustion | 1 | 0 | 124 | 0 | 0,0 % |
| 200 Info Exposure | 1 | 1 | 92 | 0 | 0,0 % |
| 78 OS Command Injection | 1 | 0 | 24 | 0 | 0,0 % |

A explicação não é a contagem de regras. É **se a fraqueza tem forma sintática
local**:

- **CWE-89 detecta** porque injeção de SQL em Go tem forma canônica —
  `db.Query(fmt.Sprintf(...))` ou concatenação entregue ao driver. O defeito cabe
  numa linha e o código correto é visivelmente diferente (`db.Query("… ?", x)`).
- **CWE-22 não detecta**, com 114 pares e duas regras estreitas
  (`filepath-clean-misuse` e Zip Slip). O caso geral é
  `os.Open(filepath.Join(base, entradaDoUsuario))` — **sintaticamente idêntico à
  versão segura**. Se é vulnerável depende de a entrada ser controlável e de não
  ter sido validada em outro lugar: pergunta semântica, sobre fluxo de dados.
- **CWE-918 não detecta** porque sua única regra é de taint e exige origem e
  destino no mesmo arquivo. SSRF real atravessa camadas — a URL é montada num
  handler, validada num serviço, buscada num cliente HTTP.
- **CWE-79 rende pouco apesar de 12 regras** porque elas miram o *sink* canônico
  (`Fprintf` no `http.ResponseWriter`, `text/template` no lugar de `html/template`),
  enquanto XSS real passa por framework (`c.HTML` do gin) ou por API JSON.

> **Adendo de 2026-09-11 — as duas hipóteses acima foram testadas, e só uma
> sobrevive.** Uma sonda executou o CodeQL — que tem fluxo interprocedural e entre
> arquivos, exatamente a capacidade apontada como faltante — sobre 81 casos
> vulneráveis que o Semgrep não detectou, em 14 repositórios. Metodologia e
> resultados completos em `docs/SONDA-MOTORES.md`.
>
> | CWE | Semgrep, esta rodada | CodeQL medido | hipótese |
> |---|---|---|---|
> | **CWE-22** | 0 de 114 — 0,0 % | 10 de 23 casos — **43,5 %** | ✅ confirmada |
> | **CWE-918** | 1 de 112 — 0,9 % | 1 de 43 casos — **2,3 %** | ❌ refutada |
>
> Para o CWE-22 o diagnóstico acima está certo: dar fluxo de dados tira a detecção
> de zero. Para o CWE-918 está incompleto — a capacidade foi fornecida, sobre 29
> arquivos de 6 repositórios distintos, e o SSRF continuou invisível.
>
> A explicação provável é a mesma dada aqui ao CWE-22 e não estendida ao CWE-918:
> uma URL montada a partir de configuração ou de campo de struct é
> **sintaticamente indistinguível** de uma URL controlada pelo atacante. A pergunta
> que decide o caso não é *"este dado flui até aqui?"* — que o taint responde —
> mas *"esta entrada é do usuário?"*, que nenhum analisador responde sem
> especificação externa.

### Sobre trocar para `p/golang`

**Seria estritamente pior.** `p/golang` tem 42 regras, contra as 84 de Go dentro do
`p/default`. A interseção é quase total: 23 CWEs em ambos, **11 só no `p/default`**
(78, 362, 377, 400, 470, 476, 489, 665, 667, 681, 688) e apenas 2 só no `p/golang`
(289, 548), nenhuma presente no corpus. Em nenhuma das CWEs produtivas o
`p/golang` acrescenta regra relevante.

### O grau de alcançabilidade, medido

A distinção acima deixou de ser qualitativa. A mudança `alcancabilidade-ponderada`
classifica cada CWE em três graus, derivados de campos **declarados pelas próprias
regras** — `metadata.subcategory` (a regra afirma detectar vulnerabilidade, ou
apenas sinaliza para auditoria?) e `mode: taint` (depende de fluxo que o motor não
resolve entre arquivos?).

Aplicado aos 690 pares desta rodada:

| grau | critério | CWEs | pares | detecções | taxa |
|---|---|---|---|---|---|
| `alta` | ≥1 regra de vulnerabilidade, não-taint | 8 | 115 | 13 | **11,30 %** |
| `media` | ≥1 regra de vulnerabilidade, todas de taint | 4 | 239 | 4 | **1,67 %** |
| `baixa` | só regras de auditoria | 9 | 336 | **1** | **0,30 %** |

**As CWEs de grau baixo consumiram 336 dos 690 pares — metade do orçamento de
colheita — e renderam uma única detecção.** Recusá-las teria concentrado a amostra
com ganho de densidade de **16,1×**, ao custo de perder 1 detecção.

A separação não depende de uma única fraqueza: removendo CWE-89, que sozinha
responde por 7 das 18 detecções, o ganho cai para 10,0× e continua nítido.

Contagem de regras, note-se, **não** prevê nada (r = +0,16 contra a taxa
observada): CWE-327 tem 8 regras Go e 0 %; CWE-601 tem 1 e 30 %. O que prevê é o
grau declarado da regra, não quantas existem.

> **Ressalva de circularidade.** O critério foi escolhido entre cinco candidatos
> **olhando** a taxa desta rodada. A separação acima é **observada nesta amostra**,
> não prevista para outra. Validá-la exige repetir a medição sobre uma rodada que
> não a gerou — `python scripts/analise_rodada.py <rodada> --secao grau`. Enquanto
> isso não ocorrer, o texto deve tratá-la como observação, e é assim que a própria
> saída do comando a rotula.

O grau **não** foi usado para redefinir a população desta rodada, e a colheita
continua aceitando toda CWE alcançável por padrão. Restringir por grau existe como
opção explícita (`--grau-minimo`), porque trocaria o denominador do recall: passaria
a medir o motor sobre as fraquezas em que ele *afirma* detectar, e não sobre as que
*declara cobrir*.

### Consequência metodológica

**A noção binária de "alcançável" superestima a cobertura.** A colheita aceita uma
CWE se *pelo menos uma* regra a declara — foi assim que CWE-918 entrou com 112
pares tendo uma única regra de taint intraarquivo, e CWE-22 com 114 pares tendo
duas regras que não cobrem o caso geral. Uma noção ponderada (quantas regras, e de
que tipo — sintática local *versus* taint) preveria o rendimento muito melhor.

Isso não foi alterado aqui, porque mudar o critério da colheita no meio da
execução invalidaria a comparação. Fica registrado como candidato a mudança
própria, e é material direto para a discussão: **a distinção entre "a ferramenta
declara cobrir" e "a ferramenta encontra" é o que este experimento mediu.**

## 9. A Q2 passou a ser respondível por inteiro?

**Não.**

A primeira metade — *"em que proporção a arquitetura reduz o volume de falsos
positivos"* — está respondida e é robusta: TRA de **0,9819** no braço especialista,
McNemar p < 0,0001 e 104 contra 5 na tabela de discordância, estável em três
rodadas e três populações.

A segunda metade — *"sem introduzir falsos negativos"* — continua sem resposta
conclusiva. São 19 amostras vulneráveis contra o mínimo de 30.

O que esta rodada acrescenta é **o motivo, medido, e o teto da fonte**:

1. Restringir a colheita às fraquezas que a ferramenta declara cobrir eleva a taxa
   de detecção de 0,93 % para 2,38 % — e para.
2. **Triplicar a colheita fez a taxa cair de 4,28 % para 2,61 %**: retorno
   decrescente, não escassez de esforço.
3. O corpus Go da OSV foi varrido por inteiro, com teto de repositório frouxo. Não
   existe mais o que colher.

A conclusão publicável, portanto, não é "faltou amostra". É: **nem varrendo o
corpus Go inteiro da OSV, restrito às fraquezas que o catálogo de regras declara
cobrir, se obtém amostra de 30 vulnerabilidades reais que a análise sintática
detecte.** O gargalo não é a colheita, nem o LLM, nem o tamanho do corpus — é a
análise sintática não reconhecer, no código real, as fraquezas que seu próprio
catálogo diz cobrir.

Isso estava previsto antes de rodar, na seção de riscos do design da mudança
`rodada-classe-positiva`, justamente para não ser lido como insucesso depois.

### O que ainda poderia elevar o `n`

Nenhum caminho é gratuito, e todos mudam o objeto medido:

| caminho | efeito | custo |
|---|---|---|
| outra linguagem além de Go | amplia a fonte | muda o escopo do TCC |
| Semgrep Pro (taint entre arquivos) | atacaria CWE-918 e CWE-22 | ferramenta paga; muda a variável medida |
| regras próprias para CWE-22 | atacaria o maior balde | mede as regras do autor, não a ferramenta |
| aceitar `n` = 19 | reporta TRA e McNemar; omite Recall/F1/MCC | **é o estado atual** |

> **Adendo de 2026-09-11 — a linha do taint entre arquivos foi medida, e vale pela
> metade.** A sonda de `docs/SONDA-MOTORES.md` executou o CodeQL, que já tem a
> capacidade atribuída ao Semgrep Pro, sobre 81 casos perdidos:
>
> | caminho | efeito estimado | efeito medido |
> |---|---|---|
> | taint entre arquivos, **CWE-22** | atacaria o balde | ✅ 0,0 % → **43,5 %** dos casos |
> | taint entre arquivos, **CWE-918** | atacaria o balde | ❌ 0,9 % → **2,3 %** — não ataca |
> | **trocar de motor (CodeQL)** | *não estava na tabela* | **3 de 47 arquivos — 6,4 %** |
> | **trocar de motor (SonarQube CE)** | *não estava na tabela* | **0 de 81** — zero regras de segurança para Go |
>
> Como CWE-22 e CWE-918 têm peso quase igual no corpus (114 e 112 pares), quem
> investisse na ferramenta paga esperando os dois baldes compraria metade do que
> imagina.
>
> Extrapolando os 6,4 % para os 778 casos perdidos, os 19 vulneráveis iriam para
> algo entre 60 e 70 — e isso **superestima**, porque a amostra foi escolhida no
> melhor cenário do concorrente (só CWEs de taint, repositórios pequenos). Dos 47
> arquivos testados, **44 são invisíveis aos três motores**.
>
> A conclusão do §9 sai reforçada: o gargalo não é do Semgrep, é da análise
> sintática. Ver `docs/PESQUISA-GARGALO-ADENDO-MEDICOES.md` para o cruzamento com
> o relatório de pesquisa.

## 10. Como reproduzir

| | comando |
|---|---|
| **A** | `python src/metricas.py results/20260908T094808Z-9a00cb2 --mcnemar` |
| **B** | `python src/metricas.py results/20260731T140000Z-af9bc32 --mcnemar` |
| **C** | `python scripts/pares_alcancaveis.py --json` |
| **D** | `python scripts/analise_rodada.py results/20260908T094808Z-9a00cb2 --secao funil` |
| **E** | `python scripts/analise_rodada.py results/20260908T094808Z-9a00cb2 --secao grau` |

Colheita e reconstrução, na ordem que evita a falha do §7.2:

```
python scripts/osv_harvest_go.py --alvo 1200 --por-repo 20 --max-scan 9200
python scripts/fetch_raso.py     --input data/tp_fixes_osv_alcancavel.json
python scripts/tp_reconstruct.py --input data/tp_fixes_osv_alcancavel.json
python scripts/preencher_cache.py
ollama stop qwen2.5-coder:7b
python run_pipeline.py --tudo --trilha TP_alcancavel --sem-llm --run-id <scratch>
python run_pipeline.py --tudo --modelo ollama:qwen2.5-coder:7b \
       --prompt baseline --prompt especialista --run-id <run_id>
```

`results/`, `cache/` e `cache_simbolico*/` não são versionados (ver `.gitignore`),
então precisam existir localmente.
