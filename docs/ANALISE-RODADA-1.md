# Análise da Rodada 1 — o que ela mede e o que ela não mede

## 1. Identificação da rodada

| campo | valor |
|---|---|
| `run_id` | `20260730T180648Z-14d6af8` |
| commit | `14d6af8` |
| comando | `run_pipeline.py --tudo --modelo ollama:qwen2.5-coder:7b --prompt baseline --prompt especialista` |
| início / fim (UTC) | 2026-07-30 18:06:48 → 20:57:11 |
| duração | 10.223,51 s (2 h 50 min) |
| modelo | `ollama:qwen2.5-coder:7b`, digest `dae161e27b0e`, Ollama 0.32.5 |
| quantização | `Q4_K_M`, 7,6 B parâmetros, 100 % GPU |
| `num_ctx` / `num_predict` | 8192 / 512 |
| semente | 42 |
| Semgrep | 1.167.0, ruleset `p/default` |
| catálogo de CWE | `data/catalogo_cwe.json`, sha256 `a81b6f5ca3a4f70c…` (15 CWEs com ficha) |
| versões de prompt | `baseline:597fcfa9`, `especialista:d1145f8b` |
| população | 948 casos — FP 791, TP_ouro 32, TP_prata 68, TP_dataset 57 |
| chamadas de LLM | 1.616 |
| custo | US$ 0,00 (modelo local) |

Todos os campos acima saem de `results/20260730T180648Z-14d6af8/manifesto.json`.

> **Escopo temporal.** Este documento analisa esta rodada e não é atualizado
> retroativamente. A mudança que corrigir o emparelhamento (seção 7) é
> responsável por gerar sua própria rodada e sua própria análise.

### Como reproduzir os números deste documento

Os comandos abaixo são citados ao longo do texto pela letra. Todos rodam sem
rede e sem chamada de LLM. `results/` e `cache_simbolico*/` não são versionados
(ver `.gitignore`), então precisam existir localmente — o resto sai de artefatos
versionados.

| | comando |
|---|---|
| **A** | `python -m src.metricas results/20260730T180648Z-14d6af8 --mcnemar` |
| **B** | `python scripts/analise_rodada.py results/20260730T180648Z-14d6af8 --secao funil` |
| **C** | `python scripts/analise_rodada.py results/20260730T180648Z-14d6af8 --secao nao-detectados` |
| **D** | `python scripts/analise_rodada.py results/20260730T180648Z-14d6af8 --secao conjuntos` |
| **E** | `python scripts/analise_rodada.py results/20260730T180648Z-14d6af8 --secao esteira` |
| **F** | `python scripts/analise_rodada.py results/20260730T180648Z-14d6af8 --secao positivos --justificativa-completa --cache cache_simbolico_pre_estrito` |
| **G** | `python scripts/analise_rodada.py results/20260730T180648Z-14d6af8 --secao regras --cache cache_simbolico_pre_estrito` |
| **H** | `python -c "import math;k,n,z=18,22,1.959964;p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z/d*math.sqrt(p*(1-p)/n+z*z/(4*n*n));print(f'{p:.4f} [{c-h:.4f},{c+h:.4f}]')"` |
| **I** | `python -c "import glob,os,statistics;t=sorted(os.path.getmtime(f) for f in glob.glob('cache_simbolico/*/*/*.json'));g=[b-a for a,b in zip(t,t[1:]) if 0<b-a<=120];print(len(g),statistics.median(g),statistics.mean(g))"` |
| **J** | `python -c "print([(e,round(1.959964**2*0.25/e**2,1)) for e in (0.20,0.15,0.10,0.05)])"` |

**I mede tempo de parede por timestamp de arquivo, e é uma medição móvel.** O
intervalo entre gravações consecutivas do cache simbólico é o tempo que a Fase 1
mais a Fase 2 levaram naquele caso. É a única medição disponível dessa etapa — a
rodada analisada foi servida do cache e por isso não cronometrou o Semgrep. Mas
o `mtime` é reescrito por qualquer execução posterior que recompute o caso, e
uma cópia do diretório o destrói por completo. Duas medições em 2026-07-31 sobre
`cache_simbolico/`, separadas por algumas horas e por uma reexecução parcial da
pipeline:

| medição | intervalos contíguos | mediana | média |
|---|---|---|---|
| 1ª | 910 | 5,85 s | 5,57 s |
| 2ª | 711 | 5,93 s | 6,24 s |

Este documento usa **≈ 6 s por caso**, que é o que as duas sustentam. Rodar o
comando **I** hoje devolve um valor próximo disso, não idêntico: a população de
intervalos muda a cada reexecução. Toda estimativa derivada dele neste documento
é de ordem de grandeza — o que basta para as decisões da seção 9, nenhuma das
quais muda se o valor for 5 s ou 8 s.

**F e G usam `--cache cache_simbolico_pre_estrito` de propósito.** O CSV da rodada não
grava qual regra produziu cada alerta; esse dado só existe no cache simbólico.
`cache_simbolico/` vem sendo regravado desde esta rodada, sob a regra de
pareamento estrita que está em desenvolvimento — na verificação de 2026-07-31,
441 das 948 entradas já eram da regra nova, e uma reexecução em curso continuava
mudando o número. Ler dali descreveria outra pipeline.
`cache_simbolico_pre_estrito/` é a cópia congelada do cache como estava na
rodada: as 948 entradas com `versao_pareamento` ausente. O próprio script avisa
quando o cache está misto, e é por isso que ele avisa.

---

## 2. Sumário executivo

1. **A rodada mede supressão de ruído, e o resultado é sólido.** Sobre 792
   amostras de gabarito seguro, o prompt especialista reduziu os falsos positivos
   de 111 para 11, sem um único caso em que o baseline acerte e ele erre
   (p < 0,0001). Especificidade de 0,8598 para 0,9862. **Seções 3 e 4.**
2. **A rodada não mede detecção, e os números que sugerem o contrário são
   artefato.** Das 107 amostras vulneráveis, 94 nunca produziram alerta e, das 13
   que chegaram ao LLM, **12 foram pareadas ao alerta de outra fraqueza** por um
   fallback da Fase 1. Sobra 1 amostra válida. O único "Verdadeiro Positivo" da
   rodada é um erro do modelo sobre um alerta que era ruído, creditado por
   acidente. Recall, F1, MCC, Precisão e TFN devem ser **omitidos**. **Seções 5,
   6 e 4.5.**
3. **O caminho à frente é barato e está claro.** Executar a pipeline custa 27 min
   para n = 100, a custo zero; o gargalo é obter casos. Construir a classe
   positiva a partir das 84 regras Go do `p/default` — e não a partir de CVEs,
   cujo rendimento está medido em 0,9 % — atinge o n necessário de 43 com folga.
   **Seções 8 e 9.**

---

## 3. Os números da rodada

### 3.1 Matriz de acerto do LLM, por braço

Comando **A**.

