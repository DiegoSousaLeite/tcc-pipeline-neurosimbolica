## 1. Decisão (bloqueia o resto)

- [x] 1.1 Decidir o modelo e o orçamento (design D4). Verificar: a decisão e o
      valor autorizado estão registrados neste arquivo, com data.
      **2026-09-30:** modelo `gpt-6-luna` (sem raciocínio, temperatura 0);
      teto de **US$ 2**; braço de filtro **duas vezes**; braço de triagem
      **sim, depois do filtro, também duas vezes** (acrescentado no mesmo
      dia). Estimativa do plano: ~US$ 0,70 (design D6).
      Justificativa e delimitação no design D4.
- [x] 1.2 Confirmar billing ativo no fornecedor escolhido (Tier 1 ou acima, no
      Gemini). Verificar: a validação de ~10 casos de `envio-em-lote-comercial`
      (tarefas 5.1–5.3) passou na mesma conta.
      2026-09-30: conta da OpenAI com crédito; validação com o `gpt-6-luna`
      passou (`provedor-lote-openai` 3.1). O Gemini foi descartado.
- [x] 1.3 Rever D2 se a `OPENAI_API_KEY` aparecer. Verificar: o `design.md`
      reflete o escopo que de fato vai rodar. D2 revisto em 2026-09-30.
- [x] 1.4 Se o modelo não for Gemini, abrir change para o provedor (síncrono e
      de lote) antes de seguir. Verificar: a change existe e está vinculada aqui.
      2026-09-30: os autores indicaram o `gpt-6-luna`; o provedor está em
      `provedor-lote-openai` (implementado e validado; arquivada em
      2026-09-30). Fechada com a decisão de modelo em 1.1.

## 2. Execução — braço de filtro primeiro (D1)

- [x] 2.1 Rodar o braço de filtro (`--modo-montagem filtro`, `baseline` e
      `especialista`, `--modo-envio lote`) sobre a população de referência,
      **duas vezes** (D5), com `--run-id rodada-comercial-luna-filtro` e
      `--run-id rodada-comercial-luna-filtro-2`. Verificar: nos dois,
      `manifesto.json` traz `modo.envio = "lote"`, o fornecedor e o `id_lote`
      de cada partição; nenhuma partição fora de `RECUPERADA`; a concordância
      entre as duas execuções está registrada.
      **2026-09-30.** Comando: `run_pipeline.py --tudo --modo-montagem filtro
      --modelo gpt-6-luna --prompt baseline --prompt especialista
      --modo-envio lote --run-id <id>` (2.328 casos, catálogo por CWE
      `e5db7d400842…`, o das Rodadas 1–6).

      | execução | commit | lote (openai) | estado | req. | ERROR/EXPIRADO |
      |---|---|---|---|---:|---:|
      | `rodada-comercial-luna-filtro` | `cf9dd32`¹ | `batch_6abd9636493c8190b9185eade3f93ec6` | `RECUPERADA` / `CONCLUIDO` | 1.666 | 0 / 0 |
      | `rodada-comercial-luna-filtro-2` | `13a0e1d` | `batch_6abd9762a05081909c39c1ee52c71715` | `RECUPERADA` / `CONCLUIDO` | 1.666 | 0 / 0 |

      ¹ O código de lote ainda não estava commitado na execução 1; entrou em
      `13a0e1d` sem alteração antes da execução 2 (o manifesto da 1 aponta
      para o commit anterior).

      **Concordância entre as execuções** (833 alertas pareados por braço,
      vereditos VP/FP):

      | braço | acordo | κ de Cohen | trocas | trocas em vulneráveis | McNemar exec. 1 × 2 (acerto) |
      |---|---:|---:|---:|---:|---|
      | `baseline` | 819/833 = 98,3 % | 0,960 | 14 | 0/22 | 8 × 6, p = 0,79 |
      | `especialista` | 811/833 = 97,4 % | 0,941 | 22 | 3/22 | 6 × 16, p = 0,053 |

      **Consequência para o McNemar `baseline` × `especialista`:** a execução 1
      dá 93 × 65, p = 0,032 (favorece o `baseline`); a execução 2 dá 85 × 69,
      p = 0,227. A significância **não se reproduz** — a variação do próprio
      Luna basta para mudá-la (é o caso que D5 previa). Recall do
      `especialista`: 11/22 na 1, 14/22 na 2. Com 22 vulneráveis no LLM, o
      recall é indicativo (a ferramenta avisa n < 30).
      Cálculo: `scripts/concordancia_execucoes.py results/rodada-comercial-luna-filtro
      results/rodada-comercial-luna-filtro-2 --modelo gpt-6-luna --prompt
      baseline --prompt especialista` (acordo, κ, trocas; McNemar exato
      binomial se b+c < 25, senão χ² com Yates) e `src/metricas.py --mcnemar`
      em cada execução.
