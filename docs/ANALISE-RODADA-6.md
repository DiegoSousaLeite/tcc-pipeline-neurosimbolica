# Rodada 6 — o modelo maior não levanta o teto, e a métrica agregada engana

> **O que esta rodada testa.** Mesmo enquadramento da Rodada 5 (templates
> `*_direto`), mesma população, mesmo cache simbólico, **semente 42 e temperatura
> 0**. A única variável é o **modelo**: `qwen2.5-coder:7b` → `gemma2:9b`.
> Qualquer diferença aqui é atribuível a ele.

## 1. Identificação

| campo | valor |
|---|---|
| `run_id` | `rodada-6-gemma` |
| modelo | `gemma2:9b`, digest `ff02c3702f32`, **Q4_0**, 9,2 B, 100 % GPU, 5,99 GB de VRAM |
| enquadramento | `baseline_direto` / `especialista_direto` (idênticos aos da Rodada 5) |
| execução | 12:43 → 20:31, 3.210 chamadas, 8,8 s/chamada |
| comparação | `rodada-5-direto` (`qwen2.5-coder:7b`, mesmo enquadramento) |

## 2. O resultado agregado

| braço | n | VP | VN | FP | FN | Precisão | Recall | F1 | **MCC** | TFN |
|---|---|---|---|---|---|---|---|---|---|---|
| R5 `baseline_direto` (qwen) | 1588 | 10 | 776 | 32 | 770 | 0,238 | 0,0128 | 0,0243 | −0,0834 | 0,9872 |
| **R6 `baseline_direto` (gemma)** | 1583 | 192 | 465 | 340 | 586 | 0,361 | **0,2468** | 0,2931 | **−0,1858** | 0,7532 |
| R5 `especialista_direto` (qwen) | 1587 | 40 | 773 | 35 | 739 | **0,533** | 0,0513 | 0,0937 | **+0,0189** | 0,9487 |
| **R6 `especialista_direto` (gemma)** | 1563 | 62 | 696 | 107 | 698 | 0,367 | 0,0816 | 0,1335 | **−0,0832** | 0,9184 |

O recall do baseline salta de 1,3 % para 24,7 % — **19×**. E o MCC piora nos dois
braços.

## 3. Por que o recall maior não é melhora

A taxa-base de vulneráveis nesta população é **~49 %**. O critério que importa é
se a precisão fica acima ou abaixo dela:

| braço | precisão | taxa-base | veredito |
|---|---|---|---|
| R5 `especialista_direto` (qwen) | **51,4 %** | 48,6 % | **acima** — informativo |
| R6 `especialista_direto` (gemma) | 36,7 % | 48,6 % | abaixo — anti-informativo |
| R5 `baseline_direto` (qwen) | 23,8 % | 49,1 % | abaixo |
| R6 `baseline_direto` (gemma) | 36,1 % | 49,1 % | abaixo |

O gemma **deslocou o viés de resposta**, não a capacidade: passou a afirmar
"vulnerável" muito mais (340 falsos positivos no baseline contra 32 do qwen), e o
recall subiu por consequência aritmética disso. A troca é pior que sorteio, e é
por isso que o MCC afunda em vez de subir.

**`qwen2.5-coder:7b` + `especialista_direto` continua sendo a única das quatro
configurações com MCC positivo no conjunto agregado.**

### A ressalva que impede o exagero

`gemma2:9b` **não é "o qwen maior"**. É outra família, **generalista** em vez de
especializada em código, e em **Q4_0** em vez de Q4_K_M. O que esta rodada
demonstra é *"este modelo maior não ajudou, e ajudou menos que um menor
especializado em código"* — **não** *"modelo maior não ajuda"*. Escrever a
segunda frase seria generalizar além do medido.

## 4. O erro de leitura que esta rodada expôs

> **Isto revisa como os MCC das Rodadas 4 e 5 devem ser lidos.** O número
> agregado do braço de triagem descreve uma população que **não pode existir**.

O braço de triagem mistura dois conjuntos de naturezas opostas:

| conjunto | n | vulneráveis | o que é |
|---|---|---|---|
| procedência `alerta` | ~823 | 18 (**2,2 %**) | a pilha de alertas real — a tarefa de **filtro** |
| procedência `gabarito` | ~760 | 760 (**100 %**) | os injetados — **não tem negativo nenhum** |

Somados, produzem uma taxa-base artificial de ~49 % que não corresponde a
cenário algum: em produção os injetados não existem. **O MCC agregado é, em boa
parte, um artefato de composição** — a mesma família de erro que já tinha sido
pega na TRA (§6 da Rodada 4).

Separando por procedência, na comparação pareada por `ID_Caso`:

### 4.1 Sobre a pilha de alertas (a tarefa real, taxa-base 2,2 %)

