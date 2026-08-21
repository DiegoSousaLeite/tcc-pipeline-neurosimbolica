## Why

A primeira rodada completa da pipeline (`results/20260730T180648Z-14d6af8`,
948 casos × 2 prompts, 1.616 chamadas, 2h50, custo zero) produziu números que,
lidos sem contexto, dizem a coisa errada. F1 de 0,016 no baseline e 0,080 no
especialista sugerem "a pipeline não funciona", quando na verdade essas três
métricas (Recall, F1, MCC) são governadas por uma classe positiva de 13
amostras, das quais ~8 estão contaminadas por um emparelhamento errado entre
alerta e gabarito. O que a rodada mede com solidez — supressão de ruído sobre
~792 negativos, com queda de 111 para 11 falsos positivos e aninhamento
estrito entre os braços — está enterrado sob métricas que não têm base
amostral.

Antes de escrever o capítulo de resultados, e antes de gastar esforço
construindo mais dados, é preciso separar por escrito o que a rodada mede do
que ela não mede, e decidir se existe caminho viável para um conjunto de
verdadeiros positivos que o Semgrep de fato detecte. Hoje 88% (94 de 107) das
amostras rotuladas como vulneráveis nunca chegam ao LLM.

**Pergunta de pesquisa atendida:** delimita a validade da resposta à pergunta
central do TCC ("um LLM consegue triar alertas do Semgrep reduzindo falsos
positivos sem descartar verdadeiros positivos?"), estabelecendo que a rodada
responde à primeira metade e não à segunda, e avaliando o custo de passar a
responder a segunda. Alimenta os capítulos de Resultados e de Limitações da
monografia. **Parte 2** do TCC.

## What Changes

- **Novo relatório de análise** em `docs/ANALISE-RODADA-1.md`, para leitura
  humana, cobrindo:
  - o que a rodada mede com validade (supressão de ruído, n≈792) e o que não
    mede (capacidade de detecção, n≈5 positivos válidos), com a tese defendida
    ou refutada a partir dos dados, não assumida;
  - diagrama do funil de recall (107 → 94 NAO_DETECTADO → 13 → ~5 válidos) e
    decomposição do que cada degrau custa;
  - recomendação explícita de quais métricas reportar no TCC, quais reportar
    com ressalva e quais omitir, com a redação da ressalva já pronta;
  - o que deu bom e o que deu ruim na rodada, separando defeito corrigível
    (emparelhamento contaminado) de limite estrutural (casamento sintático não
    alcança vulnerabilidade de intenção);
  - análise qualitativa caso a caso dos 12 falsos negativos e do único
    verdadeiro positivo, lendo as justificativas do LLM nos CSVs dos dois
    braços;
  - avaliação de viabilidade de um conjunto de verdadeiros positivos
    detectáveis pelo Semgrep, com fontes candidatas, custo estimado, risco de
    viés declarado e n alcançável.
- **Novo script auxiliar** `scripts/analise_rodada.py`, somente-leitura, que
  imprime os números derivados que `src/metricas.py` não produz: degraus do
  funil, relações de conjunto entre os braços (interseção de FN, contenção de
  FP), distribuição por CWE e por trilha dos casos `NAO_DETECTADO`, taxa de
  ERROR e estatísticas de tokens. Existe para que cada número do relatório
  tenha um comando que o reproduz, em vez de um one-liner frágil de shell.
- **Índice de documentação atualizado** (`README.md`, `docs/SCRIPTS.md`) para
  apontar o relatório e o novo script.

Nenhuma mudança altera a pipeline, os prompts, o ruleset, o engine ou os CSVs
já gerados. Nenhum resultado publicado é invalidado por esta mudança — ao
contrário, ela documenta quais números já gerados não devem ser publicados
como estão.

## Capabilities

### New Capabilities
- `analise-rodada`: relatório de análise de uma rodada completa — requisitos de
  conteúdo (validade da medição, funil de recall, orientação de quais métricas
  reportar, análise qualitativa dos casos da classe positiva, avaliação de
  viabilidade do conjunto de VPs detectáveis) e requisito de que todo número
  citado venha acompanhado do comando que o reproduz a partir dos artefatos
  versionados.

### Modified Capabilities
Nenhuma. `metricas-comparativas` já exige o aviso de poder estatístico
limitado (`avisos()` em `src/metricas.py:421`) e o relatório se apoia nele sem
alterar seu contrato. `trilha-tp-dataset` já registra a assimetria de rótulo
entre as trilhas; o relatório quantifica a consequência dela, mas não muda o
requisito.

## Impact

- **Arquivos novos:** `docs/ANALISE-RODADA-1.md`, `scripts/analise_rodada.py`.
- **Arquivos tocados:** `README.md`, `docs/SCRIPTS.md` (apenas índice).
- **Fases da pipeline:** nenhuma. O script novo lê `results/<run_id>/*.csv`,
  `results/<run_id>/manifesto.json`, `data/dataset_go_limpo.json`,
  `tp_pairs.json` e `tp_pairs_osv.json`; não escreve em nenhum deles.
- **Dependências:** nenhuma nova. O script usa apenas biblioteca padrão
  (`csv`, `json`, `collections`), coerente com a decisão de não trazer
  pandas/numpy.
- **Custo e cota de LLM:** zero. Nenhuma chamada a Gemini ou Ollama. Toda a
  análise sai dos CSVs já gravados.
- **Tempo de execução:** segundos. O script percorre ~1.600 linhas de CSV.
- **Artefatos preservados:** `tp_pairs.json` e `tp_pairs_osv.json` são lidos
  em modo somente-leitura e não são regenerados — `scripts/tp_reconstruct.py`
  exige histórico git que não está mais no disco.

## Não-objetivos

- **Não corrige o fallback de emparelhamento** de `src/fase1_semgrep.py:107-110`.
  O relatório quantifica o dano e dimensiona a correção; a correção em si é
  mudança separada. Alterar a Fase 1 agora invalidaria a própria rodada que o
  relatório analisa.
- **Não altera prompts, ruleset (`p/default`) nem engine (Semgrep OSS 1.167.0).**
  Trocar qualquer um dos três invalida o gabarito de falsos positivos herdado
  do SastBench.
- **Não constrói o conjunto de verdadeiros positivos detectáveis.** Esta
  mudança avalia a viabilidade e recomenda; a construção, se aprovada, é
  mudança própria com seu próprio custo.
- **Não regenera `tp_pairs.json` nem `tp_pairs_osv.json`.**
- **Não executa nova rodada de LLM** nem reprocessa casos.
- **Não edita a monografia LaTeX.** O relatório produz o texto e os números que
  o capítulo de resultados vai consumir; a transposição para `.tex` é decisão
  dos autores.
- **Não modifica `src/metricas.py`.** Se a análise concluir que a saída de
  métricas precisa mudar, isso vira recomendação no relatório, não código aqui.
