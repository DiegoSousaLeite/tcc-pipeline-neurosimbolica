## 1. Investigação prévia — resolve a questão em aberto antes de escrever código

- [x] 1.1 Inspecionar `src/hidratacao.py` e responder por escrito: a hidratação
      usa a linha do alerta para recortar o contexto, ou recorta o arquivo
      inteiro? Verificar: a resposta fica registrada em `design.md`, na seção de
      questões em aberto, com o trecho de código que a sustenta.
- [x] 1.2 Se usar a linha: decidir e registrar qual localização o candidato
      injetado carrega, de modo que os dois candidatos recebam contexto de mesma
      natureza. Verificar: a decisão vira uma entrada nova em `design.md` e o
      requisito de indistinguibilidade continua satisfazível.
- [x] 1.3 Confirmar como `src/metricas.py` lê múltiplas rodadas e se a leitura
      distingue séries por manifesto. Verificar: resposta registrada; se não
      distinguir, abrir tarefa em `5.`

## 2. Procedência do candidato

- [x] 2.1 Acrescentar o campo de procedência (`alerta` / `gabarito`) à estrutura
      de candidato em `src/fase2_middleware.py`. Verificar: teste que um candidato
      montado de alerta sai com procedência `alerta`.
- [x] 2.2 Propagar a procedência até o CSV em `src/fase5_auditoria.py`.
      Verificar: rodar um caso no modo filtro e conferir a coluna no CSV.
- [x] 2.3 Fazer `src/metricas.py` calcular as métricas para o conjunto completo e
      por procedência. Verificar: teste com CSV sintético contendo as duas
      procedências, conferindo que os três conjuntos de números batem à mão.
- [x] 2.4 Rodar uma rodada de modo filtro e confirmar que toda linha sai com
      procedência `alerta` e que os demais números são idênticos aos de antes.
      Verificar: diff contra o CSV da última rodada, ignorando a coluna nova.

## 3. Montagem do candidato a partir do gabarito

- [x] 3.1 Acrescentar o eixo de modo de montagem ao `run_pipeline.py`, com
      `filtro` como padrão, uniforme na rodada e registrado no manifesto.
      Verificar: teste que a invocação padrão não monta candidato de gabarito
      algum, e que o modo consta do manifesto.
- [x] 3.2 Implementar a montagem do candidato a partir da localização do gabarito
      para caso vulnerável em `NAO_DETECTADO`. Verificar: teste que um caso
      vulnerável não detectado produz candidato no modo triagem e nenhum no modo
      filtro.
- [x] 3.3 Garantir que `Status_Semgrep` e o motivo da não-detecção não são
      sobrescritos. Verificar: teste que um caso injetado sai do CSV com
      `NAO_DETECTADO` e o motivo preservado.
- [x] 3.4 Garantir que negativo nunca é injetado e que falha de esteira nunca
      vira candidato. Verificar: dois testes, um por condição.
- [x] 3.5 Implementar a precedência do emparelhamento sobre a injeção. Verificar:
      teste que caso vulnerável **detectado** sai com procedência `alerta` no modo
      triagem, e que nenhum candidato de gabarito é montado para ele.

## 4. Normalização — a guarda de integridade

- [x] 4.1 Convergir os dois caminhos de montagem para a mesma estrutura antes da
      hidratação, preenchendo com valor neutro os campos que o candidato de
      gabarito não tem. Verificar: teste que as duas estruturas têm exatamente o
      mesmo conjunto de chaves.
- [x] 4.2 Escrever o teste que monta os dois candidatos para o mesmo arquivo e a
      mesma CWE e compara as strings de prompt finais nos **dois** tipos de
      prompt. Verificar: as strings não permitem identificar a procedência; o
      teste falha se permitirem.
- [x] 4.3 Confirmar que a procedência não vaza para o prompt por nenhum caminho
      indireto — nome de regra, mensagem, contagem de alertas concorrentes.
      Verificar: inspeção do montador de prompt registrada no PR, além do teste
      de 4.2.

