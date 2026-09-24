# Reexecução da Rodada 5 (`rodada-5-direto`)

**Não é uma rodada nova.** É a reexecução da própria Rodada 5, feita em
2026-09-23/24 só para recuperar os CSVs caso a caso, apagados de `results/` antes
de 2026-09-22. A análise e os números de referência continuam sendo os de
`docs/ANALISE-RODADA-5.md`.

## Configuração (idêntica à original)

| campo | valor |
|---|---|
| run_id | `rodada-5-direto` (o mesmo da original) |
| modelo | `qwen2.5-coder:7b`, digest `dae161e27b0e`, Q4_K_M |
| modo | triagem (`--modo-montagem triagem`) |
| prompts | `baseline_direto`, `especialista_direto` |
| catálogo | por CWE, `data/catalogo_cwe.json`, hash `e5db7d400842…` (o das Rodadas 1–6) |
| população | `--tudo`, 2.328 casos, cache simbólico |
| amostragem | semente 42, temperatura 0, `num_ctx` 8192, `num_predict` 512 |
| execução | 2026-09-24 04:12 → 08:18, um braço por vez (`scripts/reexecutar_rodadas_4_5_6.sh`) |
| commits dos resultados | `1ad91fc`, `350978e` |

## Conferência contra os números publicados

| braço | original | reexecução |
|---|---|---|
| baseline_direto | n 1588 · VP 10 · VN 776 · FP 32 · FN 770 · MCC −0,0834 | n 1591 · VP 11 · VN 781 · FP 30 · FN 769 · MCC −0,0722 |
| especialista_direto | n 1587 · VP 40 · VN 773 · FP 35 · FN 739 · P 0,533 · MCC +0,0189 | n 1590 · VP 38 · VN 772 · FP 39 · FN 741 · P 0,494 · MCC +0,0016 |
| McNemar baseline × especialista | 36 × 63, **p = 0,0090** | 40 × 58, **p = 0,0859** |

**Reproduz em ordem de grandeza, mas não na significância.** A direção se
mantém — o especialista direto acerta mais que o baseline direto —, mas o
McNemar deixa de ser significativo (p = 0,086), e a precisão do especialista
direto cai para 49,4 %, praticamente a taxa-base (~49 %), com MCC colado no zero.
**Frases a suavizar no texto:** "o eixo do prompt volta a ser estatisticamente
detectável" (`resultados.tex`, §Rodada 5) e "única configuração com precisão
acima da taxa-base" (`docs/ANALISE-RODADA-6.md`). A leitura sustentável é:
indicação de vantagem do especialista direto, não significativa na reexecução.

Diferenças de poucos casos são esperadas: mesmo com semente fixa e
temperatura 0, a inferência em GPU não é idêntica byte a byte entre execuções,
e casos longos podem cair ou não no limite de contexto (`n` varia em 1–6).
