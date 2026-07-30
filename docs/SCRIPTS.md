# Referência de Scripts e Módulos

## Fase 0 — Preparação de Dados TP (`scripts/`)

Estes scripts são executados **uma única vez** antes da pipeline principal.
Produzem os manifestos de fix commits e os pares vuln/corrigido.

### `scripts/osv_harvest_go.py`

**Propósito:** Coleta CVEs do ecossistema Go na OSV.dev e gera o manifesto
de fix commits para a trilha prata.

**Entradas:** API pública `api.osv.dev`

**Saídas:** `data/tp_fixes_osv.json` — lista de CVEs com `fix_commit` e `repo_url`.

**Uso:**
```bash
python scripts/osv_harvest_go.py
```

---

### `scripts/tp_fetch_fixes.py`

**Propósito:** Preenche automaticamente o campo `fix_commit` de cada entrada
em `data/tp_fixes.json` (trilha ouro) consultando a OSV.dev. Não sobrescreve
commits já preenchidos manualmente. É idempotente.

**Entradas:** `data/tp_fixes.json` (esqueleto), API `api.osv.dev`

**Saídas:** `data/tp_fixes.json` (atualizado in-place)

**Uso:**
```bash
python scripts/tp_fetch_fixes.py
python scripts/tp_fetch_fixes.py --selftest   # valida lógica sem rede
```

---

### `scripts/fetch_raso.py`

**Propósito:** Baixa só os commits que o `tp_reconstruct.py` precisa. Para cada
repo cria um esqueleto git (`init` + `remote add`) e roda
`git fetch --depth 2 origin <fix_commit>` — profundidade 2 traz o commit do fix
e o pai dele, que é exatamente o par necessário. Não faz checkout: a working
tree fica vazia, e o `tp_reconstruct` lê tudo do object database.

**Entradas:** `data/tp_fixes_osv.json` ou arquivo passado via `--input`

**Saídas:** esqueletos git em `repos/<repo_dir>/` (~3 GB para os 70 repos da
trilha prata, contra dezenas de GB de clone completo)

**Uso:**
```bash
python scripts/fetch_raso.py --input data/tp_fixes_osv.json
python scripts/fetch_raso.py --input data/tp_fixes_osv.json --dry-run
```

Idempotente: commit já presente é pulado, então dá para reexecutar depois de uma
interrupção. Timeout de 300 s por fetch vira falha comum, para que um repo lento
não derrube a coleta. Se aparecer `Unable to create ... shallow.lock`, é lock
órfão de uma execução morta — apague o `.lock` e rode de novo.

Depois de `tp_reconstruct.py` + `preencher_cache.py`, `repos/` pode ser apagado.

---

### `scripts/tp_reconstruct.py`

**Propósito:** Para cada CVE com `fix_commit`, extrai a função alterada pelo
fix em duas versões (vulnerável = commit-pai; corrigida = commit do fix) e
grava os pares como JSON. Opcionalmente roda o Semgrep no estado vulnerável.

**Entradas:** `data/tp_fixes.json` (ou `--input`), histórico git em `repos/`
(basta o fetch raso do `fetch_raso.py`)

**Saídas:** `tp_pairs.json` (trilha ouro) ou `tp_pairs_<sufixo>.json` (prata)

**Descartes:** funções de teste (`_test.go`), funções inalteradas pelo fix,
extrações por janela (sem delimitação confiável de função), funções não nomeadas
pelo dataset e CVEs cujo advisory não traz CWE — sem tag de CWE a Fase 1 não tem
como casar o alerta. Há ainda um guarda anti-refatoração: CVE que toca mais de 8
funções sem que o dataset diga quais é descartado inteiro.

**Uso:**
```bash
# Pares sem SAST:
python scripts/tp_reconstruct.py
python scripts/tp_reconstruct.py --input data/tp_fixes_osv.json

# Com validação Semgrep (registra se passou no SAST):
python scripts/tp_reconstruct.py --sast --sast-config p/golang

# Gerar esqueleto inicial a preencher:
python scripts/tp_reconstruct.py --init
```

