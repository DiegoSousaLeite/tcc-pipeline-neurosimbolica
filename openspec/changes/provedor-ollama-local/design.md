## Context

A camada de provedores já foi desenhada para isso. `src/provedores/base.py` concentra o laço de rede (throttle, retry com backoff, validação de schema, contabilidade) e as subclasses só fornecem quatro métodos: `_url()`, `_headers()`, `_payload(prompt)` e `_extrair(dados)`. `ProvedorGemini` e `ProvedorOpenAI` têm ~50 linhas cada, quase todas payload. Um terceiro provedor cabe na mesma forma.

O que **não** cabe são quatro suposições que a base herdou de ter nascido para APIs comerciais:

1. `avaliar()` devolve `ERROR` sem tocar a rede quando `api_key` é vazia (`base.py:245`). O Ollama não autentica.
2. `timeout_s = 60`. A primeira chamada de um modelo local inclui carregar 5 GB de pesos na VRAM; uma resposta de modelo com offload parcial para CPU pode passar de dois minutos.
3. `custo_usd` devolve `0.0` para modelo fora da tabela e `tabela_para_manifesto` o lista em `modelos_sem_preco`. Para um modelo local o zero é verdade, não lacuna.
4. `familia_do_modelo` (`__init__.py:23`) despacha por prefixo de nome de modelo e levanta `ValueError` para o resto. `qwen2.5-coder:7b` não tem prefixo que o identifique como local — `gemma2` é um modelo aberto do Google servido localmente, mas `gemini` é a API do mesmo Google.

E há um defeito que só aparece com nomes de modelo do Ollama: `Braco.rotulo` (`run_pipeline.py:465`) devolve `f"{modelo}__{prompt}"` e esse valor é usado direto como nome de arquivo em `executar_matriz` (`run_pipeline.py:712`). `qwen2.5-coder:7b__baseline.csv` tem dois-pontos, que é caractere reservado no Windows: a rodada morre ao abrir o CSV, antes do primeiro caso. Não é cosmético.

Restrições de hardware do pesquisador — Ryzen 5 5600 (6 núcleos), 32 GB de RAM, Radeon RX 7600 de 8 GB (gfx1102, atendido pela build ROCm do Ollama para Windows). A VRAM de 8 GB é o limite que governa quase todas as decisões abaixo.

**Fases tocadas**: apenas 3/4 (e só pela troca de provedor) e a gravação do manifesto. Fase 0 (`scripts/`), Fase 1 (`fase1_semgrep.py`), Fase 2 (`fase2_middleware.py`/`hidratacao.py`) e o cálculo de métricas (`metricas.py`) não mudam — o prompt que chega ao provedor local é byte a byte o mesmo que vai para o Gemini, o que é justamente a condição para o eixo "modelo" ser variável independente.

**Arquivos**: `src/provedores/ollama.py` (novo), `src/provedores/base.py`, `src/provedores/__init__.py`, `src/provedores/precos.py`, `run_pipeline.py`, `tests/test_provedores.py`, `tests/test_matriz.py`, `docs/PIPELINE.md`, `README.md`.

**Dependência nova**: nenhuma em Python. O Ollama expõe HTTP em `localhost:11434` e `requests` já é dependência — o mesmo argumento que dispensou o SDK da OpenAI (`openai.py:4-6`) dispensa aqui a biblioteca `ollama`. A dependência nova é externa e **opcional**: o binário do Ollama mais o modelo baixado, exigidos somente quando um braço local é pedido.

## Goals / Non-Goals

**Goals:**
- Um braço local rodando de ponta a ponta com `qwen2.5-coder:7b`, produzindo CSV e métricas indistinguíveis em formato dos braços comerciais.
- Trocar de modelo local ser questão de `--modelo`, sem código novo, para os outros três modelos cogitados.
- Nenhuma degradação silenciosa: prompt truncado, modelo ausente, servidor fora do ar e resposta cortada por limite de saída viram erro visível, nunca veredito.
- Reprodutibilidade equivalente à dos braços comerciais: o manifesto tem que permitir dizer, meses depois, quais pesos produziram cada número.

