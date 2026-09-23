# Referência de Scripts e Módulos

## Operação

### `scripts/gatilho_rodada_triagem.py`

**Propósito:** esperar a máquina ficar ociosa e então executar a esteira inteira
da rodada de triagem, sem supervisão. Existe porque a rodada leva ~7,3 h no
provedor local (8,23 s/chamada, medido) e porque Semgrep e modelo local disputam
RAM — rodar junto de outra esteira degrada os dois.

**Entradas:** o estado dos processos da máquina (via `Get-CimInstance`), o cache
simbólico e o provedor Ollama.

**Saídas:** `results/rodada-4-triagem/` (CSVs, manifesto, `.tex`),
`results/pre-fase1-simbolica/` (a passada de cobertura) e o log
`results/gatilho-triagem.log`.

**O que faz, em ordem:**

1. Espera **`--quiet-min` minutos SEGUIDOS** sem nenhum processo concorrente
   (Semgrep em qualquer forma, `run_pipeline.py`, `verificar_pro.py`, colheita) e
   com RAM livre acima de `--ram-livre-gb`. Uma única amostra suja zera o
   relógio: a Fase 1 chama o Semgrep uma vez por caso, e uma janela curta demais
   dispararia na fresta entre dois casos.
2. **Descarrega** o modelo do Ollama (`keep_alive: 0`).
3. Roda `--tudo --sem-llm` para garantir a Fase 1 em cache para a população
   inteira. É o único ponto em que o Semgrep pode rodar sem disputar RAM com o
   modelo — por isso vem antes do passo 4, e não depois.
4. **Aquece** o modelo (`keep_alive: 24h`) e o mantém residente.
5. Piloto: `--tp-only --modo-montagem triagem`, dois braços locais. É o recorte
   que alcança os 19 positivos detectados, sem os quais não há grupo de controle.
6. Emite as métricas e aplica o **portão da tarefa 5.5**, que é **direcional**:
   ele fecha quando o LLM acerta *mais* nos **injetados** que nos detectados por
   mais que `--limiar-portao` (padrão 0,25) — é esse sentido que indica artefato
   de montagem inflando o resultado, e é o que a spec nomeia. Fecha também com
   grupo de controle vazio: sem controle não há o que concluir. O sentido
   contrário — o modelo indo *pior* nos injetados — **não** interrompe: é
   consistente com o Semgrep detectar as vulnerabilidades mais fáceis, e
   bloquear ali gastaria o portão na direção errada. Esse caso sai como
   `WARNING` no log, porque é a ameaça da "natureza das localizações" se
   manifestando e precisa ir para a análise da rodada. `--sem-portao` desliga
   o bloqueio.
7. Reconfere que a máquina continua livre e roda `--tudo` no mesmo `--run-id`; o
   checkpoint reaproveita o piloto.
8. Emite as métricas finais.

**Uso:**

```bash
# Estado da máquina agora, sem esperar nem rodar:
python scripts/gatilho_rodada_triagem.py --agora

# Armar (fica esperando; padrão: 10 min de silêncio, piloto + rodada completa):
python scripts/gatilho_rodada_triagem.py

# Só o piloto:
python scripts/gatilho_rodada_triagem.py --so-piloto
```

Destacado do terminal, para sobreviver ao fim da sessão (PowerShell):

```powershell
Start-Process -WindowStyle Hidden python \
  -ArgumentList 'scripts/gatilho_rodada_triagem.py' \
  -WorkingDirectory (Get-Location)

Get-Content results/gatilho-triagem.log -Wait     # acompanhar
```

**Trava de instância única:** `results/gatilho-triagem.lock` guarda o PID. Um
segundo gatilho recusa subir enquanto o primeiro estiver vivo; lock órfão (PID
morto) é assumido sem reclamar.

**Para cancelar:** matar o processo. O que já rodou fica no checkpoint da
rodada — reexecutar com o mesmo `--run-id` retoma de onde parou.

---

## Fase 0 — Preparação de Dados TP (`scripts/`)

Estes scripts são executados **uma única vez** antes da pipeline principal.
Produzem os manifestos de fix commits e os pares vuln/corrigido.

### `scripts/osv_harvest_go.py`

**Propósito:** Coleta CVEs do ecossistema Go na OSV.dev e gera o manifesto
de fix commits para a trilha prata, **restrito às CWEs que o motor simbólico
alcança em Go**.

