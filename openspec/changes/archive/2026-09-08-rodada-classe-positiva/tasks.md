## 1. Colheita e ponto de inspeção

- [x] 1.1 Conferir que as três mudanças anteriores estão implementadas e a suíte passa, antes de gastar rede. Verificar: `python -m pytest tests/ -q` passa integralmente e `python -c "from src.ruleset import cwes_alcancaveis; print(len(cwes_alcancaveis('go')))"` responde.
- [x] 1.2 Executar a colheita filtrada com alvo inicial generoso. Verificar: o pool de fixes é gerado e a execução termina sem erro.
  - Comando: `python scripts/osv_harvest_go.py --alvo 300 --por-repo 5 --max-scan 8000` (exit 0).
  - Alvo 300 escolhido pelo funil medido na rodada anterior: 107 vulneráveis na população → 1 veredito de LLM (0,93%); dos 34 pares `TP_prata`, só 13 (38%) com CWE alcançável. Um alvo de 30 seria dimensionar no escuro contra uma perda de duas ordens de grandeza.
  - Saída: `data/tp_fixes_osv_alcancavel.json`, 300 candidatas.

  ---
  **REVISADO — segunda colheita.** Os números acima são da primeira colheita (300
  candidatas / 257 pares). A pedido do autor, a colheita foi escalada para
  esgotar a fonte e os valores finais desta rodada são os registrados na tarefa
  5.3 e em `docs/ANALISE-RODADA-3.md`: **810 candidatas, 690 pares, 2328 casos na
  população, 19 vulneráveis com veredito de LLM.**

- [x] 1.3 PONTO DE INSPEÇÃO (D1) — ler o relatório da colheita ANTES de prosseguir e registrar nesta tarefa: quantas candidatas aceitas, distribuição por CWE, quantas recusadas por inalcançabilidade e por qual CWE, e a data do snapshot do ruleset. Decidir aqui se o rendimento justifica seguir para a reconstrução, que é a etapa cara. Verificar: os quatro números ficam registrados nesta tarefa.

  **(a) Candidatas aceitas:** 300 de 1.646 entradas varridas (o dump tem 9.113 vulns Go; a varredura parou ao atingir o alvo, não por esgotar a fonte). 194 repositórios distintos, 20 CWEs distintas.

  **(b) Distribuição por CWE aceita:**

  | CWE | n | | CWE | n | | CWE | n | | CWE | n |
  |---|---|---|---|---|---|---|---|---|---|---|
  | 22 | 61 | | 400 | 30 | | 89 | 13 | | 798 | 3 |
  | 200 | 41 | | 78 | 16 | | 362 | 10 | | 327 | 2 |
  | 918 | 37 | | 476 | 15 | | 94 | 9 | | 328/319/338/115/326 | 1 cada |
  | 79 | 33 | | 345 | 13 | | 352 | 7 | | 601 | 5 |

  **(c) Recusadas por inalcançabilidade:** 1.643, com a cauda concentrada em
  `(sem CWE declarada)` 366, CWE-863 110, CWE-284 67, CWE-862 64, CWE-20 60,
  CWE-287 55, CWE-770 50, CWE-269 44, CWE-285 42, CWE-639 34, CWE-306 29,
  CWE-295 26 — mais uma cauda longa de ~190 CWEs com contagem ≤ 24.

  **(d) Snapshot do ruleset:** `https://semgrep.dev/c/p/default`, 1.074 regras,
  obtido em `2026-07-31T00:21:45-03:00`.

  **Revalidação do snapshot (mitigação do risco de deriva do ruleset).** O
  intervalo entre o snapshot e esta execução é de 39 dias, que o design manda
  revalidar. Busquei o ruleset corrente para caminho separado, sem sobrescrever
  o cache: **1.074 regras, as mesmas 34 CWEs alcançáveis em Go, zero perdidas e
  zero ganhas**. Nenhuma das 300 candidatas tem CWE que saiu do ruleset. O risco
  está fechado para esta janela.

  **Decisão: prosseguir para a reconstrução.** O filtro rende — 300 aceitas em
  20 CWEs distintas e 194 repos. A projeção honesta, porém, precisa ficar
  registrada aqui e não ser descoberta na tarefa 5.2: ao rendimento histórico de
  reconstrução (100 candidatas → 34 pares, 34%) as 300 dão ~100 pares, e à taxa
  de detecção medida sobre casos de CWE alcançável da rodada anterior (1 de 32 =
  3,1%) isso projeta ~3 casos chegando ao LLM, não 30. A projeção é de amostra
  única (n=32, 1 acerto) e larga demais para decidir por ela; a única forma de
  substituí-la por medição é executar. Prossegue-se porque o custo é rede e
  tempo, não dinheiro nem cota, e porque o resultado é publicável nos dois
  sentidos (D2 e a seção de riscos do design).
