## Context

Estado medido do repositório na raiz `C:\WS\WS-UnB\tcc-pipeline-neurosimbolica`:

| Item | Situação |
|---|---|
| `git ls-files` | 14 caminhos, dos quais **6 são `.pyc`** — incluindo `src/__pycache__/fase1_codeql.cpython-311.pyc`, bytecode de módulo já apagado |
| Índice | `main.py` e `src/fase1_codeql.py` com deleção preparada (`D `), ainda não commitada |
| `.gitignore` | cobre `__pycache__/`, `.env`, SARIFs, `results/`, `cache_simbolico/`, `repos/`, `codeql/`. **Não** cobre `.pytest_cache/` nem `.ruff_cache/` |
| `scripts/` | 11 scripts; `pilot_funnel.py` sem nenhuma referência fora de si mesmo, `clone_repos.py` autodeclarado legado em `docs/SCRIPTS.md:70`, `ver_modelos.py` (29 linhas) duplicando `diag_gemini.py` (28 linhas) |
| `scripts/semgrep_test/` | 8 arquivos de rascunho (`out.json`, `out.sarif`, `out2.sarif`, `vuln.go`, `multi.go`, `interproc.go`, `rule.yaml`, `rule_cookie.yaml`) |
| `legacy/` | `fase1_codeql.py` + `main_codeql.py` (255 linhas, cópias do que está em `HEAD`), 6 CSVs citáveis, `_runs_antigos/` com 2 CSVs superados |
| `apresentacao/` | 11 MB: `vendor/` (reveal+katex), `apresentacao.pptx` (5,9 MB), `apresentacao-backup.pdf` (2,1 MB), `apresentacao.pdf` (693 KB) |
| Docs | `README.md` 324 linhas + `docs/PIPELINE.md` 499 + `docs/SCRIPTS.md` 347, com sobreposição substancial |
| `src/` | 12 módulos, 1.552 linhas. **Nenhum símbolo público morto** — verificado um a um (`avaliar_vulnerabilidade`, `tabela_para_manifesto`, `secao_contrato`, `TIPOS`, `espera_backoff`, `ler_retry_after`, `nome_funcao`, `classificar_cobertura_semgrep`, `inicializar_relatorio` têm 3+ referências cada) |

O código da pipeline, portanto, já está enxuto. O problema é de **arredores**: bytecode versionado, rascunho, código morto duplicado e documentação em três lugares.

Restrição dominante: nenhum artefato que a pipeline leia ou que a monografia cite pode se mover. Prioridade do projeto é reprodutibilidade acima de elegância.

## Goals / Non-Goals

**Goals:**
- `git ls-files` sem um único `.pyc`.
- `git status --short` limpo de ruído: nada de cache de ferramenta, nada de rascunho.
- Um arquivo de código morto ou órfão a menos, zero referências penduradas para arquivo removido.
- Uma fonte por assunto na documentação.
- Comentário redundante fora, racional metodológico dentro.
- Suíte de testes e `--dry-run` idênticos antes e depois — a limpeza é comprovadamente inerte.

**Non-Goals:**
- Refatorar, renomear ou mudar assinatura em `src/`. Nenhum módulo de fase é reestruturado.
- Tocar em `data/`, `cache/`, `tp_pairs*.json`, `results/`, `legacy/resultados_parte1/*.csv`.
- Tocar em `TCC1___Diego_Sousa_e_João_Artur_Leles/`.
- Mover `tp_pairs*.json` para `data/`. Ganho cosmético contra risco em caminho que já produziu resultados.
- Reduzir dependências. `requests`, `python-dotenv` e `semgrep` são o mínimo já.

## Fases e arquivos tocados

**Fases 0-5: nenhuma alterada em comportamento.** O mapa por diretório:

