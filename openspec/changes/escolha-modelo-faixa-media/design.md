## Context

O que existe de dado comercial neste projeto, medido em 2026-09-16:

| pasta | linhas | vereditos válidos |
|---|---|---|
| `results/sizing-fp` (gemini) | 965 | **0** — rodada `--sem-llm` |
| `results/cobertura-tp-dataset` (gemini) | 57 | **0** — idem |
| `results/piloto-gemini` | 70 | **17**, mais 5 `API_ERROR` |
| `results/20260729…` (gpt-4o-mini) | 12 | **0** |

**Dezessete.** Contra 2.328 casos × 2 braços × 3 rodadas de modelo local só no
braço de triagem.

E os 17 são ruins: no baseline, 4 de 5 vulneráveis viraram falso negativo e 3 de
5 seguros viraram falso positivo; no especialista, 2 de 2 vulneráveis perdidos.
Com n=17 isso é anedota — mas certamente não é evidência de superioridade
comercial.

Os tokens desta pipeline, medidos na Rodada 4 (3.171 chamadas):

| | total | média por chamada |
|---|---|---|
| entrada | 3.198.141 | 1.009 |
| saída | 315.469 | 99 |

**Arquivos tocados:** `docs/ESCOLHA-MODELO-COMERCIAL.md` (novo) e
`docs/MAPA-TCC-O-QUE-REESCREVER.md`. Nenhum arquivo de código.

## Goals / Non-Goals

**Goals:**

- Produzir uma escolha de modelo defensável, com preço de fonte primária e custo
  calculado sobre tokens medidos.
- Tornar visível o custo de integração e o limite de taxa, que preço de token
  esconde.
- Declarar, de uma vez, que a matriz comercial nunca rodou.

**Non-Goals:**

- Implementar provedor.
- Alterar a tabela de preços do projeto.
- Executar rodada ou gastar cota.
- Decidir se a rodada vai acontecer.

## Decisions

### D1 — Preço de fonte primária, sempre, com data

**Decisão:** nenhum preço entra no documento sem endereço consultado e data.
Preço que não se confirmou entra marcado como não verificado.

**Por quê:** a tabela do projeto tem `data_consulta: 2026-07-29` e continuou
alimentando cálculo em setembro sem que nada sinalizasse a idade. Pior: **quem
faz o levantamento tem conhecimento com data de corte e não sabe o que mudou
depois dela.** Um preço lembrado é um preço de antigamente apresentado como
atual. A regra existe para que o documento não invente precisão.

**Consequência aceita:** se um preço não puder ser verificado, a linha fica
incompleta. Linha incompleta é informação; número plausível inventado é dano.

### D2 — Custo sobre tokens medidos, nunca estimados

**Decisão:** usar 3.198.141 / 315.469 das rodadas reais.

**Por quê:** a primeira estimativa deste projeto usou 817 tokens de entrada e o
real foi 1.009 — **23 % a mais**, porque as funções longas dos candidatos
injetados não estavam na conta. O custo divulgado saiu abaixo do real. Os
números medidos existem; usar estimativa quando há medição é escolher errar.

### D3 — Custo de integração entra na comparação

**Decisão:** para cada modelo, registrar o que ele exige de `src/provedores/`.

**Por quê:** a camada de provedores deste projeto tem contrato definido —
`avaliar(prompt) -> RespostaLLM` com tokens, custo e tratamento de estouro de
janela. Um modelo que fale o protocolo de um provedor já implementado é
configuração; um que exija provedor novo é código, teste e uma nova superfície
de falha. Comparar só por preço de token faria a segunda opção parecer barata.

### D4 — Limite de taxa traduzido em parede

**Decisão:** registrar o limite e converter em horas estimadas para uma rodada,
com o intervalo mínimo entre chamadas que a pipeline impõe.

**Por quê:** neste projeto o dinheiro nunca foi o gargalo — a cota foi. O tier
grátis do Gemini permite 20 requisições por dia, o que torna 3.210 chamadas
impossíveis por um motivo que não é econômico. A rodada local de 3.171 chamadas
levou 4h50; um modelo comercial com throttle apertado pode ser pior que isso, e
a tabela precisa mostrar.

