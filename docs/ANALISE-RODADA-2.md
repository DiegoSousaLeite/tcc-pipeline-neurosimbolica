# Rodada 2 — efeito do pareamento estrito de CWE

## 1. Identificação da rodada

| campo | valor |
|---|---|
| `run_id` | `20260731T140000Z-af9bc32` |
| commit | `af9bc32` + a mudança `pareamento-cwe-estrito` |
| comando | `run_pipeline.py --tudo --modelo ollama:qwen2.5-coder:7b --prompt baseline --prompt especialista --run-id 20260731T140000Z-af9bc32` |
| modelo | `ollama:qwen2.5-coder:7b`, digest `dae161e27b0e`, Ollama 0.32.5 |
| quantização | `Q4_K_M`, 7,6 B parâmetros, 100 % GPU |
| `num_ctx` / `num_predict` | 8192 / 512 |
| semente | 42 |
| Semgrep | 1.167.0, ruleset `p/default` (ver ressalva em §6.1) |
| catálogo de CWE | sha256 `a81b6f5ca3a4f70c…` — idêntico ao da Rodada 1 |
| versões de prompt | `baseline:597fcfa9`, `especialista:d1145f8b` — idênticas às da Rodada 1 |
| população | 948 casos — FP 791, TP_ouro 32, TP_prata 68, TP_dataset 57 |
| `versao_pareamento` | 2 (identificador completo de CWE, sem fallback) |

Modelo, quantização, semente, prompts, catálogo e população são os mesmos da
Rodada 1. **A única variável alterada é a regra de pareamento da Fase 1** — que é
o que torna as duas rodadas comparáveis.

> **Escopo.** Este documento registra o movimento entre a Rodada 1 e a Rodada 2,
> que é o que a tarefa 7.3 da mudança pede. Ele não reproduz as seções de funil,
> conjuntos e esteira de `ANALISE-RODADA-1.md`: aquelas descrevem o corpus, que
> não mudou.

### Ressalva sobre a duração registrada

O `manifesto.json` marca início 2026-08-03 22:35 e duração de 4.159 s. Isso é a
**última retomada**, não a rodada inteira: a execução foi interrompida e retomada
várias vezes entre 31/jul e 03/ago (queda de energia, suspensão da máquina, um
processo morto por limite de tempo). O checkpoint por tripla
`(ID_Caso, Modelo_LLM, Tipo_Prompt)` é o que torna isso inofensivo — cada retomada
pula o que já estava gravado. Nenhuma medição de tempo de parede desta rodada
deve ser usada como custo de execução.

## 2. Movimento do `Status_Semgrep`

Comparação caso a caso, braço especialista (o único sem `API_ERROR` nas duas
rodadas), sobre os 948 IDs comuns:

| transição | casos | |
|---|---|---|
| `DETECTADO` → `DETECTADO` | 791 | inalterado |
| `NAO_DETECTADO` → `NAO_DETECTADO` | 140 | inalterado |
| `DETECTADO` → `NAO_DETECTADO` | **17** | **mudou** |
| `NAO_DETECTADO` → `DETECTADO` | **0** | — |

A ausência da quarta transição é a verificação de que a mudança faz o que promete
e nada além: endurecer o pareamento só pode **remover** emparelhamentos, nunca
criar. Se algum caso tivesse ganhado detecção, seria sinal de defeito.

### Taxonomia dos 157 não detectados

| origem | motivo | casos |
|---|---|---|
| já era `NAO_DETECTADO` | `SEM_ALERTA` | 118 |
| já era `NAO_DETECTADO` | `ALERTA_OUTRA_CWE` | 22 |
| era `DETECTADO` | `ALERTA_OUTRA_CWE` | 17 |

Os 39 `ALERTA_OUTRA_CWE` não são todos novos. 22 deles já eram não-detecção sob a
regra antiga — arquivos com **dois ou mais** alertas e nenhum casando, que o
fallback nunca alcançou porque ele só se aplicava a arquivo com alerta único. O
que a taxonomia acrescenta nesses 22 é o diagnóstico: "o Semgrep leu o arquivo e
enxergou outra fraqueza" é afirmação diferente de "o Semgrep não viu nada", e
antes as duas caíam no mesmo balde.

## 3. Movimento nas duas classes

### 3.1 Classe positiva (gabarito vulnerável, n = 107 nas duas rodadas)

| | Rodada 1 | Rodada 2 |
|---|---|---|
| Semgrep VP (detectou a CWE rotulada) | 13 | **1** |
| Semgrep FN (ponto cego simbólico) | 94 | **106** |
| amostras vulneráveis que chegaram ao LLM | 13 | **1** |