- [x] 2.2 Registrar o custo observado ao lado do estimado (~US$ 0,12 por
      execução do filtro e ~US$ 0,23 por execução da triagem, design D6). Verificar: consta deste arquivo, com a
      fonte (`lotes[].custo_estimado_usd` do manifesto), e o total segue abaixo
      do teto de US$ 2.
      **2026-09-30.** Fonte: soma de `lotes[].custo_estimado_usd` de cada
      `manifesto.json` (tokens reais devolvidos pelo fornecedor × preço de lote
      US$ 0,05 / 0,25 por 1 M).

      | execução | estimado (D6) | observado |
      |---|---:|---:|
      | `rodada-comercial-luna-filtro` | ~US$ 0,12 | US$ 0,1199 |
      | `rodada-comercial-luna-filtro-2` | ~US$ 0,12 | US$ 0,1201 |
      | `rodada-comercial-luna-triagem` (1ª tentativa, recusada) | — | US$ 0,0000 |
      | `rodada-comercial-luna-triagem` | ~US$ 0,23 | US$ 0,2333 |
      | `rodada-comercial-luna-triagem-2` | ~US$ 0,23 | US$ 0,2333 |
      | **total** | **~US$ 0,70** | **US$ 0,7066** (35 % do teto de US$ 2) |

      O observado é o custo calculado pela pipeline sobre o uso que o
      fornecedor reportou; a conferência contra a fatura é no painel de uso da
      OpenAI.