| braço | n | VP | VN | FP | FN | Precisão | Recall | F1 | MCC | TRA | TFN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 805 | 1 | 681 | 111 | 12 | 0,0089 | 0,0769 | 0,0160 | −0,0230 | 0,8609 | 0,9231 |
| especialista | 808 | 1 | 784 | 11 | 12 | 0,0833 | 0,0769 | 0,0800 | 0,0656 | 0,9851 | 0,9231 |

Proporção de falsos positivos filtrados (especificidade): **0,8598** no baseline
(681 / 792) e **0,9862** no especialista (784 / 795) — comando **D**, coluna
"especificidade".

### 3.2 Os dois braços não têm o mesmo denominador

Comando **E**.

| braço | linhas | DETECTADO | classificados | erros de esteira | erro / linhas |
|---|---|---|---|---|---|
| baseline | 948 | 805 | 805 | 3 | 0,3 % |
| especialista | 948 | 808 | 808 | 0 | 0,0 % |

Três casos do braço baseline terminaram em `API_ERROR`: o modelo devolveu texto
que não era JSON parseável (a resposta bruta gravada na coluna
`Justificativa` começa com `{"verdict": "FP", "reasoning": "…`, truncada). São
`be0de1ab:CWE-79:false_positive#23`, `be0de1ab:CWE-79:false_positive#24` e
`c2b310d3:CWE-94:false_positive#4`, todos de gabarito seguro, e todos
classificados como Verdadeiro Negativo pelo especialista. Nenhum deles pertence
à classe positiva, então o funil de recall não é afetado; a comparação de
proporções entre os braços é.

**Regra de leitura:** toda proporção entre braços neste documento declara seu
denominador. O teste de McNemar opera só sobre os 805 casos que os dois braços
julgaram, e por isso não é afetado.

### 3.3 Cobertura simbólica (matriz do Semgrep, separada)

Comando **A**, bloco "Cobertura do Semgrep".

| | valor |
|---|---|
| Semgrep VP (alertou sobre código vulnerável) | 13 |
| Semgrep FN (não alertou sobre código vulnerável) | 94 |
| Semgrep FP (alertou sobre código seguro) | 792 |
| Semgrep VN (não alertou sobre código seguro) | 46 |

Duas ressalvas sobre esta matriz, ambas verificáveis por **E**:

1. Ela é calculada sobre 945 casos, não 948, porque herda a coluna
   `Status_Semgrep` do braço baseline, onde três casos viraram `API_ERROR`. O
   Semgrep detectou os três — o cache simbólico os registra como `DETECTADO` e o
   braço especialista os classificou normalmente. A coluna `Status_Semgrep`
   mistura duas etapas: se o motor simbólico alertou e se a chamada de LLM
   funcionou. Está listado como defeito corrigível na seção 7.
2. Os 792 "Semgrep FP" não são erros descobertos por este trabalho: a trilha FP
   do dataset **é**, por construção, um conjunto de achados do Semgrep rotulados
   como falsos positivos pelo SastBench. O número mede o tamanho do conjunto,
   não a taxa de erro do Semgrep em campo.

---

## 4. O que a rodada mede: a classe negativa

### 4.1 A base amostral que sustenta a medição

A classe negativa tem **792 amostras** no braço baseline e **795** no
especialista — coluna "n da classe negativa" do comando **D**, e igual ao
"Semgrep FP" do comando **A**. São alertas que o Semgrep emitiu sobre código que
o gabarito do SastBench declara seguro. Sobre esta base a medição tem poder: 792 é duas ordens de
grandeza acima do mínimo de 30 que `src/metricas.py` exige para não emitir aviso
de poder estatístico limitado.

### 4.2 O resultado: 111 → 11 falsos positivos

Comando **D**.

| braço | VP | VN | FP | FN |
|---|---|---|---|---|
| baseline | 1 | 681 | 111 | 12 |
| especialista | 1 | 784 | 11 | 12 |

O prompt especialista deixou passar **11 falsos positivos onde o baseline deixou
passar 111** — uma redução de 90,1 % no ruído que sobra para o desenvolvedor,
com denominadores de 792 e 795 respectivamente.

### 4.3 O aninhamento é estrito

Comando **D**.

| categoria | só baseline | interseção | só especialista | relação |
|---|---|---|---|---|
| VP | 0 | 1 | 0 | idênticos |
| FN | 0 | 12 | 0 | idênticos |
| FP | 100 | 11 | 0 | os FP do especialista estão contidos nos do baseline |
| VN | 0 | 681 | 103 | os VN do baseline estão contidos nos do especialista |

Tabela de discordâncias sobre os 805 casos julgados pelos dois braços:

| ambos acertam | só baseline acerta | só especialista acerta | ambos erram | discordâncias |
|---|---|---|---|---|
| 682 | **0** | 100 | 23 | 100 |

McNemar: qui-quadrado com correção de Yates = 98,0100, p < 0,0001 (comando
**A**). O resultado é o mais forte possível na forma: **não existe um único caso
em que o baseline acerta e o especialista erra.** A troca de prompt não é um
compromisso — é dominância.

### 4.4 Duas leituras concorrentes, e por que não são separáveis aqui

A leitura confortável é "o prompt especialista ensinou o modelo a reconhecer
falso positivo". Há uma leitura alternativa que os dados desta rodada explicam
igualmente bem: **o prompt especialista deslocou o limiar de decisão para
'seguro'.** A evidência que a sustenta:

- a taxa de veredito "vulnerável" caiu de **0,1391** (112 de 805) para **0,0149**
  (12 de 808) — comando **D**, última coluna;
- os 100 casos de ganho estão **todos** na classe negativa, que é 98 % do corpus;
- na classe positiva o especialista não ganhou nada: mesmos 12 FN, mesmo 1 VP,
  exatamente os mesmos `ID_Caso` (comando **D**, linhas VP e FN "idênticos").

Um modelo que simplesmente responde "seguro" com mais frequência produz
exatamente este padrão num corpus 98 % negativo: ganha muito na classe
majoritária, não perde nada na minoritária porque quase não havia o que perder.
Com 13 amostras positivas, um deslocamento monotônico de limiar e uma
discriminação de fato melhorada são **indistinguíveis**.

**Experimento que as separaria:** medir a taxa de veredito "vulnerável" dos dois
braços sobre uma classe positiva de tamanho suficiente. Se o especialista mantém
o recall do baseline enquanto derruba os FP, é discriminação; se o recall cai
junto, é limiar. Isso exige a classe positiva da seção 8.

### 4.5 Orientação de reporte de métricas

Cada métrica classificada pela base amostral que a sustenta. A regra é simples:
métrica cujo numerador ou denominador passa pelas células VP ou FN está
governada por **13 amostras, das quais 12 estão contaminadas** (seção 6) — resta
uma. Métrica que vive nas células VN e FP está sustentada por ~792.

