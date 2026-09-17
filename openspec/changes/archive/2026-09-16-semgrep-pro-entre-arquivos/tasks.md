## 1. Portão de viabilidade — nada abaixo começa antes desta seção fechar

- [x] 1.1 Criar conta gratuita no Semgrep AppSec Platform, rodar `semgrep login` e
      `semgrep install-semgrep-pro`. Verificar: `semgrep --version` e a existência
      do binário Pro em disco; registrar as duas saídas.
- [x] 1.2 Escrever `scripts/verificar_pro.py` em duas etapas (ver D7). **Etapa
      sintética** (`--etapa sintetica`): projeto Go mínimo escrito para este fim,
      com fonte num arquivo e sumidouro em outro, rodado nos dois modos. **Etapa
      real** (`--etapa real`): checkout raso de ~10 repositórios da população nos
      `parent_commit`, 5 de CWE-22 e 5 de CWE-918, rodado nos dois modos sobre a
      raiz do repositório. O script SHALL recusar alvo de arquivo isolado em vez
      de classificá-lo `inconclusivo`. Verificar: `--selftest` valida a lógica de
      classificação e a recusa de alvo inválido sem rede, no padrão de
      `scripts/tp_fetch_fixes.py`.
- [x] 1.3 Executar as etapas, na ordem, e gravar o resultado em
      `data/viabilidade_pro_<data>.json`: etapa executada, edição obtida, versão
      do Semgrep, alertas por modo, quantos trazem `dataflow_trace`, tempo por
      alvo em cada modo, e a classificação final (viável / inconclusivo /
      indisponível). Se a etapa sintética devolver `indisponível`, parar sem
      clonar nada. Verificar: o arquivo existe e a classificação está preenchida.
- [x] 1.4 **Portão.** Se a classificação não for `viável`, parar aqui: registrar o
      resultado em `docs/MAPA-TCC-O-QUE-REESCREVER.md` como evidência datada para
      a seção de trabalhos futuros e arquivar a change sem implementar. Se for
      `viável`, seguir para a seção 2.

## 2. Identidade do motor simbólico

- [x] 2.1 Definir a identidade do motor em `src/fase1_semgrep.py`: edição
      (`ce`/`pro`), versão do Semgrep e estado do modo entre-arquivos, numa
      estrutura única e serializável. Verificar: teste que a identidade do motor
      corrente é obtida sem invocar o Semgrep mais de uma vez por processo.
- [x] 2.2 Acrescentar a opção de invocação que liga o modo entre-arquivos,
      desligada por padrão. Verificar: teste que a invocação padrão monta
      exatamente a mesma linha de comando de antes desta change.
- [x] 2.3 Fazer a ativação falhar cedo quando não houver registro de viabilidade
      bem-sucedida. Verificar: teste que pedir o modo sem o arquivo da Tarefa 1.3
      levanta erro explícito, e não cai no CE em silêncio.
- [x] 2.4 Propagar a identidade até o manifesto da rodada em
      `src/fase5_auditoria.py`, ao lado da identidade do modelo que já consta.
      Verificar: rodar um caso e inspecionar o manifesto gerado.

## 3. Chave e invalidação do cache simbólico

- [x] 3.1 Acrescentar a identidade do motor ao payload gravado em
      `src/cache_simbolico.py`. Verificar: teste que uma entrada nova contém os
      três eixos — ruleset, pareamento e motor.
- [x] 3.2 Acrescentar o motor como terceiro eixo de invalidação, alcançando
      também as entradas `NAO_DETECTADO`. Verificar: teste que entrada gravada sob
      um motor é ignorada sob o outro, inclusive quando registra `NAO_DETECTADO`.
- [x] 3.3 Tratar entrada sem identidade como `ce` com modo desligado — o oposto
      da regra de pareamento, e deliberadamente (ver D3). Verificar: teste que
      uma entrada legada continua válida numa rodada CE e é ignorada numa rodada
      com o modo ligado.
- [x] 3.4 Garantir coexistência das entradas dos dois motores para o mesmo caso.
      Verificar: teste que gravar sob os dois motores produz duas entradas e
      nenhuma sobrescreve a outra.
- [x] 3.5 Rodar uma rodada CE completa servida do cache e confirmar que os
      alertas são idênticos aos de antes da change. Verificar: diff vazio contra
      o CSV da última rodada CE.

## 4. Alcançabilidade e grau em função do motor

- [x] 4.1 Fazer `graus_alcancabilidade` e `grau_alcancabilidade` em
      `src/ruleset.py` receberem o motor. Verificar: teste que a mesma CWE de
      taint recebe grau intermediário sob CE e grau alto sob o modo
      entre-arquivos.
