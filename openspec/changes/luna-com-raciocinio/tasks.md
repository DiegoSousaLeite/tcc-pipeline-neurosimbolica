## 1. Código

- [x] 1.1 Variante `modelo@esforço` no provedor OpenAI (D1), preço e teto de
      fila pelo modelo base. Verificar: testes novos em
      `tests/test_openai_lote.py` (payload, recusa, preço/fila, lote); suíte
      inteira passando (644 em 2026-10-01).

## 2. Piloto e execução

- [x] 2.1 Piloto de 20 casos por braço, em lote (D4). Verificar: 0 ERROR,
      tokens de saída medidos e projeção abaixo do teto de US$ 3,96, no design.
- [ ] 2.2 Filtro: `--tudo --modo-montagem filtro --modelo gpt-6-luna@low
      --prompt baseline --prompt especialista --modo-envio lote --run-id
      rodada-comercial-luna-low-filtro`. Verificar: partições `RECUPERADA` /
      `CONCLUIDO`, custo registrado aqui.
- [ ] 2.3 Triagem direta: `--modo-montagem triagem --prompt baseline_direto
      --prompt especialista_direto`, `--run-id
      rodada-comercial-luna-low-triagem-direto`, depois de 2.2. Verificar: idem;
      custo total abaixo de US$ 3,96.

## 3. Análise

- [ ] 3.1 Comparar com o Luna sem raciocínio (duas execuções) e com os locais,
      em seção própria de `docs/ANALISE-RODADA-COMERCIAL.md`; copiar os CSVs
      para `resultados_parte2/`. Verificar: a temperatura padrão (D3) e a
      execução única estão declaradas junto dos números.
- [ ] 3.2 Monografia: só sob pedido dos autores (regra de
      `escrita-capitulo-resultados`).