**Entradas:** API pública `api.osv.dev`, catálogo de regras via `src/ruleset.py`

**Saídas:** `data/tp_fixes_osv_alcancavel.json` — lista de CVEs com `fix_commit`
e `repo_url`. Arquivo **próprio**: não sobrescreve `data/tp_fixes_osv.json` (a
colheita sem filtro) nem os pools `tp_pairs*.json`, que são a evidência do
achado dos 70% e, no caso de `tp_pairs.json`, irrecuperáveis.

**Filtros:** CWE alcançável em Go + commit de fix + repo GitHub. Limita por repo
(diversidade) e para ao atingir o alvo.

**Por que o filtro existe:** a colheita antiga aceitava qualquer CWE, e 70,1 %
dos 107 casos vulneráveis da rodada `20260731T140000Z-af9bc32` acabaram com CWE
que nenhuma regra Go do `p/default` declara — indetectáveis por construção. O
recall medido sobre essa população mede a lacuna do catálogo de regras, não a
capacidade do motor (`docs/ANALISE-RODADA-2.md` §3.1).

**Todas as CWEs declaradas são avaliadas**, não só `cwe_ids[0]`: a ordem dessa
lista é arbitrária, e ficar com a primeira recusaria candidata legítima por
acidente de listagem. **A CWE registrada é a que casou** com o ruleset — é ela
que a Fase 1 vai procurar no arquivo e contra a qual o gabarito é pontuado.
Vulnerabilidade que não declara CWE alguma é recusada, em vez de virar
`CWE-desconhecida` como antes.

**Relatório:** o bloco `=== RESUMO ===` traz a distribuição das CWEs aceitas, a
contagem de recusadas por inalcançabilidade discriminada por CWE, e a data do
snapshot do ruleset. A discriminação por CWE é o que distingue "a OSV tem pouca
coisa nestas fraquezas" de "o filtro está recusando tudo por defeito"; a data
torna visível a divergência possível entre o registry e o Semgrep instalado.
Colheita vazia é anunciada e **não** grava arquivo.

**Uso:**
```bash
python scripts/osv_harvest_go.py --alvo 100
python scripts/osv_harvest_go.py --alvo 100 --por-repo 5 --max-scan 600
python scripts/osv_harvest_go.py --alvo 1200 --por-repo 20 --max-scan 9200
```

**Grau de alcançabilidade no relatório.** A distribuição por CWE sai com o grau
(`alta`/`media`/`baixa`) de `src/ruleset.py`, mais o agregado por grau. É o que
torna o rendimento previsível **antes** de gastar rede: na rodada
`20260908T094808Z-9a00cb2` as CWEs de grau baixo consumiram metade do orçamento
e renderam 1 detecção em 336 pares.

**`--grau-minimo {baixa,media,alta}`** restringe a colheita a CWEs de grau ao
menos esse. Fica **desligado por padrão**, e não por descuido: restringir troca o
denominador do recall — passa a medir o motor sobre as fraquezas em que ele
*afirma* detectar, e não sobre as que *declara cobrir*. O valor usado é impresso
no resumo.

> **Teto empírico medido (2026-09-08):** varrendo o dump inteiro (9.113 entradas)
> com `--por-repo 20`, saem **810 candidatas** e só 2 dos 362 repositórios batem
> o teto. A fonte Go da OSV está esgotada sob o critério de alcançabilidade.

> **Cuidado:** a colheita **sobrescreve** `data/tp_fixes_osv_alcancavel.json` ao
> final. Rodar com `--alvo` pequeno para testar destrói a colheita anterior —
> copie o arquivo antes.

---

### `scripts/pares_alcancaveis.py`

**Propósito:** Identifica, entre os pares de TP **já colhidos**, aqueles cuja CWE
o motor simbólico alcança em Go — para que entrem na população sem recolheita.

**Entradas:** `tp_pairs.json`, `tp_pairs_osv.json` (ou os passados em `--pools`),
catálogo de regras via `src/ruleset.py`

**Saídas:** apenas texto (ou JSON com `--json`). **Somente leitura:** não escreve
nos pools nem monta população. Separar identificação de mutação torna a operação
repetível e segura — `tp_pairs.json` é irrecuperável, só `tp_reconstruct.py` o
regenera e ele exige o histórico git completo dos repositórios.

