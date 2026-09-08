## 1. Grau ordinal em `src/ruleset.py`

- [x] 1.1 Escrever testes do grau a partir de rulesets sintéticos: regra `vuln` não-taint → grau alto; só `vuln` de taint → grau intermediário; só `audit` → grau baixo. Verificar: os três FALHAM na árvore atual, por ausência da função.
  - Falharam com `AttributeError: module 'src.ruleset' has no attribute 'grau_alcancabilidade'` — 9 testes novos vermelhos ao todo.
- [x] 1.2 Escrever teste de degradação: regra sem `subcategory`, ou com vocabulário desconhecido, é tratada como auditoria e não levanta exceção. Verificar: falha na árvore atual.
  - `test_metadado_ausente_ou_desconhecido_degrada_para_auditoria` cobre os dois casos (CWE-611 sem campo, CWE-352 com valor inventado).
- [x] 1.3 Escrever teste de que o grau é por linguagem, e teste de que `cwe_alcancavel` continua devolvendo o mesmo para CWE de grau baixo. Verificar: o segundo PASSA na árvore atual — é a rede de proteção da consulta binária.
  - `test_grau_baixo_continua_alcancavel` nasceu **verde** e continuou verde: grau baixo segue alcançável, e a Fase 1 não teve a fronteira estreitada.
- [x] 1.4 Implementar o grau lendo `metadata.subcategory` e `mode` do mesmo cache já usado por `carregar_regras`, sem segunda leitura do ruleset (D5). Verificar: os testes de 1.1 a 1.3 passam.
  - `Regra` ganhou `subcategorias` e `taint` **com valores neutros por padrão**, então ruleset sem esses metadados degrada ao comportamento binário em vez de quebrar.
  - `graus_alcancabilidade(linguagem)` devolve o mapa inteiro numa leitura só; `grau_alcancabilidade(cwe, linguagem)` consulta uma.
  - `None` (nenhuma regra declara a CWE) e `baixa` (há regra, nenhuma afirma vulnerabilidade) são estados distintos — `CWE-863` devolve `None`, `CWE-400` devolve `baixa`.
  - 22 testes de `test_ruleset.py` passam.
- [x] 1.5 Conferir o grau contra o ruleset real. Verificar: sobre `p/default` em Go, a partição das CWEs com pares na Rodada 3 é 8 `alta` / 4 `media` / 9 `baixa`.
  - Confirmado. Sobre as 34 CWEs alcançáveis em Go: 14 `alta`, 4 `media`, 16 `baixa`. Restringindo às que têm pares na rodada: **8 / 4 / 9**, exatamente o esperado.
  - Exemplos: `CWE-89`→`alta`, `CWE-79`→`alta`, `CWE-614`→`alta`, `CWE-918`→`media`, `CWE-22`→`media`, `CWE-400`→`baixa`, `CWE-863`→`None`.

## 2. Grau no relatório da colheita

- [x] 2.1 Exibir o grau ao lado de cada CWE na distribuição impressa por `scripts/osv_harvest_go.py`. Verificar: execução com `--max-scan` pequeno mostra o grau sem consultar rede além do já feito.
  - `--alvo 12 --max-scan 90` imprimiu cada CWE com seu grau e o agregado `candidatas por grau: alta=3, media=5, baixa=4`.
  - O arquivo das 810 candidatas foi copiado antes e restaurado depois (a colheita sobrescreve `data/tp_fixes_osv_alcancavel.json`); hash `a5dfc39b…` idêntico antes e depois.
- [x] 2.2 Acrescentar `--grau-minimo`, desligado por padrão, e registrar no relatório o valor usado. Verificar: sem a opção, a contagem de candidatas é idêntica à de antes da mudança sobre o mesmo `--max-scan`.
  - `--grau-minimo` aceita `baixa|media|alta`, default `None`, e o valor usado é impresso no resumo (`grau mínimo exigido: (sem restrição)`).
  - O texto da ajuda carrega a advertência de que restringir troca o denominador do recall.
- [x] 2.3 Escrever teste de que a colheita sem `--grau-minimo` aceita exatamente as mesmas candidatas de antes. Verificar: o teste passa e é a garantia do não-objetivo de não mudar o padrão.
  - `test_sem_grau_minimo_aceita_o_mesmo_de_antes` verifica que CWE de grau `alta` **e** de grau `baixa` continuam aceitas quando a opção é omitida. Nasceu verde e é a rede de proteção do padrão.

## 3. Validação da separação