| métrica | classificação | base amostral | justificativa |
|---|---|---|---|
| Proporção de FP filtrados (especificidade) | **reportável sem ressalva** | 792 / 795 | só usa VN e FP |
| TRA (taxa de redução de alertas) | **reportável com ressalva** | 805 / 808 | dominada por VN, mas o termo FN vem da classe positiva |
| Precisão | **a omitir** | VP + FP, com VP = 1 fortuito | o único VP é um acerto acidental (seção 6.3) |
| Recall | **a omitir** | 13, sendo 1 válido | ver seção 5 |
| F1 | **a omitir** | idem | é média harmônica de duas métricas a omitir |
| MCC | **a omitir** | idem | usa as quatro células, mas o produto `VP·VN` é governado por VP = 1 |
| TFN | **a omitir** | 13, sendo 1 válido | é 1 − Recall |

**A leitura equivocada a antecipar** é: *"F1 de 0,016 no baseline e 0,080 no
especialista — a pipeline não funciona."* Ela não se sustenta porque F1 é
calculado sobre uma classe positiva de 13 amostras cujo emparelhamento entre
alerta e gabarito falhou em 12 (seção 6). O que a rodada de fato mede — supressão
de ruído sobre 792 negativos — não aparece em nenhuma dessas três métricas.

**Ressalva pronta para transposição ao `.tex`** (métrica classificada como
reportável com ressalva):

> A taxa de redução de alertas reportada é calculada sobre uma população em que
> 98 % dos alertas têm gabarito seguro. Ela mede o volume de ruído retirado da
> fila de triagem, e não deve ser lida como evidência de que o filtro preserva
> os verdadeiros positivos: o custo dos descartes incorretos é medido sobre uma
> classe positiva de apenas 13 amostras avaliadas, insuficiente para sustentar
> essa segunda afirmação.

**Ressalva pronta para as métricas omitidas**, caso os autores decidam reportá-las
por completude:

> Precisão, Recall, F1, MCC e taxa de falsos negativos dependem das células VP e
> FN da matriz de confusão, alimentadas nesta execução por 13 amostras de
> gabarito vulnerável. A inspeção caso a caso dessas 13 mostrou que em 12 delas o
> alerta submetido ao modelo pertencia a uma fraqueza distinta da rotulada,
> restando uma única amostra com emparelhamento válido. Os valores são
> reportados para completude e não sustentam inferência sobre a capacidade de
> detecção da abordagem.

### 4.6 Conclusão sobre a tese

A tese em avaliação é: *a rodada mede supressão de ruído e não mede capacidade de
detecção.*

**Evidência a favor:** a classe negativa tem 792 amostras e produz um resultado
estatisticamente inequívoco (p < 0,0001, dominância estrita); a classe positiva
tem 13 amostras, das quais 12 têm emparelhamento inválido e a 13ª é um acerto
fortuito sobre um alerta que é ele próprio ruído (seção 6.3).

**Evidência contra, que precisa ser dita:** (i) um recall de 0,0769 medido sobre
13 casos ainda é uma medição, e não uma ausência de medição — ela é apenas
imprecisa, com intervalo largo; (ii) a especificidade de 0,9862 do especialista é
alta o suficiente para levantar a suspeita oposta, de que o filtro esteja
liberando quase tudo como seguro, e a seção 4.4 mostra que esta rodada não
consegue afastar essa hipótese.

