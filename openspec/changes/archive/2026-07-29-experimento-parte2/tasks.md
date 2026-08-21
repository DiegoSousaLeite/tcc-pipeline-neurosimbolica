## 1. Fundação e higiene

- [x] 1.1 Criar `pyproject.toml` com metadados do projeto e configuração do `ruff` (regras `E`, `F`, `I`; sem reformatação em massa). Verificar: `ruff check .` executa e lista apenas violações reais.
- [x] 1.2 Criar `tests/` com `pytest` configurado no `pyproject.toml` e um teste trivial. Verificar: `pytest -q` passa.
- [x] 1.3 Criar a dataclass `Caso` (campos atuais do dict + `num_locations` + `origem`) e migrar `construir_casos_fp` e `construir_casos_tp` para devolvê-la. Verificar: `pytest -q` passa e `python run_pipeline.py --fp-only --amostra 3` lista os mesmos IDs de antes.
- [x] 1.4 Escrever testes unitários das funções puras existentes: `classificar_cobertura_semgrep`, `classificar_acerto_llm`, `extrai_funcao`, `construir_casos_fp`. Verificar: `pytest -q tests/` cobre as quatro e passa.
- [x] 1.5 Substituir `print` por `logging` em `run_pipeline.py`, `src/fase1_semgrep.py` e `src/fase5_auditoria.py`, mantendo a saída de console equivalente. Verificar: `python run_pipeline.py --fp-only --amostra 2` produz saída legível e sem `print` remanescente (`ruff check` + inspeção).
- [x] 1.6 Unificar o veredito para `VP|FP` em `docs/PIPELINE.md` (hoje diz `TP|FP`). Verificar: nenhuma ocorrência de `TP|FP` em `docs/`.

## 2. Trilha TP do dataset

- [x] 2.1 Implementar `construir_casos_tp_dataset` em `run_pipeline.py`: entradas `ground_truth == "true_positive"`, `gabarito = "vulneravel"`, `origem = "TP_dataset"`, IDs com prefixo `TPD:`, índice de location vindo da posição original. Verificar: teste unitário sobre um dataset fixture.
- [x] 2.2 Aplicar o filtro `_test.go` na nova trilha, no mesmo ponto do filtro `.go`. Verificar: teste unitário confirma que 9 dos 66 alvos são descartados no dataset real.
- [x] 2.3 Propagar `num_locations` (contado antes de qualquer filtro) do dataset até o `Caso`, nas três trilhas. Verificar: teste unitário com entrada de 11 locations e 3 descartes registra `11`.
- [x] 2.4 Ligar a nova trilha ao `main()` e às flags `--tp-only` / `--tudo`, somando-se a `TP_ouro` e `TP_prata`. Verificar: `python run_pipeline.py --tp-only` reporta as três trilhas na contagem inicial.
- [x] 2.5 Rodar `scripts/preencher_cache.py` para os alvos da trilha `TP_dataset` que não estão em cache. Verificar: reexecução do script reporta zero alvos faltantes.
- [x] 2.6 Medir a nova trilha offline (Semgrep sobre o cache, sem API) e registrar a taxa de detecção efetiva. Verificar: contagem de `DETECTADO` vs `NAO_DETECTADO` gravada no diretório da rodada-piloto.
- [x] 2.7 Documentar a assimetria de rótulo entre trilhas em `README.md` e `docs/PIPELINE.md`, qualificando a afirmação de "cada location é um achado independente" e citando o caso CVE-2025-27616 / CWE-290. Verificar: inspeção dos dois arquivos.

## 3. Cache do resultado simbólico

