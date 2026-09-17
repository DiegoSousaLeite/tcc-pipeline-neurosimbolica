# Rodada 4 — o braço de triagem, e o que o grupo de controle revelou

> **Rodada fechada.** Piloto 00:43–02:52, população inteira 03:25–05:33, 3.171
> chamadas de LLM, tudo sem supervisão. Todos os números abaixo são finais.

## 1. Identificação da rodada

| campo | valor |
|---|---|
| `run_id` | `rodada-4-triagem` |
| modo de montagem | **`triagem`** (primeira rodada do braço novo) |
| modelo | `ollama:qwen2.5-coder:7b`, digest `dae161e27b0e`, Q4_K_M, 100 % GPU |
| parâmetros de inferência | `num_ctx` 8192, `num_predict` 512, **semente 42, temperatura 0,0** |
| braços | 2 — `baseline` e `especialista`, ambos locais. **Nenhum braço comercial.** |
| templates | `baseline:597fcfa9`, `especialista:d1145f8b` (idênticos aos da Rodada 3) |
| ruleset / catálogo | `p/default` / `e5db7d400842` (idênticos aos da Rodada 3) |
| população | 2.328 casos; 797 de gabarito vulnerável |
| execução | disparada por `scripts/gatilho_rodada_triagem.py`, sem supervisão |
| janela de execução | 2026-09-16 00:43 → 05:33 (piloto + população inteira) |
| chamadas de LLM | 3.171 |

A rodada de comparação é a **Rodada 3** (`results/20260908T094808Z-9a00cb2`),
que é do braço `filtro` e usou **o mesmo modelo, os mesmos templates, o mesmo
catálogo e a mesma semente**. É essa coincidência de configuração que torna o
controle pareado da §3 um experimento e não uma observação.

### Como a rodada foi executada

O gatilho esperou a máquina ficar ociosa (a esteira da change
`semgrep-pro-entre-arquivos` estava rodando), descarregou o modelo do Ollama,
populou a Fase 1 em cache com o modelo fora da memória, aqueceu o modelo e só
então começou a chamar o LLM. Semgrep e modelo local **nunca dividiram RAM**.
A Fase 1 terminou em 8 s: o cache simbólico cobria a população inteira, e o
cache de fontes também (0 de 2.328 arquivos faltando).

Vazão medida: **8,23 s por chamada** na aferição de 50 casos com o modelo já
carregado; **~4,8 s** no regime sustentado da rodada.

---

## 2. O funil, agora com o braço de triagem

| etapa | modo `filtro` (Rodada 3) | modo `triagem` (Rodada 4) |
|---|---|---|
| gabarito vulnerável na população | 797 | 797 |
| com alerta emparelhado na Fase 1 | 19 (2,61 %) | 19 (2,61 %) |
| **com veredito de LLM** | **19** | **778–780** por braço |
| procedência `alerta` | 19 | 19 |
| procedência `gabarito` (injetados) | — | 759–761 |

`Status_Semgrep` não mudou em caso algum: os injetados saem do CSV como
`NAO_DETECTADO`, com o motivo preservado, e a matriz de cobertura simbólica da
Rodada 3 continua valendo byte a byte. A diferença entre 778 e 780 entre os
braços vem das 33 linhas de `API_ERROR` (ver §7.4), não do desenho.

**O critério de suficiência (30 vulneráveis com veredito válido) foi atingido com
folga** — 778 contra um mínimo de 30. É a primeira rodada em que Recall, F1, MCC
e TFN são calculáveis para a classe positiva.

---

## 3. O resultado principal: o controle pareado, e o que ele revelou

Este não era o resultado que a rodada foi desenhada para produzir. O grupo de
controle existia para responder *"a injeção criou artefato?"*. Respondeu que não
— e, de quebra, respondeu outra coisa.

Os 19 positivos que o Semgrep detectou aparecem nas **duas** rodadas: na de
filtro porque havia alerta, na de triagem porque o emparelhamento tem precedência
sobre a injeção (D3). Mesmos `ID_Caso`, mesmo modelo, mesmo template, semente
fixa, temperatura 0. **A única variável é o contexto**, que o modo triagem
normaliza ao código (D7).