**Resultado atual:** 17 dos 50 pares são aproveitáveis — 4 de 16 em
`tp_pairs.json` (CWE-200, CWE-352, CWE-918) e 13 de 34 em `tp_pairs_osv.json`
(CWE-400, CWE-79, CWE-200, CWE-22). Cada par é listado com a CWE que o torna
alcançável.

**Uso:**
```bash
python scripts/pares_alcancaveis.py
python scripts/pares_alcancaveis.py --pools tp_pairs.json
python scripts/pares_alcancaveis.py --json
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

### `scripts/verificar_pro.py`

**Propósito:** Portão de viabilidade do modo entre-arquivos do Semgrep. Mede, com
evidência própria e datada, se o Semgrep Pro roda com conta gratuita e se ele
produz trilha de dataflow **entre arquivos** em Go. A change que o introduziu não
avançaria sem ele: a evidência de gratuidade vinha de `semgrep.dev/pricing`,
página comercial, não de documentação técnica nem de termo de licença.

⚠️ **Exige rede e login** (`semgrep login` + `semgrep install-semgrep-pro`, ou
`SEMGREP_APP_TOKEN` no `.env`). É o único script da esteira com essa
dependência. `--selftest` é a exceção: roda sem rede e sem credencial.

Duas etapas, de custo crescente:

1. `--etapa sintetica` — projeto Go mínimo escrito para este fim, com a fonte num
   arquivo e o sumidouro em outro. Segundos. Pode devolver `indisponivel` e
   encerrar o portão **sem clonar nada**.
2. `--etapa real` — checkout raso de ~10 repositórios da população nos
   `parent_commit`, metade de CWE-22 e metade de CWE-918. Custa disco e rede;
   cada checkout é apagado assim que medido.

**Por que o alvo não é o cache de fontes:** `cache/` guarda **um arquivo por
caso** — 69 dos 226 casos de CWE-22/918 têm um único arquivo no diretório do
commit. Análise entre arquivos sobre alvo assim devolve zero trilhas por
construção, e a classificação descreveria a forma do cache, não o alcance do
motor. Por isso alvo de arquivo isolado é **recusado**, não classificado.

O projeto sintético inclui um **controle positivo** (fonte e sumidouro na mesma
função), que o CE já detecta. Sem ele, "nenhuma trilha" seria ambíguo entre "o
motor não atravessa arquivos" e "o alvo ou o ruleset estão errados".

**Entradas:** `tp_pairs_osv_alcancavel.json`, `cache/`, e o Semgrep autenticado

**Saídas:** `data/viabilidade_pro_<AAAAMMDD>.json` — etapa, edição obtida, versão
do Semgrep, alertas por modo, quantos trazem trilha (e quantos **entre
arquivos**), tempo por alvo, e a classificação: `viavel` | `inconclusivo` |
`indisponivel`. É esse arquivo que `run_pipeline.py --entre-arquivos` exige; sem
um `viavel`, a execução aborta.

Não grava nem invalida entrada de cache simbólico, e não produz CSV de rodada.

**Uso:**
```bash
python scripts/verificar_pro.py --selftest         # valida a lógica, sem rede
python scripts/verificar_pro.py --etapa sintetica  # só a etapa barata
python scripts/verificar_pro.py --etapa real       # só a etapa cara
python scripts/verificar_pro.py                    # as duas, na ordem
```

> **Limitação conhecida do critério.** A classificação `viavel` exige ≥1 trilha
> entre arquivos no alvo — isso mede a **capacidade do motor**, não o **ganho na
> nossa população**. Na medição de 2026-09-15 o portão passou e, ainda assim, o
> cruzamento manual do `seaweedfs` mostrou 0 alertas nos arquivos do gabarito nos
> dois modos. Um portão futuro para troca de ruleset ou de motor deve ter como
> critério a detecção **nos casos do gabarito**, não "a ferramenta funciona".

---

### `scripts/particionar_avaliacao.py`

**Propósito:** Separa, **antes de qualquer regra local existir**, os casos que
podem ser olhados para escrever regra dos casos que só servem para medir. Grava
`data/particao_avaliacao.json`.

**Por que existe:** escrever regra do Semgrep olhando os casos em que ela vai ser
medida é ajustar ao conjunto de teste — o número resultante mede a nossa
capacidade de descrever arquivos que já vimos, não a capacidade da análise
sintática. A separação precisa ser **estrutural, não disciplinar**: não basta
pretender não olhar.

**Unidade de partição:** o grupo `(CWE, repositório)` inteiro, nunca o par
isolado. Pares da mesma CWE no mesmo repositório compartilham idioma de código e
às vezes o mesmo helper de validação; separá-los faria uma regra escrita no
desenvolvimento detectar de graça um caso da avaliação. As versões vulnerável e
corrigida do mesmo par também não se separam — são o mesmo arquivo em dois
commits.

**Derivação determinística, sem semente:** os grupos de cada CWE são percorridos
na ordem do digest SHA-256 da chave e cada um vai para a partição que estiver
menor. Não há semente para trocar até o número melhorar, e quem tiver a população
reproduz a partição sem confiar em nada nosso. A alternativa mais simples —
paridade do digest — desequilibrava por causa dos repositórios de cabeça (CWE-22
ficava em 126 contra 102 casos).

**Recusa reparticionar.** A segunda invocação falha com erro explícito. A ordem
— partição antes de regra — é auditável no histórico do Git, e só vale enquanto
o arquivo não for reescrito. `--forcar` existe, e só pode ser usado antes de a
primeira regra existir.

**Entradas:** `tp_pairs_osv_alcancavel.json`, com os `ID_Caso` derivados por
`run_pipeline.construir_casos_tp` — importado, não reimplementado: uma partição
indexada por IDs de outra regra não casaria com CSV nenhum.

**Saídas:** `data/particao_avaliacao.json` — protocolo, data, CWEs alvo, resumo
por CWE e o mapa `ID_Caso -> partição`.

**Resultado de 2026-09-17:** CWE-22 com 108 casos no desenvolvimento e 120 na
avaliação; CWE-918 com 110 e 114. Em pares, a avaliação ficou com 60 e 57 —
acima do limiar de 30 que o projeto adota.

**Uso:**
```bash
python scripts/particionar_avaliacao.py --selftest
python scripts/particionar_avaliacao.py --cwe CWE-22 --cwe CWE-918
```

---

### `scripts/medir_regras_locais.py`

**Propósito:** Mede quanto as regras de `regras/go/` detectam, **discriminado por
partição**, e recusa emitir o número agregado quando houver regra de proveniência
`desenvolvimento` carregada.

**Por que a recusa é falha e não aviso:** aviso não impede citação. O número mais
fácil de copiar é o que acaba no texto, e um agregado que mistura a partição em
que as regras foram escritas com a partição em que elas são medidas é exatamente
o número indefensável. Recusar produzi-lo é a única mitigação que ainda funciona
meses depois, quando o contexto tiver se perdido.

**A exceção é deliberada:** se **todas** as regras carregadas forem de
proveniência `definicao`, o agregado sai. Nenhum caso da população informou a
escrita delas, então não há o que contaminar — e preservar os 114 casos de CWE-22
como denominador é o que torna o protocolo `definicao` preferível.

**Cada número sai rotulado** com a partição e o protocolo na mesma linha, para
que copiá-lo sem a ressalva seja desconfortável.

**O ruleset medido é só o local.** Medir com `p/default` junto responderia outra
pergunta — quanto o conjunto detecta —, e a lacuna que as regras locais existem
para preencher já está medida: zero, nas duas CWEs alvo.

**Critério de detecção:** o mesmo da Fase 1 — a regra que emitiu o alerta declara
a CWE do gabarito. Reaproveitá-lo não é economia: é o que impede que este número
signifique algo diferente do número da pipeline.

**Entradas:** `data/particao_avaliacao.json`, `regras/go/`, `cache/`

**Saídas:** relatório em texto (e `--json`). Grava no cache simbólico sob a
identidade do conjunto unitário `regras/go`, então reexecutar é barato.

**Uso:**
```bash
python scripts/medir_regras_locais.py --selftest
python scripts/medir_regras_locais.py                # por partição
python scripts/medir_regras_locais.py --agregado     # só se tudo for `definicao`
```

---

### `scripts/auditar_regras_ficha.py`

**Propósito:** Tabela regra × CWE × detecções sobre o cache simbólico, com a
origem da ficha que cada par recebe hoje (`regra`, `cwe` ou `fallback`). É o
insumo da escolha de quais regras ganham ficha própria no bloco `regras` do
catálogo.

**Protocolo:** lê do cache só o `check_id` do alerta e o status — nunca o
contexto hidratado —, para que a seleção das regras use apenas metadado.

```bash
python scripts/auditar_regras_ficha.py            # regras com >= 5 detecções
python scripts/auditar_regras_ficha.py --minimo 1 # todas
```

---

### `scripts/medir_prompts.py`

**Propósito:** Mede a distribuição de tamanho de prompt (em tokens estimados)
sobre a população, por tipo de prompt, para calibrar o `num_ctx` do braço local
com medida em vez de chute. Não chama LLM, não roda Semgrep e não toca a rede:
monta os mesmos prompts da Fase 3/4 a partir do contexto já gravado no cache
simbólico.

**Entradas:** `data/dataset.json`, `tp_pairs*.json` e `cache_simbolico/`

**Saídas:** relatório no terminal — n, mínimo, mediana, p95, máximo e quantos
casos estourariam a janela avaliada

**Uso:**
```bash
python scripts/medir_prompts.py
python scripts/medir_prompts.py --num-ctx 16384
python scripts/medir_prompts.py --trilha FP
```

Casos ausentes do cache simbólico ficam de fora e são reportados: preencha o
cache com `python run_pipeline.py --tudo --sem-llm` antes de fixar `num_ctx`.

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
| `SEMGREP_CONFIG` | `p/default` | Ruleset(s) do Semgrep, separados por vírgula. A identidade do **conjunto** entra no cache simbólico e no manifesto |
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
emitido por regra que declara **exatamente** a CWE do gabarito nas tags
(comparação por identificador inteiro, não por substring: `CWE-77` ≠ `CWE-770`).
Não há fallback — o número de alertas no arquivo não é critério de pareamento.
Entre vários alertas casados, escolhe o primeiro por `(linha inicial, check_id)`.

**Entrada:** `(caminho_arquivo, cwe)`

**Saída:** `ResultadoFase1(alerta, motivo, regras_nao_casadas)` — `alerta` é o
dict do alerta Semgrep com `start.line`, `check_id` e `extra.message`, ou `None`
(NAO_DETECTADO); `motivo ∈ {SEM_ALERTA, ALERTA_OUTRA_CWE, N/A}`;
`regras_nao_casadas` são os `check_id` que dispararam sem casar, deduplicados e
em ordem alfabética.

**Versionamento:** `VERSAO_PAREAMENTO` identifica a regra de pareamento vigente.
Subi-la invalida todo o cache simbólico.

**Exceções:** `SemgrepFileNotFoundError`, `SemgrepTimeoutError`, `SemgrepError`

---

### `src/ruleset.py`

**Propósito:** Responde à pergunta *"o motor simbólico tem regra para esta CWE
nesta linguagem?"*. O conjunto de CWEs alcançáveis é derivado do catálogo de
regras a cada consulta, nunca de lista embutida no código — o ruleset é
configurável por `SEMGREP_CONFIG`, e uma lista fixa passaria a mentir em silêncio
no instante em que ele mudasse.

**Alcançabilidade é por linguagem:** só contam as regras cuja `languages` inclui a
linguagem consultada. Nenhuma regra de Python dispara sobre um arquivo `.go`, e
tratar a CWE como alcançável porque o ruleset a cobre "em abstrato" produziria
população que o motor não tem como detectar. No `p/default`, das 1074 regras, 84
são de Go e cobrem 34 CWEs distintas.

**Fonte e cache:** busca `https://semgrep.dev/c/<SEMGREP_CONFIG>` e grava em
`cache_simbolico/_regras_<config>.json` (para `p/default`,
`_regras_p_default.json`). Com o cache presente, funciona offline. O nome do
arquivo carrega a configuração para que trocar `SEMGREP_CONFIG` não sirva o
catálogo antigo sem aviso.

