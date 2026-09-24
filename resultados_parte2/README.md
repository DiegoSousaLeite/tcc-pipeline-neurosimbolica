# Resultados da Parte 2 — cópia versionada

`results/` fica fora do git (`.gitignore`) e é onde a pipeline grava. Esta pasta
é a **cópia versionada** dos resultados que a monografia cita, pelo mesmo motivo
de `legacy/resultados_parte1/`: os CSVs caso a caso das Rodadas 4, 5 e 6 foram
apagados de `results/` antes de 2026-09-22, e com eles foi embora a
possibilidade de conferir ou recalcular aqueles números. Nada aqui é apagado ou
sobrescrito; uma rodada nova entra como pasta nova.

Cada pasta tem um CSV por braço (`<modelo>__<prompt>.csv`) e o
`manifesto.json` da execução. As métricas saem de
`python -m src.metricas resultados_parte2/<pasta> --mcnemar`.

## Qual pasta é qual rodada

| rodada | pasta | modelo | modo | prompts | catálogo | análise |
|---|---|---|---|---|---|---|
| 1 | `20260730T180648Z-14d6af8` | qwen2.5-coder:7b | filtro | baseline, especialista | por CWE | `docs/ANALISE-RODADA-1.md` |
| 2 | `20260731T140000Z-af9bc32` | qwen2.5-coder:7b | filtro | baseline, especialista | por CWE | `docs/ANALISE-RODADA-2.md` |
| 3 | `20260908T094808Z-9a00cb2` | qwen2.5-coder:7b | filtro | baseline, especialista | por CWE | `docs/ANALISE-RODADA-3.md` |
| 4 | `rodada-4-triagem` | qwen2.5-coder:7b | triagem | baseline, especialista | por CWE | `docs/ANALISE-RODADA-4.md` |
| 5 | `rodada-5-direto` | qwen2.5-coder:7b | triagem | baseline_direto, especialista_direto | por CWE | `docs/ANALISE-RODADA-5.md` |
| 6 | `rodada-6-gemma` | gemma2:9b | triagem | baseline_direto, especialista_direto | por CWE | `docs/ANALISE-RODADA-6.md` |
| 7 | `rodada-7-{filtro,triagem}-{qwen,gemma}` | qwen e gemma | filtro e triagem | especialista, v2 (+ baseline gemma/filtro) | **por regra** | `docs/ANALISE-RODADA-7.md` |
| 7b | `rodada-7b-filtro-gemma-cwe` | gemma2:9b | filtro | especialista | por CWE | `docs/ANALISE-RODADA-7.md` §2.2 |

## Rodadas 4, 5 e 6: reexecuções, não testes novos

As pastas `rodada-4-triagem`, `rodada-5-direto` e `rodada-6-gemma` são a
**reexecução das próprias Rodadas 4, 5 e 6**, feita em 2026-09-23/24 só para
recuperar os CSVs caso a caso que se perderam. Mesma configuração das
originais: mesmo modelo e digest, mesmos *templates* (hashes travados em teste),
mesmo catálogo por CWE (`e5db7d40…`), mesma população de 2.328 casos, mesmo
cache simbólico, semente 42 e temperatura 0. **Não são rodadas a mais nem
experimentos novos**, e não devem ser apresentadas como tal. Cada uma dessas
pastas tem um `REEXECUCAO.md` com a data, o commit e a conferência contra os
números publicados na análise original.
