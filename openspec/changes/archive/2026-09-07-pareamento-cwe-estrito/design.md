## Context

A Fase 1 tem uma única responsabilidade de decisão: dado o arquivo-alvo e a CWE do gabarito, dizer **qual alerta do Semgrep é o alerta daquele caso**. Todo o resto da pipeline depende dessa resposta — a Fase 2 hidrata a função ao redor dele, as Fases 3/4 mandam o alerta ao LLM, e a Fase 5 pontua o veredito contra o gabarito do caso. Se o alerta escolhido não é o do caso, nada a jusante consegue perceber: o LLM responde corretamente sobre o que viu e a auditoria conta o acerto como erro.

Hoje essa decisão é tomada em duas etapas (`src/fase1_semgrep.py:102-112`). A primeira procura um alerta cuja regra traga a tag da CWE do gabarito. A segunda — o fallback — aceita o alerta quando ele é o único do arquivo, mesmo sem casamento. O comentário no código registra a intenção original: cobrir "regra sem tag de CWE explícita". Na prática o fallback dispara sempre que a primeira etapa falha e há um alerta só, o que inclui o caso em que a regra tem tag de CWE, apenas de outra fraqueza.

O defeito é estrutural, não estatístico. Na trilha FP o gabarito foi produzido pelo próprio Semgrep, então a CWE do caso sempre corresponde a alguma regra e a primeira etapa resolve. Na trilha TP o gabarito vem de CVE/CVEfixes: a CWE descreve a vulnerabilidade que o CVE relata, e não há razão para que exista regra do `p/default` com aquela tag naquele arquivo. O fallback é, portanto, quase exclusivo da trilha que carrega a classe positiva do experimento.

Leitura do código revelou um segundo defeito no mesmo ponto de decisão, independente do fallback e anterior a ele: `_cwe_nas_tags` compara por substring (`cwe_upper in str(t).upper()`). Como a tag do SARIF tem a forma `CWE-770: Allocation of Resources Without Limits`, um caso de gabarito `CWE-77` casa com uma regra de `CWE-770`. Na população há quatro pares em que um identificador é prefixo de outro: `CWE-20` contra `CWE-200` e `CWE-209`, `CWE-77` contra `CWE-770`, `CWE-79` contra `CWE-798`. Esse defeito produz emparelhamento errado na **primeira** etapa, aquela que o fallback nem chega a alcançar, e é indistinguível de um emparelhamento legítimo em qualquer artefato existente.

A mudança `relatorio-rodada-1`, ativa em paralelo, documenta a rodada `results/20260730T180648Z-14d6af8` tal como ela é — com a classe positiva contaminada — para os capítulos de Resultados e Limitações. As duas são complementares e não concorrentes: aquela descreve o estado anterior à correção, esta produz o estado posterior. A ordem importa só num ponto, registrado no plano de migração.

## Goals / Non-Goals

**Goals:**

- Tornar o emparelhamento alerta↔gabarito uma decisão explícita e defensável em uma frase: a regra que emitiu o alerta declara a CWE do gabarito.
- Corrigir o casamento por prefixo, que emparelha errado sem deixar rastro.
- Separar os dois motivos de não-detecção, hoje fundidos, para que a análise de cobertura simbólica possa distinguir "o motor não alcança esta fraqueza" de "o motor viu outra fraqueza neste arquivo".
- Impedir que o cache simbólico continue servindo emparelhamentos produzidos pela regra antiga.
- Entregar uma rodada limpa do braço local e as métricas recalculadas sobre ela.

**Non-Goals:**

- Recuperar os casos que passam a ser `ALERTA_OUTRA_CWE`. Eles são, corretamente, ponto cego do motor simbólico; aumentá-los ou reduzi-los é assunto de ruleset, e ruleset está fora de escopo.
- Qualquer noção de proximidade entre CWEs (família, CWE-pai, mapeamento manual regra↔CWE). Introduziria variável nova no experimento e exigiria defesa própria na banca.
- Mudar a granularidade do gabarito. Ele é por arquivo e continua por arquivo.
- Re-executar os braços comerciais.

## Decisions

### D1 — O fallback sai, sem substituto

O fallback é removido e nada ocupa seu lugar: o casamento explícito de CWE passa a ser condição necessária e suficiente.

Por que ele existia: regras do Semgrep podem não declarar CWE nas tags, e nesses casos a primeira etapa falharia mesmo quando o alerta é de fato o do caso. O fallback tentava recuperar essa situação com a heurística mais barata disponível — "se só há um alerta, é ele".