## 5. Grupo de controle e medição

- [x] 5.1 Emitir, junto das métricas da rodada de triagem, a comparação de acerto
      do LLM entre as duas procedências. Verificar: a tabela aparece na saída e no
      arquivo de métricas.
- [x] 5.2 Fazer a comparação carregar o aviso de poder estatístico limitado
      quando o grupo `alerta` tiver menos que o limiar. Verificar: teste com 19
      casos no grupo de controle emite o aviso.
- [x] 5.3 **Medir a vazão do provedor local** sobre 50 casos do modo triagem, com
      o modelo já carregado, e extrapolar para a população inteira. Verificar:
      segundos por chamada e a estimativa de parede para ~3.200 chamadas ficam
      registrados nesta tarefa. Nenhuma tarefa abaixo assume um número sem isto.

      **MEDIDO em 2026-09-15** — `results/vazao-5.3/`, 50 casos `--tp-only` em
      modo triagem, 2 braços (baseline + especialista) contra
      `ollama:qwen2.5-coder:7b` (Ollama 0.32.5, Q4_K_M, num_ctx 8192, 100 % GPU),
      modelo já carregado, Fases 1-2 servidas do cache simbólico.

      | medida | valor |
      |---|---|
      | chamadas com veredito | 50 |
      | parede da rodada | 412 s (6,9 min) |
      | **por chamada (parede)** | **8,23 s** |
      | mediana / p90 | 7,61 s / 11,16 s |
      | mín / máx | 4,71 s / 16,34 s |
      | tokens entrada / saída (médios) | 817 / 91 |

      **Extrapolação** (contagens exatas tiradas da Rodada 3,
      `results/20260908T094808Z-9a00cb2/`):

      | escopo | chamadas/braço | 2 braços | parede |
      |---|---|---|---|
      | piloto `--tp-only` (5.4) — inclui os **19 controles** | 815 | 1.630 | **≈ 3,7 h** |
      | população inteira (5b.2) | 1.605 | 3.210 | **≈ 7,3 h** |

      O piloto é subconjunto estrito da rodada completa: rodando os dois com o
      mesmo `--run-id`, o checkpoint reaproveita as 1.630 linhas e sobram ~1.580
      chamadas (≈ 3,6 h) para fechar 5b.2.

      **Achado precoce, n = 50:** todos os 50 candidatos injetados receberam
      veredito `FP` ("não é vulnerabilidade") — 50 Falsos Negativos, nos **dois**
      tipos de prompt. Recall 0 nos injetados nesta amostra. A amostra não
      continha nenhum positivo detectado, logo **não teve grupo de controle**;
      é por isso que 5.4 precisa cobrir as trilhas TP inteiras.
- [x] 5.4 Piloto do modo triagem sobre um subconjunto, com o provedor local.
      Verificar: métricas emitidas, com Recall, F1 e MCC preenchidos e a
      comparação entre procedências presente.

      **ARMADO, NÃO DISPARADO** (decisão de 2026-09-15: a máquina está ocupada
      pela `semgrep-pro-entre-arquivos`, e Semgrep e o modelo local disputam
      RAM). O subconjunto tem que ser **as trilhas TP inteiras** — é o único
      recorte que alcança os 19 positivos detectados, sem os quais não há grupo
      de controle e 5.5 fica sem resposta. 1.630 chamadas, ≈ 3,7 h (ver 5.3).

      **EXECUTADO em 2026-09-16 00:43–02:52** pelo gatilho, sem supervisão.
      776–780 vulneráveis com veredito por braço (mínimo de suficiência: 30).
      Recall, F1, MCC e TFN calculáveis pela primeira vez.

      Com o modelo já carregado e o Semgrep parado:

      ```bash
      python run_pipeline.py --tp-only --modo-montagem triagem \
        --modelo ollama:qwen2.5-coder:7b \
        --prompt baseline --prompt especialista \
        --run-id rodada-4-triagem

      python src/metricas.py results/rodada-4-triagem --mcnemar --estratificar
      ```

      O `--run-id` é o mesmo de 5b.2 de propósito: o checkpoint por tripla
      `(ID_Caso, Modelo_LLM, Tipo_Prompt)` reaproveita estas 1.630 linhas, e a
      rodada completa fica devendo só as ~1.580 chamadas da trilha FP.