| braço | n | VP com contexto do alerta | VP com contexto só de código | delta | VP perdidos | VP ganhos |
|---|---|---|---|---|---|---|
| `baseline` | 19 | **8** | **0** | **−8** | 8 | 0 |
| `especialista` | 19 | 3 | 3 | 0 | 0 | 0 |

### A leitura

O prompt `baseline` não recebe CWE, nem definição, nem heurística — por desenho,
é a condição de controle. Mas no modo filtro o contexto hidratado abria com:

```
Alerta Semgrep: go.lang.security.audit.<nome-da-regra>
Mensagem: <texto do Semgrep, que nomeia a fraqueza>
```

**O baseline estava lendo a resposta no enunciado.** Removidos esses campos — que
é o que a normalização faz, para que a procedência não vaze —, ele vai a zero. O
especialista não se move, porque o sinal dele vem do catálogo de CWE, que
continua lá.

Isto tem duas consequências, e nenhuma é pequena:

1. **A comparação baseline × especialista das Rodadas 1-3 não mede só engenharia
   de prompt.** Parte do que o baseline acertava vinha do identificador da regra e
   da mensagem do motor. A diferença medida entre os braços é um limite inferior
   subestimado, e precisa ser declarada — não corrigida em silêncio.
2. **O braço `baseline × triagem` não é comparável com `baseline × filtro`.** Não
   é "o mesmo componente sobre mais casos": é um tratamento mais pobre. O braço
   `especialista` não sofre disso e é o único cuja série atravessa as duas
   rodadas com o mesmo significado.

### O grupo de controle, no que ele foi pedido para responder

| braço | procedência | n | VP | acerto |
|---|---|---|---|---|
| `baseline` | `alerta` | 19 | 0 | 0,0000 |
| `baseline` | `gabarito` | 761 | 3 | 0,0039 |
| `especialista` | `alerta` | 19 | 3 | 0,1579 |
| `especialista` | `gabarito` | 759 | 7 | 0,0092 |

O portão da tarefa 5.5 **passou**: a maior diferença na direção que importa
(injetado indo melhor que detectado, que seria artefato de montagem inflando o
resultado) é de **+0,0039**, contra um limiar de 0,25.

**Ressalva obrigatória, emitida pelas próprias métricas:** o grupo de controle
tem 19 casos, abaixo do mínimo de 30. Uma diferença grande ainda informaria;
a ausência de diferença **não demonstra** ausência de artefato. O controle é
indicativo, não conclusivo.

No especialista o sentido é o oposto do artefato: o modelo acerta *menos* nos
injetados (0,92 % contra 15,79 %). Isso é consistente com a explicação simples de
que o Semgrep detecta justamente as vulnerabilidades mais fáceis, e as que ele
perde são mais difíceis para qualquer um — mas é confundido com o n=19 e com a
diferença de contexto da §3. Não dá para separar os três com esta rodada.

---

## 4. O teto do desenho de filtro puro

O roteiro da apresentação anuncia esse teto sem quantificar. Agora ele tem número
— e o número é pequeno.

**Recall do sistema**: VP sobre os 797 vulneráveis da população, contando como
perdido todo caso que não recebeu veredito favorável, inclusive os que nunca
chegaram ao LLM. É o único recall comparável entre os modos, porque o denominador
é idêntico nos dois.

| braço | VP filtro | recall filtro | VP triagem | recall triagem | **teto** |
|---|---|---|---|---|---|
| `baseline` | 8 | 1,00 % | 3 | 0,38 % | **−0,63 p.p.** |
| `especialista` | 3 | 0,38 % | 10 | 1,25 % | **+0,88 p.p.** |

No especialista o braço de triagem **triplica** o recall do sistema — e ainda
assim recobra 10 de 797. No baseline o teto é **negativo**, pelo motivo da §3: a
perda de contexto supera o ganho de casos.

**Nenhum dos dois sustenta a leitura de que "bastaria deixar o LLM ver tudo".**
E o teto mistura dois efeitos que esta rodada não separa: quais casos chegam ao
LLM, e quanto contexto cada um traz.

### Recall do componente — pergunta diferente, não comparar

