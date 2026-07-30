## 1. Ambiente local

- [x] 1.1 Instalar o Ollama no Windows e subir o serviço; verificar com `curl http://localhost:11434/api/version` (ou `Invoke-RestMethod`) que a versão é devolvida.
- [x] 1.2 `ollama pull qwen2.5-coder:7b` e confirmar em `ollama list` a tag, o tamanho e a quantização; anotar o `digest` de `ollama show qwen2.5-coder:7b --modelfile`.
- [x] 1.3 Confirmar se a inferência usa a GPU: rodar `ollama run qwen2.5-coder:7b "oi"` e checar em `ollama ps` a coluna de processador (`100% GPU` vs `CPU`). Registrar o resultado no comentário de `src/provedores/ollama.py` — se cair em CPU, o tempo estimado no design muda de ordem.

## 2. Base do provedor: credencial e limites por provedor

- [x] 2.1 Adicionar `exige_chave: bool = True` a `ProvedorHTTP` e trocar a guarda de `avaliar()` por `if self.exige_chave and not self.api_key`; teste em `tests/test_provedores.py` cobrindo que provedor com `exige_chave=False` e sem chave chega a fazer o POST (com sessão falsa), e que Gemini/OpenAI sem chave continuam devolvendo `ERROR` sem tocar a rede.
- [x] 2.2 Permitir que a subclasse defina o padrão de `timeout_s` sem que o valor explícito do chamador seja sobrescrito (mesmo tratamento de sentinela `None` já usado em `intervalo_minimo_s`); teste cobrindo os dois caminhos.

## 3. `ProvedorOllama`

- [x] 3.1 Criar `src/provedores/ollama.py` com `ProvedorOllama(ProvedorHTTP)`: `nome="ollama"`, `exige_chave=False`, `intervalo_minimo_s=0`, `timeout_s=600` (env `OLLAMA_TIMEOUT`), base URL de `OLLAMA_BASE_URL` (padrão `http://localhost:11434`), `_url()` apontando para `/api/chat` e `_headers()` só com `Content-Type`.
- [x] 3.2 Implementar a propriedade que extrai a tag do nome do braço, separando `ollama:` no primeiro dois-pontos (`ollama:qwen2.5-coder:7b` → `qwen2.5-coder:7b`); teste com tag simples, tag com dois-pontos e nome de registry com barra.
- [x] 3.3 Implementar `_payload()`: `model` com a tag, `messages` com um único turno de usuário, `stream: false`, `format: "json"` (**não** JSON Schema — ver decisão 3 do design), `keep_alive: "30m"` e `options` com `temperature: 0`, `seed` fixa, `num_ctx` (env `OLLAMA_NUM_CTX`, padrão 8192) e `num_predict: 512`. Teste verificando o payload montado campo a campo.
- [x] 3.4 Implementar `_extrair()`: texto de `message.content`, tokens de `prompt_eval_count` e `eval_count`. Teste com resposta gravada real do servidor.
- [x] 3.5 Implementar a detecção de truncamento **pós-chamada**: `prompt_eval_count >= num_ctx - num_predict` ou `done_reason == "length"` viram `ERROR` com motivo distinto, sem virar veredito. Testes para os dois casos, incluindo o caso em que o JSON veio bem-formado mas o prompt foi truncado.
- [x] 3.6 Implementar a checagem **pré-chamada** de tamanho de prompt (estimativa `len(prompt)/3.5`): acima de `num_ctx - num_predict`, devolver `ERROR` sem fazer requisição. Teste confirmando que a sessão falsa não recebeu POST.
- [x] 3.7 Distinguir, na justificativa do `ERROR`, conexão recusada de tempo limite excedido. Teste com `requests.ConnectionError` e `requests.Timeout`.
- [x] 3.8 Implementar `sondar()`: `GET /api/version`, `GET /api/tags` e `POST /api/show`, devolvendo dicionário com versão do servidor, digest, quantização, tamanho de parâmetros, janela máxima declarada e `num_ctx` efetivo; campo que o servidor não informar sai como ausente, não omitido. Levanta erro acionável (endereço tentado / modelos instalados / comando `ollama pull`) quando o servidor está fora do ar ou a tag não está instalada. Testes para os três desfechos.

## 4. Fábrica, preços e matriz

