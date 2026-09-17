## 1. Portão de necessidade — RESOLVIDO em 2026-09-17

- [x] 1.1 Ler o resultado de `ruleset-gosec` e decidir, por escrito, quais CWEs
      continuam sem cobertura adequada. **Resolvido pela Tarefa 1, não pela 5:**
      o portão da Tarefa 1.4 daquela change parou antes da medição de ganho.
      CWEs alvo: **CWE-22 e CWE-918**. Detecções que o `p/gosec` alcançou em
      cada uma: **zero** — ele não acrescenta regra Go para nenhuma das duas.
      Registrado em `design.md` (Contexto e Questões em Aberto) e em
      `docs/MAPA-TCC-O-QUE-REESCREVER.md` §3.6.
- [x] 1.2 **Portão.** Se o `p/gosec` resolveu as CWEs alvo, arquivar esta change
      sem implementar. **Não resolveu — nem podia:** `gosec.G304-1` e
      `gosec.G107-1` não existem, e nenhum ruleset público consultado
      (`p/gosec`, `p/trailofbits`, `p/security-audit`) traz regra Go nova para
      CWE-22 ou CWE-918. O portão abre e a change prossegue.

## 2. Ruleset composto — absorvido de `ruleset-gosec` (D6)

As deltas destas tarefas estão em
`openspec/changes/archive/2026-09-17-ruleset-gosec/specs/`. São desenho pronto e
revisado; o que falta é implementação.

- [x] 2.1 Fazer `SEMGREP_CONFIG` aceitar mais de um ruleset, mantendo
      `p/default` sozinho como padrão. Verificar: teste que a configuração padrão
      monta exatamente a mesma linha de comando de hoje.
- [x] 2.2 Materializar a configuração como `--config` repetido em
      `montar_comando`, preservando o contrato de que `entre_arquivos=False` com
      configuração unitária devolve a lista de antes. Verificar: teste que dois
      rulesets produzem dois `--config`, na ordem configurada.
- [x] 2.3 Fazer configuração vazia falhar com erro explícito. Verificar: teste que
      a falha é levantada e que o motor não é invocado.
- [x] 2.4 Derivar a identidade do conjunto, insensível à ordem e distinta para
      subconjuntos. Verificar: três testes, um por propriedade.
- [x] 2.5 Fazer `src/ruleset.py` fundir os catálogos dos rulesets configurados,
      mantendo o cache de catálogo **por ruleset**. Verificar: teste que
      acrescentar um ruleset não rebusca o catálogo do outro, e teste que o
      conjunto alcançável com dois contém o conjunto com um.
- [x] 2.6 Fazer o grau da CWE considerar a melhor regra entre todos os rulesets.
      Verificar: teste que CWE coberta por taint num e por regra sintática de
      vulnerabilidade noutro recebe o grau alto.
- [x] 2.7 Trocar o eixo de ruleset do cache simbólico pela identidade do conjunto,
      **fundindo com o eixo de identidade do motor que
      `semgrep-pro-entre-arquivos` já aplicou** — não substituindo. Verificar:
      teste que entrada gravada sob conjunto unitário é ignorada sob conjunto
      composto, e que os testes de identidade do motor continuam passando.
- [x] 2.8 Garantir que a ordem dos rulesets não invalida e que entrada legada de
      ruleset único é lida como conjunto unitário. Verificar: dois testes.
- [x] 2.9 Implementar a deduplicação por `(arquivo, posição, CWE)`, determinística
      e sem rebaixar status. Verificar: quatro testes — equivalentes contam como
      um; mesma posição com CWEs diferentes não é duplicata; repetição preserva o
      mesmo achado; `DETECTADO` permanece `DETECTADO`.
- [x] 2.10 Registrar a procedência de cada ruleset — terceiros ou próprio — e
      propagá-la ao manifesto. Verificar: rodar um caso e inspecionar o manifesto.
- [x] 2.11 Rodar uma rodada com configuração unitária servida do cache e confirmar
      que os alertas são idênticos aos de antes. Verificar: diff vazio contra o
      CSV da última rodada.

## 3. Partição — antes de qualquer regra, e commitada isoladamente

- [ ] 3.1 Analisar a distribuição dos casos alvo por repositório e decidir se a
      estratificação é só por CWE ou também por repositório. Verificar: a decisão
      e os números que a sustentam ficam em `design.md`.
- [ ] 3.2 Escrever `scripts/particionar_avaliacao.py`: derivação determinística a
      partir do `ID_Caso`, estratificada conforme 2.1, sem semente. Verificar:
      `--selftest` confirma determinismo e estratificação sobre população
      sintética.
- [ ] 3.3 Fazer o script recusar reparticionar quando a partição já existe.
      Verificar: teste que a segunda invocação falha com erro explícito.