**Comparação de CWE:** importa `_numero_cwe` de `src/fase1_semgrep.py` em vez de
reimplementá-la. Se a alcançabilidade aceitasse por um critério e o pareamento
recusasse por outro, a colheita produziria casos que a Fase 1 descartaria —
`CWE-77` e `CWE-770` são fraquezas distintas, e ambas estão na população.
`metadata.cwe` é aceito como string única ou como lista, porque as duas formas
ocorrem no registry (959 listas contra 85 strings).

**API:** `carregar_regras()` → `{check_id: Regra(cwes, linguagens)}`;
`cwes_alcancaveis(linguagem)` → conjunto de números de CWE;
`cwe_alcancavel(cwe, linguagem)` → bool; `metadados_snapshot()` →
`Snapshot(origem, caminho, obtido_em, regras)`.

**Snapshot:** `metadados_snapshot()` expõe a data do cache porque o registry e o
Semgrep instalado são catálogos diferentes — a divergência já foi observada
(`docs/ANALISE-RODADA-2.md` §6.1) e a data a torna visível. Fixar o ruleset por
versão é assunto de outra mudança.

**Exceções:** `RulesetIndisponivelError` quando não há cache nem rede. É erro de
propósito: conjunto vazio faria toda CWE parecer inalcançável e recusaria a
população inteira em silêncio.