**Non-Goals:**
- Os da proposta, em especial: não substituir os braços comerciais, não fazer fine-tuning, não varrer quantizações, não automatizar a instalação do Ollama, não paralelizar braços.
- Não tornar o braço local mais tolerante que os comerciais em nada. Qualquer folga concedida só ao modelo local (mais tentativas, JSON mais permissivo, schema forçado no decodificador) vira vantagem artificial na comparação.

## Decisions

### 1. Namespace explícito no nome do modelo: `ollama:<tag>`

O braço é nomeado `--modelo ollama:qwen2.5-coder:7b`. `familia_do_modelo` passa a testar o prefixo `ollama:` **antes** dos prefixos comerciais, e o provedor separa no primeiro dois-pontos: `ollama:` fica como namespace, `qwen2.5-coder:7b` é a tag enviada ao servidor.

*Por que não inferir por prefixo de nome de modelo* (`qwen`, `deepseek`, `gemma`, ...): a lista teria que crescer a cada modelo testado, e o caso `gemma2` (modelo aberto do Google) contra `gemini` (API do Google) mostra que o espaço de nomes não é particionável por prefixo de forma estável. Pior: um erro de digitação cairia no `ValueError` de "modelo sem provedor conhecido" em vez de numa mensagem sobre modelo não instalado.

*Por que não uma flag `--provedor`*: ela precisaria ser pareada com `--modelo` posicionalmente, e `--modelo` é `action="append"` — pares posicionais entre duas listas repetíveis é uma fonte de erro de operação que não se justifica para resolver um problema de nomenclatura.

Efeito colateral desejável: a coluna `Modelo_LLM` do CSV passa a dizer `ollama:qwen2.5-coder:7b`, que carrega **onde** rodou, não só o quê. É exatamente o que a tabela de resultados da monografia precisa mostrar.

### 2. Exigência de credencial passa a ser atributo do provedor

`ProvedorHTTP` ganha `exige_chave: bool = True`; `ProvedorOllama` declara `False`. A guarda de `avaliar()` passa a ser `if self.exige_chave and not self.api_key`.

*Por que não preencher `api_key` com um valor de fachada* (`"local"`): esconderia a intenção e faria um Gemini mal configurado passar da guarda se alguém copiasse o padrão. *Por que não sobrescrever `avaliar()` no provedor local*: duplicaria o laço de retry, que é justamente o que precisa ser idêntico entre braços.

### 3. `format: "json"`, não schema estruturado

O Ollama aceita em `format` tanto `"json"` quanto um JSON Schema, e o schema forçaria o decodificador a só emitir `VP` ou `FP`. **Não vamos usar o schema.** O Gemini recebe `responseMimeType: application/json` e o GPT recebe `response_format: {type: json_object}` — os dois exigem JSON válido, nenhum dos dois restringe o valor do campo. Impor o enum apenas ao modelo local eliminaria dele uma modalidade de falha ("respondeu `TALVEZ`") que os comerciais continuam correndo, e a taxa de erro de esteira é um dos números comparados. `format: "json"` iguala a exigência; o enum continua sendo cobrado por `validar_resposta`, como para todos.

### 4. Janela de contexto fixada em 8192, com estouro virando erro

`options.num_ctx = 8192` explícito em toda requisição, configurável por `OLLAMA_NUM_CTX`.

O padrão do servidor é 4096 e o excedente é **descartado em silêncio** — nenhuma exceção, nenhum campo de aviso. Um veredito emitido sobre um arquivo Go visto pela metade entra no CSV idêntico a um veredito legítimo. É o modo de falha mais perigoso desta mudança inteira, e por isso a detecção é em duas camadas:

- **Antes da chamada**: estimativa barata de tokens (`len(prompt) / 3.5`, folgada para código, onde a razão caractere/token é menor que em prosa). Acima de `num_ctx - num_predict`, o caso vira `ERROR` sem gastar minutos de GPU.
- **Depois da chamada**: o servidor devolve `prompt_eval_count`. Se ele encostar no teto (`>= num_ctx - num_predict`), houve truncamento e o resultado vira `ERROR`, mesmo que o JSON tenha vindo bem-formado. Também vira `ERROR` quando `done_reason == "length"`, que é a saída cortada por `num_predict` — nesse caso o JSON normalmente já sai inválido, mas o motivo registrado precisa ser o certo.

  **Corrigido durante a implementação (achado da rodada 6.1):** `done_reason == "length"` não é a única forma de a geração morrer no meio. Em 3 dos 1616 casos, o Ollama 0.32.5 abortou a geração com o modelo em laço degenerado e devolveu `HTTP 200` com `done: false`, **sem** `done_reason` e **sem** nenhuma contagem de token. A checagem passa a aceitar as duas formas (`done is False` ou `done_reason == "length"`). O efeito prático na rodada foi só o motivo registrado — o JSON cortado já caía em `ERROR` pela validação de schema —, mas a falha de desenho era real: um corte que caísse logo depois de uma chave de fechamento produziria JSON válido, e o veredito de uma geração que o próprio servidor não declarou concluída seria aceito. É exatamente a classe de contaminação que este provedor existe para impedir.

*Por que 8192 e não mais*: é o que fecha a conta de VRAM com o modelo de 7B. Q4_K_M pesa ~4,7 GB; o cache KV de 8k tokens, com a atenção agrupada do Qwen2.5, fica na casa de 0,5 GB. Sobra margem para o contexto do sistema gráfico do Windows dentro dos 8 GB. Em 16k o cache dobra e a folga desaparece; se a medição da tarefa de calibragem mostrar que os prompts cabem em 8k com sobra, fica 8k.

`num_predict = 512`: a saída é um JSON com veredito e justificativa. O teto existe para que um modelo que entre em laço não segure a rodada por dez minutos.

### 5. Verificação prévia única, que também alimenta o manifesto

Uma função `sondar()` no provedor local, chamada uma vez por rodada em `main()` depois de `definir_bracos()`, combina `GET /api/version`, `GET /api/tags` e `POST /api/show`. Ela decide se a rodada pode começar (servidor de pé, tag instalada) e devolve, de uma vez, o que vai para o manifesto: versão do servidor, `digest` do modelo, `details.quantization_level`, `details.parameter_size` e a janela máxima que o modelo declara.

*Por que verificar antes*: sem isso, um `ollama serve` esquecido produz centenas de linhas `ERROR` de falha de rede, cada uma depois de quatro tentativas com backoff — dezenas de minutos para descobrir um erro de operação. A mensagem de aborto nomeia o endereço tentado, o modelo pedido, os instalados e o `ollama pull` correspondente.

*Por que o digest e não só a tag*: `qwen2.5-coder:7b` é ponteiro mutável no registry, igual a `latest`. Sem o digest, o número do capítulo de resultados não é reatribuível aos pesos que o geraram — é o mesmo raciocínio do `sha256` do catálogo de CWE e da `VERSAO_TABELA` de preços.

### 6. `keep_alive` longo e sem throttle

`keep_alive: "30m"` no payload, e `intervalo_minimo_s = 0`. Sem `keep_alive`, o servidor descarrega o modelo após 5 minutos ociosos e a próxima chamada paga de novo os ~15 s de carregamento; com centenas de casos, isso é dinheiro em tempo de parede jogado fora. Throttle é para cota, e não há cota local.

`timeout_s = 600`, configurável por `OLLAMA_TIMEOUT`. Cobre o carregamento inicial e uma resposta longa de modelo com offload parcial para CPU. O retry da base continua valendo para falha de conexão, mas o provedor distingue na justificativa "conexão recusada" (servidor caiu) de "tempo limite excedido" (inferência lenta demais) — sem isso, a métrica de erro do braço local mistura problema de operação com limitação de hardware.

### 7. Rótulo de braço saneado, sem perder o nome do modelo