- [ ] 3.4 Executar e gravar a partição em `data/particao_avaliacao.json`.
      Verificar: cada CWE alvo tem casos nas duas partições.
- [ ] 3.5 **Commitar a partição sozinha, antes de qualquer regra.** Verificar:
      `git log` mostra este commit sem nenhum arquivo sob `regras/go/`.

## 4. Carregamento e validação do ruleset local

- [ ] 4.1 Criar `regras/go/` com uma regra de exemplo completa — `metadata.cwe`
      casável, `metadata.subcategory`, proveniência declarada. Verificar: a regra
      carrega e dispara sobre um arquivo construído para ela.
- [ ] 4.2 Validar proveniência no carregamento: ausente ou de vocabulário
      desconhecido derruba. Verificar: dois testes, um por condição, nomeando a
      regra na mensagem.
- [ ] 4.3 Validar `metadata.cwe` no carregamento, exigindo formato aceito pela
      comparação por identificador completo já vigente. Verificar: teste que CWE
      em formato não casável derruba o carregamento.
- [ ] 4.4 Validar `metadata.subcategory` no carregamento. Verificar: teste que
      ausência derruba — e não é tratada como auditoria, ao contrário do que vale
      para ruleset de terceiros.
- [ ] 4.5 Registrar no manifesto cada regra local usada, sua proveniência e o
      commit corrente do repositório. Verificar: rodar um caso e inspecionar o
      manifesto.

## 5. Regras derivadas da definição — sem abrir a população

- [ ] 5.1 Escrever as regras `definicao` para as CWEs alvo, a partir da definição
      da CWE e do idioma de Go. **Não abrir nenhum arquivo da população durante
      esta tarefa.** Preferir padrão sintático a `mode: taint`, por D5. Verificar:
      cada regra dispara sobre um arquivo de exemplo escrito à mão para ela, e não
      dispara sobre a versão segura do mesmo exemplo.
- [ ] 5.2 Registrar, junto de cada regra, de qual fonte a definição veio —
      descrição da CWE, documentação de `os`/`net/http`/`path/filepath`.
      Verificar: comentário no YAML de cada regra.
- [ ] 5.3 Escrever `scripts/medir_regras_locais.py`, que mede a detecção por
      partição e recusa o agregado quando houver regra `desenvolvimento`
      carregada. Verificar: `--selftest` cobre as duas situações.
- [ ] 5.4 Medir as regras `definicao` sobre a **população inteira** — permitido,
      porque nenhum caso as informou. Verificar: relatório emitido com o número e
      a ressalva de protocolo na mesma linha.
- [ ] 5.5 Decidir: o número é satisfatório? Se sim, pular a seção 6 e ir para a 7.
      Registrar a decisão.

## 6. Regras derivadas da partição de desenvolvimento — só se a seção 5 não bastou

- [ ] 6.1 Abrir **apenas** a partição de desenvolvimento e analisar por que as
      regras `definicao` não dispararam. Verificar: a análise fica registrada, e
      nenhum caso da partição de avaliação foi aberto.
- [ ] 6.2 Escrever ou ajustar regras com proveniência `desenvolvimento`.
      Verificar: cada uma declara a proveniência correta.
- [ ] 6.3 Medir na partição de avaliação e confirmar que o agregado é recusado.
      Verificar: o relatório traz os dois números rotulados e a tentativa de
      agregado falha.
- [ ] 6.4 Registrar o critério que separa "corrigir sintaxe de padrão" de
      "ajustar a casos vistos", resolvendo a questão em aberto de `design.md`.

## 7. Documentação e mapa do LaTeX

- [ ] 7.1 Documentar `regras/go/`, o protocolo de partição e os dois scripts em
      `docs/SCRIPTS.md`, no formato das demais entradas.
- [ ] 7.2 Documentar em `docs/PIPELINE.md` que a taxa de redução de alertas não é
      comparável entre conjuntos de rulesets, e que o ruleset local é o único
      imune à deriva do lado do servidor.
- [ ] 7.3 **Escrever em `docs/MAPA-TCC-O-QUE-REESCREVER.md`**: que a contribuição
      é a análise de lacunas e não as regras; que o número reportado sai da
      partição de avaliação quando houver regra `desenvolvimento`; que os hashes
      de commit da partição e das regras devem ir para um apêndice, permitindo ao
      leitor verificar que a partição precedeu as regras; e a ameaça à validade
      residual. Verificar: a entrada existe com os quatro pontos.
- [ ] 7.4 Declarar na mesma entrada que a redação do `.tex` acontece em **branch
      separada**, e não nesta. Verificar: a frase está lá.
- [ ] 7.5 Confirmar que nenhum arquivo `.tex` foi tocado. Verificar:
      `git diff --name-only` contra o ponto de partida não lista nenhum `.tex`.
