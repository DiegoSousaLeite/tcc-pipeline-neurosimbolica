# Plano de escrita — Capítulo de Resultados e ajustes nos demais capítulos

> ## ⛔ NÃO COMMITAR
>
> Nada do que este plano produz deve ser commitado sem pedido explícito do
> autor. Vale para `editaveis/*.tex`, `fixos/bibliografia.bib` e para este
> próprio documento. O texto da monografia está em revisão ativa e uma edição
> commitada por engano é mais difícil de rastrear do que uma perdida — já houve
> uma reversão de `metodologia.tex` em 22/09/2026 que levou junto trabalho não
> commitado. Editar, mostrar, e **parar**.

**Criado em** 2026-09-22.
**Premissa central:** a rodada com LLM comercial acontece **depois**. O plano é
desenhado para que ela toque o menor número possível de lugares — ver §5.

**Estado de partida:** `editaveis/resultados.tex` existe como rascunho estrutural
(não versionado), com 9 seções, 6 tabelas preenchidas e prosa pronta nas partes
de enquadramento. O que falta é narrar os números e desenhar.

---

## 1. Padrão de escrita a manter

Extraído de `metodologia.tex` e `provadeconceito.tex`, que são a referência:

| Elemento | Padrão do documento |
|---|---|
| Voz | Impessoal, passiva. *"Verificou-se que"*, *"O experimento foi montado"*. Nunca "nós fizemos". |
| Parágrafos | Longos e corridos. Um argumento por parágrafo, sem listas quando a prosa dá conta. |
| Estrangeirismos | `\textit{}` — *prompt*, *dataset*, *recall*, *commit*, *pipeline*. |
| Código e identificadores | `\texttt{}` — `p/default`, `NAO_DETECTADO`, `run_pipeline.py`. |
| Blocos de saída | `\begin{verbatim}` com recuo, como nas Fases 1 e 2 da PoC. |
| Referência cruzada | `Seção~\ref{}`, `Figura~\ref{}`, `Tabela~\ref{}` — sempre com `~`. |
| Citação | `\cite{chave}` no fim da frase; `\citeonline{chave}` quando o autor é sujeito. |
| Tabelas | `[htpb]`, `\centering`, `\caption` **antes**, `\label`, `\renewcommand{\arraystretch}{1.4}`, `tabular` com `|` e `\hline` em toda linha. |
| Figuras | `[htpb]`, `\centering`, `\caption` **antes**, `\label`, depois `tikzpicture`. |

**Regra de ouro herdada da PoC:** todo número vem acompanhado da ressalva que o
limita, no mesmo parágrafo. O capítulo de Prova de Conceito já faz isso
(*"os números aqui apresentados têm caráter ilustrativo"*), e é o que dá
credibilidade ao texto.

---

## 2. Decisão pendente: `pgfplots`

`fixos/pacotes.tex` traz `tikz` mas **não** `pgfplots`. As figuras existentes
(`fig:arquitetura`, `fig:matrizes`, `fig:taint`) são TikZ desenhado à mão.

| Opção | A favor | Contra |
|---|---|---|
| **A — TikZ à mão** | Coerente com as figuras existentes; não toca em `fixos/` | Barras e eixos manuais dão trabalho e erram escala com facilidade |
| **B — acrescentar `pgfplots`** | Gráficos corretos por construção, eixos e escala automáticos | Mexe em `fixos/pacotes.tex`, que é a parte "fixa" do modelo da FGA |

**Recomendação: B**, com uma linha só (`\usepackage{pgfplots}` +
`\pgfplotsset{compat=1.18}`). Os gráficos de barra desta seção precisam de
escala correta — é a diferença entre ilustrar e enganar. Mas é decisão do autor,
porque envolve tocar em `fixos/`.

Se ficar em A, as figuras 6, 7 e 8 abaixo viram barras desenhadas com
`\fill` e coordenadas calculadas à mão; funcionam, mas exigem conferir cada
largura contra o valor.

---

## 3. As figuras do capítulo

Nove figuras. Esta é a parte que mais falta e a que mais rende para o leitor.

