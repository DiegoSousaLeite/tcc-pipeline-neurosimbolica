## Why

O eixo de verdadeiros positivos da pipeline está quebrado: das 50 amostras vulneráveis de `tp_pairs.json` + `tp_pairs_osv.json`, **apenas 4 sobrevivem à Fase 1** (8% de detecção do Semgrep). Com 4 VPs, Precisão/Recall/F1/MCC ficam reféns de um punhado de casos e o teste de McNemar entre braços experimentais não tem poder estatístico para detectar diferença alguma — o experimento da Parte 2 nasceria inconclusivo.

Ao mesmo tempo, o dataset já contém **36 entradas `ground_truth="true_positive"` que a pipeline nunca carrega**, porque `construir_casos_fp` (`run_pipeline.py:92`) descarta tudo que não é `false_positive`. Elas não são redundantes com a trilha ouro: a trilha ouro analisa o `parent_commit` do fix com 1 arquivo por par (12 alvos distintos), enquanto o dataset aponta o `commit_hash` onde o SastBench de fato escaneou, com todas as suas `locations` (66 alvos por repo+commit+arquivo+cwe, 54 arquivos distintos). A interseção é de apenas 10 alvos, e só 11 dos 36 CVEs viraram par. Medição feita nesta investigação (Semgrep sobre o `cache/`, sem API): dos 25 alvos que já estavam em cache, **6 foram DETECTADOS (24%)** — e os 6 são alvos que a trilha ouro não cobre.

**Pergunta de pesquisa atendida:** esta mudança habilita a Parte 2 do TCC — a comparação da pipeline neuro-simbólica sob a matriz 2x2 (Gemini vs. GPT × prompt baseline zero-shot vs. prompt especialista de três camadas) e a bateria completa de métricas com significância estatística. Os itens 3, 4 e 8 são infraestrutura de suporte a essa pergunta.

## What Changes

- **Trilha TP do dataset (`TP_dataset`)**: função espelho de `construir_casos_fp` que carrega as entradas `ground_truth="true_positive"` com `gabarito=vulneravel`, filtrando arquivos `_test.go` (9 dos 66 alvos; a trilha ouro já aplica esse filtro em `scripts/tp_reconstruct.py`), e preenchimento do cache dos alvos faltantes via `scripts/preencher_cache.py`. Complementar às trilhas `TP_ouro` e `TP_prata`, não substituta.
- **Coluna `Num_Locations` no CSV**, gravando a contagem de locations da entrada de origem de cada caso, para permitir análise de sensibilidade post-hoc (17 dos 66 alvos vêm de entradas com location única; 38 vêm de entradas com 7+) sem re-executar o experimento.
- **Documentação da assimetria de rótulo entre trilhas**: `metadata.source` é `semgrep` nos 261 FP (julgamento por alerta) mas `cvefixes` nos 36 TP (mineração de commit de fix). O argumento do README de que "cada location é um achado independente e rotulado" só vale simetricamente do lado FP.
- **Runner da matriz experimental 2x2** com checkpoint por chave composta `(ID_Caso, Modelo_LLM, Tipo_Prompt)`. **BREAKING**: `carregar_processados` hoje indexa só por `ID_Caso` e pularia todos os braços novos como se estivessem prontos.
- **Cache do resultado simbólico** (alerta do Semgrep + contexto hidratado, por caso) em disco, para que os braços 2–4 executem apenas a chamada de LLM.
- **Camada de provedores de LLM** com implementações Gemini e OpenAI, chave de API em header (`x-goog-api-key` / `Authorization: Bearer`) em vez de query string na URL, backoff exponencial com jitter respeitando `Retry-After`, validação de schema da resposta (`veredito ∈ {VP, FP}`) e registro de tokens/custo por chamada no CSV.
- **Catálogo de triagem por CWE** versionado: definição formal, heurística semântica de Go e par mínimo VP/FP **escrito à mão** por CWE, com fichas completas para as 15 CWEs de maior volume (85,4% das amostras, medido) e uma ficha genérica de fallback.
- **Prompts como templates versionados** em `prompts/`, tirando o f-string embutido de `src/fases3_4_llm.py`.
- **Métricas comparativas**: tabela lado a lado dos 4 braços, teste de McNemar pareado e export de tabela LaTeX pronta para o capítulo de resultados.
- **Higiene**: `pyproject.toml` + `ruff`, `logging` em vez de `print`, dataclass `Caso`, testes unitários das funções puras, resultados em `results/<run_id>/` com manifesto, e unificação do veredito `VP|FP` entre código e `docs/PIPELINE.md` (que hoje diz `TP|FP`).

## Capabilities