- [x] 4.1 Em `src/provedores/__init__.py`: registrar `ollama` em `_FABRICAS`, fazer `familia_do_modelo` testar o prefixo `ollama:` antes dos prefixos comerciais, expor `MODELO_OLLAMA_PADRAO = "ollama:qwen2.5-coder:7b"` e `ProvedorOllama` no `__all__`. Testes de resolução para os três provedores e de `ValueError` para modelo desconhecido.
- [x] 4.2 Em `src/provedores/precos.py`: `tabela_para_manifesto` passa a aceitar `modelos_locais` e a emitir `modelos_locais_sem_custo` separado de `modelos_sem_preco`; `custo_usd` continua devolvendo zero. Teste com rodada mista (um local + um comercial tabelado + um comercial fora da tabela).
- [x] 4.3 Sanear `Braco.rotulo` em `run_pipeline.py`: substituir os caracteres reservados do Windows por `-`, mantendo **inalterados** os rótulos já válidos. Testes em `tests/test_matriz.py` fixando que `gemini-2.5-flash-lite__especialista` não muda e que `ollama:qwen2.5-coder:7b` vira `ollama-qwen2.5-coder-7b__baseline`.
- [x] 4.4 Detectar colisão de rótulo saneado em `definir_bracos` e desambiguar com sufixo de hash do nome cru; teste com dois modelos que sanearizam para o mesmo texto, verificando que os dois CSVs têm nomes distintos.
- [x] 4.5 Chamar `sondar()` uma vez por rodada em `main()`, depois de `definir_bracos()` e antes do primeiro caso, apenas quando há braço local; abortar com a mensagem acionável. Teste garantindo que rodada só-comercial não faz nenhuma sondagem.
- [x] 4.6 Estender `gravar_manifesto` com o bloco `modelos_locais` (versão do Ollama, digest, quantização, `num_ctx` efetivo, semente, GPU ou CPU) e passar `modelos_locais` a `tabela_para_manifesto`. Teste inspecionando o JSON gerado.

## 5. Validação de esteira

- [x] 5.1 Rodar `python run_pipeline.py --amostra 5 --modelo ollama:qwen2.5-coder:7b --prompt especialista` e confirmar que o CSV foi criado com nome saneado, tem vereditos em `{VP, FP}`, tokens preenchidos, custo zero e `Modelo_LLM == ollama:qwen2.5-coder:7b`.
- [x] 5.2 Confirmar as falhas visíveis à mão: com o serviço parado, a rodada aborta antes do primeiro caso; com uma tag inexistente, aborta nomeando os modelos instalados; com `OLLAMA_NUM_CTX=512`, os casos viram `ERROR` de contexto e nenhum veredito é gravado.
- [x] 5.3 Escrever `scripts/medir_prompts.py` (ou estender o modo `--dry-run`) para percorrer a população e reportar a distribuição de tamanho de prompt em tokens estimados — mínimo, mediana, p95, máximo — por tipo de prompt. Verificável pela saída no terminal.
- [x] 5.4 Calibrar `num_ctx` com o resultado de 5.3 e registrar a decisão no design (`Open Questions`). Se o máximo não couber em 8 GB de VRAM, registrar explicitamente qual das saídas do risco de população foi escolhida.
- [x] 5.5 Rodar `--amostra 30` nos dois tipos de prompt, medir o tempo médio por caso e extrapolar o tempo por braço; anotar o número no design, substituindo a estimativa teórica.

## 6. Rodada e documentação

- [x] 6.1 Rodada completa do braço local sob `run_id` novo, nos dois tipos de prompt, e conferência de que o manifesto traz digest, quantização, `num_ctx`, semente e a classificação de custo zero por execução local.
- [x] 6.2 Rodar `src/metricas.py` sobre o CSV do braço local e confirmar que Precisão/Recall/F1/MCC/TRA/TFN saem sem tratamento especial; anotar a taxa de `ERROR` do braço, que é resultado a reportar e não defeito a corrigir.
- [x] 6.3 Atualizar `docs/PIPELINE.md` com a seção do provedor local: instalação do Ollama, `ollama pull`, escolha de modelo por VRAM (7B e 9B cabem nos 8 GB; 14B e 16B rodam com offload), variáveis `OLLAMA_BASE_URL`/`OLLAMA_NUM_CTX`/`OLLAMA_TIMEOUT`, e a advertência sobre truncamento silencioso de contexto.
- [x] 6.4 Atualizar `README.md` com o exemplo de `--modelo ollama:<tag>` e as variáveis de ambiente novas; e `docs/SCRIPTS.md` se 5.3 tiver criado um script.
- [x] 6.5 Rodar a suíte completa (`python -m pytest tests/ -q`) e `openspec validate provedor-ollama-local --strict`.
- [x] 6.6 Commitar em branch própria, com mensagem em português dizendo que a mudança é aditiva: nenhum resultado publicado é invalidado e o comportamento de `--matriz` não muda. A mensagem cita o modelo, a quantização e o `num_ctx` calibrado em 5.4, para que o commit sozinho identifique a configuração do braço local. Verificar: `git status --short` sem nada pendente sob `src/`, `run_pipeline.py`, `tests/`, `docs/` e `README.md`; `git show --stat HEAD` sem nenhum arquivo sob `results/`, `cache/`, `data/` ou `legacy/` (os CSVs da rodada e o manifesto são saída de execução, não versionados por esta mudança).
