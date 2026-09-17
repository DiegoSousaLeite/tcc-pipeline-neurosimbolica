## Context

Duas CWEs concentram a perda da classe positiva: CWE-22 (114 pares, 0 detecções)
e CWE-918 (112 pares, 1 detecção). `ruleset-gosec` tentou fechar a lacuna com
regras de terceiros, que não levantam objeção metodológica. **Não bastou, e por
um motivo mais forte que o esperado: as regras não existem.** Medido em
2026-09-16 — `p/gosec` traz 23 regras, 22 já dentro do `p/default`, e nem ele
nem `p/trailofbits` nem `p/security-audit` acrescentam regra Go para as duas
CWEs alvo. Detalhes em `docs/MAPA-TCC-O-QUE-REESCREVER.md` §3.6.

O portão desta change está, portanto, **aberto**: a alternativa barata foi
testada e fechada.

O precedente é sólido. O Semgrep\* (EASE 2024) mediu quatro ferramentas SAST em
Java, encontrou 11,2 %–26,5 % de detecção individual e 38,8 % na união,
investigou os padrões ausentes dos rulesets, escreveu regras novas e chegou a
44,7 %. A contribuição publicada é a análise de lacunas, não as regras.

A objeção é igualmente sólida, e é sobre nós, não sobre o método: regra escrita
olhando os 114 pares descreve 114 arquivos que já vimos. **A esteira precisa
impedir, não a disciplina.**

**Fases tocadas:** 1, e agora **muda de código**. `ruleset-gosec` foi arquivado
sem implementar, então o mecanismo de ruleset composto não existe e foi
absorvido por esta change (D6).

**Arquivos tocados:** `regras/go/` (novo), `scripts/particionar_avaliacao.py`
(novo), `scripts/medir_regras_locais.py` (novo), `src/fase1_semgrep.py`,
`src/ruleset.py`, `src/cache_simbolico.py`, `docs/`.

**Custo de LLM:** zero. Nenhuma tarefa desta change chama modelo.

**Dependências novas:** nenhuma. Regra do Semgrep é YAML; o carregamento por
caminho local já é suportado pela CLI.

## Goals / Non-Goals

**Goals:**

- Produzir um número de detecção defensável para CWEs que nenhum ruleset
  disponível alcança.
- Tornar a separação entre escrever e medir uma propriedade da esteira.
- Obter um ruleset imune à deriva do lado do servidor.

**Non-Goals:**

- Competir com o `p/default` em cobertura geral.
- Apresentar as regras como contribuição de engenharia.
- Reportar qualquer número da partição de desenvolvimento.
- Escrever regra para CWE que algum ruleset público já resolva. Para as duas
  CWEs alvo isso está verificado e nenhum resolve.

## Decisions

### D1 — Dois protocolos de escrita, com forças diferentes

**Decisão:** `definicao` e `desenvolvimento`, declarados por regra.

**Por quê:** são epistemicamente distintos e merecem tratamento distinto. Uma
regra escrita a partir da definição da CWE e do idioma de Go — `os.Open`,
`os.ReadFile`, `http.ServeFile`, `filepath.Join` — não foi informada por nenhum
caso da população, e pode ser medida sobre ela inteira. Uma regra escrita
olhando casos concretos só pode ser medida no que sobrou.

**Consequência prática:** `definicao` é o protocolo preferido, porque preserva
todos os 114 casos como denominador. Só recorrer a `desenvolvimento` quando a
regra derivada da definição não funcionar e for preciso entender por quê.

**Alternativa considerada:** proibir `desenvolvimento` de todo. Recusada porque
seria contornada na prática — é impossível depurar uma regra sem ver código que
ela deveria pegar — e uma proibição contornada é pior que uma declaração honesta.

### D2 — Partição derivada do identificador, não sorteada

**Decisão:** função determinística do `ID_Caso`, estratificada por CWE.

**Por quê:** reprodutível por terceiros sem confiar numa semente nossa. E remove
a tentação: não há como reparticionar "com outra semente" até o número melhorar,
porque não há semente.

**Reforço estrutural:** a repartição é recusada quando a partição já existe. O
protocolo depende da ordem — partição antes de regra —, e o histórico do Git é o
que a torna auditável.

### D3 — O relatório recusa emitir o agregado

**Decisão:** falha explícita, não aviso.

**Por quê:** um aviso não impede a citação. A experiência do projeto com métricas
é que o número mais fácil de copiar é o que acaba no texto, e um agregado que
mistura partição de desenvolvimento com partição de avaliação é exatamente o
número indefensável. Recusar produzi-lo é a única mitigação que funciona meses
depois, quando o contexto tiver se perdido.

**Exceção deliberada:** se todas as regras carregadas forem `definicao`, o
agregado é emitido. Não há o que contaminar.

### D4 — Metadados ausentes derrubam o carregamento

**Decisão:** regra local sem `metadata.cwe` casável ou sem
`metadata.subcategory` não carrega.

**Por quê:** o padrão vigente em `src/ruleset.py` é conservador com metadado
ausente — trata como auditoria e segue. Isso é correto para ruleset de terceiros,
sobre o qual não temos controle. Para regra nossa, ausência é defeito nosso, e
falhar cedo é mais barato que descobrir depois que a regra disparou a rodada
inteira sem emparelhar.

### D5 — Regra sintática antes de regra de taint

