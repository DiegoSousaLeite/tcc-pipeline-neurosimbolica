# Adendo de medições — *O Gargalo dos 19 Casos*

Complemento a `docs/PESQUISA-GARGALO-CLASSE-POSITIVA.pdf` (8 de setembro de 2026).
**Nada do relatório original é alterado.** Este documento acrescenta medição onde
o relatório fez estimativa, e registra três pontos em que a medição diverge do
que foi previsto.

Data das medições: 11 de setembro de 2026.
Instrumentos: CodeQL 2.27.0, SonarQube 26.9.0 Community, Semgrep 1.167.0.
Metodologia completa em `docs/SONDA-MOTORES.md`.

---

## Resumo do que foi medido

| item do relatório | o que ele afirmava | o que a medição mostrou |
|---|---|---|
| **D14** — CodeQL, CWE-22 | `go/path-injection` atacaria o balde | ✅ **confirmado** — 2 de 8 arquivos |
| **D14** — CodeQL, CWE-918 | `go/request-forgery` atacaria o balde | ❌ **refutado** — 1 de 29 arquivos |
| **D14** — `p/gosec` como "recomendação barata" | `gosec.G304-1` e `gosec.G107-1` no registry | ❌ **premissa não se verifica** |
| **D14 / B6** — SonarQube | 6,5 % de recall (RealVuln, Python) | ⚠️ **para Go: zero regras de segurança** |
| **§8 de `ANALISE-RODADA-3`** | falta de fluxo entre arquivos explica CWE-22 **e** CWE-918 | ✅ explica CWE-22 · ❌ não explica CWE-918 |

---

## 1. A linha do CodeQL na tabela D14, medida

A tabela **D14 — Outros motores para Go** registra o CodeQL como tendo taint
interprocedural e aponta `go/path-injection` para CWE-22 e `go/request-forgery`
para CWE-918. A sonda executou o CodeQL sobre **81 casos vulneráveis que o Semgrep
não detectou**, em 14 repositórios, no commit vulnerável exato.

| CWE | Semgrep (Rodada 3) | CodeQL medido | |
|---|---|---|---|
| **CWE-22** | 0 de 114 pares — 0,0 % | **10 de 23 casos — 43,5 %**<br>(2 de 8 arquivos — 25 %) | ✅ |
| **CWE-918** | 1 de 112 pares — 0,9 % | **1 de 43 casos — 2,3 %**<br>(1 de 29 arquivos — 3,4 %) | ❌ |
| CWE-94 | — | 0 de 6 casos | |
| CWE-79 | — | 0 de 5 casos | |
| CWE-78 | — | 0 de 4 casos | |

**Total: 3 de 47 arquivos recuperados — 6,4 %.**

A previsão do relatório vale para o CWE-22 e não vale para o CWE-918. Como as duas
CWEs têm peso quase idêntico no corpus (114 e 112 pares), **quem investisse numa
ferramenta com taint entre arquivos esperando os dois baldes compraria metade do
que imagina.**

Isso também é evidência contra a expectativa do bloco **D13** sobre o Semgrep Pro:
o CodeQL *já tem* a capacidade que o D13 descreve como o diferencial do Pro
("análise entre arquivos e interprocedural"), e ela entregou 6,4 %, não os 44–48 %
→ 72–75 % que o relatório cita — corretamente — como material comercial a tratar
com desconfiança.

### Detalhe que qualifica o número

Os 11 casos recuperados vêm de **3 arquivos em 2 repositórios**; 11 dos 14
repositórios deram zero. Como o gabarito do projeto é por arquivo, um único alerta
credita todas as funções rotuladas naquele arquivo — por isso a contagem por
arquivo (6,4 %) é a honesta, e a por casos (13,6 %) infla.

O CodeQL emitiu **231 achados** nesses arquivos e alertou **outra** CWE no arquivo
certo em 13,6 % dos casos. Não é cegueira: é o mesmo desalinhamento
ferramenta × gabarito já medido no Semgrep.

