## Context

O que motiva esta change está medido, não suposto — os números saem de
`docs/ESCOLHA-MODELO-COMERCIAL.md` (change `escolha-modelo-faixa-media`,
consultas de 2026-09-17).

**O desconto, verificado nos três fornecedores:**

| | Google | Anthropic | OpenAI |
|---|---|---|---|
| desconto | 50 % | 50 % | 50 % |
| prazo | 24 h alvo | maioria < 1 h | 24 h |
| expiração | job em 48 h | lote em 24 h; expirada não é cobrada | 24 h |
| tamanho | 2 GB (JSONL) | 100.000 req / 256 MB | 50.000 req / 200 MB |
| retenção | 6 semanas | 29 dias | 30 dias |

Uma rodada de dois braços tem **3.172 chamadas** e cabe em um lote nos três.

**O que o modo de lote muda, em ordem de importância:**

1. **Vazão deixa de ser risco.** É o que matou o braço comercial deste trabalho:
   20 req/dia no tier grátis do Gemini transformam 3.172 chamadas em 159 dias.
   Em lote não há RPM a estourar — há enfileiramento, preenchido de uma vez.
2. **Parede.** 1 h 46 – 3 h 32 no laço sequencial contra "maioria em menos de
   1 hora" na Anthropic.
3. **A máquina fica livre.** Hoje Semgrep e `llama-server` disputam RAM.
4. **Preço.** Metade — e é o item menos importante da lista, porque a faixa
   inteira de decisão vai de R$ 1,15 a R$ 160 por rodada.

**O obstáculo:** o contrato de `src/provedores/base.py` é síncrono por
construção. `ProvedorHTTP.avaliar` faz throttle, POST, retry e validação numa
chamada só. Não existe onde encaixar "submeta 3.172 e volte depois".

**Arquivos tocados:** `run_pipeline.py`, `src/provedores/` (módulo novo),
`src/fase5_auditoria.py` (desfecho `EXPIRADO`), o manifesto, `docs/PIPELINE.md`
e `docs/SCRIPTS.md`.

## Goals / Non-Goals

**Goals:**

- Permitir executar uma rodada comercial em lote, selecionável por flag, sem
  alterar em nada o comportamento síncrono.
- Tornar impossível — não apenas improvável — gravar um veredito no caso errado.
- Permitir retomar um lote já submetido sem pagar de novo.
- Validar a esteira inteira, inclusive o caminho de erro, por ~R$ 0,01.

**Non-Goals:**

- Implementar provedor Anthropic ou qualquer fornecedor novo.
- Decidir qual modelo rodar, ou se a rodada comercial vai acontecer.
- Executar rodada comercial completa.
- Tornar o lote o padrão.
- Dar modo de lote ao provedor local.

## Decisions

### D1 — O identificador da requisição é a chave de checkpoint

**Decisão:** o `custom_id` de cada requisição do lote é
`f"{ID_Caso}|{Modelo_LLM}|{Tipo_Prompt}"` — a tripla que `matriz-experimental`
já exige do checkpoint.

**Por quê:** os fornecedores não garantem ordem de resposta, e a OpenAI declara
isso explicitamente. Correlacionar por posição gravaria veredito no caso errado
**em silêncio**, que é a falha que a própria spec da matriz chama de pior
possível. Com a chave composta como identificador, o erro deixa de ser
representável: uma resposta sem chave válida não tem linha onde ser escrita.

Não é só segurança — é economia de conceito. A chave de correlação e a chave de
retomada passam a ser a mesma coisa, então a lógica de "o que já foi feito" não
ganha um segundo vocabulário.

**Consequência aceita:** o `custom_id` fica longo e com separador. Se algum
fornecedor limitar caracteres ou tamanho, o mapeamento passa a exigir uma tabela
em disco — e aí o benefício estrutural se perde. Verificar isso é tarefa da
implementação, não suposição do desenho.

### D2 — Protocolo separado, e não sobrecarga do `avaliar`

**Decisão:** `ProvedorLote` é um protocolo à parte, com `submeter` e
`recuperar`. `ProvedorLLM.avaliar` não muda.

