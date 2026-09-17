## Why

De 797 casos vulneráveis, **19 chegaram ao LLM**. Os outros 778 morreram em
`NAO_DETECTADO` na Fase 1: o Semgrep não emitiu alerta que casasse com a CWE do
gabarito, e o desenho de filtro puro determina que sem alerta não há chamada de
LLM. Com n=19 não há Recall, F1, MCC nem taxa de falsos negativos — e **a metade
da Q2 sobre "sem introduzir falsos negativos" fica sem resposta**.

A Rodada 3 fechou a saída por volume: triplicar a colheita (257 → 690 pares)
multiplicou as detecções por 1,6 e *derrubou* a taxa de 4,28 % para 2,61 %. A
fonte OSV para Go está esgotada. Não há caminho para 30 casos pela via atual.

O que a pesquisa externa encontrou muda o quadro: **o SastBench — a fonte da
nossa classe negativa — não exige que o scanner tenha detectado o verdadeiro
positivo.** No artigo, o Semgrep roda sobre a versão pré-correção apenas para
fabricar os negativos ("achados que não compartilham o CWE ID com o verdadeiro
positivo daquele commit"); os positivos vêm das linhas afetadas declaradas na
CVE e entram no conjunto de candidatos independentemente do que o motor emitiu.
O agente recebe o repositório no commit, um grupo de CWE por vez, e devolve o
veredito.

**A restrição que nos trava é nossa, não do benchmark que citamos.**

**Pergunta de pesquisa atendida:** a metade não respondida da **Q2**. A Q1
continua sendo respondida pelo braço atual, que esta change preserva intacto.
Parte 2.

## What Changes

- **Braço de triagem, ao lado do braço de filtro — nunca no lugar dele.** A
  matriz ganha um eixo: como o candidato foi montado.
  - Braço `filtro` (atual): candidato vem do alerta do Semgrep. Positivo que o
    motor não detectou não chega ao LLM.
  - Braço `triagem` (novo): negativo continua vindo do alerta do Semgrep;
    positivo vem da localização do gabarito, sem exigir alerta.
- **Normalização obrigatória do candidato.** Os dois caminhos convergem para o
  mesmo registro antes da hidratação. Se o positivo injetado chegasse com forma
  distinguível — campo a mais, mensagem de formato diferente, ausência de ID de
  regra — o modelo poderia aprender a pista e mediríamos a pista, não o
  julgamento.
- **Grupo de controle.** Os 19 positivos que o Semgrep *achou* entram também no
  braço de triagem, marcados. Comparar o desempenho do LLM neles contra os
  injetados é a evidência de que a injeção não criou artefato.
- **Métricas destravadas:** Recall, F1, MCC e taxa de falsos negativos passam a
  ser calculáveis no braço de triagem.
- **BREAKING (de desenho, não de código):** a invariante "o LLM é filtro puro do
  Semgrep" deixa de ser universal e passa a ser propriedade do braço `filtro`.
  Duas capabilities a declaram hoje e precisam ser emendadas.
- **Atualização obrigatória do mapa do LaTeX.** Ver "Impacto".

## Capabilities

### New Capabilities

- `braco-triagem`: montagem do candidato a partir do gabarito quando o motor não
  detectou, normalização que torna os dois caminhos indistinguíveis, grupo de
  controle, e o registro do que a mudança de desenho obriga a escrever na
  monografia.

### Modified Capabilities

- `matriz-experimental`: o cenário "LLM permanece filtro puro do Semgrep" passa a
  valer para o braço `filtro`, e não para toda combinação de modelo e prompt.
- `pareamento-simbolico`: o cenário "Sem emparelhamento, o LLM não é consultado"
  ganha a mesma qualificação. O emparelhamento em si **não muda** — continua
  sendo casamento explícito de CWE, e continua sendo o que decide o status
  `DETECTADO`.

## Impact

**Código:** `src/fase2_middleware.py` (montagem e normalização do candidato),
`run_pipeline.py` (seleção do braço), `src/fase5_auditoria.py` (procedência do
candidato no CSV), `src/metricas.py` (métricas por braço e por procedência).

**Fases 1, 3 e 4 não mudam.** A Fase 1 continua rodando o Semgrep e registrando
`DETECTADO`/`NAO_DETECTADO` exatamente como hoje — o braço de triagem *lê* esse
status, não o altera. As Fases 3 e 4 recebem um contexto hidratado e devolvem um
veredito, indiferentes a quem montou o candidato.

**Custo de LLM: zero.** Por decisão do autor, a rodada de validação desta change
roda **apenas no provedor local** — nenhum braço comercial, nenhuma cota do
Gemini. Com isso a rodada completa cabe dentro desta change em vez de ficar para
outra: são ~3.200 chamadas entre os dois tipos de prompt, que o tier grátis não
comportaria e que o modelo local absorve. O recurso escasso passa a ser tempo de
parede, e a esteira mede a vazão num subconjunto antes de comprometer a execução
longa.

**Resultados invalidados:** nenhum. As Rodadas 1–3 são rodadas do braço `filtro`
e continuam válidas e citáveis como tal. O braço novo produz uma série nova.

**Documentação — e esta parte é requisito, não cortesia:**
`docs/MAPA-TCC-O-QUE-REESCREVER.md` é o documento de acumulação do que falta
escrever no LaTeX, e nenhum número das rodadas está no `.tex` ainda. Esta change
altera o **desenho do experimento**, não só um número: a redação atual descreve
uma arquitetura em que o LLM é filtro puro, e isso deixa de ser a descrição
completa. O mapa precisa registrar o que a mudança obriga a reescrever.

**A edição do `.tex` NÃO faz parte desta change** e acontece em branch separada,
pela decisão já vigente de não mexer na monografia antes de fechar o
experimento. Esta change escreve no mapa; a branch do LaTeX consome o mapa.

## Não-objetivos

- **Não** substituir o braço de filtro. Ele responde à Q1 e continua sendo o
  único que descreve o sistema como seria implantado.
- **Não** alterar o pareamento por CWE nem o significado de `DETECTADO`.
- **Não** afrouxar a colheita, o guarda anti-refactor ou a extração de pares.
  Esta change não toca na Fase 0.
- **Não** editar arquivo `.tex`.
- **Não** executar braço comercial. Gemini e GPT ficam de fora; a rodada de
  triagem com modelos comerciais, se acontecer, é change separada.
- **Não** afirmar, com os números do braço de triagem, nada sobre o desempenho
  do sistema em operação. Ver a ameaça em `design.md`.