### Fig. 1 — `fig:funil` · O funil da população
**Onde:** §5.1, logo após a descrição dos braços.
**O que mostra:** para onde vão os 2.328 casos.

```
2.328 casos
├── 1.531 seguros ──► ~808 geram alerta ──► RUÍDO (vai ao LLM)
│                     └── ~723 silêncio ──► fora da avaliação
└──   797 vulneráveis ─►  19 detectados ──► vai ao LLM
                       └── 778 NAO_DETECTADO ──► descartados no braço de filtro
```
**Forma:** TikZ, caixas com setas, larguras proporcionais à contagem.
**Por que importa:** é a figura que explica o trabalho inteiro. Se o leitor só
olhar uma, que seja esta.

### Fig. 2 — `fig:doisbracos` · O que difere entre os braços
**Onde:** §5.1, imediatamente depois da Fig. 1.
**O que mostra:** dois painéis lado a lado, idênticos exceto pelo destino dos
778. Painel esquerdo (filtro): a seta dos 778 termina num X. Painel direito
(triagem): a seta dos 778 entra no LLM, tracejada e rotulada "injetados".
**Forma:** TikZ, dois painéis, reaproveitando o idioma de `fig:matrizes`.
**Por que importa:** esta distinção foi mal compreendida mais de uma vez durante
o próprio desenvolvimento. Um leitor de banca vai tropeçar nela se não houver
desenho.

### Fig. 3 — `fig:rotulo` · Por que o arquivo rotulado não tem a operação
**Onde:** §5.5.5 (a explicação sobrevivente). **É a figura mais importante do
argumento.**
**O que mostra:** um *commit* de correção tocando dois arquivos —
`handler.go`, onde a verificação foi **acrescentada**, e `storage.go`, onde a
operação perigosa sempre esteve. O gabarito aponta para `handler.go`. A regra
procura `os.Open` e não o encontra ali.
**Forma:** TikZ com dois blocos de código estilizados e um marcador de gabarito.
**Por que importa:** explica os ~30% melhor do que qualquer parágrafo.

### Fig. 4 — `fig:abstracao` · A operação atrás da abstração
**Onde:** §5.5.5, após a Fig. 3.
**O que mostra:** lado a lado, `os.Open(caminho)` (regra casa) e
`fs.Open(caminho)` onde `fs` é um `afero.Fs` (regra não casa). Seta da regra
apontando só para o primeiro.
**Forma:** TikZ com dois trechos em `\texttt` e um símbolo de casamento/não.
**Por que importa:** cobre os 26% (CWE-22) e 44% (CWE-918) que a Fig. 3 não
explica.

### Fig. 5 — `fig:eliminacao` · A cadeia de hipóteses rejeitadas
**Onde:** abertura da §5.5.
**O que mostra:** quatro caixas em sequência, cada uma com a hipótese, a
medição e um carimbo "rejeitada", desembocando numa quinta caixa destacada com a
explicação sobrevivente.
**Forma:** TikZ, fluxo vertical.
**Por que importa:** torna visível a estrutura argumentativa — que é o que
distingue este trabalho.

### Fig. 6 — `fig:cwe-barras` · Detecção por CWE
**Onde:** §5.4.
**Dados:** CWE-89 38,9% · CWE-601 30% · CWE-79 8,8% · CWE-918 0,9% · CWE-22 0%.
**Forma:** barras horizontais, ordenadas decrescentes, com a contagem de pares ao
lado de cada barra.
**Por que importa:** mostra num relance que o motor funciona onde a forma é
sintática local e falha onde exige fluxo.

### Fig. 7 — `fig:tra-tfn` · O compromisso entre TRA e TFN
**Onde:** §5.8.2 (padrão de supressão excessiva).
**O que mostra:** eixo X = TRA, eixo Y = TFN. Uma linha tracejada marcando o
classificador degenerado ("diz não para tudo": TRA 1,0 / TFN 1,0). Pontos para
*baseline* (0,85 / 0,58) e especialista (0,98 / 0,84), mostrando que o
especialista se aproxima do degenerado.
**Forma:** dispersão com anotações.
**Por que importa:** é o argumento mais delicado do capítulo e o mais difícil de
sustentar só em prosa.

