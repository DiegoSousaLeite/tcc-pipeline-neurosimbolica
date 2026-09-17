## 1. Base de cálculo — antes de olhar preço de fornecedor

- [ ] 1.1 Confirmar as contagens de tokens nas rodadas em disco e registrar de
      qual rodada saem. Verificar: os totais de `Tokens_Entrada` e
      `Tokens_Saida` batem com 3.198.141 / 315.469 da Rodada 4, e o documento
      nomeia a rodada.
- [ ] 1.2 Registrar as escalas de cálculo: uma rodada de dois braços, a matriz
      completa, e uma amostra estratificada de ~300 casos. Verificar: as três
      contagens de chamadas estão no documento, derivadas dos CSVs e não
      estimadas.
- [ ] 1.3 Ler `src/provedores/` e escrever o contrato que um provedor precisa
      cumprir — método, retorno, tokens, custo, tratamento de estouro de janela e
      de geração interrompida. Verificar: o contrato cabe em meia página e cita
      os arquivos.

## 2. Levantamento dos candidatos

- [ ] 2.1 Listar os modelos candidatos das três faixas (barata, média, topo),
      **verificando na página de preços de cada fornecedor** quais existem hoje.
      Verificar: cada candidato tem fornecedor, identificador e a data em que foi
      confirmado que existe.
- [ ] 2.2 Registrar preço de entrada e de saída por milhão de tokens, com
      endereço consultado e data. Verificar: nenhuma linha tem preço sem fonte;
      as que não puderam ser confirmadas estão marcadas como **não verificadas**,
      sem valor inventado no lugar.
- [ ] 2.3 Registrar a janela de contexto de cada candidato. Verificar: a tabela
      diz se a janela comporta os prompts desta pipeline — 26 das 33 falhas da
      Rodada 4 foram estouro de janela em 8.192 tokens, com prompts de até
      ~27.400.
- [ ] 2.4 Registrar limite de requisições no nível de acesso considerado, e se
      há nível gratuito utilizável. Verificar: o tier grátis do Gemini (20
      req/dia) aparece como exemplo de por que isso importa mais que o preço.

## 3. Custo real, nas escalas que importam

- [ ] 3.1 Calcular o custo de cada candidato nas três escalas de `1.2`, com os
      tokens de `1.1`. Verificar: a tabela traz US$ por rodada de dois braços,
      por matriz completa e por amostra de ~300.
- [ ] 3.2 Traduzir o limite de taxa em tempo de parede estimado por rodada,
      respeitando o intervalo mínimo entre chamadas da pipeline. Verificar: a
      coluna de parede existe, e a rodada local de 3.171 chamadas em 4h50 está
      como referência de comparação.
- [ ] 3.3 Classificar o custo de integração de cada candidato contra o contrato
      de `1.3`: **configuração** (fala o protocolo de um provedor já
      implementado), **provedor novo** (precisa ser escrito), ou
      **incompatível**. Verificar: cada candidato tem uma das três marcas e uma
      frase justificando.

## 4. A recomendação

- [ ] 4.1 Declarar o critério de escolha **antes** de aplicá-lo. Verificar: o
      critério está escrito no documento acima da tabela de decisão, e não
      deduzido dela depois.
- [ ] 4.2 Recomendar um modelo. Verificar: há exatamente um recomendado, e a
      justificativa liga o critério de `4.1` aos números de `3.`.
- [ ] 4.3 Registrar cada alternativa recusada **com o motivo**. Verificar:
      nenhum candidato da tabela fica sem destino — ou é o recomendado, ou tem
      motivo de recusa escrito.
- [ ] 4.4 Declarar se o modelo recomendado é capaz o bastante para **falsificar**
      a conclusão atual, ou se apenas a confirmaria. Verificar: a frase existe e
      é explícita; se for da mesma banda dos modelos locais já medidos, o
      documento diz isso em vez de omitir.
- [ ] 4.5 Responder as questões em aberto do `design.md` que o levantamento
      permitir fechar — restrição institucional de fornecedor, população inteira
      vs amostra, e qual enquadramento de prompt o braço comercial usaria.
      Verificar: cada uma tem resposta ou fica registrada como ainda aberta, com
      o que falta para fechá-la.

## 5. Entrega e registro

- [ ] 5.1 Escrever `docs/ESCOLHA-MODELO-COMERCIAL.md` com tudo acima, no formato
      das análises do projeto. Verificar: o documento existe e um leitor que não
      acompanhou esta conversa consegue refazer o cálculo.
- [ ] 5.2 Registrar em `docs/MAPA-TCC-O-QUE-REESCREVER.md` que **a matriz
      comercial nunca foi executada**, com os números reais: 17 vereditos
      comerciais mais 5 `API_ERROR`, contra as rodadas locais completas.
      Verificar: a entrada existe e nomeia as pastas onde isso pode ser
      conferido.
- [ ] 5.3 Registrar no mesmo lugar que a `matriz-experimental` descreve o par
      comercial como matriz de referência, o que induz a leitura de que foi
      usada. Verificar: a frase está lá, porque é ela que a banca vai cobrar.

## 6. Guardas de escopo

- [ ] 6.1 Confirmar que nenhuma chamada de API foi feita. Verificar: nenhuma
      cota consumida, nenhum `results/` novo criado por esta change.
- [ ] 6.2 Confirmar que `src/provedores/` e a tabela de preços do projeto estão
      inalteradas. Verificar: `git diff --name-only` não lista nada sob `src/`.
- [ ] 6.3 Confirmar que nenhum arquivo `.tex` foi tocado. Verificar:
      `git status --porcelain` não lista nenhum `.tex`.