| Caminho | Ação | Fase |
|---|---|---|
| `.gitignore` | + `.pytest_cache/`, `.ruff_cache/`, `apresentacao/` | — |
| `__pycache__/`, `src/__pycache__/`, `scripts/__pycache__/`, `tests/__pycache__/`, `src/provedores/__pycache__/` | remover do índice e do disco | — |
| `main.py`, `src/fase1_codeql.py` | consolidar deleção já preparada | — |
| `scripts/semgrep_test/` | apagar | 0 |
| `scripts/pilot_funnel.py`, `scripts/clone_repos.py`, `scripts/ver_modelos.py` | apagar | 0 |
| `scripts/osv_harvest_go.py` | remover menções a `clone_repos.py` (linhas 7 e 131) | 0 |
| `legacy/fase1_codeql.py`, `legacy/main_codeql.py`, `legacy/resultados_parte1/_runs_antigos/` | apagar | — |
| `README.md` | reescrever enxuto (≤120 linhas) | — |
| `docs/PIPELINE.md`, `docs/SCRIPTS.md` | remover seções de script apagado; absorver o que só existia no README | — |
| `openspec/config.yaml` | atualizar o `context` onde menciona arquivo removido | — |
| `src/*.py`, `run_pipeline.py`, `scripts/*.py` | passada de comentário redundante | 1-5 |

`src/metricas.py`, `src/fase5_auditoria.py` (esquema do CSV), a numeração de casos e `docs/OPENSPEC.md` não são alterados em conteúdo semântico.

## Decisions

### 1. `git rm --cached` para o bytecode, não só `.gitignore`

`.gitignore` só age sobre arquivo **não rastreado**. Os 6 `.pyc` entraram no commit inicial, então continuam rastreados apesar da regra `__pycache__/` já existir. Só `git rm -r --cached` os tira do índice.

*Alternativa considerada e recusada:* reescrever o histórico com `git filter-repo` para apagar os blobs. São 72 KB, o repo é de TCC com histórico curto e reescrever quebraria os clones existentes e o `git rev-parse HEAD` que o `run_pipeline.py` grava no `run_id` de todo manifesto já produzido. Não vale.

### 2. Código superado vive no histórico, não em `legacy/*.py`

`legacy/fase1_codeql.py` e `legacy/main_codeql.py` são cópias do que o `HEAD` já guarda em `src/fase1_codeql.py` e `main.py`. Manter as duas formas é manter duas verdades. A recuperação fica documentada no `README.md` como `git show HEAD:src/fase1_codeql.py`.

Os CSVs são o oposto: irreprodutíveis (dependiam de execução paga com CodeQL em ambiente que não existe mais) e citados. Ficam, com o `README.md` que explica sob qual configuração cada linha nasceu.

*Alternativa recusada:* apagar `legacy/` inteiro. Quebraria `run_pipeline.py:88` (`LEGADO_PARTE1`) e `--reaproveitar-anteriores`, e o TCC perderia o lastro da PoC no disco.

### 3. `apresentacao/` sai do versionamento, não do disco

Dos 11 MB, 8 MB são `vendor/` (reveal.js + KaTeX vendorizados para funcionar offline) e exports binários que não fazem diff útil. O artefato citável de uma apresentação é o PDF final, entregue por outro canal.

*Trade-off aceito:* a apresentação deixa de ser reproduzível a partir de um clone limpo. Mitigação: `apresentacao/README.md` permanece no disco descrevendo a estrutura, e a entrada no `.gitignore` leva uma nota dizendo explicitamente que o diretório existe localmente e por que foi excluído — para que ninguém conclua no futuro que ele foi perdido.

### 4. README como porta de entrada, `docs/` como referência

A duplicação atual não é redundância inofensiva: já divergiu (contagens de casos e caminhos de saída aparecem com valores diferentes entre `README.md` e `docs/`). Com três cópias, a atualização é sempre parcial, então a informação errada é indistinguível da certa.

Divisão: `README.md` responde "o que é, como instalo, como rodo, onde está cada coisa". `docs/PIPELINE.md` responde "como funciona". `docs/SCRIPTS.md` responde "o que este script faz". Cada frase mora em um só arquivo; o README aponta.

