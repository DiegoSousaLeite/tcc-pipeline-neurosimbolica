## Why

Os dois braços de modelo hoje disponíveis (Gemini e GPT) são serviços pagos de terceiros, e isso impõe duas restrições ao experimento: a cota do tier grátis do Gemini é de 20 req/dia por modelo — inviável para uma população de centenas de casos, obrigando a habilitar billing só para gerar os números finais — e todo caso triado envia código-fonte de terceiros para uma API externa. Um provedor local via Ollama remove as duas: custo marginal zero, sem cota, e o código nunca sai da máquina.

A pergunta de pesquisa que isso atende é a de **viabilidade prática da abordagem neuro-simbólica fora de um provedor comercial**: um modelo aberto de 7B rodando em hardware de desktop consegue filtrar falsos positivos do Semgrep com qualidade comparável à dos modelos comerciais? Um resultado positivo fortalece muito a tese, porque uma equipe que não pode enviar código proprietário para fora consegue rodar a pipeline inteira on-premise. Um resultado negativo também é resultado publicável: quantifica o custo, em qualidade de triagem, de manter o código dentro de casa. É trabalho de **Parte 2** — pertence ao eixo "modelo" da matriz experimental, ao lado do braço GPT.

## What Changes

- Novo provedor `ProvedorOllama`, falando com a API local do Ollama (`/api/chat`), atrás da mesma interface `ProvedorLLM` que Gemini e OpenAI já usam. As Fases 1/2, 3/4 e a auditoria não mudam.
- O contrato de autenticação passa a admitir provedores **sem chave de API**. Hoje `ProvedorHTTP.avaliar` devolve `ERROR` sem tocar a rede quando `api_key` é vazia, o que é a proteção correta para as APIs comerciais mas bloquearia qualquer provedor local.
- A janela de contexto passa a ser **explícita e verificada**. O padrão do Ollama (`num_ctx = 4096`) truncaria o prompt em silêncio nos casos de arquivo grande, e um prompt truncado produz um veredito sobre código que o modelo não viu por inteiro — contaminação silenciosa dos resultados, o pior modo de falha possível para o experimento. O provedor fixa `num_ctx` e trata estouro de contexto como `ERROR` explícito, nunca como veredito.
- Custo zero passa a ser **declarado**, e não inferido da ausência de preço. Hoje `precos.py` devolve `0.0` para modelo fora da tabela e o lista no manifesto como "sem preço"; para um modelo local o custo é genuinamente zero, e o manifesto precisa dizer isso em vez de dar a entender que faltou consultar o preço.
- A matriz experimental deixa de ser fixada em 2x2 e passa a ser o produto (modelos selecionados x tipos de prompt), com o par comercial preservado como o padrão de `--matriz`. Não há promoção automática do braço local para dentro de `--matriz`: quem quiser rodá-lo o nomeia.
- **BREAKING** (interno, sem efeito nos CSVs já gravados): o nome do CSV de braço deixa de ser o nome cru do modelo. `Braco.rotulo` produz hoje `qwen2.5-coder:7b__baseline.csv`, e dois-pontos é caractere inválido em nome de arquivo no Windows — a rodada quebraria ao abrir o CSV. O rótulo passa por saneamento, e o nome cru do modelo continua registrado dentro do CSV e no manifesto.
- O manifesto da rodada passa a registrar a identidade do modelo local: versão do Ollama, digest do modelo, quantização e `num_ctx` efetivo. Sem isso, "qwen2.5-coder:7b" não identifica nada de forma reprodutível — a tag é mutável no registry do Ollama.
- Documentação: `docs/PIPELINE.md` ganha a seção do provedor local (instalação, `ollama pull`, escolha de modelo por VRAM) e o `README.md` a variável `OLLAMA_BASE_URL`.

## Capabilities

### New Capabilities
- `provedor-local-ollama`: execução de braços da matriz contra um servidor Ollama na máquina do pesquisador — descoberta e validação do modelo, janela de contexto explícita com falha visível em estouro, determinismo (temperatura zero e seed fixa), custo zero declarado, e registro da identidade do modelo local no manifesto para reprodutibilidade.

### Modified Capabilities
- `provedores-llm`: a autenticação por cabeçalho passa a valer apenas para provedores que exigem credencial, e provedor local sem chave deixa de ser erro; a contabilidade de custo distingue "custo zero por execução local" de "modelo ausente da tabela de preços"; o despacho por nome de modelo passa a resolver também os modelos locais.
- `matriz-experimental`: a matriz deixa de ser definida como 2x2 sobre (Gemini, GPT) e passa a ser o produto dos modelos selecionados pelos tipos de prompt, mantendo o par comercial como padrão; o rótulo de braço usado em nome de arquivo passa a ser saneado sem perder o nome do modelo nos dados.

## Impact

- **Código**: `src/provedores/ollama.py` (novo); `src/provedores/base.py` (chave opcional, timeout por provedor); `src/provedores/__init__.py` (fábrica e resolução de família); `src/provedores/precos.py` (custo zero declarado); `run_pipeline.py` (`Braco.rotulo` saneado, `definir_bracos`, manifesto); `tests/test_provedores.py` e `tests/test_matriz.py`.
- **Dependências**: nenhuma nova em Python — o Ollama expõe HTTP e `requests` já é dependência. Passa a existir uma dependência **externa opcional**: o binário do Ollama e o modelo baixado. A pipeline sem `--modelo` local continua funcionando em máquina sem Ollama instalado.
- **Hardware do pesquisador** (Ryzen 5 5600, 32 GB RAM, Radeon RX 7600 8 GB): `qwen2.5-coder:7b` e `gemma2:9b` em quantização Q4 cabem na VRAM; `qwen2.5-coder:14b` e `deepseek-coder-v2:16b` não cabem e rodam com offload parcial para CPU, muito mais lentos. O desenho não privilegia nenhum: o modelo é parâmetro, e a única exigência é que o provedor não degrade em silêncio quando o modelo não couber. O design detalha a estimativa de tempo por braço.
- **Resultados já gerados**: nenhum é invalidado. Os braços comerciais não mudam de comportamento, e uma rodada nova grava sob `run_id` próprio. O único ponto de atenção é que um braço local **não é comparável** aos comerciais em nada além do veredito — latência e custo saem de regimes diferentes —, e o texto da monografia precisa dizer isso ao apresentar a tabela.

## Não-objetivos

- **Não** substituir os braços Gemini e GPT. O braço local é um terceiro ponto do eixo "modelo", não um substituto; os números comerciais continuam sendo a referência do capítulo de resultados.
- **Não** fazer fine-tuning, LoRA ou qualquer adaptação de pesos. O experimento compara prompts e modelos prontos.
- **Não** varrer quantizações (Q4 vs Q5 vs Q8) nem tratar throughput de inferência como contribuição de pesquisa. Tempo de execução entra como nota de viabilidade, não como resultado medido com rigor — a máquina é de uso geral e não há controle de carga.
- **Não** rodar os quatro modelos locais citados. O escopo desta mudança é fazer **um** funcionar de ponta a ponta (`qwen2.5-coder:7b`) e deixar os outros a um `--modelo` de distância, sem código novo.
- **Não** empacotar, conteinerizar ou automatizar a instalação do Ollama. O pesquisador instala e sobe o serviço; a pipeline só o consome e falha com mensagem clara se ele não estiver de pé.
- **Não** introduzir concorrência entre braços. A GPU tem 8 GB: dois modelos em paralelo se atrapalhariam, e execução sequencial é o que mantém a comparação limpa.