### Fig. 8 — `fig:recall-comparado` · Recall em perspectiva
**Onde:** §5.8.1.
**Dados:** este trabalho (filtro 2,4%), este trabalho (triagem 4,3–7,4%),
Semgrep no RealVuln (17,5%), CodeQL no CWE-Bench-Java (22,5%), faixa do
Semgrep\* (11,2–26,5%), união de 4 ferramentas (38,8%).
**Forma:** barras horizontais com a legenda de cada estudo.
**⚠ Obrigatório:** legenda declarando que **não são comparáveis entre si** —
linguagens, motores e critérios diferentes. Serve para situar ordem de grandeza.
**→ Esta é uma das figuras que a rodada comercial altera (§5).**

### Fig. 9 — `fig:contexto-braco` · O que o modelo recebe em cada braço
**Onde:** §5.1, no fecho, ou como apêndice.
**O que mostra:** o cabeçalho do candidato nos dois braços, evidenciando que no
modo triagem os campos do alerta são removidos **para as duas procedências**, de
modo que o injetado seja indistinguível.
**Forma:** dois blocos `verbatim` lado a lado em TikZ, com os campos removidos
riscados.
**Por que importa:** é a guarda de integridade do experimento; sem mostrá-la, a
banca tem razão de perguntar se a injeção não deixou pista.

---

## 4. Ordem de escrita

Sequência pensada para que cada etapa produza texto que não será refeito.

### Etapa 1 — Fundação (não depende de nada)
1. §5.1 completa, com Fig. 1 e Fig. 2. **Começar aqui**: sem a distinção entre
   braços clara, nenhum número do capítulo se lê direito.
2. §5.7 Limitações — escrever cedo, porque cada seção seguinte vai remeter a ela.

### Etapa 2 — O resultado positivo
3. §5.2 (Q1), com o McNemar e as duas subseções de achado não planejado.
4. §5.3.1 (Q2 no braço de filtro), com a Tabela `tab:filtro`.

### Etapa 3 — O teto
5. §5.3.2 e §5.3.3 (braço de triagem e a distância entre braços).
6. §5.4 (Q3), com Fig. 6. Incluir a subseção de concorrência — é resultado, não
   lacuna.

### Etapa 4 — O argumento central
7. §5.5 inteira, com Fig. 5, Fig. 3 e Fig. 4. **É a seção mais longa e a mais
   valiosa; reservar tempo.**

### Etapa 5 — Fecho
8. §5.8 Discussão, com Fig. 7 e Fig. 8. A prosa da inversão do OpenVuln já está
   escrita; falta narrar as demais subseções.
9. §5.6 Comparação de modelos — **deixar por último**, é a que espera a rodada
   comercial.

### Etapa 6 — Depois da rodada comercial
Ver §5 abaixo.

---

## 5. O que a rodada comercial toca — e só isso

Princípio de desenho: **isolar a dependência**. Escrito conforme este plano, o
capítulo inteiro fica pronto antes da rodada, e ela altera quatro lugares:

| Lugar | O que muda |
|---|---|
| `tab:modelos` (§5.6) | Acrescenta linhas dos modelos comerciais |
| `fig:recall-comparado` (Fig. 8) | Acrescenta uma série |
| §5.7, item "Escopo de modelos" | Deixa de dizer "modelos locais de 7 a 9 bilhões" |
| §5.8.2, um parágrafo | Se o comercial confirmar a supressão excessiva, reforça; se não, ressalva |

**Nada mais.** Nenhuma seção precisa ser reescrita.

