## Why

Seis rodadas foram executadas, seis documentos de análise foram escritos, e
**nenhum número deles está na monografia**. O `docs/MAPA-TCC-O-QUE-REESCREVER.md`
acumulou o que precisa ser escrito; falta transformá-lo em texto.

A apresentação é em novembro. A partir daqui, cada change de experimento adianta
a pesquisa e atrasa a monografia — e as quatro hipóteses grandes já foram
fechadas. O que resta é redação.

A leitura integral de `editaveis/metodologia.tex` em 22/09/2026 revelou, além
disso, três defeitos de fato que precisam ser corrigidos **antes** que o capítulo
de resultados os contradiga:

1. a Fase 1 afirma que o SARIF traz trilha de taint de origem a sumidouro —
   medimos **0 de 807 alertas** com trilha, mesmo com `--dataflow-traces`;
2. o capítulo de resultados cobre três das **cinco** perguntas declaradas na
   metodologia: faltam a Questão Geral e a Q4;
3. a limitação sobre APIs descreve custo e limite de taxa de serviços de
   terceiros, quando a maior parte dos vereditos veio de modelo local.

**O plano detalhado do que escrever está em
[`docs/PLANO-ESCRITA-RESULTADOS.md`](../../../docs/PLANO-ESCRITA-RESULTADOS.md)**,
que especifica o padrão de redação, as nove figuras, a ordem de escrita e as
pendências de cada capítulo. Esta change é o contrato; o plano é o detalhamento.

**Pergunta de pesquisa atendida:** nenhuma diretamente — é **redação**. Mas é o
que torna reportáveis as respostas a Q1, Q2 e Q3 já obtidas, e o que destrava a
Questão Geral e a Q4, hoje sem seção. Parte 2.

## What Changes

- **Capítulo de Resultados escrito** em `editaveis/resultados.tex`, com nove
  figuras TikZ e as tabelas já rascunhadas, e incluído em `tcc.tex`.
- **Duas seções que não existiam:** a Questão Geral (fadiga de alertas) e a Q4
  (auditoria qualitativa de `reasoning`).
- **Auditoria qualitativa de 30 a 50 vereditos**, que é o único dado novo desta
  change. Não exige rodada: os campos `reasoning` já estão nos CSVs. Responde à
  Q4 e, de quebra, quantifica a ameaça da classe negativa aproximada.
- **Correção das afirmações sobre trilha de taint** na metodologia — três frases,
  já registradas como pendentes.
- **Reequilíbrio da limitação sobre APIs**, acrescentando quantização em 4 bits e
  janela de contexto dos modelos locais.
- **Referencial teórico** recebe os trabalhos correlatos lidos em 17/09.

## Capabilities

### New Capabilities

- `capitulo-resultados`: o que o capítulo de resultados precisa satisfazer para
  ser defensável — cobertura das perguntas declaradas, ressalva junto de cada
  número, denominadores explícitos, e coerência com os demais capítulos.

### Modified Capabilities

Nenhuma. Esta change não altera comportamento de código.

## Impact

**Arquivos:** `TCC2___Diego_Sousa_e_João_Artur_Leles/editaveis/resultados.tex`
(principal), `editaveis/metodologia.tex`, `editaveis/referencialteorico.tex`,
`tcc.tex`, `fixos/bibliografia.bib`, e possivelmente `fixos/pacotes.tex` (ver
decisão sobre `pgfplots` na §2 do plano).

**Código:** nenhum. Nada em `src/` ou `scripts/` é tocado.

**Custo de LLM:** zero. A auditoria qualitativa é leitura humana de CSV já
gravado.

**Dependência externa:** a rodada comercial. O plano isola essa dependência em
**quatro lugares** (§5 do plano), de modo que o capítulo fique pronto antes dela.

**Resultados invalidados:** nenhum. Esta change escreve sobre números já
medidos; não produz número novo além da auditoria qualitativa.

## Não-objetivos

- **Não** executar rodada de LLM, local ou comercial.
- **Não** alterar código da esteira.
- **Não** mexer no bloco `\begin{comment}` da metodologia — é decisão do autor, e
  fica como está.
- **Não** reescrever a introdução ou as considerações finais antes do capítulo de
  resultados estar fechado.
- **NÃO COMMITAR.** Ver o requisito correspondente na spec: as edições ficam na
  árvore de trabalho e o autor decide quando versioná-las.
