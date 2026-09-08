## Context

Três mudanças seguintes (`colheita-cwe-alcancavel`, `trilha-tp-alcancavel`,
`rodada-classe-positiva`) precisam responder à mesma pergunta: *o motor tem regra
para esta CWE nesta linguagem?* Hoje a resposta é obtida de forma ad-hoc.

`scripts/medir_pareamento.py` já faz metade do caminho:

- `carregar_regras()` busca `https://semgrep.dev/c/p/default`, cacheia em
  `cache_simbolico/_regras_p_default.json` e devolve `{id: [cwes]}` —
  **descartando `languages`**
- `_lista()` normaliza `metadata.cwe`, que vem ora como string, ora como lista
- `_casava_por_substring()` é a comparação **antiga**, que faz `CWE-77` casar com
  `CWE-770`

`src/fase1_semgrep.py` tem a comparação correta (`_numero_cwe`, `_cwe_nas_tags`),
mas aplicada às tags de um alerta já emitido, não ao catálogo de regras.

Medição de referência: o `p/default` tem 1074 regras, 84 delas de Go, cobrindo 34
CWEs distintas.

## Goals / Non-Goals

**Goals:**
- Um lugar único e correto para responder à pergunta de alcançabilidade
- Reaproveitar a comparação da Fase 1, sem reimplementá-la
- Preservar `languages`, hoje descartado
- Funcionar offline a partir do cache do ruleset

**Non-Goals:**
- Fixar o ruleset por versão (mudança própria)
- Alterar a Fase 1 ou qualquer regra de pareamento
- Consumir o módulo fora de `medir_pareamento.py` — isso vem nas mudanças
  seguintes

## Decisions

### D1 — O módulo mora em `src/ruleset.py`

*Por quê:* será consumido por `scripts/` (colheita, medição) e potencialmente por
`src/` (análise). `src/` é importável pelos dois lados e já é onde vive o código
de domínio do projeto; `scripts/` é a camada de execução da Fase 0. Colocá-lo em
`scripts/` obrigaria `src/` a importar de `scripts/`, invertendo a dependência.

*Decisão do autor, questão em aberto resolvida.*

### D2 — A comparação vem de `src/fase1_semgrep.py`, não é reescrita

`_numero_cwe` é importado, não copiado.

*Por quê:* se a alcançabilidade aceitasse por um critério e o pareamento
recusasse por outro, a colheita produziria casos que a Fase 1 descartaria. Uma
segunda cópia divergiria no primeiro ajuste — e o defeito a evitar é justamente
o casamento por substring, corrigido há pouco.

*Alternativa descartada:* mover a comparação para `src/ruleset.py` e fazer
`fase1_semgrep.py` importar de lá. Inverteria a direção da dependência sem ganho:
a Fase 1 é o consumidor mais crítico e não deve depender de módulo que faz rede.

### D3 — `_casava_por_substring` permanece em `medir_pareamento.py`

*Por quê:* aquela função **descreve a regra antiga**, e existe para reproduzir as
medições já registradas em `docs/ANALISE-RODADA-1.md` §7.1 e
`docs/ANALISE-RODADA-2.md`. Removê-la tornaria irreproduzíveis números que já
estão documentados. Ela não deve ser exportada nem reaproveitada.

### D4 — Falta de cache e de rede é erro, não conjunto vazio

*Por quê:* conjunto vazio faria toda CWE parecer inalcançável, e a colheita
recusaria a população inteira **em silêncio** — o mesmo modo de falha do
`settings.yml` corrompido, em que saída vazia virou "nenhum achado" e produziu 200
não-detecções falsas. Falhar alto é a lição já aprendida.

### D5 — Fases e arquivos tocados

| fase | arquivo | o que muda |
|---|---|---|
| — | `src/ruleset.py` | novo |
| 0 | `scripts/medir_pareamento.py` | importa do módulo; preserva `languages` |
| 1 | `src/fase1_semgrep.py` | **sem alteração**, apenas importado |
| doc | `docs/SCRIPTS.md` | módulo novo documentado |

**Custo de LLM:** zero — não há chamada de LLM.
**Tempo:** desprezível; só rede na primeira busca do ruleset.

## Risks / Trade-offs

**[Ruleset do registry diferente do Semgrep local]** → o módulo consulta o
snapshot do registry; a pipeline executa o Semgrep instalado. Já se observou
divergência (`ANALISE-RODADA-2.md` §6.1). **Mitigação:** expor a data de obtenção
do snapshot junto do resultado, para que o desvio seja visível. Fixar o ruleset
fica para mudança própria.

**[Cache do ruleset envelhecer sem aviso]** → o arquivo em
`cache_simbolico/_regras_p_default.json` não expira. **Mitigação:** a data de
obtenção fica disponível; a decisão de refazer a busca é de quem consome.

**[Dependência de `src/` em `scripts/`]** → evitada por construção (D1): o módulo
está em `src/` e `scripts/` importa dele, nunca o contrário.