- [x] 3.1 Acrescentar a `scripts/analise_rodada.py` uma seção que agrega pares e detecções por grau a partir dos CSVs de uma rodada. Verificar: `python scripts/analise_rodada.py results/20260908T094808Z-9a00cb2 --secao grau` reporta as três faixas.
  - Reporta. De passagem, corrigi `TRILHAS` de `analise_rodada.py`, que ainda não listava `TP_alcancavel` — lacuna deixada pela mudança `trilha-tp-alcancavel` que fazia a trilha nova cair na ordenação de "desconhecidas".
- [x] 3.2 Conferir que a agregação é por grupo e não média de taxas por CWE. Verificar: teste com duas CWEs de contagens desiguais devolve a razão das somas.
  - `test_agrega_somas_e_nao_media_de_taxas`: uma CWE com 2 pares e 100% e outra com 98 pares e ~1% resultam em **3,0%** (3/100), não na média de ~50,5%.
- [x] 3.3 Permitir excluir a CWE de maior contribuição e reportar a separação recalculada (D4). Verificar: excluindo CWE-89, a separação continua acima de 5×.
  - A seção identifica sozinha a CWE que mais detecta e recalcula. Sem CWE-89 (7 das 18 detecções): acima de `baixa` 2,98% contra 0,30% em `baixa` — **ganho de 10,0×**. A separação não depende de uma única fraqueza.
- [x] 3.4 Tratar rodada sem a trilha filtrada. Verificar: a saída informa a ausência em vez de falhar.
  - Três testes cobrem: rodada sem a trilha filtrada, rodada vazia, e rodada só com casos de gabarito seguro. Todos imprimem "indisponível" sem exceção.

## 4. Registro dos números medidos

- [x] 4.1 Rodar a validação sobre a Rodada 3 e registrar nesta tarefa as três taxas e a contagem de pares por grau. Verificar: os números batem com os do design (11,30 % / 1,67 % / 0,30 %).

    | grau | CWEs | pares | detecções | taxa |
    |---|---|---|---|---|
    | `alta` | 8 | 115 | 13 | **11,30 %** |
    | `media` | 4 | 239 | 4 | **1,67 %** |
    | `baixa` | 9 | 336 | **1** | **0,30 %** |

  - Acima de `baixa`: 354 pares, 17 detecções (4,80 %). Em `baixa`: 336 pares, 1 detecção (0,30 %). **Ganho de densidade 16,1×**, com 1 detecção perdida se recusasse.
  - **As CWEs de grau baixo consumiram metade do orçamento de colheita e renderam uma detecção.**
- [x] 4.2 Registrar explicitamente que a separação é **observada dentro da amostra que gerou o critério**, e que a validação fora da amostra depende de rodada futura. Verificar: a ressalva fica nesta tarefa e em `docs/ANALISE-RODADA-3.md`.
  - **O critério foi escolhido entre cinco candidatos OLHANDO a taxa desta rodada.** Isso gera hipótese, não a valida: ajustar um critério ao resultado e depois citá-lo como previsão é circular.
  - A separação medida é **observada nesta amostra**, não prevista para outra. A própria saída do comando imprime a ressalva, para que ela não dependa de quem escreve lembrar dela.
  - Validação fora da amostra depende de rodada futura — é o requisito da capacidade `validacao-do-grau`.
- [x] 4.3 Acrescentar a `docs/ANALISE-RODADA-3.md` a seção do grau, ligando-a à §8 (por que umas CWEs detectam e outras não). Verificar: o documento cita as três taxas e a ressalva de circularidade.
  - Seção "O grau de alcançabilidade, medido" acrescentada ao §8, com a tabela das três faixas, o ganho de 16,1×, a checagem de robustez sem CWE-89 e a ressalva em bloco destacado. Comando **E** acrescentado à seção "Como reproduzir".

## 5. Verificação

- [x] 5.1 Rodar a suíte inteira e o lint. Verificar: `python -m pytest tests/ -q` passa integralmente e `ruff check` fica limpo nos arquivos tocados.
  - **307 testes passam** (eram 284; 23 novos). `ruff check` limpo em `src/ruleset.py`, `scripts/osv_harvest_go.py`, `scripts/analise_rodada.py` e os três arquivos de teste.
- [x] 5.2 Confirmar que nada foi reinterpretado: população, CSVs e manifesto da Rodada 3 inalterados, e nenhum arquivo `.tex` tocado. Verificar: mtime dos CSVs inalterado e `git status -- "*.tex"` vazio.
  - CSVs e manifesto da Rodada 3 com mtime inalterado; nenhuma população foi reinterpretada. `git status --short -- "*.tex"` vazio.
