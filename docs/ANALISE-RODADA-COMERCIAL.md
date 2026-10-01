# Rodada comercial — `gpt-6-luna` contra os modelos locais

> **O que esta rodada testa.** Se o que foi medido com modelos locais de 7 a 9 B
> (`qwen2.5-coder:7b`, `gemma2:9b`) vale para um modelo comercial sobre a mesma
> população, nas mesmas condições. Muda só o modelo: mesma população (2.328
> casos), mesmo cache simbólico, mesmo catálogo por CWE (`e5db7d400842…`),
> mesmos *templates* (hashes travados em teste). Change `rodada-comercial`.
>
> **Conclusão.** O Luna não é "melhor" nem "pior" em bloco: ele tem **outro
> viés de resposta**. Diz "vulnerável" com muito mais frequência que os locais.
>
> - **No braço de filtro** (o sistema implantável, Q1–Q3), isso o torna um
>   **filtro pior**: remove 66–70 % dos alertas, contra 85–98 % do qwen, e o
>   MCC fica abaixo do qwen nos dois *prompts*. O recall maior (9–12 de 19,
>   contra 3–8) não compensa sobre uma pilha 97,7 % segura. O especialista
>   **não melhora** o Luna no filtro — o mesmo que se viu no gemma.
> - **No braço de triagem**, com o enquadramento direto, o Luna é o **melhor dos
>   três**, e com folga: na pilha de alertas acerta 15 de 21 vulneráveis com MCC
>   de +0,30 (qwen +0,07, gemma +0,12), e entre os injetados recupera ~17 %
>   (qwen 4 %, gemma 6,5 %) — sem o deslocamento de viés que explica o recall do
>   gemma. Mesmo assim, ~83 % do que o Semgrep perde continua perdido: a
>   conclusão central do capítulo — o componente neural não recupera os pontos
>   cegos do simbólico — **se mantém** com um modelo comercial.
> - **O Luna não exibe a supressão excessiva** dos modelos locais; erra para o
>   lado do alarme. A leitura de que a supressão é "propriedade da tarefa e do
>   enquadramento" precisa ser ressalvada.
> - **O ganho do especialista não se reproduz no filtro** (p = 0,032 na
>   execução 1, 0,227 na 2), mas se reproduz na triagem, nos dois enquadramentos.

## 1. Identificação

| campo | valor |
|---|---|
| modelo | `gpt-6-luna` (OpenAI), `reasoning_effort: "none"`, temperatura 0, API de lote (50 % de desconto) |
| população | `--tudo`: 2.328 casos; 833 com alerta (filtro), 1.597 candidatos (triagem) |
| catálogo | por CWE, `data/catalogo_cwe.json`, `e5db7d400842…` (o das Rodadas 1–6 e 7b) |
| execuções | cada braço **duas vezes** (o Luna não é determinístico com temperatura 0 — design D5) |
| data | 2026-09-30 |
| commits | `cf9dd32` (filtro 1, código de lote ainda não commitado, idêntico ao de `13a0e1d`), `13a0e1d` (filtro 2, triagem 1–2), `d891a3b` (triagem direta 1–2) |
| fila | `OPENAI_LOTE_TOKENS_ENFILEIRADOS=2000000` nas triagens (teto real da conta; design D6) |
| CSVs | `resultados_parte2/rodada-comercial-luna-{filtro,triagem,triagem-direto}{,-2}/` |
| custo | **US$ 1,1505** no total (teto autorizado US$ 2) — `tasks.md` 2.2 |

| run id | modo | prompts | custo |
|---|---|---|---:|
| `rodada-comercial-luna-filtro` / `-2` | filtro | baseline, especialista | US$ 0,1199 / 0,1201 |
| `rodada-comercial-luna-triagem` / `-2` | triagem | baseline, especialista | US$ 0,2333 / 0,2333 |
| `rodada-comercial-luna-triagem-direto` / `-2` | triagem | baseline_direto, especialista_direto | US$ 0,2219 / 0,2220 |

**Referências locais** (mesmo modo e mesmo enquadramento — a Rodada 5 mostrou
que o enquadramento sozinho muda o resultado):

| bloco | qwen2.5-coder:7b | gemma2:9b |
|---|---|---|
| filtro | Rodada 3 (`20260908T094808Z-9a00cb2`) | Rodada 7 (`baseline`) e 7b (`especialista`, por CWE) |
| triagem, enquadramento de alerta | Rodada 4 (reexecução) | — (não existe) |
| triagem, enquadramento direto | Rodada 5 (reexecução) | Rodada 6 (reexecução) |

As Rodadas 4–6 em disco são as **reexecuções** (os CSVs originais se perderam).
A comparação caso a caso só é possível contra elas; a `tab:modelos` do capítulo
cita as execuções originais, cujos números diferem em poucos casos.