---

### `scripts/diag_gemini.py`

**Propósito:** Lista modelos Gemini disponíveis e compatíveis com a chave
`GEMINI_API_KEY` configurada no `.env`. Útil para diagnosticar a conexão.

**Entradas:** `.env` com `GEMINI_API_KEY`

**Uso:**
```bash
python scripts/diag_gemini.py
```

---

## Pipeline Principal (`src/`)

### `src/config.py`

Carrega variáveis de ambiente e define paths globais (`DATASET_PATH`,
`REPORT_PATH`, `REPOS_DIR`, `CACHE_DIR`, `CACHE_SIMBOLICO_DIR`,
`CATALOGO_CWE_PATH`, `PROMPTS_DIR`, `RESULTS_DIR`).

Não monta URL de API: a chave vai em header, nos provedores.

**Variáveis lidas do ambiente ou do `.env` da raiz:**

| Variável | Padrão | Descrição |
|---|---|---|
| `GEMINI_API_KEY` | — | Obrigatória para os braços Gemini |
| `OPENAI_API_KEY` | — | Obrigatória para os braços GPT |
| `LLM_MODEL_VERSION` | `gemini-2.5-flash-lite` | Modelo do braço padrão (o tier grátis do 2.5-flash é só 20 req/dia) |
| `PROMPT_TYPE` | `especialista` | Tipo de prompt do braço padrão |
| `SEMGREP_BIN` | path padrão Windows | Executável do Semgrep |
| `SEMGREP_CONFIG` | `p/default` | Ruleset do Semgrep (entra no cache simbólico e no manifesto) |
| `SEMGREP_TIMEOUT` | `240` | Timeout do Semgrep, em segundos |
| `GEMINI_MIN_INTERVALO` | `7` | Intervalo mín. entre chamadas ao Gemini (s); 0 desativa |
| `OPENAI_MIN_INTERVALO` | `0` | Idem para a OpenAI |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Endpoint alternativo (proxy/compatível) |
| `GITHUB_TOKEN` | — | Opcional; eleva o limite de requisições ao baixar arquivos-alvo |
| `FETCH_TIMEOUT` | `30` | Timeout (s) do download do arquivo-alvo |

---

### `src/hidratacao.py`

Utilitários compartilhados de extração de código Go:

- `extrai_funcao(linhas, alvo_idx)` — extrai a função que contém a linha alvo
  (balanceamento de chaves; fallback: janela ±25).
- `nome_funcao(codigo)` — extrai o nome da função Go da assinatura.

Importado por `fase2_middleware.py` e `scripts/tp_reconstruct.py`.

---

### `src/fase1_semgrep.py`

**Propósito:** Roda `semgrep --config p/default --sarif --quiet` sobre o arquivo
já resolvido por `src/fonte.py` — não clona nem faz checkout. Devolve o alerta
cuja CWE casa com a do dataset, ou `None` (NAO_DETECTADO).

**Entrada:** `(caminho_arquivo, cwe)`

**Saída:** dict do alerta Semgrep com `start.line`, `check_id`, `extra.message`

**Exceções:** `SemgrepFileNotFoundError`, `SemgrepTimeoutError`, `SemgrepError`

---

### `src/fase2_middleware.py`

**Propósito:** Dado o alerta Semgrep e o caminho absoluto do arquivo, lê o
arquivo e extrai o contexto (função ao redor da linha do alerta). Retorna
string formatada para o LLM.

**Entrada:** `(alerta: dict, caminho_arquivo: str)`

**Saída:** string com header do alerta + código da função relevante

---

### `src/cache_simbolico.py`

**Propósito:** Persiste o resultado das Fases 1 e 2 por caso, para que os braços
da matriz não reexecutem o Semgrep e vejam contexto byte-a-byte idêntico.