### D5 — O documento escolhe, e registra as recusas

**Decisão:** terminar em uma recomendação, com critério declarado e cada
alternativa recusada com motivo.

**Por quê:** levantamento que lista e não escolhe devolve a decisão intacta. E
este projeto já tem histórico de decisão tomada e depois revogada — a 5c.1, do
enquadramento do prompt. O que tornou a revogação honesta foi o motivo estar
escrito: deu para mostrar *por que* a decisão anterior era razoável com os dados
de então. Recusa sem motivo registrado não permite isso.

### D6 — A recomendação declara se o modelo pode falsificar a conclusão

**Decisão:** dizer explicitamente se o modelo escolhido é capaz o bastante para
derrubar o resultado atual, ou se apenas o confirmaria.

**Por quê:** é a lição da Rodada 6. Gastou-se um dia de GPU para descobrir que
`gemma2:9b` é pior que `qwen2.5-coder:7b` — resultado legítimo, mas que não
moveu o escopo da conclusão, porque os dois estão na mesma banda. Rodar
`gemini-2.5-flash-lite` e `gpt-4o-mini`, que são a faixa barata de cada
fornecedor, corre o mesmo risco: US$ 0,45 por uma confirmação que a banca vai
descartar com *"mas você testou um modelo bom?"*.

O critério que importa não é "qual o mais barato", é **"qual consegue me provar
errado"**.

### D7 — Separar a escolha da execução

**Decisão:** esta change entrega documento; provedor e rodada são change própria.

**Por quê:** é o padrão que funcionou no braço de triagem — a change entregou a
capacidade e a rodada foi decisão separada, deliberada, tomada com o custo já
medido na mão. Juntar as duas faria a investigação carregar um compromisso de
gasto que ela não deveria tomar sozinha.

## Risks / Trade-offs

**[O levantamento envelhecer rápido]** → Preço e catálogo de modelo mudam em
semanas. Mitigação: data de consulta em cada linha, e o documento declara que é
um retrato, não uma referência permanente. Quem for executar reconfere.

**[Escolher um modelo que o orçamento não cobre]** → A faixa média está na ordem
de US$ 14 por rodada de dois braços e a de topo em ~US$ 72, ambas calculadas
sobre os tokens medidos. Mitigação: apresentar as três faixas, e a recomendação
justificar a escolhida contra as outras duas.

**[Viés de quem escreve]** → Quem faz o levantamento tem conhecimento com data
de corte e pode preferir o que conhece. Mitigação: D1 força fonte primária, e o
critério de D6 é sobre poder de falsificação, não sobre familiaridade.

**[O documento virar justificativa de uma decisão já tomada]** → Risco real:
ele nasce depois de eu já ter dito que recomendo a faixa média. Mitigação: as
recusas registradas com motivo (D5) tornam a preferência auditável em vez de
implícita, e o critério de D6 é verificável por terceiros.

## Migration Plan

1. Levantar os modelos candidatos e verificar preço na fonte primária.
2. Calcular custo com os tokens medidos, nas escalas de uma rodada e da matriz.
3. Ler `src/provedores/` e classificar o custo de integração de cada candidato.
4. Levantar limite de taxa e converter em parede.
5. Escrever a recomendação com critério, recusas e poder de falsificação.
6. Registrar no mapa do LaTeX que a matriz comercial nunca rodou.

**Rollback:** o documento é aditivo. Descartá-lo não afeta nada.

## Open Questions

- **Existe restrição de fornecedor por parte da instituição?** Alguns programas
  restringem uso de API estrangeira ou exigem processamento em região
  específica. Se houver, corta candidatos antes do preço.
- **A rodada comercial seria sobre a população inteira ou uma amostra?** Uma
  amostra estratificada de ~300 casos custaria um décimo e provavelmente já
  responderia à pergunta de escopo. Vale dimensionar as duas.
- **O braço comercial usaria o enquadramento direto ou o original?** A Rodada 5
  mostrou que o enquadramento importa. Rodar o prompt antigo num modelo caro
  repetiria um artefato já conhecido — mas usar o novo quebra a comparabilidade
  com as Rodadas 1-3. Provavelmente os dois, o que dobra o custo.