- [x] 4.2 Marcar o conjunto alcançável sob modo entre-arquivos como limite
      inferior quando o catálogo não enumerar as regras próprias do modo.
      Verificar: teste que a marcação está presente e que o conjunto não é
      apresentado como exato.
- [x] 4.3 Confirmar que o eixo de auditoria não é afetado pelo motor. Verificar:
      teste que CWE coberta só por regra de auditoria recebe grau baixo nos dois
      motores.
- [x] 4.4 Confirmar que a consulta binária de alcançabilidade não mudou sob CE.
      Verificar: teste de regressão comparando o conjunto alcançável em Go sob CE
      com o conjunto atual.

## 5. Medição do ganho

- [ ] 5.0 **Decidir a unidade de análise da Fase 1 sob o motor novo** (ver D7).
      Hoje ela é o arquivo isolado, e repopular o cache mantendo essa unidade
      produziria resultado equivalente ao CE a custo de Pro. Analisar o
      repositório no commit muda o custo de parede da fase mais cara e o
      significado de `SEM_ALERTA` — um alerta pode passar a apontar para arquivo
      diferente do do gabarito, e a regra de pareamento não prevê isso. Esta
      decisão está fora dos artefatos atuais: registrá-la antes de 5.1, em
      change própria se alterar a Fase 1.
- [ ] 5.1 Repopular o cache simbólico sob o motor novo **apenas** para CWE-22 e
      CWE-918, sob a unidade de análise decidida em 5.0, registrando o tempo
      total. Verificar: contagem de entradas novas bate com o número de casos
      daquelas duas CWEs.
- [x] 5.2 Medir a detecção nas duas CWEs sob o motor novo e comparar com o CE
      sobre exatamente os mesmos casos. **Satisfeita por outro caminho:** sem
      repopular o cache (5.0/5.1 continuam abertas), medindo direto sobre
      checkouts com `--etapa gabarito`. 6 casos (3 CWE-22, 3 CWE-918), os dois
      motores sobre os mesmos casos, mesma regra de pareamento da Fase 1:
      **0 detecções novas**. Tabela em `docs/MAPA-TCC-O-QUE-REESCREVER.md` §3.5
      e dados em `data/viabilidade_pro_20260916.json` — não no diretório de uma
      rodada, porque nenhuma rodada foi executada.
- [x] 5.3 Registrar quantos dos alertas novos trazem `dataflow_trace`.
      **Registrado, e a resposta é zero:** não há alerta novo nos arquivos do
      gabarito em caso algum, logo não há trilha a contar neles. No repositório
      inteiro o Pro produziu 9 trilhas entre arquivos (etapa `real`), nenhuma
      tocando arquivo de gabarito. O campo
      `trilhas_entre_arquivos_tocando_gabarito` do relatório é a contagem.
- [x] 5.4 Decidir e registrar: **PARAR.** O ganho medido é nulo nas duas CWEs,
      e repopular o resto da população custaria 4-6x o tempo da fase mais cara
      para reproduzir os mesmos vereditos. Registrado em
      `docs/MAPA-TCC-O-QUE-REESCREVER.md` §3.5 (resultado negativo, com o limite
      da amostra declarado), §3.4 (ameaça do motor não fixado) e §6.5 (correção
      do critério de portão). `p/gosec` apontado como caminho alternativo — o
      gargalo medido é cobertura de regra, não alcance. Ver a change
      `ruleset-gosec`.

## 6. Documentação

- [x] 6.1 Corrigir a afirmação de esteira offline em `docs/PIPELINE.md`: passa a
      dizer "buscar uma vez, congelar, reexecutar offline", explicitando que o
      modo entre-arquivos acrescenta uma busca autenticada ao preenchimento e
      nada à reexecução. Verificar: a seção não afirma mais offline sem
      qualificar.
- [x] 6.2 Documentar `scripts/verificar_pro.py` em `docs/SCRIPTS.md`, no formato
      das demais entradas, incluindo o aviso de que o script exige rede e login.
- [x] 6.3 Documentar a flag do modo entre-arquivos e o terceiro eixo do cache em
      `docs/PIPELINE.md`, incluindo o aviso de que ligar a flag invalida o cache
      daquela população.
- [x] 6.4 Registrar em `docs/MAPA-TCC-O-QUE-REESCREVER.md` a ameaça à validade
      introduzida — motor proprietário sem versionamento sob nosso controle,
      agravando "ruleset não fixado" — e o resultado do portão, qualquer que
      tenha sido.
- [x] 6.5 Atualizar `README.md` se a interface de invocação da pipeline mudar.
      Verificar: as opções documentadas batem com `--help`.
