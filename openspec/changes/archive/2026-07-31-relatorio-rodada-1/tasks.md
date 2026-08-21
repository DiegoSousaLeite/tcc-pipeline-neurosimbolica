## 1. Ferramenta de números derivados

- [x] 1.1 Criar `scripts/analise_rodada.py` com o esqueleto de CLI: argumento
      posicional do diretório da rodada, `--secao <nome>` opcional, ordem fixa
      das seções, erro alto e explícito quando o diretório não tiver CSV de
      rodada. Reusar `carregar`, `contar`, `_categoria_llm` e
      `_categoria_semgrep` de `src.metricas` (D3), com o mesmo ajuste de
      `sys.path` dos demais scripts.
      **Verificação:** `python scripts/analise_rodada.py results/nao-existe`
      encerra com mensagem explícita e código de saída diferente de 0;
      `python scripts/analise_rodada.py --help` lista as seções.
- [x] 1.2 Implementar a seção `funil`: das 107 linhas com
      `Gabarito = vulneravel` até as efetivamente avaliadas, com número
      absoluto e percentual por degrau, recall de ponta a ponta, e as
      contagens separadas por `Status_Semgrep`.
      **Verificação:** `python scripts/analise_rodada.py
      results/20260730T180648Z-14d6af8 --secao funil` imprime 107 no topo,
      94 `NAO_DETECTADO` e 13 `DETECTADO`.
- [x] 1.3 Implementar a seção `nao-detectados`: distribuição dos 94 casos por
      CWE (ordem decrescente, desempate alfabético) e por trilha de origem,
      com o total de CWEs distintas.
      **Verificação:** a saída traz 34 CWEs distintas, `TP_dataset` 48,
      `TP_prata` 31, `TP_ouro` 15, e CWE-77 e CWE-284 com 10 cada.
- [x] 1.4 Implementar a seção `conjuntos`: por braço, os conjuntos de
      `ID_Caso` classificados como FN, FP e VP; e entre os braços, a
      interseção dos FN, a relação de contenção entre os FP (com a direção
      declarada) e a tabela 2x2 de discordâncias.
      **Verificação:** a saída mostra interseção de FN igual a 12, FP do
      especialista contido estritamente nos do baseline (11 de 111), e
      discordâncias 0 / 100.
- [x] 1.5 Implementar a seção `esteira`: linhas por braço, contagem por
      `Status_Semgrep`, taxa de ERROR por braço, denominador efetivo de cada
      braço, e estatísticas de `Tokens_Entrada` (mínimo, mediana, máximo,
      quantos acima de `num_ctx`) e `Tempo_Execucao_s`.
      **Verificação:** a saída mostra 3 `API_ERROR` no baseline e 0 no
      especialista, denominadores 805 e 808, e zero prompts acima de 8192
      tokens.
- [x] 1.6 Implementar a seção `positivos`: extração das 13 linhas de gabarito
      vulnerável com `Status_Semgrep = DETECTADO`, trazendo `ID_Caso`, CWE,
      origem, repositório, `Classificacao_Semgrep`, e veredito mais
      justificativa de cada braço, lado a lado.
      **Verificação:** a saída traz exatamente 13 casos, entre eles
      `TPD:f4b33b64:CWE-290:true_positive` como o único Verdadeiro Positivo.
- [x] 1.7 Conferir o script contra o caminho principal: rodar
      `python -m src.metricas results/20260730T180648Z-14d6af8 --mcnemar` e
      confrontar VP/VN/FP/FN por braço e a tabela de McNemar com a saída de
      `analise_rodada.py`.
      **Verificação:** as contagens batem célula a célula; qualquer
      divergência é resolvida no script novo, nunca em `src/metricas.py`.
- [x] 1.8 Verificar as invariantes de somente-leitura e determinismo: rodar o
      script duas vezes redirecionando a saída e comparar; conferir a árvore
      de trabalho depois.
      **Verificação:** as duas saídas são idênticas e
      `git status --porcelain` não aponta modificação em `results/`, `data/`,
      `tp_pairs.json` ou `tp_pairs_osv.json`.

## 2. Levantamento para a análise qualitativa