- [x] 1.4 Se o relatório indicar que o filtro recusa tudo por defeito (e não por escassez real da OSV), parar e abrir mudança própria em vez de prosseguir. Verificar: a distinção entre escassez e defeito fica registrada, com a evidência que a sustenta.

  **É escassez, não defeito.** Três evidências:

  1. **O filtro aceita.** 300 candidatas passaram, distribuídas em 20 CWEs
     distintas. Um filtro defeituoso que recusasse por construção não teria
     aceitado nada, e o script tem guarda explícita para esse caso
     (`osv_harvest_go.py`: "NENHUMA candidata sobreviveu").
  2. **A recusa é concentrada, não uniforme.** 366 das 1.643 recusas (22%) são
     de advisories que **não declaram CWE alguma** — nada a ver com o ruleset. O
     restante concentra-se na família de controle de acesso (863, 284, 862, 285,
     269, 306: 356 recusas somadas) e em validação de entrada genérica (CWE-20:
     60). São fraquezas de **lógica de autorização**, que regra sintática do
     Semgrep não expressa: não há padrão de código que diga "faltou checar
     permissão aqui". A ausência delas no ruleset é propriedade da análise
     sintática, não bug do filtro.
  3. **As CWEs aceitas são exatamente as sintaticamente expressáveis** —
     path traversal (22), SSRF (918), XSS (79), injeção de comando (78) e de SQL
     (89), credencial embutida (798), cripto fraca (327/328/326). O corte cai
     onde a teoria prevê que caia.

## 2. Reconstrução dos pares e cache

- [x] 2.1 Reconstruir os pares com `scripts/fetch_raso.py` sobre a saída da colheita. Verificar: a execução termina e reporta quantos arquivos foram obtidos.
  - `python scripts/fetch_raso.py --input data/tp_fixes_osv_alcancavel.json` (exit 0).
  - **192/192 repositórios** com ao menos 1 commit; 296 dos 300 commits de fix obtidos. 4 falhas, todas por ref reescrita no remoto (`upload-pack: not our ref`): `filebrowser` ×3, `go` ×1. `repos/` ficou com 6,4 GB — esqueletos descartáveis depois do preenchimento do cache.
