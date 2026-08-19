## Why

O repositório acumulou lixo que não pertence ao controle de versão nem ao TCC: seis `.pyc` **versionados** (inclusive de módulos já apagados, como `src/fase1_codeql.py`), diretórios de rascunho, scripts órfãos, 8 MB de binários duplicados na apresentação e documentação triplicada entre `README.md` e `docs/`. Nada disso é lido pela pipeline, mas tudo isso é lido por quem tenta entender o projeto — e a banca vai olhar este repositório.

Esta mudança é **infraestrutura**: não atende a nenhuma pergunta de pesquisa do TCC e não altera nenhum número. O critério de corte é "o que a pipeline lê, o que o TCC cita, ou o que reproduz a execução". O resto sai.

## What Changes

**Artefatos versionados por engano**
- Remover do índice do Git os 6 `.pyc` rastreados (`__pycache__/main.cpython-311.pyc`, `src/__pycache__/*.cpython-311.pyc`) — herdados do commit inicial e imunes ao `.gitignore`, que só ignora arquivos ainda não rastreados.
- Consolidar no índice as deleções já preparadas (`main.py`, `src/fase1_codeql.py`), substituídas por `run_pipeline.py` e `src/fase1_semgrep.py`.

**Diretórios de rascunho e caches locais**
- Apagar `scripts/semgrep_test/` (experimento manual de regra Semgrep: `out.json`, `out.sarif`, `out2.sarif`, `vuln.go`, `multi.go`, `interproc.go`, `rule*.yaml`) — nenhum arquivo é lido por código algum.
- Apagar `__pycache__/`, `src/__pycache__/`, `scripts/__pycache__/`, `tests/__pycache__/`, `src/provedores/__pycache__/` do disco.
- Adicionar `.pytest_cache/` e `.ruff_cache/` ao `.gitignore` (hoje ficam de fora e aparecem como untracked).

**Scripts órfãos**
- Apagar `scripts/pilot_funnel.py` (172 linhas): sondagem descartável do funil, sem nenhuma referência em código, `docs/` ou `README.md`. O diagnóstico que ela produziu já está registrado na proposta arquivada `2026-07-29-experimento-parte2`.
- Apagar `scripts/clone_repos.py` (81 linhas): a própria `docs/SCRIPTS.md` o declara legado, substituído por `fetch_raso.py`, "mantido apenas como referência".
- Apagar `scripts/ver_modelos.py` (29 linhas): duplica `scripts/diag_gemini.py`. Manter apenas `diag_gemini.py`.
- Remover as menções a `clone_repos.py` em `scripts/osv_harvest_go.py` (comentário de uso e `print` final), que passariam a apontar para arquivo inexistente.

**`legacy/`**
- Apagar `legacy/fase1_codeql.py` e `legacy/main_codeql.py`: recuperáveis por `git show HEAD:src/fase1_codeql.py` e `git show HEAD:main.py`. O histórico já é o arquivo morto.
- Apagar `legacy/resultados_parte1/_runs_antigos/` (duas rodadas antigas superadas pelos CSVs do diretório-pai).
- **Manter** `legacy/resultados_parte1/*.csv` e seu `README.md`: `src/metricas.py` os lê, `run_pipeline.py --reaproveitar-anteriores` os referencia e o TCC cita os números da PoC.

**`apresentacao/`**
- Deixar de versionar `apresentacao/` inteiro (11 MB, dos quais 8 MB são `vendor/` reveal+katex e exports binários). Os arquivos permanecem no disco; entram no `.gitignore` com nota explicando que o artefato citável é o PDF.

**Documentação — `docs/` como fonte única**
- Enxugar `README.md` (324 → ~100 linhas): propósito, instalação, como rodar, mapa de diretórios em uma linha por item, ponteiros para `docs/`.
- Manter `docs/PIPELINE.md` (arquitetura e trilhas) e `docs/SCRIPTS.md` (referência de módulos/scripts) como o detalhe canônico, ajustados para os arquivos removidos.
- A duplicação atual já divergiu em pontos (contagem de casos, caminhos de saída); a fonte única elimina a classe do problema.

**Comentários e docstrings**
- Remover comentário que apenas reescreve o código e docstring que apenas repete a assinatura.
- **Preservar** toda nota que registra decisão de método (por que `p/default` e não `p/golang`; por que `--reaproveitar-anteriores` é desligado por padrão; por que `tp_pairs*.json` não é gitignorado; por que o gabarito é por arquivo). É esse racional que sustenta as escolhas na defesa.
- O cabeçalho de 32 linhas do `run_pipeline.py` fica: é o único mapa das trilhas e das fases em um só lugar.

## Capabilities

### New Capabilities
- `higiene-repositorio`: define o que entra no controle de versão (código, dados de entrada, gabaritos, documentação, CSVs citados) contra o que é derivado ou descartável (caches, `__pycache__`, SARIFs, rodadas, binários de apresentação), e fixa `docs/` como fonte única da documentação de detalhe, com o `README.md` restrito a orientação inicial.

### Modified Capabilities
*(nenhuma — as sete specs existentes descrevem comportamento da pipeline, que não muda)*

## Não-objetivos

- **Não mexer em `TCC1___Diego_Sousa_e_João_Artur_Leles/`.** A monografia LaTeX fica intocada; em particular, nenhum TODO ou nota de autor sai de arquivo `.tex`.
- **Não apagar `cache/`** (16 MB, chave imutável): é o que permite rodar a pipeline offline sem os ~70 repos.
- **Não apagar `tp_pairs.json` / `tp_pairs_osv.json` nem movê-los da raiz.** São gabaritos de entrada irrecuperáveis sem o histórico git completo, que não está mais no disco; mover exigiria tocar em código que já produziu resultados, sem ganho real.
- **Não refatorar código, renomear módulo, alterar assinatura nem mexer em `src/metricas.py`, na numeração de casos ou no esquema do CSV.** Limpeza não altera comportamento.
- **Não remover dependência de `requirements.txt` / `pyproject.toml`** — já são mínimas.
- **Não apagar `openspec/changes/archive/`**: é o registro de decisões do projeto.

## Impact

- **Resultados publicados: nenhum invalidado.** Nada em `data/`, `cache/`, `tp_pairs*.json`, `results/` ou `legacy/resultados_parte1/*.csv` é alterado ou removido. Nenhum CSV fica obsoleto e nenhuma rodada precisa ser re-executada.
- **Código:** `scripts/osv_harvest_go.py` (só menções a script removido). Nenhum arquivo de `src/` ou `run_pipeline.py` muda de comportamento — apenas comentários redundantes.
- **Testes:** os 10 arquivos de `tests/` continuam válidos; `tests/test_matriz.py` já cria seu próprio `legacy/resultados_parte1` em `tmp_path`, então não depende do diretório real. A suíte inteira deve passar antes e depois.
- **Documentação:** `README.md` encurtado; `docs/PIPELINE.md` e `docs/SCRIPTS.md` ajustados. `docs/OPENSPEC.md` inalterado.
- **Configuração:** `.gitignore` ganha `.pytest_cache/`, `.ruff_cache/` e `apresentacao/`. `openspec/config.yaml` precisa de ajuste na menção a `clone_repos.py`/`legacy/` se ficar desatualizada.
- **Fases 0-5:** nenhuma alterada.
- **Custo/cota de LLM:** zero. Nenhuma tarefa desta mudança chama API.
- **Disco/repo:** ~11 MB saem do versionamento (apresentação) e ~500 KB de rascunho e código morto saem do disco.
