# TCC — Pipeline Neuro-Simbólica de Triagem de Alertas SAST em Go

Pipeline que combina **Semgrep** (motor simbólico) com um **LLM** (Gemini, GPT ou
um modelo aberto rodando localmente via Ollama) para triar alertas de análise estática em código Go, reduzindo falsos positivos e
avaliando verdadeiros positivos. O LLM é um filtro puro do Semgrep: nada chega a
ele sem que a Fase 1 tenha alertado antes.

## Instalação

```
Python >= 3.10
pip install semgrep requests python-dotenv
```

Crie um `.env` na raiz com a chave do provedor que for usar:

```
GEMINI_API_KEY=sua_chave_aqui
```

As demais variáveis têm padrão e estão listadas em `docs/SCRIPTS.md`
(`src/config.py`).

Para o braço local não há chave: instale o [Ollama](https://ollama.com/download),
suba o serviço e baixe o modelo.

```bash
ollama pull qwen2.5-coder:7b
```

| Variável | Padrão | Para quê |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | endereço do servidor Ollama |
| `OLLAMA_NUM_CTX` | `8192` | janela de contexto do braço local |
| `OLLAMA_TIMEOUT` | `600` | segundos por requisição (cobre o carregamento dos pesos) |

## Como rodar

```bash
# O que seria executado, sem executar nada:
python run_pipeline.py --tudo --dry-run

# Subconjunto rápido (prioriza o que já está em cache):
python run_pipeline.py --amostra 20

# Pipeline completa, braço padrão (gemini-2.5-flash-lite + especialista):
python run_pipeline.py --tudo

# Matriz 2x2 completa: Gemini e GPT x baseline e especialista
python run_pipeline.py --tudo --matriz

# Braço local (sem custo e sem cota; exige o Ollama de pé):
python run_pipeline.py --tudo --modelo ollama:qwen2.5-coder:7b --prompt especialista

# Só cobertura simbólica, sem gastar cota de API:
python run_pipeline.py --tp-only --sem-llm

# Braço de TRIAGEM: positivo que o Semgrep não detectou também vai ao LLM,
# montado a partir da localização do gabarito. Multiplica as chamadas —
# pilote no provedor local antes de comprometer cota comercial.
python run_pipeline.py --tudo --modo-montagem triagem \
  --modelo ollama:qwen2.5-coder:7b --prompt baseline --prompt especialista
```

`--modo-montagem` tem dois valores e é **uniforme na rodada**:

| valor | o que chega ao LLM |
|---|---|
| `filtro` (padrão) | só o que o Semgrep emitiu e emparelhou — o LLM é filtro puro do motor simbólico |
| `triagem` | o mesmo, **mais** os casos de gabarito vulnerável que o Semgrep não detectou |

No modo `triagem` o `Status_Semgrep` **não muda** (um caso injetado continua
`NAO_DETECTADO`), o negativo nunca é injetado, e a coluna `Procedencia` do CSV
diz de onde cada candidato veio (`alerta` / `gabarito` / `N/A`). Os números dessa
rodada medem o componente neural isolado, **não o sistema em operação** — ver
`docs/PIPELINE.md`.

O Semgrep roda por padrão no motor aberto (CE), que rastreia *taint* apenas
dentro de um arquivo. `--entre-arquivos` liga a análise entre arquivos do
Semgrep Pro — **desligada por padrão**, porque ligá-la muda o conjunto de
alertas, invalida o cache simbólico daquela população e torna a rodada
incomparável com as anteriores. Ela exige um registro de viabilidade aprovado
(`python scripts/verificar_pro.py`), e aborta sem ele em vez de cair no CE em
silêncio. O que a medição de 2026-09-15 encontrou está em `docs/PIPELINE.md`.

Cada execução cria `results/<run_id>/`, com um CSV por braço
(`<modelo>__<prompt>.csv`) e um `manifesto.json`. Caractere inválido em nome de
arquivo é saneado — `ollama:qwen2.5-coder:7b` vira
`ollama-qwen2.5-coder-7b__especialista.csv` —, e o nome cru do modelo continua
em cada linha do CSV e no manifesto.

```bash
# Métricas de uma rodada (ou de um CSV avulso)
python src/metricas.py results/<run_id> --mcnemar --estratificar --latex

# Testes e lint
python -m pytest -q
python -m ruff check .
```

A Fase 0 (preparação dos pares TP) **já foi executada** — `tp_pairs.json` e
`tp_pairs_osv.json` estão versionados. Só é preciso repeti-la para regerar os
pares do zero; o procedimento está em `docs/PIPELINE.md`.

## Mapa do repositório

```
run_pipeline.py          # Orquestrador: 5 fases, N braços (modelo x prompt)
pyproject.toml           # Metadados, config do ruff e do pytest
src/                     # Módulos da pipeline (config, fonte, fases 1-5, métricas)
  provedores/            # Camada de rede por provedor de LLM + tabela de preços
prompts/                 # Templates de prompt: baseline.md e especialista.md
scripts/                 # Fase 0 (coleta e reconstrução de pares) e utilitários
data/                    # Dataset, catálogo de CWE e manifestos de fix commits
tp_pairs.json            # Pares TP ouro   (versionado: exige histórico git p/ regerar)
tp_pairs_osv.json        # Pares TP prata  (idem)
cache/                   # Arquivos-alvo por (repo, commit, caminho) — chave imutável
cache_simbolico/         # Alerta + contexto por caso (recriável; gitignored)
results/<run_id>/        # 1 CSV por braço + manifesto.json (gitignored)
tests/                   # pytest: funções puras, trilhas, cache, provedores, métricas
legacy/resultados_parte1/  # CSVs da PoC com CodeQL (não comparáveis com a Parte 2)
apresentacao/            # Slides da defesa (gitignored; ver nota no .gitignore)
docs/                    # Documentação de detalhe (abaixo)
```

## Documentação

| Arquivo | Responde |
|---|---|
| `docs/PIPELINE.md` | Como funciona: arquitetura das 5 fases, trilhas de entrada, as duas matrizes, métricas, catálogo de CWE, caches, provedores |
| `docs/SCRIPTS.md` | O que cada módulo e script faz: entradas, saídas, flags, variáveis de ambiente |
| `docs/ANALISE-RODADA-1.md` | Análise da rodada `20260730T180648Z-14d6af8`: o que ela mede (supressão de ruído, n≈792), o que ela não mede (detecção, 1 positivo válido), quais métricas levar para a monografia e com que ressalva, e a viabilidade de construir a classe positiva |
| `docs/OPENSPEC.md` | Comandos do OpenSpec e o fluxo de trabalho de mudanças |

> Antes de citar Recall, F1 ou MCC da Parte 2 em qualquer lugar, leia a seção 4.5
> de `docs/ANALISE-RODADA-1.md`: estas três métricas são governadas por uma
> classe positiva de 13 amostras das quais 12 têm emparelhamento inválido, e o
> relatório recomenda omiti-las.

O código da Parte 1 (fluxo CodeQL) não é mantido em cópia: vive no histórico do
Git e se recupera por caminho antigo.

```bash
git show HEAD:main.py               # orquestrador original (5 fases via CodeQL)
git show HEAD:src/fase1_codeql.py   # Fase 1: clone + database create + analyze
```
