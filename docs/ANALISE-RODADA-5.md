# Rodada 5 — o enquadramento do prompt era mesmo parte do resultado

> **O que esta rodada testa, e só isso.** Mesmo modelo da Rodada 4
> (`qwen2.5-coder:7b`), mesma população, mesmo cache simbólico, **semente 42 e
> temperatura 0**. A única variável é o **enquadramento da pergunta**. Qualquer
> diferença aqui é atribuível a ele, e a nada mais.

## 1. A hipótese que motivou a rodada

A Rodada 4 mediu recall de 1,29 % no braço de triagem e MCC de −0,0033. A leitura
óbvia era "o componente neural não enxerga o que o SAST perde".

Mas havia uma hipótese rival que o grupo de controle **não conseguia detectar**,
porque o problema era uniforme nas duas procedências: os templates perguntavam
*"decida se o ALERTA é verdadeiro positivo ou falso positivo"* — e para os 759
candidatos injetados **não existiu alerta nenhum**. Pedir para validar um alerta
inexistente e receber "falso positivo" é uma resposta coerente com a pergunta
feita, não uma falha de detecção.

Os templates `_direto` trocam a pergunta por *"este código contém a fraqueza
descrita / alguma vulnerabilidade?"*, com a linha explícita `Julgue o código. Não
há alerta de ferramenta a validar.`

**Eles não acrescentam informação.** O `especialista_direto` mantém exatamente as
mesmas três camadas e a mesma CWE do gabarito que o `especialista` já recebia; o
`baseline_direto` continua sem ver CWE alguma, como a condição de controle exige.
Muda a forma da pergunta, não a evidência. São arquivos novos
(`baseline_direto:1ac39caf`, `especialista_direto:f537598a`): os originais não
foram tocados, e há um teste travando os hashes `baseline:597fcfa9` e
`especialista:d1145f8b` que estão nos manifestos das Rodadas 1 a 4.

## 2. A resposta: sim, o enquadramento era parte do resultado

| braço | n | VP | VN | FP | FN | Precisão | Recall | F1 | **MCC** | TFN |
|---|---|---|---|---|---|---|---|---|---|---|
| R4 `baseline` | 1585 | 3 | 803 | 2 | 777 | 0,600 | 0,0038 | 0,0076 | +0,0121 | 0,9962 |
| **R5 `baseline_direto`** | 1588 | 10 | 776 | 32 | 770 | 0,238 | 0,0128 | 0,0243 | **−0,0834** | 0,9872 |
| R4 `especialista` | 1586 | 10 | 797 | 11 | 768 | 0,476 | 0,0129 | 0,0250 | −0,0033 | 0,9871 |
| **R5 `especialista_direto`** | 1587 | **40** | 773 | 35 | 739 | **0,533** | **0,0513** | **0,0937** | **+0,0189** | 0,9487 |

**No especialista, o recall quadruplicou: 1,29 % → 5,13 %.** E não foi trocando
recall por precisão — a precisão **subiu** junto, de 0,476 para 0,533. O modelo
passou a afirmar vulnerabilidade mais vezes *e* a errar menos quando afirma.

## 3. O teste que impede a leitura ingênua

A armadilha óbvia seria o modelo virar carimbo ao contrário, dizendo "vulnerável"
para tudo. O recall subiria e não significaria nada. A rodada correu `--tudo`
justamente para ter os 790 negativos da trilha FP e poder checar isso.

Comparação pareada, caso a caso, dos mesmos `ID_Caso`:

| braço | recorte | n | disse "vulnerável" | viraram sim | viraram não |
|---|---|---|---|---|---|
| `especialista` → `_direto` | todos | 1586 | 21 → **75** | +54 | −0 |
| | injetados | 759 | 7 → 34 | +27 | −0 |
| | com alerta (**régua**) | 827 | 14 → 41 | +27 | −0 |
| | **negativos (seguro)** | 808 | 11 → **35** | **+24** | −0 |
| `baseline` → `_direto` | todos | 1585 | 5 → **42** | +39 | −2 |
| | injetados | 761 | 3 → 8 | +7 | −2 |
| | com alerta (**régua**) | 824 | 2 → 34 | +32 | −0 |
| | **negativos (seguro)** | 805 | 2 → **32** | **+30** | −0 |

Decompondo os 54 vereditos novos do especialista: **+30 VP e +24 FP**. Precisão
dos vereditos novos: **55,6 %**, contra uma taxa-base de 49 % na população. Ou
seja, o ganho é real mas **magro** — os vereditos que apareceram são só
ligeiramente melhores que sorteio.

No baseline a decomposição é o oposto: **+7 VP e +30 FP**, precisão de **19 %**
nos vereditos novos, muito **abaixo** da taxa-base. Daí o MCC ir a **−0,0834**:
pior que chute.

**A leitura:** sem uma CWE-alvo, perguntar "este código contém alguma
vulnerabilidade?" produz ruído. Com a CWE-alvo (que o especialista já recebia),
a pergunta coerente extrai sinal que a pergunta incoerente suprimia.

## 4. A régua de controle funcionou

Os casos **com alerta** existem nas duas rodadas e as duas perguntas são
coerentes para eles — é a régua que separa "efeito geral do enquadramento" de
"penalidade específica da pergunta incoerente".

| especialista, acerto sobre vulneráveis | R4 | R5 | fator |
|---|---|---|---|
| procedência `alerta` (régua) | 15,79 % | 31,58 % | 2,0× |
| procedência `gabarito` (injetados) | 0,92 % | 4,47 % | **4,8×** |

O enquadramento direto ajuda os dois grupos — mas ajuda os **injetados mais que
o dobro** do que ajuda a régua. É a evidência de que a pergunta incoerente
penalizava especificamente os candidatos sem alerta, exatamente como a hipótese
previa.

## 5. O eixo do prompt volta a ser detectável

| McNemar entre os dois prompts | discordâncias | teste | p |
|---|---|---|---|
| Rodada 4 (enquadramento alerta) | 14 × 12 | Yates | **0,8445** |
| **Rodada 5 (enquadramento direto)** | 36 × 63 | Yates | **0,0090** |

Na Rodada 4 concluí que os dois prompts convergiam por degeneração. A Rodada 5
mostra que **o enquadramento incoerente estava mascarando o eixo do prompt**: com
a pergunta certa, a diferença entre baseline e especialista volta a ser
estatisticamente detectável — e agora com sinal claro, porque o especialista
ganha e o baseline piora.

## 6. O que isso muda, e o que NÃO muda

**Muda:**

1. **O número do braço de triagem é 5,13 %, não 1,29 %.** A Rodada 5 é a medição
   justa; a Rodada 4 mede o braço de triagem sob uma pergunta que não se aplica a
   metade dos seus casos.
2. **A decisão 5c.1 ("manter o template") está revogada.** Ela foi tomada com os
   dados da Rodada 4, que não permitiam ver isto. Ver §4b.5b do mapa.
3. **A conclusão da Rodada 4 sobre "os dois prompts são degenerados" era parcial.**
   O baseline é degenerado; o especialista estava sendo suprimido pela pergunta.

**Não muda:**

1. **MCC continua praticamente zero** (+0,0189). Quadruplicar um recall de 1,29 %
   dá 5,13 %, que continua não sendo utilizável. A TFN é de **94,87 %**.
2. **Os pontos cegos continuam majoritariamente compartilhados.** O componente
   neural não recupera o que o SAST perde, nem com a pergunta certa.
3. **A resposta à Q2 continua sendo "sim, introduz falsos negativos em massa"** —
   só que agora com um número defensável, obtido depois de tentar derrubá-lo.

## 7. Ressalvas

### 7.1 Isto vale para um modelo local de 7 B

`qwen2.5-coder:7b`, Q4_K_M, `num_ctx` 8192. A Rodada 6 (`gemma2:9b`, mesmo
enquadramento direto) isola o eixo do modelo e responde se o teto é do modelo ou
da tarefa.

### 7.2 O oráculo da CWE continua de pé, e é maior no braço de triagem

O `especialista` recebe a CWE do gabarito. No braço de **filtro** isso é
realista: quando há alerta, a CWE do gabarito é a que a regra do Semgrep
declarou, e um sistema implantado a teria. No braço de **triagem, nos casos
injetados**, não há alerta nenhum — a CWE vem só da CVE, e em produção não
haveria nada para preencher aquele campo.

Portanto os 5,13 % são um **limite superior generoso**: o modelo é informado de
qual fraqueza procurar e em qual função olhar. Mesmo assim, 5,13 %.

Resta um oráculo fraco também no braço de filtro, que vale declarar: quando
várias regras disparam com CWEs diferentes no mesmo arquivo, o experimento usa o
gabarito para escolher **qual** alerta avaliar; em produção se triaria todos, e a
carga real de FP seria maior que a medida.

### 7.3 O ganho é magro e precisa ser dito como tal

55,6 % de precisão nos vereditos novos contra 49 % de taxa-base. É sinal, não é
ruído — mas é pouco, e nenhuma frase do texto deve sugerir que o enquadramento
"resolveu" o problema. Ele corrigiu uma medição enviesada.

## 8. Referência rápida

| artefato | onde |
|---|---|
| CSVs da Rodada 5 | `results/rodada-5-direto/` |
| Rodada 4 (mesmo modelo, enquadramento alerta) | `results/rodada-4-triagem/` |
| Templates novos | `prompts/baseline_direto.md`, `prompts/especialista_direto.md` |
| Fila que executou | `scripts/fila_rodadas.py`, log em `results/fila-rodadas.log` |
| O que isso obriga no LaTeX | `docs/MAPA-TCC-O-QUE-REESCREVER.md` §4b |