- [x] 2.2 Gerar o pool de pares com `scripts/tp_reconstruct.py`, gravando no caminho que a trilha `TP_alcancavel` lê. Verificar: o pool existe e `python run_pipeline.py --trilha TP_alcancavel --dry-run` lista os casos.
  - `python scripts/tp_reconstruct.py --input data/tp_fixes_osv_alcancavel.json` (exit 0). O sufixo derivado do nome do input faz `OUT_FILE` virar `tp_pairs_osv_alcancavel.json`, que é exatamente `run_pipeline.TP_PAIRS_ALCANCAVEL` — conferido antes de executar, para que `tp_pairs.json` (o `OUT_FILE` padrão) não fosse sobrescrito.
  - **257 pares** reconstruídos, 83 repositórios distintos, 14 CWEs: 918 (60), 22 (51), 400 (30), 79 (30), 200 (22), 78 (14), 345 (14), 94 (10), 89 (7), 362 (5), 601 (5), 476 (4), 352 (4), 327 (1). Todos os 257 com `parent_commit` e `arquivo` preenchidos. 7 falhas de reconstrução (pai do commit ausente no fetch raso) e 2.814 descartes por janela/fora do dataset.
  - Rendimento acima da projeção do D1: esperavam-se ~100 pares (34% histórico), vieram 257 — um fix altera várias funções, e cada função vira par.
  - `python run_pipeline.py --tudo --trilha TP_alcancavel --dry-run` → **514 casos** (257 pares × 2). A invocação da tarefa precisa de `--tudo` junto: `--trilha` é filtro, não modo.
  - População completa passa de 948 para **1462** casos (FP=791, TP_ouro=32, TP_prata=68, TP_dataset=57, TP_alcancavel=514).

  ---
  **REVISADO — segunda colheita.** Os números acima são da primeira colheita (300
  candidatas / 257 pares). A pedido do autor, a colheita foi escalada para
  esgotar a fonte e os valores finais desta rodada são os registrados na tarefa
  5.3 e em `docs/ANALISE-RODADA-3.md`: **810 candidatas, 690 pares, 2328 casos na
  população, 19 vulneráveis com veredito de LLM.**

- [x] 2.3 Confirmar que `tp_pairs.json` e `tp_pairs_osv.json` permanecem intactos — o primeiro é irrecuperável, o segundo guarda os pares inalcançáveis que são evidência. Verificar: `sha256sum` dos dois coincide com o de antes das execuções.
  - Conferido depois da colheita, do fetch raso e da reconstrução — os dois hashes coincidem com os tomados antes de qualquer escrita:
    - `tp_pairs.json` → `3c72a66e3502ebac65d294a97d9136e22276fdfa07df0281db04a53648719624`
    - `tp_pairs_osv.json` → `202f7ae322e63c7c0bfae1ddef8a11205cb0137ffd6f25b3e7c287746401c860`
- [x] 2.4 Preencher o cache de fontes dos alvos novos com `scripts/preencher_cache.py`, para que a Fase 1 não dependa de rede. Verificar: `python run_pipeline.py --tudo --dry-run` não reporta alvo faltante.
  - **Lacuna encontrada:** `scripts/preencher_cache.py` monta `casos_unicos()` só com `TP_PAIRS_OURO` e `TP_PAIRS_PRATA` — `TP_PAIRS_ALCANCAVEL` ficou de fora quando a mudança `trilha-tp-alcancavel` foi implementada. Rodá-lo sozinho teria deixado os 360 alvos da trilha nova sem cache, e a Fase 1 dependeria de rede exatamente onde a tarefa quer que não dependa. Não corrigi o script (D5 — código de produto fora de escopo); usei a mesma API `src.fonte` a partir de um script de scratchpad. Fica registrado para mudança própria, junto do defeito da tarefa 3.1.
  - Trilha nova: 514 casos → **360 arquivos-alvo distintos, 346 extraídos de `repos/`, 14 já em cache, 0 baixados da rede, 0 faltando**.
  - Trilhas antigas: `preencher_cache.py --dry-run` → 766 alvos distintos, **0 faltando**.
  - `python run_pipeline.py --tudo --dry-run` → 1462 casos, cache com 1156 arquivos / 20,4 MB, nenhum alvo faltante.

## 3. Verificação antes da rodada