**Acrescentado em 2026-09-23 (Rodada 7):** a rodada comercial passa a ter uma
**segunda execução opcional**, com o catálogo por regra
(`--catalogo data/catalogo_cwe_por_regra.json`, só o especialista, só o filtro).
Ela testa se um modelo que segue condições usa a ficha como contexto de verdade,
e não só como postura. Comandos e leitura: `docs/MAPA-TCC-O-QUE-REESCREVER.md`
§11.8. Se for feita, toca **um lugar a mais**: o parágrafo de ablação da §5.7
(abaixo, §6.7) ganha a linha do modelo comercial. A primeira execução, com o
catálogo por CWE, é a que alimenta a tabela acima — é ela que se compara com as
Rodadas 1–6.

**Dado novo a considerar (2026-09-22):** uma execução preliminar com
`gemini-2.5-flash-lite` no braço de triagem obteve *recall* de 7,39% sobre ~406
casos injetados — praticamente idêntico aos 7,41% do `gemma2:9b` local. Se o
número se sustentar numa rodada completa, ele **reforça** a tese de que o teto
não é de capacidade de modelo. Conferir antes de citar: identidade exata do
modelo, trilhas incluídas e por que foram 406 e não 778.

---

## 6. Mudanças fora do capítulo de Resultados

### 6.0 `metodologia.tex` — PENDÊNCIAS CRÍTICAS (levantadas em 22/09/2026)

Achadas na leitura integral do capítulo. As três primeiras são **defeitos de
fato**, não ajustes de estilo.

#### 6.0.1 ⚠ A Fase 1 afirma produzir trilha de taint. Não produz.

**Linha 86:**

> *"...um relatório estruturado no formato SARIF, que conterá a localização do
> alerta, a categoria da fraqueza associada (CWE), **além do rastreio do fluxo de
> dados desde a sua origem (source) até a sua utilização em um ponto crítico
> (sink), por meio do modo de rastreamento de dados corrompidos (taint mode)**."*

**Medido: 0 de 807 alertas do corpus trouxeram trilha de fluxo**, mesmo com
`--dataflow-traces`. O SARIF não contém esse rastreio. É uma das três trocas de
frase sobre taint já registradas como pendentes.

**Por que é grave, e não cosmético:** a discussão dos resultados
(`subsec:porquemelhor`) explica a distância para o ZeroFalse dizendo que *aquele
trabalho entrega a trilha completa ao modelo e este não tem trilha alguma*. Com
a metodologia afirmando o contrário, o documento se contradiz internamente. É o
tipo de inconsistência que uma banca que leia os dois capítulos encontra.

**Herdeiras da mesma frase:**
- **Linha 89** — *"extrairá um bloco de código adjacente ao redor de cada ponto
  do rastreio"*. Não há rastreio; a hidratação extrai a função que contém a
  linha do alerta.
- **Linha 95** — *"chamada via API HTTP REST para os dois modelos de linguagem
  de fronteira definidos no plano metodológico"*. Defasagem do item de modelos,
  corrigido em 22/09; esta frase não acompanhou.

#### 6.0.2 ⚠ Faltam duas seções inteiras em `resultados.tex`

A metodologia declara **cinco** perguntas; o rascunho do capítulo cobre três.

| Pergunta | Métricas declaradas (Seção~`sec:metricas`) | Seção nos resultados |
|---|---|---|
| **Questão Geral** — fadiga de alertas | TRA, Proporção de FP Filtrados | ❌ **falta** |
| Q1 — enriquecimento semântico | Precisão, F1, MCC | ✅ `sec:q1` |
| Q2 — reduz FP sem introduzir FN | Recall, TFN | ✅ `sec:q2` |
| Q3 — CWEs de Go, concorrência | Acurácia por CWE | ✅ `sec:q3` |
| **Q4** — raciocínio do modelo | Auditoria qualitativa de `reasoning` | ❌ **falta** |

- **Questão Geral:** barata. Os números existem (TRA 98,19 %; especificidade
  796/808). Falta seção própria, em vez de ficarem diluídos na Q2. Entra como
  `sec:geral`, antes da Q1.
- **Q4:** é a única pergunta do trabalho **sem nenhum dado coletado**. Pede
  verificação manual do campo `reasoning` para atestar se a decisão veio da
  fundamentação correta ou de alucinação. Nenhuma das seis rodadas fez essa
  auditoria.