**Por quê:** os ciclos de vida são incompatíveis. A forma síncrona devolve
resposta na mesma chamada; a em lote devolve um identificador e exige consulta
depois. Espremer as duas na mesma assinatura obrigaria a síncrona a carregar
estado que ela não tem, ou a em lote a bloquear esperando — que é exatamente o
que ela existe para não fazer.

Também protege o que já funciona: seis rodadas locais passaram por
`ProvedorHTTP.avaliar`. Mexer nele para acomodar um caminho que ainda não rodou
nenhuma vez seria arriscar o que está provado pelo que não está.

### D3 — O identificador do lote vai para o disco antes da submissão

**Decisão:** gravar `results/<run_id>/lote.json` com o identificador **antes** de
a requisição de submissão partir, e consultá-lo na entrada de toda execução.

**Por quê:** lote submetido é lote pago. Se uma queda local obrigasse a
reenviar, o custo dobraria por um motivo que não tem nada a ver com o
experimento. Os fornecedores retêm resultados por 29 a 42 dias, então a janela é
folgada — o que falta é a informação estar em disco no instante certo, e não
depois.

Gravar *depois* da submissão tem uma janela em que o gasto existe e o registro
não. Gravar antes tem a janela oposta: um identificador que talvez não exista,
que é barato de tratar (consulta devolve "não encontrado" e a execução
ressubmete).

### D4 — `EXPIRADO` é desfecho próprio, não um `ERROR`

**Decisão:** requisição que não foi processada dentro da janela do lote é
registrada como `EXPIRADO`.

**Por quê:** `ERROR` significa "o modelo respondeu e a resposta não passou na
validação". `EXPIRADO` significa "o modelo nunca viu isso". Somar as duas
inflaria a taxa de erro do modelo com uma falha de esteira — e este trabalho já
teve de declarar que as 33 falhas da Rodada 4 eram enviesadas por tamanho de
função. Perder a distinção seria repetir o problema de propósito.

Há um segundo motivo, contábil: a Anthropic não cobra requisição expirada.

### D5 — A esteira é validada antes de qualquer decisão de modelo

**Decisão:** um lote de ~10 casos em `gemini-2.5-flash-lite` (custo ~R$ 0,01)
exercita submissão, correlação, retomada e o caminho de erro, antes de qualquer
rodada de verdade.

**Por quê:** "a esteira funciona" e "o modelo responde bem" são perguntas
diferentes, que falham por motivos diferentes e em momentos diferentes.
Misturá-las faz um bug de correlação parecer um modelo ruim. Por um centavo,
separa-se.

É a mesma lógica do portão da tarefa 5.5 do braço de triagem, que já funcionou
neste projeto: gastar pouco para decidir se vale gastar muito.

### D6 — O primeiro provedor de lote é o Gemini

**Decisão:** implementar a entrega em lote para o provedor que **já existe** —
`ProvedorGemini` —, e não para o modelo que a §4 de
`docs/ESCOLHA-MODELO-COMERCIAL.md` recomenda.

**Por quê:** separar as duas decisões. Esta change entrega a capacidade; qual
fornecedor roda a rodada comercial é escolha de quem executar, e depende de
billing que pode nem existir ainda. O Gemini já tem provedor síncrono, tem API
de lote, e é onde o lote de validação custa R$ 0,01.

**Consequência aceita:** se a rodada comercial for em outro fornecedor, será
preciso escrever mais um provedor de lote. É trabalho pequeno e conhecido — os
provedores síncronos deste projeto têm 52 e 57 linhas — e o protocolo de D2
existe justamente para que o segundo seja mais barato que o primeiro.

### D7 — Particionamento por orçamento de tokens, declarado pelo provedor

**Decisão:** o provedor declara seu limite de enfileiramento; o runner parte a
rodada em lotes que caibam nele e trata o conjunto como uma rodada só.

**Por quê:** não é hipótese. O Tier 1 do Gemini enfileira 3.000.000 de tokens e
uma rodada de dois braços tem 3.199.085 de entrada — **não cabe, por 6,6 %**.
Um corte natural é por braço (1.196.812 e 2.002.273, ambos abaixo do teto), mas
amarrar a partição ao braço seria coincidência virando regra; o critério é o
orçamento.

