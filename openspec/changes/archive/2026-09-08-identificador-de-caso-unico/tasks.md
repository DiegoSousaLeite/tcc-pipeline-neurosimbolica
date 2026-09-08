## 1. Provar o defeito antes de corrigir

- [x] 1.1 Escrever teste que monta um pool com pares de mesmo repo/CWE/função e arquivos distintos e exige identificadores distintos. Verificar: o teste FALHA na árvore atual, pelo motivo certo (identificador repetido, não erro de montagem do teste).
  - `test_pares_em_arquivos_distintos_nao_colidem` falhou com `assert 6 == 2`: 3 pares em `commit.go`/`tag.go`/`tree.go` produziam `TPA:servico:CWE-327:Handler:vuln` e `…:fix` e mais nada.
- [x] 1.2 Escrever teste que exige que a montagem aborte, nomeando os repetidos, quando houver identificador duplicado. Verificar: falha na árvore atual.
  - `test_montagem_aborta_com_identificador_repetido` e `test_populacao_sem_duplicados_passa_pela_guarda` falharam por `AttributeError` — não existia guarda alguma.
- [x] 1.3 Escrever teste que congela os identificadores de `TP_ouro` e `TP_prata` contra os gravados nos CSVs de `results/20260731T140000Z-af9bc32`. Verificar: PASSA na árvore atual — é a rede de proteção, não pode nascer vermelha.
  - `test_ids_das_trilhas_ja_executadas_sao_os_dos_csvs` nasceu verde, comparando os IDs derivados dos pools contra os gravados nos CSVs da rodada de referência. Continua verde depois da mudança.
- [x] 1.4 Confirmar que nenhum CSV existente contém identificador com o prefixo da trilha nova, o que autoriza mudar o esquema dela sem invalidar checkpoint. Verificar: a contagem é 0 e fica registrada nesta tarefa.
  - **0 CSVs em `results/` contêm identificador com prefixo `TPA:`, e 0 linhas.** A trilha nunca foi executada, então mudar o esquema dela não invalida checkpoint nem torna rodada alguma irretomável.

## 2. Corrigir o esquema de identificador

- [x] 2.1 Acrescentar a `construir_casos_tp` um discriminador derivado do caminho do arquivo (D1, D2), aplicado somente quando o pool é carregado sob prefixo próprio (D3). Verificar: os testes 1.1 e 1.3 passam.
  - `base_id` ganha `:{sha256(arquivo)[:8]}` quando `prefixo_id` é não-vazio. Ex.: `TPA:go-git:CWE-345:Decode:29b4659e:vuln`.
  - `TP_ouro` e `TP_prata` continuam sem discriminador, e o teste 1.3 confirma que seus IDs são os dos CSVs.
- [x] 2.2 Fazer a montagem da população abortar com identificador repetido, nomeando os repetidos e a trilha (D4). Verificar: o teste 1.2 passa.
  - `IdentificadorDuplicadoError` + `verificar_ids_unicos(casos)`, chamada em `main` depois do filtro de trilha e antes de `--amostra`, varredura ou LLM. A mensagem traz quantidade, casos envolvidos e até 5 IDs com as trilhas de cada um.
- [x] 2.3 Conferir a população real montada com o pool da colheita filtrada. Verificar: 1462 casos, 0 identificadores duplicados, contagem por trilha inalterada (FP=791, TP_ouro=32, TP_prata=68, TP_dataset=57, TP_alcancavel=514).
  - **1462 casos, 1462 IDs distintos, 0 duplicados.** Contagem por trilha exatamente a esperada; por gabarito, 1098 seguros e 364 vulneráveis. `verificar_ids_unicos` retorna `None` sobre a população real.

## 3. Fechar a lacuna de cache

- [x] 3.1 Incluir `TP_PAIRS_ALCANCAVEL` em `casos_unicos()` de `scripts/preencher_cache.py`, com o mesmo prefixo de identificador que a pipeline usa. Verificar: `python scripts/preencher_cache.py --dry-run` reporta os alvos das quatro trilhas e 0 faltando.
  - **1112 alvos distintos, 0 faltando** (eram 766 sem a trilha nova). O salto de 346 é a trilha nova menos os 14 alvos que ela já compartilhava com as demais.
- [x] 3.2 Escrever teste que exige a trilha nova no conjunto de alvos do preenchimento de cache. Verificar: o teste falha antes de 3.1 e passa depois.
  - `test_preenchimento_de_cache_cobre_a_trilha_nova` neutraliza os pools antigos e exige que o arquivo do pool novo apareça em `casos_unicos()`. Vermelho antes, verde depois.

## 4. Verificação

- [x] 4.1 Rodar a suíte inteira. Verificar: `python -m pytest tests/ -q` passa integralmente, sem teste novo ficando para trás.
  - **284 testes passam** (eram 278; 6 novos). `ruff check` limpo em `run_pipeline.py`, `scripts/preencher_cache.py` e `tests/test_populacao.py`.
- [x] 4.2 Confirmar que nenhuma rodada em `results/` foi tocada e que nenhum arquivo `.tex` foi alterado. Verificar: mtime das rodadas inalterado e `git status -- "*.tex"` vazio.
  - `20260731T140000Z-af9bc32` e `20260730T180648Z-14d6af8` com mtime idêntico ao do início da sessão. `git status -- "*.tex"` vazio.