### New Capabilities
- `trilha-tp-dataset`: carregamento das amostras `ground_truth="true_positive"` do dataset como casos de gabarito vulnerável, com filtro de arquivos de teste, rastreio de `num_locations` e registro da assimetria de rótulo entre trilhas.
- `matriz-experimental`: execução da matriz 2x2 (modelo × tipo de prompt) com checkpoint por chave composta, identidade de execução (`run_id`) e manifesto de rodada.
- `cache-simbolico`: persistência em disco do alerta do Semgrep e do contexto hidratado por caso, garantindo que todos os braços vejam contexto byte-a-byte idêntico.
- `provedores-llm`: abstração de provedor com implementações Gemini e OpenAI, autenticação por header, backoff com jitter, validação de schema e contabilidade de tokens/custo.
- `catalogo-cwe`: catálogo versionado por CWE (definição, heurística de Go, par VP/FP manual) com protocolo anti-viés declarado e hash congelado.
- `prompts-versionados`: templates de prompt em arquivo (baseline zero-shot e especialista de três camadas), com identificação da versão no CSV.
- `metricas-comparativas`: comparação entre braços, teste de McNemar e export LaTeX.

### Modified Capabilities
Nenhuma — `openspec/specs/` está vazio; não há specs publicadas cujos requisitos mudem.

## Impact

**Código**
- `run_pipeline.py` — nova função `construir_casos_tp_dataset`, dataclass `Caso`, checkpoint por chave composta, laço da matriz 2x2, saída em `results/<run_id>/`.
- `src/fase5_auditoria.py` — novas colunas (`Num_Locations`, `Ficha_CWE`, `Tokens_*`, `Custo_USD`, `Versao_Prompt`, `Hash_Catalogo`); **CSVs existentes ficam com cabeçalho antigo**.
- `src/fases3_4_llm.py` — dividido: montagem de prompt (a partir de `prompts/`) separada da chamada de rede, que migra para a nova camada de provedores.
- `src/metricas.py` — passa a ler múltiplos CSVs/braços; ganha McNemar e export LaTeX.
- Novos: `src/provedores/`, `src/cache_simbolico.py`, `prompts/`, `data/catalogo_cwe.*`, `tests/`, `pyproject.toml`.
- `scripts/preencher_cache.py` — invocado para os alvos TP faltantes (só download, não exige git).

**Documentação**
- `docs/PIPELINE.md` (unificar `VP|FP`, documentar trilha `TP_dataset` e cache simbólico), `docs/SCRIPTS.md`, `README.md` (corrigir a afirmação de simetria de rótulo entre trilhas).

**Dependências**
- Nenhuma dependência pesada nova: `ruff` fica em dev-dependency e o McNemar é implementado à mão (distribuição binomial exata / qui-quadrado com correção de continuidade), coerente com a decisão de não usar numpy/scipy.

**Custo e cota de LLM**
- A matriz 2x2 multiplica por 4 o número de chamadas de LLM sobre os casos `DETECTADO`. O tier grátis do Gemini (20 req/dia por modelo) é inviável para a rodada final — **billing é pré-requisito**. O cache simbólico corta ~75% do tempo de parede, mas não reduz o número de chamadas.

**Resultados invalidados**
- Os `resultados_tcc*.csv` na raiz **não são comparáveis** com os da Parte 2: a população de casos muda (entram os TP do dataset) e o cabeçalho do CSV muda. Eles permanecem válidos como registro da PoC da Parte 1 e devem ser arquivados, não deletados. Toda a bateria de métricas da Parte 2 precisa ser gerada do zero, após o catálogo de CWE estar congelado.

## Não-objetivos

- **Não reescrever `scripts/tp_reconstruct.py` para obter o diff via API do GitHub (`.patch`).** O diagnóstico de que os 83 CVEs OSV não reconstruídos caíram por falta de clone está errado: o log real da execução mostra "Falhas de reconstrução: 2" e os repositórios existiam no momento (a ordem foi fetch → tp_reconstruct → preencher_cache → apagar `repos/`). A causa real são os filtros de qualidade do próprio script — pré-filtro de CWE desconhecida, descarte de extração por janela e o guard anti-refatoração (com entrada OSV a variável `esperadas` fica sempre vazia, então todo fix que toca mais de 8 funções é descartado inteiro). Como o descarte acontece **depois** do diff, na análise dele, trocar a origem do diff não recupera nada.
- **Não preencher agora o CWE dos 45 advisories sem CWE via NVD.** Retorno menor e o guard anti-refatoração ainda consumiria boa parte do ganho. Ajustar `--max-funcs-por-fix` muda o critério de inclusão da amostra: é decisão metodológica do autor, não da implementação.
- **Não cravar um subconjunto de "alta confiança" de TPs nesta mudança.** Os 6 VPs detectados vêm todos de entradas multi-location; a decisão de filtrar por `num_locations` fica para depois, com o dado gravado no CSV.
- **Não alterar a arquitetura de 5 fases**, a semântica do LLM como filtro puro do Semgrep (só consultado quando a Fase 1 dispara), as duas matrizes separadas (cobertura simbólica e acerto neural), nem a chave imutável do cache por repo+commit+arquivo.
- **Não reintroduzir CodeQL** no caminho principal; `legacy/` permanece como referência histórica.
- **Não renumerar IDs de caso existentes** — os índices de location continuam vindo da posição original na lista.
- **Não executar a rodada final do experimento** dentro desta mudança: o escopo termina na infraestrutura pronta, validada por uma rodada-piloto pequena.