*Alternativa recusada:* fundir tudo no README. Um arquivo de 800 linhas é pior de navegar que três focados, e `openspec/config.yaml` já instrui a manter `docs/` atualizado.

### 5. Critério mecânico para cortar comentário

Um comentário sai se, apagado, nenhuma informação se perde além do que a linha seguinte já diz. Fica se responde "por quê" em vez de "o quê" — e nesse caso é copiado **literalmente**, não reescrito, porque a reescrita é onde o sentido se perde.

Docstring de função pública fica sempre que descreve entrada/saída ou contrato, porque `docs/SCRIPTS.md` a espelha. O cabeçalho de 32 linhas do `run_pipeline.py` fica: é o único lugar onde as 4 trilhas, as 5 fases e a matriz experimental aparecem juntas, e é a primeira coisa que um leitor da banca abre.

### 6. Ordem: apagar antes de reescrever docs

Remoções primeiro, documentação depois. Reescrever `README.md` antes de saber o conjunto final de arquivos garante uma segunda passada. E a checagem de referências penduradas (cenário da spec) só faz sentido contra o disco já podado.

### 7. Verificação por baseline capturado, não por inspeção

Antes de qualquer remoção, capturar `pytest -q` e `run_pipeline.py --tudo --dry-run` em arquivo sob o scratchpad. Ao final, comparar. Igualdade byte-a-byte da população e dos braços é a prova de que a limpeza foi inerte — mais forte que reler os diffs.

## Risks / Trade-offs

- **Apagar arquivo que algo lê em silêncio** → antes de cada remoção, `grep -rn "<nome>" --include=*.py --include=*.md --include=*.yaml .` ignorando `__pycache__`, `.git/` e `.ruff_cache/`. Só remover com zero referências vivas. Já feito para os três scripts: `pilot_funnel` aparece só em si mesmo e em cache de ferramenta; `clone_repos` só em prosa que também será ajustada.
- **Enxugar o README e derrubar informação que só existia lá** → antes de reescrever, diferenciar o README contra `docs/` e mover para `docs/` o que for exclusivo, em vez de apagar direto.
- **Corte de comentário levar embora justificativa metodológica** → o cenário "Decisões de método sobrevivem à limpeza" lista as cinco notas nomeadamente; conferir cada uma pelo nome ao final. Na dúvida sobre um comentário, **mantê-lo**: o custo de uma linha a mais é nulo, o de perder o racional na defesa não é.
- **`apresentacao/` gitignorado ser lido como "diretório perdido"** → nota explicativa na própria entrada do `.gitignore`, no mesmo estilo das notas que o arquivo já usa para `cache_simbolico/` e `tp_pairs*.json`.
- **Deleção acidental de dado irrecuperável** (`cache/`, `tp_pairs*.json`, CSVs da Parte 1) → estão nos não-objetivos e nenhuma tarefa os menciona; `git status` conferido ao final da limpeza deve mostrar zero deleções sob `data/`, `cache/` e `legacy/resultados_parte1/*.csv`.

## Impacto em custo, cota e tempo

**Zero.** Nenhuma tarefa desta mudança chama Gemini, OpenAI ou Semgrep sobre a população real. `run_pipeline.py --dry-run` não faz chamada de rede. Nenhuma dependência nova é introduzida.

## Migration Plan

Sem migração: nenhum consumidor externo, nenhum dado transformado.

Rollback: as remoções de arquivo já rastreado voltam com `git checkout -- <caminho>` antes do commit, ou `git revert` depois. Os arquivos hoje **não rastreados** que serão apagados (`scripts/semgrep_test/`, `scripts/pilot_funnel.py`, `legacy/*.py`, `legacy/resultados_parte1/_runs_antigos/`) não têm rollback pelo Git — `legacy/*.py` é recuperável do `HEAD` pelos caminhos antigos; os demais são rascunho descartável e sua perda é o objetivo.

## Open Questions

Nenhuma. As quatro decisões de escopo (`legacy/`, `apresentacao/`, documentação, agressividade nos comentários) foram resolvidas com o autor antes desta proposta.
