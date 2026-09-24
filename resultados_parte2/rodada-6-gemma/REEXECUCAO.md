# Reexecução da Rodada 6 (`rodada-6-gemma`)

**Não é uma rodada nova.** É a reexecução da própria Rodada 6, feita em
2026-09-23/24 só para recuperar os CSVs caso a caso, apagados de `results/` antes
de 2026-09-22. A análise e os números de referência continuam sendo os de
`docs/ANALISE-RODADA-6.md`.

## Configuração (idêntica à original)

| campo | valor |
|---|---|
| run_id | `rodada-6-gemma` (o mesmo da original) |
| modelo | `gemma2:9b`, digest `ff02c3702f32`, Q4_0 |
| modo | triagem (`--modo-montagem triagem`) |
| prompts | `baseline_direto`, `especialista_direto` |
| catálogo | por CWE, `data/catalogo_cwe.json`, hash `e5db7d400842…` (o das Rodadas 1–6) |
| população | `--tudo`, 2.328 casos, cache simbólico |
| amostragem | semente 42, temperatura 0, `num_ctx` 8192, `num_predict` 512 |
| execução | 2026-09-24 08:18 → 15:52, um braço por vez (`scripts/reexecutar_rodadas_4_5_6.sh`) |
| commits dos resultados | `2d2245d`, `2f8581e` |

## Conferência contra os números publicados

| braço | original | reexecução |
|---|---|---|
| baseline_direto | n 1583 · VP 192 · VN 465 · FP 340 · FN 586 · MCC −0,1858 | n 1589 · VP 188 · VN 473 · FP 337 · FN 591 · MCC −0,1857 |
| especialista_direto | n 1563 · VP 62 · VN 696 · FP 107 · FN 698 · MCC −0,0832 | n 1563 · VP 56 · VN 701 · FP 105 · FN 701 · MCC −0,0930 |
| McNemar baseline × especialista | 174 × 284, p < 0,0001 | 173 × 278, p < 0,0001 |

**Reproduz.** Os dois braços e o McNemar ficam praticamente iguais aos publicados.

Diferenças de poucos casos são esperadas: mesmo com semente fixa e
temperatura 0, a inferência em GPU não é idêntica byte a byte entre execuções,
e casos longos podem cair ou não no limite de contexto (`n` varia em 1–6).