| braço | n filtro | recall filtro | n triagem | recall triagem |
|---|---|---|---|---|
| `baseline` | 19 | 42,11 % | 780 | 0,38 % |
| `especialista` | 19 | 15,79 % | 778 | 1,29 % |

Os denominadores são populações diferentes — no filtro, os positivos que o
Semgrep achou; na triagem, os da população. Os 42,11 % do baseline no filtro são,
em grande parte, o efeito da §3.

---

## 5. A resposta à Q2, e por que ela é ruim

A metade *"sem introduzir falsos negativos"* estava em branco por falta de n.
Agora tem n = 778, e tem resposta.

Matriz de acerto do LLM, rodada inteira:

| braço | n | VP | VN | FP | FN | Precisão | Recall | F1 | **MCC** | TFN |
|---|---|---|---|---|---|---|---|---|---|---|
| `baseline` | 1585 | 3 | 803 | 2 | 777 | 0,6000 | 0,0038 | 0,0076 | **0,0121** | 0,9962 |
| `especialista` | 1586 | 10 | 797 | 11 | 768 | 0,4762 | 0,0129 | 0,0250 | **−0,0033** | 0,9871 |

**O MCC é o número que resume a rodada: 0,012 e −0,003.** Zero é o valor de um
classificador que não discrimina nada. Os dois braços dizem "não é
vulnerabilidade" para quase tudo — o baseline emite 5 vereditos positivos em
1.585 casos, o especialista 21 em 1.586. O especialista é melhor no que importa
(10 VP contra 3, F1 três vezes maior), e ainda assim está no chão.

⚠️ **A coluna TRA da tabela de braços do `src/metricas.py` NÃO deve ser citada
para esta rodada**, e as próprias métricas agora avisam isso: ela divide pelos
casos avaliados, que aqui incluem injetados — e injetado nunca foi alerta. A TRA
interpretável está na §6.

**O braço neural introduz falsos negativos em massa quando lhe é dado julgar o
que o motor simbólico não viu.** Isso não é um fracasso da medição: é a medição.
Ela diz que a promessa de "o LLM cobre o ponto cego do SAST" não se sustenta com
este modelo, este prompt e este contexto.

**O braço neural introduz falsos negativos em massa quando lhe é dado julgar o
que o motor simbólico não viu.** Isso não é um fracasso da medição: é a medição.
Ela diz que a promessa de "o LLM cobre o ponto cego do SAST" não se sustenta com
este modelo, este prompt e este contexto.

---

## 6. TRA sobre a pilha de alertas, e o McNemar

### 6.1 TRA — só sobre a procedência `alerta`

A pilha de alertas real tem 824–827 casos por braço. Os injetados ficam de fora:
nunca foram alerta, e incluí-los mudaria o número por composição, não por
comportamento.

| braço | n filtro | TRA filtro (Rodada 3) | n triagem | TRA triagem (Rodada 4) | diferença |
|---|---|---|---|---|---|
| `baseline` | 825 | 0,8497 | 824 | **0,9976** | +0,1479 |
| `especialista` | 827 | 0,9819 | 827 | **0,9831** | +0,0012 |

O especialista é **estável**: 0,9819 → 0,9831 sobre praticamente a mesma pilha.
A remoção dos campos do alerta não mexeu na capacidade dele de descartar ruído,
porque o sinal dele vem do catálogo.

O baseline vai a **0,9976** — descarta 822 dos 824 alertas. Somado aos 3 VP em
1.585 casos da §5, isso não é "filtrar bem": é dizer "não é vulnerabilidade" para
quase tudo. A TRA alta dele, aqui, é sintoma de degeneração e não de qualidade, e
**não deve ser reportada como ganho**. É o caso didático de por que a TRA precisa
ser lida junto da TFN, como a metodologia já exige.

### 6.2 McNemar — os dois prompts deixam de se distinguir

| campo | valor |
|---|---|
| n pareado | 1.583 |
| ambos acertam | 792 |
| só `baseline` acerta | 14 |
| só `especialista` acerta | 12 |
| ambos erram | 765 |
| discordâncias b+c | 26 → qui-quadrado (Yates) |
| estatística | 0,0385 |
| **p-valor** | **0,8445** |

