## Context

**O detalhamento desta change vive em
[`docs/PLANO-ESCRITA-RESULTADOS.md`](../../../docs/PLANO-ESCRITA-RESULTADOS.md).**
Aquele documento especifica o padrão de redação extraído dos capítulos
existentes, as nove figuras com o que cada uma mostra e por quê, a ordem de
escrita em seis etapas, e as pendências de cada capítulo. Este design registra
apenas as decisões; consultar o plano antes de executar qualquer tarefa.

Estado de partida, em 22/09/2026:

| Artefato | Estado |
|---|---|
| `editaveis/resultados.tex` | Rascunho estrutural, não versionado. 9 seções, 6 tabelas preenchidas, prosa pronta no enquadramento e na discussão |
| `editaveis/metodologia.tex` | Modelos corrigidos para os que de fato rodaram. Três afirmações sobre taint ainda falsas |
| `fixos/bibliografia.bib` | 9 entradas novas acrescentadas, 3 marcadas `% VERIFICAR` |
| `tcc.tex` | Não inclui `resultados` |
| Seis `docs/ANALISE-RODADA-*.md` | Fonte de todos os números |

**Fases da esteira tocadas:** nenhuma. Esta change não executa código.

**Custo de LLM:** zero.

**Dependências novas:** possivelmente `pgfplots` em `fixos/pacotes.tex` — ver D2.

## Goals / Non-Goals

**Goals:**

- Transformar seis documentos de análise em capítulo defensável.
- Fechar as duas perguntas hoje sem seção: a Questão Geral e a Q4.
- Corrigir as afirmações da metodologia que o capítulo de resultados
  contradiria.
- Deixar o capítulo pronto **antes** da rodada comercial, com a dependência
  isolada em quatro lugares.

**Non-Goals:**

- Executar rodada.
- Alterar código.
- Tocar no bloco `\begin{comment}` da metodologia.
- Escrever introdução e considerações finais antes de o capítulo fechar.

## Decisions

### D1 — O plano em `docs/` é a fonte, esta change é o contrato

**Decisão:** o detalhamento — padrão de escrita, especificação das figuras, ordem
de escrita — fica em `docs/PLANO-ESCRITA-RESULTADOS.md`. A change carrega os
requisitos verificáveis e as tarefas.

**Por quê:** o plano é documento de trabalho, consultado durante a redação e
revisado conforme o texto evolui. Duplicá-lo aqui criaria duas versões que
divergiriam no primeiro ajuste. A spec descreve o que precisa ser **verdade** ao
final; o plano descreve **como** chegar lá.

### D2 — `pgfplots` é decisão do autor, não desta change

**Decisão:** o plano recomenda acrescentar `pgfplots` a `fixos/pacotes.tex`, mas
a change não o faz por conta própria. Se a decisão for negativa, as três figuras
de barra são desenhadas em TikZ puro.

**Por quê:** `fixos/` é a parte do modelo da FGA que não se mexe por hábito.
Escala correta em gráfico de barras é a diferença entre ilustrar e enganar, e por
isso a recomendação existe — mas a decisão de tocar no modelo é do autor.

### D3 — A auditoria qualitativa serve a duas perguntas de uma vez

**Decisão:** a amostra de 30 a 50 vereditos lidos à mão classifica cada um em
dois eixos: **tipo de fundamento** (correto / correto por motivo errado /
alucinação), que responde à Q4; e, para os casos de gabarito seguro que o modelo
manteve, **se eram de fato seguros**, o que mede a ameaça da classe negativa
aproximada.

**Por quê:** as duas análises leem os mesmos registros. Separá-las custaria duas
passagens sobre o mesmo material, e a segunda hoje é ameaça declarada sem número
— o que é a forma mais fraca de declarar ameaça.

**Tamanho da amostra:** 30 é o limiar que o projeto já adota para poder
estatístico; 50 dá folga. A amostra SHALL ser estratificada por veredito, para
que os casos em que o modelo manteve o alerta não fiquem sub-representados — eles
são minoria (15 de 827 no braço especialista) e são justamente os interessantes.

### D4 — Ordem de escrita começa pelos dois braços

**Decisão:** a §5.1 (desenho dos dois braços, com as Figuras 1 e 2) é escrita
primeiro, antes de qualquer seção de número.

**Por quê:** sem a distinção clara entre braço de filtro e braço de triagem,
nenhum número do capítulo se lê corretamente — a distinção foi mal compreendida
mais de uma vez durante o próprio desenvolvimento. Escrevê-la depois obrigaria a
revisar todas as seções anteriores.

### D5 — Correções na metodologia vêm antes do capítulo que as usa

**Decisão:** as três frases sobre trilha de taint são corrigidas na Etapa 1,
antes de a discussão dos resultados ser escrita.

**Por quê:** a discussão explica a distância para trabalhos correlatos pela
ausência da trilha. Escrevê-la enquanto a metodologia afirma o contrário produz
um documento que se contradiz, e a correção posterior é mais fácil de esquecer do
que a anterior.

## Risks / Trade-offs

**[A Q4 revelar que o raciocínio é ruim]** → Possível, e não é motivo para não
fazer. Se a auditoria mostrar que o modelo acerta por motivo errado com
frequência, isso é resultado — e converge com o achado de que a redução de ruído
vem majoritariamente de rejeitar tudo. Reportar.

**[A auditoria ser subjetiva]** → É. Mitigação: classificar segundo critério
escrito antes de ler os casos, registrar o critério no capítulo, e declarar que a
classificação foi feita pelos autores sem cegamento. Declarar a limitação vale
mais do que fingir objetividade.

**[O capítulo crescer demais]** → Nove figuras e seis tabelas em um capítulo é
muito. Mitigação: as Figuras 9 e, se necessário, 4 podem ir para apêndice sem
perda de argumento.

**[Escrever antes da rodada comercial e ter de refazer]** → Mitigado por
construção: o plano isola a dependência em quatro lugares — as linhas de
`tab:modelos`, uma série da Figura 8, o item de escopo nas limitações, e um
parágrafo da discussão.

**[Commitar por engano]** → Já aconteceu uma reversão que levou trabalho não
commitado junto. Mitigação: o requisito de não commitar é o primeiro da spec, e
o plano abre com o aviso em destaque.

## Migration Plan

Não se aplica: não há código a migrar. A ordem de execução está nas tarefas, e
segue a §4 do plano.

**Rollback:** as edições vivem na árvore de trabalho até o autor commitá-las.
Desfazer é `git checkout` do arquivo — com a ressalva, aprendida em 22/09/2026,
de que isso também descarta o que ainda não foi commitado.

## Open Questions

- `pgfplots` entra? (D2) — decisão do autor, bloqueia as Figuras 6, 7 e 8.
- As três entradas marcadas `% VERIFICAR` em `fixos/bibliografia.bib` serão
  confirmadas ou rebaixadas? Afeta como `alatasi2026aisast` e `white2025feature`
  podem ser citadas no texto.
- A Q4 entra como seção do capítulo de resultados ou como capítulo próprio de
  análise qualitativa? O plano assume seção; se a auditoria render muito, pode
  justificar mais.
- O cronograma da metodologia precisa ser atualizado, ou fica como registro do
  que foi planejado em TCC 1?
