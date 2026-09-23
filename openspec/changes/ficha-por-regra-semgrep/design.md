## Context

Parte 2 do TCC, eixo horizontal da matriz (baseline × especialista). Fases tocadas: 3/4 (montagem do prompt) e, indiretamente, 5 (valor novo em `Ficha_CWE`). As Fases 0, 1 e 2 não mudam.

Hoje `processar_caso` (`run_pipeline.py:909`) resolve a ficha **antes** de rodar o Semgrep, só com `caso["cwe"]` e `caso["cwe_name"]`. A Fase 1 aceita qualquer regra cuja tag contenha aquela CWE (`src/fase1_semgrep.py:536`), então o número da CWE da ficha e o do alerta coincidem, mas a construção de código não. A contagem de `check_id` no cache simbólico (791 detecções) mostra o desalinhamento:

| CWE | Ficha fala de | Regras que disparam |
|---|---|---|
| CWE-327 | `md5`/`sha1` em senha | `missing-ssl-minversion` 93 |
| CWE-94 | texto de template vindo de entrada | `dangerous-exec-command` 91, `dangerous-exec-cmd` 3 |
| CWE-665 | chave zerada em `aes`/`hmac` | `invalid-usage-of-modified-variable` 62, `iterate-over-empty-map` 13 |
| CWE-319 | URL `http://` | `bypass-tls-verification` 42, `use-tls` 42 |
| CWE-79 | `template.HTML`, `Fprintf` | `import-text-template` 56, `no-direct-write-to-responsewriter` 53, ... |

O `Candidato` (`src/fase2_middleware.py:74`) já carrega `check_id`; no candidato de gabarito ele vale `VALOR_NEUTRO`.

## Goals / Non-Goals

**Goals:**
- Que as camadas 1–3 do especialista descrevam a construção que o alerta aponta, em todas as regras de volume relevante.
- Separar, na medição, o efeito do catálogo novo e o efeito da instrução nova do template.
- Manter as rodadas anteriores reproduzíveis e identificáveis por hash.

**Non-Goals:**
- Ver `proposal.md`, seção "Não-objetivos". Em especial: nada muda no baseline, na Fase 1, na hidratação nem no contrato de saída.

## Decisions

### D1 — Chave da ficha de regra é o `check_id` completo
Casar pelo identificador inteiro (`go.lang.security.audit.crypto.missing-ssl-minversion.missing-ssl-minversion`).

Alternativa descartada: casar pelo último segmento (`missing-ssl-minversion`). É mais legível, mas os pacotes `p/default`, `trailofbits.*` e as regras locais `regras.go.*` convivem na mesma rodada e nada impede nomes curtos repetidos entre eles. Um casamento acidental aplicaria a ficha errada sem aviso, que é o mesmo defeito que esta mudança corrige.

### D2 — Bloco `regras` dentro de `data/catalogo_cwe.json`, não arquivo separado
Um arquivo só mantém um hash só (`Hash_Catalogo`) e uma fonte única, que é o que a spec `catalogo-cwe` exige. Um segundo arquivo exigiria uma segunda coluna de hash e uma segunda regra de divergência em `src/metricas.py`.

Consequência aceita: a chave `regras` não é uma CWE. `cwes_especificas` e `tem_ficha` precisam excluí-la, da mesma forma que já excluem `__fallback__`, e a validação trata `regras` como um mapa de fichas.

### D3 — A ficha passa a ser resolvida depois da candidatura
Em `processar_caso`, resolver a ficha com `candidatura.candidato.check_id` depois de `montar_candidatura`. Casos sem candidato (`NAO_DETECTADO` sem injeção, falha de esteira) continuam registrando a origem da ficha de CWE, como hoje, porque a coluna precisa existir em toda linha e não há regra para consultar.

O `check_id` `VALOR_NEUTRO` do candidato de gabarito é tratado como ausência de regra: o braço de triagem continua usando a ficha de CWE para os injetados, e a procedência não vaza para o prompt por uma ficha diferente.

Consequência para a comparação pareada no modo triagem: um mesmo caso vulnerável pode receber ficha de regra quando veio de alerta e ficha de CWE quando foi injetado. Isso já decorre de o candidato ser diferente; a coluna `Ficha_CWE` permite estratificar.

### D4 — Instrução nova em template novo, medida como braço separado
`prompts/especialista_v2.md` = `especialista.md` + um parágrafo antes de "ALERTA E CÓDIGO FONTE" (no direto, antes de "CÓDIGO FONTE"):

> Não presuma validação, sanitização ou mitigação que não aparece no trecho. Se o dado que chega à operação sensível pode vir de origem externa e nenhuma verificação é visível no código, isso conta a favor de VP.

