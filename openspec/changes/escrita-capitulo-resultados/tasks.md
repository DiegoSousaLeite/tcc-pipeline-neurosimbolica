> **Consultar [`docs/PLANO-ESCRITA-RESULTADOS.md`](../../../docs/PLANO-ESCRITA-RESULTADOS.md)
> antes de cada tarefa.** Ele traz o padrão de redação (§1), a especificação das
> nove figuras (§3), a ordem de escrita (§4) e as pendências por capítulo (§6).
>
> **⛔ NÃO COMMITAR nada desta change sem pedido explícito do autor.**

## 1. Correções de fato, antes de escrever o que as usa

- [x] 1.1 Corrigir a afirmação de trilha de taint na Fase 1
      (`metodologia.tex`, linha ~86): o SARIF traz localização e CWE, e **não**
      traz rastreio de origem a sumidouro. Verificar: a frase não afirma mais
      trilha, e o texto diz que a edição aberta do Semgrep rastreia dados
      corrompidos apenas dentro de um arquivo. Ver §6.0.1 do plano.
- [x] 1.2 Corrigir a herdeira na Fase 2 (linha ~89): a hidratação extrai a função
      que contém a linha do alerta, não "um bloco ao redor de cada ponto do
      rastreio". Verificar: a frase descreve o que `src/hidratacao.py` faz.
- [x] 1.3 Corrigir a herdeira na Fase 4 (linha ~95): "os dois modelos de
      linguagem de fronteira definidos no plano metodológico" não corresponde aos
      modelos declarados. Verificar: a frase acompanha o item de modelos.
- [x] 1.4 Reequilibrar a limitação "Dependência de APIs e Modelos Proprietários",
      acrescentando quantização em 4 bits e janela de contexto dos modelos
      locais. Verificar: a limitação descreve o experimento executado. Ver
      §6.0.3 do plano.
- [x] 1.5 Decidir sobre `pgfplots` (D2) e registrar a decisão. Verificar: se
      afirmativa, `fixos/pacotes.tex` traz o pacote e o documento compila.

## 2. Fundação do capítulo

- [x] 2.1 Acrescentar `\input{editaveis/resultados}` a `tcc.tex`, após
      `provadeconceito`. Verificar: `latex tcc.tex` compila e o capítulo aparece
      no sumário.
- [x] 2.2 Escrever a §5.1 completa — desenho dos dois braços. **Primeira seção a
      escrever** (D4). Verificar: um leitor que não acompanhou o projeto
      distingue braço de filtro de braço de triagem depois de lê-la.
- [x] 2.3 Desenhar a **Figura 1** (`fig:funil`): o caminho dos 2.328 casos até o
      que chega ao LLM. Verificar: larguras proporcionais às contagens; compila.
- [x] 2.4 Desenhar a **Figura 2** (`fig:doisbracos`): dois painéis idênticos
      exceto pelo destino dos 778. Verificar: a diferença entre os braços é
      legível sem ler o texto.
- [x] 2.5 Escrever a §5.7 Limitações. Escrita cedo porque as seções seguintes
      remetem a ela. Verificar: contém os sete itens listados no rascunho,
      incluindo a granularidade de rótulo como ameaça **medida**.

## 3. Questão Geral e Q1 — o resultado positivo

- [x] 3.1 Criar a seção da **Questão Geral** (`sec:geral`), antes da Q1, com TRA
      e Proporção de FP Filtrados. Verificar: a seção existe e reporta as duas
      métricas que a metodologia associa à pergunta. Ver §6.0.2 do plano.
- [x] 3.2 Escrever a §5.2.1 — comparação pareada entre os tipos de \textit{prompt},
      com McNemar. Verificar: a tabela 2x2 de discordâncias e o valor de p constam.
- [x] 3.3 Narrar a §5.2.2 — o \textit{baseline} nunca foi controle limpo. A prosa
      de enquadramento e a citação a `white2025feature` já estão escritas; falta
      o número. Verificar: os 8 VP que foram a zero estão no texto.
- [x] 3.4 Narrar a §5.2.3 — o enquadramento do \textit{prompt} como variável
      (1,29 % para 5,13 %). Verificar: a mudança isolada está descrita.

## 4. Q2 e Q3 — o teto

- [x] 4.1 Narrar a §5.3.1 (braço de filtro) sobre `tab:filtro`. Verificar: a TRA
      é apresentada junto da TFN, e a ressalva dos 19 casos está no mesmo
      parágrafo.
