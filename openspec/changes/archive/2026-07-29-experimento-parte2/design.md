# Design — Experimento completo da Parte 2

## Contexto

A PoC da Parte 1 roda um único braço (Gemini + prompt especialista embutido) sobre uma população dominada por FPs. A Parte 2 exige quatro braços pareados sobre a **mesma** população, com um eixo de VP grande o bastante para dar poder ao teste de McNemar. O desenho abaixo mantém intactas a arquitetura de 5 fases, a semântica do LLM como filtro puro do Semgrep e a chave imutável do cache.

## Fases e arquivos tocados

| Fase | Arquivo | Mudança |
|---|---|---|
| 0 | `scripts/preencher_cache.py` | invocado (sem alteração de código) para os alvos TP faltantes |
| — | `run_pipeline.py` | `construir_casos_tp_dataset`, dataclass `Caso`, checkpoint composto, laço da matriz, `results/<run_id>/` |
| 1 | `src/fase1_semgrep.py` | inalterado; passa a ser chamado através do cache simbólico |
| 2 | `src/fase2_middleware.py`, `src/hidratacao.py` | inalterados; saída passa a ser persistida |
| — | `src/cache_simbolico.py` (novo) | persistência de alerta + contexto por caso |
| 3/4 | `src/fases3_4_llm.py` | reduzido a montagem de prompt; rede migra para provedores |
| 3/4 | `src/provedores/` (novo) | `base.py`, `gemini.py`, `openai.py` |
| — | `prompts/` (novo) | `baseline.md`, `especialista.md` |
| — | `data/catalogo_cwe.json` (novo) | fichas por CWE |
| 5 | `src/fase5_auditoria.py` | novas colunas do CSV |
| — | `src/metricas.py` | multi-braço, McNemar, export LaTeX |
| — | `tests/`, `pyproject.toml` (novos) | ruff + pytest |
| docs | `docs/PIPELINE.md`, `docs/SCRIPTS.md`, `README.md` | trilha nova, cache simbólico, `VP\|FP`, assimetria de rótulo |

## Decisões

### D1 — Trilha `TP_dataset` como função espelho, não como generalização de `construir_casos_fp`

`construir_casos_fp` recebe uma nova irmã `construir_casos_tp_dataset(dataset, ...)` em vez de virar uma função parametrizada por `ground_truth`. Motivo: as duas trilhas divergem em três pontos (filtro `_test.go`, valor de `gabarito`, prefixo do ID), e unificá-las produziria uma função com três flags cujo caminho FP é usado para gerar números já publicados. Duas funções pequenas são mais auditáveis para a banca do que uma com ramos condicionais.

- **IDs**: prefixo `TPD:` (`TPD:<finding_id>` para a location 0, `TPD:<finding_id>#<i>` para as demais), garantindo que nenhum ID novo colida com os `resultados_tcc*.csv` já gerados.
- **Índice de location**: vem da posição **original** na lista, antes de qualquer filtro — igual à trilha FP.
- **Filtro `_test.go`**: aplicado no mesmo ponto do filtro `.go`, removendo 9 dos 66 alvos. Alinha com o que `scripts/tp_reconstruct.py` já faz na trilha ouro.
- **`num_locations`**: capturado de `len(alerta["to_analyzer"]["locations"])` **antes** de qualquer filtro, propagado até o CSV.

**Alternativa descartada**: cravar agora um subconjunto de alta confiança (só entradas com location única). Rejeitada porque os 6 VPs detectados na medição vêm todos de entradas multi-location — filtrar zeraria o ganho. Grava-se `num_locations` e a decisão fica para a análise.

### D2 — Assimetria de rótulo é documentada, não corrigida

`metadata.source` é `semgrep` nos 261 FP (julgamento humano por alerta) e `cvefixes` nos 36 TP (mineração de commit de fix). Do lado TP, o rótulo afirma que o *commit* corrigiu uma CVE, não que *cada arquivo* é a vulnerabilidade — a entrada de CVE-2025-27616 / CWE-290 tem 11 locations, uma delas `router/middleware/header_test.go`. Isso é uma **limitação declarada** da amostra, registrada em `README.md`, `docs/PIPELINE.md` e no texto da monografia; não há dado disponível para corrigi-la sem reanotação manual, que está fora de escopo.

### D3 — Cache simbólico com chave `(repo, commit, arquivo, cwe, versao_ruleset)`

Arquivo JSON em `cache_simbolico/<owner>__<repo>/<commit>/<hash-do-caminho>__<cwe>.json`, contendo `{alerta, contexto_hidratado, status_semgrep, versao_ruleset, timestamp}`. O `contexto_hidratado` é gravado como string exata, e é ela que alimenta os quatro braços — é o que garante contexto **byte-a-byte idêntico**, requisito de validade interna da comparação pareada.