**Decisão:** começar pelo padrão sintático; recorrer a `mode: taint` só se o
sintático for insuficiente.

**Por quê:** o motor CE só rastreia taint dentro de um arquivo, e é exatamente
essa limitação que deixou CWE-22 e CWE-918 secas. Escrever regra de taint para
rodar sob o motor que não a alcança repetiria o defeito que a change tenta
corrigir. Regra sintática é ruidosa e o braço neural existe para isso.

### D6 — O ruleset composto é absorvido por esta change

**Decisão:** o mecanismo de configuração de múltiplos rulesets — `--config`
repetido, identidade de conjunto insensível à ordem, deduplicação por
`(arquivo, posição, CWE)`, procedência por ruleset — passa a ser construído
aqui, recuperando as deltas de `ruleset-gosec`.

**Por quê:** ele não existe. `ruleset-gosec` o especificou e foi arquivado com 6
de 28 tarefas, sem tocar `src/`. Como esta change precisa somar um ruleset local
ao `p/default`, e somar exige `--config` repetido, não há caminho que a
dispense.

**Por que aqui e não numa change própria:** porque foi exatamente assim que o
mecanismo morreu da primeira vez — especificado sem consumidor, justificado por
um ganho (`p/gosec`) que não se materializou. Agora há um consumidor real, e o
mecanismo é meio para ele, não fim.

**O que muda em relação ao plano original:** a promessa de que "nada em `src/`
precisa mudar" cai. Era condicional a um pré-requisito que não se cumpriu.

## Risks / Trade-offs

**[Ajuste ao conjunto de teste]** → É o risco central. Mitigações empilhadas:
partição gravada antes por ordem de commit, derivação determinística sem
semente, repartição recusada, proveniência por regra, agregado recusado. Nenhuma
sozinha basta.

**[Partição de avaliação pequena demais]** → 114 casos de CWE-22 divididos ao
meio deixam ~57 para medir. É pouco, mas acima do limiar de 30 que o projeto já
adota. Para CWEs menores pode não ser. Mitigação: preferir protocolo `definicao`,
que não consome partição.

**[Regra nossa ser ruidosa demais]** → Vai ser, por D5. Consequência mensurável:
a taxa de redução de alertas ganha denominador maior e deixa de ser comparável
com as séries anteriores. Mitigação: reportar por conjunto de rulesets, nunca
fundindo séries — disciplina que `ruleset-gosec` exigia e que, com o
arquivamento dela, passa a ser responsabilidade desta change.

**[Confundir a contribuição]** → O risco de o texto apresentar "escrevemos
regras" como resultado. A contribuição é a lacuna: *o que o ruleset precisaria
ter para detectar estas fraquezas em código real*. As regras são a evidência de
que a lacuna é preenchível, não o achado.

**[Escopo maior que o planejado]** → Absorver o ruleset composto (D6) faz esta
change mexer em `src/`, o que o plano original evitava. É custo real, e o
cronograma precisa contá-lo. Mitigação: a delta já está escrita e revisada no
arquivo de `ruleset-gosec`; o que falta é implementação, não desenho.

**[Fusão de deltas com `semgrep-pro-entre-arquivos`]** → `cache-simbolico` e
`ruleset-alcancabilidade` já foram modificadas por aquela change, que está
aplicada. As deltas recuperadas precisam ser **fundidas**, não substituídas: os
eixos são independentes — conjunto de rulesets aqui, identidade do motor lá — e
o requisito final deve registrar os três, com a regra de pareamento.

## Migration Plan

1. ~~Confirmar que a medição de `ruleset-gosec` deixou lacuna.~~ **Feito:**
   deixou, e por ausência de regra publicada. Ver §3.6 do mapa.
2. Implementar o ruleset composto absorvido (D6), com configuração unitária —
   sem efeito observável. Verificar que uma rodada produz alertas idênticos.
3. Particionar e commitar a partição, isoladamente.
4. Escrever regras `definicao` para as CWEs alvo, sem abrir a população.
5. Medir sobre a população inteira — protocolo `definicao` permite.
6. Só se o número for insatisfatório: abrir a partição de desenvolvimento,
   escrever regras `desenvolvimento`, medir na partição de avaliação, e reportar
   os dois números separados.

**Rollback:** retirar o ruleset local da configuração. Nenhum artefato anterior é
alterado.

## Open Questions

- ~~Quais CWEs entram como alvo?~~ **Respondida:** CWE-22 e CWE-918. São as
  duas que concentram a perda, e a medição de `ruleset-gosec` confirmou que
  nenhum ruleset público as cobre em Go. Se outra CWE entrar depois, a
  verificação de cobertura pública se repete para ela.
- A partição estratificada é por CWE apenas, ou também por repositório? Casos da
  mesma CWE no mesmo repositório podem compartilhar idioma de código, e cair em
  partições diferentes vazaria informação de desenvolvimento para avaliação.
  **Provavelmente precisa ser por repositório também — verificar a distribuição
  antes de particionar.**
- Uma regra `definicao` que não funcionou pode ser corrigida sem virar
  `desenvolvimento`? Corrigir sintaxe de padrão não é o mesmo que ajustar a casos
  vistos, mas a fronteira é tênue e precisa de critério escrito.
- Como demonstrar, a quem ler a monografia, que o protocolo foi seguido? O
  histórico do Git é evidência, mas exige que o leitor o consulte. Vale um
  apêndice com os hashes de commit da partição e das regras.