- [x] 4.2 Narrar a §5.3.2 (braço de triagem) e a §5.3.3 (distância entre braços).
      Verificar: o texto declara que o MCC é indefinido sobre os injetados e por
      quê.
- [x] 4.3 Narrar a §5.4 (Q3) e desenhar a **Figura 6** (`fig:cwe-barras`).
      Verificar: as cinco CWEs aparecem com contagem de pares ao lado.
- [x] 4.4 Escrever a §5.4.3 — concorrência em Go sem instrumento. Verificar: o
      texto a apresenta como resultado, e não como lacuna, citando
      `tu2019understanding`.

## 5. A cadeia de eliminação — a seção mais longa

- [x] 5.1 Desenhar a **Figura 5** (`fig:eliminacao`): quatro hipóteses rejeitadas
      em sequência, desembocando na sobrevivente. Verificar: cada caixa traz a
      hipótese, a medição e o carimbo de rejeição.
- [x] 5.2 Narrar as §5.5.1 a §5.5.4 — ruleset, alcance do motor, ruleset público,
      regra própria. Verificar: a §5.5.2 declara que a sonda do Pro cobriu 5
      casos; a §5.5.4 descreve o protocolo de partição **antes** dos números.
- [x] 5.3 Escrever a §5.5.5 — granularidade do rótulo e abstração. Verificar: os
      ~30 % e os 26 %/44 % constam, e o texto declara que é propriedade conhecida
      dos conjuntos derivados de \textit{commits} de correção, citando
      `croft2023dataquality`.
- [x] 5.4 Desenhar a **Figura 3** (`fig:rotulo`): o \textit{commit} tocando o
      arquivo da verificação acrescentada, não o da operação perigosa.
      Verificar: a figura explica os ~30 % sem apoio do texto.
- [x] 5.5 Desenhar a **Figura 4** (`fig:abstracao`): `os.Open` contra `fs.Open`
      atrás de `afero`. Verificar: fica claro por que a regra casa com um e não
      com o outro.

## 6. Q4 — a auditoria qualitativa (único dado novo)

- [x] 6.1 Escrever o critério de classificação **antes** de ler qualquer caso:
      correto / correto por motivo errado / alucinação, com definição de cada um.
      Verificar: o critério está registrado e datado antes da amostragem.
- [x] 6.2 Amostrar 30 a 50 vereditos dos CSVs, estratificados por veredito, para
      que os casos em que o modelo manteve o alerta não fiquem
      sub-representados (15 de 827 no braço especialista). Verificar: a amostra
      é reproduzível a partir do critério registrado.
- [x] 6.3 Ler e classificar, registrando o segundo eixo em paralelo (D3): para os
      casos de gabarito seguro que o modelo manteve, se eram de fato seguros.
      Verificar: as duas classificações constam da planilha de auditoria.
- [x] 6.4 Escrever a seção da **Q4** com o resultado, declarando que a
      classificação foi feita pelos autores sem cegamento. Verificar: a seção
      existe e a limitação está declarada.
- [x] 6.5 Levar o segundo eixo para a §5.7 — a ameaça da classe negativa
      aproximada deixa de ser declarada sem número. Verificar: o item de
      limitação traz a proporção medida.

## 7. Discussão

- [x] 7.1 Narrar a §5.8.1 — a inversão da unidade de rotulagem do OpenVuln. A
      prosa já está escrita; conferir e ajustar. Verificar: a composição do
      OpenVuln (dois projetos com zero verdadeiros positivos) consta.
- [x] 7.2 Desenhar a **Figura 8** (`fig:recall-comparado`) com a declaração de
      não comparabilidade na legenda. Verificar: a declaração está presente.
- [x] 7.3 Desenhar a **Figura 7** (`fig:tra-tfn`) com o classificador degenerado
      marcado. Verificar: os dois braços estão posicionados e a linha do "diz não
      para tudo" aparece.
- [x] 7.4 Narrar a §5.8.2 (supressão excessiva) e a §5.8.3 (comparação com
      eliminação sã). Verificar: o colapso do `gemini-2.5-pro` e os números do
      `wang2026rican` constam.
- [x] 7.5 Fechar a §5.8.4 — consequências para a arquitetura neuro-simbólica,
      com `huang2026memhint` como direção de trabalho futuro. Verificar: o texto
      declara que é direção futura, não resultado.

