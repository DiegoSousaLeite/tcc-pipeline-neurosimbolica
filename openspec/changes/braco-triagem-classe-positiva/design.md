## Context

O funil da classe positiva, medido na Rodada 3:

| Etapa | Casos |
|---|---|
| Gabarito vulnerável na população | 797 |
| Alerta emparelhado na Fase 1 | 19 (2,61 %) |
| Veredito de LLM | 19 |

`suficiencia-classe-positiva` define suficiência como **30 casos de gabarito
vulnerável produzindo veredito válido do LLM**. Estamos em 19, e as duas saídas
conhecidas estão fechadas: a fonte OSV para Go está esgotada (810 candidatas,
690 pares, só 2 de 362 repositórios batendo o teto por repo) e escalar piorou a
taxa. As alavancas que restariam — enviesar a colheita para CWEs que detectam
bem, afrouxar o guarda anti-refactor — foram recusadas por integridade, e
continuam recusadas.

A saída que sobra não é conseguir mais casos: é **parar de exigir que o Semgrep
os encontre**. É o que o SastBench faz, e o SastBench é a fonte da nossa classe
negativa. A assimetria atual é difícil de defender: aceitamos a definição de
falso positivo do benchmark e rejeitamos a de verdadeiro positivo.

**Fases tocadas:** 2 (montagem e normalização do candidato), 5 (procedência no
CSV). A Fase 1 **não muda** — continua rodando o Semgrep e escrevendo
`DETECTADO`/`NAO_DETECTADO`; o braço de triagem lê esse status e não o
sobrescreve. As Fases 3 e 4 não mudam — recebem contexto hidratado e devolvem
veredito, indiferentes a quem montou o candidato.

**Arquivos tocados:** `src/fase2_middleware.py`, `run_pipeline.py`,
`src/fase5_auditoria.py`, `src/metricas.py`, `docs/PIPELINE.md`,
`docs/MAPA-TCC-O-QUE-REESCREVER.md`.

**Custo de LLM: zero — a rodada desta change é local.** Por decisão do autor, a
rodada de validação usa **apenas o provedor local** (`qwen2.5-coder:7b` via
Ollama); nenhum braço comercial é executado. Isso remove a restrição que antes
governava o desenho: no modo triagem, a rodada acrescenta os 778 positivos hoje
descartados por braço, e com os dois tipos de prompt são ~3.200 chamadas — número
que o tier grátis do Gemini (20 req/dia por modelo) não comportaria, mas que o
provedor local absorve sem custo.

**O recurso escasso deixa de ser cota e passa a ser tempo de parede.** Um modelo
de 7B quantizado numa máquina de trabalho responde em segundos por chamada;
~3.200 chamadas podem significar horas. O número não é estimável daqui — depende
da máquina e do tamanho dos prompts —, e por isso a esteira mede a vazão num
subconjunto e extrapola antes de comprometer a execução longa. Ver D8.

**Consequência de método, e ela é favorável:** a comparação baseline × especialista
no braço de triagem fica *pareada dentro do mesmo modelo*, que é exatamente o que
o McNemar exige. Dois braços locais sobre a mesma população respondem à Q1 e à
metade aberta da Q2 sem depender de nenhum serviço externo — e sem a ameaça de
reprodutibilidade que o roteiro da apresentação já declara para as APIs
proprietárias.

## Goals / Non-Goals

**Goals:**

- Destravar Recall, F1, MCC e taxa de falsos negativos, respondendo a metade da
  Q2 que hoje está em branco.
- **Executar a rodada de triagem completa com o provedor local** e produzir esses
  números, não apenas a capacidade de produzi-los.
- Preservar integralmente o braço de filtro e as Rodadas 1–3.
- Produzir a evidência de que a injeção não cria artefato, em vez de afirmá-lo.
- Registrar no mapa do LaTeX o que a mudança de desenho obriga a reescrever.

**Non-Goals:**

- Substituir o braço de filtro.
- Alterar o pareamento, a Fase 1 ou o significado de `DETECTADO`.
- Tocar na Fase 0 ou na colheita.
- Editar `.tex`.
- **Executar qualquer braço comercial.** Gemini e GPT ficam de fora por decisão
  do autor. A rodada de triagem com os modelos comerciais, se acontecer, é change
  separada — e a decisão de gastar cota é dele, não de uma tarefa marcada.