- [x] 3.1 Criar `src/cache_simbolico.py` com leitura/gravação por chave `(repo, commit, arquivo, cwe)`, payload contendo alerta, contexto hidratado, status e versão do ruleset. Verificar: teste unitário de ida e volta em diretório temporário.
- [x] 3.2 Implementar invalidação por divergência de versão de ruleset, sem tocar em `cache/`. Verificar: teste unitário com ruleset divergente força recomputação e nenhum arquivo de `cache/` é alterado.
- [x] 3.3 Integrar o cache simbólico às Fases 1 e 2 em `processar_caso`, incluindo os casos `NAO_DETECTADO`, com flag de desativação. Verificar: segunda execução do mesmo conjunto não invoca o Semgrep (medir tempo e/ou log).
- [x] 3.4 Adicionar teste que confirma contexto byte-a-byte idêntico entre duas leituras do mesmo caso. Verificar: `pytest -q` passa.

## 4. Camada de provedores de LLM

- [x] 4.1 Criar `src/provedores/base.py` com a dataclass `RespostaLLM` e o protocolo `ProvedorLLM`. Verificar: import limpo e `ruff check` sem erros.
- [x] 4.2 Implementar `src/provedores/gemini.py` com chave em header `x-goog-api-key` e remover a chave da URL em `src/config.py`. Verificar: teste unitário confirma que a URL montada não contém a chave.
- [ ] 4.3 Implementar `src/provedores/openai.py` com `Authorization: Bearer`, via `requests` sobre a API REST (sem SDK). Verificar: chamada real de fumaça com uma amostra retorna veredito válido.
- [x] 4.4 Implementar backoff exponencial com jitter, teto de espera e respeito a `Retry-After`, substituindo os delays fixos `[10, 30, 60]`; preservar o intervalo mínimo por provedor. Verificar: teste unitário com relógio e respostas simuladas.
- [x] 4.5 Implementar validação de schema da resposta (`veredito ∈ {VP, FP}`, justificativa presente); resposta malformada vira `ERROR`, nunca `FP`. Verificar: teste unitário com veredito inválido e com JSON quebrado.
- [x] 4.6 Criar `src/provedores/precos.py` com tabela de preços por 1M de tokens, datada e versionada, e derivar o custo por chamada. Verificar: teste unitário de cálculo de custo.
- [x] 4.7 Reduzir `src/fases3_4_llm.py` à montagem de prompt, delegando a rede aos provedores. Verificar: `ruff check` limpo e nenhuma chamada `requests` remanescente no arquivo.

## 5. Catálogo de triagem por CWE

- [x] 5.1 Conferir o ranking de CWEs por volume contra o dataset atual (contando locations `.go` e excluindo `_test.go`). Valores medidos em 2026-07-29: total de 878 locations em 50 CWEs; as 15 primeiras cobrem 85,4%. Verificar: o script de contagem reproduz a tabela da tarefa 5.3; qualquer divergência exige atualizar a lista antes de escrever as fichas.
- [x] 5.2 Definir o esquema de `data/catalogo_cwe.json` (definição, heurística de Go, exemplo VP, exemplo FP) e escrever a ficha genérica de fallback. Verificar: carregamento validado por teste unitário.
- [x] 5.3 Escrever à mão as 15 fichas de CWE conforme o briefing autocontido abaixo (seção "Briefing da tarefa 5.3"). Verificar: `data/catalogo_cwe.json` carrega, tem as 15 chaves esperadas, cada ficha tem os quatro campos não vazios, e cada par VP/FP usa a mesma API em contextos opostos.
- [x] 5.4 Implementar o carregador do catálogo com resolução para fallback e cálculo do SHA-256 do arquivo. Verificar: teste unitário com CWE coberta e CWE não coberta.
- [x] 5.5 Congelar o catálogo (commit dedicado) e registrar o protocolo anti-viés em `docs/PIPELINE.md`. Verificar: hash do arquivo commitado consta da documentação.

## 6. Prompts versionados