**Chave:** `(repo, commit, arquivo, cwe)` →
`cache_simbolico/<owner>__<repo>/<commit>/<hash>__<cwe>.json`

**Payload:** `{versao_formato, versao_ruleset, status_semgrep, alerta,
contexto_hidratado, ...}`. `NAO_DETECTADO` também é gravado.

**Invalidação:** divergência de `versao_ruleset` ou de `versao_formato` faz a
entrada ser ignorada (não apagada). Nada sob `cache/` é tocado.

---

### `src/catalogo.py`

**Propósito:** Carrega e valida `data/catalogo_cwe.json`, resolve CWE sem ficha
para `__fallback__` e calcula o SHA-256 dos bytes do arquivo.

**API:** `Catalogo.carregar(caminho)`, `.ficha(cwe, cwe_name)` → `Ficha`
(com `.origem ∈ {especifica, fallback}`), `.sha256`, `.cwes_especificas`.

**Exceção:** `CatalogoInvalido` quando falta o fallback, um campo obrigatório
está vazio ou o JSON é inválido.

---

### `src/prompts.py`

**Propósito:** Renderiza `prompts/*.md` por `str.format` com placeholders
nomeados e calcula a versão (hash curto) de cada template.

**API:** `montar_prompt(tipo, contexto, cwe_id, cwe_name, description, ficha)`,
`versao_prompt(tipo)` → `especialista:d1145f8b`, `secao_contrato(tipo)`.

O `baseline` recebe **só** o contexto — nem o identificador da CWE. É a condição
de controle: qualquer camada da metodologia que vaze para ele mata o contraste.

---

### `src/provedores/`

| Arquivo | Conteúdo |
|---|---|
| `base.py` | `RespostaLLM`, protocolo `ProvedorLLM`, `ProvedorHTTP` (throttle, retry, validação), `validar_resposta`, `espera_backoff`, `ler_retry_after` |
| `gemini.py` | `ProvedorGemini` — REST `generateContent`, header `x-goog-api-key` |
| `openai.py` | `ProvedorOpenAI` — REST `/v1/chat/completions`, `Authorization: Bearer` |
| `precos.py` | `TABELA` por 1M de tokens, `custo_usd()`, `tabela_para_manifesto()` |

`criar_provedor(modelo)` escolhe a implementação pelo nome do modelo.
`avaliar(prompt)` devolve sempre `RespostaLLM`, com veredito já validado
(`VP`/`FP`/`ERROR`), tokens e custo.

---

### `src/fases3_4_llm.py`

**Propósito:** Monta o prompt do tipo pedido e delega a rede ao provedor. Não
contém texto de prompt nem chamada HTTP.

**Entrada:** `(contexto_hidratado, cwe_id, cwe_name, description, provedor,
tipo_prompt, ficha)`

**Saída:** `avaliar(...)` → `RespostaLLM`;
`avaliar_vulnerabilidade(...)` → `{"verdict": "VP"|"FP"|"ERROR", "reasoning": "..."}`

---

### `src/fase5_auditoria.py`

**Propósito:** Grava cada caso no CSV de resultados e classifica nas duas
matrizes.

- `classificar_cobertura_semgrep(gabarito, detectado)` — matriz de cobertura
  do Semgrep (VP/VN/FP/FN do motor simbólico).
- `classificar_acerto_llm(gabarito, verdict_llm)` — matriz de acerto do LLM.
- `registrar_resultado(...)` — grava linha no CSV e imprime resumo.

**Colunas do CSV:** `ID_Caso, Repositorio, CWE, Origem, Modelo_LLM,
Tipo_Prompt, Gabarito, Status_Semgrep, Classificacao_Semgrep, Veredito_LLM,
Classificacao_LLM, Tempo_Execucao_s, Justificativa, Num_Locations, Ficha_CWE,
Versao_Prompt, Hash_Catalogo, Tokens_Entrada, Tokens_Saida, Custo_USD`