- [x] 3.1 Conferir a população montada: contagem por trilha, contagem por gabarito e 0 IDs duplicados. Verificar: script de inspeção reporta os três, e o total de casos `FP` continua 791.
  - **Bloqueio encontrado e resolvido fora desta mudança.** Na primeira inspeção a população tinha **18 identificadores repetidos**, todos na trilha `TP_alcancavel`: 46 casos envolvidos, **28 que sumiriam em silêncio** (o checkpoint por tripla trata o segundo como já gravado e `metricas.py` deduplica pela primeira ocorrência). Causa: `run_pipeline.construir_casos_tp` derivava o ID de `(prefixo, repo, CWE, função, versão)` **sem o arquivo**, e em Go o mesmo método aparece em vários arquivos do pacote alterados pelo mesmo fix — `Decode` em `commit.go`, `tag.go` e `tree.go` do `go-git` davam três casos com um ID só.
  - Conforme o não-objetivo *"defeito encontrado vira mudança própria"* e o D5, **não corrigi aqui**. Abri e implementei `identificador-de-caso-unico` (11/11 tarefas), que acrescenta o discriminador de arquivo aos pools com prefixo, congela os IDs de `TP_ouro`/`TP_prata` contra os CSVs das rodadas anteriores, faz a montagem abortar alto em colisão e fecha a lacuna de `scripts/preencher_cache.py`. Suíte: 284 testes.
  - **Resultado após o desbloqueio (população final, 690 pares):** 2328 casos, **2328 IDs distintos, 0 duplicados**.
    - por trilha: `FP`=791, `TP_ouro`=32, `TP_prata`=68, `TP_dataset`=57, **`TP_alcancavel`=1380**
    - por gabarito: 1531 seguros, **797 vulneráveis**
    - casos `FP`: **791**, inalterado
    - Os dois braços terminam com o **mesmo conjunto de 2328 identificadores**, o que mantém o McNemar pareado válido.
- [x] 3.2 Conferir que `versao_ruleset` e `versao_pareamento` do cache simbólico não divergem das correntes — divergência faria os 791 casos da classe negativa pagarem varredura de novo, multiplicando o tempo. Verificar: contagem de entradas do cache sob a versão corrente.
  - Correntes: `versao_ruleset = p/default`, `versao_pareamento = 2`.
  - **916 entradas em `cache_simbolico/`, 916 sob `('p/default', 2)`** — nenhuma divergente. Os 791 casos da classe negativa são servidos do cache; só os alvos novos pagam varredura.
- [x] 3.3 Registrar quantos casos vulneráveis da população têm CWE alcançável e quantos não têm, antes de rodar. É o denominador da taxa de sobrevivência. Verificar: as duas contagens ficam registradas nesta tarefa.
  - **797 casos vulneráveis na população: 722 com CWE alcançável, 75 sem** (9,41% inalcançáveis).
  - Comparação com a rodada anterior: eram 107 vulneráveis, 32 alcançáveis e 75 inalcançáveis (70,1%). Os 75 inalcançáveis são **os mesmos** — nenhum foi removido, como manda o não-objetivo. O que mudou é o denominador: a colheita filtrada acrescentou 690 vulneráveis, todos alcançáveis por construção, e a proporção de ponto cego cai de 70,1% para 9,41% sem que um único caso saia da população.
  - Por trilha (vulneráveis / alcançáveis / inalcançáveis): `TP_ouro` 16/4/12 · `TP_prata` 34/13/21 · `TP_dataset` 57/15/42 · `TP_alcancavel` 690/690/0.

## 4. Rodada