## Decisions

### D1 — Modo de montagem é um eixo da matriz, não um braço a mais

**Decisão:** `filtro` e `triagem` são valores de um eixo novo, ortogonal a modelo
e prompt, e uniforme dentro de uma rodada.

**Por quê:** a alternativa — tratar triagem como um quinto braço ao lado dos
quatro — quebraria o pareamento. Braços da matriz precisam cobrir exatamente o
mesmo conjunto de `ID_Caso`, porque é isso que o McNemar exige. Um braço que vê
778 casos a mais que os outros não é pareável com eles. Como eixo uniforme por
rodada, o pareamento continua valendo *dentro* de cada rodada, e a comparação
entre modos é entre rodadas.

**Consequência:** duas rodadas em vez de uma. É o preço de manter o McNemar
válido nas duas.

### D2 — O status simbólico não é sobrescrito

**Decisão:** caso injetado permanece `NAO_DETECTADO`.

**Por quê:** `NAO_DETECTADO` é uma afirmação sobre o motor simbólico, e é
verdadeira independentemente de o LLM ter opinado. Sobrescrevê-la apagaria a
medição de cobertura que a Rodada 3 produziu e que é resultado por si só — e
`suficiencia-classe-positiva`, `metricas-comparativas` e o cache simbólico todos
comparam esse valor diretamente.

**Alternativa considerada:** um terceiro valor, `INJETADO`. Recusada pelo mesmo
motivo que `pareamento-simbolico` recusou um terceiro valor para o motivo da
não-detecção: quebraria em silêncio os consumidores que comparam o campo
diretamente. A informação vai num campo novo — procedência —, não neste.

### D3 — Emparelhamento tem precedência sobre injeção

**Decisão:** se o caso tem alerta emparelhado, o candidato vem do alerta, mesmo
no modo triagem.

**Por quê:** é o que forma o grupo de controle sem nenhum trabalho extra. Os 19
positivos detectados entram na rodada de triagem com procedência `alerta`, e a
comparação entre procedências sai de graça. Injetar por cima deles destruiria o
único controle disponível.

### D4 — Normalização acontece antes da hidratação, não no prompt

**Decisão:** os dois caminhos convergem para a mesma estrutura em
`src/fase2_middleware.py`; a Fase 3 recebe uma estrutura só e não sabe da
diferença.

**Por quê:** se a normalização ficasse no montador de prompt, cada tipo de prompt
teria que reimplementá-la, e o baseline e o especialista poderiam divergir — o
que introduziria exatamente a pista que a normalização existe para eliminar.
Convergir cedo torna a propriedade estrutural em vez de disciplinar.

**Verificação associada:** um teste que monta os dois candidatos para o mesmo
arquivo e a mesma CWE e compara as strings de prompt. Se diferirem quanto à
procedência, o teste falha.

### D5 — O que fazer quando o gabarito aponta arquivo e o alerta aponta linha

**Decisão:** o candidato injetado usa a mesma granularidade que o gabarito já
usa — **arquivo** —, e a localização de linha, quando ausente, é preenchida com
valor neutro em vez de omitida.

**Por quê:** o gabarito do projeto é por arquivo, e `populacao-classe-positiva`
proíbe comparação por número de linha na avaliação de acerto. Introduzir linha no
candidato injetado criaria uma assimetria com o gabarito e uma segunda com o
alerta do Semgrep, que aponta linha real. Preencher com valor neutro mantém a
estrutura idêntica sem inventar informação.

**Risco reconhecido:** o alerta do Semgrep aponta a linha que casou; o injetado
não aponta linha alguma. Se a hidratação usar a linha para recortar o contexto,
os dois candidatos receberão contextos de naturezas diferentes — e essa *é* a
pista que D4 quer eliminar. **Questão em aberto abaixo.**

### D6 — O candidato injetado carrega a linha inicial da função do gabarito

**Decisão:** substitui a parte prática de D5. O candidato montado a partir do
gabarito carrega `vulneravel.linha_inicio` do par TP (ou `line_start` da location,
na trilha `TP_dataset`), e não um valor neutro.