---

### `src/regras_locais.py`

**Propósito:** Carrega e valida o ruleset mantido neste repositório
(`regras/go/`), e o descreve para o manifesto da rodada.

**Por que o ruleset é local:** é o único do projeto imune à ameaça de mudança do
lado do servidor. Qualquer ruleset do registry — o `p/default` inclusive — pode
mudar sem que nada no código perceba; este muda apenas por commit, e o manifesto
permite dizer, meses depois, exatamente quais regras produziram cada número.

**Três metadados obrigatórios, e o carregamento derruba sem qualquer um deles:**

| metadado | o que a ausência causaria |
|---|---|
| `proveniencia` | o relatório não saberia qual número pode sair de qual partição, e o caminho de menor resistência seria reportar tudo junto |
| `cwe` (formato casável) | a regra dispara, o alerta não emparelha, a Fase 1 registra `ALERTA_OUTRA_CWE` e o esforço se perde com a regra *funcionando* |
| `subcategory` | a regra é tratada como auditoria pelo grau de alcançabilidade, e a CWE não sobe de grau ainda que a detecção melhore |

**É o oposto do que `src/ruleset.py` faz com ruleset de terceiros**, e de
propósito. Lá, metadado ausente degrada para o comportamento conservador e a
execução segue: não temos controle sobre o que o registry publica, e derrubar a
rodada por isso seria recusar a ferramenta inteira. Aqui, ausência é defeito
nosso, e descobri-lo depois de a rodada varrer a população custa horas.