- [x] 4.1 Executar a rodada sob `run_id` novo, braço local, baseline e especialista. Se for interrompida, retomar com o mesmo `--run-id`; antes de retomar, remover as linhas em categoria de erro, que não são checkpointadas e virariam ID duplicado. Verificar: `manifesto.json` gravado e CSVs com o mesmo número de linhas em ambos os braços.
  - `run_id` = **`20260908T094808Z-9a00cb2`**, braços `(ollama:qwen2.5-coder:7b, baseline)` e `(…, especialista)`. Ollama 0.32.5, digest `dae161e27b0e`, Q4_K_M, 100% GPU, `num_ctx` 8192, semente 42 — mesma configuração da Rodada 2.
  - **Foi interrompida por exaustão de memória, e retomada.** A primeira passagem (2h14) terminou com 488 casos em `SEMGREP_ERROR`, todos da trilha nova, a partir do caso 908: `Semgrep rc=3221225794` = `0xC0000142` = `STATUS_DLL_INIT_FAILED` — o Semgrep não chegou a **iniciar**, porque o `llama-server` mantinha 11,6 GB residentes. A trilha nova é a única que exigia varredura fresca; as demais vinham do cache simbólico e nunca invocaram o Semgrep. Aritmética confirmatória: `974 reaproveitados, 0 gravados` = 948 antigos + 26 da trilha nova já cacheados por medição prévia.
  - Recuperação pelo procedimento previsto: backup dos CSVs, remoção das **490 linhas em categoria de erro** (488 `SEMGREP_ERROR` + 2 `API_ERROR`), descarga do modelo (4,0 → 15,2 GB livres), Fase 1 da trilha nova isolada com `--sem-llm` (**514/514, zero falhas**, 340 entradas gravadas no cache), e retomada com o mesmo `--run-id` (3min43, 46 chamadas de LLM, Fase 1 toda do cache).
  - **Estado final:** `manifesto.json` gravado; **2328 linhas em cada braço**, com conjuntos de identificadores idênticos.
  - Após a segunda colheita a rodada foi estendida sob o **mesmo `run_id`**: o checkpoint pulou os casos já avaliados e processou apenas os 870 novos, sem repetir chamada de LLM alguma. O veredito de um caso não depende do tamanho da população, então reaproveitá-los é legítimo. Quatro linhas ficaram órfãs (IDs que saíram do pool quando a reconstrução maior mudou a chave de dedup) e foram removidas dos dois braços de forma idêntica.
  - Recomendação de esteira que sai daqui: em máquina única, separar Fase 1 completa das fases neurais em duas invocações — motor simbólico e modelo local disputam a mesma memória.
- [x] 4.2 Conferir a integridade dos CSVs: 0 IDs duplicados, 0 linhas truncadas, contagem de `Status_Semgrep` por braço. Verificar: script de inspeção reporta os três.
  - **0 IDs duplicados** e **0 linhas truncadas** nos dois braços (após a limpeza descrita abaixo).
  - `Status_Semgrep` — baseline: `DETECTADO` 825, `NAO_DETECTADO` 1501, `API_ERROR` 2. Especialista: `DETECTADO` 827, `NAO_DETECTADO` 1501, 0 erros.
  - Falha de esteira não é checkpointada, então cada retomada regravou os 2 casos de `API_ERROR`, acumulando duplicatas no baseline. Foram deduplicados mantendo uma linha por caso.
  - Os 2 `API_ERROR` são os do grupo `be0de1ab:CWE-79` (`harness/harness`), laço degenerativo já documentado na Rodada 2 §6.2 — reapareceram na retomada, confirmando a reprodutibilidade.

## 5. Critério de aceite

- [x] 5.1 Calcular as métricas da rodada. Verificar: `python src/metricas.py results/<run_id_novo> --mcnemar` executa sem erro.
  - `python src/metricas.py results/20260908T094808Z-9a00cb2 --mcnemar` executou sem erro.
  - Matriz de acerto do LLM — baseline: n=825, VP/VN/FP/FN = 8/690/116/11, TRA **0,8497**. Especialista: n=827, VP/VN/FP/FN = 3/796/12/16, TRA **0,9819** (Rodada 1: 0,9851 · Rodada 2: 0,9874 — imóvel com a população 146% maior).
  - Matriz simbólica (n=2326): VP=19, VN=723, FP=806, FN=778; Recall **0,0238** (era 0,0093), TFN 0,9762, TRA 0,6453.
  - McNemar: n pareado 825, ambos acertam 693, **só baseline 5, só especialista 104**, ambos erram 23; χ²=88,11, **p < 0,0001**.
- [x] 5.2 CRITÉRIO DE ACEITE (D3) — confirmar que o aviso de PODER ESTATÍSTICO LIMITADO desapareceu, ou seja, ao menos 30 casos vulneráveis com veredito válido do LLM. Verificar: a saída de 5.1 não contém o aviso.
  - **NÃO ATINGIDO.** O aviso permanece nos dois braços: *"apenas 19 amostras vulneráveis chegaram ao LLM com veredito válido (mínimo sugerido: 30)"*.
  - `Recall`, `F1`, `MCC` e `TFN` do eixo neural continuam não reportáveis como conclusão. A metade não respondida da Q2 permanece sem resposta conclusiva.
  - Não é falha de execução: é a medição que a mudança existia para produzir. Ver 5.3.
