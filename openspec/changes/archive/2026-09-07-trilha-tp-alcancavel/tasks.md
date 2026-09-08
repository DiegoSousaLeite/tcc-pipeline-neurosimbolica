## 1. Trilha na pipeline

- [x] 1.1 Acrescentar `TP_alcancavel` a `TRILHAS` (`run_pipeline.py:288`) e a constante com o caminho do pool da colheita filtrada, ao lado de `TP_PAIRS_OURO` e `TP_PAIRS_PRATA`. Verificar: `python -c "import run_pipeline; print(run_pipeline.TRILHAS)"` inclui a trilha nova.
- [x] 1.2 Somar a trilha à montagem da população (`run_pipeline.py:952-953`) via `construir_casos_tp`, com rótulo de origem próprio (D1). Verificar: `python run_pipeline.py --trilha TP_alcancavel --dry-run` executa sem erro.
- [x] 1.3 Confirmar que a trilha com pool ausente devolve zero casos sem quebrar a montagem, e que a contagem aparece no cabeçalho da execução — trilha vazia não pode passar despercebida. Verificar: com o pool ausente, `python run_pipeline.py --tudo --dry-run` roda e reporta 0 casos na trilha nova.
- [x] 1.4 Atualizar o cabeçalho de documentação de `run_pipeline.py` (linhas 7-9), que descreve as trilhas, incluindo a nova e a origem dela. Verificar: `grep -n "TP_alcancavel" run_pipeline.py` retorna a linha do cabeçalho.

## 2. Integridade da população

- [x] 2.1 Verificar que nenhum identificador de caso colide entre as cinco trilhas. Verificar: script que monta a população inteira e reporta 0 IDs duplicados.
- [x] 2.2 Verificar que os identificadores da classe negativa não mudaram — o índice do ID vem da posição original na lista de locations, e renumerar quebraria os CSVs já gerados e o checkpoint. Verificar: os IDs de origem `FP` da população montada são idênticos aos do CSV de `results/20260731T140000Z-af9bc32`.
- [x] 2.3 Confirmar que as trilhas `TP_ouro`, `TP_prata` e `TP_dataset` continuam produzindo exatamente os mesmos casos de antes, incluindo os de CWE inalcançável (D3). Verificar: contagens por trilha iguais a 32, 68 e 57.
- [x] 2.4 Confirmar que os 17 pares já alcançáveis dos pools antigos NÃO são recarregados pela trilha nova, o que criaria duplicata e destruiria a rastreabilidade por procedência (D4). Verificar: nenhum ID aparece em duas trilhas.

## 3. Testes

- [x] 3.1 Escrever testes de composição da população em `tests/`: trilha nova com pool sintético entra com o rótulo próprio; pool ausente não quebra; classe negativa mantém os mesmos IDs; nenhum ID duplicado na população inteira. Verificar: `python -m pytest tests/ -q -k populacao` passa.
- [x] 3.2 Cobrir que um caso vulnerável de CWE inalcançável continua entrando na população e é classificado como ponto cego na matriz de cobertura, ficando fora da matriz de acerto do LLM (D3). Verificar: `python -m pytest tests/ -q -k "populacao or matriz"` passa.
- [x] 3.3 Rodar a suíte inteira. Verificar: `python -m pytest tests/ -q` passa integralmente.

## 4. Documentação

- [x] 4.1 Atualizar `docs/PIPELINE.md`: a trilha `TP_alcancavel` na composição da população, por que ela é trilha própria em vez de sobrescrever o pool da `TP_prata`, e por que os casos de CWE inalcançável permanecem. Verificar: `grep -n "TP_alcancavel" docs/PIPELINE.md` retorna as ocorrências.
- [x] 4.2 Verificar se `README.md` descreve as trilhas ou a composição da população e atualizar se descrever. Verificar: `grep -n "TP_prata\|TP_ouro\|trilha" README.md` — se vazio, a tarefa se encerra sem alteração.