- [x] 2.1 Extrair os 13 casos da classe positiva para arquivo de trabalho no
      scratchpad e ler as justificativas dos dois braços caso a caso.
      **Verificação:** o arquivo tem 13 registros, cada um com as duas
      justificativas.
- [x] 2.2 Para cada um dos 13, abrir o arquivo-alvo no cache e comparar a
      location apontada pelo alerta do Semgrep com a location do gabarito, e
      classificar o caso como erro de gabarito, erro de emparelhamento ou erro
      de julgamento do modelo.
      **Verificação:** tabela com 13 linhas, cada uma com a causa atribuída e
      a evidência que a sustenta; o total de "erro de emparelhamento" é
      registrado com o número apurado, confirmando ou corrigindo a estimativa
      de 8 do levantamento preliminar.
- [x] 2.3 Dissecar o único Verdadeiro Positivo
      (`TPD:f4b33b64:CWE-290:true_positive`): regra do Semgrep que disparou,
      trecho de código, justificativa em cada braço, e veredito sobre se o
      acerto é substantivo ou fortuito.
      **Verificação:** o parágrafo de análise cita a regra, o arquivo-alvo no
      cache e as duas justificativas.
- [x] 2.4 Registrar o comando de reprodução do diagnóstico amostral dos 94
      não detectados (22 casos re-rodados: 18 com zero alertas, 4 com alerta
      de outra CWE) e calcular o intervalo de confiança binomial da proporção.
      **Verificação:** o comando executa e o intervalo está calculado com a
      fórmula declarada no texto.

## 3. Redação do relatório

- [x] 3.1 Criar `docs/ANALISE-RODADA-1.md` com o cabeçalho e o esqueleto das
      nove seções na ordem de D8. O cabeçalho traz `run_id`, commit, modelo,
      quantização, `num_ctx`, semente, versão do Semgrep, ruleset, hash do
      catálogo, versões dos prompts, duração e custo.
      **Verificação:** cada campo do cabeçalho é conferido contra
      `results/20260730T180648Z-14d6af8/manifesto.json`.
- [x] 3.2 Escrever a seção 3 (números da rodada): tabela por braço com
      n, VP, VN, FP, FN, Precisão, Recall, F1, MCC, TRA e TFN, cada tabela
      precedida do comando que a regenera, e nota sobre os denominadores
      distintos dos dois braços (805 contra 808).
      **Verificação:** todos os comandos citados executam e produzem os
      valores da tabela.
- [x] 3.3 Escrever a seção 4 (o que a rodada mede): a classe negativa, com o
      n de cada braço, a queda de 111 para 11 falsos positivos, o aninhamento
      estrito, a tabela de McNemar, e a discussão de que discriminação
      melhorada e deslocamento de limiar não são separáveis aqui (D6).
      **Verificação:** a seção apresenta a hipótese concorrente e o
      experimento que a separaria.
- [x] 3.4 Escrever a seção 5 (o que a rodada não mede): diagrama do funil de
      recall com percentual e causa por degrau, distribuição por CWE e por
      trilha dos não detectados, e o diagnóstico amostral com o intervalo de
      confiança — nunca extrapolado para os 94 (D5).
      **Verificação:** o diagrama tem todos os degraus e o texto não contém a
      forma "82% dos 94".
- [x] 3.5 Escrever a seção 6 (análise qualitativa) a partir do levantamento do
      grupo 2: os 12 falsos negativos e o verdadeiro positivo, cada um com
      `ID_Caso`, CWE, trilha, resumo das justificativas nos dois braços e
      causa atribuída.
      **Verificação:** os 13 casos estão cobertos e cada citação indica o CSV
      de origem.
- [x] 3.6 Escrever a seção 7 (corrigível contra estrutural): localizar o
      emparelhamento incorreto em `src/fase1_semgrep.py:107-110`, quantificar
      o dano apurado em 2.2, dizer o que precisa ser reexecutado após a
      correção; argumentar o limite estrutural a partir da distribuição de
      CWEs; e registrar o que deu certo (zero estouros de contexto, ERROR
      ~0%, redução de ruído).
      **Verificação:** a seção separa explicitamente as duas categorias e
      declara quais CSVs ficariam obsoletos após a correção.
