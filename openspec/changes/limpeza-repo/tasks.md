## 1. Baseline de verificação

- [x] 1.1 Capturar o estado atual em arquivos de referência no scratchpad: `python -m pytest tests/ -q > baseline_testes.txt`, `python run_pipeline.py --tudo --dry-run > baseline_dryrun.txt`, `git ls-files > baseline_lsfiles.txt`. Verificar: os três arquivos existem e a suíte passa (nenhum `failed` em `baseline_testes.txt`).
- [x] 1.2 Rodar a varredura de referências para cada candidato à remoção — `pilot_funnel`, `clone_repos`, `ver_modelos`, `semgrep_test`, `fase1_codeql`, `main_codeql`, `_runs_antigos` — com `grep -rn "<nome>" --include=*.py --include=*.md --include=*.yaml --include=*.toml .` ignorando `.git/`, `__pycache__` e `.ruff_cache`. Verificar: registrar num arquivo do scratchpad quais referências são código (bloqueiam) e quais são prosa em `docs/`/`README.md` (serão ajustadas na etapa 5).

## 2. Bytecode e caches fora do controle de versão

- [x] 2.1 Remover os 6 `.pyc` do índice: `git rm -r --cached __pycache__ src/__pycache__`. Verificar: `git ls-files | grep -c pyc` retorna `0`.
- [x] 2.2 Apagar do disco todos os `__pycache__/` (raiz, `src/`, `src/provedores/`, `scripts/`, `tests/`). Verificar: `find . -name __pycache__ -not -path "./.git/*"` não retorna nada.
- [x] 2.3 Acrescentar `.pytest_cache/` e `.ruff_cache/` ao `.gitignore`, na seção de cache. Verificar: `git status --short` não lista nenhum dos dois após rodar `pytest` e `ruff check .`.
- [x] 2.4 Confirmar no índice as deleções já preparadas de `main.py` e `src/fase1_codeql.py`. Verificar: `git status --short` mostra `D` staged para ambos e nenhum deles existe no disco.

## 3. Remoção de rascunho e scripts órfãos

- [x] 3.1 Apagar `scripts/semgrep_test/` inteiro. Verificar: o diretório não existe e `python -m pytest tests/ -q` continua passando.
- [x] 3.2 Apagar `scripts/pilot_funnel.py`, `scripts/clone_repos.py` e `scripts/ver_modelos.py`. Verificar: `ls scripts/*.py` lista exatamente 7 arquivos (`diag_gemini`, `fetch_raso`, `osv_harvest_go`, `preencher_cache`, `ranking_cwe`, `tp_fetch_fixes`, `tp_reconstruct`).
- [x] 3.3 Remover de `scripts/osv_harvest_go.py` as duas menções a `clone_repos.py` (comentário de uso na linha 7 e o `print` de "próximo passo" na linha 131), apontando-as para `fetch_raso.py`. Verificar: `python scripts/osv_harvest_go.py --help` roda sem erro e `grep -rn clone_repos scripts/` não retorna nada.

## 4. Poda de `legacy/` e `apresentacao/`

- [x] 4.1 Apagar `legacy/fase1_codeql.py` e `legacy/main_codeql.py`. Verificar: `git show HEAD:src/fase1_codeql.py | head -5` e `git show HEAD:main.py | head -5` ainda imprimem o código (prova de que a recuperação pelo histórico funciona).
- [x] 4.2 Apagar `legacy/resultados_parte1/_runs_antigos/`. Verificar: os 6 CSVs de `legacy/resultados_parte1/` e o `README.md` continuam presentes e `python src/metricas.py legacy/resultados_parte1/resultados_tcc.csv --por-cwe` roda sem erro.
- [x] 4.3 Acrescentar `apresentacao/` ao `.gitignore` com nota explicando que o diretório existe localmente, que o artefato citável é o PDF e que `vendor/` são bibliotecas vendorizadas sem diff útil. Verificar: `git status --short` e `git ls-files apresentacao/` não retornam nada, e `apresentacao/index.html` continua no disco.