O cache simbólico é separado do `cache/` de fontes: o de fontes é imutável por construção (conteúdo de um commit), o simbólico depende da versão do ruleset do Semgrep, que muda. Por isso `versao_ruleset` entra no payload e uma divergência invalida a entrada. **Não** se mistura com `cache/` para não violar a invariante "o cache de fontes nunca invalida".

Ganho: os braços 2–4 pulam Fase 1 e 2 inteiras. O Semgrep é o custo de parede dominante nos casos `NAO_DETECTADO` (a maioria), então o corte fica em ~75% do tempo total do experimento. Não reduz o número de chamadas de LLM.

### D4 — Provedores atrás de uma interface mínima

```python
class RespostaLLM:      # dataclass
    veredito: str       # "VP" | "FP" | "ERROR"
    justificativa: str
    tokens_entrada: int
    tokens_saida: int
    custo_usd: float
    modelo: str

class ProvedorLLM(Protocol):
    def avaliar(self, prompt: str) -> RespostaLLM: ...
```

- **Autenticação em header**: `x-goog-api-key` (Gemini) e `Authorization: Bearer` (OpenAI). Hoje a chave vai na query string de `URL_API_GEMINI` (`src/config.py`), onde vaza em qualquer log de URL, traceback ou proxy. É correção de segurança, não refactor cosmético.
- **Backoff**: exponencial com jitter (`base * 2**n * uniform(0.5, 1.5)`, teto de 120 s), respeitando `Retry-After` quando presente, substituindo os delays fixos `[10, 30, 60]`. O throttle global `GEMINI_MIN_INTERVALO` é preservado e generalizado para intervalo mínimo por provedor.
- **Validação de schema**: `json.loads` cru é substituído por validação explícita — `veredito ∈ {VP, FP}` e `justificativa` presente. Resposta fora do schema vira `ERROR` com a justificativa carregando o texto bruto truncado, e é contabilizada como falha de esteira, nunca silenciosamente como FP.
- **Custo**: tabela de preço por 1M de tokens em `src/provedores/precos.py`, versionada com data de consulta. O custo é derivado, não medido — a tabela precisa estar declarada no texto.

**Dependência nova**: nenhuma. OpenAI é chamada via `requests` sobre a API REST, igual ao Gemini — o SDK oficial não justifica o peso num projeto deliberadamente enxuto.

### D5 — Catálogo de CWE como JSON versionado, congelado por hash

`data/catalogo_cwe.json`, uma ficha por CWE:

```json
{
  "CWE-327": {
    "definicao": "...",
    "heuristica_go": "...",
    "exemplo_vp": {"codigo": "...", "porque": "md5.Sum para hash de senha"},
    "exemplo_fp": {"codigo": "...", "porque": "md5.Sum para chave de cache/ETag"}
  }
}
```

**Os exemplos são escritos à mão.** A interseção de CWEs entre as trilhas FP e TP é de apenas 5 de 26 (CWE-22, 79, 352, 400, 918), então para as 21 CWEs que carregam quase todo o volume (79: 124 locations, 327: 93, 94: 92, 319: 86, 338: 82) **não existe nenhum VP real disponível** para extrair; e os VPs que existem são escassos demais para canibalizar sem contaminar o conjunto de avaliação.

- **Padrão dos exemplos**: mesma API, contextos opostos. CWE-327 — VP: `md5.Sum` para hash de senha; FP: `md5.Sum` para chave de cache/ETag. CWE-338 — VP: `math/rand` para token de sessão; FP: `math/rand` para jitter de backoff. Isso força o modelo a decidir por contexto, não por reconhecimento de API.
- **Cobertura**: fichas completas para as **15** CWEs de maior volume mais uma ficha genérica de fallback. Medição sobre o dataset (locations `.go`, excluindo `_test.go`): 878 amostras em 50 CWEs; 12 fichas cobririam 79,8% e 15 cobrem 85,4% — o número "~12" da versão inicial era estimativa, não medida. O CSV grava `Ficha_CWE ∈ {especifica, fallback}` para permitir estratificar os resultados.
- **Execução isolada**: a redação das fichas é especificada como briefing autocontido em `tasks.md` (seção "Briefing da tarefa 5.3"), destacável do repositório. Isso não é conveniência: um executor sem acesso ao dataset **satisfaz o protocolo anti-viés por construção**, em vez de por promessa. O briefing carrega a lista nominal das CWEs, o schema do JSON, o padrão do par contrastante e os critérios de aceitação, porque quem o executa não pode consultar nada.
- **Protocolo anti-viés**, a declarar na monografia: os exemplos são escritos a partir da definição da CWE (MITRE) e da documentação da stdlib de Go, **sem consultar as amostras avaliadas**; o arquivo é congelado antes da primeira rodada e seu SHA-256 é gravado em cada linha do CSV (`Hash_Catalogo`). Uma linha cujo hash difere do arquivo atual é resultado de outra versão do catálogo e não pode ser misturada na mesma tabela.
- A **mesma ficha** alimenta a camada de heurística e a camada de few-shot do prompt especialista — não há duas fontes de verdade.