**Como responder à Q4 sem rodada nova:** os `reasoning` já estão nos CSVs.
Amostrar 30–50 vereditos, ler à mão e classificar por tipo de fundamento
(correto / correto por motivo errado / alucinação). De quebra, essa mesma
amostragem mede a ameaça da **classe negativa aproximada** — quantos dos
"falsos positivos" do gabarito eram vulnerabilidade real de outra CWE —, que
hoje está declarada sem número.

#### 6.0.3 A limitação sobre APIs descreve um experimento que não foi o executado

**Item "Dependência de APIs e Modelos Proprietários"** fala em custo, limite de
taxa e latência de APIs de terceiros. A maior parte dos vereditos veio de modelo
**local**: custo zero, sem limite de requisição, determinístico.

Reescrever para refletir o que de fato limita, e acrescentar as duas ausentes:
- **quantização em 4 bits** (`Q4_K_M`), com a evidência de que esse nível de
  compressão afeta comportamento em tarefas de segurança de código mais que a de
  8 bits;
- **janela de contexto dos modelos locais**, com a perda de amostras por estouro
  medida na Rodada 4 (prompts de até ~27.420 tokens contra teto efetivo de
  7.680).

A dependência de API continua valendo — mas para o braço comercial, e como
ameaça à reprodutibilidade de longo prazo, não como custo operacional.

#### 6.0.4 Itens menores

- **Linhas 19–31:** doze linhas em branco consecutivas após a lista de fatores.
  Inofensivas em LaTeX, mas são resíduo de edição.
- **Bloco `\begin{comment}`** (limitação sobre natureza estocástica, com uma
  entrada BibTeX colada dentro): **não mexer** — decisão do autor. Registrado
  aqui só para constar que é intencional. Vale notar que o conteúdo dele
  **volta a ser verdadeiro** quando houver rodada comercial: APIs comerciais não
  garantem determinismo nem com temperatura zero, ao contrário do braço local.
- **Cronograma:** texto ainda fala em "atividades futuras de pesquisa", que é
  redação de TCC 1.

### 6.1 `metodologia.tex` — três pontos conflitam, um é oportunidade

| Linha | Trecho | Ação |
|---|---|---|
| ~179 | *"o LLM opera como filtro puro: só é acionado..."* | **Qualificar.** Passa a descrever os dois modos de montagem, com o filtro como padrão. |
| ~242 | Matriz de acerto do LLM *"calculada exclusivamente sobre a coluna detectou"* | **Qualificar.** Vale no braço de filtro; no de triagem a população inclui os injetados. Possivelmente exige variante de `fig:matrizes`. |
| ~357 | *"Limite arquitetural do filtro puro... herda o teto de recall do analisador estático"* | **Manter e valorizar.** A metodologia *previu* o teto; os resultados o mediram. Acrescentar remissão para `\ref{sec:eliminacao}`. É um ponto forte de coerência do texto. |

**Acrescentar à metodologia** (não existia quando foi escrita):
- os dois modos de montagem de candidato, como eixo experimental;
- os *prompts* `baseline_direto` e `especialista_direto`;
- o eixo de modelo (local × comercial);
- o protocolo de partição das regras próprias, **se** a §5.5.4 permanecer no
  capítulo — o protocolo é método, não resultado.
- **de onde vem cada parte do prompt** (template, CWE do gabarito, ficha do
  catálogo por CWE, contexto da Fase 2): mapeado parte a parte em
  `docs/MAPA-TCC-O-QUE-REESCREVER.md` §12. A metodologia continua descrevendo
  **ficha por CWE** — a ficha por regra não entra aqui, só na ablação (§6.7).

⚠ **Há 13 linhas não commitadas em `metodologia.tex`** neste momento. Conferir o
que são antes de editar.

### 6.2 `referencialteorico.tex`
- Acrescentar os trabalhos correlatos lidos: `huang2026memhint`, `wang2026rican`,
  `alatasi2026aisast`, `white2025feature` — todos já em `fixos/bibliografia.bib`.
