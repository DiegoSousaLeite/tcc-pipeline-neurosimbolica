## Context

`src/ruleset.py` responde hoje uma pergunta binária: *o motor tem regra para esta
CWE nesta linguagem?* A Rodada 3 mostrou que a resposta "sim" comporta realidades
muito diferentes.

Anatomia do `p/default` medida (84 das 1.074 regras rodam em Go):

| campo | valores |
|---|---|
| `mode` | ausente 74 · `taint` 10 |
| `metadata.subcategory` | `vuln` 43 · `audit` 41 |
| `metadata.confidence` | MEDIUM 41 · LOW 25 · HIGH 18 |

Correlação de Pearson de cada atributo com a taxa de detecção observada, sobre as
18 CWEs com ao menos 3 pares:

| atributo | r |
|---|---|
| nº de regras `subcategory=vuln` | **+0,335** |
| nº de regras `taint` | +0,330 |
| nº de regras (total) | +0,160 |
| nº de regras `confidence=HIGH` | −0,039 |

Nenhuma correlação é forte. A separação útil não aparece na correlação linear por
CWE — aparece na **agregação por grupo**, que é como a colheita realmente gasta o
orçamento.

## Goals / Non-Goals

**Goals**
- Grau ordinal por CWE, derivado de campo declarado do ruleset
- Rendimento previsível antes de gastar rede e disco
- Separação verificável fora da amostra que a gerou
- Consulta binária preservada

**Non-Goals**
- Redefinir a população de rodadas existentes
- Excluir CWEs por padrão
- Score contínuo
- Tocar em `.tex`

## Decisions

### D1 — O grau sai de campo declarado, nunca de lista de CWEs no código

`metadata.subcategory` e `mode` são escritos pelos autores das regras.

*Por quê:* uma lista de CWEs "boas" embutida no código seria a minha opinião sobre
quais fraquezas são sintáticas, passaria a mentir no instante em que o ruleset
mudasse, e mentiria em silêncio — o mesmo defeito que `ruleset-alcancabilidade`
já evita ao derivar o conjunto alcançável do catálogo em vez de fixá-lo. Além
disso, `audit` × `vuln` é distinção **do Semgrep**, não minha: citar a ferramenta
é argumento; inventar a régua é viés.

### D2 — Três graus ordinais, não um score contínuo

| grau | critério | pares | detecções | taxa |
|---|---|---|---|---|
| `alta` | ≥1 regra `vuln` **não**-taint | 115 | 13 | **11,30 %** |
| `media` | ≥1 regra `vuln`, todas taint | 239 | 4 | **1,67 %** |
| `baixa` | só regras `audit` | 336 | 1 | **0,30 %** |

*Por quê ordinal:* a escala é monotônica e sustentada por 18 detecções no total.
Um score contínuo (`0,73`) sugeriria precisão que 18 eventos não comportam, e
convidaria a comparações entre CWEs que a amostra não suporta. Três faixas é o que
o dado paga.

*Por quê o eixo taint separa `alta` de `media`:* uma regra de *taint* precisa de
origem e destino **no mesmo arquivo**, e o Semgrep OSS não faz fluxo entre
arquivos — nenhum dos 807 alertas do corpus trouxe trilha. CWE-918 é o caso
exemplar: única regra, de taint, 112 pares, 1 detecção.

### D3 — O grau não filtra a colheita por padrão

`--grau-minimo` existe, e o padrão é aceitar tudo o que hoje se aceita.

*Por quê:* restringir a colheita às CWEs onde a ferramenta acerta produz um recall
que mede a seleção, não a ferramenta. O grau serve para **prever e explicar** o
rendimento; quem decidir restringi-lo assume a mudança de denominador
explicitamente, na linha de comando, e ela fica gravada no relatório da colheita.

### D4 — O critério foi derivado dentro da amostra, e a spec exige testá-lo fora

O grau foi escolhido entre cinco candidatos **olhando** a taxa observada na
Rodada 3. Isso é geração de hipótese, não validação: ajustar um critério ao
resultado e depois citá-lo como previsão seria circular.

Daí o comando de validação ser requisito, e não conveniência. Ele recalcula a
separação sobre os CSVs de **qualquer** rodada, de modo que a próxima rodada teste
o critério sobre dados que não o geraram. Enquanto isso não acontecer, o texto
deve tratar a separação como **observada na Rodada 3**, não como prevista.

Robustez dentro da amostra, por remoção da CWE mais influente:

| removendo | `alta`+`media` | `baixa` | ganho |
|---|---|---|---|
| nada | 4,80 % | 0,30 % | 16,1× |
| CWE-89 (7 det.) | 2,98 % | 0,30 % | ~10× |
| CWE-79 (4 det.) | 4,38 % | 0,30 % | ~14,6× |

A separação não depende de uma única CWE.

### D5 — Reaproveita a leitura de ruleset existente

O grau entra em `src/ruleset.py`, ao lado de `cwes_alcancaveis` e
`cwe_alcancavel`, lendo o mesmo cache e a mesma comparação de CWE
(`fase1_semgrep._numero_cwe`).

*Por quê:* uma segunda leitura do ruleset divergiria da primeira no primeiro
ajuste, e o módulo já existe exatamente para impedir isso.

### D6 — Fases e arquivos tocados

| fase | arquivo | o que muda |
|---|---|---|
| — | `src/ruleset.py` | grau ordinal + leitura de `subcategory`/`mode` |
| 0 | `scripts/osv_harvest_go.py` | grau no relatório; `--grau-minimo` opcional |
| doc | `scripts/analise_rodada.py` | seção que valida a separação sobre uma rodada |
| teste | `tests/test_ruleset.py` | cobertura do grau |
| — | `run_pipeline.py`, `src/fase1_*` | **sem alteração** |
| doc | `*.tex` | **proibido** |

## Risks / Trade-offs

**[Circularidade do critério]** → derivado da mesma rodada que ele descreve.
**Mitigação:** D4 torna a validação fora da amostra um requisito, e o texto fica
obrigado a chamar a separação de observada até que isso ocorra.

**[Convite ao viés de seleção]** → existir um `--grau-minimo` facilita colher só
onde a ferramenta acerta. **Mitigação:** padrão inalterado (D3) e registro do
valor usado no relatório da colheita, para que a escolha apareça no artefato.

**[`subcategory` pode sumir ou mudar de vocabulário]** → é metadado do registry,
não contrato. **Mitigação:** ausência do campo degrada para o grau mais baixo
compatível com o que se sabe, e nunca levanta exceção — o pior caso é o
comportamento de hoje, o binário.

**[Amostra pequena]** → 18 detecções sustentam a escala inteira. **Mitigação:**
três faixas em vez de score (D2), e as taxas citadas sempre com o `n`.

## Open Questions

- **O grau se sustenta noutra linguagem?** Só é respondível colhendo fora de Go, o
  que muda o escopo do TCC. Fica registrado, não resolvido aqui.
