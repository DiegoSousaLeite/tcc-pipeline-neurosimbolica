# Auditoria qualitativa da Q4 — resultado (PROVISÓRIO)

> **Pré-classificação assistida por IA, 2026-09-22, aguardando revisão dos
> autores.** Critério em `CRITERIO.md`, registrado antes da amostragem. Planilha
> caso a caso em `classificacao.csv`; amostra reproduzível por `amostrar.py`.
>
> ⛔ Não commitar sem pedido explícito do autor.

Amostra: 25 casos da Rodada 3 (braço de filtro, `qwen2.5-coder:7b`), cada um
lido nos dois prompts — 50 vereditos. Estratos: E-VP 3/3, E-FP 12/12, E-FN 5/16,
E-VN/B-FP 5/104 (ver `CRITERIO.md` §2). **As proporções abaixo são da amostra
estratificada e não estimam a população sem reponderação.**

## Eixo 1 — fundamento

| prompt | FUNDADO | MOTIVO_ERRADO | ALUCINACAO |
|---|---:|---:|---:|
| baseline (25) | 2 | 22 | 1 |
| especialista (25) | 4 | 18 | 3 |
| **total (50)** | **6** | **40** | **4** |

Cruzando com o acerto do veredito:

| prompt | vereditos certos | certos e FUNDADO | certos por motivo errado ou alucinação |
|---|---:|---:|---:|
| baseline | 4 | 1 | 3 |
| especialista | 8 | 4 | 4 |

Os quatro FUNDADO do especialista estão todos em vereditos certos; três deles no
estrato E-VN/B-FP, isto é, nos casos em que o especialista descartou o ruído que o
baseline manteve — o argumento aponta o uso não criptográfico do MD5 ou do
`math/rand`, que é o que a heurística do catálogo pede para verificar.

## O que a leitura mostrou (padrões, não contagens)

1. **Repetição da mensagem do alerta.** Nos 8 casos de CWE-614 do estrato E-FP e
   nos 2 de E-VP, os dois prompts afirmam que o cookie "não tem o atributo
   `Secure`", quando o código define `Secure:` a partir de uma variável, de
   `isTLS(r)` ou de `isSecure(r)`. É a frase da mensagem do Semgrep, não uma
   leitura do código. O mesmo mecanismo aparece no `io.CopyN` do caso 8, que está
   na mensagem do alerta e não no código.
2. **Reprodução do exemplo do catálogo.** No caso 16 (`cri-o`, CWE-94), o
   especialista reproduz quase literalmente a justificativa do `exemplo_fp` da
   ficha de CWE-94 ("a entrada externa é apenas dado interpolado, não código"),
   trocando "template" por "comando" — num caso em que a entrada externa chega
   aos argumentos do processo e a vulnerabilidade é real.
3. **Raciocínio certo, veredito oposto.** Nos casos 12 e 13 (`incus`, CWE-327) o
   especialista descreve corretamente o código como boa prática (TLS 1.3 por
   padrão) e emite "verdadeiro positivo".
4. **Entradas idênticas, rótulos opostos.** Os casos 1/10 e 2/11 (`nebula-mesh`)
   entregam ao modelo **o mesmo recorte, byte a byte**, rotulado vulnerável na
   versão anterior à correção e seguro na corrigida. Com temperatura zero e
   semente fixa, o modelo necessariamente erra um dos dois. É a granularidade do
   rótulo vista do lado do modelo.

## Eixo 2 — os seguros mantidos eram seguros?

17 casos de gabarito seguro mantidos por pelo menos um dos prompts:

| | SEGURO | INDETERMINADO | VULNERAVEL |
|---|---:|---:|---:|
| mantidos pelo especialista (12, população inteira do estrato) | 6 | 6 | 0 |
| mantidos só pelo baseline (5 sorteados de 104) | 5 | 0 | 0 |

Nenhum foi classificado como vulnerável de forma inequívoca. Mas **metade dos 12
falsos positivos do especialista não é decidível a partir do recorte entregue**:
cinco dependem de como uma variável de configuração é definida fora da função, e
um (caso 8, `portainer`) exibe dois padrões sem mitigação — cópia ilimitada de
arquivo compactado e montagem de caminho sem verificação de prefixo (*zip-slip*,
CWE-22) — cuja exploração depende da origem do arquivo, fora do recorte.

Leitura para a ameaça da classe negativa aproximada: dos 12 alertas que o
especialista manteve sobre código rotulado seguro, 0 foram confirmados como
vulnerabilidade real, 6 como seguros e 6 ficaram indeterminados; entre os
indeterminados há ao menos um forte candidato a vulnerabilidade de outra CWE.
