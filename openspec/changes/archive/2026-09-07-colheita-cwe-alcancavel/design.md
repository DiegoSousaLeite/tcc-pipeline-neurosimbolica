## Context

`scripts/osv_harvest_go.py` (Fase 0) baixa o dump de Go da OSV, consulta a API por
CVE/GHSA atrás do commit de fix, e monta candidatos. O fluxo atual:

```
dump Go da OSV → para cada entrada: osv_por_id() → extrai() → candidato
                                                      ↓
                       repo GitHub + commit de fix + cwe_ids[0]
```

`extrai()` devolve `(repo_url, fix_commit, cwe)` e fica com `cwes[0]` de
`database_specific.cwe_ids`. Não há consulta ao ruleset em ponto algum.

A cadeia completa da Fase 0 é `osv_harvest_go.py` → `tp_fixes_osv.json` →
`fetch_raso.py` → `tp_reconstruct.py` → `tp_pairs_osv.json`.

Esta mudança depende de `ruleset-alcancabilidade`, que entrega `src/ruleset.py`
com `cwes_alcancaveis(linguagem)` e `cwe_alcancavel(cwe, linguagem)`.

## Goals / Non-Goals

**Goals:**
- Recusar na colheita a candidata cuja CWE o motor não alcança
- Considerar todas as CWEs declaradas, registrando a que casou
- Reportar aceitas, recusadas por CWE e a data do snapshot do ruleset
- Identificar os 17 pares já alcançáveis nos pools atuais
- Preservar `tp_pairs.json` e `tp_pairs_osv.json` intactos

**Non-Goals:**
- Executar a colheita com alvo real (é de `rodada-classe-positiva`)
- Tocar em `run_pipeline.py` ou montar população (é de `trilha-tp-alcancavel`)
- Alterar `fetch_raso.py` ou `tp_reconstruct.py` — eles só serão executados
- Escrever qualquer coisa no TCC

## Decisions

### D1 — O filtro entra em `extrai()`, não no laço principal

*Por quê:* `extrai()` já é onde a CWE é lida. Filtrar ali mantém a decisão junto
da extração e evita que o laço principal precise conhecer a estrutura da
vulnerabilidade. O laço continua responsável apenas por diversidade de repo,
deduplicação e alvo.

### D2 — Recusa é contabilizada, não apenas descartada

Cada recusa incrementa um contador indexado pela CWE que a causou.

*Por quê:* sem isso, uma colheita que rende pouco é ambígua entre "a OSV tem
pouca coisa nessas fraquezas" e "o filtro está recusando tudo por defeito". A
primeira é resultado; a segunda é bug. O relatório precisa distinguir as duas
antes de se investir na reconstrução de pares.

### D3 — Aceitar se QUALQUER CWE declarada for alcançável, registrando a que casou

*Por quê:* a ordem de `database_specific.cwe_ids` é arbitrária. Ficar com a
primeira recusaria candidatas legítimas por acidente de listagem. E a CWE
registrada tem de ser a que casou, não a primeira: é ela que a Fase 1 vai
procurar no arquivo, e é contra ela que o gabarito será pontuado.

*Efeito colateral desejado:* candidatas com CWE alcançável **e** inalcançável
entram pela alcançável, que é a única sobre a qual o experimento pode dizer algo.

### D4 — Saída em arquivo próprio

A colheita filtrada não sobrescreve `tp_fixes_osv.json`.

*Por quê:* três motivos. `tp_pairs.json` é irrecuperável (exige histórico git que
não existe mais em disco). Os pares inalcançáveis de `tp_pairs_osv.json` são
evidência do achado dos 70%. E manter as saídas separadas é o que permitirá, na
mudança seguinte, distinguir na população o que veio da colheita filtrada do que
veio de reaproveitamento.

### D5 — `pares_alcancaveis.py` é somente leitura

O script identifica e lista; não escreve nos pools nem monta população.

*Por quê:* separar identificação de mutação torna a operação repetível e segura,
e deixa a decisão de composição para a mudança que trata de população.

### D6 — Testes com a API da OSV dublada

*Por quê:* a colheita real depende de rede, de um dump de dezenas de MB e de
dezenas de minutos. Nada disso é testável em suíte. O que precisa de teste é a
**decisão** — aceitar, recusar, qual CWE registrar —, e essa é testável com
vulnerabilidade sintética e ruleset sintético. É o mesmo padrão já adotado em
`tests/test_pareamento.py`, que testa a decisão da Fase 1 sobre SARIF sintético
sem invocar o Semgrep.

### D7 — Fases e arquivos tocados

| fase | arquivo | o que muda |
|---|---|---|
| 0 | `scripts/osv_harvest_go.py` | filtro em `extrai()`, contadores, relatório |
| 0 | `scripts/pares_alcancaveis.py` | novo, somente leitura |
| 0 | `scripts/fetch_raso.py`, `scripts/tp_reconstruct.py` | **sem alteração** |
| — | `src/ruleset.py` | apenas consumido |
| doc | `docs/SCRIPTS.md` | contrato novo da colheita |

**Custo de LLM:** zero.
**Tempo:** nesta mudança, apenas o de testes. A colheita real é da mudança
seguinte.

## Risks / Trade-offs

**[A OSV pode ter poucas vulnerabilidades nas CWEs alcançáveis]** → as CWEs
cobertas por regra Go são majoritariamente de configuração e criptografia
(CWE-327, 328, 338, 319), enquanto CVEs de Go tendem a controle de acesso
(CWE-284, 862, 863). **Mitigação:** é exatamente o que o relatório de recusa por
CWE (D2) revela — e revela **antes** da reconstrução de pares, que é a etapa
cara.

**[Ruleset do registry diferente do Semgrep local]** → o filtro consulta o
snapshot do registry; a rodada executa o Semgrep instalado. Já se observou
divergência (`ANALISE-RODADA-2.md` §6.1: `lxc/incus | CWE-338` casava em 30/jul e
não casava em 03/ago). A colheita pode aceitar CWE que o Semgrep local não cobre
mais. **Mitigação:** a data do snapshot vai no relatório; o desvio fica visível
em vez de silencioso.

**[Alcançável não é o mesmo que detectável]** → a regra existir não garante que
dispare naquele código: ela procura um padrão sintático específico, e a
vulnerabilidade da CVE pode não ter aquela forma. **Mitigação:** é limitação
assumida, não removível nesta mudança; o dimensionamento com folga e a
verificação do rendimento real são de `rodada-classe-positiva`.

**[Filtro recusar demais por defeito]** → um erro no casamento (por exemplo
comparar string com inteiro) recusaria tudo silenciosamente. **Mitigação:** os
testes da tarefa 2.x cobrem aceitação e recusa explicitamente, e o relatório
distingue recusa por CWE de colheita vazia.