- [x] 3.7 Escrever a seção da orientação de métricas (dentro da seção 4, com
      remissão da seção 3): cada uma de Precisão, Recall, F1, MCC, TRA e TFN
      classificada em reportável, reportável com ressalva ou a omitir, com
      justificativa pela base amostral, a frase de ressalva pronta para o
      `.tex`, e a leitura equivocada nomeada ("F1 de 0,08, não funciona") com
      o motivo de não se sustentar.
      **Verificação:** as seis métricas aparecem classificadas e há pelo menos
      uma frase de ressalva transponível sem reescrita.

## 4. Viabilidade do conjunto de verdadeiros positivos detectáveis

- [x] 4.1 Levantar quantas e quais regras o `p/default` efetivamente dispara
      sobre o corpus atual, cruzando com as CWEs do gabarito, para dimensionar
      o espaço de regras a partir do qual minerar.
      **Verificação:** tabela regra → contagem de alertas na rodada, com o
      comando que a reproduz.
- [x] 4.2 Avaliar as fontes candidatas de casos (mineração de commits de fix
      guiada por regra, avisos do OSV para Go já coletados em
      `tp_pairs_osv.json`, casos sintéticos derivados dos padrões das regras,
      e quaisquer outras que o levantamento indicar), cada uma com o que
      oferece, o custo de extração e o motivo de ser viável ou inviável aqui.
      **Verificação:** cada fonte tem as três colunas preenchidas e nenhuma
      viola a restrição de que `tp_pairs.json` e `tp_pairs_osv.json` não são
      regeneráveis sem reclonar.
- [x] 4.3 Estimar o custo em unidades verificáveis — horas, chamadas de API,
      volume de download, casos por hora — declarando para cada estimativa se
      a base é taxa medida, amostra observada ou premissa.
      **Verificação:** nenhuma estimativa aparece sem base declarada.
- [x] 4.4 Escrever a declaração de viés: um conjunto construído a partir das
      regras do detector favorece o detector; por que isso é aceitável para
      medir triagem e não para medir detecção; e a redação dessa declaração
      para a monografia.
      **Verificação:** o parágrafo está redigido em forma transponível para o
      `.tex`.
- [x] 4.5 Confrontar n necessário com n alcançável e emitir a recomendação de
      seguir ou não seguir, com a premissa de tamanho de efeito declarada.
      **Verificação:** a seção termina com uma recomendação explícita, não com
      uma ponderação.

## 5. Fechamento

- [x] 5.1 Escrever a seção 9 (próximos passos): lista numerada por retorno
      sobre esforço, cada item com ganho esperado, custo estimado, dependência
      que o bloqueia e o artefato ou comando por onde começar. Incluir a
      correção do emparelhamento e o censo dos 94 como itens com custo, sem
      executá-los.
      **Verificação:** todos os itens têm os quatro campos e estão em ordem
      declarada de retorno sobre esforço.
- [x] 5.2 Escrever o sumário executivo (seção 2) por último, em até 10 linhas,
      com as três conclusões do documento.
      **Verificação:** cabe em 10 linhas e cada conclusão remete à seção que a
      sustenta.
- [x] 5.3 Auditar a rastreabilidade: percorrer o relatório e conferir que todo
      valor numérico tem comando associado ou remissão à seção que o reproduz,
      e executar cada comando citado.
      **Verificação:** todos os comandos executam sem erro e produzem os
      valores citados; nenhum número fica órfão.
- [x] 5.4 Atualizar `docs/SCRIPTS.md` com a entrada de
      `scripts/analise_rodada.py` (o que faz, seções, garantia de
      somente-leitura) e `README.md` com o apontamento para
      `docs/ANALISE-RODADA-1.md`.
      **Verificação:** os dois arquivos citam os caminhos corretos e o script
      aparece descrito com as mesmas seções que `--help` lista.
- [x] 5.5 Validar a mudança e revisar o conjunto entregue.
      **Verificação:** `openspec validate relatorio-rodada-1` passa e
      `git status` mostra apenas `docs/ANALISE-RODADA-1.md`,
      `scripts/analise_rodada.py`, `docs/SCRIPTS.md`, `README.md` e os
      artefatos da mudança em `openspec/changes/relatorio-rodada-1/`.