## 8. Referencial e fechamento

- [x] 8.1 Acrescentar os trabalhos correlatos lidos ao `referencialteorico.tex`:
      `huang2026memhint`, `wang2026rican`, `alatasi2026aisast`,
      `white2025feature`. Verificar: todos já estão na bibliografia.
- [x] 8.2 Resolver as três trocas de frase sobre taint pendentes no referencial.
      Verificar: nenhuma afirma trilha que o motor não produz.
- [x] 8.3 Conferir ou rebaixar as entradas marcadas `% VERIFICAR` em
      `fixos/bibliografia.bib`. Verificar: nenhuma citação ativa depende de
      entrada com veículo não confirmado.
- [x] 8.4 Desenhar a **Figura 9** (`fig:contexto-braco`), ou mover para apêndice.
      Verificar: decisão registrada.

## 9. Verificação final

- [x] 9.1 Compilar com `make` e conferir ausência de erro. Verificar: exit 0.
- [x] 9.2 Rodar o ciclo completo (latex, bibtex, latex, latex) e conferir que não
      restam `Citation undefined` nem `Reference undefined`.
- [x] 9.3 Conferir que toda figura declarada é referenciada por `\ref` e vice-versa.
- [x] 9.4 Conferir que cada uma das cinco perguntas tem seção e que cada métrica
      declarada na metodologia é reportada.
- [x] 9.5 Conferir que nenhum número aparece sem ressalva no mesmo parágrafo, e
      que os denominadores 19/797 e 18/690 nunca aparecem como equivalentes.
- [x] 9.6 **Confirmar que nada foi commitado.** Verificar: `git log` não traz
      \textit{commit} desta change que o autor não tenha pedido.

## 10. Integrar a Rodada 7 — ablação da granularidade da ficha

> A instrução completa já existe em `docs/PLANO-ESCRITA-RESULTADOS.md` §6.7 e em
> `docs/MAPA-TCC-O-QUE-REESCREVER.md` §11.6 a §11.8, com o enquadramento
> decidido, os números que o sustentam, o mecanismo e o tamanho sugerido.
> **Estas tarefas apontam; não repetem.** Ler lá antes de escrever.
>
> Fase **aditiva**: os números das Rodadas 1–6 continuam valendo e nada do que
> já foi escrito é refeito (MAPA §11.3).

- [x] 10.1 §5.7, limitações — o parágrafo com o enquadramento de MAPA §11.6.
      Verificar: fala em **granularidade da orientação**, e a frase "corrigimos o
      desalinhamento e ficou pior" NÃO aparece no capítulo.
- [x] 10.2 §5.8.2, supressão excessiva — reforço com o mecanismo de MAPA §11.7
      (a ficha desloca a postura do modelo, não aprofunda a análise do código).
      Verificar: os dois casos citados lá aparecem como evidência.
- [x] 10.3 §5.6, comparação de modelos — o que do gemma entra e o que fica de
      fora, conforme PLANO §6.7. Verificar: o que ficou de fora está dito, não
      omitido.
- [x] 10.4 `fig:eliminacao` passa de quatro caixas para cinco. Verificar: a
      quinta traz a hipótese, a medição e o desfecho, no mesmo formato das
      outras.
- [x] 10.5 Conferir que nenhum número das Rodadas 1–6 mudou no capítulo.
      Verificar: `git diff` do `.tex` não altera tabela nem valor já escrito.

## 11. Pendências abertas

- [ ] 11.1 Revisão autoral de `docs/auditoria-q4/classificacao.csv`. Enquanto
      não houver, os números da Q4 seguem marcados como provisórios no capítulo.
- [x] 11.2 Referência sobre o efeito da quantização em 4 bits — há TODO em
      `resultados.tex` (§limitações), e a lacuna também aparece na metodologia.
- [ ] 11.3 Rodada comercial: os quatro pontos que só ela fecha (MAPA §11.8,
      PLANO §5). Não bloqueia o resto do capítulo.
- [ ] 11.4 Decidir o que commitar. **Nada desta change foi versionado** — o
      capítulo, o plano, a auditoria Q4 e a própria change estão fora do git.

## Registro de execução (2026-09-22)

- **1.5 / D2:** o autor decidiu pela opção B; `pgfplots` com `compat=1.18` em
  `fixos/pacotes.tex`. Figuras 6, 7 e 8 em `pgfplots`.