**Este é o resultado principal da mudança.** Dos 13 casos vulneráveis que o
Semgrep aparentava detectar, **12 eram artefato do fallback**: o motor havia
disparado um alerta sobre outra fraqueza no mesmo arquivo, e o código antigo o
aceitava como sendo o alerta do caso. O LLM recebia esse alerta, respondia
corretamente sobre ele, e a auditoria pontuava a resposta contra um gabarito que
não lhe pertencia.

A Rodada 1 previu este número. `ANALISE-RODADA-1.md` §7.1 mediu 12 dos 13 casos
positivos pareados por fallback (92,3 %) e projetou que "a classe positiva cai de
13 para ~1 caso avaliado". A projeção bateu exata.

Amostras de emparelhamento desfeito, com a regra que disparava no lugar:

| caso | CWE do gabarito | regra que o fallback aceitava | CWE da regra |
|---|---|---|---|
| `TPD:b311a5c9:CWE-862` | 862 (autorização ausente) | `use-of-md5` | 328 |
| `TPD:d137a063:CWE-770#1` | 770 (alocação sem limite) | `dangerous-exec-command` | 94 |
| `TPD:d137a063:CWE-770#2` | 770 | `math-random-used` | 338 |
| `TPD:f4b33b64:CWE-290` | 290 (spoofing de autenticação) | `open-redirect` | 601 |
| `webtransport-go:CWE-401` | 401 (vazamento de memória) | `missing-ssl-minversion` | 327 |

Nenhum desses pares tem relação semântica. O `recall` de 0,1215 da Rodada 1 era,
em 12/13 dos casos, medição de outra coisa.

**A correção não melhora o recall — ela remove uma medição falsa.** O recall real
do Semgrep sobre a CWE rotulada cai de 0,1215 para 0,0093, e a taxa de falsos
negativos sobe de 0,8785 para 0,9907. Esse é o número honesto: o motor simbólico
não alcança a fraqueza rotulada em 99 % dos casos vulneráveis deste corpus.

### 3.2 Classe negativa (gabarito seguro, n = 838 → 839)

| | Rodada 1 | Rodada 2 |
|---|---|---|
| Semgrep FP (ruído sobre código seguro) | 792 | 788 |
| Semgrep VN (silêncio correto) | 46 | 51 |

Cinco casos seguros migraram de FP para VN — o Semgrep deixou de ser creditado
com um alerta que não era sobre a fraqueza em questão. O `n` sobe em 1 porque um
caso que era `API_ERROR` na Rodada 1 produziu veredito válido nesta (§6.2).

O dano do fallback na classe negativa era pequeno, como a Rodada 1 já apontava
(0,5 % contra 92,3 % na positiva), e a razão é estrutural: a trilha FP foi
construída **a partir de achados do Semgrep**, então a CWE do gabarito é a CWE da
regra por construção. As trilhas TP vêm de CVEs, e a CWE do aviso de segurança
raramente coincide com a de alguma regra que dispare naquele arquivo.

## 4. TRA e proporção de FP filtrados

### 4.1 Matriz de cobertura simbólica

| métrica | Rodada 1 | Rodada 2 | variação |
|---|---|---|---|
| TRA (redução de alertas) | 0,1481 | 0,1660 | **+0,0179** |
| Prop. de FP filtrados | 0,0549 | 0,0608 | **+0,0059** |
| MCC | −0,7346 | −0,7916 | −0,0570 |
| Recall | 0,1215 | 0,0093 | −0,1122 |
| TFN | 0,8785 | 0,9907 | +0,1122 |

TRA e proporção de FP filtrados **sobem** porque 5 alertas de ruído deixaram de
ser contabilizados como detecção. O MCC piora porque a célula VP esvaziou. As duas
coisas são o mesmo fato visto de ângulos diferentes, e nenhuma delas é melhora ou
piora do motor: é a mesma realidade, medida sem o artefato.

### 4.2 Matriz de acerto do LLM

| braço | métrica | Rodada 1 | Rodada 2 | variação |
|---|---|---|---|---|
| baseline | n | 805 | 789 | −16 |
| baseline | TRA | 0,8609 | 0,8606 | −0,0003 |
| baseline | MCC | −0,0230 | −0,0143 | +0,0087 |
| baseline | VP / VN / FP / FN | 1 / 681 / 111 / 12 | 0 / 678 / 110 / 1 | |
| especialista | n | 808 | 791 | −17 |
| especialista | TRA | 0,9851 | 0,9874 | **+0,0023** |
| especialista | MCC | 0,0656 | −0,0040 | −0,0696 |
| especialista | VP / VN / FP / FN | 1 / 784 / 11 / 12 | 0 / 780 / 10 / 1 | |

O TRA do LLM praticamente não se move: ele mede filtragem de ruído, e o ruído
está na classe negativa, que a mudança quase não tocou. **É o resultado central do
trabalho e ele sobrevive à correção.**