---

## 2. `p/gosec` — a premissa da recomendação não se verifica

O bloco **D** encerra recomendando `p/gosec` como *"a recomendação barata deste
bloco"*, com o argumento de que `gosec.G304-1` (CWE-22) e `gosec.G107-1` (CWE-918)
*"já estão no registry do Semgrep, no mesmo motor e na mesma CLI"*.

O ruleset foi baixado do registry e inspecionado:

| | |
|---|---|
| Regras em `p/gosec` | **23** |
| Delas, já presentes em `p/default` | **22** |
| Regras exclusivas | **1** — `go.lang.security.audit.unsafe.use-of-unsafe-block` |
| Regras `gosec.G304-1` / `gosec.G107-1` | **não existem** |
| Regras para CWE-918 | **0** |
| Regras para CWE-22 | 1 — `zip.path-traversal-inside-zip-extraction`, já contada no §8 da Rodada 3 |

**O `p/gosec` do registry do Semgrep não é uma portabilidade do gosec.** São 23
regras `go.lang.security.*` de autoria do próprio Semgrep, e 22 delas já estão no
`p/default` que a pipeline usa hoje. Adotá-lo acrescentaria **uma** regra, sobre
blocos `unsafe`, e removeria 61 outras.

A confusão é compreensível e o próprio relatório a evita na tabela D14, onde
**gosec** (securego, Apache-2.0, AST/SSA) aparece como linha separada, com `G304`
e `G107`. É o texto da recomendação que funde os dois. A distinção importa:

- **gosec** (a ferramenta autônoma) tem G304 e G107 — **não foi testado aqui**;
- **`p/gosec`** (o ruleset do Semgrep) não tem nenhum dos dois.

A recomendação barata do bloco D, portanto, continua de pé — mas o caminho é
instalar o **gosec autônomo**, não trocar o `--config` do Semgrep. São ferramentas
diferentes com o mesmo nome, e o custo metodológico é outro: gosec é binário
próprio, saída própria, e exigiria adaptador na Fase 1.

---

## 3. SonarQube — o número do B6 não se aplica a Go

O gráfico **B6** posiciona o SonarQube em **6,5 %** de recall, com a ressalva
correta de que é *RealVuln · Python · por achado*. Para Go, a medição é outra
ordem de coisa.

| SonarQube 26.9.0 Community, linguagem Go | |
|---|---|
| Regras no catálogo | **36** — 29 `CODE_SMELL` + 7 `BUG` |
| Regras de segurança (`VULNERABILITY` / `SECURITY_HOTSPOT`) | **0** |
| Regras de taint (S2076, S2083, S5131, S5144) | não existem na instância |
| Casos recuperados na sonda | **0 de 81** |

Para dimensionar: Java tem 768 regras, TypeScript 546, JavaScript 528, Python 444.
Go tem 36 — e nenhuma de segurança.

Ele processou **62.724 issues** nos 14 repositórios, 2.138 de regras `go:`. Nos
arquivos que contêm os SSRF e os path traversal, o que disparou foi `go:S3776`
(complexidade cognitiva), `go:S1135` (há um TODO), `go:S1192` (string duplicada).

**Ressalva de precisão:** o SonarQube *emitiu* 66 issues de segurança nos 14
repositórios — todas em Dockerfile e YAML de Kubernetes. A afirmação correta é
*"não possui regras de segurança para Go"*, não *"não possui regras de
segurança"*.

Comparação de catálogo com o motor atual:

| | regras Go | de segurança |
|---|---|---|
| Semgrep OSS `p/default` | 84 | 84 |
| SonarQube Community | 36 | **0** |

Trocar Semgrep por SonarQube Community seria regressão. O 6,5 % do B6 permanece
válido como referência de escala em Python; não transfere para Go.

---

## 4. O que isso acrescenta ao §8 da Rodada 3

