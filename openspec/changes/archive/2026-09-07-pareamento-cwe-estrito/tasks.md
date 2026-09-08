## 1. Fase 1 — regra de pareamento

- [x] 1.1 Trocar o casamento por substring de `_cwe_nas_tags` por comparação de identificador completo de CWE (D2), reconhecendo `CWE-<dígitos>` na tag e comparando o número. Verificar: `python -c "from src.fase1_semgrep import _cwe_nas_tags; print(_cwe_nas_tags(['CWE-770: Allocation'],'CWE-77'), _cwe_nas_tags(['CWE-77: Command Injection'],'CWE-77'))"` imprime `False True`.
- [x] 1.2 Remover o fallback de alerta único (`src/fase1_semgrep.py:107-110`), substituindo o comentário por uma nota que registre por que ele existia e por que saiu, nos termos da decisão D1. Verificar: `grep -n "len(results) == 1" src/fase1_semgrep.py` não retorna nada.
- [x] 1.3 Ordenar os alertas candidatos por `(linha inicial, check_id)` antes de escolher o casado (D6). Verificar: teste da tarefa 1.6 que embaralha a ordem dos `results` do SARIF e obtém sempre o mesmo alerta.
- [x] 1.4 Trocar o retorno de `executar_semgrep` pela `NamedTuple` `ResultadoFase1(alerta, motivo, regras_nao_casadas)` (D5), com `motivo` em `SEM_ALERTA | ALERTA_OUTRA_CWE | N/A` e `regras_nao_casadas` como lista de `check_id` deduplicada e ordenada alfabeticamente. Verificar: `python -m pytest tests/test_smoke.py -q` passa.
- [x] 1.5 Adicionar a constante `VERSAO_PAREAMENTO` em `src/fase1_semgrep.py`, com comentário dizendo que subi-la invalida o cache simbólico. Verificar: `python -c "from src.fase1_semgrep import VERSAO_PAREAMENTO; print(VERSAO_PAREAMENTO)"`.
- [x] 1.6 Escrever os testes de emparelhamento sobre SARIF sintético: arquivo com 1 alerta de CWE diferente (não emparelha, motivo `ALERTA_OUTRA_CWE`), 1 alerta de CWE casada (emparelha), N alertas com um casado (emparelha o certo), N alertas sem nenhum casado, arquivo sem alerta algum (motivo `SEM_ALERTA`), regra sem tag de CWE (não emparelha), e prefixo de CWE (`CWE-77` contra regra `CWE-770`, não emparelha). Verificar: `python -m pytest tests/ -q -k pareamento` passa.
- [x] 1.7 Tratar saída inválida do Semgrep (stdout vazio, JSON ilegível, JSON sem `runs`) como `SemgrepError` em vez de `SEM_ALERTA`. Fora do plano original: um `settings.yml` corrompido por queda de energia fez o Semgrep sair com `rc=1` e stdout vazio, e o `or "{}"` transformou isso em 200 não-detecções falsas já gravadas no cache. Verificar: `python -m pytest tests/ -q -k pareamento` passa, incluindo o contraponto de que SARIF bem formado com zero achados continua sendo `SEM_ALERTA`.

## 2. Cache simbólico

- [x] 2.1 Subir `VERSAO_FORMATO` para 2 e adicionar `versao_pareamento` ao payload gravado por `CacheSimbolico.gravar`, junto dos campos `motivo` e `regras_nao_casadas` (D4). Verificar: inspeção de um JSON recém-gravado num diretório temporário mostra as chaves novas.
- [x] 2.2 Fazer `CacheSimbolico.ler` recusar entrada cuja `versao_pareamento` divirja da corrente, inclusive quando o campo está ausente. Verificar: teste da tarefa 2.3.
- [x] 2.3 Cobrir em `tests/test_cache_simbolico.py`: entrada gravada sob `versao_pareamento` anterior é ignorada; entrada sem o campo é ignorada; entrada ignorada permanece em disco; motivo e regras sobrevivem à ida e volta pelo cache. Verificar: `python -m pytest tests/test_cache_simbolico.py -q` passa.

## 3. Propagação e auditoria

- [x] 3.1 Adaptar `resolver_simbolico` em `run_pipeline.py` para consumir a `ResultadoFase1`, propagar motivo e regras, e gravá-los no cache. Verificar: `python -m pytest tests/test_cache_simbolico.py -q` continua passando sem alteração dos testes que acessam a tupla por índice.
- [x] 3.2 Acrescentar `Motivo_Nao_Deteccao` e `Regras_Nao_Casadas` ao fim de `CABECALHO` em `src/fase5_auditoria.py` e preenchê-las em `registrar_resultado`, com `N/A` e vazio quando o caso foi detectado (D3). Verificar: `python -c "from src.fase5_auditoria import CABECALHO, COLUNAS_PARTE2; print(CABECALHO[-2:]); print(len(COLUNAS_PARTE2))"` mostra as duas colunas no fim e a fatia da Parte 2 ainda coerente.
- [x] 3.3 Repassar motivo e regras de `processar_caso` até `_registrar`, garantindo que `Status_Semgrep` continue `NAO_DETECTADO` nos dois motivos. Verificar: `python -m pytest tests/test_matriz.py -q` passa.
- [x] 3.4 Confirmar que o checkpoint por tripla continua tratando os dois motivos como caso resolvido. Verificar: teste em `tests/test_matriz.py` com linha `NAO_DETECTADO` + `ALERTA_OUTRA_CWE` que não é reexecutada.

