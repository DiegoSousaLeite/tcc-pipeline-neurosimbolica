## 1. Resolução da ficha por regra (código, sem conteúdo novo)

- [x] 1.1 Em `src/catalogo.py`, aceitar o bloco opcional `regras` (mapa `check_id -> ficha`), validá-lo com os mesmos campos obrigatórios e excluí-lo de `cwes_especificas` e `tem_ficha`, como `__fallback__`. Verificar: `pytest -q tests/test_catalogo.py`, com teste novo de ficha de regra malformada cujo erro nomeia a regra.
- [x] 1.2 Estender `Catalogo.ficha(cwe, cwe_name="", check_id=None)` com a precedência regra > CWE > fallback, casamento pelo `check_id` completo, `VALOR_NEUTRO` tratado como ausência de regra e origem `regra`. Verificar: testes dos cenários "Regra com ficha própria", "Regra sem ficha própria", "Sem regra", "Casamento exato" e "Ficha de regra preserva a CWE do caso", com catálogo de fixture.
- [x] 1.3 Em `run_pipeline.py`, resolver a ficha depois de `montar_candidatura`, usando o `check_id` do candidato; casos sem candidato mantêm a ficha de CWE. Verificar: teste do runner em que um alerta de regra com ficha grava `Ficha_CWE=regra` e um `NAO_DETECTADO` grava a origem da ficha de CWE.
- [x] 1.4 Conferir que a estratificação por `Ficha_CWE` em `src/metricas.py` lista `regra` sem mudança de código. Verificar: `python -m src.metricas <csv-de-fixture> --estratificar`, com um CSV com os três valores.

## 2. Templates v2

- [x] 2.1 Criar `prompts/especialista_v2.md` (cópia de `especialista.md`) e `prompts/especialista_direto_v2.md` (cópia de `especialista_direto.md`), acrescentando nos dois o mesmo parágrafo de D4, antes da seção do contexto. Verificar: `diff` de cada par mostra só o parágrafo novo, com texto idêntico nos dois.
- [x] 2.2 Registrar `ESPECIALISTA_V2` e `ESPECIALISTA_DIRETO_V2` em `src/prompts.py` (em `TIPOS`, fora de `TIPOS_SEM_FICHA`; o direto também em `TIPOS_DIRETOS`). Verificar: `pytest -q tests/test_prompts.py` com testes de instrução presente só nas variantes, contrato idêntico e hashes originais travados (`especialista:d1145f8b`, `especialista_direto:f537598a`).
- [x] 2.3 Conferir que `--prompt` e `--matriz` aceitam os tipos novos, que o modo triagem aceita `especialista_direto_v2` e que o manifesto lista as versões. Verificar: `python run_pipeline.py --amostra 2 --prompt especialista_v2 --sem-llm` termina sem erro e o manifesto contém `especialista_v2:<hash>` e `especialista_direto_v2:<hash>`.

## 3. Auditoria regra × ficha (só metadados)

- [x] 3.1 Escrever `scripts/auditar_regras_ficha.py`, que conta `check_id` por CWE do caso a partir do cache simbólico **sem ler `contexto_hidratado`** e emite a tabela regra, CWE, detecções. Verificar: a execução reproduz as contagens da tabela do `design.md` (93 para `missing-ssl-minversion`, 91 para `dangerous-exec-command`, ...).
- [x] 3.2 Aplicar o critério de D6 (≥ 5 detecções e alvo diferente da API central da ficha da CWE) e gravar a lista final em `openspec/changes/ficha-por-regra-semgrep/regras-selecionadas.md`, com uma linha de justificativa por regra. Verificar: inspeção do arquivo; inclui no mínimo as 8 regras citadas na proposta ou justifica a exclusão.

## 4. Conteúdo do catálogo

- [x] 4.1 Registrar no `regras-selecionadas.md` quem escreve as fichas e com qual ferramenta, para a declaração de uso de IA da monografia. Verificar: inspeção do arquivo.
- [x] 4.2 Escrever as fichas de regra das regras de TLS (`missing-ssl-minversion`, `bypass-tls-verification`, `use-tls`) a partir do registry do Semgrep e da stdlib, conferindo nas release notes de Go os mínimos padrão de TLS citados. Verificar: `python -c "from src.catalogo import Catalogo; Catalogo.carregar()"` carrega sem erro.
- [x] 4.3 Escrever as fichas de `dangerous-exec-command` e `dangerous-exec-cmd`, com exemplo FP que não seja editor lido de variável de ambiente. Verificar: carregamento sem erro.
- [x] 4.4 Escrever as fichas das regras de corretude da Trail of Bits (`invalid-usage-of-modified-variable`, `iterate-over-empty-map`) a partir de `trailofbits/semgrep-rules`, declarando na definição que são regras de corretude. Verificar: carregamento sem erro.
- [x] 4.5 Escrever as fichas das demais regras selecionadas em 3.2 (no mínimo `import-text-template` e `websocket-missing-origin-check`). Verificar: carregamento sem erro.
- [x] 4.6 Reescrever as heurísticas das 15 fichas de CWE no formato "É VP quando ... / É FP quando ...", sem mudar definição nem exemplos. Verificar: teste novo em `tests/test_catalogo.py` exige as duas frases em toda heurística específica, de CWE e de regra.
- [x] 4.7 Validar os exemplos: todo `codigo` é Go sintaticamente válido e todas as fichas de regra usam a construção da regra nos dois exemplos. Verificar: o teste de Go válido já existente cobre o bloco `regras`; teste novo: a ficha de `missing-ssl-minversion` usa `tls.Config` nos dois exemplos e não usa `md5`/`sha1`.
- [x] 4.8 Verificar a não contaminação: nenhum trecho de exemplo (linhas não triviais) aparece em `cache/` ou `cache_simbolico/`. Verificar: script ou teste que procura cada linha não trivial dos exemplos nos arquivos do cache e retorna zero ocorrências.
- [x] 4.9 Congelar o catálogo num commit próprio e registrar o novo SHA-256. Verificar: `sha256sum data/catalogo_cwe.json` bate com o hash gravado no manifesto da primeira rodada nova.