- [x] 6.1 Criar `prompts/baseline.md` — zero-shot, sem CWE, sem heurística, sem exemplos — com placeholders nomeados. Verificar: teste unitário confirma que o texto renderizado não contém heurística nem exemplos.
- [x] 6.2 Criar `prompts/especialista.md` com as três camadas alimentadas pelo catálogo. Verificar: teste unitário confirma presença das três camadas para CWE com ficha específica e com fallback.
- [x] 6.3 Implementar o renderizador por `str.format` com placeholders nomeados e o cálculo do hash curto de cada template. Verificar: `pytest -q` passa.
- [x] 6.4 Confirmar que os dois prompts exigem o mesmo contrato de saída JSON. Verificar: teste unitário compara a seção de contrato dos dois arquivos.

## 7. Runner da matriz 2x2 e auditoria

- [x] 7.1 Estender o cabeçalho do CSV em `src/fase5_auditoria.py` com `Num_Locations`, `Ficha_CWE`, `Versao_Prompt`, `Hash_Catalogo`, `Tokens_Entrada`, `Tokens_Saida`, `Custo_USD`. Verificar: uma execução curta gera CSV com todas as colunas preenchidas.
- [x] 7.2 Reescrever `carregar_processados` para indexar por `(ID_Caso, Modelo_LLM, Tipo_Prompt)`, tratando linhas antigas sem as colunas novas como braço `(gemini-2.5-flash-lite, especialista)`. Verificar: teste unitário com CSV antigo e CSV novo misturados.
- [x] 7.3 Implementar o laço da matriz no `run_pipeline.py` com seleção de braços por CLI, garantindo que `NAO_DETECTADO` nunca dispare chamada de LLM em nenhum braço. Verificar: execução com `--amostra` pequena e chave de API ausente falha só nos braços com casos detectados.
- [x] 7.4 Implementar `results/<run_id>/` com `manifesto.json` (run_id, commit, versões de Semgrep e ruleset, hashes de catálogo e prompts, modelos, preços, contagens por trilha, horários). Verificar: manifesto gerado e completo após rodada curta.
- [ ] 7.5 Rodada-piloto pequena nos quatro braços, com billing ativo, para validar a esteira ponta a ponta. Verificar: `results/<run_id>/` com quatro CSVs, custos registrados e nenhum caso em categoria de erro inesperada.

## 8. Métricas comparativas

- [x] 8.1 Refatorar `src/metricas.py` para consolidar uma rodada inteira a partir de `results/<run_id>/`, mantendo a leitura dos CSVs antigos da Parte 1. Verificar: métricas de um CSV antigo saem idênticas às atuais.
- [x] 8.2 Gerar a tabela comparativa lado a lado dos braços, com as duas matrizes ainda separadas. Verificar: saída da rodada-piloto tem uma linha por braço.
- [x] 8.3 Implementar estratificação por trilha, por `Num_Locations` e por origem da ficha de CWE. Verificar: as três estratificações rodam sobre o CSV do piloto.
- [x] 8.4 Implementar o teste de McNemar em Python puro (binomial exato para `b+c < 25`, qui-quadrado com correção de Yates acima), restrito às amostras pareadas com veredito válido. Verificar: teste unitário fixa os valores contra um exemplo canônico de referência.
- [x] 8.5 Sinalizar poder estatístico limitado quando o número de amostras vulneráveis avaliadas for pequeno, e sinalizar divergência de hash de catálogo. Verificar: saída do piloto exibe os avisos quando aplicável.
- [x] 8.6 Implementar o export de `tabela_bracos.tex` e `tabela_mcnemar.tex` no diretório da rodada. Verificar: os arquivos compilam via `\input{}` num documento LaTeX mínimo.

## 9. Documentação e fechamento

- [x] 9.1 Atualizar `docs/PIPELINE.md` com a trilha `TP_dataset`, o cache simbólico, a camada de provedores e o novo cabeçalho do CSV. Verificar: inspeção do arquivo contra a implementação.
- [x] 9.2 Atualizar `docs/SCRIPTS.md` e `README.md` com a nova interface de uso do runner (seleção de braços, `run_id`, `results/`). Verificar: os comandos documentados executam como descrito.
- [x] 9.3 Arquivar os `resultados_tcc*.csv` da raiz sob um diretório de legado, declarando na documentação que são da Parte 1 e não comparáveis com a Parte 2. Verificar: raiz sem CSVs soltos e nota presente no `README.md`.
- [x] 9.4 Rodar `ruff check .` e `pytest -q` em estado limpo. Verificar: ambos passam sem erro.