## 4. Métricas

- [x] 4.1 Discriminar a não-detecção por motivo no bloco de cobertura simbólica de `src/metricas.py`, contando cada caso uma vez só entre braços e tolerando CSV sem a coluna. Verificar: `python src/metricas.py results/20260730T180648Z-14d6af8` roda sem erro e reporta motivo indisponível para aquela rodada.
- [x] 4.2 Cobrir em `tests/test_metricas.py`: contagem por motivo, soma dos motivos igual ao total de `NAO_DETECTADO`, e CSV legado sem a coluna. Verificar: `python -m pytest tests/test_metricas.py -q` passa.

## 5. Documentação

- [x] 5.1 Atualizar `docs/PIPELINE.md`: regra de pareamento da Fase 1, taxonomia de não-detecção e as duas colunas novas do CSV. Verificar: `grep -n "ALERTA_OUTRA_CWE" docs/PIPELINE.md` retorna as ocorrências.
- [x] 5.2 Atualizar `docs/SCRIPTS.md`: contrato de `executar_semgrep` (hoje descrito como "ou `None` (NAO_DETECTADO)", linha 186) e payload do cache simbólico (linha 217). Verificar: `grep -n "ResultadoFase1\|versao_pareamento" docs/SCRIPTS.md` retorna as ocorrências.
- [x] 5.3 Verificar se `README.md` descreve o status da Fase 1 ou as colunas do CSV e atualizar se descrever. Verificar: `grep -n "NAO_DETECTADO" README.md` — se vazio, a tarefa se encerra sem alteração.

## 6. Medição do efeito

- [x] 6.1 Rodar a suíte inteira antes de tocar em qualquer rodada. Verificar: `python -m pytest tests/ -q` passa integralmente.
- [x] 6.2 Medir, com o cache antigo ainda em disco, quantos casos hoje `DETECTADO` deixam de emparelhar sob a regra nova, separando os que caem por fallback dos que caem por prefixo de CWE. Verificar: script de medição em `scripts/` (ou execução pontual registrada) produz as duas contagens, que entram no relatório da rodada.

## 7. Re-execução do braço local

- [x] 7.1 Re-executar as Fases 1 e 2 sobre os 948 casos com o cache simbólico invalidado, sob `run_id` novo. Verificar: contagem de `DETECTADO` / `NAO_DETECTADO` da nova varredura registrada, e os dois motivos presentes no CSV. (Varredura completa do Semgrep — é o custo de parede dominante.) Resultado em `run_id 20260731T140000Z-af9bc32`: 791 `DETECTADO` / 157 `NAO_DETECTADO` (especialista), com os dois motivos no CSV — `SEM_ALERTA` 118, `ALERTA_OUTRA_CWE` 39.
- [x] 7.2 Re-executar o braço local (`qwen2.5-coder-7b`, baseline e especialista) sobre a população nova. Verificar: `results/<run_id_novo>/manifesto.json` gravado e os CSVs dos dois braços completos. (~2h50, custo e cota zero.) Manifesto gravado; 948 linhas por braço, 0 IDs duplicados. A execução foi interrompida e retomada várias vezes (queda de energia, suspensão da máquina, processo morto por limite de tempo); o checkpoint por tripla absorveu todas — por isso a duração do manifesto é a da última retomada, não da rodada.
- [x] 7.3 Recalcular as métricas da rodada nova e registrar o movimento nas duas classes em relação a `results/20260730T180648Z-14d6af8`, incluindo a variação de TRA e de proporção de FP filtrados. Verificar: `python src/metricas.py results/<run_id_novo> --mcnemar` executa e a comparação entre as duas rodadas fica registrada. Registrado em `docs/ANALISE-RODADA-2.md`. Classe positiva: Semgrep VP 13 → 1 (12 dos 13 eram artefato do fallback, como a Rodada 1 previu); classe negativa: FP 792 → 788, VN 46 → 51. TRA simbólico 0,1481 → 0,1660; prop. FP filtrados 0,0549 → 0,0608; TRA do especialista 0,9851 → 0,9874. McNemar idêntico nas duas rodadas (só especialista acerta = 100, só baseline = 0, p < 0,0001).
- [x] 7.4 Confirmar que `results/20260730T180648Z-14d6af8` permanece intacta em disco. Verificar: `git status` e listagem do diretório mostram a rodada anterior preservada. Conferido: 948 linhas por braço, 0 IDs duplicados, mtime 30/jul 17:57, `manifesto.json` presente (baseline 805 DETECTADO / 140 NAO_DETECTADO / 3 API_ERROR; especialista 808 / 140 / 0). Ressalva sobre o critério: `results/` está no `.gitignore` (linha 38), então `git status` não observa esse diretório — a evidência é o mtime e a contagem, não o git.