**Por quê:** a investigação (Q1) mostrou que a hidratação recorta a **função que
contém a linha**. Com linha neutra, o injetado receberia a primeira função do
arquivo; com a linha inicial da função vulnerável, `extrai_funcao` sobe até o
`func ` daquela mesma linha e devolve exatamente a função que a CVE corrigiu. Os
dois caminhos passam a entregar **uma função Go recortada pelo mesmo algoritmo** —
que é a condição que D4 exige, e que o valor neutro não cumpria.

**O que D5 preserva:** a granularidade do *gabarito* continua sendo o arquivo, e
a avaliação de acerto continua sem comparar número de linha
(`populacao-classe-positiva`). A linha é insumo do recorte, não critério de
acerto.

**Se a linha faltar:** não há candidato injetado para o caso. Nenhum par das três
trilhas está nessa situação hoje (740/740 têm `metodo: funcao`), e inventar uma
linha seria fabricar localização.

### D7 — No modo triagem, o contexto é normalizado ao código, sem campos do alerta

**Decisão:** no modo `triagem`, o cabeçalho do contexto hidratado perde
`Alerta Semgrep:`, `Mensagem:` e `Localização: linha N`, para **as duas**
procedências. Sobra o recorte do código com o mesmo cabeçalho de arquivo e faixa
de linhas que o modo filtro já emite. O modo `filtro` **não muda em byte algum**.

**Por quê:** cada um daqueles três campos é uma pista de procedência que nenhum
preenchimento neutro elimina.

- `check_id`: o candidato de gabarito não tem regra. Um `"regra desconhecida"` ao
  lado de um `go.lang.security.audit.*` real é a pista, não a ausência dela; e
  sintetizar um identificador plausível seria fabricar.
- `Mensagem`: idem, e o texto do Semgrep frequentemente já nomeia a fraqueza.
- `Localização: linha N`: a mais sutil das três. No injetado, `N` é sempre igual
  ao início da função recortada; no alerta, quase sempre cai no meio dela.
  Bastaria comparar `N` com o cabeçalho `[Arquivo: ... | Linhas A a B]` para
  separar os grupos.

**Consequência, declarada:** o braço de triagem entrega ao LLM estritamente menos
que o braço de filtro. Isso é resultado, não defeito — o número da triagem mede o
componente neural julgando **código**, sem a dica do motor simbólico. Também
implica que a diferença entre os dois braços mistura dois efeitos (quais casos
chegam, e quanto contexto cada um traz), o que precisa constar do mapa do LaTeX.

**Alternativa recusada:** manter os campos no candidato de alerta e neutralizá-los
só no injetado. É exatamente a pista que a spec proíbe.

**Efeito colateral bom:** o cabeçalho normalizado também para de vazar o nome da
CWE para o braço `baseline` por dentro do `check_id` — o que o desenho do baseline
já queria e o modo filtro nunca garantiu.

## Risks / Trade-offs

**[O número da triagem ser lido como desempenho do sistema]** → É o risco
principal, e é de redação, não de código. Num uso real os positivos não seriam
injetados; viriam do Semgrep, que perde 97,4 % deles. Mitigação: o requisito de
registro no mapa do LaTeX obriga a declarar isso, e a procedência no CSV torna
o recálculo possível para quem quiser conferir.

**[Injeção criar artefato mensurável]** → Mitigação: o grupo de controle. Se o
LLM acertar sistematicamente mais nos injetados, o número não pode ser reportado
como está. **Este risco não é hipotético** — ver a questão em aberto sobre a
hidratação.

**[Custo de cota]** → ~3.100 chamadas a mais por rodada completa da matriz 2x2.
Mitigação: piloto com o provedor local (custo zero) antes de comprometer cota
comercial; e a change entrega a capacidade sem executar a rodada.

**[Emendar uma invariante declarada]** → "O LLM é filtro puro do Semgrep" está
escrito em duas capabilities e no contexto do projeto. Emendá-la é decisão de
desenho, não ajuste. Mitigação: a emenda é *qualificação*, não remoção — a
invariante continua valendo integralmente no modo filtro, que é o padrão, e os
cenários modificados dizem isso explicitamente.