### D8 — Submeter e recuperar são o mesmo comando, e a retomada faz o trabalho

**Decisão:** `--modo-envio lote` submete e acompanha até terminar. Se o processo
for interrompido, **rodar o mesmo comando de novo recupera** o lote pendente via
D3, sem ressubmeter.

**Por quê:** dois comandos separados (submeter / recuperar) seriam mais
explícitos, mas obrigariam o operador a lembrar do segundo — e o histórico deste
projeto é de execuções longas, destacadas, retomadas dias depois. Um comando só,
idempotente por retomada, é mais difícil de usar errado. E o benefício de "a
máquina fica livre" se preserva: interromper o acompanhamento não perde nada.

## Risks / Trade-offs

**[Perda do checkpoint incremental]** → Hoje cada veredito é gravado ao chegar;
em lote só há resultado no fim. Mitigação: D3 mais a retenção do fornecedor. O
que não se recupera é o *parcial de um lote em andamento* — aceito, porque um
lote fecha em menos de 24 h por contrato.

**[O `custom_id` esbarrar em limite do fornecedor]** → Mata o benefício
estrutural de D1. Mitigação: verificar tamanho e alfabeto aceitos **na primeira
tarefa**, antes de o desenho depender disso; se não couber, cair para tabela de
mapeamento em disco e declarar a perda.

**[Dois caminhos para manter]** → Síncrono e lote podem divergir em validação
com o tempo, e aí as rodadas deixam de ser comparáveis. Mitigação: a paridade é
requisito de spec, não convenção — os dois caminhos chamam a mesma
`validar_resposta` e o mesmo `custo_usd`.

**[Lote voltar parcial]** → Parte processada, parte expirada. Mitigação: D4 dá
desfecho próprio à expiração; a decisão de reenviar os expirados fica com quem
executa, e não é automática, porque reenviar custa e o custo tem de ser
escolhido.

**[Formato e limites mudarem]** → Já mudaram durante o próprio levantamento (a
URL de preços da OpenAI passou a redirecionar). Mitigação: os limites vêm do
provedor, não de constante espalhada; e a validação de D5 é barata o bastante
para ser refeita antes de qualquer rodada.

## Migration Plan

1. Verificar, contra a documentação do fornecedor, o que o `custom_id` aceita de
   tamanho e de alfabeto. É o que D1 pressupõe.
2. Definir o protocolo `ProvedorLote` e o desfecho `EXPIRADO`, com testes que
   não tocam a rede.
3. Implementar a entrega em lote no `ProvedorGemini`, com o limite de
   enfileiramento declarado.
4. Ligar o eixo `--modo-envio` no runner, com a recusa precoce para provedor sem
   suporte e a uniformidade entre braços.
5. Persistir e consultar `lote.json`; testar a retomada matando o processo.
6. Validar com o lote de ~10 casos (D5), inclusive forçando um caso de erro.
7. Atualizar `docs/PIPELINE.md` e `docs/SCRIPTS.md`.

**Rollback:** o modo padrão continua síncrono. Descartar esta change é remover
um caminho que ninguém é obrigado a usar; nenhuma rodada existente depende dele.

## Open Questions

- **Em qual fornecedor a rodada comercial vai acontecer?** D6 implementa o
  Gemini por ser o mais barato de validar, mas a recomendação da §4 de
  `docs/ESCOLHA-MODELO-COMERCIAL.md` é `claude-sonnet-5`. Se a decisão for por
  ela, esta change precisa de uma sucessora com o provedor Anthropic — síncrono
  e em lote.
- **Requisições expiradas devem ser reenviadas automaticamente?** O desenho
  atual não reenvia. Automatizar seria conveniente e gastaria dinheiro sem
  autorização; deixar manual é seguro e pode travar uma rodada por descuido.
  Fica aberta até haver uma expiração de verdade para observar.
- **O piloto de decisão de modelo deve rodar em lote ou síncrono?** Se o piloto
  for em lote e a rodada também, não há problema. Se o piloto for síncrono por
  pressa e a rodada em lote, os dois não são comparáveis entre si — o que não
  invalida o piloto como instrumento de decisão de gasto, mas precisa estar
  dito.