As sete últimas são da Parte 2 (`COLUNAS_PARTE2`); CSVs da Parte 1 não as têm.

---

### `src/metricas.py`

**Propósito:** Consolida uma rodada (`results/<run_id>/`) ou um CSV avulso e
calcula as métricas do TCC (Seção 3.5), por braço.

**Entrada:** diretório de rodada **ou** caminho de um CSV

**Saída:** tabela lado a lado dos braços, cobertura do Semgrep à parte,
estratificações, McNemar pareado e, com `--latex`, `tabela_bracos.tex` e
`tabela_mcnemar.tex` no diretório da rodada.

**Uso:**
```bash
python src/metricas.py results/<run_id>
python src/metricas.py results/<run_id> --mcnemar --estratificar --latex
python src/metricas.py legacy/resultados_parte1/resultados_tcc.csv --por-cwe
```

---

## Orquestrador

### `run_pipeline.py`

**Propósito:** Orquestra as 5 fases para todas as trilhas, em N braços
`(modelo, tipo de prompt)`.

**Seleção da população:**
- `--amostra N` — N casos, priorizando o que já está em cache
- `--tudo` / `--fp-only` / `--tp-only` — modo de entrada
- `--trilha TRILHA` — restringe a `FP`, `TP_ouro`, `TP_prata` ou `TP_dataset`
  (repetível, aplicado depois do modo)
- `--uma-location`, `--todas-extensoes` — recortes do dataset

**Seleção de braços:**
- `--matriz` — matriz 2x2 completa (Gemini e GPT × baseline e especialista)
- `--modelo M` / `--prompt T` — produto cartesiano; repetíveis. Sem eles, o
  braço padrão vem de `LLM_MODEL_VERSION` e `PROMPT_TYPE`.

**Execução:**
- `--dry-run` — só relata a população e os braços
- `--sem-llm` — Fases 1-2 apenas (cobertura simbólica, sem gastar API)
- `--sem-cache-simbolico` — reexecuta Fases 1-2 sempre
- `--run-id ID` — retoma uma rodada existente
- `--verboso` — DEBUG (mostra cada invocação real do Semgrep)

**Saída:** `results/<run_id>/` com `<modelo>__<prompt>.csv` por braço e
`manifesto.json`. Nenhum CSV é criado na raiz.

**Checkpoint:** pela tripla `(ID_Caso, Modelo_LLM, Tipo_Prompt)`, lida **só da
rodada corrente** (`results/<run_id>/`). Assim uma rodada nova começa do zero e
uma interrompida retoma de onde parou.

`--reaproveitar-anteriores` estende a leitura às rodadas passadas, aos CSVs da
raiz e a `legacy/resultados_parte1/`. Fica desligado por padrão porque as linhas
da Parte 1 pertencem ao braço `(gemini-2.5-flash-lite, especialista)`: contá-las
faria esse braço vir com menos casos que os outros três, quebrando a premissa de
que os quatro cobrem a mesma população — que é o que torna o McNemar pareado
válido.

Um caso só conta como concluído se terminou em `NAO_DETECTADO` ou em
`DETECTADO` **com veredito em {VP, FP}**. Um `DETECTADO` sem veredito é o que
`--sem-llm` produz (o Semgrep disparou, ninguém triou) e continua pendente.
Casos em categoria de erro nunca são checkpointados — a rodada seguinte os
re-tenta.

---

### `scripts/ranking_cwe.py`

**Propósito:** Conta as amostras por CWE (locations `.go`, excluindo
`_test.go`) para dimensionar a cobertura do catálogo. Lê só `cwe_id`: nenhum
trecho de código sai daqui, para não contaminar quem escreve as fichas.

**Uso:**
```bash
python scripts/ranking_cwe.py            # top 15 + cobertura acumulada
python scripts/ranking_cwe.py --json
```
