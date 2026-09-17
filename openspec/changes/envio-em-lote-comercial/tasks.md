## 1. Verificar as premissas antes de desenhar em cima delas

- [ ] 1.1 Confirmar, na documentação do fornecedor, o que o `custom_id` aceita
      de tamanho máximo e de alfabeto. Verificar: o limite está registrado com
      endereço e data, e uma chave real do projeto (`TPA:prest:CWE-89:…|
      gemini-2.5-flash-lite|especialista`) foi medida contra ele. Se não couber,
      **parar** e registrar a queda para tabela de mapeamento antes de seguir —
      é a premissa de D1.
- [ ] 1.2 Confirmar o limite de enfileiramento do tier em uso e o tamanho máximo
      de lote. Verificar: os valores estão em lugar único no código, vindos do
      provedor, e o cálculo de partição da rodada de 3.199.085 tokens de entrada
      está demonstrado.
- [ ] 1.3 Registrar o formato exato de submissão e de recuperação do fornecedor
      escolhido em D6. Verificar: um exemplo mínimo de requisição e de resposta
      está no código como docstring ou fixture, não só na cabeça de quem
      implementou.

## 2. O protocolo e os desfechos

- [ ] 2.1 Definir o protocolo `ProvedorLote` com `submeter` e `recuperar`.
      Verificar: `ProvedorLLM` e `ProvedorHTTP.avaliar` não foram alterados, e
      os testes existentes dos provedores síncronos passam sem edição.
- [ ] 2.2 Acrescentar o desfecho `EXPIRADO`, distinto de `ERROR`. Verificar: há
      teste que prova que uma requisição expirada não vira `ERROR` nem `FP`, e
      que seu custo não é somado quando o fornecedor não cobra.
- [ ] 2.3 Garantir a paridade de validação entre os modos. Verificar: existe
      teste que passa a **mesma** resposta bruta pelos dois caminhos e compara
      `RespostaLLM` inteira — veredito, tokens e custo.
- [ ] 2.4 Recusar cedo o modo de lote para provedor que não o implementa.
      Verificar: o erro nomeia o provedor e acontece antes de qualquer montagem
      de prompt ou chamada de Fase 1; há teste para o caso do `ollama`.

## 3. Correlação e retomada

- [ ] 3.1 Implementar o `custom_id` como a tripla `(ID_Caso, Modelo_LLM,
      Tipo_Prompt)`. Verificar: há teste que embaralha a ordem das respostas e
      prova que cada veredito cai na linha certa.
- [ ] 3.2 Tratar resposta órfã — chave que não consta da submissão. Verificar:
      nada é gravado para ela e a anomalia aparece em log; há teste.
- [ ] 3.3 Persistir `results/<run_id>/lote.json` **antes** da submissão.
      Verificar: há teste que prova a ordem (o arquivo existe no momento em que
      a submissão é chamada), e não apenas que o arquivo é criado.
- [ ] 3.4 Recuperar lote pendente na entrada da execução, sem ressubmeter.
      Verificar: matar o processo entre submissão e recuperação e rodar de novo
      recupera os resultados; o teste simula isso sem tocar a rede.
- [ ] 3.5 Particionar por orçamento de tokens. Verificar: a união das partições
      é exatamente o conjunto de requisições que o modo síncrono faria, sem
      repetição nem omissão — provado por teste sobre a população real.

## 4. O eixo no runner

- [ ] 4.1 Acrescentar `--modo-envio sincrono|lote` ao `run_pipeline.py`, com
      padrão `sincrono`. Verificar: uma rodada sem a flag produz CSV idêntico ao
      de antes desta change, comparado byte a byte num caso pequeno.
- [ ] 4.2 Impedir modos de envio diferentes entre braços da mesma rodada.
      Verificar: a execução é recusada antes de qualquer chamada, com teste.
- [ ] 4.3 Registrar modo de envio, fornecedor e identificador de cada lote no
      manifesto. Verificar: o manifesto de uma rodada em lote traz os três, e o
      de uma rodada síncrona traz `sincrono` sem campos vazios de lote.
- [ ] 4.4 No modo de coleta, acumular os prompts em vez de chamar. Verificar: o
      LLM continua sendo filtro puro do Semgrep no modo `filtro` — nenhum caso
      `NAO_DETECTADO` entra no lote.

## 5. Validação barata da esteira

- [ ] 5.1 Executar um lote de ~10 casos em `gemini-2.5-flash-lite`. Verificar: o
      custo real observado está registrado e é da ordem de R$ 0,01; os 10 casos
      voltaram com veredito gravado na linha certa.
- [ ] 5.2 Exercitar o caminho de erro no mesmo lote pequeno. Verificar: ao menos
      uma requisição inválida de propósito produz `ERROR` — e não `FP` — sem
      derrubar o restante do lote.
- [ ] 5.3 Exercitar a retomada com o lote real. Verificar: interromper e
      reexecutar recupera os resultados **sem** novo gasto, comprovado pelo
      custo total registrado.

## 6. Documentação e guardas

- [ ] 6.1 Atualizar `docs/PIPELINE.md` com o eixo do modo de envio. Verificar: a
      descrição diz que o padrão é síncrono e que o modo não varia dentro de uma
      rodada.
- [ ] 6.2 Atualizar `docs/SCRIPTS.md` com a flag e com o arquivo `lote.json`.
      Verificar: um leitor que não acompanhou esta change consegue submeter e
      retomar um lote lendo só o documento.
- [ ] 6.3 Confirmar que nenhuma rodada existente foi invalidada. Verificar:
      nenhum CSV em `results/` foi alterado, e nenhum número de
      `docs/ANALISE-RODADA-*.md` muda.
- [ ] 6.4 Confirmar que nenhum arquivo `.tex` foi tocado. Verificar:
      `git status --porcelain` não lista nenhum `.tex`.