`Braco.rotulo` passa por um saneamento que substitui os caracteres reservados do Windows (`: * ? " < > | / \`) por `-`. Nomes já válidos ficam **idênticos** aos de hoje: `gemini-2.5-flash-lite__especialista.csv` continua com esse nome, o que preserva a retomada de rodadas em andamento e a leitura dos CSVs já gravados. Só o braço local ganha nome novo: `ollama-qwen2.5-coder-7b__baseline.csv`.

Colisão (dois modelos que sanearizam para o mesmo texto) é detectada em `definir_bracos`, e os braços em conflito recebem sufixo com os primeiros caracteres do `sha256` do nome cru. É improvável na prática, mas silenciosamente sobrescrever o CSV de um braço com o de outro seria falha de integridade dos dados, do mesmo tipo do checkpoint indexado só por `ID_Caso`.

O nome cru do modelo continua na coluna `Modelo_LLM` de cada linha e no manifesto: o rótulo é nome de arquivo, não identidade.

### 8. Custo zero declarado, com a classificação vindo de fora de `precos.py`

`tabela_para_manifesto` ganha um parâmetro `modelos_locais`, computado em `run_pipeline` a partir de `familia_do_modelo`, e o manifesto passa a ter três listas: `precos` (tabelados), `modelos_sem_preco` (comerciais não tabelados — anomalia a notar) e `modelos_locais_sem_custo` (zero por construção).

*Por que não `precos.py` decidir sozinho pelo prefixo `ollama:`*: a tabela de preços não deve conhecer namespaces de provedor; ela sabe de preços. A classificação de família já existe em `__init__.py` e é de lá que a resposta sai.

### Impacto em custo, cota e tempo de execução

- **Cota de LLM comercial**: zero. Nenhuma chamada a Gemini ou OpenAI é feita ou alterada por esta mudança. O braço local, ao contrário, é o primeiro que pode rodar a população inteira repetidas vezes sem billing — é o principal ganho operacional aqui.
- **Custo monetário**: zero, fora energia elétrica.
- **Tempo de parede** (medido na tarefa 5.5, `--amostra 30` nos dois tipos de prompt, 60 chamadas, com o modelo em `100% GPU`): **6,19 s por caso no `baseline`** (saída média de 125 tokens) e **5,87 s no `especialista`** (116 tokens). A estimativa teórica anterior — 15 a 25 s por caso — era pessimista por um fator de ~3: a avaliação do prompt na RX 7600 é muito mais rápida do que se supôs, e a saída real é metade do que se projetou. Extrapolando para os 805 casos `DETECTADO` da população: **~83 min no braço `baseline`, ~79 min no `especialista`, ~2 h 45 para os dois** — uma tarde, não uma rodada noturna. `qwen2.5-coder:14b` e `deepseek-coder-v2:16b` não cabem nos 8 GB e rodam com camadas na CPU; conte com 3 a 6 vezes esse tempo, o que os torna viáveis mas não confortáveis.

  Como o design já dizia, esse número é **nota de viabilidade, não resultado medido com rigor**: a máquina é de uso geral e não houve controle de carga.
- **Modelos e VRAM**: `qwen2.5-coder:7b` (Q4, ~4,7 GB) e `gemma2:9b` (Q4, ~5,4 GB, mas com janela máxima de 8k e cache KV mais pesado) cabem. `qwen2.5-coder:14b` (~9 GB) e `deepseek-coder-v2:16b` (~8,9 GB, mistura de especialistas com poucos parâmetros ativos, o que ameniza a lentidão do offload) não cabem em Q4. Nada disso está codificado: o modelo é parâmetro, e a exigência de desenho é só que o provedor não minta quando o modelo não couber.

## Risks / Trade-offs

- **[O braço local perde casos por estouro de contexto e deixa de ser comparável]** → É o risco mais sério: se os arquivos maiores viram `ERROR` só no braço local, a população dele fica menor que a dos comerciais e o McNemar pareado perde a premissa. Mitigação: a tarefa de calibragem mede a distribuição de tamanho de prompt sobre a população **antes** da rodada de valer, e `num_ctx` é escolhido acima do máximo observado. Se o máximo não couber nos 8 GB, as saídas são reduzir a hidratação (o que muda o prompt e portanto exige rodar os braços comerciais de novo, no mesmo prompt) ou declarar o braço local restrito a um subconjunto — explicitamente, na monografia. O que não é opção é rodar e reportar como se a população fosse a mesma.

- **[Fallback silencioso para CPU]** → Se o ROCm não engatar na RX 7600, o Ollama roda em CPU: mesmos vereditos, throughput ~10x menor. Mitigação: registrar no manifesto se a rodada foi em GPU ou CPU (via `ollama ps`) e tratar o tempo como nota de viabilidade, não como resultado — a máquina é de uso geral e não há controle de carga.

- **[Determinismo é aproximado]** → Temperatura 0 e semente fixa não garantem reprodução bit a bit entre versões do servidor, quantizações ou divisões GPU/CPU diferentes. Mitigação: registrar versão, digest, quantização e semente; rodar cada braço de uma vez; e não afirmar na monografia mais do que "geração determinística dentro da configuração registrada".

- **[Modelo de 7B erra mais o formato de saída]** → A taxa de `ERROR` por JSON inválido tende a ser maior que nos comerciais. Isso é **resultado**, não defeito a corrigir: reportar. A tentação a resistir é afrouxar a validação ou aumentar as tentativas só nesse braço — viraria vantagem artificial (ver Non-Goals).

- **[Contenção de VRAM com o resto da máquina]** → 8 GB são compartilhados com o compositor do Windows e qualquer navegador aberto; um pico pode empurrar camadas para a CPU no meio da rodada, mudando o tempo mas não os vereditos. Mitigação: rodar com a máquina ociosa, execução sequencial (já é Non-Goal paralelizar).

- **[Uma quinta implementação de provedor pressiona a base]** → A base já acumula throttle, retry, custo e agora credencial opcional e limites por provedor. Trade-off aceito: quatro atributos configuráveis numa dataclass é preço baixo diante de duplicar o laço de rede, e a alternativa (hierarquia "provedor local" vs "provedor comercial") acrescenta uma camada para dois métodos de diferença.

## Migration Plan

Puramente aditiva; não há migração de dados. Nenhum CSV existente é lido de forma diferente, nenhum resultado publicado é invalidado, e o comportamento de `--matriz` fica idêntico. Rollback é não passar `--modelo ollama:...` — em máquina sem Ollama, nada da mudança é exercitado.

Ordem de validação: subir o servidor e baixar o modelo → `--amostra 5 --modelo ollama:qwen2.5-coder:7b` para confirmar a esteira → medir tamanho de prompt e calibrar `num_ctx` → `--amostra 30` para estimar tempo por caso → rodada completa sob `run_id` novo.

## Open Questions

- ~~`num_ctx = 8192` cobre o maior prompt da população?~~ **Respondido pela calibragem (tarefa 5.4): sim, fica em 8192.** Medição de `scripts/medir_prompts.py` sobre os 805 casos `DETECTADO` da população (as Fases 1/2 rodaram sobre os 948; 140 deram `NAO_DETECTADO` e 3 estouraram o tempo do Semgrep — nenhum dos dois grupos vira prompt):

  | prompt | n | mín | mediana | p95 | máx | acima do teto |
  |---|---|---|---|---|---|---|
  | `baseline` | 805 | 265 | 575 | 1976 | 7016 | 0 (0,0%) |
  | `especialista` | 805 | 711 | 1091 | 2477 | 7462 | 0 (0,0%) |

  O teto de entrada é 7680 (`8192 - 512`), e o maior prompt observado está 218 tokens abaixo dele. A margem é apertada em termos relativos (~2,8%), mas erra para o lado seguro por construção: os números da tabela vêm da estimativa `len/3.5`, que **superestima** em código, então o `prompt_eval_count` real fica abaixo deles. Subir para 12k/16k dobraria o cache KV sem caso que o justifique e comeria a folga de VRAM que hoje mantém o modelo em `100% GPU`. A camada de detecção pós-chamada continua valendo como rede de segurança: se algum caso encostar no teto na rodada de valer, ele vira `ERROR` visível em vez de veredito contaminado. Nenhuma das saídas do risco de população precisou ser acionada — a população do braço local é a mesma dos comerciais.
- O braço local entra na monografia como terceiro ponto do eixo "modelo" na tabela principal, ou como seção própria de viabilidade on-premise? A segunda opção é mais honesta quanto à assimetria de latência e custo, mas a primeira aproveita melhor os testes pareados. Decisão do texto, não do código — e pode ser tomada depois de ver os números.
- Vale rodar o segundo modelo local (`qwen2.5-coder:14b`) para separar "modelo aberto é pior" de "modelo pequeno é pior"? Cientificamente é a pergunta mais interessante que sobra; depende do tempo restante de TCC e do custo de 10–15 h por braço.
