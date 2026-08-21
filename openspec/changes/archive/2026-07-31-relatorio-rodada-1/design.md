## Context

A rodada `results/20260730T180648Z-14d6af8` é a primeira execução completa da
pipeline com os dois braços de prompt sobre o dataset inteiro. Ela contém
apenas dois CSVs e um `manifesto.json`; tudo que o relatório precisa afirmar
tem de sair daí, de `data/dataset_go_limpo.json`, de `tp_pairs.json` /
`tp_pairs_osv.json` e do código em `src/`.

Estado atual verificado diretamente nos CSVs (`csv.DictReader`, 948 linhas por
braço):

| grandeza | baseline | especialista |
|---|---|---|
| linhas no CSV | 948 | 948 |
| `Status_Semgrep = DETECTADO` | 805 | 808 |
| `Status_Semgrep = NAO_DETECTADO` | 140 | 140 |
| `Status_Semgrep = API_ERROR` | 3 | 0 |
| Verdadeiro Negativo | 681 | 784 |
| Falso Positivo | 111 | 11 |
| Falso Negativo | 12 | 12 |
| Verdadeiro Positivo | 1 | 1 |

E, restringindo a `Gabarito = vulneravel` (107 casos, idêntico nos dois
braços): 94 `NAO_DETECTADO`, 13 `DETECTADO`, distribuídos em 34 CWEs
distintas e nas trilhas `TP_dataset` (48), `TP_prata` (31) e `TP_ouro` (15).

Dois detalhes que o enunciado da análise não captura e que o relatório precisa
tratar com cuidado:

1. **Os 140 `NAO_DETECTADO` não são os 94.** Há 46 casos de gabarito seguro
   que também não produziram alerta. O funil de recall usa só os 94; a taxa
   global de não-detecção é outra coisa.
2. **Os braços não têm o mesmo denominador.** O baseline perdeu 3 casos para
   `API_ERROR` que o especialista completou (805 contra 808 avaliados). Toda
   comparação de proporções entre braços precisa dizer sobre qual denominador
   está calculada, e o McNemar já opera só sobre o pareado.

A restrição dominante é de reprodutibilidade: o projeto prioriza
reprodutibilidade acima de tudo, e o relatório vai para a banca. Um número
sem comando que o regenere é passivo.

## Goals / Non-Goals

**Goals:**

- Produzir um documento único, autocontido, que um leitor externo consiga
  seguir sem abrir os CSVs — mas que todo número dele possa ser reconferido
  por quem quiser abrir.
- Separar, de forma defensável, o que a rodada mede (supressão de ruído) do
  que ela não mede (detecção), com a conclusão saindo dos dados e não da
  hipótese de partida.
- Dar aos autores uma decisão pronta sobre quais métricas levar para a
  monografia e com que ressalva.
- Responder se vale a pena construir um conjunto de verdadeiros positivos
  detectáveis pelo Semgrep, com números de custo, não com adjetivos.
- Deixar as ferramentas de conferência dos números no repositório, não no
  histórico do terminal.

**Non-Goals:**

- Corrigir o fallback de `src/fase1_semgrep.py:107-110`. Corrigir agora
  invalidaria a rodada que o relatório analisa.
- Tocar em prompts, ruleset ou engine.
- Construir o conjunto de VPs detectáveis — só avaliar a viabilidade.
- Alterar `src/metricas.py`. Se a conclusão for que a saída de métricas
  precisa mudar, isso vira recomendação escrita.
- Editar a monografia LaTeX.

## Decisions

### D1. Script auxiliar somente-leitura em vez de one-liners no texto

**Escolha:** criar `scripts/analise_rodada.py`, biblioteca padrão apenas, que
imprime as seções de números derivados; o relatório cita
`python scripts/analise_rodada.py results/<run_id> --secao <nome>`.

**Alternativas consideradas:**

- *One-liners de PowerShell no corpo do relatório.* Rejeitado: as
  justificativas do LLM no CSV contêm vírgulas, aspas e quebras de linha; um
  `Import-Csv` ou um `Select-String` para contar linhas erra silenciosamente.
  Além disso o relatório teria comandos que só rodam no Windows, e o projeto
  precisa continuar reprodutível fora dele.
- *Notebook Jupyter.* Rejeitado: traria dependência nova e um artefato binário
  de diff ruim, contra a decisão do projeto de manter a stack enxuta e sem
  pandas/numpy.
