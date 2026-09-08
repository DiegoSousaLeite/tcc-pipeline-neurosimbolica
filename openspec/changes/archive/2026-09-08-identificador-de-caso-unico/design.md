## Context

`run_pipeline.construir_casos_tp` deriva o identificador de um caso TP de
`(prefixo, repo_dir, cwe, funcao, versao)`. O par TP, porém, é identificado por
`(repo, fix_commit, arquivo, funcao)` — o **arquivo** está no par e não no
identificador.

O `prefixo_id` foi introduzido por `trilha-tp-dataset` e reaproveitado por
`trilha-tp-alcancavel` para separar o espaço de identificadores **entre** trilhas.
Ele resolve a colisão entre pools; não resolve a colisão **dentro** de um pool.

Medição sobre `tp_pairs_osv_alcancavel.json` (257 pares, 83 repos):

| | |
|---|---|
| identificadores repetidos | 18 |
| casos envolvidos | 46 |
| casos que sumiriam | 28 |
| pares com chave `(repo, cwe, funcao)` repetida | 23 de 257 |

## Goals / Non-Goals

**Goals**
- Identificador único dentro de cada trilha e entre trilhas
- Identificadores de `FP`, `TP_ouro`, `TP_prata` e `TP_dataset` inalterados
- Colisão remanescente falha alto, não em silêncio
- Alvos da trilha `TP_alcancavel` preenchíveis pela ferramenta padrão de cache

**Non-Goals**
- Renumerar trilha alguma
- Executar rodada
- Alterar prompts, modelo, semente, métricas ou classe negativa

## Decisions

### D1 — O discriminador vem do caminho do arquivo, não da posição no pool

O identificador de um caso SHALL depender apenas dos atributos daquele caso.

*Por quê:* a alternativa óbvia — desambiguar só quando há colisão, sufixando a
partir da segunda ocorrência — faz o identificador de um caso depender de quais
**outros** casos existem no pool. Uma colheita futura que acrescentasse um par
colidindo com um par hoje único mudaria o identificador do par antigo, quebrando
o checkpoint de uma rodada em andamento. Derivar do caminho do arquivo é estável
sob qualquer crescimento do pool.

### D2 — Discriminador é hash curto, não o caminho inteiro

`hashlib.sha256(arquivo).hexdigest()[:8]`.

*Por quê:* o caminho inteiro (`plumbing/object/commit.go`) traz barras e pontos
para dentro de um identificador cujos campos são separados por `:`, e o
identificador vai para nome de arquivo de checkpoint e para coluna de CSV. O
idioma de hash curto já existe na trilha do dataset (`TPD:1f40a88b:CWE-79:…`), o
que mantém a leitura uniforme. Colisão de 8 hex dentro de um repo é
desprezível, e a guarda do D4 a pegaria.

### D3 — O discriminador só se aplica a pools com prefixo próprio

Pools carregados sem `prefixo_id` — `TP_ouro` e `TP_prata` — mantêm o esquema
antigo.

*Por quê:* os identificadores dessas duas trilhas estão gravados nos CSVs e no
checkpoint das rodadas `20260730T180648Z-14d6af8` e `20260731T140000Z-af9bc32`.
Mudá-los invalidaria a retomada e a comparação entre rodadas. É a mesma razão
que criou o `prefixo_id`, e a regra fica ligada ao mesmo sinal: **pool com
prefixo é pool novo, cujo espaço de identificadores ainda não foi observado por
ninguém.**

Consequência aceita: os dois pools antigos continuam teoricamente sujeitos à
colisão. Hoje não colidem (medido: 0 repetidos em ambos), e a guarda do D4
denuncia se algum dia colidirem — o que é o comportamento correto, já que
consertar aquele caso exigiria decidir o que fazer com os CSVs antigos.

### D4 — Colisão remanescente aborta a montagem

A montagem da população SHALL falhar ao encontrar identificador repetido.

*Por quê:* é o que teria transformado este defeito em erro de dez segundos em
vez de 28 casos perdidos numa rodada de horas. O modo de falha a evitar é o
mesmo do `settings.yml` corrompido e o do fallback de pareamento: **saída
plausível e errada**. A guarda é barata e roda uma vez por execução.

Ela fica na montagem, e não dentro de `construir_casos_tp`, porque só a montagem
enxerga a população inteira — que é onde a unicidade precisa valer.

### D5 — Fases e arquivos tocados

| fase | arquivo | o que muda |
|---|---|---|
| 0 | `scripts/preencher_cache.py` | inclui `TP_PAIRS_ALCANCAVEL` em `casos_unicos()` |
| 1-5 | `run_pipeline.py` | esquema de identificador + guarda de colisão |
| teste | `tests/test_populacao.py` | teste de colisão dentro do pool |
| doc | `*.tex` | **proibido** |

## Risks / Trade-offs

**[Mudar identificador da trilha nova invalidaria checkpoint]** → não há
checkpoint a invalidar: a trilha `TP_alcancavel` nunca foi executada, e nenhum
CSV em `results/` contém um identificador `TPA:`. **Mitigação:** verificação
explícita nos CSVs existentes antes de fechar a mudança.

**[A guarda quebrar uma rodada legítima]** → se algum pool antigo colidir, a
montagem passa a abortar onde antes seguia. **Isto é o comportamento desejado**,
mas precisa ser conhecido: a mensagem de erro nomeia os identificadores
repetidos e a trilha, para que a decisão seja tomada com o dado à vista.

**[Hash curto reduzir a legibilidade do identificador]** → aceito. A procedência
continua legível no identificador (`TPA:go-git:CWE-345:Decode:…`), e o caminho
completo continua no pool e na coluna do CSV.

## Open Questions

Nenhuma. O escopo é fechado e verificável pela suíte.
