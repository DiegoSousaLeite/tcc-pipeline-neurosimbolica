# Reexecução da Rodada 4 (`rodada-4-triagem`)

**Não é uma rodada nova.** É a reexecução da própria Rodada 4, feita em
2026-09-23/24 só para recuperar os CSVs caso a caso, apagados de `results/` antes
de 2026-09-22. A análise e os números de referência continuam sendo os de
`docs/ANALISE-RODADA-4.md`.

## Configuração (idêntica à original)

| campo | valor |
|---|---|
| run_id | `rodada-4-triagem` (o mesmo da original) |
| modelo | `qwen2.5-coder:7b`, digest `dae161e27b0e`, Q4_K_M |
| modo | triagem (`--modo-montagem triagem`) |
| prompts | `baseline`, `especialista` (enquadramento de alerta) |
| catálogo | por CWE, `data/catalogo_cwe.json`, hash `e5db7d400842…` (o das Rodadas 1–6) |
| população | `--tudo`, 2.328 casos, cache simbólico |
| amostragem | semente 42, temperatura 0, `num_ctx` 8192, `num_predict` 512 |
| execução | 2026-09-23 23:53 → 2026-09-24 04:12, um braço por vez (`scripts/reexecutar_rodadas_4_5_6.sh`) |
| commits dos resultados | `71e129c`, `19cd852` |

## Conferência contra os números publicados

| braço | original | reexecução |
|---|---|---|
| baseline | n 1585 · VP 3 · VN 803 · FP 2 · FN 777 · MCC 0,0121 | n 1589 · VP 3 · VN 807 · FP 2 · FN 777 · MCC 0,0123 |
| especialista | n 1586 · VP 10 · VN 797 · FP 11 · FN 768 · MCC −0,0033 | n 1583 · VP 11 · VN 796 · FP 11 · FN 765 · MCC 0,0023 |
| McNemar baseline × especialista | 14 × 12, p = 0,8445 | 14 × 13, p = 1,0 |

**Reproduz.** A conclusão publicada — os dois prompts não se distinguem na triagem com o enquadramento de alerta — se mantém.

Diferenças de poucos casos são esperadas: mesmo com semente fixa e
temperatura 0, a inferência em GPU não é idêntica byte a byte entre execuções,
e casos longos podem cair ou não no limite de contexto (`n` varia em 1–6).
