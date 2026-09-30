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

- [ ] 2.1 Rodar o braço de filtro (`--modo-montagem filtro`, `baseline` e
      `especialista`, `--modo-envio lote`) sobre a população de referência,
      **duas vezes** (D5), com `--run-id rodada-comercial-luna-filtro` e
      `--run-id rodada-comercial-luna-filtro-2`. Verificar: nos dois,
      `manifesto.json` traz `modo.envio = "lote"`, o fornecedor e o `id_lote`
      de cada partição; nenhuma partição fora de `RECUPERADA`; a concordância
      entre as duas execuções está registrada.
- [ ] 2.2 Registrar o custo observado ao lado do estimado (~US$ 0,12 por
      execução do filtro e ~US$ 0,23 por execução da triagem, design D6). Verificar: consta deste arquivo, com a
      fonte (`lotes[].custo_estimado_usd` do manifesto), e o total segue abaixo
      do teto de US$ 2.
- [ ] 2.3 Braço de triagem, **duas vezes**, **depois do filtro** (decisão de
      2026-09-30, design D5; estimativa ~US$ 0,23 cada). Verificar: mesma forma
      de 2.1, com `--modo-montagem triagem` e `--run-id
      rodada-comercial-luna-triagem` e `rodada-comercial-luna-triagem-2`; a
      concordância entre as duas execuções está registrada. Uma execução de
      cada vez (design D6: a fila do modelo não comporta duas triagens juntas).

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