### D6 — Prompts em arquivo, com placeholders explícitos

`prompts/baseline.md` e `prompts/especialista.md`, renderizados por `str.format` com placeholders nomeados (`{contexto}`, `{cwe_id}`, `{cwe_nome}`, `{heuristica}`, `{exemplos}`). Sem engine de template: `format` basta e não adiciona dependência.

- **baseline** (zero-shot): system genérico de análise de segurança + código + alerta. **Sem** definição de CWE, **sem** heurística, **sem** exemplos. É a condição de controle — se ele receber qualquer camada da metodologia, o contraste do experimento morre.
- **especialista**: as três camadas da metodologia (definição formal da CWE, heurística semântica de Go, par few-shot VP/FP), todas vindas do catálogo.
- Ambos exigem o mesmo formato de saída JSON `{"veredito": "VP"|"FP", "justificativa": "..."}` — a diferença entre os braços tem que estar no conteúdo, não no contrato de saída.
- `Versao_Prompt` (hash curto do arquivo) vai para o CSV.

### D7 — Checkpoint por chave composta e layout de resultados

`carregar_processados` passa a indexar por `(ID_Caso, Modelo_LLM, Tipo_Prompt)`. Sem isso, ao rodar o segundo braço, todos os casos apareceriam como já processados e o braço sairia vazio — falha silenciosa, o pior modo de falha possível aqui.

Resultados vão para `results/<run_id>/` (`run_id` = timestamp UTC + hash curto do commit), com `resultados.csv` por braço e um `manifesto.json` registrando: `run_id`, commit do repositório, versão do Semgrep e do ruleset, hash do catálogo, hashes dos prompts, modelos e preços usados, contagem de casos por trilha, e horário de início/fim. Isso substitui os `resultados_tcc_N.csv` na raiz.

**Compatibilidade**: `carregar_processados` continua lendo os CSVs antigos da raiz, tratando linhas sem as colunas novas como pertencentes ao braço `(gemini-2.5-flash-lite, especialista)`. Nenhum resultado antigo é apagado.

### D8 — McNemar à mão

Comparação pareada entre dois braços sobre as amostras que ambos classificaram (`Status_Semgrep == DETECTADO` e veredito válido nos dois). Tabela 2x2 de discordâncias `(b, c)`; para `b + c < 25` usa-se o teste binomial exato, acima disso o qui-quadrado com correção de continuidade de Yates. Implementação em Python puro (`math.comb`), coerente com a decisão de não trazer scipy. Um teste unitário fixa os valores contra um exemplo canônico de referência.

O export LaTeX gera `tabela_braços.tex` e `tabela_mcnemar.tex` com `\begin{tabular}` prontos para `\input{}` no capítulo de resultados.

### D9 — Higiene com escopo contido

`pyproject.toml` com metadados + config do `ruff` (só as regras `E`, `F`, `I`; sem formatação automática em massa, que poluiria o diff e dificultaria a revisão da banca). `logging` substitui `print` no caminho de execução — o formato de console permanece equivalente para não quebrar quem lê a saída. A dataclass `Caso` substitui o dict solto, com os campos atuais mais `num_locations`. Testes unitários cobrem as funções puras: `classificar_cobertura_semgrep`, `classificar_acerto_llm`, `extrai_funcao`, `construir_casos_fp`, `construir_casos_tp_dataset`, backoff e McNemar.

`docs/PIPELINE.md` diz `TP|FP` onde o código usa `VP|FP`; unifica-se em **`VP|FP`** (o código é a fonte de verdade e `VP` é o termo em português usado no resto do material).

## Riscos

| Risco | Mitigação |
|---|---|
| Mesmo com a trilha nova, o eixo de VP fica pequeno (estimativa: 24% de 57 alvos ≈ 14 VPs detectados, contra 4 hoje) | Reportar o poder do teste explicitamente; `num_locations` no CSV permite análise de sensibilidade sem re-executar |
| Custo da rodada 2x2 acima do previsto | Contabilidade de custo por chamada no CSV desde o piloto; rodada-piloto pequena antes da final |
| Ruído do rótulo TP (arquivos do commit de fix que não são a vulnerabilidade) | Filtro `_test.go` + `num_locations` + limitação declarada no texto (D2) |
| Catálogo escrito à mão vazar informação das amostras | Protocolo anti-viés (D5): escrito a partir de MITRE + stdlib, congelado por hash antes da primeira rodada |

## Escopo temporal

Esta mudança entrega a **infraestrutura** validada por uma rodada-piloto pequena. A rodada final do experimento e a redação dos resultados são trabalho subsequente, fora deste escopo.
