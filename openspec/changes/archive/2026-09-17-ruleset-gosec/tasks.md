## 1. Reconhecimento do `p/gosec` — antes de escrever código

- [x] 1.1 Baixar o catálogo do `p/gosec` pelo mesmo caminho que `src/ruleset.py`
      usa e responder por escrito: quantas regras rodam em Go, quantas declaram
      `metadata.cwe`, e em que formato. Verificar: contagens registradas em
      `design.md`, na seção de questões em aberto.
- [x] 1.2 Confirmar que `gosec.G304-1` e `gosec.G107-1` existem, rodam em Go e
      declaram CWE-22 e CWE-918 em formato que o casamento por identificador
      completo aceita. Verificar: as tags extraídas batem com as do gabarito pela
      função de comparação já vigente.
- [x] 1.3 Verificar se as regras declaram `metadata.subcategory`. Se não
      declararem, registrar que o grau daquelas CWEs não subirá ainda que a
      detecção melhore — e que isso não bloqueia a change.
- [x] 1.4 Rodar `semgrep --config p/default --config p/gosec` à mão sobre 5
      arquivos de CWE-22 do cache e contar os alertas. Verificar: saída registrada;
      se zero alertas novos, parar e reavaliar antes da seção 2.
- [x] 1.5 Verificar se há colisão de identificador de regra entre os dois
      rulesets. Verificar: interseção dos conjuntos de `id` é vazia, ou o efeito
      da colisão está registrado.

## 2. Configuração composta

- [ ] 2.1 Fazer `SEMGREP_CONFIG` aceitar mais de um ruleset, mantendo
      `p/default` sozinho como padrão. Verificar: teste que a configuração padrão
      monta exatamente a mesma linha de comando de antes desta change.
- [ ] 2.2 Materializar a configuração como `--config` repetido na invocação da
      Fase 1. Verificar: teste que dois rulesets produzem dois `--config`, na
      ordem configurada.
- [ ] 2.3 Fazer configuração vazia falhar com erro explícito. Verificar: teste que
      a falha é levantada e que o motor não é invocado.
- [ ] 2.4 Derivar a identidade do conjunto, insensível à ordem e distinta para
      subconjuntos. Verificar: três testes, um por propriedade.
- [ ] 2.5 Registrar a procedência de cada ruleset — terceiros ou próprio — e
      propagá-la ao manifesto. Verificar: rodar um caso e inspecionar o manifesto.

## 3. Catálogo e cache

- [ ] 3.1 Fazer `src/ruleset.py` carregar e fundir os catálogos dos rulesets
      configurados, mantendo o cache de catálogo **por ruleset**. Verificar: teste
      que acrescentar um ruleset não rebusca o catálogo do outro.
- [ ] 3.2 Garantir que acrescentar ruleset só amplia o conjunto alcançável.
      Verificar: teste que o conjunto com dois rulesets contém o conjunto com um.
- [ ] 3.3 Fazer o grau da CWE considerar a melhor regra entre todos os rulesets.
      Verificar: teste que CWE coberta por taint num e por regra sintática de
      vulnerabilidade noutro recebe o grau alto.
- [ ] 3.4 Trocar o eixo de ruleset do cache simbólico pela identidade do conjunto,
      invalidando por divergência e alcançando `NAO_DETECTADO`. Verificar: teste
      que entrada gravada sob conjunto unitário é ignorada sob conjunto composto.
- [ ] 3.5 Garantir que a ordem dos rulesets não invalida e que entrada legada de
      ruleset único é lida como conjunto unitário. Verificar: dois testes.
- [ ] 3.6 Rodar uma rodada com configuração unitária servida do cache e confirmar
      que os alertas são idênticos aos de antes. Verificar: diff vazio contra o
      CSV da última rodada.

## 4. Deduplicação

- [ ] 4.1 Implementar a deduplicação por `(arquivo, posição, CWE)`. Verificar:
      teste que achados equivalentes de rulesets diferentes contam como um.
- [ ] 4.2 Garantir que mesma posição com CWEs diferentes não é duplicata.
      Verificar: teste.
- [ ] 4.3 Garantir que a deduplicação é determinística e que nunca rebaixa o
      status. Verificar: dois testes, o segundo confirmando que `DETECTADO`
      permanece `DETECTADO` quando os achados equivalentes casam com a CWE do
      gabarito.

## 5. Medição do ganho

- [ ] 5.1 Repopular o cache simbólico com `p/default + p/gosec` **apenas** para
      CWE-22 e CWE-918, registrando o tempo. Verificar: contagem de entradas novas
      bate com o número de casos daquelas CWEs.
- [ ] 5.2 Medir detecções por CWE antes e depois, sobre exatamente os mesmos
      casos. Verificar: tabela gravada no diretório da rodada, com as duas séries
      lado a lado.
- [ ] 5.3 Medir o efeito no denominador: quantos alertas a mais por arquivo o
      conjunto composto produz. Verificar: número registrado, porque a taxa de
      redução de alertas depende dele e deixa de ser comparável com as Rodadas
      1–3.
- [x] 5.4 Decidir e registrar: repopular o resto da população ou parar. Se o ganho
      for nulo, escrever em `docs/MAPA-TCC-O-QUE-REESCREVER.md` que o problema de
      CWE-22 não é sintático — o que reforça o caminho de
      `semgrep-pro-entre-arquivos`.

## 6. Documentação

- [ ] 6.1 Documentar a configuração composta em `docs/PIPELINE.md`, incluindo o
      aviso de que ligar um ruleset novo invalida o cache daquela população.
- [ ] 6.2 Documentar em `docs/PIPELINE.md` que a taxa de redução de alertas não é
      comparável entre conjuntos de rulesets diferentes, e por quê.
- [ ] 6.3 Registrar em `docs/MAPA-TCC-O-QUE-REESCREVER.md` o resultado da medição
      e a consequência para o texto: a descrição da camada simbólica deixa de ser
      "`p/default`" e passa a nomear o conjunto, com a procedência de cada
      ruleset. A redação do `.tex` acontece em **branch separada**, não nesta.
- [ ] 6.4 Atualizar `docs/SCRIPTS.md` onde `SEMGREP_CONFIG` for mencionado.
      Verificar: as menções descrevem lista, não valor único.
- [ ] 6.5 Atualizar `README.md` se a interface de configuração mudar.