A redação fala em "operação sensível", e não em "ponto apontado", para servir aos dois enquadramentos: no direto não há alerta apontando linha.

O modo triagem usa os templates `_direto`, então a instrução ganha duas variantes: `especialista_v2.md` (cópia de `especialista.md` mais o parágrafo) e `especialista_direto_v2.md` (cópia de `especialista_direto.md` mais o mesmo parágrafo, com o mesmo texto). O parágrafo é idêntico nas duas, para que o efeito medido nos dois modos seja o da mesma instrução.

Rodar os dois especialistas com o catálogo novo permite ler dois efeitos separados:
- catálogo: especialista com hash antigo × especialista com hash novo. Só é **pareado** no qwen em modo filtro, porque a rodada `20260908T094808Z-9a00cb2` ainda está em disco. Nos demais (gemma no filtro, que nunca rodou; qwen e gemma na triagem, cujos CSVs das Rodadas 5 e 6 foram apagados), a comparação é só com os agregados publicados em `docs/ANALISE-RODADA-5.md` e `docs/ANALISE-RODADA-6.md`, sem McNemar;
- instrução: especialista × v2, ambos com o hash novo, pareado em todos os modelos e modos.

Alternativa descartada: editar `especialista.md` ou `especialista_direto.md`. Mudaria o `Versao_Prompt` das rodadas anteriores sem que elas soubessem e misturaria os dois efeitos numa diferença só.

### D7 — Matriz da rodada nova: dois modelos × dois modos
Critério: não repetir o que já foi testado. Braço que não lê o catálogo e já foi medido não é refeito, nos dois modelos. Os modos são exclusivos por rodada (`--modo-montagem` é uniforme, para manter a comparação pareada), então são **duas rodadas**, cada uma com os dois modelos:

| rodada | modelo | braços | observação |
|---|---|---|---|
| filtro | `qwen2.5-coder:7b` | `especialista`, `especialista_v2` | `baseline` já testado: reaproveitado de `20260908T094808Z-9a00cb2` (CSV em disco), pareado por `ID_Caso`; diferença de n (825 × 827) tratada restringindo às amostras com veredito válido nos dois |
| filtro | `gemma2:9b` | `baseline`, `especialista`, `especialista_v2` | gemma nunca rodou no modo filtro |
| triagem | `qwen2.5-coder:7b` | `especialista_direto`, `especialista_direto_v2` | `baseline_direto` já testado na Rodada 5: comparação só com o agregado publicado, sem McNemar |
| triagem | `gemma2:9b` | `especialista_direto`, `especialista_direto_v2` | `baseline_direto` já testado na Rodada 6: comparação só com o agregado publicado, sem McNemar |

Semente 42 e temperatura 0, como nas Rodadas 5 e 6. O `gemma2:9b` roda com o mesmo digest da Rodada 6 (`ff02c3702f32`, Q4_0); se o digest local for outro, isso é registrado no manifesto e na análise.

### D5 — Heurísticas com "É VP quando ... / É FP quando ..."
Formato fixo, verificável por teste (presença das duas frases). Vale para fichas de regra e para as 15 de CWE; o fallback já tem essa forma.

Mexer nas heurísticas de CWE também muda o hash, mas o hash já muda por D2. Fazer tudo numa mudança só evita um terceiro hash.

### D6 — Seleção das regras por auditoria de metadados, escrita a partir da documentação
A lista de regras que ganham ficha sai de um script de auditoria que lê **só** o `check_id` e a CWE do caso no cache simbólico, nunca o código hidratado. Critério: a regra tem pelo menos 5 detecções e o alvo dela não é a API central da ficha da CWE. A lista vai para o artefato da change, antes da escrita.

As fichas são escritas a partir de: página da regra no registry do Semgrep e o YAML da regra (padrões, mensagem, metadados), repositório `trailofbits/semgrep-rules` para as regras `trailofbits.*`, e a documentação da stdlib de Go. O protocolo anti-viés continua valendo: nenhum trecho de código do cache, do dataset ou de CSV de resultado.

## Risks / Trade-offs

