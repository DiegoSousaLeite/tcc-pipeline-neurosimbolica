## Why

A rodada comercial (`rodada-comercial`) mediu o `gpt-6-luna` **sem
raciocínio**, e o capítulo de resultados declara como limitação que "o mesmo
modelo com raciocínio não foi medido". É a extensão mais barata e mais limpa
que existe: mesmo modelo, mesmos *prompts*, mesma população — muda o raciocínio
(e, por exigência da API, a temperatura deixa de ser 0).

A pergunta: o excesso de alarme do Luna no braço de filtro, e o teto de ~17 %
sobre os injetados na triagem, são da **resposta direta** ou do **modelo**?

**Parte do TCC:** Parte 2.

## What Changes

- **Código:** variante de nome `modelo@esforço` (`gpt-6-luna@low`). O nome
  completo vai ao CSV e ao checkpoint; à API, o nome base com
  `reasoning_effort: "<esforço>"` e sem `temperature`. Preço e teto de fila
  pelo modelo base.
- **Execução:** uma execução de cada braço — filtro e triagem direta — com
  `gpt-6-luna@low`, em lote, depois de um piloto de 20 casos por braço.

## Capabilities

### Modified Capabilities

- `provedores-llm`: o requisito "Modelo de raciocínio roda sem raciocínio e com
  temperatura zero" passa a admitir a variante com esforço explícito.

## Impact

**Código:** `src/provedores/openai.py`, `precos.py`, `openai_lote.py`; testes
em `tests/test_openai_lote.py`.

**Custo:** teto dos autores **US$ 3,96** (saldo da conta). Projeção pelo
piloto: ~US$ 0,58; pior caso ~US$ 1,45.

**Resultados invalidados:** nenhum. A rodada sem raciocínio fica como está.

## Não-objetivos

- **Não** rodar duas vezes cada braço nesta etapa (decisão dos autores, por
  saldo): uma diferença marginal não poderá ser separada da variação do modelo.
- **Não** rodar a triagem no enquadramento de alerta.
- ~~**Não** testar `medium`/`high`.~~ Revisto em 2026-10-01: os autores pediram
  o piloto com `high` na triagem direta (`especialista_direto`), onde o `low`
  teve efeito — ver `tasks.md` 2.4.
