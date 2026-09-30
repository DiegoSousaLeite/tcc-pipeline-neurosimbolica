## 1. Verificar as premissas antes de desenhar em cima delas

- [x] 1.1 Confirmar, na documentação do fornecedor, o que o `custom_id` aceita
      de tamanho máximo e de alfabeto. Verificar: o limite está registrado com
      endereço e data, e uma chave real do projeto (`TPA:prest:CWE-89:…|
      gemini-2.5-flash-lite|especialista`) foi medida contra ele. Se não couber,
      **parar** e registrar a queda para tabela de mapeamento antes de seguir —
      é a premissa de D1.
- [x] 1.2 Confirmar o limite de enfileiramento do tier em uso e o tamanho máximo
      de lote. Verificar: os valores estão em lugar único no código, vindos do
      provedor, e o cálculo de partição da rodada de 3.199.085 tokens de entrada
      está demonstrado.
- [x] 1.3 Registrar o formato exato de submissão e de recuperação do fornecedor
      escolhido em D6. Verificar: um exemplo mínimo de requisição e de resposta
      está no código como docstring ou fixture, não só na cabeça de quem
      implementou.

## 2. O protocolo e os desfechos

- [x] 2.1 Definir o protocolo `ProvedorLote` com `submeter` e `recuperar`.
      Verificar: `ProvedorLLM` e `ProvedorHTTP.avaliar` não foram alterados, e
      os testes existentes dos provedores síncronos passam sem edição.
- [x] 2.2 Acrescentar o desfecho `EXPIRADO`, distinto de `ERROR`. Verificar: há
      teste que prova que uma requisição expirada não vira `ERROR` nem `FP`, e
      que seu custo não é somado quando o fornecedor não cobra.
- [x] 2.3 Garantir a paridade de validação entre os modos. Verificar: existe
      teste que passa a **mesma** resposta bruta pelos dois caminhos e compara
      `RespostaLLM` inteira — veredito, tokens e custo.
- [x] 2.4 Recusar cedo o modo de lote para provedor que não o implementa.
      Verificar: o erro nomeia o provedor e acontece antes de qualquer montagem
      de prompt ou chamada de Fase 1; há teste para o caso do `ollama`.

## 3. Correlação e retomada

- [x] 3.1 Implementar o `custom_id` como a tripla `(ID_Caso, Modelo_LLM,
      Tipo_Prompt)`. Verificar: há teste que embaralha a ordem das respostas e
      prova que cada veredito cai na linha certa.
- [x] 3.2 Tratar resposta órfã — chave que não consta da submissão. Verificar:
      nada é gravado para ela e a anomalia aparece em log; há teste.
- [x] 3.3 Persistir `results/<run_id>/lote.json` **antes** da submissão.
      Verificar: há teste que prova a ordem (o arquivo existe no momento em que
      a submissão é chamada), e não apenas que o arquivo é criado.
- [x] 3.4 Recuperar lote pendente na entrada da execução, sem ressubmeter.
      Verificar: matar o processo entre submissão e recuperação e rodar de novo
      recupera os resultados; o teste simula isso sem tocar a rede.
- [x] 3.5 Particionar por orçamento de tokens. Verificar: a união das partições
      é exatamente o conjunto de requisições que o modo síncrono faria, sem
      repetição nem omissão — provado por teste sobre a população real.

## 4. O eixo no runner

- [x] 4.1 Acrescentar `--modo-envio sincrono|lote` ao `run_pipeline.py`, com
      padrão `sincrono`. Verificar: uma rodada sem a flag produz CSV idêntico ao
      de antes desta change, comparado byte a byte num caso pequeno.
- [x] 4.2 Impedir modos de envio diferentes entre braços da mesma rodada.
      Verificar: a execução é recusada antes de qualquer chamada, com teste.
- [x] 4.3 Registrar modo de envio, fornecedor e identificador de cada lote no
      manifesto. Verificar: o manifesto de uma rodada em lote traz os três, e o
      de uma rodada síncrona traz `sincrono` sem campos vazios de lote.
- [x] 4.4 No modo de coleta, acumular os prompts em vez de chamar. Verificar: o
      LLM continua sendo filtro puro do Semgrep no modo `filtro` — nenhum caso
      `NAO_DETECTADO` entra no lote.

## 5. Validação barata da esteira

- [x] 5.1 Executar um lote de ~10 casos em `gemini-2.5-flash-lite`. Verificar: o
      custo real observado está registrado e é da ordem de R$ 0,01; os 10 casos
      voltaram com veredito gravado na linha certa.
- [x] 5.2 Exercitar o caminho de erro no mesmo lote pequeno. Verificar: ao menos
      uma requisição inválida de propósito produz `ERROR` — e não `FP` — sem
      derrubar o restante do lote.
- [x] 5.3 Exercitar a retomada com o lote real. Verificar: interromper e
      reexecutar recupera os resultados **sem** novo gasto, comprovado pelo
      custo total registrado.

Ferramenta: `scripts/validar_lote.py` (10 casos DETECTADO do cache, braços
baseline e especialista, uma requisição inválida de propósito; o Semgrep não
roda). Primeira execução com `--parar-apos-submissao`, segunda com o mesmo
`--run-id`.