## 5. Documentação: `docs/` como fonte única

- [x] 5.1 Diferenciar `README.md` contra `docs/PIPELINE.md` e `docs/SCRIPTS.md` e mover para `docs/` a informação que hoje só existe no README. Verificar: lista no scratchpad dos trechos exclusivos do README, cada um com o destino em `docs/`.
- [x] 5.2 Remover de `docs/SCRIPTS.md` a seção `scripts/clone_repos.py` e de `docs/PIPELINE.md` a menção a `clone_repos.py` (linha 345). Verificar: `grep -rn "clone_repos\|pilot_funnel\|ver_modelos" docs/` não retorna nada.
- [x] 5.3 Reescrever `README.md` enxuto: propósito, instalação, como rodar, mapa de diretórios com uma linha por item, recuperação do código CodeQL via `git show HEAD:<caminho>`, e ponteiros para `docs/PIPELINE.md`, `docs/SCRIPTS.md` e `docs/OPENSPEC.md`. Verificar: `wc -l README.md` ≤ 120 e nenhuma flag de script individual descrita nele.
- [x] 5.4 Atualizar o bloco `context` de `openspec/config.yaml` onde ele menciona arquivo ou diretório removido. Verificar: `openspec validate limpeza-repo` passa e cada caminho citado no `context` existe no disco.
- [x] 5.5 Resolver as referências penduradas: para cada caminho de arquivo mencionado em `README.md`, `docs/*.md` e em comentário ou `print` sob `src/`, `scripts/` e na raiz, conferir que existe no disco. Verificar: script ou varredura manual registrada no scratchpad com zero caminhos inexistentes.

## 6. Poda de comentários

- [x] 6.1 Passada em `src/*.py` e `src/provedores/*.py` removendo comentário que apenas repete a linha seguinte e docstring que apenas reescreve a assinatura. Verificar: `git diff --stat src/` mostra só remoções, `ruff check src/` limpo e `python -m pytest tests/ -q` passando.
- [x] 6.2 Passada em `run_pipeline.py` e `scripts/*.py` com o mesmo critério, **preservando** o cabeçalho de módulo do `run_pipeline.py`. Verificar: `python run_pipeline.py --help` e `python run_pipeline.py --tudo --dry-run` rodam sem erro.
- [x] 6.3 Conferir nomeadamente a sobrevivência das cinco notas metodológicas: `p/default` vs `p/golang`; `--reaproveitar-anteriores` desligado por padrão; `tp_pairs*.json` fora do `.gitignore`; gabarito por arquivo e não por linha; `baseline` recebendo só o contexto. Verificar: `grep -rn` localiza cada uma das cinco no código ou no `.gitignore`.

## 7. Verificação final

- [ ] 7.1 Comparar contra o baseline da etapa 1: `python -m pytest tests/ -q` e `python run_pipeline.py --tudo --dry-run` devem reproduzir a mesma população e os mesmos braços. Verificar: `diff` do dry-run contra `baseline_dryrun.txt` sem diferença material e a suíte com a mesma contagem de testes passando.
- [ ] 7.2 Conferir que nenhum dado protegido foi tocado: `git status --short` sem deleção sob `data/`, `cache/`, `tp_pairs*.json`, `results/`, `legacy/resultados_parte1/*.csv` ou `TCC1___Diego_Sousa_e_João_Artur_Leles/`. Verificar: `git status --short -- data cache legacy/resultados_parte1 tp_pairs.json tp_pairs_osv.json` sem nenhuma linha começando por `D`.
- [ ] 7.3 Commitar a limpeza em português, listando o que saiu do índice e o que saiu do disco. Verificar: `git ls-files | grep -c pyc` retorna `0` no commit e `git status --short` mostra apenas os arquivos que o autor deliberadamente deixa untracked.
