## Why

O braço comercial deste trabalho nunca rodou: o projeto inteiro tem **17
vereditos comerciais** válidos, todos de piloto. As conclusões do capítulo de
resultados estão, por isso, delimitadas a "modelos locais de 7 a 9 bilhões de
parâmetros" — e essa delimitação é exatamente a objeção de escopo que a banca
tem mais motivo para levantar.

O impedimento medido nunca foi preço, e sim vazão: 20 requisições por dia no
tier grátis do Gemini. A change `envio-em-lote-comercial` removeu esse
impedimento — construiu o modo de envio em lote (`--modo-envio lote`), sem RPM a
estourar e com 50 % de desconto — e **nomeou esta change como sua consumidora
obrigatória**. Esta change é o destino daquele andaime.

**Pergunta de pesquisa atendida:** o escopo das respostas a Q1, Q2 e Q3 — se o
que foi medido em modelos locais vale, ou não, para um modelo comercial sobre a
mesma população.

**Estado:** parada, aguardando decisão de orçamento. Nada aqui executa enquanto
os autores não autorizarem o gasto e não houver billing ativo.

**Parte do TCC:** Parte 2.

## What Changes

- **Executar a rodada comercial** sobre a população de referência, no modo de
  envio `lote`, **começando pelo braço de filtro** (ver `design.md`, D1).
- **Fechar os quatro pontos de `editaveis/resultados.tex`** marcados com
  `RODADA COMERCIAL`, dos quais dois são obrigatórios por construção desta
  change: as linhas dos modelos de fronteira na Tabela `tab:modelos` e o item
  "Escopo de modelos" da seção de limitações.
- **Registrar o escopo efetivo** da conclusão comercial: um único modelo
  comercial, da OpenAI (o Gemini foi descartado em 2026-09-30) — "três modelos,
  um comercial", e não "quatro, dois comerciais".

## Capabilities

### New Capabilities

- `rodada-comercial`: o que uma rodada com modelo comercial precisa garantir
  para ser comparável às rodadas locais e citável na monografia — ordem dos
  braços, uniformidade do modo de envio entre piloto e rodada, orçamento
  autorizado antes do gasto e escopo declarado da conclusão.

### Modified Capabilities

(nenhuma)

## Impact

**Código:** nenhum previsto. O provedor de lote da OpenAI existe desde
2026-09-30 (`provedor-lote-openai`); só um modelo de outro fornecedor, como a
Anthropic, exigiria provedores novos.

**Monografia:** `editaveis/resultados.tex` (os quatro pontos marcados), sob a
regra da change `escrita-capitulo-resultados`: nenhuma edição é commitada sem
pedido explícito dos autores.

**Custo:** a decidir. Faixa levantada em `docs/ESCOLHA-MODELO-COMERCIAL.md` §9:
de R$ 1,15 a R$ 160 por rodada de dois braços, conforme o modelo.

**Resultados invalidados:** nenhum. As rodadas locais não são reexecutadas.

## Não-objetivos

- **Não** reabrir o desenho de prompt, população, catálogo ou modo de montagem.
- **Não** tornar o lote o padrão da pipeline.
- **Não** executar a matriz comercial completa se o orçamento cobrir só o braço
  de filtro — o braço de triagem é extensão opcional (D1).