**[Divergência entre os dois modos passar despercebida]** → Mitigação: o modo
consta do manifesto e da procedência no CSV; `metricas-comparativas` lê múltiplas
rodadas e precisa saber distinguir as duas séries.

## Migration Plan

1. Procedência no CSV, com modo filtro apenas. Sem efeito observável: toda linha
   sai com procedência `alerta`. Verificar que uma rodada filtro é idêntica à
   anterior.
2. Montagem do candidato de gabarito e normalização, atrás do eixo novo,
   desligado por padrão.
3. Piloto do modo triagem com o provedor local sobre um subconjunto — custo zero,
   e já responde se o grupo de controle acusa artefato.
4. Se o controle estiver limpo, decidir sobre a rodada comercial completa.
5. Registro no mapa do LaTeX.

**Rollback:** não selecionar o modo triagem. Nenhum artefato do modo filtro é
alterado por esta change.

## Investigação prévia — respostas

### Q1 (tarefa 1.1) — A hidratação usa a linha do alerta? **Sim.**

`src/fase2_middleware.extrair_e_hidratar_contexto` lê `alerta["start"]["line"]` e
passa esse número a `src/hidratacao.extrai_funcao(linhas, alvo_idx)`, que sobe do
alvo até o `func ` mais próximo e fecha por balanceamento de chaves:

```python
linha = alerta.get("start", {}).get("line", 1)
...
resultado = extrai_funcao(linhas, linha)
```

Com o fallback de janela ±25 quando nenhum `func ` é encontrado acima. Um
candidato sem linha cairia sempre na primeira função do arquivo (`alvo_idx = 1`),
que quase nunca é a função vulnerável. **D5 do desenho original está errado na
parte prática**: preencher a linha com valor neutro produziria contexto de
natureza diferente, e D4 falharia. Ver D6.

### Q2 (tarefa 1.2) — Qual localização o candidato injetado carrega?

Ver **D6** e **D7** abaixo. O gabarito TP **tem** linha: os pares em
`tp_pairs*.json` carregam `vulneravel.linha_inicio` / `linha_fim` / `metodo`
(`funcao` em 740/740 pares das três trilhas), e as entradas `true_positive` de
`data/dataset_go_limpo.json` carregam `line_start` por função alterada. O que não
tem linha é a trilha FP (`function: "FILE_SCOPE"`, `line_start: 1`) — e FP nunca
é injetado.

### Q3 (tarefa 1.3) — `src/metricas.py` lê múltiplas rodadas? **Não.**

`carregar(alvo)` aceita **um** diretório de rodada ou **um** CSV avulso, e o
glob não é recursivo (`glob(os.path.join(alvo, "*.csv"))`): apontar para
`results/` devolve zero CSVs. O agrupamento em braços é por
`(Modelo_LLM, Tipo_Prompt)` lidos da linha; **o manifesto não é lido em ponto
algum**. Logo não existe leitura cruzada de séries a proteger: uma rodada de
filtro e uma de triagem são invocações separadas e nunca se misturam por
acidente. A única mistura possível é alguém concatenar CSVs à mão — e é
exatamente para isso que serve a coluna de procedência. **Nenhuma tarefa nova
em `5.`**; o campo de procedência basta.

### D8 — A rodada é local, completa, e dimensionada por vazão medida

**Decisão:** a rodada de validação desta change executa os dois tipos de prompt
contra o **provedor local apenas**, sobre a população inteira do modo triagem. A
vazão é medida num subconjunto e extrapolada **antes** de comprometer a execução
longa.

**Por quê:** com cota fora da equação, não há razão para amostrar. Amostrar
introduziria uma decisão de seleção a defender — quais 100 casos, por quê — e o
limiar de 30 de `suficiencia-classe-positiva` é piso para poder estatístico, não
teto para ambição. Rodar tudo evita a pergunta.

**Por que medir a vazão antes:** o único risco real passa a ser descobrir, seis
horas depois, que a execução não termina hoje. Medir 50 casos e multiplicar custa
minutos e transforma uma execução de duração desconhecida em uma decisão
informada — inclusive a de rodar em segundo plano e recolher depois.