- [x] 5.3 Medir e registrar a taxa de sobrevivência dos casos vulneráveis entre a colheita e a chegada ao LLM, para dimensionar uma eventual repetição com base em medição. Verificar: a proporção fica registrada nesta tarefa.
  - Funil final: **810 candidatas → 690 pares (85,2%) → 18 detectados = 18 no LLM**.
  - **Sobrevivência par → veredito de LLM: 18/690 = 2,61%.** População inteira: 19/797 = **2,38%** (era 1/107 = 0,93% na Rodada 2).
  - **O achado decisivo é a queda da taxa ao escalar:**

    | | 257 pares | 690 pares |
    |---|---|---|
    | vulneráveis detectados | 11 | 18 |
    | taxa | **4,28%** | **2,61%** |

    Triplicar a colheita multiplicou as detecções por 1,6 e **piorou a taxa**. Os primeiros pares eram a cabeça fácil do dump. Isso é retorno decrescente medido, não escassez de esforço — e sustenta a conclusão muito melhor do que o número absoluto sozinho.
  - É a resposta à incógnita central: **a CWE estar no ruleset não faz a regra disparar naquele código.** 97,4% dos casos vulneráveis de CWE comprovadamente alcançável não produzem alerta na CWE certa.
- [x] 5.4 Discriminar por trilha de origem quantos casos vulneráveis chegaram ao LLM, isolando o rendimento da colheita filtrada do rendimento do reaproveitamento. Verificar: contagem por `Origem` registrada.
  - Vulneráveis com veredito válido de LLM, por trilha: **`TP_alcancavel` 18, `TP_dataset` 1, `TP_ouro` 0, `TP_prata` 0**.
  - Taxas: `TP_alcancavel` 18/690 = 2,61% · `TP_dataset` 1/57 = 1,75% · `TP_ouro` 0/16 · `TP_prata` 0/34.
  - **O ganho veio inteiramente da colheita filtrada.** 18 dos 19 casos avaliados são dela; as duas trilhas de colheita antiga contribuíram com zero. O filtro funcionou no que prometia — a amostra saiu de 1 para 19 — mas 19 continua abaixo de 30.
  - Detecções por CWE: CWE-89 7 · CWE-79 5 · CWE-601 3 · CWE-614 2 · CWE-94 1 · CWE-918 1. **Zero** em CWE-22 (114 pares), CWE-400 (124), CWE-200 (92), CWE-345 (45) e CWE-78 (24) — 399 pares sem um único alerta na CWE certa.
- [x] 5.5 Se o critério não for atingido, registrar a taxa medida e voltar à tarefa 1.2 com alvo calculado a partir dela, sem refazer as etapas de código. Verificar: o alvo novo e o cálculo que o justifica ficam registrados.
  - **A segunda colheita foi executada, e esgotou a fonte.**

    | | 1ª colheita | 2ª colheita |
    |---|---|---|
    | `--alvo` / `--por-repo` | 300 / 5 | **1200 / 20** |
    | entradas varridas | 1.646 | **9.113 (dump inteiro)** |
    | candidatas | 300 | **810** |
    | repos no teto | 38 de 194 | **2 de 362** |
    | pares | 257 | **690** |
    | vulneráveis no LLM | 11 | **18** |

  - Com o teto em 20 só `mattermost/mattermost` e `gogs/gogs` o alcançam: afrouxá-lo mais não renderia candidatas. **As 810 são tudo o que o corpus Go da OSV oferece sob o critério de alcançabilidade.**
  - **Terceira alavanca medida e rejeitada:** `--incluir-janela` acrescentaria 156 pares, mas quase todos em CWEs de taxa zero (CWE-22 +78, CWE-200 +19, CWE-400 +17) — ganho esperado de **0,6 detecção** em troca de degradar a precisão do pool.
  - **Quarta alavanca deliberadamente recusada:** afrouxar `--max-funcs-por-fix`, o guarda anti-refactor. Ele descarta milhares de candidatos a par e elevaria o `n` com folga, mas num fix que altera 30 funções em 10 arquivos a maioria dos arquivos não carrega a vulnerabilidade. Marcá-los como vulneráveis injetaria falsos positivos no gabarito e **inflaria o recall artificialmente**. Pelo mesmo motivo a colheita não foi enviesada para as CWEs de alta detecção: selecionar os casos em que a ferramenta acerta mede a seleção, não a ferramenta.
  - **Não há mais alavanca sem mudar o objeto medido.** As opções restantes — outra linguagem, Semgrep Pro com taint entre arquivos, ou regras próprias para CWE-22 — mudam o escopo do TCC ou a variável do experimento. Ficam registradas em `docs/ANALISE-RODADA-3.md` §9 para decisão do autor.