**Vocabulário de `proveniencia`:**

- `definicao` — derivada da definição da CWE e do idioma de Go, sem que nenhum
  caso da população tenha sido inspecionado. Pode ser medida sobre a população
  inteira.
- `desenvolvimento` — derivada da inspeção da partição de desenvolvimento. Só
  pode ser medida sobre a partição de avaliação.

Vocabulário fora desses dois **não** é tratado como o mais parecido: adivinhar
escolheria por nós qual número é reportável.

**API:** `carregar(diretorio)` → `{id: RegraLocal}`; `proveniencias(diretorio)` →
conjunto de protocolos carregados; `para_manifesto(diretorio, commit)` → o bloco
`semgrep.regras_locais` do manifesto.

**Exceções:** `RegraLocalInvalidaError`

---

### `regras/go/` — o ruleset próprio

Regras do Semgrep escritas neste projeto para CWEs que **nenhum ruleset público
alcança em Go**. Medido em 2026-09-16: nem `p/gosec`, nem `p/trailofbits`, nem
`p/security-audit` acrescentam regra Go para CWE-22 ou CWE-918
(`docs/MAPA-TCC-O-QUE-REESCREVER.md` §3.6).

Entram por configuração explícita (`SEMGREP_CONFIG=p/default,regras/go`); o
padrão continua sem elas.

Cada `.yaml` tem ao lado um `.go` de teste no formato que `semgrep --test`
consome, com as anotações `// ruleid:` e `// ok:`. Os arquivos de teste foram
escritos à mão a partir do idioma de Go — nenhum trecho veio da população.

```bash
semgrep --test regras/go        # as regras disparam no exemplo e calam no seguro
```

**São sintáticas, não de taint**, por decisão registrada: o motor CE só rastreia
fluxo dentro de um arquivo, e é essa limitação que deixou CWE-22 e CWE-918 secas.
Regra de taint rodando sob o motor que não a alcança repetiria o defeito. O custo
é ruído — que é precisamente o que o braço neural existe para filtrar.

**As quatro regras, e sob qual protocolo cada uma foi escrita:**

| regra | CWE | proveniência |
|---|---|---|
| `caminho-de-entrada-externa-sem-restricao` | CWE-22 | `definicao` |
| `requisicao-a-url-de-entrada-externa` | CWE-918 | `definicao` |
| `extracao-de-compactado-sem-prender-a-base` | CWE-22 | `desenvolvimento` |
| `url-de-campo-de-struct-em-cliente-http` | CWE-918 | `desenvolvimento` |