## 2. Variação entre execuções do próprio Luna

Fonte: `scripts/concordancia_execucoes.py`.

| bloco | prompt | pareados | acordo | κ | trocas em vulneráveis |
|---|---|---:|---:|---:|---:|
| filtro | baseline | 833 | 98,3 % | 0,960 | 0/22 |
| filtro | especialista | 833 | 97,4 % | 0,941 | 3/22 |
| triagem (alerta) | baseline | 1.597 | 99,1 % | 0,969 | 6/786 |
| triagem (alerta) | especialista | 1.597 | 99,1 % | 0,958 | 8/786 |
| triagem (direto) | baseline_direto | 1.597 | 97,9 % | 0,935 | 9/786 |
| triagem (direto) | especialista_direto | 1.597 | 98,8 % | 0,950 | 10/786 |

Nenhum McNemar entre as duas execuções de um mesmo braço é significativo
(menor p = 0,053, filtro/especialista, 6 × 16).

**McNemar entre os prompts, por execução:**

| bloco | execução 1 | execução 2 | reproduz? |
|---|---|---|---|
| filtro: baseline × especialista | 93 × 65, p = 0,032 (baseline) | 85 × 69, p = 0,227 | **não** |
| triagem (alerta) | 78 × 204, p < 0,0001 (especialista) | 78 × 202, p < 0,0001 | sim |
| triagem (direto) | 110 × 189, p < 0,0001 (especialista) | 105 × 187, p < 0,0001 | sim |

O caso do filtro é o que o D5 previa: com 22 vulneráveis no LLM, a variação do
próprio modelo basta para mudar a significância. **O p = 0,032 não deve ser
citado como resultado.**

## 3. Braço de filtro — Luna × qwen × gemma

Fonte: `scripts/comparar_comercial_locais.py`. Casos com veredito válido em
**todos** os braços do bloco (820 no baseline, 822 no especialista; 19
vulneráveis). TRA = fração dos alertas descartada.

| prompt | braço | VP | FP | FN | VN | Recall | Precisão | MCC | TRA |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | Luna 1 | 9 | 240 | 10 | 561 | 47,37 % | 3,61 % | +0,057 | 69,63 % |
| baseline | Luna 2 | 9 | 242 | 10 | 559 | 47,37 % | 3,59 % | +0,056 | 69,39 % |
| baseline | qwen (R3) | 8 | 115 | 11 | 686 | 42,11 % | 6,50 % | **+0,117** | 85,00 % |
| baseline | gemma (R7) | 5 | 127 | 14 | 674 | 26,32 % | 3,79 % | +0,043 | 83,90 % |
| especialista | Luna 1 | 10 | 269 | 9 | 534 | 52,63 % | 3,58 % | +0,061 | 66,06 % |
| especialista | Luna 2 | 12 | 262 | 7 | 541 | 63,16 % | 4,38 % | +0,097 | 66,67 % |
| especialista | qwen (R3) | 3 | 12 | 16 | 791 | 15,79 % | 20,00 % | **+0,160** | 98,18 % |
| especialista | gemma (7b) | 4 | 173 | 15 | 630 | 21,05 % | 2,26 % | −0,002 | 78,47 % |

McNemar (acerto), Luna × local — o local acerta mais em todos:

| prompt | Luna × qwen | Luna × gemma |
|---|---|---|
| baseline | 94 × 218 / 93 × 219, p < 10⁻¹¹ | 73 × 182 / 71 × 182, p < 10⁻¹⁰ |
| especialista | 14 × 264 / 16 × 257, p < 10⁻⁴⁷ | 77 × 167 / 82 × 163, p < 10⁻⁶ |

(primeiro número: casos em que só o Luna acerta; segundo: só o local; execução
1 / execução 2.)

No capítulo, os MCC do qwen e do gemma neste braço são citados com os valores
que o texto já usava (+0,116 / +0,161 e +0,043 / −0,002, base pareada qwen ×
gemma de 822 casos); na base pareada com o Luna, acima, o qwen fica em +0,117 /
+0,160 — a diferença é de um a dois casos e não muda nenhuma leitura.

**Leitura.** O acerto aqui é dominado pelos 800 alertas seguros, e o Luna mantém
o dobro (contra o qwen/baseline) a vinte vezes (contra o qwen/especialista) mais
falsos alarmes. No MCC, que pondera as duas classes, o qwen é melhor nos dois
*prompts*; o Luna fica acima do gemma no especialista e empata no baseline. O
recall do Luna é o mais alto do bloco, mas sobre 19 casos: 9–12 acertos contra
3–8.

