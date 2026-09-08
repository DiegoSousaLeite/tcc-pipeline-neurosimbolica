# Apontamentos da banca do TCC 1 — pontos de melhoria para o TCC 2

Fonte: anotações da Profa. Elaine Venson + transcrição da defesa do TCC 1.
Banca: Prof. Dr. Glauco Vitor Pedrosa e Prof. Dr. André Barros de Sales.

Escopo deste documento: **somente** os apontamentos levantados pela orientadora e
pelos avaliadores. Não inclui a transição estrutural TCC 1 → TCC 2 nem auditorias
internas anteriores.

Caminho base dos arquivos: `TCC2___Diego_Sousa_e_João_Artur_Leles/`

---

## Visão geral

| # | Avaliador | Apontamento | Arquivos afetados | Tipo | Bloqueia? |
|---|---|---|---|---|---|
| G1 | Glauco | Justificativa CodeQL/Semgrep melhor na fala que no texto | `referencialteorico.tex` | Reescrita argumentativa | Não |
| G2 | Glauco | Qual o menor contexto? Usar outro LLM? | escopo do experimento | **Decisão de escopo** | — |
| G3 | Glauco | Ollama | `metodologia.tex` | Código pronto, falta texto | Não |
| G4 | Glauco | "Neuro-simbólico não é integração, achar outro termo" | 8 arquivos, título incluso | **Decisão de nomenclatura** | **Sim** |
| A1 | André | Acerto do LLM só se liga à 1ª coluna do detector | `metodologia.tex`, `provadeconceito.tex` | Figura + texto | Não |
| A2 | André | Incluir classificação científica da metodologia | `metodologia.tex` | Seção nova | Não |
| A3 | André | Cronograma: prazos, ponto crítico, contingência | `metodologia.tex` + cap. de resultados | Remoção + Discussão | Não |

---

## G1 — Justificativa do Semgrep

> *"justificativa do CodeQL/Semgrep está melhor na apresentação do que no texto"* — Elaine (Glauco)

**Diagnóstico.** Não falta informação: os quatro motivos (dispensa build, achado na
linha exata, nativo de CI, adequado a reanálise de commits históricos) estão nos dois
lugares. O que falta no texto é a **estrutura do argumento**.

| Aspecto | Falado (`apresentacao/roteiro-diego.md:69-71`) | Escrito (`referencialteorico.tex:16`) |
|---|---|---|
| Anúncio da escolha | 2ª frase — *"que é a ferramenta que adotamos"* | última frase — *"razão pela qual foi adotado"* |
| Requisito do trabalho | posto explicitamente antes do veredito | oração subordinada no fim de frase longa |
| Os 4 motivos | reunidos numa frase, colados à conclusão | dispersos nas frases 1, 3 e 4 |
| GitLab / DevSecOps | ausente | ocupa 2/3 da frase 3, entre os motivos e a conclusão |

Mesmo efeito, menor, no CodeQL (`referencialteorico.tex:14`): falando, o *build* é
**impeditivo** ("trava a análise de versões históricas de terceiros"); escrito, é
propriedade neutra ("eleva o tempo e a fragilidade da análise").

**Ação.** Reestruturar `referencialteorico.tex:14-16` como decisão, não como
inventário: requisito → CodeQL não atende → Semgrep atende → portanto. Mover o
GitLab para fora do trecho conclusivo. Avaliar tabela comparativa, que é o que o
slide 7 fazia visualmente.

---

## G2 — Menor contexto / outro LLM

> *"qual o menor contexto que podemos trabalhar? usar outro LLM?"* — Elaine (Glauco)
> *"se trabalhar com o contexto, ótimo. Então tem como reduzir o contexto para ter
> esses elementos? É uma outra contribuição que vocês podem agregar"* — André,
> endossando (50:47)

**Contexto factual.** O prompt mediano mede ~1,1k tokens: contexto não é o gargalo
de custo do experimento. Além disso, o desenho já contém um braço de menor contexto
— o prompt *baseline* não recebe ancoragem de CWE, heurísticas de Go nem few-shot.

**Decisão em aberto.** Três caminhos:

| Opção | O que envolve | Custo |
|---|---|---|
| A | Responder com medição + argumentar que o baseline já é o braço de menor contexto | Zero execução nova |
| B | Novo fator experimental de hidratação (sem hidratação × função × arquivo) | Triplica um eixo do fatorial |
| C | Registrar só como trabalho futuro | Deixa pergunta direta da banca sem resposta empírica |

**Status:** aguardando decisão.

---

## G3 — Ollama

> *"Ollama?"* — Elaine (Glauco)

**Já implementado.** Commit `7ab82dc` — *"adiciona provedor local via Ollama como
terceiro braço do eixo modelo"*; spec arquivada em `af9bc32`; código em
`src/provedores/ollama.py`.

**Ação — falta refletir no texto, em dois pontos:**

| Arquivo | Linha | O que fazer |
|---|---|---|
| `metodologia.tex` | 14 | Fator "Modelos de inferência" lista só `gemini-3.1-pro-preview` e `gpt-5.4`; incluir o provedor local |
| `metodologia.tex` | 316 | Limitação "Dependência de APIs e Modelos Proprietários" afirma dependência absoluta de terceiros — deixou de ser verdade |

---

## G4 — Termo "integração neuro-simbólica"

> *"neuro-simbólico: não é integração, achar outro termo"* — Elaine (Glauco)

**Decisão em aberto e bloqueante:** não se sabe se a objeção é à palavra
*integração* (mantendo *neuro-simbólico*) ou ao conceito inteiro. Confirmar com a
Elaine antes de qualquer edição — o termo atravessa o documento todo.