Na Rodada 3 essa mesma comparação era o resultado principal do trabalho:
discordâncias 104 × 5, p < 0,0001. Aqui, 14 × 12 e p = 0,8445.

**Cuidado com a leitura.** Isso NÃO é "os prompts são equivalentes". É que, sem
os campos do alerta, os dois convergem para o mesmo comportamento quase
constante — e dois classificadores degenerados concordam trivialmente. O p-valor
alto aqui mede a perda de poder discriminativo dos dois, não uma equivalência
entre eles. O MCC de 0,012 e −0,003 da §5 é a leitura correta do mesmo fato.

E a comparação carrega a confusão da §3: os dois braços não receberam contexto
equivalente ao que receberam nas rodadas anteriores.

---

## 7. Ressalvas

### 7.1 O contexto do braço de triagem é mais pobre, de propósito

D7 remove `check_id`, mensagem e linha apontada **das duas procedências**. Era a
única forma de tornar os candidatos indistinguíveis sem fabricar dados: um
`N/A` ao lado de um `go.lang.security.audit.*` real *é* a pista, e a linha do
injetado coincide sempre com o início da função recortada. O preço está medido na
§3 e é alto para o baseline.

### 7.2 O enquadramento do prompt continua o de sempre

Os dois templates abrem com "abaixo está um alerta emitido por uma ferramenta de
análise estática". No braço de triagem a frase é falsa para os injetados, e por
ser uniforme às duas procedências **o grupo de controle não a detecta**. Não foi
alterada: trocá-la mudaria `Versao_Prompt` e quebraria a comparabilidade que
ainda resta com as Rodadas 1-3, sem resolver o que a normalização já resolveu.
Fica como limitação declarada.

### 7.3 Um modelo local de 7 B não é o teto do que um LLM consegue

Toda conclusão acima é sobre `qwen2.5-coder:7b` com `num_ctx` 8192. A rodada foi
local por decisão de custo — 3.210 chamadas comerciais não cabiam na cota. **Não
se pode concluir daqui que modelos de fronteira falhariam igual**, e o texto
precisa dizer isso onde citar a TFN de 98,71 %.

### 7.4 Trinta e três vereditos perdidos, todos por recusa explícita

33 linhas saíram como `API_ERROR` (15 no `baseline`, 18 no `especialista`):

- **26** (13 casos × 2 braços): prompt maior que a janela — de ~7.883 a ~27.420
  tokens estimados contra o teto de 7.680 (`num_ctx` 8192 menos `num_predict`
  512). São funções Go longas, e no braço de triagem o recorte do injetado é a
  função inteira declarada pela CVE.
- **7**: geração interrompida antes de concluir o JSON.

Nenhum virou veredito inventado: o provedor **recusa** em vez de truncar em
silêncio, que é o comportamento documentado em `docs/PIPELINE.md`. O efeito é
uma perda de 1 % da amostra, sem viés de conteúdo conhecido — mas é uma perda
enviesada por **tamanho de função**, e isso precisa ser declarado: as funções
mais longas estão sub-representadas nos vereditos.

### 7.5 Os números desta rodada não descrevem o sistema em operação

Num uso real os positivos não seriam injetados: viriam do Semgrep, que perde
97,4 % deles. O que o braço de triagem mede é a capacidade do componente neural
isolado.

---

## 8. Referência rápida

| artefato | onde |
|---|---|
| CSVs da Rodada 4 | `results/rodada-4-triagem/` |
| Manifesto | `results/rodada-4-triagem/manifesto.json` |
| Log da execução automática | `results/gatilho-triagem.log` |
| Aferição de vazão (50 casos) | `results/vazao-5.3/` |
| Rodada 3 (braço `filtro`) | `results/20260908T094808Z-9a00cb2/` |
| Comparação entre os braços | `python scripts/comparar_filtro_triagem.py --filtro results/20260908T094808Z-9a00cb2 --triagem results/rodada-4-triagem` |
| O que isso obriga no LaTeX | `docs/MAPA-TCC-O-QUE-REESCREVER.md` §4b |