**Conclusão declarada:** a tese se sustenta para a primeira metade e precisa ser
qualificada na segunda. A rodada mede supressão de ruído com validade, e o
resultado é robusto. Ela **não** mede capacidade de detecção — mas também não
demonstra que a abordagem preserva verdadeiros positivos, e é essa segunda
afirmação, não a primeira, que a monografia precisa evitar fazer. Responder à
pergunta central do TCC ("um LLM consegue triar alertas do Semgrep reduzindo
falsos positivos **sem descartar verdadeiros positivos**?") exige a classe
positiva discutida na seção 8.

---

## 5. O que a rodada não mede: o funil de recall

### 5.1 O funil

Comando **B**.

```
  107  amostras com Gabarito = vulneravel                        100,0 %
   |
   |   -94  o Semgrep não pareou nenhum alerta                    -87,9 %
   |        causa: não-detecção do motor simbólico
   v
   13  alertas pareados, submetidos ao LLM                         12,1 %
   |
   |    -0  falha de esteira (API_ERROR)                            0,0 %
   v
   13  avaliadas pelo LLM, nos dois braços                         12,1 %
   |
   |   -12  o alerta pareado é de outra fraqueza                   -11,2 %
   |        causa: emparelhamento incorreto entre alerta e gabarito
   v
    1  amostras com emparelhamento válido                           0,9 %
   |
   |    -1  o modelo julgou "falso positivo"                        -0,9 %
   |        causa: julgamento do modelo
   v
    0  detecções válidas de ponta a ponta                           0,0 %
```

Os dois primeiros degraus e o quarto saem do comando **B**; o terceiro sai da
análise caso a caso da seção 6, que é julgamento humano e não contagem
automática.

**Recall de ponta a ponta** (comando **B**): 1 / 107 = **0,0093** contando o
único VP, ou **0,0000** descontando que esse VP é fortuito. O recall medido pela
matriz de acerto, 0,0769, tem como denominador as 13 que chegaram ao LLM — a
distância entre 0,0769 e 0,0093 é exatamente o que a matriz de acerto não
enxerga.

### 5.2 Atribuição do degrau de 94: não-detecção do motor simbólico

Comando **C**. Os 94 casos, por trilha de origem:

| trilha | n | % |
|---|---|---|
| TP_dataset | 48 | 51,1 % |
| TP_prata | 31 | 33,0 % |
| TP_ouro | 15 | 16,0 % |

E por CWE — **34 CWEs distintas para 94 casos**, com a maior concentrando 10,6 %:

| CWE | n | | CWE | n |
|---|---|---|---|---|
| CWE-284 (controle de acesso impróprio) | 10 | | CWE-22 | 3 |
| CWE-77 (injeção de comando) | 10 | | CWE-345 | 3 |
| CWE-290 (bypass de autenticação por spoofing) | 7 | | CWE-401 | 3 |
| CWE-400 (consumo descontrolado de recurso) | 7 | | CWE-405 | 3 |
| CWE-200 (exposição de informação) | 6 | | CWE-532 | 3 |
| CWE-248 | 4 | | *(mais 22 CWEs com 1–2 casos cada)* | |
| CWE-79 | 4 | | | |
| CWE-862 (autorização ausente) | 4 | | | |

Contra as 15 CWEs que têm ficha própria no catálogo de triagem do projeto:
**6 casos em 2 CWEs** (CWE-352 e CWE-79) estão cobertos; **88 casos em 32 CWEs**
não estão.

### 5.3 A não-detecção não é lacuna de configuração

A afirmação exige evidência, e há quatro linhas dela.

**Primeira — 69 % das perdas são sobre fraquezas que o ruleset não promete
alcançar.** Comando **C**. O `p/default` tem 84 regras de linguagem `go`, todas
com CWE declarada, cobrindo 34 CWEs distintas. Cruzando com os 94 não detectados:

| situação | CWEs | casos | % |
|---|---|---|---|
| o ruleset tem regra para a CWE do gabarito | 9 | 29 | 30,9 % |
| o ruleset **não tem** regra para a CWE do gabarito | 25 | **65** | **69,1 %** |

As 9 com regra: CWE-22, CWE-78, CWE-79, CWE-89, CWE-200, CWE-345, CWE-352,
CWE-400, CWE-918 — injeção, travessia de caminho, XSS, SSRF: fraquezas de
*forma*. As 25 sem regra incluem CWE-77, CWE-119, CWE-125, CWE-190, CWE-269,
CWE-284, CWE-285, CWE-290, CWE-401, CWE-459, CWE-755, CWE-770, CWE-862,
CWE-863 — controle de acesso, autorização, autenticação, gestão de recurso,
memória: fraquezas de *intenção*.

A separação importa porque desfaz uma leitura preguiçosa em cada direção. Não é
verdade que "o Semgrep simplesmente falhou" — em 69 % dos casos ele nunca
prometeu olhar. E não é verdade que "basta trocar o ruleset" — o que falta são
regras para fraquezas que não têm forma sintática estável, e a segunda linha da
tabela é exatamente a lista dessas fraquezas.

Os 29 casos da primeira linha são falhas dentro do escopo declarado: aí existe
regra para a CWE e ela não disparou naquele arquivo. É o único subconjunto sobre
o qual "ajustar o ruleset" seria uma resposta pertinente.

**Segunda — a distribuição de CWEs.** A cauda é dominada por fraquezas de
*intenção*: controle de acesso (CWE-284, 10), autorização ausente (CWE-862, 4),
bypass de autenticação (CWE-290, 7), exaustão de recurso (CWE-400, 7), exposição
de informação (CWE-200, 6). Decidir se um `if` de permissão está faltando exige
saber qual é a política de acesso do sistema — informação que não está no
arquivo. Não existe padrão sintático que reconheça "esta verificação de
autorização deveria estar aqui". Isto é limite da **classe de ferramenta**
(casamento de padrões sintáticos sobre um arquivo isolado), não escolha de
ruleset: trocar `p/default` por qualquer outro conjunto de regras sintáticas não
alcança fraqueza definida por política.

**Terceira — o ruleset dispara, e dispara bastante.** Comando **G**: **39 regras
distintas** do `p/default` produziram **808 alertas pareados** sobre os 948
casos. O motor não está mudo sobre este corpus; ele fala sobre outras coisas.

**Quarta — a constatação lógica.** Sob a regra de pareamento vigente nesta
rodada (`src/fase1_semgrep.py:100-111` no commit `14d6af8`), um arquivo com
**exatamente um alerta** era sempre pareado, qualquer que fosse a CWE. Logo todo
caso `NAO_DETECTADO` desta rodada tem **zero alertas** ou **dois ou mais alertas,
nenhum casando com a CWE do gabarito**. Não há caso `NAO_DETECTADO` em que o
Semgrep tenha produzido um único alerta.

**Diagnóstico amostral.** Uma medição exploratória re-varreu 22 dos 94 casos: 18
não produziram alerta algum e 4 produziram alerta de outra CWE. A proporção
amostral de "zero alertas" é 18 / 22 = 0,8182, com **intervalo de Wilson 95 % de
[0,6148; 0,9269]** (comando **H**). Esta amostra não foi preservada como
artefato versionado — é por isso que ela é reportada como amostra com intervalo,
e não como proporção da população. O censo dos 94 está na seção 9 como próximo
passo, com custo medido. **Este documento nunca converte essa proporção amostral
em percentual da população dos 94.**

### 5.4 A classe positiva não é composta de amostras independentes

Comando **F**, com a leitura caso a caso da seção 6. Os 13 casos vêm de **10
commits distintos**:

- os casos 1 e 6 (`portainer:CWE-200:…:vuln` e `TPD:731afbee:CWE-200:true_positive`)
  são o **mesmo arquivo**, a **mesma CWE-200** e a **mesma função no gabarito**
  (`newSingleHostReverseProxyWithHostHeader` em
  `api/http/proxy/factory/reverse_proxy.go`), em commits diferentes do mesmo
  projeto — chegaram por trilhas diferentes (TP_ouro e TP_dataset);
- os casos 9 a 12 são **um único commit de correção** (`d137a063`, incus,
  CWE-770) expandido em quatro arquivos.

Corrigindo pela dependência, as 13 amostras representam cerca de **9
vulnerabilidades distintas**. O poder efetivo da classe positiva é ainda menor
que os 13 sugerem.

---

## 6. Análise qualitativa dos 13 casos da classe positiva

Extração pelo comando **F**. Os vereditos e justificativas citados estão em
`results/20260730T180648Z-14d6af8/ollama-qwen2.5-coder-7b__baseline.csv` e
`…__especialista.csv`, localizáveis pelo `ID_Caso`. A regra do Semgrep e a linha
do alerta vêm do payload do cache simbólico, cujo caminho o comando **F** imprime
por caso.

### 6.1 Critério de atribuição de causa

A regra de pareamento da rodada tinha duas etapas
(`src/fase1_semgrep.py:100-111` em `14d6af8`):

1. aceitar o alerta cuja regra mencione a CWE do gabarito como **substring** de
   alguma tag; se nenhum,
2. **fallback**: se o arquivo tem exatamente um alerta, aceitá-lo, seja qual for
   a CWE.

Um caso pareado pelo passo 2 carrega zero evidência de que o alerta seja sobre a
fraqueza rotulada — ele só é o único alerta daquele arquivo. É este o critério de
"erro de emparelhamento" usado abaixo: **a regra que disparou declara uma CWE
diferente da do gabarito**, o que implica que o pareamento veio do fallback.

O critério é conservador em uma direção e generoso em outra. Ele não prova que a
fraqueza rotulada esteja ausente do arquivo; prova que o LLM foi consultado sobre
outra coisa. E é a consulta ao LLM que a matriz de acerto está medindo.

### 6.2 Os 12 falsos negativos

| # | `ID_Caso` | CWE gab. | trilha | regra que disparou | CWE da regra | linha | intervalo do gabarito | causa |
|---|---|---|---|---|---|---|---|---|
| 1 | `portainer:CWE-200:newSingleHostReverseProxyWithHostHeader:vuln` | CWE-200 | TP_ouro | `reverseproxy-director` | CWE-115 | 30 | 13–31 | emparelhamento |
| 2 | `minio:CWE-269:verifyBinary:vuln` | CWE-269 | TP_prata | `missing-ssl-minversion` | CWE-327 | 410 | 521–573 | emparelhamento |
| 3 | `olivetin:CWE-284:Sanitize:vuln` | CWE-284 | TP_prata | `import-text-template` | CWE-79 | 5 | 14–27 | emparelhamento |
| 4 | `webtransport-go:CWE-401:Dial:vuln` | CWE-401 | TP_prata | `missing-ssl-minversion` | CWE-327 | 68 | 56–127 | emparelhamento |
| 5 | `TPD:1f40a88b:CWE-79:true_positive` | CWE-79 | TP_dataset | `unsafe-template-type` | **CWE-79** | 194 | 316–354 | **julgamento** |
| 6 | `TPD:731afbee:CWE-200:true_positive` | CWE-200 | TP_dataset | `reverseproxy-director` | CWE-115 | 14 | 13–31 | emparelhamento |
| 7 | `TPD:b311a5c9:CWE-862:true_positive` | CWE-862 | TP_dataset | `use-of-md5` | CWE-328 | 762 | 259–363 | emparelhamento |
| 8 | `TPD:c2b310d3:CWE-863:true_positive` | CWE-863 | TP_dataset | `import-text-template` | CWE-79 | 4 | 1–381 (arquivo) | emparelhamento |
| 9 | `TPD:d137a063:CWE-770:true_positive` | CWE-770 | TP_dataset | `import-text-template` | CWE-79 | 13 | 404–489 | emparelhamento |
| 10 | `TPD:d137a063:CWE-770:true_positive#1` | CWE-770 | TP_dataset | `dangerous-exec-command` | CWE-94 | 100 | 814–851 | emparelhamento |
| 11 | `TPD:d137a063:CWE-770:true_positive#2` | CWE-770 | TP_dataset | `math-random-used` | CWE-338 | 12 | 1101–1215 | emparelhamento |
| 12 | `TPD:d137a063:CWE-770:true_positive#3` | CWE-770 | TP_dataset | `import-text-template` | CWE-79 | 4 | 1–384 (arquivo) | emparelhamento |

**Apuração: 11 dos 12 falsos negativos são erro de emparelhamento.** O
levantamento preliminar estimava 8; a apuração caso a caso corrigiu para 11 entre
os FN, ou **12 dos 13** contando o verdadeiro positivo da seção 6.3.

Descontando os dois casos cujo gabarito é o arquivo inteiro (`FILE_SCOPE`, casos
8 e 12, em que a comparação de linha é vácua), a linha do alerta cai **fora** do
intervalo de linhas do gabarito em 8 dos 11 restantes — os casos 1, 4 e 6 são os
únicos em que o alerta ao menos incide sobre a região certa do arquivo, ainda que
sobre outra fraqueza.

**Resumo das justificativas.** Nos 12 casos o padrão é o mesmo nos dois braços: o
modelo lê o alerta que recebeu, argumenta corretamente que aquele alerta é ruído,
e é penalizado por isso. Exemplos textuais (comando **F**):

- caso 3, especialista: *"A entrada 'cfg' não é controlada pelo usuário externo.
  Ela é uma estrutura de configuração interna do aplicativo… o código não está
  renderizando…"* — sobre um alerta de XSS num arquivo cujo rótulo é controle de
  acesso.
- caso 11, baseline: *"O alerta é um FALSO POSITIVO porque o código em questão
  não está utilizando a biblioteca `math/rand` diretamente… o pacote
  `crypto/rand` é importado e usado…"* — sobre um alerta de PRNG fraco num
  arquivo cujo rótulo é exaustão de recurso.
- caso 10, especialista: *"A entrada 'iptablesCmd' é uma constante definida
  dentro da função, não sendo controlada por um agente externo."* — sobre um
  alerta de injeção de comando num arquivo cujo rótulo é CWE-770.

Em nenhum dos 12 o modelo teve a chance de errar sobre a vulnerabilidade
rotulada, porque ela não lhe foi mostrada.

**O caso 5 é diferente e é o único falso negativo legítimo.** A regra
`unsafe-template-type` declara exatamente CWE-79, igual ao gabarito. O alerta, na
linha 194 de `server/web/templatefunc.go` (beego), é sobre a função `Str2html`,
que converte uma string em `template.HTML` — desativando o escape. O modelo
respondeu FP nos dois braços, argumentando (baseline) *"não há evidências de que
esta string seja controlada…"* e (especialista) *"essa conversão ocorre dentro de
outra função que deve ser responsável por garantir a segurança"*. O segundo
argumento é a falácia de assumir que a validação existe em outro lugar. **Causa:
erro de julgamento do modelo.**

Ressalva sobre o caso 5: o gabarito da trilha TP_dataset é atribuído por
**arquivo**, não por linha — o rótulo afirma que o commit corrigiu uma CVE, não
que cada linha do arquivo seja a vulnerabilidade (limitação já declarada em
`run_pipeline.construir_casos_tp_dataset`). O intervalo do gabarito é
`renderFormField` 316–354, e o alerta está na linha 194. Ainda assim a CWE bate e
a fraqueza apontada é real, então a atribuição a julgamento se sustenta.

### 6.3 Dissecação do único verdadeiro positivo

**`TPD:f4b33b64:CWE-290:true_positive`** — oauth2-proxy, `oauthproxy.go` no
commit `f4b33b64bd66`.

| | |
|---|---|
| gabarito | CWE-290 (Authentication Bypass by Spoofing), função `isAllowedPath`, linhas 582–590 |
| regra que disparou | `go.lang.security.injection.open-redirect.open-redirect` |
| CWE declarada pela regra | CWE-601 (URL Redirection to Untrusted Site) |
| linha do alerta | 942, dentro de `OAuthCallback` (857–947) |
| veredito | VP nos dois braços |

**Primeiro problema: o alerta não é a vulnerabilidade rotulada.** Está 350 linhas
depois da função do gabarito e é sobre outra fraqueza — CWE-601, não CWE-290.
Emparelhamento pelo fallback de alerta único.

**Segundo problema: o alerta é ele próprio um falso positivo.** O contexto
hidratado gravado no cache e enviado ao modelo contém, antes do `http.Redirect`:

```go
if !p.redirectValidator.IsValidRedirect(appRedirect) {
    appRedirect = "/"
}
```

O redirecionamento **é** validado contra allowlist. O alerta é ruído.

**Terceiro problema: os dois braços erraram.** O baseline respondeu com uma
condicional que não afirma nada — *"Se essa entrada não for corretamente
validada, pode levar a uma vulnerabilidade de redirecionamento aberto"*. O
especialista foi mais longe e errou o fato: *"Embora o código verifique se
`appRedirect` está em uma lista permitida (`p.redirectValidator.IsValidRedirect(appRedirect)`),
a validação ocorre **após** um redirecionamento"* — não ocorre; a validação
precede o `http.Redirect` no trecho que o próprio prompt entregou.

**Veredito sobre o acerto: fortuito, e agravado.** Não é apenas que o acerto tenha
vindo por acaso; ele veio de uma resposta **errada** a um alerta que era ruído,
creditada como Verdadeiro Positivo porque o gabarito rotula o arquivo inteiro por
conta de outra fraqueza. Recall, F1, MCC e Precisão da rodada inteira repousam
sobre esta única célula.

### 6.4 Balanço da atribuição de causa

| causa | casos | quais |
|---|---|---|
| erro de emparelhamento | **12** | 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13 |
| erro de julgamento do modelo | **1** | 5 |
| erro de gabarito | 0 (como causa primária) | — |

Nenhum caso foi atribuído a erro de gabarito como causa primária, mas dois
padrões de gabarito agravam os números e estão registrados: a atribuição por
arquivo na trilha TP_dataset (seção 6.2, ressalva do caso 5) e a expansão de um
commit em quatro amostras (seção 5.4).

---

## 7. Defeito corrigível contra limite estrutural

### 7.1 Defeito corrigível: o fallback de alerta único

**Onde:** `src/fase1_semgrep.py:107-110` no commit `14d6af8`:

```python
# Fallback: se só há um alerta no arquivo, assume que é o mesmo
# (regra sem tag de CWE explícita)
if len(results) == 1:
    return _normalizar(results[0])
```

E, imediatamente acima, o casamento de CWE por **substring**, que faz `CWE-77`
casar com uma regra tagueada `CWE-770`.

**Dano quantificado.** Comando **G**: dos 808 alertas pareados, **792 (98,0 %)
têm a regra declarando a mesma CWE do gabarito** e 16 não têm. A distribuição
desses 16 é o ponto (tabela "separada por classe de gabarito" do mesmo comando):

| classe | alertas | pareamento exato | pareamento por fallback | % por fallback |
|---|---|---|---|---|
| negativa (gabarito seguro) | 795 | 791 | 4 | 0,5 % |
| positiva (gabarito vulnerável) | 13 | 1 | **12** | **92,3 %** |

O defeito é praticamente inofensivo na classe negativa (0,5 %) e **catastrófico
na classe positiva (92,3 %)**. A assimetria tem causa clara e não é coincidência:
a trilha FP foi construída **a partir de achados do Semgrep**, então a CWE do
gabarito é a CWE da regra por construção; as trilhas TP foram construídas a
partir de CVEs, e a CWE do aviso de segurança raramente coincide com a CWE de
alguma regra que dispare naquele arquivo.

**O que precisa ser reexecutado após a correção.** A Fase 1 inteira, sobre os 948
casos: mudar a regra de pareamento muda quais alertas são aceitos, portanto quais
casos viram `DETECTADO`, portanto quais chamadas de LLM acontecem. Ficam
obsoletos:

- `results/20260730T180648Z-14d6af8/*.csv` — os dois braços, integralmente;
- as entradas de `cache_simbolico/` gravadas sob a regra antiga (por isso o eixo
  `versao_pareamento` foi introduzido no cache e por isso a cópia
  `cache_simbolico_pre_estrito/` existe);
- toda tabela da monografia derivada desses CSVs.

Não fica obsoleto `cache/` (o cache de arquivos-fonte, imutável por construção),
nem `tp_pairs.json` / `tp_pairs_osv.json`.

**Efeito esperado da correção:** a classe positiva cai de 13 para ~1 caso
avaliado. A correção **não melhora** o recall — ela remove uma medição falsa e
deixa o problema visível, que é o resultado correto. É por isso que a correção
precisa vir acompanhada da construção da classe positiva (seção 8), não sozinha.

### 7.2 Defeito corrigível: `Status_Semgrep` mistura duas etapas

Os três casos de `API_ERROR` da seção 3.2 aparecem na coluna `Status_Semgrep`,
que também carrega `DETECTADO` e `NAO_DETECTADO`. O Semgrep detectou os três — o
que falhou foi a leitura da resposta do LLM. A consequência é que a matriz de
cobertura simbólica de `src/metricas.py` sai calculada sobre 945 casos e
subconta `DETECTADO` em 3. É defeito pequeno e de correção barata (uma coluna
separada de status de esteira), mas está aqui porque contamina a matriz que mede
o motor simbólico com uma falha do braço neural.

### 7.3 Limite estrutural: casamento sintático não alcança intenção

Argumentado na seção 5.3 a partir da distribuição de CWEs: 34 CWEs distintas
entre os 94 não detectados, dominadas por controle de acesso (CWE-284),
autorização (CWE-862, CWE-863), bypass de autenticação (CWE-290), exaustão de
recurso (CWE-400) e exposição de informação (CWE-200).

Este limite **não é corrigível por configuração**. Ele é da classe de ferramenta:
um motor que casa padrões sintáticos sobre um arquivo isolado não tem como
representar "esta verificação de autorização deveria existir aqui", porque a
proposição depende da política de acesso do sistema, que não está no arquivo.
Trocar `p/default` por outro ruleset sintático não altera o resultado; trocar o
motor por um de análise interprocedural com especificação de política é outro
trabalho.

**Consequência para o desenho do experimento:** enquanto o LLM for filtro puro do
Semgrep — e ele é, por decisão de projeto —, a pipeline **não pode** detectar o
que o Semgrep não alcança. Medir recall de ponta a ponta sobre um conjunto de
CVEs mede o recall do Semgrep, não o do LLM.

### 7.4 O que deu certo

Registrado aqui para que o capítulo de limitações não apague os resultados.

| resultado | número | comando |
|---|---|---|
| Redução de ruído entre os braços | 111 → 11 FP; especificidade 0,8598 → 0,9862 | **A**, **D** |
| Dominância estrita do especialista | 0 casos em que o baseline acerta e o especialista erra, contra 100 no sentido inverso; p < 0,0001 | **A**, **D** |
| Calibragem de `num_ctx` | **zero** prompts acima de 8192 tokens; máximo observado 7.389 (especialista) e 6.880 (baseline); mediana 1.107 e 590 | **E** |
| Taxa de erro do modelo local | 3 de 948 no baseline (0,3 %), **0 de 948** no especialista | **E** |
| Custo e cota | US$ 0,00, sem limite de requisições, 1.616 chamadas em 2 h 50 | manifesto |
| Determinismo da esteira | semente 42 fixada, contexto byte-a-byte idêntico entre os braços via cache simbólico | manifesto, `src/cache_simbolico.py` |

O ponto sobre `num_ctx` merece nota: a mediana de prompt é de 590 tokens no
baseline e 1.107 no especialista, contra uma janela de 8.192. **Contexto não é
gargalo desta pipeline** — o prompt mais longo da rodada usou 90 % da janela, e
nenhum a estourou. Qualquer esforço de "reduzir contexto" resolveria um problema
que não existe.

Um contraponto honesto ao tempo: a mediana por chamada foi de 5,11 s (baseline) e
4,75 s (especialista), mas o máximo do especialista foi de **1.108 s** — uma
chamada isolada, provavelmente o carregamento dos pesos na primeira invocação
(comando **E**).

---

## 8. Viabilidade de um conjunto de verdadeiros positivos detectáveis

### 8.1 A hipótese: inverter o funil

O funil atual parte de CVEs e torce para que o Semgrep dispare. A taxa de
sucesso dessa aposta está medida: **107 amostras vulneráveis derivadas de CVEs
produziram 1 emparelhamento válido — 0,9 %** (seções 5.1 e 6.4).

A inversão proposta parte das regras que o motor **de fato possui** e busca casos
em que um achado daquela regra corresponde a uma vulnerabilidade real. O
conjunto passa a ser rule-aligned por construção, e a taxa de emparelhamento
válido vira 100 % por definição.

### 8.2 O espaço de regras disponível

Comando **G**, primeiras duas linhas da saída:

| grandeza | valor | base |
|---|---|---|
| regras no `p/default` | 1.074 | medido |
| regras de linguagem `go` | 84 | medido |
| regras Go com CWE declarada | 84 (100 %) | medido |
| CWEs distintas cobertas por regras Go | 34 | medido |
| regras que dispararam neste corpus | 39 | medido |
| alertas pareados que produziram | 808 | medido |

O espaço a partir do qual minerar são as **84 regras Go**, não as 39 que
dispararam neste corpus — as outras 45 simplesmente não encontraram alvo neste
conjunto de repositórios.

### 8.3 Fontes candidatas

| fonte | o que oferece | custo de extração | viável aqui? |
|---|---|---|---|
| **(A)** Fixtures de teste do repositório `semgrep-rules` | Cada regra do registry acompanha um arquivo `.go` de teste com linhas anotadas `// ruleid: <id>` (positivo) e `// ok: <id>` (negativo). Alinhamento regra↔rótulo por construção, e rótulo negativo de brinde. | Um clone raso do repositório (~1 download, sem API, sem cota) e um parser de anotações. **Premissa:** 84 regras Go × 2–5 positivos anotados ⇒ 170–420 amostras. | **Sim.** É a única fonte que atinge n de três dígitos sem custo de rede recorrente. Validade externa baixa: são trechos mínimos sintéticos, não código de produção. |
| **(B)** Mineração de commits de fix guiada por regra | Para cada uma das 84 regras, achar commits Go em que um achado daquela regra desaparece entre pai e fix. Código real, alinhamento por construção. | Clonagem rasa por repositório candidato + varredura do par pai/fix. Fase 1+2 custa **≈6 s por caso** (medido, ver 8.4). O gargalo é a razão candidatos-varridos por caso-aproveitado, que é **premissa não medida**. | **Sim, com escopo reduzido.** Vale como complemento de validade externa a (A), não como fonte principal — a incerteza de rendimento é grande e o custo é dominado por clonagem. |
| **(C)** `tp_pairs_osv.json` (34 pares) e `tp_pairs.json` (16 pares), já coletados | Código real, CVE real, já em disco e já reconstruídos. | Zero: estão versionados. | **Não como fonte de positivos detectáveis.** Rendimento medido: os 50 pares dão 50 amostras vulneráveis (manifesto: TP_ouro 32 e TP_prata 68 casos, metade de cada trilha); o comando **C** mostra 15 + 31 = 46 não detectadas, logo **4 chegaram ao LLM, e 0 com emparelhamento válido** (casos 1–4 da seção 6.2). São CVE-driven, exatamente o funil que se quer inverter. Continuam úteis como classe de comparação e como evidência do próprio argumento. |
| **(D)** Casos sintéticos escritos à mão a partir dos padrões das regras | Controle total sobre a fraqueza e sobre a dificuldade. | Horas de trabalho humano por caso, com revisão. **Premissa:** 15–30 min por caso escrito e revisado ⇒ 40 amostras custam 10–20 h. | **Sim, em volume pequeno.** O projeto já faz isso para os exemplos few-shot por CWE do prompt especialista. Usar as mesmas amostras para avaliar seria contaminação treino/teste — casos novos e disjuntos dos few-shot. |

**Restrições respeitadas.** Nenhuma das fontes acima depende de regenerar
`tp_pairs.json` ou `tp_pairs_osv.json`: com `repos/` apagado, regenerá-los exige
refazer o fetch raso de ~70 repositórios (≈ 1 h, conforme registrado em
`.gitignore`) e `scripts/tp_reconstruct.py` exige histórico git que não está mais
em disco. As duas são lidas como estão. Nenhuma das fontes propõe trocar o
ruleset ou o engine — trocá-los invalidaria o gabarito de falsos positivos
herdado do SastBench, que é a única parte da rodada com validade hoje.

### 8.4 Custo em unidades verificáveis

| item | estimativa | base |
|---|---|---|
| Fase 1 + Fase 2 por caso (Semgrep + hidratação + resolução do arquivo) | **≈ 6 s** (medianas de 5,85 s e 5,93 s em duas medições) | **taxa medida** — comando **I**; ver a ressalva na seção 1 |
| Chamada de LLM por caso por braço (modelo local) | **4,75–5,11 s** (mediana) | **taxa medida** — comando **E** |
| Rodar uma classe positiva de n=100 nos dois braços | 100 × 6 s + 200 × 5 s ≈ **27 min** | derivado das duas taxas medidas |
| Custo monetário e de cota | **US$ 0,00**, sem limite de requisições | medido — braço local, manifesto |
| Censo do Semgrep sobre os 94 não detectados | 94 × 6 s ≈ **9 min** | derivado de taxa medida |
| Fonte (A): clone + parser de anotações | ~1 h de implementação + 1 download | **premissa** |
| Fonte (A): volume resultante | 170–420 amostras positivas | **premissa** (84 regras × 2–5 anotações) |
| Fonte (B): rendimento candidatos→casos | não estimado | **premissa não medida** — declarada como incerteza, não convertida em número |
| Fonte (D): 40 amostras escritas à mão | 10–20 h | **premissa** (15–30 min/caso) |

O achado que reordena as prioridades: **executar a pipeline é barato** (27 min
para n=100, custo zero). Todo o custo do problema está em *obter e rotular* os
casos, não em processá-los. Isto derruba a suposição de que o censo dos 94 seria
caro em tempo de máquina — são 9 minutos.

### 8.5 Declaração de viés

Um conjunto construído a partir das regras do detector **favorece o detector**,
e isso não é um detalhe a ser mencionado em nota de rodapé.

Por que é aceitável para medir **triagem**: a pergunta de pesquisa é se um LLM
consegue triar alertas do Semgrep reduzindo falsos positivos sem descartar
verdadeiros positivos. A população sobre a qual essa pergunta faz sentido é
exatamente *a dos alertas que o Semgrep emite* — nenhum alerta que o Semgrep não
emite chega ao LLM, por decisão de projeto (o LLM é filtro puro). Amostrar dessa
população não é enviesar a medida; é medir sobre a população correta. O que muda
é apenas que a amostra passa a cobrir a classe positiva dessa população, que hoje
está praticamente vazia.

Por que **não** é aceitável para medir **detecção**: um conjunto assim não diz
nada sobre quantas vulnerabilidades existem no mundo que o Semgrep não vê. O
recall medido sobre ele é o recall do LLM *condicionado* a o Semgrep ter
alertado, e não pode ser lido como recall da abordagem. Os 94 casos da seção 5
são a evidência de que a diferença entre os dois é enorme.

**Redação proposta para a monografia** (transponível ao `.tex` sem reescrita):

> O conjunto de verdadeiros positivos utilizado nesta avaliação foi construído a
> partir das regras que o motor simbólico efetivamente possui, e não a partir de
> um catálogo independente de vulnerabilidades. A escolha é deliberada e enviesa
> o conjunto em favor do detector: por construção, todo caso positivo é um caso
> que o Semgrep alerta. Esse viés é adequado ao objeto desta pesquisa, que é a
> triagem de alertas — a população de interesse é a dos alertas emitidos, pois
> nenhum outro caso chega ao modelo de linguagem. Ele é, em contrapartida,
> inadequado para qualquer afirmação sobre capacidade de detecção: as métricas
> de recall aqui reportadas são condicionais à emissão do alerta pelo motor
> simbólico e não estimam a fração de vulnerabilidades reais que a abordagem
> encontraria em um repositório arbitrário. A magnitude dessa distinção está
> quantificada no funil de recall apresentado na Seção X.

### 8.6 n necessário contra n alcançável

**Premissa de tamanho de efeito, declarada:** o objetivo é estimar a taxa de
falsos negativos do filtro com precisão suficiente para distinguir "o filtro
preserva a maioria dos verdadeiros positivos" de "o filtro descarta a maioria" —
isto é, separar recall ≈ 0,3 de recall ≈ 0,7. Uma meia-largura de intervalo de
confiança de 95 % de ±0,15 basta. Esta é uma escolha dos autores, não uma
constante: qualquer alvo de precisão mais fino multiplica o n.

Fórmula: `n = z² · 0,25 / E²`, com `z = 1,959964` (comando **J**).

| meia-largura do IC 95 % (pior caso, p = 0,5) | n de positivos válidos (arredondado para cima) |
|---|---|
| ±0,20 | 25 |
| **±0,15** | **43** |
| ±0,10 | 97 |
| ±0,05 | 385 |

Referência interna: `src/metricas.py:33` já declara 30 amostras vulneráveis como
o piso abaixo do qual o próprio código emite aviso de poder estatístico limitado.
O alvo de 43 é coerente com esse piso e o supera.

| via | n alcançável | base |
|---|---|---|
| hoje, com o funil CVE-driven | **1** | medido |
| fonte (C) inteira, esgotada | ~1 | medido (0,9 % de rendimento) |
| fonte (D), 20 h de trabalho | ~40 | premissa |
| fonte (B), escopo reduzido | dezenas | premissa não medida |
| **fonte (A)** | **170–420** | premissa (84 regras × 2–5 anotações) |

**Recomendação: seguir.** Construir a classe positiva a partir das fixtures de
teste do `semgrep-rules` (fonte A) como base principal, complementada por um
lote pequeno da fonte (B) para validade externa, e declarar o viés com a redação
de 8.5. O alvo de 43 positivos válidos é atingível com folga por (A) sozinha, e
o custo de execução da pipeline sobre eles é de dezenas de minutos a custo zero.

A recomendação **não** é seguir por (B) ou (C) como fonte principal: (C) está
medida em 0,9 % de rendimento e (B) tem rendimento não medido com custo dominado
por clonagem. E **não** é abandonar a pergunta de detecção: ela permanece sem
resposta, e a seção 8.5 diz explicitamente que o conjunto proposto não a
responde.

---

## 9. Próximos passos, por retorno sobre esforço

Ordenados por ganho dividido por custo. Cada item traz o ganho esperado, o custo
estimado, a dependência que o bloqueia e o artefato ou comando por onde começar.

**1. Censo do Semgrep sobre os 94 não detectados.**
- *Ganho:* troca a amostra de 22 com IC de [0,61; 0,93] por um censo exato, e
  separa `SEM_ALERTA` de `ALERTA_OUTRA_CWE` nos 94. Fecha a seção 5.3 com número
  em vez de intervalo.
- *Custo:* **≈ 9 min** de máquina (94 × ≈6 s medidos), zero custo monetário.
- *Dependência:* a Fase 1 com `Motivo_Nao_Deteccao` — já implementada na mudança
  `pareamento-cwe-estrito`, ainda não integrada.
- *Começar por:* `python run_pipeline.py --tp-only --sem-llm --sem-cache-simbolico`,
  depois `python -m src.metricas <nova rodada>` no bloco "NAO_DETECTADO por motivo".

**2. Correção do emparelhamento (mudança `pareamento-cwe-estrito`).**
- *Ganho:* elimina a contaminação de 12 dos 13 positivos. Não melhora nenhuma
  métrica — torna honestas as que existem.
- *Custo:* a mudança já está escrita; falta reexecutar a rodada inteira. 948
  casos × ≈6 s + 1.616 chamadas × ~5 s ≈ **2 h 50** (a duração medida desta
  rodada), custo zero.
- *Dependência:* nenhuma técnica. Depende da decisão de que a rodada atual pode
  ser descartada — o que esta análise recomenda.
- *Começar por:* `src/fase1_semgrep.py:100-111` e
  `scripts/medir_pareamento.py`, que já mede o efeito da mudança sobre o cache
  antigo sem reexecutar o Semgrep.

**3. Construção da classe positiva pela fonte (A), fixtures do `semgrep-rules`.**
- *Ganho:* leva a classe positiva de 1 para as centenas. É o único item da lista
  que torna Recall, F1 e MCC reportáveis, e o único que permite responder à
  segunda metade da pergunta de pesquisa.
- *Custo:* ~1 h de implementação (clone + parser de anotações) + ~27 min de
  execução para n = 100 nos dois braços. Premissa de implementação; execução
  medida.
- *Dependência:* item 2 — construir a classe positiva antes de corrigir o
  emparelhamento produziria a mesma contaminação em escala maior.
- *Começar por:* o repositório `semgrep-rules`, diretório `go/`, arquivos de
  teste com anotações `// ruleid:` e `// ok:`; e a seção 8.5 para a declaração de
  viés, que precisa entrar na monografia junto com os números.

**4. Separar `Status_Semgrep` de status de esteira.**
- *Ganho:* a matriz de cobertura simbólica deixa de subcontar `DETECTADO` em 3 e
  de ser calculada sobre 945 em vez de 948.
- *Custo:* uma coluna no CSV e o ajuste correspondente em `src/metricas.py`;
  minutos de implementação, mais uma reexecução que o item 2 já paga.
- *Dependência:* nenhuma; é barato o bastante para entrar junto do item 2.
- *Começar por:* `src/fase5_auditoria.py`, definição de `CABECALHO`.

**5. Experimento que separa discriminação de deslocamento de limiar.**
- *Ganho:* decide qual das duas leituras da seção 4.4 é a correta. Sem ele, a
  monografia não pode afirmar que o prompt especialista "aprendeu a reconhecer
  falso positivo" — só que ele reduz alertas.
- *Custo:* nenhuma implementação nova; é a leitura da taxa de veredito
  "vulnerável" por classe sobre a rodada do item 3.
- *Dependência:* item 3. Não é executável antes.
- *Começar por:* `python scripts/analise_rodada.py <rodada> --secao conjuntos`
  sobre a nova rodada, comparando as linhas VP e FN entre os braços.

**6. Ampliação da fonte (B), mineração guiada por regra.**
- *Ganho:* validade externa — casos de código de produção, não fixtures.
  Complementa o item 3; não o substitui.
- *Custo:* não estimável com base medida hoje; o rendimento
  candidatos→aproveitados é premissa não medida.
- *Dependência:* item 3 concluído, para que o esforço seja incremental e não
  esteja no caminho crítico.
- *Começar por:* medir o rendimento num piloto de 5 regras antes de comprometer
  esforço — `scripts/osv_harvest_go.py` e `scripts/tp_reconstruct.py --sast` já
  têm a mecânica de par vulnerável/corrigido com varredura do Semgrep.