- [x] 2.3 Braço de triagem, **duas vezes**, **depois do filtro** (decisão de
      2026-09-30, design D5; estimativa ~US$ 0,23 cada). Verificar: mesma forma
      de 2.1, com `--modo-montagem triagem` e `--run-id
      rodada-comercial-luna-triagem` e `rodada-comercial-luna-triagem-2`; a
      concordância entre as duas execuções está registrada. Uma execução de
      cada vez (design D6: a fila do modelo não comporta duas triagens juntas).
      **2026-09-30.** Comando igual ao de 2.1 com `--modo-montagem triagem`,
      sob `OPENAI_LOTE_TOKENS_ENFILEIRADOS=2000000` (teto real da fila desta
      organização; correção no design D6). Commit `13a0e1d` nas duas.

      **Primeira tentativa recusada.** Sem a variável, a pipeline usou o teto
      de 5 M e montou uma partição única (~3,9 M estimados); o fornecedor a
      recusou na validação (`batch_6abd98efac508190b29bedc5b2cc4c89`,
      `token_limit_exceeded`, limite de 2.000.000), 3.194 `API_ERROR`, custo
      zero. A pasta foi preservada como
      `results/rodada-comercial-luna-triagem.falhou-teto-fila/` (e o log ao
      lado), e a execução refeita do zero com o mesmo `run_id` — reenviar
      dentro dela deixaria as linhas `API_ERROR`, que sobrescrevem o
      `Status_Semgrep`, na frente dos vereditos na leitura de cobertura.

      | execução | lotes (openai), em sequência | estado | req. | ERROR/EXPIRADO |
      |---|---|---|---:|---:|
      | `rodada-comercial-luna-triagem` | `batch_6abd99d4bddc8190916e1807d46ae7b5` (1.687), `batch_6abd9acfe4e881908f94cc8e26558649` (1.314), `batch_6abd9bc86c8481909b102b2f47392103` (193) | todos `RECUPERADA` / `CONCLUIDO` | 3.194 | 0 / 0 |
      | `rodada-comercial-luna-triagem-2` | `batch_6abd9c710e7c8190a21072b29cf14d27` (1.687), `batch_6abd9d6aed148190b2cc81f798cab215` (1.314), `batch_6abd9f1a188881909901c476251147a4` (193) | todos `RECUPERADA` / `CONCLUIDO` | 3.194 | 0 / 0 |

      **Concordância entre as execuções** (1.597 casos pareados por braço, 786
      vulneráveis — alertas e positivos injetados, vereditos VP/FP):

      | braço | acordo | κ de Cohen | trocas | trocas em vulneráveis | McNemar exec. 1 × 2 (acerto) |
      |---|---:|---:|---:|---:|---|
      | `baseline` | 1.582/1.597 = 99,1 % | 0,969 | 15 | 6/786 | 8 × 7, p = 1,0 |
      | `especialista` | 1.582/1.597 = 99,1 % | 0,958 | 15 | 8/786 | 9 × 6, p = 0,61 |

      **McNemar `baseline` × `especialista`: reproduz.** Execução 1: 78 × 204,
      χ² = 55,4, p < 0,0001; execução 2: 78 × 202, χ² = 54,0, p < 0,0001 — o
      `especialista` acerta mais nas duas (precisão 0,667 / 0,660 contra
      0,403 / 0,400; MCC 0,134 / 0,128 contra −0,086 / −0,088).
      Cálculo: `scripts/concordancia_execucoes.py results/rodada-comercial-luna-triagem
      results/rodada-comercial-luna-triagem-2 --modelo gpt-6-luna --prompt
      baseline --prompt especialista` e `src/metricas.py --mcnemar` em cada
      execução. (O pareamento do script usa só o veredito VP/FP, sem filtrar
      por `Status_Semgrep` — os injetados vêm `NAO_DETECTADO`; no filtro o
      resultado de 2.1 não muda.)

## 3. Monografia — `editaveis/resultados.tex`

Sob a regra de `escrita-capitulo-resultados`: nada é commitado sem pedido
explícito dos autores.

- [ ] 3.1 Acrescentar a linha do modelo comercial (`gpt-6-luna` — **não** "de
      fronteira", design D4) na Tabela `tab:modelos` de
      `editaveis/resultados.tex`. Verificar: a tabela traz o
      modelo comercial ao lado de `qwen2.5-coder:7b` e `gemma2:9b`, pela mesma
      leitura por procedência, e o marcador `RODADA COMERCIAL` do ponto sai.
- [ ] 3.2 Reescrever o item "Escopo de modelos" da seção de limitações
      (`sec:limitacoesresultados`) de `editaveis/resultados.tex`. Verificar: o
      texto delimita a conclusão aos modelos efetivamente executados (D2) e o
      marcador `RODADA COMERCIAL` do item sai.
- [ ] 3.3 Atualizar `fig:recall-comparado` e o parágrafo marcado em
      `subsec:supressao` (reforçar ou ressalvar a supressão excessiva, conforme
      o modelo comercial a confirme ou não). Verificar: nenhum marcador
      `RODADA COMERCIAL` resta em `resultados.tex`.
- [ ] 3.4 Registrar os números em `docs/ANALISE-RODADA-*.md` próprio antes de
      levá-los ao `.tex`. Verificar: todo número novo do capítulo tem fonte no
      documento de análise.