- [x] 5.5 Ler o resultado do controle e decidir: se o acerto divergir muito entre
      procedências, **parar aqui** — registrar que o número da triagem não pode
      ser reportado como está e abrir change para investigar a causa, antes de
      gastar a execução longa. Verificar: decisão registrada em
      `docs/MAPA-TCC-O-QUE-REESCREVER.md`.

      **LIDO. O portão PASSOU** — maior diferença na direção de artefato
      (injetado melhor que detectado) = **+0,0039**, contra limiar 0,25. Com a
      ressalva que as métricas emitem sozinhas: o controle tem 18–19 casos,
      abaixo de 30; ausência de diferença não demonstra ausência de artefato.

      **O controle revelou outra coisa, não prevista** (mapa §4b.5): nos MESMOS
      casos, com semente 42 e temperatura 0, o baseline foi de **8 VP para 0** ao
      perder os campos do alerta, e o especialista ficou em 3. O baseline das
      Rodadas 1-3 lia a fraqueza na mensagem do Semgrep — nunca foi controle
      limpo. `baseline × triagem` NÃO é comparável com `baseline × filtro`.

> **As tarefas 5.4, 5.5 e 5b.1 a 5b.4 estão AUTOMATIZADAS** em
> `scripts/gatilho_rodada_triagem.py`: ele espera a máquina ficar ociosa,
> descarrega o modelo, popula a Fase 1, aquece o modelo, roda o piloto, aplica o
> portão de 5.5 e só então roda a população inteira. Documentado em
> `docs/SCRIPTS.md`. Restam para leitura humana: 5.5 (a decisão, se o portão
> fechar), 5b.5, 5b.6 e 5c.1.

## 5b. Rodada de triagem completa — provedor local, sem braço comercial

- [x] 5b.1 Confirmar que a Fase 1 está populada em cache para a população inteira
      e que o modelo local está descarregado durante qualquer reexecução simbólica
      — Semgrep e `llama-server` disputam RAM. Verificar: a rodada simbólica
      termina e só então o modelo é carregado.

      **Implementado como etapa do gatilho**, e não como procedimento manual:
      `descarregar_modelo()` (Ollama `keep_alive: 0`) → `popular_fase1()`
      (`--tudo --sem-llm`, modo filtro, `--run-id pre-fase1-simbolica`) →
      `aquecer_modelo()` (`keep_alive: 24h`) → só então o piloto. A ordem está
      codificada em `main()`; se a etapa simbólica falhar, o gatilho para antes
      de subir o modelo. A rodada simbólica usa `--run-id` próprio porque ela é
      de modo `filtro`, e a pipeline recusa misturar modos no mesmo diretório.
- [x] 5b.2 Executar a rodada de triagem completa com **os dois tipos de prompt
      contra o provedor local**, nomeando o modelo explicitamente, sobre a
      população inteira. Nenhum braço comercial. Verificar: o manifesto registra
      modo de montagem `triagem`, o modelo local e dois braços; o CSV cobre a
      população.

      3.210 chamadas no total, ≈ 7,3 h (ver 5.3) — ou ≈ 3,6 h se 5.4 já tiver
      rodado no mesmo `--run-id`:

      ```bash
      python run_pipeline.py --tudo --modo-montagem triagem \
        --modelo ollama:qwen2.5-coder:7b \
        --prompt baseline --prompt especialista \
        --run-id rodada-4-triagem
      ```

      A pipeline recusa retomar este `--run-id` com `--modo-montagem filtro`: o
      modo é uniforme na rodada, e misturar os dois produziria um McNemar
      pareado sobre um conjunto de `ID_Caso` que nunca existiu.
