## Why

A Fase 1 emparelha o alerta do Semgrep com o gabarito do caso por casamento de tag de CWE, mas cai num fallback quando nenhuma regra casa: se o arquivo tem exatamente um alerta, ele é aceito assim mesmo (`src/fase1_semgrep.py:107-110`). O alerta que chega ao LLM passa então a não ter relação alguma com a fraqueza rotulada, e o veredito é pontuado contra um gabarito que não lhe pertence.

O efeito é assimétrico por construção, e cai justamente sobre o eixo mais frágil do experimento. Na trilha FP o gabarito foi gerado pelo próprio Semgrep (`metadata.source: semgrep`), então a CWE sempre casa com alguma regra e o fallback quase não dispara. Na trilha TP o gabarito vem de CVE/CVEfixes, e a CWE do CVE não tem motivo para corresponder a regra alguma naquele arquivo — é onde o fallback dispara e destrói o caso. Na rodada `results/20260730T180648Z-14d6af8` (ollama `qwen2.5-coder-7b`, 948 casos × 2 prompts), 8 dos 12 casos contados como "Falso Negativo (Falha Crítica)" são emparelhamentos errados: o LLM respondeu corretamente sobre o alerta que viu. Das 13 amostras vulneráveis que chegaram ao LLM, cerca de 8 estão contaminadas, e a classe positiva válida cai para ~5 — Recall, F1, MCC e TFN daquela rodada não são interpretáveis.

A mudança atende diretamente a pergunta de pesquisa principal do TCC — se o LLM filtra falsos positivos sem descartar verdadeiros positivos —, porque hoje a métrica que responde a segunda metade da pergunta é medida sobre uma classe positiva contaminada.

## What Changes

- **BREAKING (semântica de resultados)**: o fallback de alerta único é removido. Um alerta só é emparelhado ao caso quando a regra que o emitiu traz explicitamente a tag da CWE do gabarito. Não entra heurística substituta: qualquer aproximação por família de CWE exigiria um mapeamento CWE↔regra que viraria variável nova do experimento.
- A não-detecção deixa de ser um motivo único e passa a ter dois, hoje fundidos em `NAO_DETECTADO`:
  - `SEM_ALERTA` — o Semgrep não emitiu alerta nenhum sobre o arquivo;
  - `ALERTA_OUTRA_CWE` — emitiu alerta, mas de outra fraqueza.
  Os dois continuam em `Status_Semgrep = NAO_DETECTADO` e continuam contando como ponto cego simbólico na matriz de cobertura, porque a CWE rotulada de fato não foi detectada nos dois casos. O motivo entra em coluna própria do CSV, não em novo valor de status — mudar o valor de status quebraria o checkpoint por tripla, o cache e a leitura das métricas, que comparam a string `NAO_DETECTADO` diretamente.
- Quando o motivo é `ALERTA_OUTRA_CWE`, os `check_id` das regras que dispararam sem casar são registrados. É a evidência direta da análise de cobertura simbólica — "o Semgrep viu o arquivo, mas enxergou outra fraqueza" — e permite reproduzir a tabela de diagnóstico sem re-executar nada.
- O cache simbólico passa a registrar a versão da regra de pareamento e a invalidar entradas gravadas sob regra anterior. Sem isso, uma rodada nova continuaria servindo do disco exatamente os emparelhamentos que esta mudança elimina.
- A saída de cobertura simbólica de `src/metricas.py` passa a discriminar os dois motivos de não-detecção em vez de reportar só o total de `NAO_DETECTADO`.
- O braço local é re-executado ao fim da mudança, e as métricas são recalculadas sobre a rodada limpa.

## Capabilities

### New Capabilities
- `pareamento-simbolico`: a regra de emparelhamento entre o alerta do Semgrep e o gabarito do caso, a exigência de casamento explícito de CWE, a taxonomia de motivos de não-detecção e o registro das regras concorrentes.

### Modified Capabilities
- `cache-simbolico`: a entrada passa a registrar a versão da regra de pareamento, e a divergência dessa versão passa a invalidar a entrada — hoje só a versão do ruleset e a do formato invalidam.
- `metricas-comparativas`: o bloco de cobertura simbólica passa a reportar a não-detecção discriminada por motivo.

## Impact

Código:
- `src/fase1_semgrep.py` — remoção do fallback; `executar_semgrep` passa a devolver também o motivo da não-detecção e as regras que dispararam sem casar.
- `run_pipeline.py` — `resolver_simbolico` e `processar_caso` propagam motivo e regras até a auditoria.
- `src/fase5_auditoria.py` — duas colunas novas no CSV (`Motivo_Nao_Deteccao`, `Regras_Nao_Casadas`).
- `src/cache_simbolico.py` — versão da regra de pareamento no payload e na invalidação.
- `src/metricas.py` — cobertura simbólica discriminada por motivo.
- `tests/` — cobertura dos três casos de emparelhamento (1 alerta de outra CWE, 1 alerta casado, N alertas) e da invalidação do cache.
- `docs/PIPELINE.md` e `docs/SCRIPTS.md` — descrição da Fase 1 e do contrato de `executar_semgrep`.

Resultados que ficam obsoletos:
- A rodada `results/20260730T180648Z-14d6af8` inteira. Ela permanece em disco como evidência do defeito, mas nenhum número dela vai para a monografia.
- Todo o cache simbólico vigente é invalidado, então a re-execução inclui varredura completa do Semgrep sobre os 948 casos, além das ~2h50 do braço local. A invalidação é total e não parcial de propósito: uma entrada `NAO_DETECTADO` antiga continuaria correta quanto ao status, mas não sabe dizer qual dos dois motivos a produziu.
- As métricas mudam nas **duas** classes, não só na positiva. Um caso da trilha FP aceito pelo fallback era contado como `Semgrep FP` na cobertura e, quando o LLM respondia "seguro", como Verdadeiro Negativo no acerto; sob pareamento estrito ele sai da matriz de acerto e vira `Semgrep VN` na de cobertura. TRA, proporção de FP filtrados e MCC se movem junto com Recall e TFN.

Não muda: o ruleset (`p/default`) e o engine (OSS) do Semgrep permanecem como estão — os rótulos FP foram atribuídos contra achados desse ruleset nesse engine, e trocá-los invalidaria o gabarito.

## Não-objetivos

- Trocar ruleset ou engine do Semgrep, ou tentar recuperar por outro motor os casos que passam a ser `ALERTA_OUTRA_CWE`.
- Introduzir mapeamento ou taxonomia de proximidade entre CWEs (famílias, CWEs-pai) para emparelhar de forma aproximada.
- Emparelhar por número de linha: o gabarito é por arquivo, e a granularidade não muda aqui.
- Alterar o desenho em que o LLM é filtro puro do Semgrep — nenhum caso não emparelhado passa a ser enviado ao LLM.
- Re-executar os braços comerciais (Gemini e GPT). Só o braço local entra nesta mudança, porque não consome cota nem custo; os comerciais são re-executados quando houver billing, fora deste escopo.