Com qualquer regra `desenvolvimento` carregada, o número reportável passa a ser o
da **partição de avaliação** — a medição recusa o agregado. Medido em 2026-09-17:
CWE-22 4/60 (6,7 %) e CWE-918 1/57 (1,8 %) na avaliação. Só com as `definicao`,
sobre a população inteira: 2/114 (1,8 %) e 1/112 (0,9 %).

**As regras não são a contribuição.** A contribuição é a análise de lacunas que
elas tornaram possível — ~30 % dos arquivos rotulados não contêm a operação
perigosa, e outros 26–44 % só a expõem atrás de abstração. Ver
`docs/MAPA-TCC-O-QUE-REESCREVER.md` §3.7.

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

**Payload:** `{versao_formato, versao_ruleset, versao_pareamento, status_semgrep,
alerta, motivo, regras_nao_casadas, contexto_hidratado, ...}`. `NAO_DETECTADO`
também é gravado, com o motivo e as regras, para que o diagnóstico de cobertura
sobreviva ao cache.

**Invalidação:** divergência de `versao_ruleset`, `versao_pareamento` ou
`versao_formato` faz a entrada ser ignorada (não apagada) — inclusive quando
`versao_pareamento` está ausente, que é o estado das entradas anteriores ao
campo. Nada sob `cache/` é tocado.

---

### `src/catalogo.py`

**Propósito:** Carrega e valida `data/catalogo_cwe.json`, resolve a ficha com a
precedência regra > CWE > fallback e calcula o SHA-256 dos bytes do arquivo.

**API:** `Catalogo.carregar(caminho)`, `.ficha(cwe, cwe_name, check_id=None)` →
`Ficha` (com `.origem ∈ {regra, especifica, fallback}`), `.sha256`,
`.cwes_especificas`, `.regras` (fichas do bloco `regras`, por `check_id`
completo).

**Exceção:** `CatalogoInvalido` quando falta o fallback, um campo obrigatório
está vazio (em ficha de CWE ou de regra), o bloco `regras` não é objeto ou o
JSON é inválido.

---

### `src/prompts.py`

**Propósito:** Renderiza `prompts/*.md` por `str.format` com placeholders
nomeados e calcula a versão (hash curto) de cada template.

**API:** `montar_prompt(tipo, contexto, cwe_id, cwe_name, description, ficha)`,
`versao_prompt(tipo)` → `especialista:d1145f8b`, `secao_contrato(tipo)`.

O `baseline` recebe **só** o contexto — nem o identificador da CWE. É a condição
de controle: qualquer camada da metodologia que vaze para ele mata o contraste.

Tipos: `baseline`, `especialista` (modo filtro), `baseline_direto`,
`especialista_direto` (modo triagem: perguntam pelo código, não pelo alerta) e
as variantes `especialista_v2` / `especialista_direto_v2` — o original mais um
parágrafo pedindo que o modelo não presuma mitigação ausente do trecho. As
variantes são arquivos novos: os hashes dos originais estão travados em teste
porque identificam as rodadas já gravadas.

---

### `src/provedores/`

| Arquivo | Conteúdo |
|---|---|
| `base.py` | `RespostaLLM`, protocolo `ProvedorLLM`, `ProvedorHTTP` (throttle, retry, validação), `validar_resposta`, `espera_backoff`, `ler_retry_after` |
| `gemini.py` | `ProvedorGemini` — REST `generateContent`, header `x-goog-api-key` |
| `openai.py` | `ProvedorOpenAI` — REST `/v1/chat/completions`, `Authorization: Bearer` |
| `ollama.py` | `ProvedorOllama` — REST `/api/chat` local, sem chave; `num_ctx` explícito, estouro vira `ERROR`; `sondar()` para a verificação prévia e o manifesto |
| `precos.py` | `TABELA` por 1M de tokens, `custo_usd()`, `tabela_para_manifesto()` |