`ANALISE-RODADA-3.md` §8 atribui a não-detecção de CWE-22 e CWE-918 à mesma causa:
ausência de análise de fluxo entre arquivos. A sonda separa as duas.

**CWE-22 — hipótese confirmada.** O documento descreve o caso geral como
`os.Open(filepath.Join(base, entradaDoUsuario))`, *"sintaticamente idêntico à
versão segura"*, cuja decisão depende de fluxo de dados. Dar esse fluxo tira a
detecção de 0,0 % para 43,5 % dos casos.

**CWE-918 — hipótese refutada.** O documento afirma que a regra de SSRF *"exige
origem e destino no mesmo arquivo"* e que *"SSRF real atravessa camadas"*. A
capacidade apontada como faltante foi fornecida, sobre 29 arquivos de 6
repositórios distintos, e o SSRF continuou invisível (1 recuperado).

A explicação provável é a mesma que o §8 dá ao CWE-22 e não estendeu ao CWE-918:
uma URL montada a partir de configuração, de campo de struct ou de valor vindo do
banco é **sintaticamente indistinguível** de uma URL controlada pelo atacante. A
pergunta que decide o caso não é *"este dado flui até aqui?"* — que o taint
responde — mas *"esta entrada é do usuário?"*, que nenhum analisador responde sem
especificação externa.

Isso conversa diretamente com o quadro do **IRIS** citado no bloco C: o IRIS usa o
LLM justamente para *inferir especificações de taint* (fontes e sumidouros) e
injetá-las no CodeQL. A medição desta sonda sugere **por que** esse movimento é
necessário: não é o rastreamento que falta, é a especificação de o que rastrear.

---

## 5. Conclusão do adendo

**Trocar de motor não abre o funil.** Dos 47 arquivos vulneráveis testados, **44
são invisíveis aos três motores** — Semgrep, CodeQL e SonarQube.

Extrapolar os 6,4 % do CodeQL para os 778 casos perdidos levaria os 19 vulneráveis
que hoje chegam ao LLM para algo entre 60 e 70 — e isso **superestima**, porque a
amostra foi escolhida no melhor cenário do CodeQL (só CWEs de taint, repositórios
pequenos). Sobre os 418 casos perdidos de CWE-400, CWE-200 e CWE-345 não há razão
para esperar sequer isso.

E o custo seria alto: a medição de 2026-06-17 registrou **6 de 43** falsos
positivos do dataset reproduzidos pelo CodeQL. Trocar de motor quebraria a classe
negativa — que funciona precisamente porque nasceu do Semgrep — para ganhar 6 % na
classe positiva.

O que o relatório chama de *"a descoberta central"* — que o SastBench não exige
que o scanner tenha detectado o verdadeiro positivo — permanece o caminho mais
promissor, e agora com um argumento a mais: **nenhum motor disponível fecha a
lacuna pela via da detecção.**

---

## 6. Limitações desta medição

- **81 casos de 778**, repositórios escolhidos por tamanho e CWEs escolhidas no
  melhor cenário do concorrente. Serve para decidir se vale investir; **não é
  estimativa da população**.
- **A amostra do CWE-22 é pequena** — 8 arquivos, 2 recuperados. A direção contra
  o zero do Semgrep é clara; o número 25 % é frágil. Uma reamostragem aleatória de
  40 arquivos (semente 42, universo de 86 arquivos em 46 repositórios) estava em
  execução no fechamento deste adendo; o resultado entra em
  `docs/SONDA-MOTORES.md` §8.
- **O gosec autônomo não foi testado.** É a alavanca barata que resta do bloco D,
  e a única do relatório cuja premissa sobrevive à verificação.
- **SonarQube Community**, não Developer Edition — o que é, em si, o resultado.
- `build-mode=none` **não existe para Go** no CodeQL 2.27.0 (o relatório não
  afirma o contrário; fica o registro, porque contraria a expectativa comum de que
  o build seria o obstáculo — ele não foi: 14 de 14 bancos construíram).