---

## Briefing da tarefa 5.3 — Catálogo de triagem por CWE

> Esta seção é **autocontida por desenho**: ela deve ser executável por alguém (ou por um modelo) que não tem acesso a este repositório nem ao dataset avaliado. Essa é uma exigência metodológica, não uma conveniência — ver "Restrição de isolamento" abaixo.

### Contexto mínimo

Uma pipeline de triagem de alertas de análise estática (SAST) em código **Go** usa um LLM para decidir se cada alerta é verdadeiro positivo (VP) ou falso positivo (FP). O catálogo produzido nesta tarefa alimenta duas camadas do prompt especialista: a **heurística** e os **exemplos few-shot**.

### Restrição de isolamento (obrigatória)

As fichas SHALL ser escritas **exclusivamente** a partir de:
1. a definição formal da CWE no catálogo MITRE, e
2. a documentação da biblioteca padrão de Go.

É **proibido** consultar, inspecionar ou se inspirar em qualquer amostra do material avaliado (o dataset de alertas, os repositórios em `cache/`, ou qualquer CSV de resultados). Nenhum trecho de código de uma amostra pode aparecer nos exemplos. O objetivo é que o conjunto few-shot não carregue informação do conjunto de avaliação — se essa restrição for violada, os resultados do experimento ficam inválidos e o protocolo declarado no texto da monografia deixa de ser verdadeiro.

### Idioma

Todo o conteúdo textual em **português do Brasil**. Comentários dentro dos exemplos de código também. Identificadores de código em inglês, como é idiomático em Go.

### Formato de saída

Um único arquivo JSON, `data/catalogo_cwe.json`, com esta estrutura exata:

```json
{
  "CWE-327": {
    "definicao": "Uso de algoritmo criptográfico quebrado ou de risco...",
    "heuristica_go": "Em Go, procurar por crypto/md5 e crypto/sha1 em caminhos de autenticação, assinatura ou armazenamento de credencial. O mesmo import em caminho de deduplicação, cache ou checksum não criptográfico não caracteriza a fraqueza.",
    "exemplo_vp": {
      "codigo": "func hashSenha(senha string) string {\n    soma := md5.Sum([]byte(senha))\n    return hex.EncodeToString(soma[:])\n}",
      "porque": "md5.Sum aplicado a credencial: hash rápido e sem sal, vulnerável a busca exaustiva e a colisão."
    },
    "exemplo_fp": {
      "codigo": "func chaveCache(url string) string {\n    soma := md5.Sum([]byte(url))\n    return hex.EncodeToString(soma[:])\n}",
      "porque": "md5.Sum usado como chave de cache/ETag: propriedade exigida é dispersão, não resistência a adversário."
    }
  }
}
```

Regras de formato:
- Chaves no padrão `"CWE-<número>"`, exatamente como na lista abaixo.
- `definicao`: 1 a 3 frases, derivadas da descrição MITRE, sem copiar o texto literalmente.
- `heuristica_go`: o sinal concreto a procurar em Go (pacote, função, padrão de chamada) **e** a condição que separa VP de FP. Deve mencionar identificadores reais da stdlib.
- `codigo`: Go sintaticamente válido, ~5 a 15 linhas, autocontido o suficiente para ser lido isolado. Imports omitidos.
- `porque`: 1 frase explicando o que torna aquele contexto vulnerável ou seguro.
- Adicionar também a chave `"__fallback__"` com uma ficha genérica, aplicável a qualquer CWE fora da lista (definição genérica de "alerta de segurança a triar", heurística genérica de alcançabilidade e mitigação, e um par VP/FP genérico).

### Padrão obrigatório do par VP/FP

