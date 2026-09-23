## Why

A ficha do prompt especialista é escolhida pela CWE do caso, mas uma mesma CWE agrupa regras do Semgrep que olham para construções de código diferentes. Medido sobre as 791 detecções do cache simbólico (2026-09-22), em várias CWEs a ficha fala de uma API e o alerta aponta outra: em CWE-327 a ficha ensina `md5` em senha e os 93 alertas são `missing-ssl-minversion` (configuração TLS); em CWE-94 a ficha ensina template montado de entrada externa e 91 de 94 alertas são `dangerous-exec-command`; em CWE-665 a ficha ensina chave zerada em `aes`/`hmac` e os alertas são regras de corretude da Trail of Bits. Nesses cerca de 260 casos as camadas 1–3 não orientam o julgamento do alerta que o modelo recebe, e o braço especialista deixa de ser, ali, a condição experimental que a monografia descreve.

Somado a isso, o especialista respondeu VP zero vezes na rodada `20260908T094808Z-9a00cb2`, inclusive nos 5 vulneráveis de CWE-79. As fichas atuais terminam sempre na condição de FP ("... não caracteriza a fraqueza"), e o template não diz nada sobre mitigação que não aparece no trecho.

Pergunta de pesquisa atendida: a da Parte 2 que compara baseline e especialista (eixo horizontal da matriz). A mudança não cria pergunta nova; torna a comparação válida em todas as CWEs em vez de só nas que a ficha acerta por coincidência.

## What Changes

- O catálogo ganha um bloco `regras`, com fichas no mesmo formato das fichas de CWE, indexadas pelo `check_id` completo do Semgrep.
- A resolução da ficha passa a seguir a precedência **regra > CWE > fallback**. A ficha de CWE continua existindo e continua sendo a usada quando não há regra (candidato injetado do gabarito no braço de triagem) ou quando a regra não tem ficha própria.
- A coluna `Ficha_CWE` do CSV ganha o valor `regra`, ao lado de `especifica` e `fallback`.
- Novas fichas de regra para as regras cujo alvo diverge da API central da ficha da CWE: no mínimo `missing-ssl-minversion`, `dangerous-exec-command`/`dangerous-exec-cmd`, `invalid-usage-of-modified-variable`, `iterate-over-empty-map`, `bypass-tls-verification`, `use-tls`, `import-text-template` e `websocket-missing-origin-check`. A lista final sai de uma auditoria regra × ficha feita antes da escrita.
- Fichas escritas a partir da documentação das regras (registry do Semgrep, repositório de regras da Trail of Bits) e da documentação da stdlib de Go, **sem consulta às amostras avaliadas**, como o protocolo anti-viés já exige.
- Correção do viés para FP no conteúdo: heurísticas (de regra e de CWE) passam a declarar explicitamente a condição de VP, e não apenas a de FP.
- Novos templates `prompts/especialista_v2.md` (modo filtro) e `prompts/especialista_direto_v2.md` (modo triagem), cada um igual ao seu original com uma instrução a mais: não presumir mitigação que não aparece no trecho. São **arquivos novos** e tipos de prompt novos; `especialista.md` e `especialista_direto.md` não são editados, para não tornar as rodadas anteriores irreproduzíveis.
- **Invalida resultados**: o `Hash_Catalogo` muda, então todas as linhas do braço especialista produzidas até aqui (rodadas `20260731T*` e `20260908T094808Z-9a00cb2`) deixam de ser agregáveis com as novas. O mesmo vale para o `especialista_direto` do braço de triagem (Rodadas 4–6, qwen e gemma), que lê o mesmo catálogo: os casos que vêm de alerta passam a receber a ficha de regra; os injetados do gabarito continuam com a ficha de CWE. O braço baseline não é afetado: não lê o catálogo. O braço especialista precisa ser refeito.
- **Provável mudança nas evidências e na escrita dos resultados**: as tabelas, os números por CWE e a comparação baseline × especialista usados como evidência (incluindo o que já foi rascunhado em `editaveis/resultados.tex` e `docs/PLANO-ESCRITA-RESULTADOS.md`) provavelmente terão de ser refeitos a partir da rodada nova. O texto da metodologia também muda (ficha por regra, variante `especialista_v2`). Até a rodada nova existir, nenhum número do especialista deve ser tratado como definitivo na monografia.
- A rodada nova é **só local** (Ollama), com **dois modelos** (`qwen2.5-coder:7b`, principal, e `gemma2:9b`, para ver se o efeito se repete em outra família) e **nos dois modos de montagem** (filtro e triagem). Os braços comerciais ficam fora desta mudança e serão rodados depois, pelos autores.
- Os CSVs das Rodadas 5 e 6 (`results/rodada-5-direto`, `results/rodada-6-gemma`) não estão mais no disco, e o gemma nunca rodou no modo filtro. Critério da rodada nova: **não repetir o que já foi testado**. O baseline não lê o catálogo, então baseline já medido não é refeito: o `baseline` do qwen no filtro vem da rodada `20260908T094808Z-9a00cb2` (CSV em disco) e o `baseline_direto` dos dois modelos na triagem fica com os números publicados das Rodadas 5 e 6. Entram o que nunca rodou (o gemma inteiro no modo filtro) e todo braço que lê o catálogo. A regra vale igual para os dois modelos. Custo aceito: como os CSVs das Rodadas 5 e 6 foram apagados, a comparação baseline × especialista na triagem é feita só contra os agregados publicados, sem McNemar.