- *Estender `src/metricas.py`.* Rejeitado: `metricas.py` é código do caminho
  principal, coberto pela spec `metricas-comparativas` e consumido pelo export
  LaTeX. Números de diagnóstico desta rodada não pertencem ao contrato dele.
  A separação também mantém o não-objetivo de não mexer em `src/`.

**Consequência:** `scripts/analise_rodada.py` fica em `scripts/` junto com a
fase 0, e entra em `docs/SCRIPTS.md`. Ele não é chamado por
`run_pipeline.py`.

### D2. Seções nomeadas e saída determinística

**Escolha:** o script aceita `--secao` para imprimir uma seção isolada e, sem
o argumento, imprime todas na ordem fixa. Toda ordenação de saída é
determinística (chave explícita de ordenação, nunca ordem de iteração de
conjunto).

**Razão:** cada tabela do relatório precisa de um comando curto que produza
exatamente aquela tabela, e o cenário de determinismo da spec exige que duas
execuções deem saída idêntica. Ordenar por contagem decrescente com desempate
alfabético resolve o caso das distribuições por CWE.

### D3. Reuso das categorias de `src/metricas.py` em vez de reimplementar

**Escolha:** `scripts/analise_rodada.py` importa `_categoria_llm`,
`_categoria_semgrep`, `contar` e `carregar` de `src.metricas` (o script já
precisa ajustar `sys.path`, como os outros de `scripts/`).

**Razão:** os rótulos de classificação existem em duas grafias (português
atual e inglês legado) e `metricas.py` já normaliza ambas. Reimplementar a
normalização criaria duas verdades sobre o que conta como VP. Se o script
divergir de `metricas.py`, o relatório contradiz as tabelas do capítulo de
resultados.

**Trade-off:** acopla o script ao módulo do caminho principal. Aceito: o
acoplamento é de leitura, e uma mudança em `metricas.py` que quebre o script
é exatamente o sinal que se quer receber.

### D4. Análise qualitativa manual, com extração automatizada

**Escolha:** o script extrai os 13 casos de gabarito vulnerável que chegaram
ao LLM (`ID_Caso`, CWE, origem, repositório, regra, veredito e justificativa
nos dois braços) para um arquivo de trabalho; a leitura, o resumo e a
atribuição de causa (erro de gabarito / de emparelhamento / de julgamento) são
escritos à mão no relatório.

**Razão:** a spec exige atribuir causa por caso. Isso é julgamento, não
contagem — decidir se o Semgrep casou o alerta certo com o gabarito exige
abrir o arquivo-alvo no cache e comparar com a location do dataset. São 13
casos; automatizar o julgamento seria caro e menos confiável que fazê-lo.

**Consequência:** o arquivo de trabalho da extração é intermediário e vai para
o scratchpad, não para o repositório; o que fica versionado é o relatório com
a análise já escrita e o comando que regenera a extração.

### D5. Diagnóstico de não-detecção: reusar a amostra de 22 e declarar o erro

**Escolha:** o relatório reporta o diagnóstico já feito (22 dos 94 casos
re-rodados no Semgrep: 18 com zero alertas, 4 com alerta de outra CWE) como
**amostra**, com o intervalo de confiança binomial explícito, e não como
proporção da população. O comando que reproduz o diagnóstico fica registrado.

**Alternativa considerada:** re-rodar o Semgrep nos 94. Rejeitado por
enquanto: a informação marginal não muda nenhuma conclusão do relatório (a
distribuição de CWEs já sustenta o argumento de limite estrutural), e a
execução é cara em tempo de máquina. Fica listada nos próximos passos, com
custo estimado, para os autores decidirem.

**Consequência:** o relatório nunca escreve "82% dos 94"; escreve "18 de 22
amostrados (≈82%, IC95% aproximado 61–93%)".

### D6. Duas leituras concorrentes sobre o ganho do especialista, sem escolher a falsa

**Escolha:** o relatório apresenta a hipótese "o especialista reconhece FP" e
a hipótese "o especialista deslocou o limiar para seguro" como não separáveis
com os dados desta rodada, e propõe o experimento que as separaria (medir a
taxa de veredito "vulnerável" sobre a classe positiva com n suficiente).

