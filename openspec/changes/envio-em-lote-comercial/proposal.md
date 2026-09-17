## Why

O braço comercial deste trabalho nunca rodou: existem **17 vereditos
comerciais** contra dezenas de milhares locais, e a matriz 2x2 que
`matriz-experimental` declara como referência existe só no papel. O
levantamento da change `escolha-modelo-faixa-media` mediu o porquê e a resposta
não foi preço — **foi vazão**. O tier grátis do Gemini permite 20 requisições
por dia, o que transforma 3.172 chamadas em 159 dias por um motivo que não tem
nada a ver com dinheiro.

O modo de envio em lote resolve exatamente isso, e de quebra melhora tudo o mais:
**50 % de desconto** nos três fornecedores, **sem RPM para estourar** (o limite
vira enfileiramento, preenchido de uma vez), a maioria dos lotes fechando em
menos de uma hora contra 1 h 46 – 3 h 32 de laço sequencial, e a máquina
**livre** — hoje o Semgrep e o `llama-server` disputam RAM e as rodadas precisam
ser agendadas em volta disso.

Só que **não existe caminho para enviar um lote hoje**: o contrato de
`src/provedores/` é síncrono por construção — `avaliar(prompt) -> RespostaLLM`,
um prompt por vez. Esta change constrói esse caminho e o valida por **R$ 0,01**,
antes de qualquer decisão sobre qual modelo rodar de verdade.

**Pergunta de pesquisa atendida: nenhuma. Isto é infraestrutura.** Não produz
número para a monografia; produz a capacidade de produzir. A pergunta de escopo
(até onde valem as respostas a Q1, Q2 e Q3) continua sendo respondida pela
rodada comercial, que é decisão separada desta.

**Parte do TCC:** Parte 2 — a comparação com modelo comercial é Parte 2 por
definição.

## What Changes

- **Eixo novo de execução: o modo de envio**, com dois valores — `sincrono`
  (padrão, idêntico ao comportamento atual) e `lote`. Selecionável por
  `--modo-envio` em `run_pipeline.py`, na mesma forma do `--modo-montagem` que
  já existe.
- **Protocolo `ProvedorLote`**, ao lado do `ProvedorLLM` existente: `submeter`
  devolve um identificador de lote, `recuperar` devolve os vereditos mapeados.
  O `ProvedorLLM` síncrono **não muda**.
- **A chave de correlação do lote é a chave de checkpoint que o projeto já
  usa** — a tripla `(ID_Caso, Modelo_LLM, Tipo_Prompt)` que
  `matriz-experimental` exige. Não é detalhe de implementação: é o que impede
  estruturalmente que uma resposta seja gravada no caso errado.
- **Retomada após queda**: o identificador do lote é persistido **antes** da
  submissão, para que um crash local não perca o gasto já feito — os resultados
  ficam no fornecedor por 29 a 42 dias.
- **Desfecho `EXPIRADO`**, distinto de `ERROR`: uma requisição que estoura a
  janela de 24 h do lote não é a mesma coisa que um erro do modelo, e na
  Anthropic sequer é cobrada.
- **Particionamento por orçamento de tokens**, porque o Tier 1 do Gemini
  enfileira 3.000.000 de tokens e uma rodada de dois braços tem 3.199.085 — não
  cabe, por 6,6 %.
- **Modo de envio no manifesto**, junto do identificador do lote e do
  fornecedor, pela mesma razão que o modo de montagem já está lá.
- **Validação barata da esteira**: um lote de ~10 casos em
  `gemini-2.5-flash-lite` custa cerca de R$ 0,01 e exercita o caminho inteiro,
  inclusive o de erro.

Nenhuma mudança de comportamento no modo `sincrono`. Uma rodada que não passa
`--modo-envio` é indistinguível de uma rodada de hoje.

## Capabilities

### New Capabilities

- `envio-em-lote`: o que um modo de envio assíncrono precisa garantir para que
  os vereditos que ele produz sejam tão confiáveis quanto os síncronos —
  correlação por chave de checkpoint, uniformidade dentro da rodada, retomada
  sem regasto, contabilidade de tokens e custo preservada, e desfechos de falha
  distinguíveis.

### Modified Capabilities

- `provedores-llm`: o contrato de provedor passa a admitir **duas formas de
  entrega** — a síncrona existente e a em lote —, com a exigência de que ambas
  produzam `RespostaLLM` validada pelas mesmas regras de schema. A validação de
  veredito e a contabilidade de custo **não** podem divergir entre as duas.
- `matriz-experimental`: ganha o eixo do modo de envio, com a mesma restrição
  que já vale para o modo de montagem — **não varia dentro de uma rodada** — e
  a exigência de que conste do manifesto.

## Impact

**Código:** `run_pipeline.py` (flag e despacho), `src/provedores/` (protocolo
novo e ao menos uma implementação), o ponto de gravação em
`src/fase5_auditoria.py` para o desfecho `EXPIRADO`, e o manifesto.

**Documentação:** `docs/PIPELINE.md` e `docs/SCRIPTS.md` precisam registrar o
eixo novo.

**Resultados invalidados: nenhum.** Nenhuma rodada é re-executada, nenhum CSV
existente fica obsoleto, nenhum número já publicado muda. O modo padrão
continua sendo o síncrono.

**Ressalva que precisa ficar escrita:** uma rodada em lote e uma rodada síncrona
**não são comparáveis braço a braço** se o modo variar entre os braços, porque
aí o modo de envio entra como variável do experimento. É o mesmo argumento que
`matriz-experimental` já faz para o modo de montagem, e por isso a restrição de
uniformidade é requisito, não recomendação.

**Custo e cota:** a validação da esteira custa ~R$ 0,01 e exige billing ativo em
um fornecedor. Esta change **não** executa rodada comercial nem assume que a
decisão de rodar foi tomada.

**Dependência:** o levantamento de `escolha-modelo-faixa-media` (arquivada) é o
insumo — os preços de lote, os limites de enfileiramento por tier e o desenho
esboçado na §9.6 de `docs/ESCOLHA-MODELO-COMERCIAL.md` saem de lá.

## Não-objetivos

- **Não** implementar o provedor Anthropic (nem qualquer provedor novo). Esta
  change entrega o modo de envio; qual fornecedor ganha uma implementação de
  lote é decisão de quem for executar.
- **Não** decidir qual modelo rodar, nem se a rodada comercial vai acontecer.
- **Não** executar rodada comercial completa.
- **Não** tornar o lote o padrão. O síncrono continua sendo o modo default, e a
  rodada local **não muda em nada**.
- **Não** dar modo de lote ao provedor local (`ollama`): não existe API de lote
  para inferência local, e o gargalo dela é GPU, não vazão de rede.
- **Não** reabrir o desenho do prompt, da população ou do modo de montagem.
