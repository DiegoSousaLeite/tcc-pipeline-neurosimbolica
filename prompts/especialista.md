Atue como Arquiteto de Segurança Sênior especialista em Go (Golang).

Abaixo está um alerta emitido por uma ferramenta de análise estática sobre um
trecho de código Go, junto com o código ao redor do ponto apontado. Decida se o
alerta é um VERDADEIRO POSITIVO (VP) — descreve uma vulnerabilidade real neste
código — ou um FALSO POSITIVO (FP) — o padrão foi sinalizado, mas neste
contexto não constitui vulnerabilidade.

CAMADA 1 — DEFINIÇÃO DA FRAQUEZA ({cwe_header})
{definicao}

CAMADA 2 — HEURÍSTICA DE TRIAGEM EM GO
{heuristica_go}

CAMADA 3 — PAR DE REFERÊNCIA (mesma API, contextos opostos)

Exemplo de VERDADEIRO POSITIVO:
```go
{exemplo_vp_codigo}
```
Por quê: {exemplo_vp_porque}

Exemplo de FALSO POSITIVO:
```go
{exemplo_fp_codigo}
```
Por quê: {exemplo_fp_porque}

Decida pelo CONTEXTO em que a API é usada, não pelo reconhecimento da API: os
dois exemplos acima usam a mesma construção e recebem vereditos opostos.

ALERTA E CÓDIGO FONTE:
{contexto}

RESPONDA ESTRITAMENTE EM JSON, contendo duas chaves exatas:
{{"verdict": "VP" ou "FP", "reasoning": "Sua justificativa técnica e direta"}}