- **8.4:** o autor decidiu manter a Figura 9 no corpo, no fecho da §5.1.
- **6.x:** por decisão do autor, a classificação é **pré-classificação assistida
  por IA**, marcada provisória em `docs/auditoria-q4/classificacao.csv` e
  declarada assim no capítulo. Fonte: Rodada 3 (os CSVs das Rodadas 4–6 não
  existem mais em disco). **Pendente dos autores:** revisar a planilha.
- **8.3:** `alatasi2026aisast` e `white2025feature` rebaixadas (busca na web não
  localizou veículo); citadas no texto como manuscritos. `li2025iris`: autores
  conferidos no arXiv.
- **9.1:** `make` não está instalado nesta máquina (e o `Makefile` exige um
  `bibliografia.bib` na raiz que não existe); verificado com o ciclo equivalente
  latex → bibtex → latex → latex: exit 0, zero erros, zero indefinidos.
- **5.2:** a sonda do Semgrep Pro tem 5 casos com dado nos JSON de
  `data/viabilidade_pro_*` (3 CWE-22, 2 CWE-918) e 1 *timeout*; o MAPA §3.5 fala
  em 6 e cita `seaweedfs`, que não está nesses arquivos. O capítulo usa 5.
- **Pendente de referência:** o efeito da quantização em 4 bits (TODO no
  `.tex`, na metodologia e nas limitações); não havia entrada na bibliografia.

## Registro de execução (2026-09-23)

- **10.1–10.4:** números da Rodada 7 recalculados dos CSVs em
  `results/rodada-7-*` antes de citar; batem com `docs/ANALISE-RODADA-7.md`.
  Os dois exemplos de 10.2 (CWE-352 16/17, CWE-328 29/41) são do braço de
  triagem do qwen; no filtro as mesmas fichas deram 1/41 e 0/17, e o texto diz
  isso. O baseline do gemma no filtro entra na §5.6 restrito aos mesmos casos
  da `tab:filtro` (822 vereditos, 19 vulneráveis: 5 VP, 127 FP, MCC +0,043).
- **10.4:** H5 trata do componente neural, não do motor simbólico; na figura
  fica abaixo da explicação sobrevivente, ligada por seta tracejada, com o
  mesmo formato e carimbo das outras. Legenda e frase de abertura da seção
  dizem isso.
- **10.5:** `resultados.tex` não é versionado, então o `git diff` foi feito
  contra um instantâneo tirado antes das edições: 4 linhas anteriores
  alteradas, nenhuma com tabela ou valor numérico.
- **11.2:** `haque2025quantized` (arXiv 2512.08213, conferido); é sobre geração
  de código, e o texto cita com esse escopo. Os dois TODOs foram substituídos.

## Registro de execução (2026-09-24) — reexecução R4–R6 e Rodada 7b

- Números de referência continuam os das execuções originais
  (`resultados_parte2/README.md`); a reexecução foi usada para marcar o que se
  reproduz. Tudo recalculado dos CSVs de `resultados_parte2/` antes de citar.
- **Q1:** especialista do gemma no filtro (R7b, catálogo por CWE) é PIOR que o
  baseline do gemma: McNemar 96 × 49 a favor do baseline (p ≈ 0,0001), FP
  127 → 173, MCC −0,002; 47 dos FP novos na CWE-327 (57 contra 10 do baseline).
  A resposta da Q1 passou a ser declarada dependente do modelo.
- **Rodada 5 suavizada:** p 0,0090 → 0,086; precisão 49,4 % na reexecução;
  régua 2,0× → 1,3×; recall dos injetados reproduz (4,49 %).
- **"Replicação" do MCC +0,159 × +0,161** substituída: na reexecução, +0,110
  sobre os mesmos 827 casos.
- **§5.6:** ordenação qwen × gemma pelo MCC na pilha de alertas não é estável
  entre execuções; no filtro, qwen > gemma com o especialista (176 × 16) e sem
  diferença no baseline (97 × 82, p = 0,30).
- **tab:filtro:** linhas do gemma no filtro (R7, R7b); linhas R5/R6 separadas e
  marcadas como leitura da pilha dentro da triagem.
- **Limitações:** parágrafo da Rodada 7 com os 4 cenários pareados (3 de 4 para
  a ficha por CWE; exceção gemma/filtro) e item novo de reprodutibilidade.