**Razão:** o aninhamento é perfeito — zero casos em que o baseline acerta e o
especialista erra, 100 no sentido inverso, e o modelo passou de 13,9% para
1,5% de vereditos "vulnerável". Com 13 positivos, um deslocamento monotônico
de limiar explica os dados tão bem quanto discriminação melhorada. Afirmar a
segunda seria exatamente o tipo de leitura que o relatório existe para
impedir.

### D7. Um documento, não uma série

**Escolha:** um arquivo `docs/ANALISE-RODADA-1.md`, com o `run_id` declarado
no cabeçalho e numeração sequencial de rodada no nome.

**Alternativa considerada:** nomear pelo `run_id`
(`docs/ANALISE-20260730T180648Z.md`). Rejeitado: ilegível como referência no
texto da monografia e no README. O `run_id` fica no cabeçalho e no comando de
reprodução, que é onde precisa ser exato.

### D8. Estrutura do documento

Ordem fixa, do que é sólido para o que é especulativo:

1. Cabeçalho: `run_id`, configuração, custo, duração.
2. Sumário executivo — as três conclusões, em até 10 linhas.
3. Os números da rodada e como reproduzi-los.
4. O que a rodada mede: a classe negativa.
5. O que a rodada não mede: o funil de recall e a classe positiva.
6. Análise qualitativa dos 13 casos.
7. Corrigível contra estrutural; e o que deu certo.
8. Viabilidade do conjunto de VPs detectáveis.
9. Próximos passos por retorno sobre esforço.

O sumário executivo vem antes dos números porque o leitor primário é a banca,
que precisa da conclusão antes da evidência; a evidência inteira vem logo
abaixo para quem quiser conferir.

## Risks / Trade-offs

- **[O relatório vira advocacia da tese em vez de teste dela]** → a seção 4 é
  escrita antes da 5, e a conclusão sobre a tese só é redigida depois de
  ambas; a spec exige apresentar a evidência contra, não só a favor. Evidência
  contra a tese que existe e precisa aparecer: um recall de 0,077 medido sobre
  13 casos ainda é uma medição, e o TRA de 0,985 do especialista é alto o
  bastante para levantar a suspeita oposta — de que o filtro está simplesmente
  liberando quase tudo.
- **[Divergência entre o script novo e `src/metricas.py`]** → mitigado por D3
  (reuso das funções de categorização) e por uma tarefa que confere as
  contagens do script contra `python -m src.metricas` na mesma rodada.
- **[A extração dos 13 casos quebrar com aspas e quebras de linha nas
  justificativas]** → usar `csv.DictReader` sempre, nunca `split(",")`; a
  tarefa de extração é verificada contra a contagem esperada de 13 linhas.
- **[Estimar custo do conjunto de VPs com números inventados]** → toda
  estimativa de custo declara a base de cálculo (taxa medida, amostra
  observada ou premissa explícita), e premissa não medida é rotulada como
  premissa.
- **[O relatório envelhecer em silêncio quando o fallback for corrigido]** →
  o cabeçalho declara o `run_id` e o commit; a mudança que corrigir o
  emparelhamento fica responsável por gerar sua própria rodada e sua própria
  análise. Este documento não é atualizado retroativamente.
- **[Escopo escorregar para consertar o que o relatório diagnostica]** → os
  não-objetivos estão na proposta e a implementação não toca em `src/`; o
  script novo é somente-leitura, o que a spec verifica por `git status`.

## Migration Plan

Não há migração. Os arquivos criados são novos, os tocados são de
documentação, e nenhum artefato de dados ou resultado existente é modificado.
Reversão é `git revert` do commit.

## Open Questions

- **Vale re-rodar o Semgrep nos 94 casos não detectados** para trocar a
  amostra de 22 por um censo? Custa tempo de máquina e não muda a conclusão;
  entra nos próximos passos com custo estimado, para os autores decidirem.
- **O relatório deve propor um valor-alvo de n para a classe positiva?**
  A spec exige confrontar n necessário com n alcançável; o valor necessário
  depende do tamanho de efeito que os autores queiram detectar, e essa escolha
  fica registrada como premissa declarada no relatório, não como decisão desta
  mudança.
- **`docs/ANALISE-RODADA-1.md` ou uma pasta `docs/analises/`?** Fica o arquivo
  único enquanto houver uma rodada analisada; a pasta é decisão da segunda.
