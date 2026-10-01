## 1. Código

- [x] 1.1 Variante `modelo@esforço` no provedor OpenAI (D1), preço e teto de
      fila pelo modelo base. Verificar: testes novos em
      `tests/test_openai_lote.py` (payload, recusa, preço/fila, lote); suíte
      inteira passando (644 em 2026-10-01).

## 2. Piloto e execução

- [x] 2.1 Piloto de 20 casos por braço, em lote (D4). Verificar: 0 ERROR,
      tokens de saída medidos e projeção abaixo do teto de US$ 3,96, no design.
- [x] 2.2 Filtro: `--tudo --modo-montagem filtro --modelo gpt-6-luna@low
      --prompt baseline --prompt especialista --modo-envio lote --run-id
      rodada-comercial-luna-low-filtro`. Verificar: partições `RECUPERADA` /
      `CONCLUIDO`, custo registrado aqui.
      **2026-10-01.** Commit `50e1196`. Lotes `batch_6abed228a6ac8190aa4a3043290495ba`
      (1.515) e `batch_6abed54401b481909f3ddba3a8cf1067` (151), ambos
      `RECUPERADA` / `CONCLUIDO`, 0 ERROR / 0 EXPIRADO. Custo **US$ 0,1825**
      (projeção ~0,19). Saída média 228 / 268 tokens (sem raciocínio: 95 / 101).
      A triagem (2.3) **fica parada** até decisão dos autores, depois de verem
      o filtro.
- [x] 2.3 Triagem direta: `--modo-montagem triagem --prompt baseline_direto
      --prompt especialista_direto`, `--run-id
      rodada-comercial-luna-low-triagem-direto`, depois de 2.2. Verificar: idem;
      custo total abaixo de US$ 3,96.
      **2026-10-01** (autorizada pelos autores depois de verem o filtro).
      Commit `5f6e7a7`. Lotes `batch_6abed79b30d88190ad1e4025d579e969` (1.736),
      `batch_6abedb30e954819087fae86a1de55bed` (1.315),
      `batch_6abedd5b23388190a7b6560b4382a957` (143), todos `RECUPERADA` /
      `CONCLUIDO`, 0 ERROR / 0 EXPIRADO. Custo **US$ 0,3900**.
      **Total da change: US$ 0,5824** (pilotos US$ 0,0099 + filtro 0,1825 +
      triagem 0,3900), 15 % do teto de US$ 3,96.

## 3. Análise

- [ ] 3.1 Comparar com o Luna sem raciocínio (duas execuções) e com os locais,
      em seção própria de `docs/ANALISE-RODADA-COMERCIAL.md`; copiar os CSVs
      para `resultados_parte2/`. Verificar: a temperatura padrão (D3) e a
      execução única estão declaradas junto dos números.
- [ ] 3.2 Monografia: só sob pedido dos autores (regra de
      `escrita-capitulo-resultados`).