O MCC do especialista cair de +0,0656 para −0,0040 tem uma causa só: com um único
caso vulnerável na população avaliada, qualquer coeficiente que dependa da classe
positiva perde sentido. Não é degradação do modelo. `Precisao`, `Recall`, `F1` e
`MCC` **não devem ser reportados** para esta rodada — o próprio `metricas.py`
emite o aviso de poder estatístico limitado (1 amostra contra o mínimo sugerido
de 30).

## 5. McNemar — o resultado principal é estável

| | Rodada 1 | Rodada 2 |
|---|---|---|
| n pareado | 805 | 789 |
| ambos acertam | 682 | 678 |
| só baseline acerta | **0** | **0** |
| só especialista acerta | **100** | **100** |
| ambos erram | 23 | 11 |
| χ² (Yates) | 98,01 | 98,01 |
| p-valor | < 0,0001 | < 0,0001 |

A tabela de discordância é **idêntica** nas duas rodadas: 100 casos em que só o
especialista acerta, zero em que só o baseline acerta. A superioridade do prompt
especialista sobre o baseline na filtragem de falsos positivos não depende da
regra de pareamento — é a conclusão mais robusta do experimento, e a correção não
a arranha.

## 6. Ressalvas

### 6.1 O ruleset não é fixado, e o cache não detecta isso

Dos 17 casos que deixaram de emparelhar, **16 caíram por fallback** — exatamente
os 16 que a medição prévia previa. O 17º não:

```
lxc/incus | CWE-338 | cmd/incusd/images.go
  Rodada 1: pareava go.lang.security.audit.crypto.math_random.math-random-used
            (declara CWE-338) -> casamento EXATO, legítimo
  Rodada 2: essa regra não disparou mais; sobrou dangerous-exec-command
            -> ALERTA_OUTRA_CWE
```

Esse caso não caiu pela regra nova. **O conjunto de alertas do Semgrep mudou entre
30/jul e 03/ago.** `p/default` é o nome de uma coleção do registry do Semgrep, não
uma versão fixada: seu conteúdo é atualizado continuamente do lado do servidor.

O eixo `versao_ruleset` do cache simbólico grava a string `"p/default"`, que não
mudou — então a invalidação por ruleset **nunca dispara**, mesmo quando as regras
por trás do nome mudam. Entradas de cache gravadas sob um conjunto de regras podem
ser servidas sob outro sem que nada perceba.

Isto não foi corrigido nesta mudança: fixar o ruleset (por hash do conteúdo ou por
versão explícita) altera uma variável do experimento e exige rodada nova. Fica
registrado como ameaça à reprodutibilidade, e é candidato natural a uma mudança
própria.

### 6.2 Dois casos de falha de esteira

O braço baseline tem 2 casos em `API_ERROR`, ambos do grupo
`be0de1ab:CWE-79` (`harness/harness`, 34 locations):

```
{"verdict": "FP", "reasoning": "O alerta é um FALSO POSITIVO porque o código
não está diretamente escrevendo dados em 'http.ResponseWriter'...
   <e aqui o modelo entra em laço de linhas em branco até estourar num_predict>
```

Não é raciocínio longo demais para 512 tokens: o modelo entra em **laço
degenerativo de espaços em branco** e nunca fecha o JSON. É modo de falha
conhecido de modelo pequeno quantizado, reprodutível nessas entradas.

Três pontos importam:

1. **Não é efeito desta mudança.** Os mesmos dois casos falham na Rodada 1, sob a
   regra antiga. A Rodada 1 tem um terceiro (`c2b310d3:CWE-94:false_positive#4`)
   que nesta produziu veredito válido.
2. **Aumentar `num_predict` não resolveria** — o laço consumiria o novo teto.
3. Como o McNemar é pareado, esses 2 casos saem da comparação nas duas rodadas.
   O `n` pareado (789) já reflete isso.

A detecção melhorou de passagem: na Rodada 1 o erro aparecia como "resposta não é
JSON parseável" (o parser tentava e falhava); nesta, o provedor barra antes, pelo
`done_reason == "length"`. Mesmo evento, diagnóstico mais preciso.

## 7. Como reproduzir

| | comando |
|---|---|
| **A** | `python src/metricas.py results/20260731T140000Z-af9bc32 --mcnemar` |
| **B** | `python src/metricas.py results/20260730T180648Z-14d6af8 --mcnemar` |
| **C** | `python scripts/analise_rodada.py results/20260730T180648Z-14d6af8 --secao regras --cache cache_simbolico_pre_estrito` |

`results/` e `cache_simbolico*/` não são versionados (ver `.gitignore`), então
precisam existir localmente. A cópia `cache_simbolico_pre_estrito/` preserva o
estado do cache sob `versao_pareamento` 1 e é o que permite **C** e a checagem da
§6.1 depois da rodada nova ter sobrescrito `cache_simbolico/`.