Registro 2026-09-30: **bloqueado pela conta.** A submissão foi recusada com
`HTTP 400 FAILED_PRECONDITION` ("Precondition check failed."), e o exemplo
mínimo copiado da documentação do fornecedor recebeu a mesma recusa, nos dois
modelos (`2.5-flash-lite` e `2.5-flash`), enquanto `countTokens` com a mesma
chave respondeu 200. Conclusão: o projeto da chave está no tier grátis, que não
tem lote; o formato não é a causa. Nenhum lote foi criado, nada foi cobrado. O
registro local (`results/validacao-lote-20260930/`, partição em `SUBMETENDO`,
sem lote no fornecedor e CSVs só com cabeçalho) foi removido no mesmo dia,
quando os autores trocaram a validação para o `gpt-6-luna` (change
`provedor-lote-openai`): ele bloquearia `--modo-envio lote` sem `--run-id`.

**Decisão dos autores (2026-09-30): o Gemini foi descartado; a validação é a do
`gpt-6-luna`.** O modelo nomeado em 5.1 era meio, não fim — D5 existe para
separar "a esteira funciona" de "o modelo responde", e o Gemini tinha sido
escolhido só por ser o mais barato de validar (D6). A validação com o Luna
exercita exatamente as mesmas verificações e fecha 5.1–5.3:

- 5.1: lote `batch_6abd8f5cb06881909553d5f4e8eb40f2`, 10 casos × 2 braços, 20/20
  com veredito na linha certa (cada justificativa trata do código do próprio
  caso); custo faturado US$ 0,0012 ≈ R$ 0,006.
- 5.2: a requisição inválida de propósito voltou `"TALVEZ"` e saiu `API_ERROR`,
  nunca `FP`; as outras 19 com veredito válido.
- 5.3: processo morto com o lote pendente; a retomada recuperou tudo sem nova
  submissão (um único lote com o rótulo no fornecedor).

Registro completo na tarefa 3.1 de `provedor-lote-openai`. O provedor de lote
do Gemini continua no código, testado contra dublê, mas **não foi validado
contra o fornecedor real**.

## 6. Documentação e guardas

- [x] 6.1 Atualizar `docs/PIPELINE.md` com o eixo do modo de envio. Verificar: a
      descrição diz que o padrão é síncrono e que o modo não varia dentro de uma
      rodada.
- [x] 6.2 Atualizar `docs/SCRIPTS.md` com a flag e com o arquivo `lote.json`.
      Verificar: um leitor que não acompanhou esta change consegue submeter e
      retomar um lote lendo só o documento.
- [x] 6.3 Confirmar que nenhuma rodada existente foi invalidada. Verificar:
      nenhum CSV em `results/` foi alterado, e nenhum número de
      `docs/ANALISE-RODADA-*.md` muda.
- [x] 6.4 Confirmar que nenhum arquivo `.tex` foi tocado **por esta change**.
      Verificar: `git status --porcelain` não lista nenhum `.tex`.
      A justificativa mudou em 17/09/2026 e o registro importa: a regra antiga era
      não mexer na monografia antes de fechar o experimento, porque não havia
      histórico para desfazer um erro. A monografia passou a ser versionada, então
      a guarda hoje vale por outro motivo — esta change é infraestrutura e não
      produz número algum para reportar. Não é mais proibição geral; é escopo.

- [x] 6.5 Fazer `src/metricas.py` mostrar o custo faturado em rodada de lote.
      O CSV guarda o preço de tabela (paridade entre os modos, spec
      `envio-em-lote`), e a soma dele — que é o custo que `metricas.py`
      reportava — daria o dobro do cobrado. Verificar: numa rodada em lote a
      tabela dos braços e o `.tex` trazem "Custo tabela USD" e "Custo faturado
      USD", com aviso; numa síncrona, a saída não muda. (Acrescentada em
      2026-09-28, depois de a implementação expor a divergência.)

## 7. Encerramento — abrir a sucessora

- [x] 7.1 Criar a change `rodada-comercial` **antes de arquivar esta**, ainda que
      ela fique parada aguardando decisão de orçamento. Verificar:
      `openspec/changes/rodada-comercial/` existe e `openspec validate
      rodada-comercial --strict` passa.
      O andaime existe para uma parede; sem a sucessora registrada, a capacidade
      construída aqui fica sem consumidor e o esforço se perde por esquecimento.
- [x] 7.2 Registrar na sucessora, como tarefas dela e não desta, os dois pontos
      de `editaveis/resultados.tex` que só ela pode fechar: as linhas dos modelos
      de fronteira na Tabela `tab:modelos`, e o item "Escopo de modelos" da seção
      de limitações. Verificar: as duas tarefas constam do `tasks.md` da
      sucessora, nomeando o arquivo e o rótulo da tabela.
- [x] 7.3 Registrar na sucessora a ordem de prioridade entre os braços: **o braço
      de filtro primeiro**, porque é onde moram Q1, Q2 e Q3 e é a metade mais
      barata (~1.654 chamadas contra ~3.200); o braço de triagem é extensão
      opcional. Verificar: a decisão e a justificativa constam do `design.md` da
      sucessora.
- [x] 7.4 Verificar que a chave da OpenAI está disponível, ou registrar na
      sucessora que a matriz comercial fica restrita ao Gemini. Verificar: o
      `.env` traz `OPENAI_API_KEY`, ou o `design.md` da sucessora declara que a
      conclusão passa a ser "três modelos, um comercial" em vez de "quatro, dois
      comerciais".