`criar_provedor(modelo)` escolhe a implementação pelo nome do modelo — o
namespace `ollama:` é testado antes dos prefixos comerciais.
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
Versao_Prompt, Hash_Catalogo, Tokens_Entrada, Tokens_Saida, Custo_USD,
Motivo_Nao_Deteccao, Regras_Nao_Casadas`

As nove últimas são posteriores à Parte 1 (`COLUNAS_PARTE2`); CSVs da Parte 1
não as têm, e as duas de pareamento faltam também nos CSVs anteriores a ela —
quem lê trata a ausência como "indisponível", nunca como erro. Elas vão no fim
porque `registrar_resultado` escreve a linha posicionalmente e `COLUNAS_PARTE2`
é uma fatia do cabeçalho.

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
- `--catalogo CAMINHO` — catálogo de fichas do especialista (padrão `data/catalogo_cwe.json`, por CWE; o por regra da Rodada 7 é `data/catalogo_cwe_por_regra.json`)
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

---

### `scripts/analise_rodada.py`

**Propósito:** Imprime os números derivados de uma rodada que `src/metricas.py`
não produz. `metricas.py` responde "qual o desempenho de cada braço"; este
script responde "quantas amostras sustentam esse desempenho". É a ferramenta de
conferência do relatório `docs/ANALISE-RODADA-1.md`: cada tabela de lá cita a
invocação exata que a regenera.

Reusa `carregar`, `contar`, `mcnemar` e as funções de categorização de
`src.metricas`, para que não existam duas verdades sobre o que conta como
Verdadeiro Positivo.

**Garantias:** somente-leitura (não escreve, move nem regenera artefato algum),
offline (nenhuma chamada de rede ou de LLM) e determinístico (toda ordenação tem
chave explícita; duas execuções produzem saída idêntica).

**Seções** — sem `--secao`, saem todas nesta ordem:

| seção | o que imprime |
|---|---|
| `funil` | degraus de "gabarito vulneravel" até o veredito do LLM, com perda absoluta e percentual por degrau, a causa de cada uma, e recall medido contra recall de ponta a ponta |
| `nao-detectados` | casos vulneráveis sem alerta pareado, por CWE e por trilha, cruzados com o catálogo de triagem e com as CWEs que o ruleset declara cobrir em Go |
| `conjuntos` | conjuntos de VP/VN/FP/FN por braço, especificidade, taxa de veredito "vulnerável", interseção, contenção com direção declarada, e a tabela 2x2 de discordâncias conferida contra `src.metricas.mcnemar` |
| `esteira` | linhas e status do Semgrep por braço, taxa de erro, denominador efetivo, e estatísticas de `Tokens_Entrada` e `Tempo_Execucao_s` |
| `positivos` | um registro por caso de gabarito vulnerável que chegou ao LLM, com a regra que disparou, a CWE que ela declara, e veredito e justificativa de cada braço |
| `regras` | quais regras do ruleset de fato dispararam sobre o corpus, com a CWE declarada e o pareamento exato contra o pareamento por fallback, separado por classe de gabarito |
| `grau` | taxa de detecção agregada por grau de alcançabilidade (`alta`/`media`/`baixa`), o ganho de densidade ao recusar o grau mais baixo, e a checagem de robustez removendo a CWE que mais detecta |

**Uso:**
```bash
python scripts/analise_rodada.py results/<run_id>
python scripts/analise_rodada.py results/<run_id> --secao funil
python scripts/analise_rodada.py results/<run_id> --secao positivos --justificativa-completa
python scripts/analise_rodada.py results/<run_id> --secao regras --cache cache_simbolico_pre_estrito
python scripts/analise_rodada.py results/<run_id> --secao grau
```

**Sobre a seção `grau`.** Ela agrega pares e detecções **somados por grupo**,
nunca a média das taxas por CWE — uma CWE com 3 pares não pode pesar como uma com
124. A saída imprime, por conta própria, a ressalva de que o critério do grau foi
derivado *olhando* a rodada `20260908T094808Z-9a00cb2`: a separação é **observada
naquela amostra**, não prevista. Validá-la exige rodar esta seção sobre uma rodada
que não a gerou.

**Flags:** `--secao` isola uma seção; `--justificativa-completa` não trunca as
justificativas do LLM; `--cache` escolhe o diretório de cache simbólico
consultado por `positivos` e `regras`.

**Sobre `--cache`:** o CSV não grava qual regra produziu o alerta — esse dado só
existe no cache simbólico, que é invalidado e regravado quando a regra de
pareamento muda. Ler um cache regravado descreveria outra pipeline, então as
seções que dependem dele imprimem a distribuição de `versao_pareamento` das
entradas lidas e avisam quando o cache está misto.

Um diretório inexistente ou sem CSV de rodada encerra com mensagem explícita e
código de saída 1, em vez de imprimir tabelas vazias. Não é chamado por
`run_pipeline.py`.