- [x] 5.6 Registrar a proporção de casos vulneráveis de CWE inalcançável que permanecem na população, preservando a comparação com o achado dos 70,1% da rodada anterior. Verificar: contagem registrada e casos presentes na matriz de cobertura como ponto cego.
  - **75 dos 797 casos vulneráveis (9,41%) têm CWE inalcançável.** São **os mesmos 75** da Rodada 2, onde eram 70,09% de uma população vulnerável de 107. Nenhum foi removido.
  - Todos terminam em `NAO_DETECTADO` (verificado): 55 por `SEM_ALERTA`, 20 por `ALERTA_OUTRA_CWE`. Entram na matriz de cobertura como ponto cego simbólico e ficam fora da matriz de acerto do LLM.
  - **A queda de 70,1% para 9,41% é diluição, não correção.** O denominador cresceu com 690 vulneráveis alcançáveis por construção. A afirmação do capítulo de limitações continua verdadeira sobre o corpus a que se refere.

## 6. Preservação e registro

- [x] 6.1 Confirmar que `results/20260731T140000Z-af9bc32` e `results/20260730T180648Z-14d6af8` permanecem intactas. Verificar: contagem de linhas por braço e mtime inalterados. (Lembrete: `results/` está no `.gitignore`, então `git status` não observa esse diretório — a evidência é mtime e conteúdo.)
  - `20260731T140000Z-af9bc32`: mtime dos CSVs `2026-08-03 23:44:56`, 950 e 949 linhas — idênticos ao levantamento feito no início da sessão, antes de qualquer execução.
  - `20260730T180648Z-14d6af8`: mtime `2026-07-30 17:57:11`, 991 e 949 linhas — idem.
  - Nenhuma das duas foi tocada.
- [x] 6.2 Escrever `docs/ANALISE-RODADA-3.md` no formato da Rodada 2: identificação, composição da população, movimento das duas classes, TRA e proporção de FP filtrados, McNemar, e se a Q2 passou a ser respondível por inteiro. Declarar explicitamente que a comparação caso a caso com as rodadas anteriores não é válida, e por quê. Verificar: o documento existe e cita o `run_id` novo.
  - `docs/ANALISE-RODADA-3.md` escrito, citando `20260908T094808Z-9a00cb2`. Seções: identificação, composição da população, o funil que não abre, movimento das duas classes, TRA e FP filtrados, McNemar, ressalvas (ruleset revalidado, falha de memória, falhas de esteira, inalcançáveis) e a resposta à Q2.
  - A não comparabilidade caso a caso com as Rodadas 1 e 2 está declarada em bloco destacado no §1, **com o porquê**: a população difere em 514 casos, e métricas dependentes de composição (TRA simbólica, proporção de FP filtrados, contagens absolutas) mudam por composição, não por comportamento. O §4.3 mostra o caso concreto — a TRA simbólica salta de 0,1660 para 0,4445 sem que o motor tenha mudado.
- [x] 6.3 Confirmar que nenhum arquivo `.tex` foi tocado — a redação do TCC está fora do escopo destas mudanças. Verificar: `git status -- "*.tex"` não mostra alteração.
  - `git status --short -- "*.tex"` vazio. Nenhum arquivo `.tex` foi criado, alterado ou removido em nenhum momento.