## Não-objetivos

- Não reescreve as fichas de CWE que já casam com as regras que disparam (CWE-338, CWE-328, CWE-667, CWE-681), além do ajuste de viés na heurística.
- Não gera fichas automaticamente nem a partir de trechos do cache, do dataset ou dos CSVs.
- Não altera o baseline, o contrato de saída JSON, a hidratação do contexto nem a Fase 1.
- Não troca o modelo nem o provedor.
- Não roda os braços comerciais (Gemini, GPT); isso fica para depois, fora desta mudança.
- Não resolve a dependência do `Hash_Catalogo` em relação ao fim de linha do checkout (CRLF/LF); é problema separado.
- Não cria ficha para regra rara (< 5 detecções) cuja CWE já tem ficha adequada; essas continuam na ficha de CWE.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `catalogo-cwe`: o catálogo passa a ter fichas por regra do Semgrep, com precedência regra > CWE > fallback, validação do bloco `regras`, novo valor de origem `regra` e exigência de que as heurísticas declarem a condição de VP.
- `prompts-versionados`: novos tipos `especialista_v2` e `especialista_direto_v2`, com as mesmas três camadas e uma instrução sobre mitigação ausente; a ficha usada no especialista passa a depender do alerta, não só da CWE.

## Impact

- `data/catalogo_cwe.json`: bloco `regras` novo e ajuste das heurísticas; novo hash.
- `src/catalogo.py`: validação do bloco `regras`, `ficha(cwe, cwe_name, check_id=None)` com a nova precedência, origem `regra`.
- `src/prompts.py`: tipos `especialista_v2` e `especialista_direto_v2`.
- `prompts/especialista_v2.md` e `prompts/especialista_direto_v2.md`: templates novos.
- `run_pipeline.py`: a ficha passa a ser resolvida depois da candidatura, com o `check_id` do candidato; casos sem candidato continuam com a ficha de CWE.
- `src/metricas.py`: estratificação por origem da ficha reconhece `regra`.
- `tests/test_catalogo.py`, `tests/test_prompts.py`, testes do runner.
- `docs/PIPELINE.md` e o protocolo anti-viés na documentação; texto da metodologia na monografia (Parte 2).
- Resultados: nova rodada local (qwen e gemma, filtro e triagem) dos braços especialista e v2, mais os baselines de controle que faltam, sobre as mesmas populações das rodadas de referência; as linhas antigas do especialista ficam como registro histórico com o hash antigo.
- Monografia: evidências e escrita do capítulo de resultados (`editaveis/resultados.tex`, `docs/PLANO-ESCRITA-RESULTADOS.md`) e trecho da metodologia provavelmente precisarão ser revistos; o registro do que muda vai para `docs/MAPA-TCC-O-QUE-REESCREVER.md`.
