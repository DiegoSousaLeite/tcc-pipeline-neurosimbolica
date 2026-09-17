# Escolha do modelo comercial — levantamento, custo e decisão

> **O que este documento é.** Um retrato datado, feito em **2026-09-17**, de
> quais modelos comerciais existem, quanto custaria rodar esta pipeline neles, e
> qual deles é recomendado. É insumo de decisão, **não** registro de execução:
> nenhuma chamada de API foi feita, nenhum provedor foi implementado e a tabela
> de preços do projeto (`src/provedores/precos.py`) não foi alterada.
>
> **Validade.** Preço e catálogo de modelo mudam em semanas. Toda linha traz a
> data em que foi conferida. Quem for executar **reconfere antes de gastar**.

---

## 1. Base de cálculo

### 1.1 De onde vêm os tokens

Os números de custo deste documento saem da **Rodada 4** (`run_id`
`rodada-4-triagem`, commit `033b3ab`, manifesto em
`results/rodada-4-triagem/manifesto.json`), a rodada de dois braços
`baseline` × `especialista` sobre `ollama:qwen2.5-coder:7b` em modo `triagem`.

Recontagem feita diretamente sobre os dois CSVs da rodada:

| | chamadas | tokens de entrada | tokens de saída |
|---|---:|---:|---:|
| `…__baseline.csv` | 1.585 | 1.196.812 | 161.840 |
| `…__especialista.csv` | 1.587 | 2.002.273 | 154.141 |
| **total faturável** | **3.172** | **3.199.085** | **315.981** |
| média por chamada | — | 1.008,5 | 99,6 |

"Chamada" aqui é **linha com `Tokens_Entrada` ou `Tokens_Saida` maior que zero**.
As 4.672 linhas dos CSVs incluem 1.500 casos que nunca chegaram ao LLM
(`Veredito_LLM` = `N/A`, sem tokens) e que, portanto, não custam nada.

#### A diferença de uma chamada, resolvida

`proposal.md`, `design.md` e `docs/ANALISE-RODADA-4.md` registram **3.171
chamadas, 3.198.141 de entrada e 315.469 de saída**. A recontagem dá 3.172 /
3.199.085 / 315.981. A diferença fecha **exatamente** em uma única linha:

```
ID_Caso: TPA:prest:CWE-89:ReturningByRequest:159caf80:vuln
Tokens_Entrada: 944   Tokens_Saida: 512   Veredito_LLM: N/A
```

3.172 − 1 = 3.171; 3.199.085 − 944 = 3.198.141; 315.981 − 512 = 315.469.

É uma geração **interrompida no teto** (`num_predict` = 512, batido na mosca),
que não produziu veredito válido e por isso ficou fora da contagem anterior. As
duas contagens estão certas para o que cada uma mede:

- **3.171** é o número de vereditos — o certo para métrica.
- **3.172** é o número de chamadas — **o certo para custo**, porque uma geração
  truncada é cobrada integralmente pelo fornecedor. Este documento usa 3.172.

A diferença é de 0,03 % e não move decisão alguma. Está registrada porque a
alternativa seria dois números conflitantes no projeto sem explicação.

### 1.2 As três escalas

Derivadas da população do manifesto (2.328 casos; trilhas: `TP_alcancavel`
1.380, `FP` 791, `TP_prata` 68, `TP_dataset` 57, `TP_ouro` 32) e da contagem de
`1.1`, não de estimativa:

| escala | o que é | chamadas comerciais |
|---|---|---:|
| **rodada de dois braços** | 1 modelo × 2 prompts, população inteira | **3.172** |
| **matriz 2x2 completa** | 2 modelos comerciais × 2 prompts (o desenho de referência de `matriz-experimental`) | **6.344** |
| **amostra estratificada ~300** | ~300 casos **que geram chamada** × 2 prompts, proporcional às trilhas | **600** |

A amostra usa as médias de `1.1` (1.008,5 de entrada e 99,6 de saída por
chamada), porque quais 300 casos entram ainda não está decidido; as duas
primeiras usam os totais medidos.

> **Precisão sobre o que é "300 casos".** A escala acima conta **300 casos que
> efetivamente geram chamada**, cada um submetido aos **dois braços** — logo 600
> chamadas. Não é 300 por braço, e não é 300 sorteados da população.
>
> A distinção importa porque **só 68,1 % dos casos chegam ao LLM**: na Rodada 4,
> 1.586 dos 2.328 casos em média por braço. Sortear 300 da população renderia
> ~204 casos com candidato, ou **409 chamadas**, e um custo ~32 % menor. As duas
> leituras estão tabeladas na §9.5.

### 1.3 O contrato que um provedor precisa cumprir

Lido em `src/provedores/base.py`, `gemini.py`, `openai.py` e `precos.py`.

A pipeline conhece uma interface só (`ProvedorLLM`, `base.py`):

```python
modelo: str
def avaliar(self, prompt: str) -> RespostaLLM
```

`RespostaLLM` normaliza `veredito`, `justificativa`, `modelo`,
`tokens_entrada`, `tokens_saida`, `custo_usd` e `tentativas`. O veredito só é
`VP` ou `FP`; **qualquer outra coisa é `ERROR`, nunca `FP`** — contar falha de
esteira como "o modelo achou seguro" inventaria um verdadeiro negativo.

Tudo que é comum já está em `ProvedorHTTP` (`base.py`) e **não se reescreve**:

| responsabilidade | onde | comportamento |
|---|---|---|
| throttle | `_aguardar_throttle` | intervalo mínimo entre chamadas, por instância de provedor |
| retry | laço de `avaliar` | 4 tentativas; backoff exponencial 5 s → teto 120 s, com jitter |
| códigos transitórios | `CODIGOS_TRANSITORIOS` | 429, 500, 502, 503, 504 repetem; 4xx de configuração não |
| `Retry-After` | `ler_retry_after` | vence o backoff local, sujeito ao teto |
| validação de schema | `validar_resposta` | JSON (tolera cerca ```` ```json ````), veredito no domínio, justificativa não vazia |
| custo | `_custo` → `precos.custo_usd` | derivado dos tokens; modelo fora da tabela custa 0 e é sinalizado |

**Um provedor novo implementa quatro métodos**, e nada mais:

```python
def _url(self) -> str
def _headers(self) -> dict
def _payload(self, prompt: str) -> dict
def _extrair(self, dados: dict) -> tuple[str, int, int]   # (texto, tok_in, tok_out)
```

Mais o padrão de `intervalo_minimo_s` e, se for o caso, `timeout_padrao_s`.
`gemini.py` tem **57 linhas** e `openai.py` **52**, comentários incluídos. Esse
é o tamanho real de "provedor novo" neste projeto.

**Duas lacunas do contrato, que valem para a decisão:**

1. **Não há truncamento de contexto.** Prompt maior que a janela vira erro do
   fornecedor, tratado como `ERROR`. Foi assim que a Rodada 4 perdeu 26
   chamadas. O contrato não tem onde encaixar uma política de truncamento — e,
   como a §2.3 mostra, com janela comercial o problema simplesmente não ocorre.
2. **Geração interrompida não é distinguida de resposta completa.** Se o modelo
   para no teto de saída e ainda assim emite JSON válido, o veredito é aceito.
   É a origem da chamada discrepante de `1.1`.

---

## 2. Candidatos

### 2.1 e 2.2 Preço, verificado na fonte primária em 2026-09-17

Fontes consultadas hoje, **2026-09-17**:

| fornecedor | endereço consultado |
|---|---|
| Google | `https://ai.google.dev/gemini-api/docs/pricing` |
| OpenAI | `https://developers.openai.com/api/docs/pricing` (301 de `platform.openai.com/docs/pricing`) |
| Anthropic | `https://platform.claude.com/docs/en/docs/about-claude/pricing` (301 de `docs.anthropic.com`) |

> **Nota de procedência.** Os dois endereços gravados em
> `src/provedores/precos.py` (`FONTES`) ainda funcionam, mas o da OpenAI passou
> a redirecionar para outro domínio. Se a tabela do projeto for atualizada um
> dia, o endereço novo é o que deve entrar.

Preços em **USD por 1 milhão de tokens**, tier padrão, sem desconto de batch ou
de cache:

| faixa | modelo | entrada | saída | verificado |
|---|---|---:|---:|---|
| barata | `gpt-5-nano` | 0,05 | 0,40 | ✅ 2026-09-17 |
| barata | `gemini-2.5-flash-lite` | 0,10 | 0,40 | ✅ 2026-09-17 |
| barata | `gpt-4o-mini` | 0,15 | 0,60 | ✅ 2026-09-17 |
| barata | `gemini-3.1-flash-lite` | 0,25 | 1,50 | ✅ 2026-09-17 |
| média | `gpt-5-mini` | 0,25 | 2,00 | ✅ 2026-09-17 |
| média | `gemini-2.5-flash` | 0,30 | 2,50 | ✅ 2026-09-17 |
| média | `gpt-5.4-mini` | 0,75 | 4,50 | ✅ 2026-09-17 |
| média | `claude-haiku-4-5` | 1,00 | 5,00 | ✅ 2026-09-17 |
| média | `gpt-4.1` | 2,00 | 8,00 | ✅ 2026-09-17 |
| média | `claude-sonnet-5` | 2,00 | 10,00 | ✅ 2026-09-17 |
| média | `gpt-5.6-terra` | 2,00 | 12,00 | ✅ 2026-09-17 |
| média | `gemini-3.1-pro-preview` | 2,00 | 12,00 | ✅ 2026-09-17 |
| topo | `claude-opus-5` | 5,00 | 25,00 | ✅ 2026-09-17 |
| topo | `gpt-5.5` | 5,00 | 30,00 | ✅ 2026-09-17 |
| topo | `claude-fable-5-1` | 10,00 | 50,00 | ✅ 2026-09-17 |
| topo | `gpt-6-astra` | 10,00 | 50,00 | ✅ 2026-09-17 |

**Os dois preços que o projeto já carrega seguem corretos**:
`gemini-2.5-flash-lite` (0,10 / 0,40) e `gpt-4o-mini` (0,15 / 0,60) batem
exatamente com a tabela de `2026-07-29`. Sete semanas depois, nenhum dos dois
mudou — o que não valida a prática de não reconferir, só significa que desta vez
não custou nada.

### 2.3 Janela de contexto

O teto efetivo local da Rodada 4 era **7.680 tokens** (`num_ctx` 8192 menos
`num_predict` 512). O maior prompt que passou mediu **7.337** tokens de entrada;
**26 chamadas** (13 casos × 2 braços) estouraram a janela, com prompts estimados
entre ~7.883 e **~27.420** tokens (`docs/ANALISE-RODADA-4.md` §11). Essa perda é
enviesada por **tamanho de função** e está declarada como ameaça à validade.

| modelo | janela de entrada | saída máx. | comporta os ~27.420? | verificado |
|---|---:|---:|---|---|
| `claude-sonnet-5` | 1M | 128k | sim, com 36x de folga | ✅ 2026-09-17 |
| `claude-opus-5` | 1M | 128k | sim | ✅ 2026-09-17 |
| `claude-fable-5-1` | 1M | 128k | sim | ✅ 2026-09-17 |
| `claude-haiku-4-5` | 200k | 64k | sim, com 7x de folga | ✅ 2026-09-17 |
| `gpt-6-astra`, `gpt-5.6-*` | 1,05M | 128k | sim | ✅ 2026-09-17 |
| `gpt-5-mini`, `gpt-5`, `gpt-4.1`, `gpt-4o-mini` | — | — | — | ❌ **não verificado** |
| `gemini-2.5-flash`, `-flash-lite`, `-pro` | — | — | — | ❌ **não verificado** |

**Nada foi preenchido de memória.** As páginas de modelos da OpenAI e do Google
consultadas hoje não publicam janela por modelo para essas linhas: a da OpenAI
lista apenas a geração corrente (GPT-6 Astra e GPT-5.6) e a do Google remete à
página individual de cada modelo. Números lembrados não entram aqui.

**O que já dá para concluir mesmo com as lacunas:** todo candidato comercial
cuja janela foi verificada tem **no mínimo 200k tokens**, contra os 7.680
efetivos do local. As 26 falhas por estouro de janela da Rodada 4 **deixam de
existir** em qualquer um deles — e com elas some a perda enviesada por tamanho
de função. Isso é ganho metodológico, independente de qual modelo se escolha.

### 2.4 Limite de requisições e nível gratuito

Esta é a seção que mais separa os fornecedores, e **não** pelo valor do limite:
pela possibilidade de saber qual é ele antes de abrir conta.

| fornecedor | limites no nível considerado | verificado |
|---|---|---|
| **Anthropic** (Start tier) | `claude-sonnet-5`, `claude-opus-5`, `claude-haiku-4-5`: **1.000 RPM, 2.000.000 ITPM, 400.000 OTPM**. Teto de gasto mensal **US$ 500**. Só tokens de entrada **não cacheados** contam para o ITPM. | ✅ 2026-09-17, `platform.claude.com/docs/en/api/rate-limits` |
| **OpenAI** | Apenas os tiers de **gasto** são públicos: Free US$ 100/mês, Tier 1 (US$ 5 pagos) US$ 100/mês, até Tier 5 US$ 200.000/mês. **RPM/TPM por modelo não são publicados** — a página remete a `platform.openai.com/settings/organization/limits`, que exige conta. | ⚠️ parcial, 2026-09-17 |
| **Google** | **Não publicados.** A página de rate limits diz que os limites "podem ser vistos no Google AI Studio" e remete a `aistudio.google.com/rate-limit`, que exige conta. Só há limites de *batch* tabelados. | ❌ **não verificado**, 2026-09-17 |

**Por que isso importa mais que preço, neste projeto.** O tier grátis do Gemini
permite **20 requisições por dia** (medido pelo próprio projeto — ver a memória
`gemini-free-tier-cota`; não é número de documentação do fornecedor). A 20
req/dia, as 3.172 chamadas de uma rodada levariam **159 dias**. O impedimento
não é econômico: a rodada custaria US$ 0,45. Foi exatamente esse muro que
travou o braço comercial deste trabalho, e ele não aparece em nenhuma tabela de
preço.

**Nível gratuito utilizável para uma rodada completa: nenhum.** O da OpenAI é um
crédito de gasto, não uma isenção de limite; o do Google é inviável pela cota; a
Anthropic oferece créditos de teste, não um tier grátis permanente.

---

## 3. Custo e parede

### 3.1 Custo nas três escalas

Calculado sobre os tokens **medidos** de `1.1` (3.199.085 de entrada, 315.981 de
saída, 3.172 chamadas), com os preços verificados de `2.2`. Valores em USD.

| faixa | modelo | US$/1M ent | US$/1M sai | rodada 2 braços | matriz 2x2 | amostra ~300 |
|---|---|---:|---:|---:|---:|---:|
| barata | `gpt-5-nano` | 0,05 | 0,40 | **0,29** | 0,57 | 0,05 |
| barata | `gemini-2.5-flash-lite` | 0,10 | 0,40 | **0,45** | 0,89 | 0,08 |
| barata | `gpt-4o-mini` | 0,15 | 0,60 | **0,67** | 1,34 | 0,13 |
| barata | `gemini-3.1-flash-lite` | 0,25 | 1,50 | **1,27** | 2,55 | 0,24 |
| média | `gpt-5-mini` | 0,25 | 2,00 | **1,43** | 2,86 | 0,27 |
| média | `gemini-2.5-flash` | 0,30 | 2,50 | **1,75** | 3,50 | 0,33 |
| média | `gpt-5.4-mini` | 0,75 | 4,50 | **3,82** | 7,64 | 0,72 |
| média | `claude-haiku-4-5` | 1,00 | 5,00 | **4,78** | 9,56 | 0,90 |
| média | `gpt-4.1` | 2,00 | 8,00 | **8,93** | 17,85 | 1,69 |
| média | `claude-sonnet-5` | 2,00 | 10,00 | **9,56** | 19,12 | 1,81 |
| média | `gpt-5.6-terra` | 2,00 | 12,00 | **10,19** | 20,38 | 1,93 |
| média | `gemini-3.1-pro-preview` | 2,00 | 12,00 | **10,19** | 20,38 | 1,93 |
| topo | `claude-opus-5` | 5,00 | 25,00 | **23,89** | 47,79 | 4,52 |
| topo | `gpt-5.5` | 5,00 | 30,00 | **25,47** | 50,95 | 4,82 |
| topo | `claude-fable-5-1` | 10,00 | 50,00 | **47,79** | 95,58 | 9,04 |
| topo | `gpt-6-astra` | 10,00 | 50,00 | **47,79** | 95,58 | 9,04 |

**Confere com o que a proposta afirmava:** `gemini-2.5-flash-lite` dá US$ 0,45
por rodada de dois braços, exatamente o número citado em `proposal.md`.

**Não confere com o resto.** `design.md` estimava "faixa média da ordem de
US$ 14" e "topo em ~US$ 72". O cálculo sobre os preços verificados hoje dá
**US$ 1,43 a US$ 10,19** na faixa média e **US$ 23,89 a US$ 47,79** no topo. As
duas estimativas eram altas — cerca de 40 % acima na média e 35 % acima no topo.
Como as estimativas anteriores deste projeto erraram para **menos** (817 tokens
estimados contra 1.009 medidos), vale notar que desta vez o erro foi para mais e
na direção segura.

#### Ressalva de tokenização (a que mais pode mover estes números)

Os tokens de `1.1` foram contados pelo **tokenizador do `qwen2.5-coder:7b`**.
Nenhum fornecedor comercial usa esse tokenizador, então toda linha acima é uma
**aproximação de primeira ordem**. Há um caso em que o desvio é conhecido e
documentado: a Anthropic declara que os modelos **4.7 em diante** usam um
tokenizador novo que produz **~30 % mais tokens para o mesmo texto**.

| modelo | rodada 2 braços, tokens medidos | com +30 % declarado |
|---|---:|---:|
| `claude-sonnet-5` | 9,56 | **12,43** |
| `claude-opus-5` | 23,89 | **31,06** |
| `claude-fable-5-1` | 47,79 | **62,13** |

`claude-haiku-4-5` usa o tokenizador anterior e **não** leva o ajuste. Para
OpenAI e Google não há fator publicado, e nenhum foi inventado aqui.

Ordem de grandeza: mesmo o pior caso da faixa média fica em **US$ 12,43** por
rodada. A decisão continua não sendo orçamentária.

### 3.2 Tempo de parede

**Referência local, medida:** a Rodada 4 levou **7.620,9 s = 2 h 07 min** para
3.172 chamadas (`duracao_s` do manifesto), ou **2,40 s por chamada**, incluindo
a Fase 1 simbólica.

> ⚠️ **Correção de um número dos artefatos.** `design.md` e a spec afirmam que
> "a rodada local de 3.171 chamadas levou 4h50". **Nenhum manifesto em disco
> registra isso.** As durações reais são: Rodada 4 = 2 h 07 min, Rodada 5
> (`rodada-5-direto`) = 4 h 08 min, Rodada 6 (`rodada-6-gemma`) = 7 h 48 min. O
> valor de 4h50 não foi reproduzido a partir de nenhuma rodada e **não é usado
> aqui**; a referência de comparação passa a ser os 2 h 07 min medidos da própria
> Rodada 4.

**O gargalo é a serialidade, não o limite de taxa.** `ProvedorHTTP.avaliar` é
síncrono e o laço da rodada é sequencial — uma chamada por vez, por instância de
provedor (e `matriz-experimental` exige que os dois braços do mesmo modelo
compartilhem a instância, justamente para o throttle valer entre eles). Logo:

```
parede ≈ n_chamadas × (latência_por_chamada + intervalo_mínimo)
```

| cenário | intervalo | parede estimada para 3.172 chamadas |
|---|---|---|
| Anthropic Start, `intervalo_minimo_s = 0` | 0 s | **1 h 46 min a 3 h 32 min** (latência de 2 a 4 s/chamada) |
| OpenAI, padrão do projeto (`OPENAI_MIN_INTERVALO = 0`) | 0 s | mesma faixa |
| Gemini, **padrão do projeto** (`GEMINI_MIN_INTERVALO = 7`) | 7 s | **≥ 6 h 10 min**, piso imposto só pelo throttle |
| Gemini, tier grátis (20 req/dia) | — | **159 dias** — inviável |

Contra os limites da Anthropic no Start tier, a rodada inteira consome ~1,6
minuto do orçamento de ITPM (3,2M tokens contra 2M por minuto) e ~3,2 minutos do
de RPM (3.172 contra 1.000 por minuto). **O limite de taxa nunca é o que
segura**; a latência sequencial é.

**Armadilha de configuração, registrada:** o padrão de 7 s do `gemini.py` foi
escolhido para o tier grátis. Em tier pago ele **triplica a parede** sem
necessidade. Quem executar precisa zerá-lo explicitamente.

### 3.3 Custo de integração

Classificado contra o contrato de `1.3`.

| modelo | classe | justificativa |
|---|---|---|
| `gemini-2.5-*`, `gemini-3.*` | **configuração** | `ProvedorGemini` já existe; troca-se o campo `modelo`. |
| `gpt-4o-mini`, `gpt-4.1`, `gpt-5*`, `gpt-6-astra` | **configuração** | `ProvedorOpenAI` fala `/v1/chat/completions` e o `BASE_URL` já é parametrizado por `OPENAI_BASE_URL`. Zero linha de código. |
| `claude-*` (Anthropic) | **provedor novo** | Endpoint, formato e contagem diferentes: `POST /v1/messages`; headers `x-api-key` + `anthropic-version`; `max_tokens` **obrigatório** no payload; texto em `content[0].text`; tokens em `usage.input_tokens` / `usage.output_tokens`. São os mesmos quatro métodos de `gemini.py` (57 linhas) e `openai.py` (52). |
| qualquer um via Bedrock/Vertex | **incompatível** (hoje) | Exigiria autenticação assinada da nuvem (SigV4 / ADC), que `ProvedorHTTP` não tem. Fora de escopo — a API de primeira parte resolve. |

**Nenhum candidato é incompatível pela via direta.** A diferença real entre
"configuração" e "provedor novo" aqui é de **~55 linhas mais testes**, contra
uma classe base que o projeto já exercitou duas vezes. É custo, mas é pequeno e
conhecido — e o documento não vai fingir que é maior do que é.

---

## 4. A recomendação

### 4.1 O critério, declarado antes de aplicá-lo

Em ordem de peso. Os três primeiros eliminam; os dois últimos desempatam.

1. **Poder de falsificação** (design D6). O resultado atual do trabalho é
   **negativo**. Um modelo que só possa confirmá-lo não compra escopo nenhum.
   Isso exige um modelo de capacidade claramente acima de um 7 B especializado
   em código — o que **elimina a faixa barata inteira**, inclusive os dois
   modelos que hoje são o padrão do projeto.
2. **Janela ≥ 32k tokens, verificada.** Para que as 26 perdas por estouro da
   Rodada 4 desapareçam e a ameaça à validade por tamanho de função caia junto.
3. **Verificabilidade** (design D1). Preço, janela e **limite de taxa**
   conferíveis na fonte primária **sem abrir conta**. Não é preciosismo
   bibliográfico: vazão é o que já matou o braço comercial deste trabalho uma
   vez, e um limite que só se descobre depois de pagar é um risco assumido às
   cegas.
4. **Custo de integração** (design D3), pela classificação de `3.3`.
5. **Custo em dólar.** Desempate **apenas**, porque toda a faixa média cabe
   entre US$ 1,43 e US$ 12,43 por rodada. Nessa escala o preço não é informação
   de decisão.

### 4.2 Recomendado: `claude-sonnet-5`

**US$ 9,56 por rodada de dois braços** com os tokens medidos, **US$ 12,43** com
o ajuste de +30 % do tokenizador declarado — o número pelo qual se deve
planejar. Matriz 2x2 completa: US$ 19,12 a US$ 24,86.

> **Modo síncrono, e por quê.** A §8 avalia o modo batch dos três fornecedores:
> o desconto de 50 % é real e verificado, mas **não muda esta recomendação**,
> porque o batch quebra o contrato de provedor da §1.3 e custa de 3 a 5 vezes
> mais integração para economizar US$ 6. A §8.7 registra os três gatilhos
> objetivos que fariam o batch passar a valer a pena.

Como o critério leva até ele:

- **(1) Falsificação.** É geração corrente, descrita pelo próprio fornecedor
  como "a melhor combinação de velocidade e inteligência", uma banda inteira
  acima de um 7 B quantizado em Q4. Se ele também falhar em recuperar o que o
  Semgrep perde, isso **é** evidência de escopo, e não anedota.
- **(2) Janela.** 1M de contexto verificados, 128k de saída. Contra prompts de
  no máximo ~27.420 tokens, é folga de 36x. As 26 falhas somem.
- **(3) Verificabilidade.** **Único candidato cujo limite de taxa é público**:
  1.000 RPM, 2M ITPM, 400k OTPM no Start tier, com teto de gasto de US$ 500/mês.
  Dá para afirmar, **antes de pagar**, que a rodada fecha em uma noite.
- **(4) Integração.** Perde aqui: exige provedor novo, ~55 linhas mais testes.
- **(5) Custo.** Irrelevante na escala; US$ 12,43 contra US$ 1,43 do mais barato
  da faixa é uma diferença de US$ 11.

### 4.3 As alternativas, e por que cada uma foi recusada

Nenhum candidato da tabela fica sem destino.

| modelo | destino |
|---|---|
| `gpt-5-nano` | **recusado** — critério 1. Faixa barata; confirmação fraca. |
| `gemini-2.5-flash-lite` | **recusado** — critério 1. É um dos padrões atuais do projeto e a faixa mais barata do fornecedor; rodá-lo é um modelo pequeno confirmando o que outro modelo pequeno já disse. Agravante: cota de 20 req/dia no tier grátis. |
| `gpt-4o-mini` | **recusado** — critério 1, mesmo argumento. Outro padrão atual do projeto. |
| `gemini-3.1-flash-lite` | **recusado** — critério 1. Nome novo, mesma faixa. |
| `gpt-5-mini` | **recusado** — critério 1, por pouco. É o candidato mais barato que quase passa (US$ 1,43) e é **configuração pura**. Se o orçamento fosse o problema, seria este. Recusado porque um "mini" mantém a dúvida da banca de pé: *"mas você testou um modelo bom?"*. |
| `gemini-2.5-flash` | **recusado** — critério 3. Limite de taxa não publicado, no fornecedor que já travou este trabalho por cota. |
| `gpt-5.4-mini` | **recusado** — critérios 1 e 3. |
| `claude-haiku-4-5` | **recusado** — critério 1, por pouco. Janela de 200k verificada, limite de taxa público, US$ 4,78. É a opção econômica caso `claude-sonnet-5` seja vetado por custo; fica registrada como **segunda escolha**. |
| `gpt-4.1` | **recusado** — critérios 2 e 3: janela não verificada hoje e limite de taxa não público. Geração anterior. |
| `gpt-5.6-terra` | **recusado por pouco, e é o concorrente real.** US$ 10,19, janela de 1,05M verificada, geração corrente e **configuração pura** (zero linha de código). Perde só no critério 3: RPM/TPM não publicados. Ver §4.3b. |
| `gemini-3.1-pro-preview` | **recusado** — critério 3, e `preview` no identificador: não é base estável para número de monografia. |
| `claude-opus-5` | **recusado** — critério 5. US$ 23,89 (US$ 31,06 ajustados) por um ganho de poder de falsificação que a faixa média já entrega. Se o `claude-sonnet-5` **não** falsificar a conclusão, este é o próximo passo defensável. |
| `gpt-5.5` | **recusado** — critérios 3 e 5. |
| `claude-fable-5-1`, `gpt-6-astra` | **recusados** — critério 5. US$ 47,79 (US$ 62,13 ajustados) para responder uma pergunta de escopo é desproporcional. |

#### 4.3b A decisão apertada, exposta — e um conflito de interesse declarado

`claude-sonnet-5` e `gpt-5.6-terra` empatam em tudo que importa e se separam em
dois critérios que apontam para lados opostos:

| | `claude-sonnet-5` | `gpt-5.6-terra` |
|---|---|---|
| custo/rodada | 9,56 (12,43 ajustado) | 10,19 |
| janela verificada | 1M ✅ | 1,05M ✅ |
| limite de taxa | **público** ✅ | não publicado ❌ |
| integração | provedor novo (~55 linhas) | **configuração, zero código** ✅ |

A recomendação pesa **verificabilidade acima de integração**, porque o risco que
já se materializou neste projeto foi o de vazão, e porque o custo de integração
aqui é conhecido e pequeno — o projeto escreveu dois provedores desses, de 52 e
57 linhas.

> **Conflito de interesse, declarado.** Este levantamento foi feito por um
> modelo da Anthropic, e recomenda um modelo da Anthropic. O design já previa
> esse risco ("quem faz o levantamento pode preferir o que conhece"). Por isso:
> o critério está escrito **antes** da tabela de decisão, é mecânico, e o ponto
> exato onde ele vira está isolado acima. **Quem pesar integração acima de
> verificabilidade chega em `gpt-5.6-terra` seguindo o mesmo critério, e essa
> leitura é legítima.** Quem revisar este documento deveria começar por aqui.

### 4.4 O modelo recomendado pode falsificar a conclusão atual?

**Pode — e é por isso que ele foi escolhido.** A declaração explícita:

`claude-sonnet-5` **não** está na mesma banda de capacidade dos modelos locais
já medidos. `qwen2.5-coder:7b` (7,6 B, Q4_K_M) e `gemma2:9b` são modelos de 7–9
B quantizados; a Rodada 6 gastou um dia de GPU para mostrar que trocar um pelo
outro não move o teto, **porque os dois estão na mesma banda**. Um modelo de
geração corrente de fornecedor comercial não está.

O que isso compra, concretamente: se `claude-sonnet-5` recuperar uma fração
substancial dos casos que o Semgrep perde, o resultado atual do trabalho
**cai** — a conclusão passaria a ser "a limitação era do modelo, não da
abordagem". Se ele **também** recuperar de 4 a 8 %, a conclusão negativa deixa
de valer só "para modelos locais de 7–9 B" e passa a valer para a faixa média
comercial, que é a diferença entre um resultado frágil e um resultado com
escopo.

**O contraponto honesto:** os dois modelos padrão do projeto
(`gemini-2.5-flash-lite`, `gpt-4o-mini`) **não** têm esse poder. São a faixa
barata de cada fornecedor e provavelmente estão na mesma banda de um 7 B
especializado em código. Rodá-los custaria US$ 1,12 os dois e produziria
exatamente a confirmação fraca que a Rodada 6 já demonstrou não mover nada.
**Executar a matriz 2x2 como `matriz-experimental` a define hoje não responderia
a pergunta de escopo.**

### 4.5 As questões em aberto do `design.md`

**① Existe restrição institucional de fornecedor?** — **Continua aberta.** Nada
no repositório menciona restrição de API estrangeira ou de região. É pergunta
para o orientador ou o regimento do programa, e não para o código. *O que falta
para fechar:* uma resposta do orientador. *Impacto se houver restrição:* corta
candidatos antes do preço, e possivelmente todos — o que tornaria a conclusão
"com modelos locais" não uma fragilidade, mas a única opção disponível, o que é
um argumento de defesa bem mais forte do que o atual.

**② População inteira ou amostra de ~300?** — **Fechada: população inteira.** A
amostra só faria sentido se custo ou parede fossem proibitivos, e nenhum dos
dois é: US$ 12,43 contra US$ 2,35, uma noite de parede contra ~20 minutos.
Contra isso, a população inteira preserva o **pareamento por `ID_Caso`** com as
Rodadas 1 a 6 — que é o que sustenta o McNemar e é o ativo metodológico mais
caro deste trabalho. Uma amostra exigiria reestratificar e defender a
representatividade, trabalho maior que os US$ 10 economizados. **Salvo se ①
impuser restrição**, caso em que a amostra volta à mesa.

**③ Enquadramento direto ou original?** — **Continua aberta, e é a mais cara.**
A Rodada 5 mostrou que o enquadramento importa, e o achado central da Rodada 4 é
que **o baseline das Rodadas 1-3 nunca foi controle limpo** (lia a fraqueza no
`Alerta Semgrep:` do contexto). Rodar só o prompt antigo reproduz um artefato
conhecido; rodar só o novo quebra a comparabilidade com as Rodadas 1-3. Rodar os
dois dobra para **US$ 24,86** na rodada de dois braços — o que, nesta escala,
não é obstáculo. *Recomendação preliminar (não é decisão desta change):* rodar
os dois, porque US$ 12 a mais é preço baixo por não ter que escolher qual
comparabilidade sacrificar. *O que falta para fechar:* decidir se o capítulo de
resultados vai comparar contra as Rodadas 1-3 ou contra a 5.

---

## 5. O que este documento não decide

Por desenho (design D7): **se a rodada vai acontecer**. Ele produz a informação;
a decisão de gastar é de quem lê. Também não implementa provedor, não altera
`src/provedores/precos.py` e não consome cota.

Para executar, seria preciso: conta com billing ativo no fornecedor escolhido
(não pressuposta em lugar nenhum deste documento), a chave em `ANTHROPIC_API_KEY`,
um `ProvedorAnthropic` de ~55 linhas com testes, e o registro do preço na tabela
do projeto **na data da execução** — não na de hoje.

## 6. Guardas de escopo, verificadas

- **Nenhuma chamada de API a fornecedor de LLM foi feita.** Nenhuma cota
  consumida, nenhum diretório novo em `results/`. As únicas requisições de rede
  foram as leituras das páginas públicas de preço, limites e modelos listadas em
  `2.2` e `2.4`.
- **`src/provedores/` inalterado**, tabela de preços incluída.
- **Nenhum `.tex` tocado.**
- Arquivos alterados por esta change: este documento (novo) e
  `docs/MAPA-TCC-O-QUE-REESCREVER.md` (§10, acrescentado).

## 7. Procedência dos números

| número | de onde |
|---|---|
| 3.172 chamadas, 3.199.085 / 315.981 tokens | recontagem dos CSVs de `results/rodada-4-triagem/` |
| 3.171 / 3.198.141 / 315.469 | `docs/ANALISE-RODADA-4.md`; difere por uma geração truncada (§1.1) |
| 2 h 07 min de parede | `duracao_s` do `manifesto.json` da Rodada 4 |
| 26 estouros de janela, prompts até ~27.420 | `docs/ANALISE-RODADA-4.md` §11 |
| 7.337 tokens no maior prompt que passou | recontagem dos CSVs |
| população 2.328 e trilhas | `manifesto.json` da Rodada 4 |
| 17 vereditos comerciais + 5 `API_ERROR` | `results/piloto-gemini/` (10 + 7 vereditos válidos) |
| todos os preços | páginas dos fornecedores, consultadas em 2026-09-17 (§2.2) |
| limites da Anthropic | `platform.claude.com/docs/en/api/rate-limits`, 2026-09-17 |
| 20 req/dia do tier grátis do Gemini | medição do próprio projeto, **não** documentação do fornecedor |
| +30 % do tokenizador Claude 4.7+ | nota na página de preços da Anthropic, 2026-09-17 |
| desconto e limites de batch (Google) | `ai.google.dev/gemini-api/docs/batch-api` e `…/docs/rate-limits`, 2026-09-17 |
| desconto e limites de batch (Anthropic) | `platform.claude.com/docs/en/build-with-claude/batch-processing`, 2026-09-17 |
| desconto e limites de batch (OpenAI) | `developers.openai.com/api/docs/guides/batch`, 2026-09-17 |

---

## 8. Modo batch — o desconto de 50 %, e o que ele muda de verdade

> Levantado em **2026-09-17**, a pedido, depois de fechada a recomendação da §4.
> Resposta curta: **o desconto existe e é real nos três fornecedores, mas não
> muda a decisão — porque preço nunca foi a variável de decisão.** O que o modo
> batch muda de verdade é tempo de parede e risco de vazão. Detalhe abaixo.

### 8.1 O que cada fornecedor oferece

Todos verificados hoje, nas páginas de documentação de cada um:

| | **Google** | **Anthropic** | **OpenAI** |
|---|---|---|---|
| desconto | **50 %** do custo padrão | **50 %** em entrada e saída | **50 %** vs. síncrono |
| prazo alvo | 24 h ("na maioria dos casos, bem mais rápido") | maioria **< 1 h**; resultados liberados quando tudo termina ou em 24 h | 24 h ("frequentemente mais rápido") |
| expiração | job expira em **48 h** se ainda pendente | lote expira em **24 h**; requisição expirada **não é cobrada** | 24 h |
| tamanho | inline < 20 MB, ou JSONL até **2 GB** | **100.000** requisições ou **256 MB** por lote | **50.000** requisições, **200 MB**; 2.000 lotes/hora |
| resultados ficam | 6 semanas | 29 dias | 30 dias |
| pool de limites | enfileiramento próprio, **publicado por tier** | fila própria (Start: 200.000 requisições em processamento) | **pool separado** do síncrono |
| endereço | `ai.google.dev/gemini-api/docs/batch-api` | `platform.claude.com/docs/en/build-with-claude/batch-processing` | `developers.openai.com/api/docs/guides/batch` |

Uma rodada de dois braços tem 3.172 chamadas — **cabe em um único lote** em
qualquer um dos três.

### 8.2 Custo com e sem batch

Mesmos tokens medidos da §1.1. `*(aj.)*` marca as linhas já com o +30 % do
tokenizador Claude 4.7+ da §3.1.

| faixa | modelo | rodada sínc. | **rodada batch** | matriz 2x2 sínc. | **matriz batch** |
|---|---|---:|---:|---:|---:|
| barata | `gemini-2.5-flash-lite` | 0,45 | **0,22** | 0,89 | **0,45** |
| barata | `gpt-4o-mini` | 0,67 | **0,33** | 1,34 | **0,67** |
| média | `gpt-5-mini` | 1,43 | **0,72** | 2,86 | **1,43** |
| média | `gemini-2.5-flash` | 1,75 | **0,87** | 3,50 | **1,75** |
| média | `claude-haiku-4-5` | 4,78 | **2,39** | 9,56 | **4,78** |
| média | `gpt-5.6-terra` | 10,19 | **5,09** | 20,38 | **10,19** |
| média | `claude-sonnet-5` | 12,43 *(aj.)* | **6,21** | 24,85 | **12,43** |
| topo | `gpt-5.5` | 25,47 | **12,74** | 50,95 | **25,47** |
| topo | `claude-opus-5` | 31,06 *(aj.)* | **15,53** | 62,13 | **31,06** |
| topo | `gpt-6-astra` | 47,79 | **23,89** | 95,58 | **47,79** |
| topo | `claude-fable-5-1` | 62,13 *(aj.)* | **31,06** | 124,25 | **62,13** |

### 8.3 O que o desconto realmente compra — e por que não é barateamento

**Barateamento na ponta barata é irrelevante.** Economizar 22 centavos em
`gemini-2.5-flash-lite` não é decisão; é ruído. E a §4.1 já eliminou a faixa
barata por um motivo que desconto nenhum resolve: ela não tem poder de
falsificação. **Um modelo fraco pela metade do preço continua sendo um modelo
fraco.**

**O efeito interessante é o inverso do que "baratear" sugere: o batch puxa a
faixa de topo para dentro do orçamento da faixa média.**

```
claude-opus-5  em batch  = US$ 15,53
claude-sonnet-5 síncrono = US$ 12,43
```

Por **US$ 3,10 a mais** que a recomendação atual, o modo batch entrega um modelo
uma faixa inteira acima. Pelo critério da §4.1 — em que poder de falsificação é
o peso 1 e custo é apenas desempate — isso deveria bastar para mudar a
recomendação.

**Mas não muda, e o motivo importa.** Toda a tabela da §8.2 cabe entre US$ 0,22
e US$ 62,13. Nessa escala, **nem o preço cheio era obstáculo**: `claude-opus-5`
síncrono custa US$ 31,06, que também não é decisão orçamentária para um TCC. O
desconto de 50 % não destrava nada que os 100 % já não destravassem. Ele
confirma, com mais folga, o que o `design.md` já dizia: **dinheiro nunca foi o
gargalo deste projeto; cota e vazão foram.**

### 8.4 Onde o batch ganha de verdade: parede e vazão

Estes são os argumentos que sustentam o modo batch, e nenhum deles é preço.

1. **Parede.** A §3.2 estimou **1 h 46 min a 3 h 32 min** para 3.172 chamadas
   síncronas, porque `ProvedorHTTP.avaliar` é sequencial e a parede é
   `n × latência`. Em batch, submete-se tudo de uma vez: a Anthropic fecha a
   maioria dos lotes em **menos de 1 hora**. É submeter e ir dormir, em vez de
   segurar o processo por uma noite.
2. **A máquina fica livre.** Hoje a Fase 1 do Semgrep e o `llama-server` disputam
   RAM, e por isso as rodadas neurais precisam ser agendadas em volta da
   simbólica. Um lote comercial **não ocupa a máquina** — some a disputa, e a
   Fase 1 pode rodar em paralelo.
3. **O risco de vazão evapora.** Este é o ponto forte. O critério 3 da §4.1
   (verificabilidade do limite de taxa) existia porque **vazão foi o que matou o
   braço comercial deste trabalho**. Em batch não há RPM a estourar: o que existe
   é um limite de *enfileiramento*, e ele é preenchido de uma vez.
4. **Pool separado.** A OpenAI declara explicitamente que o batch tem pool de
   limites próprio, que não consome o síncrono.

### 8.5 A consequência incômoda: o critério que decidiu a §4 enfraquece

A recomendação da §4.2 foi decidida no critério 3 — a Anthropic é a única que
publica RPM/TPM síncronos. **Em batch, essa vantagem quase desaparece**, porque
o Google *publica* os limites de enfileiramento de batch por tier, embora não
publique os síncronos. Verificado hoje:

| tier | exemplo publicado (Gemini 3.8 Flash) |
|---|---|
| Tier 1 | 3.000.000 tokens enfileirados |
| Tier 2 | 400.000.000 |
| Tier 3 | 1.000.000.000 |
| Free | **não consta da tabela de batch** |

Dois achados concretos:

- **Uma rodada não cabe no Tier 1 do Google.** Os 3.199.085 tokens de entrada de
  uma rodada de dois braços excedem o limite de 3.000.000 em **6,6 %**. Seria
  preciso partir em dois lotes ou estar no Tier 2. É uma restrição pequena, mas
  é exatamente o tipo de coisa que só se descobre depois — e desta vez deu para
  descobrir antes.
- **Não há caminho gratuito, nem em batch.** O Free tier não aparece na tabela
  de enfileiramento. Confirma a §2.4 por outro lado.

Se o projeto for para batch, portanto, o desempate entre `claude-sonnet-5` e
`gpt-5.6-terra` **deixa de ser decidido pela verificabilidade de vazão**. Fica
decidido por custo de integração — onde, como a §8.6 mostra, **ninguém é
configuração pura**, então a vantagem que `gpt-5.6-terra` tinha na §4.3b também
some. Os dois voltam a empatar, e o desempate passa a ser poder de falsificação,
que é o critério 1.

### 8.6 O custo real do batch: ele quebra o contrato de provedor

Esta é a razão pela qual o batch **não** é recomendado para a primeira rodada.

O contrato da §1.3 é síncrono por construção:

```python
def avaliar(self, prompt: str) -> RespostaLLM     # um prompt, uma resposta, agora
```

Batch é outro formato de execução, não outro provedor:

| o que muda | impacto |
|---|---|
| `avaliar(prompt)` → `avaliar_lote(prompts) -> dict` | protocolo novo; `ProvedorLLM` não serve |
| submeter → **poll** → recuperar | o laço da rodada deixa de ser "chama e grava" |
| ordem de saída **não preservada** (a OpenAI declara) | exige mapear por `custom_id` para o `ID_Caso` |
| estado `expired` | caso novo de erro, distinto de `ERROR`; na Anthropic não é cobrado |
| checkpoint por `(ID_Caso, Modelo_LLM, Tipo_Prompt)` | hoje grava incrementalmente; em batch só há resultado no fim |
| `_aguardar_throttle`, backoff, `CODIGOS_TRANSITORIOS` | irrelevantes no lote; a lógica de retry é outra |

O que **se aproveita** inteiro: `validar_resposta`, `RespostaLLM`,
`precos.custo_usd` — são agnósticos de transporte.

**Estimativa honesta:** um provedor síncrono novo custa ~55 linhas (a §3.3 mediu
`gemini.py` em 57 e `openai.py` em 52). O modo batch custa **algo entre 150 e
250 linhas**, mais testes, **mais uma mudança em `run_pipeline.py` e no
checkpoint**, mais um requisito novo na spec `provedores-llm` ou
`matriz-experimental`. É de 3 a 5 vezes o custo, e — o que pesa mais — **mexe na
parte mais arriscada do sistema**, que é a lógica de checkpoint que garante que
os braços cubram exatamente a mesma população. `matriz-experimental` é explícita
em que comparação pareada quebrada é "a pior forma de falha possível aqui,
porque é silenciosa".

### 8.7 Veredito sobre o batch

**Recomendação mantida: `claude-sonnet-5`, síncrono, na primeira rodada.**

O raciocínio, explícito:

- Economizar US$ 6,21 não paga 200 linhas de código novo em cima da lógica de
  checkpoint. A troca é ruim por uma ordem de grandeza.
- A vantagem real do batch (parede, máquina livre, risco de vazão zero) é
  atraente, mas a §3.2 mostra que a parede síncrona já é **uma noite**, e uma
  noite é aceitável para uma rodada que se pretende fazer **uma vez**.
- Risco assimétrico: implementar batch antes de ter qualquer veredito comercial
  é construir esteira nova para transportar carga que ainda não se sabe se vale
  transportar.

**Quando o batch passa a valer a pena** — e vale a pena registrar agora, porque
o gatilho é objetivo:

1. **Se a decisão for ir para a faixa de topo.** `claude-opus-5` a US$ 15,53 em
   batch, contra US$ 31,06 síncrono, ainda não é decisão de orçamento — mas se a
   matriz completa em topo entrar em pauta (US$ 62,13 síncrono), o desconto começa
   a significar algo.
2. **Se a rodada precisar ser repetida várias vezes.** Uma rodada é US$ 12; dez
   variações de prompt são US$ 124, e aí 50 % é dinheiro. A questão aberta ③ da
   §4.5 (rodar os dois enquadramentos) já dobra o custo — e se virarem quatro
   variações, o batch se paga.
3. **Se a máquina não puder ficar ocupada uma noite.** Aí o argumento é
   operacional, não econômico, e é legítimo sozinho.

Nada disso está decidido nesta change. Fica registrado para que a decisão de
implementar batch, se vier, seja tomada com o número na mão em vez de com a
intuição de que "batch é mais barato" — que é verdade, e é irrelevante.

---

## 9. Revisão: custo em real, e o batch como padrão

> Acrescentado em **2026-09-17**, depois que a restrição orçamentária real foi
> declarada: **quem paga a conta recebe em BRL.** Isso não muda os preços, muda o
> **peso do critério 5** da §4.1, que estava declarado como "desempate apenas"
> sob a premissa de que a escala era irrelevante. A premissa era minha, não do
> projeto, e estava errada. Esta seção corrige.
>
> **Câmbio usado: USD 1 = BRL 5,15**, cotação de 2026-09-17. Como todo preço
> deste documento, é um retrato — e este envelhece mais rápido que os outros.

### 9.1 Tabela completa: Gemini × Claude × OpenAI, síncrono e batch

Custo de **uma rodada de dois braços** (3.172 chamadas, 3.199.085 tokens de
entrada, 315.981 de saída — os medidos da §1.1). Preços de batch **citados
individualmente** nas páginas dos fornecedores, não inferidos de um "50 % geral":

| fornec. | modelo | sínc. US$ | sínc. R$ | **batch US$** | **batch R$** |
|---|---|---:|---:|---:|---:|
| Gemini | `gemini-2.5-flash-lite` | 0,45 | 2,30 | 0,22 | **1,15** |
| Gemini | `gemini-2.5-flash` | 1,75 | 9,01 | 0,87 | **4,51** |
| Gemini | `gemini-3.5-flash-lite` | 1,75 | 9,01 | 0,87 | **4,51** |
| Gemini | `gemini-2.5-pro` | 7,16 | 36,87 | 3,58 | **18,43** |
| OpenAI | `gpt-5-mini` | 1,43 | 7,37 | 0,72 | **3,69** |
| OpenAI | `gpt-5.4-mini` | 3,82 | 19,68 | 1,91 | **9,84** |
| OpenAI | `gpt-5.6-terra` | 10,19 | 52,48 | 5,09 | **26,24** |
| OpenAI | `gpt-5.3-codex` | 10,02 | 51,61 | **não existe** | **—** |
| Claude | `claude-haiku-4-5` | 4,78 | 24,61 | 2,39 | **12,31** |
| Claude | `claude-sonnet-5` *(aj.)* | 12,43 | 63,99 | 6,21 | **32,00** |
| Claude | `claude-opus-5` *(aj.)* | 31,06 | 159,98 | 15,53 | **79,99** |

`*(aj.)*` = já com o +30 % do tokenizador Claude 4.7+ (§3.1). `claude-haiku-4-5`
usa o tokenizador anterior e não leva o ajuste.

**Resposta direta: `claude-sonnet-5` em batch custa US$ 6,21 = R$ 32,00** por
rodada de dois braços (US$ 4,78 = R$ 24,61 sem o ajuste de tokenizador). A
matriz 2x2 completa nele sairia por R$ 63,99.

### 9.2 Achado: o Codex não tem modo batch

`gpt-5.3-codex` (US$ 1,75 / US$ 14,00) aparece na tabela de preços padrão e na
de *fast mode* (US$ 3,50 / US$ 28,00), mas **não aparece na tabela de preços de
batch** — verificado em `developers.openai.com/api/docs/pricing` em 2026-09-17.

Duas consequências:

- O Codex é **o pior custo-benefício da lista para este uso**: R$ 51,61 por
  rodada, sem desconto possível, contra R$ 32,00 do `claude-sonnet-5` em batch.
  O preço de saída é alto (US$ 14/1M) porque ele é desenhado para gerar código
  longo — e esta pipeline pede **um JSON de duas chaves**, com 99,6 tokens de
  saída em média. Paga-se por uma capacidade que o prompt não usa.
- Como o modelo é especializado em *escrever* código e a tarefa aqui é
  **classificar** um trecho como VP ou FP, a especialização não é claramente
  vantagem. **Recusado**, e agora com um motivo a mais que na §4.3.

### 9.3 O que são os tiers do Google

Verificado em `ai.google.dev/gemini-api/docs/billing`, 2026-09-17. Os tiers são
do **billing account**, não do projeto, e o gasto acumulado em **qualquer produto
do Google Cloud** conta para a qualificação.

| tier | como se qualifica | teto de gasto/mês | enfileiramento de batch* |
|---|---|---|---|
| **Free** | projeto ativo, sem billing | — | **não consta da tabela de batch** |
| **Tier 1** | vincular billing ativo + **pré-pagar US$ 5** | US$ 250 | 3.000.000 tokens |
| **Tier 2** | **US$ 100 pagos** + 3 dias do primeiro pagamento | US$ 2.000 | 400.000.000 |
| **Tier 3** | **US$ 1.000 pagos** + 30 dias | US$ 20.000+ | 1.000.000.000 |

\* valores publicados para `gemini-3.8-flash`, usados como referência de ordem de
grandeza; variam por modelo.

**O que isso significa na prática, para este projeto:**

- **Tier 1 é trivial de alcançar: US$ 5 (R$ 25,75) pré-pagos.** É o tier em que
  este trabalho realisticamente vai estar.
- **Tier 2 é praticamente inalcançável aqui**, e isso é uma boa notícia
  disfarçada: exige **US$ 100 de gasto acumulado**. Rodando a R$ 4,51 por
  rodada, seriam ~114 rodadas para chegar lá. Ou seja: **o projeto inteiro cabe
  folgado dentro do Tier 1** e nunca vai esbarrar no teto de US$ 250/mês.
- **Mas o limite de enfileiramento do Tier 1 morde.** Os 3.199.085 tokens de
  entrada de uma rodada excedem os 3.000.000 em **6,6 %**. Em batch no Gemini,
  no Tier 1, seria preciso **partir a rodada em dois lotes** — o que é trivial
  (por braço, por exemplo: 1.196.812 e 2.002.273 tokens, ambos abaixo do teto),
  mas precisa estar no código desde o começo, não ser descoberto no meio.

### 9.4 Recomendação revisada, com o orçamento pesando

O critério da §4.1 continua válido; o que muda é que o critério 5 deixa de ser
desempate e passa a ter peso real. Aplicado de novo:

**Piso defensável — `claude-haiku-4-5` em batch: R$ 12,31 por rodada.**

- **Critério 1 (falsificação):** passa. O fornecedor o descreve como "o modelo
  mais rápido, com inteligência quase de fronteira". **Não** está na banda de um
  7 B quantizado em Q4 — que é a única comparação que importa aqui. É um degrau
  menor que o `claude-sonnet-5`, e o documento não vai fingir o contrário, mas é
  um degrau real.
- **Critério 2 (janela):** 200k verificados, 7x de folga sobre os ~27.420. As 26
  perdas por estouro somem igual.
- **Critério 3 (verificabilidade):** passa — mesmos limites publicados do Start
  tier (1.000 RPM, 2M ITPM), mais a fila de batch.
- **Critério 5:** R$ 12,31 contra R$ 32,00 do `claude-sonnet-5`. **R$ 20 de
  diferença por rodada**, que sob a premissa antiga era ruído e sob a premissa
  correta é 2,6x.
- Bônus: **não sofre o +30 % do tokenizador** (usa o anterior), então o número
  dele é mais firme que o do Sonnet.

**Se o orçamento permitir o degrau acima — `claude-sonnet-5` em batch: R$ 32,00.**
Continua sendo a escolha de maior poder de falsificação dentro da faixa média, e
R$ 32 por uma rodada que se pretende fazer uma vez ainda é defensável.

**Recusados por custo, agora explicitamente:** `claude-opus-5` em batch (R$ 79,99)
e qualquer coisa acima. `gpt-5.6-terra` em batch (R$ 26,24) fica de pé como
alternativa ao Sonnet, com a ressalva da §8.5.

**O piso absoluto, se o orçamento for o problema dominante:** `gpt-5-mini` em
batch, **R$ 3,69**. Ele foi recusado na §4.3 por ser um "mini" — mas a recusa era
sob a premissa de que custo não importava. Com R$ 3,69 contra R$ 12,31, ele volta
à mesa como **piloto**, não como rodada definitiva.

### 9.5 A jogada barata que resolve o dilema: pilotar antes

Uma amostra estratificada de ~300 casos são 600 chamadas — **18,9 % do custo de
uma rodada inteira**. Em batch:

**O que "300 casos" quer dizer, exatamente.** São **300 casos, cada um submetido
aos dois braços** — `baseline` e `especialista` — o que dá **600 chamadas**. Não
é 300 por braço (seriam 1.200 chamadas), e os valores abaixo **já são o total
somado dos dois braços**.

Os dois braços não custam igual, porque o prompt do especialista é maior: 1.261,7
tokens de entrada por chamada contra 755,1 do baseline (médias medidas na Rodada
4). O especialista sai de **30 % a 45 % mais caro** que o baseline, conforme a
mistura de preço de entrada e de saída de cada modelo.

| modelo | baseline | especialista | **total (600 ch.)** |
|---|---:|---:|---:|
| `gemini-2.5-flash-lite` | 0,09 | 0,13 | **R$ 0,22** |
| `gpt-5-mini` | 0,30 | 0,39 | **R$ 0,70** |
| `gemini-2.5-flash` | 0,37 | 0,48 | **R$ 0,85** |
| `gpt-5.4-mini` | 0,79 | 1,07 | **R$ 1,86** |
| `claude-haiku-4-5` | 0,98 | 1,35 | **R$ 2,33** |
| `gemini-2.5-pro` | 1,52 | 1,97 | **R$ 3,49** |
| `gpt-5.6-terra` | 2,11 | 2,85 | **R$ 4,96** |
| `claude-sonnet-5` | 2,54 | 3,51 | **R$ 6,05** |
| `claude-opus-5` | 6,36 | 8,77 | **R$ 15,13** |

**Se a amostragem for por sorteio na população**, em vez de 300 casos já sabidos
com candidato, o custo cai: só **68,1 %** dos casos chegam ao LLM, então 300
sorteados viram ~204 com candidato e **409 chamadas**.

| modelo | total, 300 sorteados (409 ch.) |
|---|---:|
| `gemini-2.5-flash-lite` | R$ 0,15 |
| `gpt-5-mini` | R$ 0,47 |
| `gemini-2.5-flash` | R$ 0,58 |
| `claude-haiku-4-5` | **R$ 1,58** |
| `claude-sonnet-5` | **R$ 4,12** |
| `claude-opus-5` | R$ 10,29 |

A primeira leitura (600 chamadas) é a que deve ser usada para **dimensionar
gasto**, porque é o teto; a segunda descreve o que acontece se a amostra for
sorteada sem olhar o resultado da Fase 1.

**Por R$ 6,05 dá para saber se o `claude-sonnet-5` derruba a conclusão.** Se o
piloto mostrar recall substancialmente acima dos 4 a 8 % locais, a rodada inteira
(R$ 32,00) se justifica sozinha. Se mostrar o mesmo teto, a resposta de escopo já
está dada e a rodada inteira vira opcional.

Isso inverte a ordem da decisão de um jeito que favorece quem tem orçamento
apertado: **não se escolhe o modelo e depois se paga; pilota-se dois ou três por
menos de R$ 10 no total e escolhe-se com dado na mão.** É a mesma lógica do
portão da tarefa 5.5 do braço de triagem, que já funcionou neste projeto.

> **Ressalva metodológica, que não pode ser esquecida:** o piloto serve para
> **decidir**, não para publicar. Um resultado de n=300 não substitui a rodada
> pareada sobre a população inteira, porque quebra a comparabilidade por
> `ID_Caso` com as Rodadas 1 a 6 — que é o ativo mais caro deste trabalho (§4.5,
> questão ②). Piloto é instrumento de decisão de gasto; a rodada publicável
> continua sendo a população inteira.

### 9.6 Mapeamento do modo batch por flag — investigação, não decisão

> **Registrado a pedido, para investigação.** Não é decisão desta change, não há
> tarefa correspondente em `tasks.md`, e nada disto foi implementado.

**Revisão do argumento da §8.6.** Lá eu pesei o custo do batch em *linhas de
código*, estimando 150–250 linhas como impeditivo. Com assistência de IA, contar
linhas é a métrica errada — escrever não é o gargalo. O que sobra de custo real é
**risco**, e ele é menor do que a §8.6 sugeriu, por um motivo específico:

O `custom_id` que os três fornecedores exigem para mapear requisição → resposta
pode ser **exatamente a chave de checkpoint que o projeto já usa**:

```
custom_id = f"{ID_Caso}|{Modelo_LLM}|{Tipo_Prompt}"
```

`matriz-experimental` já exige essa tripla ("Checkpoint por chave composta"). Se
o `custom_id` **for** a chave, o risco que eu levantei — pareamento quebrado
silenciosamente — fica **estruturalmente impedido**, não apenas testado: uma
resposta sem chave válida não tem onde ser gravada. A desordem que a OpenAI
declara ("output line order may not match input line order") deixa de importar.

**Esboço do desenho, se for investigado:**

| peça | proposta |
|---|---|
| flag | `--modo-envio sincrono\|batch`, padrão `sincrono` (mesma forma de `--modo-montagem`, que já existe) |
| protocolo | `ProvedorLote`: `submeter(prompts: dict[str, str]) -> str` e `recuperar(id_lote) -> dict[str, RespostaLLM]` |
| chave | `custom_id` = a tripla de checkpoint, como acima |
| coleta | o laço da rodada já monta o prompt por caso; em modo batch ele **acumula** em vez de chamar |
| retomada | gravar o `id_lote` em `results/<run_id>/lote.json` **antes** de submeter; resultados ficam no fornecedor por 29–42 dias, então um crash local não perde o gasto |
| `expired` | `Motivo_Nao_Deteccao` novo, distinto de `ERROR` — na Anthropic não é cobrado, e isso precisa aparecer na contabilidade |
| partição | lotes de no máximo ~1.500.000 tokens de entrada, para caber no Tier 1 do Gemini (§9.3) |
| manifesto | registrar `modo_envio`, `id_lote` e o fornecedor, para rastreabilidade |
| reaproveitado | `validar_resposta`, `RespostaLLM`, `precos.custo_usd` — agnósticos de transporte |

**O que ganha, além do preço:** a máquina fica livre (hoje Semgrep e
`llama-server` disputam RAM), a parede cai de 1 h 46 – 3 h 32 para menos de uma
hora na Anthropic, e o risco de vazão — o que de fato matou o braço comercial
deste trabalho — desaparece.

**O que ainda merece cuidado numa investigação:**

1. **Perda do checkpoint incremental.** Hoje cada veredito é gravado ao chegar.
   Em batch só há resultado no fim. Mitigado pelo `lote.json` e pela retenção do
   fornecedor, mas é comportamento novo.
2. **O piloto e a rodada precisam ser o mesmo código.** Se o piloto rodar
   síncrono e a rodada em batch, a diferença entre eles passa a incluir o modo de
   envio. Para o pareamento valer, **os dois braços de uma mesma rodada têm de
   usar o mesmo modo** — é o mesmo argumento que `matriz-experimental` já faz
   para o modo de montagem ("NÃO SHALL variar dentro de uma mesma rodada").
3. **Testar o caminho de erro sem gastar.** Um lote com 2 requisições custa
   frações de centavo; o teste do fluxo não precisa esperar a rodada real.

**Sugestão de encaminhamento, se virar change:** implementar o modo batch e
validá-lo com um lote de ~10 casos em `gemini-2.5-flash-lite` (custo:
R$ 0,01), antes de qualquer decisão sobre qual modelo rodar de verdade. Separa
"a esteira funciona" de "o modelo responde", que são duas perguntas diferentes e
falham por motivos diferentes.