**O especialista não ajuda o Luna no filtro.** Ele acrescenta ~25 falsos
alarmes e 1–3 acertos (MCC +0,057 → +0,061/+0,097), sem significância
reproduzida (§2). Os falsos alarmes acrescentados se concentram na CWE-327
: 19 / 20 no baseline, **57 / 54** no especialista (execução 1 / 2) — o mesmo número e, pelo perfil, o mesmo
mecanismo do gemma na Rodada 7 (ficha por CWE fala de *hash* fraco, os 93
alertas são de TLS sem versão mínima). Onde o Luna mais alarma, nos dois
*prompts*: CWE-319 (57/61 de 86 alertas seguros), CWE-665 (43/35 de 75), CWE-94
(33/15 de 93).

## 4. Braço de triagem — enquadramento de alerta (Luna × Rodada 4)

Casos com veredito válido nos três braços (1.589 no baseline, 1.583 no
especialista), separados por procedência.

| prompt | procedência | braço | VP | FP | FN | Recall | Precisão | MCC |
|---|---|---|---:|---:|---:|---:|---:|---:|
| baseline | pilha | Luna 1 / 2 | 13 / 14 | 178 / 177 | 9 / 8 | 59,1 / 63,6 % | 6,8 / 7,3 % | +0,142 / +0,159 |
| baseline | pilha | qwen (R4) | 0 | 2 | 22 | 0,0 % | 0,0 % | −0,008 |
| baseline | injetados | Luna 1 / 2 | 105 / 102 | — | 653 / 656 | 13,9 / 13,5 % | — | — |
| baseline | injetados | qwen (R4) | 3 | — | 755 | 0,4 % | — | — |
| especialista | pilha | Luna 1 / 2 | 8 / 9 | 65 / 66 | 14 / 13 | 36,4 / 40,9 % | 11,0 / 12,0 % | +0,161 / +0,183 |
| especialista | pilha | qwen (R4) | 3 | 11 | 19 | 13,6 % | 21,4 % | +0,153 |
| especialista | injetados | Luna 1 / 2 | 125 / 122 | — | 629 / 632 | 16,6 / 16,2 % | — | — |
| especialista | injetados | qwen (R4) | 8 | — | 746 | 1,1 % | — | — |

McNemar (acerto): baseline — qwen acerta mais (117 × 178 / 115 × 177,
p < 0,001), por dizer "seguro" para quase tudo numa pilha quase toda segura;
especialista — Luna acerta mais (135 × 67 / 134 × 69, p < 10⁻⁵).

**Leitura.** O artefato da Rodada 4 — pedir para validar um alerta que não
existe, nos injetados — afeta o Luna muito menos que o qwen: ele recupera 14–17
% dos injetados mesmo com a pergunta mal posta, contra 0,4–1,1 %.

## 5. Braço de triagem — enquadramento direto (Luna × Rodadas 5 e 6)

É a comparação da `tab:modelos`. Casos com veredito válido nos quatro braços
(1.589 no baseline direto, 1.563 no especialista direto).

| prompt | procedência | braço | VP | FP | FN | Recall | Precisão | MCC |
|---|---|---|---:|---:|---:|---:|---:|---:|
| baseline_direto | pilha | Luna 1 / 2 | 14 / 13 | 164 / 166 | 8 / 9 | 63,6 / 59,1 % | 7,9 / 7,3 % | +0,170 / +0,151 |
| baseline_direto | pilha | qwen (R5) | 2 | 30 | 20 | 9,1 % | 6,3 % | +0,045 |
| baseline_direto | pilha | gemma (R6) | 9 | 337 | 13 | 40,9 % | 2,6 % | −0,002 |
| baseline_direto | injetados | Luna 1 / 2 | 136 / 133 | — | 621 / 624 | 18,0 / 17,6 % | — | — |
| baseline_direto | injetados | qwen (R5) | 9 | — | 748 | 1,2 % | — | — |
| baseline_direto | injetados | gemma (R6) | 179 | — | 578 | 23,6 % | — | — |
| especialista_direto | pilha | Luna 1 / 2 | 15 / 15 | 82 / 85 | 6 / 6 | 71,4 / 71,4 % | 15,5 / 15,0 % | **+0,299 / +0,294** |
| especialista_direto | pilha | qwen (R5) | 3 | 39 | 18 | 14,3 % | 7,1 % | +0,068 |
| especialista_direto | pilha | gemma (R6) | 8 | 105 | 13 | 38,1 % | 7,1 % | +0,115 |
| especialista_direto | injetados | Luna 1 / 2 | 126 / 127 | — | 610 / 609 | 17,1 / 17,3 % | — | — |
| especialista_direto | injetados | qwen (R5) | 30 | — | 706 | 4,1 % | — | — |
| especialista_direto | injetados | gemma (R6) | 48 | — | 688 | 6,5 % | — | — |

McNemar (acerto), Luna × local:

