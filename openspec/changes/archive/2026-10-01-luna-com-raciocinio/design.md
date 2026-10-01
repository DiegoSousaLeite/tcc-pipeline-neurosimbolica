## Context

`provedores-llm` força `reasoning_effort: "none"` e `temperature: 0` no Luna.
A API recusa `temperature` quando o esforço não é `none` e o padrão do Luna é
`medium` (`src/provedores/openai.py`, citação da documentação).

## Decisions

### D1 — Variante no nome do modelo, e não flag de linha de comando

`gpt-6-luna@low`. O nome completo é a identidade do braço: entra em
`Modelo_LLM`, no nome do CSV e na chave do checkpoint, e uma rodada com
raciocínio nunca se mistura com uma sem. Uma flag deixaria a distinção só no
manifesto. Preço (`precos.modelo_base`) e teto de fila usam o nome base: é o
mesmo modelo, cobrado igual, e os tokens de raciocínio já vêm somados aos de
saída. Variante em modelo que não é de raciocínio, ou esforço fora de
`low`/`medium`/`high`, é recusada na construção do provedor.

### D2 — Esforço `low`

É o realista para triagem em volume e o que cabe no saldo com folga. Mede-se
"raciocínio ligado", não o teto do raciocínio.

### D3 — Temperatura padrão, declarada

Com raciocínio, a chamada sai na temperatura padrão do fornecedor. Mudam juntas
duas coisas — raciocínio e temperatura —, e o texto precisa dizê-lo.

### D4 — Piloto antes da rodada, no mesmo modo de envio

20 casos por braço, em lote (D3 de `rodada-comercial`), para medir os tokens de
raciocínio antes de gastar.

**Piloto de 2026-10-01** (`results/piloto-luna-low-{filtro,triagem-direto}`):
40 + 40 requisições, 0 ERROR, US$ 0,0049 + 0,0049. Saída média com `low`:
245 / 281 tokens no filtro (sem raciocínio: 95 / 101), 408 / 176 na triagem
direta (sem: 88 / 83); máximo observado 1.057.

| execução | requisições | esperado | pior caso (1.000 tokens de saída em todas) |
|---|---:|---:|---:|
| filtro | 1.666 | ~US$ 0,19 | ~US$ 0,50 |
| triagem direta | 3.194 | ~US$ 0,39 | ~US$ 0,95 |
| **total** | | **~US$ 0,58** | **~US$ 1,45** (teto US$ 3,96) |

## Risks / Trade-offs

**[Uma execução por braço]** → a rodada sem raciocínio mostrou que a variação
entre execuções desfaz significância marginal (filtro: p = 0,032 → 0,227).
Mitigação: comparar contra as duas execuções sem raciocínio e só afirmar
diferenças muito acima dessa variação.