- [Contaminação pela conversa em que o problema foi achado: trechos do argo-cd já foram lidos durante a análise (`InteractiveEdit` com `$EDITOR`, `secretToRepository`)] → Nenhum exemplo pode repetir essas construções; o exemplo FP de `dangerous-exec-command` não pode ser um editor lido de variável de ambiente. Uma task de verificação compara cada exemplo com o cache.
- [Quem escreve as fichas: se houver apoio de IA na redação, isso precisa aparecer na declaração de uso de IA da monografia] → Registrar autoria e ferramenta no artefato da change, antes da rodada.
- [Classe positiva quase vazia nas CWEs corrigidas (1 vulnerável em CWE-94, 0 em 327 e 665)] → O ganho esperado é de validade, não de número. Declarar isso no texto; não vender melhora de recall que a amostra não consegue medir.
- [Os CSVs das Rodadas 5 e 6 foram apagados e os baselines da triagem não são refeitos: na triagem, nem o efeito do catálogo nem baseline × especialista têm teste pareado] → Comparar com os agregados publicados e dizer isso no texto; na triagem, a única comparação pareada é especialista × v2. No filtro, baseline × especialista é pareado nos dois modelos (qwen contra o CSV de `20260908T094808Z-9a00cb2`).
- [A instrução do `especialista_v2` pode inverter o viés e inflar os VPs sobre uma população quase toda FP] → É exatamente o que o braço separado mede; a especificidade (TNR) aparece na tabela ao lado do recall.
- [Fatos de versão de Go na ficha de TLS (mínimo padrão TLS 1.2 no cliente desde Go 1.18 e no servidor desde Go 1.22)] → Conferir nas release notes oficiais antes de congelar; a ficha cita a versão.
- [O hash continua dependendo do fim de linha do checkout] → Fora do escopo (proposta). A rodada nova é feita na mesma máquina, com o mesmo `core.autocrlf`, para o hash ser comparável dentro do TCC.

## Migration Plan

1. Implementar resolução por regra e os tipos `especialista_v2` e `especialista_direto_v2` com testes, sem tocar ainda no conteúdo do catálogo (as fichas de teste ficam em fixtures).
2. Rodar a auditoria (D6) e fixar a lista de regras.
3. Escrever as fichas de regra e ajustar as heurísticas (D5); rodar a validação e o teste anti-contaminação; congelar o catálogo num commit próprio.
4. Rodar as duas rodadas da matriz D7 (filtro e triagem, qwen e gemma), com a Fase 1 servida do cache simbólico e o modelo carregado só depois dela.

Custo e tempo: tudo **local** (Ollama), sem custo de API nem cota. Estimativa pelas velocidades medidas (qwen ≈ 4,6 s/chamada na Rodada 5; gemma ≈ 8,8 s/chamada na Rodada 6), com ~800 chamadas por braço no filtro e ~1.590 na triagem:

| rodada | modelo | braços | chamadas | tempo estimado |
|---|---|---|---|---|
| filtro | qwen | 2 | ~1.600 | ~2 h |
| filtro | gemma | 3 | ~2.400 | ~6 h |
| triagem | qwen | 2 | ~3.200 | ~4 h |
| triagem | gemma | 2 | ~3.200 | ~8 h |
| **total** | | **9** | **~10.400** | **~20 h** |

Cada rodada é retomável pelo checkpoint `(ID_Caso, Modelo_LLM, Tipo_Prompt)`, então pode ser dividida em sessões. Nenhuma chamada ao Gemini ou à OpenAI é feita nesta mudança; os braços comerciais serão rodados depois pelos autores, com o catálogo já congelado aqui, e o custo seguirá a estimativa por token registrada no manifesto.

Evidências e escrita: como a tabela baseline × especialista é a evidência central do capítulo de resultados, a rodada nova provavelmente muda os números e parte da interpretação. O rascunho em `editaveis/resultados.tex` e o `docs/PLANO-ESCRITA-RESULTADOS.md` devem ser revistos depois da rodada, não antes; o que muda fica anotado no mapa de reescrita.

Rollback: o catálogo antigo está no git (`a875610`); voltar o arquivo restaura o hash antigo, e o código novo trata a ausência do bloco `regras` como catálogo sem fichas de regra.

Resultados obsoletos: as linhas do braço especialista das rodadas `20260731T*` e `20260908T094808Z-9a00cb2`, e os números do `especialista_direto` das Rodadas 4–6 (qwen e gemma), passam a ser de uma versão anterior do catálogo. Ficam como registro histórico; as tabelas da monografia usam as rodadas novas.

## Open Questions

- ~~Incluir os braços comerciais na rodada nova?~~ Decidido: não. Só local nesta mudança; os comerciais serão rodados depois pelos autores.
- ~~Quais modelos e modos?~~ Decidido: `qwen2.5-coder:7b` e `gemma2:9b`, filtro e triagem, mantendo as variantes v2 (D7).
- As 5 detecções de corte da auditoria (D6) são suficientes, ou `reverseproxy-director` (18) e `websocket-missing-origin-check` (17), cujas CWEs não foram auditadas nesta análise, também entram? A auditoria decide com base no critério, mas o corte pode ser revisto.