O exemplo VP e o exemplo FP **devem usar a mesma API** em **contextos opostos**. Isso é o ponto central da tarefa: se o par contrastar APIs diferentes, o modelo aprende a reconhecer a API em vez de julgar o contexto, e o catálogo perde a função.

Dois pares já decididos, use-os como modelo de calibragem:

| CWE | Exemplo VP | Exemplo FP |
|---|---|---|
| CWE-327 | `md5.Sum` para hash de senha | `md5.Sum` para chave de cache/ETag |
| CWE-338 | `math/rand` para token de sessão | `math/rand` para jitter de backoff |

### As 15 CWEs (medidas por volume de amostras, cobrem 85,4%)

| # | CWE | Amostras | Nome |
|---|---|---|---|
| 1 | CWE-79 | 125 | Cross-site Scripting |
| 2 | CWE-327 | 93 | Uso de algoritmo criptográfico quebrado ou de risco |
| 3 | CWE-94 | 92 | Injeção de código |
| 4 | CWE-319 | 86 | Transmissão de informação sensível em texto claro |
| 5 | CWE-338 | 82 | Uso de PRNG criptograficamente fraco |
| 6 | CWE-665 | 75 | Inicialização inadequada |
| 7 | CWE-328 | 41 | Uso de hash fraco |
| 8 | CWE-614 | 27 | Cookie sensível sem o atributo Secure |
| 9 | CWE-601 | 25 | Redirecionamento aberto para site não confiável |
| 10 | CWE-470 | 19 | Uso de entrada controlada externamente para selecionar classe ou código (reflexão insegura) |
| 11 | CWE-115 | 18 | Interpretação incorreta de entrada |
| 12 | CWE-352 | 18 | Cross-Site Request Forgery |
| 13 | CWE-681 | 18 | Conversão incorreta entre tipos numéricos |
| 14 | CWE-1004 | 17 | Cookie sensível sem o atributo HttpOnly |
| 15 | CWE-667 | 14 | Travamento inadequado (locking) |

Confirme os nomes contra o catálogo MITRE antes de escrever — a coluna acima é referência de trabalho, não fonte canônica.

### Notas por CWE que merecem atenção no contraste

- **CWE-79** em Go: o contraste natural é `html/template` (escapa por padrão → FP) versus `text/template` ou escrita direta no `http.ResponseWriter` (→ VP). Mantenha a mesma API nos dois lados sempre que possível; onde a distinção for inevitavelmente entre dois pacotes, deixe isso explícito no campo `porque`.
- **CWE-319** e **CWE-614**/**CWE-1004**: o sinal costuma estar em configuração (`http://` literal, `TLSClientConfig.InsecureSkipVerify`, campos de `http.Cookie`), não em fluxo de dados. A heurística deve refletir isso.
- **CWE-681**: em Go o padrão é conversão entre inteiros de larguras diferentes (`int64` → `int32`, `int` → `uint`) sem verificação de faixa. O FP contrastante é a mesma conversão com o valor comprovadamente limitado antes.
- **CWE-667**: contraste entre `sync.Mutex` destravado em todos os caminhos de retorno (via `defer`) e caminho de erro que retorna sem destravar.
- **CWE-115**: CWE de definição vaga; se a ficha específica ficar fraca demais para ser útil, registre isso e prefira encaminhar essa CWE ao fallback — anote a decisão para o texto da monografia.

### Critério de aceitação

1. `data/catalogo_cwe.json` é JSON válido e carrega sem erro.
2. Contém exatamente as 15 chaves da tabela mais `"__fallback__"`.
3. Cada ficha tem `definicao`, `heuristica_go`, `exemplo_vp` e `exemplo_fp`, todos não vazios.
4. Cada `exemplo_vp.codigo` e `exemplo_fp.codigo` é Go sintaticamente válido.
5. Em cada par, VP e FP usam a mesma API central, ou o desvio está justificado em `porque`.
6. Nenhum trecho de código provém do material avaliado.