- [x] 5b.3 Emitir as métricas da rodada: Precisão, Recall, F1, MCC e taxa de
      falsos negativos, para o conjunto completo e por procedência. Verificar: os
      cinco números estão preenchidos e nenhum traz o aviso de poder estatístico
      limitado no conjunto completo.
- [x] 5b.4 Executar o McNemar pareado entre baseline e especialista **dentro da
      rodada de triagem**. Verificar: a tabela 2x2 de discordâncias e o valor de p
      ficam gravados, e o conjunto de `ID_Caso` é idêntico nos dois braços.
- [x] 5b.5 Comparar, entre a rodada de filtro e a de triagem, a taxa de redução de
      alertas e o recall. Verificar: a tabela registra os dois números lado a lado
      — **é a medida do teto de filtro puro**, que o roteiro da apresentação hoje
      anuncia sem quantificar.
- [x] 5b.6 Escrever `docs/ANALISE-RODADA-4.md` no formato das análises anteriores,
      com o funil, os números por procedência, o McNemar e a distância entre os
      dois braços. Verificar: o documento existe e os números batem com os CSVs.

## 5c. Decisão em aberto, a tomar DEPOIS do piloto

- [x] 5c.1 Decidir o enquadramento do prompt no modo triagem. Os dois templates
      abrem com "abaixo está um alerta emitido por uma ferramenta de análise
      estática": no braço de triagem isso é **falso** para os candidatos
      injetados e, por ser uniforme às duas procedências, **o grupo de controle
      não o detecta**. Manter preserva `Versao_Prompt` e a comparabilidade com as
      Rodadas 1-3; trocar torna a pergunta fiel ao que o modelo recebe, mas mexe
      no eixo experimental do prompt. Decisão de 2026-09-15: **usar o resultado
      de 5.4 para julgar** — se o recall nos injetados continuar em zero, pesar
      se o enquadramento contribui. Verificar: decisão registrada em `design.md`
      e, se for troca, change própria para o template.

      **DECIDIDO: manter.** O vazamento relevante não era a frase de abertura, e
      sim o `check_id` e a mensagem no corpo do contexto — que o modo triagem já
      remove. Trocar o template mudaria `Versao_Prompt` e quebraria a
      comparabilidade restante com as Rodadas 1-3 sem resolver nada a mais.
      Segue como limitação declarada em `docs/ANALISE-RODADA-4.md` §7.2.

## 6. Documentação e mapa do LaTeX

- [x] 6.1 Documentar o eixo de modo de montagem em `docs/PIPELINE.md`, incluindo
      o custo de cota do modo triagem e a recomendação de piloto local.
- [x] 6.2 Documentar a coluna de procedência e as métricas por procedência em
      `docs/PIPELINE.md`.
- [x] 6.3 **Escrever a entrada em `docs/MAPA-TCC-O-QUE-REESCREVER.md`** com os
      quatro pontos que a spec exige: que a arquitetura deixa de ser descrita como
      filtro puro e passa a ter dois braços; que os números da triagem não são
      desempenho do sistema em operação; que a distância entre os braços é a
      medida do teto de filtro puro anunciado no roteiro; e a ameaça à validade
      sobre a natureza das localizações, com o grupo de controle como resposta.
      Verificar: a entrada existe e nomeia os quatro pontos.
- [x] 6.4 Declarar na mesma entrada que a redação correspondente do `.tex`
      acontece em **branch separada**, e não nesta. Verificar: a frase está lá.
- [x] 6.5 Confirmar que nenhum arquivo `.tex` foi tocado pela change inteira.
      Verificar: `git diff --name-only` contra o ponto de partida não lista
      nenhum `.tex`.
- [x] 6.6 Atualizar `README.md` se a interface de invocação mudar. Verificar: as
      opções documentadas batem com `--help`.