Por que sai: a heurística não distingue "a regra não declara CWE" de "a regra declara outra CWE", e é o segundo grupo que domina na prática. Todos os oito casos do diagnóstico vêm de regras que existem para outra fraqueza (`import-text-template`, `math-random-used`, `missing-ssl-minversion`, `use-of-md5`, `dangerous-exec-command`). O fallback também é silencioso por construção: nada no CSV distinguia um emparelhamento por casamento de um por fallback, então o defeito só apareceu por inspeção manual dos casos classificados como falha crítica.

Alternativas consideradas:

- **Manter o fallback só quando a regra não declara CWE alguma.** Preserva a intenção original e elimina os oito casos observados. Rejeitada porque continua aceitando um alerta sem relação demonstrada com o gabarito — a ausência de tag não é evidência de que o alerta seja o do caso — e porque a condição é rara o bastante para não justificar carregar uma exceção que precisa ser explicada na metodologia.
- **Heurística por família de CWE.** Rejeitada como pedido: exigiria construir e versionar um mapeamento CWE↔regra, que passaria a ser variável experimental, com hash próprio no manifesto e defesa própria na banca. O custo metodológico é desproporcional ao ganho de alguns casos.

Consequência aceita: o conjunto `DETECTADO` encolhe. Pela taxa medida (~8% dos casos amostrados vieram do fallback), a ordem de grandeza é de algumas dezenas de casos que migram para `NAO_DETECTADO`. A perda é aparente — esses casos nunca foram evidência sobre o LLM.

### D2 — Casamento por identificador completo, não por substring

`_cwe_nas_tags` passa a extrair o identificador da tag e compará-lo por igualdade, em vez de procurar a string do gabarito dentro da tag. Na prática: reconhecer `CWE-<dígitos>` no início da tag e comparar o número inteiro, de modo que `CWE-77` e `CWE-770` sejam identificadores distintos e `CWE-077` — se aparecer — seja o mesmo que `CWE-77`.

Alternativa considerada: manter substring e exigir que o caractere seguinte não seja dígito. Funciona, mas amarra a correção ao formato textual da tag; extrair o identificador é a operação que o código de fato quer fazer e sobrevive a mudanças de formatação do SARIF.

### D3 — O motivo vai para coluna própria, não para um valor novo de `Status_Semgrep`

`Status_Semgrep` continua com o domínio de hoje (`DETECTADO`, `NAO_DETECTADO`, categorias de erro), e o motivo entra em duas colunas novas no fim do `CABECALHO`: `Motivo_Nao_Deteccao` (`SEM_ALERTA` | `ALERTA_OUTRA_CWE` | `N/A`) e `Regras_Nao_Casadas`.

O motivo é defensivo. Três consumidores comparam a string `NAO_DETECTADO` diretamente — o checkpoint por tripla (`run_pipeline.carregar_processados`), o desvio de fluxo em `processar_caso` e a auditoria em `registrar_resultado` —, e `src/metricas.py` agrega por `Status_Semgrep` em `contar_status`. Um terceiro valor de status faria cada um deles falhar de um jeito diferente e nenhum deles falhar ruidosamente: o checkpoint deixaria de reconhecer o caso como resolvido e o reexecutaria em toda rodada, o que é justamente o modo de falha silenciosa que a spec de matriz experimental existe para evitar.

As colunas vão para o **fim** do cabeçalho porque `registrar_resultado` escreve a linha posicionalmente e `COLUNAS_PARTE2 = CABECALHO[13:]` é definido por fatia — inserir no meio deslocaria as duas coisas de uma vez.

`Regras_Nao_Casadas` é uma lista de `check_id` separada por `;`, ordenada alfabeticamente e deduplicada. Alfabética e não por ordem de aparição porque o campo existe para comparar CSVs entre si; ordem de aparição carregaria a ordem interna do Semgrep para dentro do dado.

### D4 — Duas versões distintas invalidam o cache simbólico

O payload do cache ganha `versao_pareamento`, e `CacheSimbolico.ler` passa a recusar entrada cuja `versao_pareamento` divirja da corrente — inclusive quando ausente, que é o estado de todas as entradas atuais. `VERSAO_FORMATO` sobe de 1 para 2 no mesmo movimento, porque o payload de fato ganhou campos.