**Alternativa considerada:** rodar direto e acompanhar. Recusada porque o
checkpoint por chave composta já permite retomar, mas não permite *prever* — e
saber de antemão é o que decide se a rodada cabe antes de novembro.

## Inspeção do montador de prompt (tarefa 4.3)

Caminhos por onde a procedência poderia chegar ao modelo, e o que cada um
entrega:

| Caminho | Depende da procedência? |
|---|---|
| `montar_prompt(baseline)` — só `{contexto}` | Não |
| `montar_prompt(especialista)` — `cwe_header`, `definicao`, `heuristica_go`, os dois exemplos e `{contexto}` | Não: todos saem da ficha do catálogo, que é por CWE |
| `description` do dataset | Não entra em prompt nenhum (decisão anterior, documentada em `src/prompts.py`) |
| `regras_nao_casadas` / contagem de alertas concorrentes | Vão ao CSV e nunca a `avaliar()` |
| `Ficha_CWE`, `Versao_Prompt`, `Hash_Catalogo` | Colunas de CSV, fora do prompt |
| `contexto` no modo triagem | Só `basename`, faixa de linhas e código (D7) |

`src/fases3_4_llm.avaliar()` recebe exatamente
`(contexto, cwe_id, cwe_name, description, provedor, tipo_prompt, ficha)`. Não há
parâmetro por onde a procedência trafegue, e o `Candidato` não é passado adiante.

**Conclusão:** a procedência não vaza. Coberto pelos testes `4.2` em
`tests/test_braco_triagem.py`, que comparam as strings finais nos dois tipos de
prompt.

### Achado colateral que NÃO é vazamento, mas é ameaça à validade

Os dois templates abrem com:

> "Abaixo está um alerta emitido por uma ferramenta de análise estática sobre um
> trecho de código Go."

No modo triagem isso é **uniformemente** dito para as duas procedências — logo
não distingue uma da outra, e o requisito de indistinguibilidade continua
satisfeito. Mas para o candidato injetado a frase é **falsa**: nenhuma ferramenta
emitiu alerta ali. E, com D7, o contexto que vem abaixo dela não traz alerta
nenhum nem no caso de procedência `alerta`.

O efeito plausível é de enquadramento: "uma ferramenta apontou isto" empurra o
modelo para VP. Como empurra os dois grupos igualmente, o **grupo de controle não
detecta esse viés** — ele detecta diferença ENTRE procedências, e aqui não há.

**Não foi alterado nesta change, de propósito.** Trocar o texto do template muda
`Versao_Prompt` e o eixo experimental do prompt, que é decisão do autor e não
consequência da montagem do candidato. Fica registrado como ameaça à validade no
mapa do LaTeX, e como questão em aberto abaixo.

## Open Questions

- **O enquadramento "abaixo está um alerta" deve ser mantido no modo triagem?**
  Ver a inspeção 4.3 acima. Manter preserva `Versao_Prompt` e a comparabilidade
  com as Rodadas 1-3; trocar tornaria a pergunta fiel ao que o modelo de fato
  recebe. Qualquer das duas precisa ser declarada na monografia.

  **Decisão de 2026-09-15: adiada para depois do piloto (tarefa 5c.1).** O
  template fica como está por ora. A medição de vazão (5.3) trouxe um sinal que
  pesa nessa decisão: nos 50 candidatos injetados da amostra, o modelo local
  respondeu `FP` em 50/50, nos dois tipos de prompt — recall zero. Se isso se
  confirmar no piloto com o grupo de controle junto, vale perguntar quanto do
  resultado é o enquadramento e quanto é o modelo.

- A comparação entre procedências tem poder estatístico com 19 casos no grupo de
  controle? Provavelmente não. Isso não invalida o controle — um controle fraco
  que acusa diferença grande ainda é informativo —, mas precisa ser declarado.
- Qual a vazão real do provedor local nesta máquina? Determina se a rodada é de
  uma tarde ou de uma noite. **Tarefa 5.3 mede; nada depois dela assume um
  número.**
- O modelo local, em Q4_K_M, tem qualidade suficiente para que o resultado da Q2
  seja reportável? A ameaça de quantização agressiva está mapeada e não é
  resolvida por esta change; se os números saírem fracos, é preciso distinguir
  "o LLM não separa" de "este modelo comprimido não separa".