## 5. Rodada nova

Tudo local (Ollama); nada de Gemini/GPT nesta mudança. Semente 42, temperatura 0. Fase 1 servida do cache simbólico, com o modelo carregado só depois dela.

- [x] 5.1 Registrar os digests locais de `qwen2.5-coder:7b` e `gemma2:9b` e conferir se o do gemma é o da Rodada 6 (`ff02c3702f32`) e o do qwen o da rodada `20260908T094808Z-9a00cb2`. Verificar: `ollama show` contra os manifestos de referência; divergência registrada no `regras-selecionadas.md`.
- [x] 5.2 Rodada **filtro**: qwen com `especialista` e `especialista_v2` (baseline reaproveitado de `20260908T094808Z-9a00cb2`); gemma com `baseline`, `especialista` e `especialista_v2`, sobre a população de `20260908T094808Z-9a00cb2`. Verificar: o manifesto tem o hash novo do catálogo e cada CSV tem o mesmo número de casos `DETECTADO` da rodada de referência.
- [x] 5.3 Rodada **triagem** (`--modo-montagem triagem`): qwen e gemma, cada um com `especialista_direto` e `especialista_direto_v2` (baselines das Rodadas 5 e 6, só agregado), sobre a população das Rodadas 5 e 6. Verificar: o manifesto tem o hash novo e o número de casos por braço bate com o `n` publicado em `docs/ANALISE-RODADA-6.md` (~1.588), com diferença explicada se houver.
- [x] 5.4 Gerar, para cada rodada, a tabela por braço, por CWE, por `Ficha_CWE` e por procedência (na triagem), e o McNemar entre especialista × v2 e baseline × especialista. Verificar: `python -m src.metricas <rodada> --por-cwe --estratificar --mcnemar` roda nas duas rodadas.
- [x] 5.5 Comparar o especialista novo com o antigo: pareado no qwen/filtro (contra `20260908T094808Z-9a00cb2`); nos demais, só contra os agregados de `docs/ANALISE-RODADA-5.md` e `-6.md`, declarando que não é pareado. Registrar em `docs/ANALISE-RODADA-7.md`. Verificar: inspeção do documento, com a origem de cada número indicada.

## 6. Documentação

- [x] 6.1 Atualizar `docs/PIPELINE.md` (precedência regra > CWE > fallback, bloco `regras`, valor `regra` em `Ficha_CWE`, tipos `especialista_v2` e `especialista_direto_v2`) e o protocolo anti-viés (documentação da regra como fonte permitida). Verificar: inspeção contra a implementação.
- [x] 6.2 Atualizar `README.md` e `docs/SCRIPTS.md` com `--prompt especialista_v2`, `--prompt especialista_direto_v2` e `scripts/auditar_regras_ficha.py`. Verificar: os comandos documentados executam como descrito.
- [x] 6.3 Registrar em `docs/MAPA-TCC-O-QUE-REESCREVER.md` o que muda na metodologia e nos resultados da monografia (ficha por regra, rodada nova, limitação da classe positiva nas CWEs corrigidas), sem editar o `.tex`. Verificar: inspeção do arquivo.
- [x] 6.4 Depois das rodadas 5.2 e 5.3, listar quais evidências e trechos do rascunho de resultados (`editaveis/resultados.tex`, `docs/PLANO-ESCRITA-RESULTADOS.md`) dependem de números do especialista e precisam ser refeitos, anotando no mapa de reescrita. Não editar o `.tex` sem perguntar. Verificar: inspeção do mapa, com cada trecho afetado apontado (inclui a Tabela da seção 4b.5f, rodadas 5–6, e os números do `especialista_direto`).
- [x] 6.5 Rodar `ruff check .` e `pytest -q` em estado limpo. Verificar: ambos passam.

## 7. Desfecho da Rodada 7 (2026-09-23)

- [x] 7.1 Opção `--catalogo CAMINHO` no runner, para rodar catálogos diferentes em rodadas separadas; o catálogo por regra salvo em `data/catalogo_cwe_por_regra.json` (mesmos bytes, hash `3d2bc71d…`). Verificar: `--dry-run --catalogo data/catalogo_cwe_por_regra.json` mostra 15 fichas de CWE + 16 de regra.
- [x] 7.2 Depois que o último braço da Rodada 7 terminar, restaurar `data/catalogo_cwe.json` ao catálogo por CWE do commit `a875610` (padrão das Rodadas 1–6). Não antes: um braço que falhe e seja retomado recarregaria o padrão e misturaria catálogos na rodada. Verificar: `sha256sum data/catalogo_cwe.json` = `e5db7d40…` (CRLF) e `pytest -q` passa.