Os dois eixos coexistem de propósito e não são redundantes a médio prazo. `VERSAO_FORMATO` responde "a estrutura gravada mudou"; `versao_pareamento` responde "a regra que decide qual alerta é do caso mudou". A próxima alteração na regra de pareamento não mudará a estrutura do payload, e sem um eixo dedicado alguém teria de lembrar de subir a versão de formato por um motivo que não é de formato — exatamente o tipo de acoplamento que o comentário atual em `cache_simbolico.py:38-39` já tenta evitar ("subir isto invalida todas as entradas — use quando a estrutura gravada mudar, não quando o ruleset mudar").

A invalidação alcança também as entradas `NAO_DETECTADO`, embora endurecer o pareamento nunca transforme não-detecção em detecção e o status delas continue correto. Elas não sabem informar qual dos dois motivos as produziu, e são a maioria da população — aceitá-las deixaria o diagnóstico de cobertura em branco justamente onde ele tem mais a dizer. É o que torna a re-execução uma varredura completa do Semgrep, e não parcial.

### D5 — `executar_semgrep` devolve um resultado nomeado

A assinatura passa de `dict | None` para uma `NamedTuple` — `ResultadoFase1(alerta, motivo, regras_nao_casadas)` — com `alerta=None` quando não houve emparelhamento.

`NamedTuple` e não `dict` nem dataclass: é da biblioteca padrão, não adiciona dependência, dá nome aos campos no ponto de uso e mantém indexação e igualdade posicional. Isso importa porque `resolver_simbolico` devolve hoje a tripla `(status, alerta, contexto)` e os testes existentes a acessam por índice (`[0]`, `[2]`) e por igualdade de tupla inteira (`tests/test_cache_simbolico.py:175-179`); estendendo-a no fim como `NamedTuple`, esses testes continuam válidos sem reescrita.

`executar_semgrep` tem um único chamador de produção (`run_pipeline.py:600`) — a mudança de contrato é contida.

### D6 — Escolha determinística entre alertas casados

Quando mais de um alerta casa com a CWE do gabarito, o alerta escolhido passa a ser o primeiro na ordenação por `(linha inicial, check_id)`, em vez do primeiro na ordem de saída do Semgrep.

O código atual depende da ordem em que o Semgrep emite os resultados. Ela é estável na prática, mas é um detalhe interno da ferramenta e não uma garantia; ordenar explicitamente custa uma linha e torna a reprodutibilidade independente disso. A prioridade declarada do projeto é reprodutibilidade acima de elegância, e este é um caso em que as duas nem competem.

Efeito colateral registrado: em arquivos onde duas regras diferentes tagueiam a mesma CWE, o alerta escolhido pode passar a ser outro. Como a rodada inteira será refeita, isso não cria divergência entre resultados antigos e novos além da que a mudança já causa.

## Fases e arquivos tocados

Fase 1 e Fase 5 mudam de comportamento; Fases 2, 3 e 4 não são tocadas (recebem o mesmo contrato de sempre, apenas para menos casos).

- `src/fase1_semgrep.py` — Fase 1: remoção do fallback (D1), casamento por identificador completo (D2), ordenação determinística (D6), novo retorno (D5), constante `VERSAO_PAREAMENTO`.
- `src/cache_simbolico.py` — `VERSAO_FORMATO` para 2, `versao_pareamento` no payload e na invalidação, novos campos gravados (D4).
- `run_pipeline.py` — `resolver_simbolico` propaga motivo e regras; `processar_caso` os repassa a `_registrar`.
- `src/fase5_auditoria.py` — duas colunas novas no fim de `CABECALHO`, preenchidas por `registrar_resultado` (D3).
- `src/metricas.py` — contagem de cobertura discriminada por motivo, tolerante a CSV sem a coluna.
- `tests/test_funcoes_puras.py` (ou módulo novo de Fase 1) — os três casos de emparelhamento pedidos, mais prefixo de CWE e regra sem tag.
- `tests/test_cache_simbolico.py` — invalidação por `versao_pareamento` e propagação de motivo/regras pelo cache.
- `tests/test_metricas.py` — contagem por motivo e CSV legado sem a coluna.
- `docs/PIPELINE.md` — descrição da Fase 1, taxonomia de não-detecção, colunas novas do CSV.
- `docs/SCRIPTS.md` — contrato de `executar_semgrep` (documentado hoje como "ou `None` (NAO_DETECTADO)", linha 186) e do payload do cache (linha 217).

