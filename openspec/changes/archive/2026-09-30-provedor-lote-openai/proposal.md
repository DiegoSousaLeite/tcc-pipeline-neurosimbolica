## Why

Os autores indicaram, em 2026-09-30, que a validação real e a rodada comercial
devem usar o `gpt-6-luna` da OpenAI, e não o Gemini. Duas coisas impediam isso:

- **Não havia provedor de lote para a OpenAI.** `envio-em-lote-comercial`
  implementou só o do Gemini (D6), e declarou que o segundo seria "trabalho
  pequeno e conhecido". A sucessora `rodada-comercial` (tarefa 1.4) exige uma
  change própria para ele.
- **O provedor síncrono falharia com o Luna.** O Luna é modelo de raciocínio, e
  com o raciocínio no padrão (`medium`) a OpenAI exige que `temperature` seja
  removido — e o provedor manda `temperature: 0` em toda chamada.

A validação no Gemini também está bloqueada pela conta: sem billing, a
submissão é recusada com `FAILED_PRECONDITION` (registro de 2026-09-30 em
`envio-em-lote-comercial`).

**Pergunta de pesquisa atendida:** nenhuma. Infraestrutura para a
`rodada-comercial`.

**Parte do TCC:** Parte 2.

## What Changes

- **`ProvedorOpenAILote`** (`src/provedores/openai_lote.py`), implementando o
  protocolo `ProvedorLote` existente: JSONL pela Files API, lote em
  `/v1/batches` com o rótulo do cliente em `metadata`, resultado lido dos
  arquivos de saída e de erro, `batch_expired` como `EXPIRADO`.
- **`reasoning_effort: "none"`** no síncrono para os modelos de raciocínio que o
  aceitam (`gpt-6-luna`, `gpt-6-sol`), mantendo `temperature: 0`.
- **Preço do `gpt-6-luna`** na tabela, com data de consulta própria.
- **`scripts/validar_lote.py --modelo`**, para validar a esteira com o Luna.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `provedores-llm`: o provedor OpenAI passa a oferecer entrega em lote, e
  modelos de raciocínio passam a rodar com o raciocínio desligado.

## Impact

**Código:** `src/provedores/openai.py`, `src/provedores/openai_lote.py` (novo),
`src/provedores/precos.py`, `src/provedores/__init__.py`, `src/provedores/lote.py`
(função de consulta com repetição, agora comum aos dois provedores de lote),
`scripts/validar_lote.py`.

**Resultados invalidados:** nenhum. O `gpt-4o-mini` não recebe o parâmetro novo
e segue idêntico; nenhuma rodada existente usou modelo da OpenAI.

**Tabela de preços:** `VERSAO_TABELA` sobe para `2026-09-30`. Os preços antigos
não foram reconferidos, e por isso o manifesto passa a trazer a data de
consulta por modelo acrescentado.

## Não-objetivos

- Não decidir o modelo da rodada comercial — isso é da `rodada-comercial`.
- Não dar lote a modelos de raciocínio que não aceitam `none` (GPT-6 Astra,
  GPT-6.1 Sol): neles `temperature` teria de sair, e isso mudaria a condição
  experimental. Ficam para quando alguém precisar deles.