| prompt | Luna × qwen | Luna × gemma |
|---|---|---|
| baseline_direto | 153 × 148 / 147 × 148, p ≥ 0,82 (empate) | 335 × 200 / 330 × 201, p < 10⁻⁷ (Luna) |
| especialista_direto | 146 × 81 / 147 × 84, p < 10⁻⁴ (Luna) | 188 × 80 / 188 × 82, p < 10⁻⁹ (Luna) |

**Leitura.** Com o especialista direto, o Luna é o melhor dos três nas duas
procedências e nas duas execuções: na pilha, quase dobra o recall do gemma
(71 % contra 38 %) com o dobro da precisão; nos injetados, recupera 3 a 4 vezes mais que os locais.
O recall de 23,6 % do gemma/baseline_direto nos injetados é maior, mas vem de
marcar como vulnerável 44 % de uma pilha 97,8 % segura (337 falsos alarmes) — é
deslocamento de viés, não discriminação; o Luna/baseline_direto mantém metade
dos falsos alarmes (164–166) e tem MCC de +0,15–0,17 contra −0,002.

**Sem pareamento** (todos os casos do Luna; usado na `fig:recall-comparado`):
especialista_direto — pilha 16/22 (72,73 %), precisão 16,2 / 15,8 %, MCC +0,310
/ +0,306; injetados 133/764 (**17,41 %** nas duas execuções). baseline_direto —
injetados 138/764 (18,06 %) e 136/764 (17,80 %).

**O que não muda.** Mesmo o melhor braço deixa de fora ~83 % dos casos que o
Semgrep não detectou. A conclusão de `subsec:consequencias` — o componente
neural não recupera os pontos cegos do simbólico — se mantém com um modelo
comercial; o que muda é a magnitude (de 4–7 % para ~17 %).

## 6. Supressão excessiva

O padrão de `subsec:supressao` — modelo que descarta quase tudo, perto do
classificador degenerado — **não aparece no Luna**. No filtro, sua TRA é 66–70 %
(qwen/especialista: 98 %), e a TFN 0,37–0,53 (qwen/especialista: 0,84). O
deslocamento que a ficha por CWE produz é na direção do alarme (CWE-327), como
no gemma, e não do ceticismo, como no qwen. A convergência com o
`gemini-2.5-pro` do ZeroFalse, que o capítulo usa para sugerir que a supressão
é "propriedade da tarefa e do enquadramento", não se estende ao Luna: o que é
comum aos modelos é o **deslocamento** do limiar pela orientação do *prompt*, e
não a sua direção.

## 7. Ressalvas

- **Um modelo comercial, sem raciocínio.** `gpt-6-luna` com `reasoning_effort:
  "none"` — o modelo econômico da linha. Nada aqui descreve modelos de topo nem
  o mesmo modelo com raciocínio (design D4).
- **Locais quantizados em 4 bits; Luna não.** Muda o modelo inteiro: família,
  tamanho, quantização e acesso. O resultado não isola nenhum desses fatores.
- **Reexecuções como referência.** A comparação caso a caso usa as reexecuções
  das Rodadas 4–6; os números originais da `tab:modelos` diferem em poucos
  casos (o especialista direto do qwen: 27,78 % de recall na pilha no original,
  14,29 % na reexecução pareada aqui — a R5 é justamente a que não reproduz a
  significância).
- **Classe positiva do filtro: 19 casos.** Vale para o Luna o mesmo limite de
  `sec:limitacoesresultados`.
- **Contaminação.** O Luna pode ter visto, no treino, os repositórios ou os
  *commits* de correção. Os locais também; não há como medir.

## 8. Reprodução

```bash
# execuções (lote; uma de cada vez; ~4–20 min cada)
python run_pipeline.py --tudo --modo-montagem filtro  --modelo gpt-6-luna \
  --prompt baseline --prompt especialista --modo-envio lote --run-id rodada-comercial-luna-filtro
OPENAI_LOTE_TOKENS_ENFILEIRADOS=2000000 python run_pipeline.py --tudo --modo-montagem triagem \
  --modelo gpt-6-luna --prompt baseline --prompt especialista --modo-envio lote \
  --run-id rodada-comercial-luna-triagem
OPENAI_LOTE_TOKENS_ENFILEIRADOS=2000000 python run_pipeline.py --tudo --modo-montagem triagem \
  --modelo gpt-6-luna --prompt baseline_direto --prompt especialista_direto --modo-envio lote \
  --run-id rodada-comercial-luna-triagem-direto
# (e o mesmo com o sufixo -2)

# números deste documento
python scripts/concordancia_execucoes.py resultados_parte2/rodada-comercial-luna-filtro \
  resultados_parte2/rodada-comercial-luna-filtro-2 --modelo gpt-6-luna \
  --prompt baseline --prompt especialista
python scripts/comparar_comercial_locais.py
python src/metricas.py resultados_parte2/rodada-comercial-luna-filtro --mcnemar
```