`scripts/preencher_cache.py` importa de `run_pipeline` e não chama a Fase 1 diretamente; segue funcionando sem alteração, mas passa a popular o cache no formato novo.

Nenhuma dependência nova. `NamedTuple` e `re` são de biblioteca padrão.

## Custo, cota e tempo

Custo em dinheiro e cota de LLM: **zero**. A re-execução é do braço local (Ollama, `qwen2.5-coder-7b`), que não consome cota nem billing. Nenhuma chamada a Gemini ou GPT entra nesta mudança.

Tempo de parede: a invalidação total do cache simbólico obriga a varredura completa do Semgrep sobre os 948 casos, que é o custo dominante da pipeline, somada às ~2h50 do braço local medidas na rodada anterior. A quantidade de chamadas de LLM **diminui**, porque o conjunto `DETECTADO` encolhe — o tempo adicional vem inteiramente do Semgrep.

## Risks / Trade-offs

- **A classe positiva encolhe em vez de crescer.** Corrigido o emparelhamento, os ~5 positivos válidos passam a ser o número honesto, e Recall/F1/MCC continuam sem poder estatístico. → Mitigação: nenhuma, e é o resultado certo. Esta mudança entrega a medição correta, não uma medição melhor; ampliar a classe positiva é problema de dataset e está fora daqui. A `relatorio-rodada-1` é onde o custo desse limite é avaliado.
- **As métricas se movem também na classe negativa.** Casos da trilha FP aceitos pelo fallback contavam como Verdadeiro Negativo do LLM e como `Semgrep FP` na cobertura; sob pareamento estrito saem da matriz de acerto e viram `Semgrep VN`. TRA, proporção de FP filtrados e MCC mudam junto. → Mitigação: declarar a mudança nas duas classes ao reportar a rodada nova, para que a queda de TRA não seja lida como regressão da pipeline.
- **Invalidação total do cache é cara e irreversível na prática.** Uma vez começada a re-execução, não há rodada intermediária utilizável. → Mitigação: as entradas antigas não são apagadas (requisito já existente da spec), então o cache anterior continua em disco como evidência do que a regra antiga produziu; e a re-execução só começa depois de os testes passarem.
- **Duas colunas novas quebram leitores posicionais externos.** Qualquer script fora do repositório que leia os CSVs por índice de coluna vê o cabeçalho crescer. → Mitigação: as colunas vão para o fim, e todos os leitores internos usam `csv.DictReader`.
- **A correção de prefixo pode mover casos que hoje contam como detectados.** Um caso de `CWE-77` emparelhado a uma regra de `CWE-770` deixa de emparelhar, e o efeito não foi quantificado antes da implementação. → Mitigação: medir a variação explicitamente antes e depois na varredura de re-execução, e registrá-la no relatório da rodada em vez de deixá-la diluída no efeito da remoção do fallback.

## Migration Plan

1. Implementar e testar com o cache intacto: os testes de Fase 1 são unitários sobre SARIF sintético e não dependem de rodada.
2. Medir o efeito antes de re-executar: varrer a população com o cache antigo ainda em disco e contar quantos casos `DETECTADO` deixariam de emparelhar, separando os que caem por fallback dos que caem por prefixo de CWE. É o número que vai para o relatório.
3. Re-executar Fases 1/2 sobre os 948 casos (cache invalidado) e depois o braço local completo, sob `run_id` novo.
4. Recalcular as métricas e comparar com a rodada anterior, declarando o movimento nas duas classes.
5. `results/20260730T180648Z-14d6af8` permanece em disco, não é apagada: é a evidência do defeito e a base da `relatorio-rodada-1`.

Rollback: reverter o commit restaura o comportamento anterior, e as entradas de cache antigas continuam em disco — mas os CSVs da rodada nova passariam a conter colunas que a versão antiga da auditoria não escreve. O rollback é, portanto, do código e não dos resultados.

Ordem em relação a `relatorio-rodada-1`: aquela mudança descreve a rodada contaminada e não depende desta. Se as duas forem arquivadas na mesma janela, o relatório precisa dizer que o defeito já está corrigido e apontar o `run_id` novo, para que um leitor não conclua que a pipeline ainda emparelha errado.

## Open Questions

- Nenhuma pendente. As três decisões abertas da proposta original (destino dos casos, sobrevivência do fallback, escopo da re-execução) foram resolvidas com o autor antes da escrita das specs, e a quarta (registrar ou não as regras concorrentes) também.
