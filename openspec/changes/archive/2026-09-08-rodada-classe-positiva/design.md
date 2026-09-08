## Context

Esta é a mudança de execução. As três anteriores entregam:

- `ruleset-alcancabilidade` → `src/ruleset.py`
- `colheita-cwe-alcancavel` → filtro em `scripts/osv_harvest_go.py` e
  `scripts/pares_alcancaveis.py`
- `trilha-tp-alcancavel` → trilha `TP_alcancavel` em `run_pipeline.py`

Nenhuma delas produziu um número. A rodada `20260731T140000Z-af9bc32` continua
sendo o estado da arte do experimento: 107 casos vulneráveis na população, **1
chegando ao LLM**, e o aviso de poder estatístico limitado ativo.

Cadeia a executar:

```
osv_harvest_go.py --alvo N  →  pool de fixes
        ↓  (inspecionar relatório ANTES de prosseguir)
fetch_raso.py  →  tp_reconstruct.py  →  pool de pares
        ↓
preencher_cache.py  →  cache/ dos alvos novos
        ↓
run_pipeline.py --tudo --modelo ollama:... --run-id <novo>
        ↓
metricas.py --mcnemar  →  o aviso sumiu?
```

## Goals / Non-Goals

**Goals:**
- Executar a colheita filtrada com alvo decidido a partir do relatório
- Reconstruir pares e preencher cache dos alvos novos
- Executar a rodada e verificar o critério de aceite
- Isolar o rendimento da colheita filtrada do rendimento do reaproveitamento
- Registrar a taxa de sobrevivência para dimensionar uma eventual repetição

**Non-Goals:**
- Escrever qualquer coisa em arquivo `.tex`
- Alterar código de produto — defeito encontrado vira mudança própria
- Alterar prompts, modelo, semente, métricas ou classe negativa

## Decisions

### D1 — Ponto de inspeção obrigatório antes da reconstrução

A colheita é executada, o relatório é lido, e só então se decide prosseguir.

*Por quê:* a reconstrução de pares (`fetch_raso.py` + `tp_reconstruct.py`) e o
preenchimento de cache são as etapas caras em rede e tempo. O relatório de recusa
por CWE distingue "a OSV tem pouca coisa nessas fraquezas" de "o filtro está
recusando tudo por defeito" — a primeira é resultado, a segunda é bug, e investir
horas antes de saber qual é o caso seria desperdício.

### D2 — O alvo é decidido com o relatório, não antes

*Questão em aberto que se resolve por medição, não por decisão prévia.*

A taxa de sobrevivência entre colheita e chegada ao LLM é a incógnita central e
não é conhecida hoje. Fixar um número agora seria chute. A tarefa de colheita
registra a distribuição obtida; a tarefa de verificação mede a taxa real; se o
critério não for atingido, volta-se à colheita com alvo calculado a partir da
medição, sem refazer nada de código.

### D3 — Critério de aceite é a ausência do aviso, não uma contagem manual

*Por quê:* `src/metricas.py` já implementa o limiar de 30 e já emite o aviso. Usar
a saída dele como critério evita uma segunda definição de "suficiente" que possa
divergir da primeira. O critério é verificável por inspeção da saída de um comando.

### D4 — Os 17 pares já alcançáveis não mudam de trilha

Eles continuam contando como `TP_ouro` e `TP_prata`.

*Por quê:* movê-los para a trilha nova criaria identificadores duplicados —
`metricas.py` deduplica pela **primeira** ocorrência, então o caso apareceria uma
vez só, com procedência ambígua, destruindo a rastreabilidade. "Aproveitar" aqui
significa **não descartá-los**, e é o que já acontece por eles estarem na
população.

### D5 — Sem alteração de código

*Por quê:* misturar execução com correção tornaria impossível atribuir o
resultado a uma configuração conhecida. Se um defeito aparecer, ele é registrado
e vira mudança própria; esta rodada é abortada ou reexecutada depois.

### D6 — Fases e arquivos tocados

| fase | arquivo | o que muda |
|---|---|---|
| 0 | `scripts/osv_harvest_go.py` | **executado**, não alterado |
| 0 | `scripts/fetch_raso.py`, `tp_reconstruct.py`, `preencher_cache.py` | **executados** |
| 1-5 | `src/`, `run_pipeline.py` | **sem alteração** |
| doc | `docs/ANALISE-RODADA-3.md` | novo |
| doc | `*.tex` | **proibido** — fora de escopo |

**Custo de LLM:** zero em dinheiro e em cota — braço local via Ollama.

**Tempo:** colheita dominada por rede (dezenas de minutos; até 2 requisições por
entrada com `time.sleep(0.15)`). Rodada: a parte neural abaixo da anterior (cerca
de 1h10 para 948 casos, quase tudo servido do cache simbólico), mais a varredura
de Semgrep dos alvos novos.

## Risks / Trade-offs

**[O funil pode não abrir mesmo com CWE alcançável]** → a regra existir não
garante que dispare naquele código: ela procura um padrão sintático específico, e
a vulnerabilidade da CVE pode não ter aquela forma. **Mitigação:** alvo com folga
(D2) e ponto de inspeção (D1). **E se ainda assim render pouco, o resultado
continua publicável, mudando de afirmação:** em vez de *"o LLM preserva
vulnerabilidades reais"*, passa a ser *"nem restringindo às fraquezas que a
ferramenta cobre o funil se abre"* — conclusão forte sobre o limite da análise
sintática, não fracasso. Isso precisa estar previsto **antes** de rodar, para não
ser lido como insucesso depois.

**[Execução longa interrompida]** → a rodada anterior foi interrompida várias
vezes (queda de energia, suspensão da máquina, processo morto por limite de
tempo). **Mitigação:** o checkpoint por tripla absorve interrupções; retomar com
o mesmo `--run-id` pula o que já está gravado. Atenção conhecida: linhas em
categoria de erro **não** são checkpointadas e viram ID duplicado na retomada —
removê-las antes de retomar é procedimento estabelecido.

**[Ruleset mudar entre a colheita e a rodada]** → `p/default` é nome de coleção,
não versão fixada, e o cache simbólico não detecta a troca porque a string não
muda (`ANALISE-RODADA-2.md` §6.1). Uma CWE aceita na colheita pode não ser mais
coberta na rodada. **Mitigação:** a data do snapshot fica no relatório da
colheita; se o intervalo até a rodada for grande, revalidar. Fixar o ruleset
continua sendo mudança própria.

**[Cache simbólico invalidar sem necessidade]** → se `versao_ruleset` ou
`versao_pareamento` divergirem, os 791 casos da classe negativa pagam varredura
de novo, multiplicando o tempo. **Mitigação:** conferir as duas versões antes de
disparar a rodada.

**[Crescimento de `cache/`]** → alvos novos baixam arquivos novos. **Mitigação:**
chave imutável, nada invalida; é disco, não corretude.

## Open Questions

- **Qual o alvo da colheita?** Resolvido por medição na Etapa 1, não por decisão
  prévia (D2).
- **Quantas repetições de colheita são aceitáveis antes de concluir que o funil
  não abre?** A decidir com o autor se o critério de aceite falhar na primeira
  tentativa — é decisão de escopo do TCC, não técnica.