**Superfície de impacto — 30 ocorrências em português + 2 em inglês:**

| Arquivo | Ocorrências | Observação |
|---|---|---|
| `informacoes.tex` | 2 | **título** (linha 6) e **palavra-chave 2** (linha 9) |
| `resumo.tex` | 2 | |
| `abstract.tex` | 2 | `neuro-symbolic architecture`, linhas 3 e 8 |
| `introducao.tex` | 3 | |
| `referencialteorico.tex` | 9 | inclui **título de seção** (linha 93) |
| `metodologia.tex` | 12 | inclui **título de subseção** (linha 123) |
| `provadeconceito.tex` | 1 | |
| `consideracoes.tex` | 1 | |

Ocorrências exatas da expressão "integração neuro-simbólica": `informacoes.tex:6`,
`introducao.tex:11`, `metodologia.tex:35`, `referencialteorico.tex:4`, `:93`, `:96`.

Fora do `.tex`, o termo também está na capa e no rodapé de todos os slides
(`apresentacao/`).

**Ordem de execução:** resolver G4 **antes** dos demais itens que tocam os mesmos
parágrafos, para não reescrever duas vezes.

---

## A1 — Vínculo entre as duas matrizes

> *"na explicação ela ficou boa, mas não está no texto (…) a parte do acerto do LLM,
> ele só vai estar relacionado à primeira coluna do detector. Aí você faz o desenho,
> explica e tudo mais. Isso poderia estar tanto na apresentação (…) quanto no
> documento escrito também"* — André (50:14)
>
> *"a gente deseja que não precise explicar, que o próprio texto, os gráficos, se
> apresente ali"* — André (50:47)

**Diagnóstico.** A `fig:matrizes` (`metodologia.tex:239-274`) desenha as duas matrizes
**lado a lado, como irmãs**, sem nenhum elemento ligando uma à outra. O vínculo — a
matriz de acerto do LLM é calculada **só sobre a coluna "Detectou"** da matriz de
cobertura — foi dito em voz alta no slide 16 e existe em prosa
(`metodologia.tex:226-227`), mas não aparece em nenhuma figura.

**Ação, em três lugares:**

| Arquivo | Linha | O que fazer |
|---|---|---|
| `metodologia.tex` | 239-274 | Seta/marcação explícita da coluna "Detectou" → matriz do LLM |
| `metodologia.tex` | 226 | Reforçar o vínculo no texto que introduz a matriz de acerto |
| `provadeconceito.tex` | tab. cobertura/acerto | Explicitar que os 6 alertas da matriz de acerto **são** os 6 da coluna Detectou (0 vulnerável + 6 seguro) |

---

## A2 — Classificação científica da metodologia

> *"eu acho que a parte da metodologia poderia ser melhor detalhada a nível de um
> aspecto científico (…) É uma pesquisa aplicada, não é aplicada, é um estudo de caso?
> Então vocês podem trazer os termos mesmo científicos para dentro do documento, para
> vocês se situarem"* — André (51:05)

**Estado atual.** `metodologia.tex:8` traz apenas *"abordagem empírica e quantitativa,
estruturada sob a forma de um experimento controlado"* — sem taxonomia formal e sem
referência metodológica.

**Ação.** Nova subseção em `metodologia.tex`, dentro de "Plano Metodológico"
(seção na linha 6), classificando a pesquisa quanto a natureza, objetivos, abordagem
e procedimentos, com citação metodológica de apoio.

**Item relacionado, do mesmo bloco da banca —** enquadramento como replicação:

> *"vocês estão fazendo uma replicação de um estudo que estava para Java e está indo
> para o Go. É válido como um trabalho de TCC (…) a replicação também não é de todo
> em si inválida. Ela é válida para mostrar o conhecimento de vocês"* — André (52:12),
> concordando com o Glauco

Assumir o enquadramento dentro desta mesma seção — replicação diferenciada é uma
classificação legítima, e nomeá-la desarma a crítica em vez de contorná-la.

---

## A3 — Cronograma, ponto crítico e contingência

> *"o que a gente espera de um engenheiro de software é que ele saiba fazer um
> planejamento das atividades"* — André (51:56)
>
> *"qual dessas atividades seria um ponto crítico? Está tudo assim, tudo é um mês (…)
> existe algum risco de insucesso de uma dessas atividades? E qual seria? E como é que
> vocês estão planejando um plano de contingência?"* — André (53:20)

**O que foi respondido na defesa:**

- João (53:53): o dataset é o ponto mais crítico; **não havia plano de contingência**.
- Diego (54:26): segundo ponto crítico — engenharia de prompts e execução dos testes,
  que andam acopladas e podem estourar os dois meses previstos.

**Ação em duas partes:**

| Parte | Onde | O que fazer |
|---|---|---|
| Remoção | `metodologia.tex:337` | A seção "Cronograma" sai no TCC 2 — não há mais atividades futuras a planejar |
| Resposta | capítulo de resultados (Discussão) | O risco previsto **se materializou**: o dataset foi de fato o gargalo. Registrar o que aconteceu e como foi contornado responde ao André com evidência, não com plano |

---

## Pendências de decisão

| Item | Decisão necessária | Quem decide |
|---|---|---|
| G4 | O que exatamente o Glauco quis dizer com "não é integração" | Confirmar com a Elaine |
| G2 | Medir e argumentar (A), novo braço experimental (B) ou trabalho futuro (C) | Diego / João |

**Nenhum arquivo do TCC foi alterado até aqui.**
