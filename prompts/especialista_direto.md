Atue como Arquiteto de Segurança Sênior especialista em Go (Golang).

Abaixo está um trecho de código Go. Decida se ele contém a fraqueza descrita
abaixo: responda VP se contém — o código é explorável como está — ou FP se não
contém — o código é seguro neste contexto.

Julgue o código. Não há alerta de ferramenta a validar.

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

CÓDIGO FONTE:
{contexto}

RESPONDA ESTRITAMENTE EM JSON, contendo duas chaves exatas:
{{"verdict": "VP" ou "FP", "reasoning": "Sua justificativa técnica e direta"}}