| braço | recall | precisão | **MCC** |
|---|---|---|---|
| R5 `especialista_direto` (qwen) | 27,78 % | 12,50 % | **+0,1593** |
| R6 `especialista_direto` (gemma) | 38,89 % | 6,14 % | +0,1083 |
| R5 `baseline_direto` (qwen) | 11,11 % | 5,88 % | +0,0524 |
| R6 `baseline_direto` (gemma) | 44,44 % | 2,30 % | +0,0065 |

**Na tarefa de filtro os quatro braços são positivamente informativos**, e o
melhor deles — qwen + especialista — tem MCC **+0,1593**. Não é forte, mas não é
zero, e é **estável**: a Rodada 3, no braço de filtro com os mesmos casos e o
mesmo modelo, deu MCC +0,1606. Dois caminhos independentes chegando ao mesmo
número.

### 4.2 Sobre os injetados (100 % vulneráveis)

| braço | recall |
|---|---|
| R5 `especialista_direto` (qwen) | 4,31 % |
| R6 `especialista_direto` (gemma) | 7,41 % |
| R5 `baseline_direto` (qwen) | 1,05 % |
| R6 `baseline_direto` (gemma) | 24,21 % |

**O MCC aqui é indefinido, e isso não é falha de cálculo:** o conjunto não tem um
único negativo, então as células VN e FP são estruturalmente vazias e o
denominador do MCC é zero. Sobre os injetados só existe recall — qualquer outra
métrica seria inventada.

E é aqui que o viés de resposta do gemma aparece sem disfarce: 24,21 % de recall
no baseline, contra 44,44 % de "vulnerável" gritado sobre a pilha de alertas, que
é 97,8 % código seguro.

### 4.3 O que o texto precisa passar a dizer

1. **O MCC agregado do braço de triagem não deve ser reportado como se
   descrevesse desempenho.** Ele mede uma mistura artificial. Reportar por
   procedência.
2. **Na tarefa de filtro, o componente neural É informativo** — MCC ~+0,16 com o
   especialista, replicado em duas rodadas independentes. Isso é mais favorável à
   arquitetura do que as Rodadas 4 e 5 sugeriam.
3. **Sobre o que o SAST perde, ele não é** — 4 a 7 % de recall com o especialista,
   e o único jeito de subir isso foi deslocar o viés de resposta, ao custo de
   inundar a pilha de falsos positivos.

O achado central das Rodadas 4 e 5 — **os pontos cegos são majoritariamente
compartilhados** — sobrevive intacto. O que muda é que a frase "o LLM não
discrimina nada" era forte demais: ele discrimina na tarefa para a qual foi
desenhado, e não discrimina na que o braço de triagem inventou para testá-lo.

## 5. McNemar entre os prompts, dentro do gemma

| | discordâncias | teste | p |
|---|---|---|---|
| R4 (qwen, enquadramento alerta) | 14 × 12 | Yates | 0,8445 |
| R5 (qwen, enquadramento direto) | 36 × 63 | Yates | 0,0090 |
| **R6 (gemma, enquadramento direto)** | **174 × 284** | Yates | **< 0,0001** |

O eixo do prompt é detectável nos dois modelos sob o enquadramento direto, e a
direção é a mesma: o especialista ganha. No gemma a diferença é enorme (458
discordâncias), o que é coerente com o baseline dele ser o braço mais
descontrolado de todos.

## 6. Ressalvas

### 6.1 Mais vereditos perdidos que no qwen

42 linhas de `API_ERROR` contra 13 do qwen — 3× mais. Mesma causa da Rodada 4:
prompt maior que a janela de 8.192 tokens. A perda continua enviesada por
**tamanho de função**, e no gemma ela é maior, o que reduz um pouco a
comparabilidade entre as duas rodadas nos casos de função longa.

### 6.2 Três variáveis mudam juntas entre R5 e R6

Família (Qwen → Gemma), especialização (código → generalista) e quantização
(Q4_K_M → Q4_0). O desenho isola o **modelo** como bloco, não cada um desses
fatores. Separá-los exigiria rodadas adicionais que não estão planejadas.

### 6.3 O oráculo da CWE continua de pé

Vale tudo o que a §7.2 da Rodada 5 registra: sobre os injetados o modelo recebe
qual fraqueza procurar e em qual função olhar, e em produção não haveria nada
para preencher isso. Os números dos injetados são limite superior generoso.

## 7. Referência rápida

| artefato | onde |
|---|---|
| CSVs da Rodada 6 | `results/rodada-6-gemma/` |
| Rodada 5 (mesmo enquadramento, modelo menor) | `results/rodada-5-direto/` |
| Rodada 4 (mesmo modelo da R5, enquadramento alerta) | `results/rodada-4-triagem/` |
| Fila que executou as duas | `scripts/fila_rodadas.py`, log `results/fila-rodadas.log` |
| O que isso obriga no LaTeX | `docs/MAPA-TCC-O-QUE-REESCREVER.md` §4b |