- Resolver as **3 trocas pendentes de frases sobre taint** já registradas
  (o slide 8 da apresentação já está correto; o texto não).
- ⚠ Há 4 linhas não commitadas aqui também.

### 6.3 `introducao.tex`
- A declaração de contribuição precisa incorporar a estrutura de eliminação e o
  achado de granularidade de rótulo. Escrever **depois** do capítulo de
  resultados, nunca antes.

### 6.4 `consideracoes.tex`, `resumo.tex`, `abstract.tex`
- Por último, nesta ordem. São os que mais sofrem com mudança de número.

### 6.5 `tcc.tex`
- Falta a linha de inclusão, depois de `provadeconceito`:
  ```latex
  \input{editaveis/resultados}
  ```

### 6.6 `fixos/pacotes.tex`
- Só se a decisão da §2 for pela opção B (`pgfplots`).

### 6.7 Rodada 7 — ablação da granularidade da ficha (2026-09-23)

> **Atualizado em 2026-09-24:** Rodadas 4–6 reexecutadas (mesma configuração;
> ver MAPA §11.9). Consequência para o texto: suavizar a afirmação de
> significância da Rodada 5 (p passou de 0,009 para 0,086 na reexecução).

Análise completa: `docs/ANALISE-RODADA-7.md`. Enquadramento e números prontos
para o texto: `docs/MAPA-TCC-O-QUE-REESCREVER.md` §11.6–§11.8.

**Nada do capítulo precisa ser refeito.** O catálogo por CWE continua o oficial;
os números das Rodadas 1–6 continuam valendo.

Onde a rodada entra, se entrar:

| Lugar | O que acrescentar |
|---|---|
| §5.7 Limitações / ameaças à validade | **Um parágrafo**, enquadrado como granularidade da orientação: as fichas por CWE nunca pretenderam descrever a regra do Semgrep; a orientação por regra foi testada e a por CWE venceu em 3 de 4 cenários pareados (mesmo recall, menos falsos alarmes); a exceção (gemma/filtro) ocorre quando a ficha por CWE descreve outra fraqueza que a do alerta e o modelo combina as duas. **Não** escrever "corrigimos o desalinhamento e ficou pior". Texto-base e tabela em MAPA §11.6. |
| §5.8.2 (supressão excessiva) | **Reforço.** A Rodada 7 mostra o mecanismo: a ficha desloca a postura do modelo local (ceticismo com a ficha por CWE; alarme com a por regra e com o v2), sem ganho de discriminação. Recall e falsos alarmes nunca melhoram juntos. Texto-base em MAPA §11.7. **Não** escrever "o especialista compreende melhor o contexto". |
| §5.6 Comparação de modelos | O gemma nunca tinha rodado no filtro. O **baseline** do gemma no filtro (R7) vale e pode entrar na tabela: o baseline não lê ficha. O **especialista** do gemma no filtro só existe com o catálogo por regra e **não** entra na tabela principal; para tê-lo com o catálogo oficial, rodar `--prompt especialista` com o padrão (~2 h). |

Os *prompts* `*_v2` (instrução contra presumir mitigação ausente) **não** entram
no texto como braço: pioraram a acurácia em todas as quatro comparações
pareadas. No máximo, meia frase na mesma ablação.

---

## 7. Verificações antes de considerar pronto

- [ ] `make` compila sem erro e sem `Citation undefined`.
- [ ] Toda figura referenciada por `\ref` existe e toda figura existente é
      referenciada no texto.
- [ ] As entradas marcadas `% VERIFICAR` em `fixos/bibliografia.bib`
      (`alatasi2026aisast`, `white2025feature`, `li2025iris`) foram conferidas ou
      rebaixadas.
- [ ] Nenhum número aparece sem a ressalva que o limita no mesmo parágrafo.
- [ ] Os denominadores estão explícitos onde há risco de confusão — 19/797
      (2,38%) e 18/690 (2,61%) medem coisas diferentes e **não podem** aparecer
      como se fossem o mesmo.
- [ ] A Figura 8 carrega a declaração de não comparabilidade.
