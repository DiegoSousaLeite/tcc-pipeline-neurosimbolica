## Why

`ruleset-gosec` não fechou a lacuna de CWE-22 e CWE-918, e não vai fechar:
medido em 2026-09-16, as regras que o justificavam (`gosec.G304-1`,
`gosec.G107-1`) não existem, e nenhum ruleset público do registry acrescenta
regra Go para essas fraquezas além das que o `p/default` já tem. Aquela change
foi arquivada com 6 de 28 tarefas. Sobra escrever regra. É caminho legítimo e tem precedente direto: o **Semgrep\*** (EASE 2024)
investigou por que quatro ferramentas SAST perdiam 61,2 % das vulnerabilidades
reais em Java, identificou os padrões ausentes dos rulesets, escreveu regras
novas para o Semgrep e chegou a **44,7 % de detecção — acima dos 38,8 % da união
das quatro ferramentas**. A análise de lacunas *é* a contribuição do artigo.

Há também um ganho de reprodutibilidade que nenhum ruleset do registry oferece.
A ameaça "ruleset não fixado" já está mapeada: o `p/default` muda do lado do
servidor e nada no nosso código percebe. Regra mantida neste repositório é
versionada por commit, congelada por construção, e auditável por quem ler a
monografia.

**O risco é outro, e é grave.** Escrever regra olhando para os casos em que ela
vai ser medida é ajustar ao conjunto de teste. O número resultante não mede a
capacidade da análise sintática de encontrar CWE-22 em código Go — mede a nossa
capacidade de descrever 114 arquivos que já vimos. Uma banca tem razão de não
acreditar num número produzido assim, e teria razão.

Esta change existe para tornar a separação **estrutural em vez de disciplinar**:
não basta pretender não olhar; a esteira tem que impedir.

**Pergunta de pesquisa atendida:** **Q3** diretamente. Parte 2.

## What Changes

- **Configuração composta de rulesets**, absorvida de `ruleset-gosec`: a Fase 1
  passa a aceitar mais de um ruleset, materializado como `--config` repetido,
  com identidade de conjunto insensível à ordem e deduplicação declarada. O
  padrão continua `p/default` sozinho.
- **Ruleset local versionado** em `regras/go/`, carregado por esse mecanismo e
  marcado com procedência própria.
- **Partição de desenvolvimento e de avaliação**, derivada de forma
  determinística e **registrada antes de qualquer regra ser escrita**. Regra é
  escrita olhando apenas a partição de desenvolvimento; o número reportado sai
  apenas da partição de avaliação.
- **Selo de proveniência por regra**: cada regra declara sob qual protocolo foi
  escrita — derivada da definição da CWE e do idioma de Go, sem inspecionar a
  população, ou derivada da partição de desenvolvimento.
- **Relatório que recusa fundir as partições.** A medição emite os dois números
  separados e nunca um número único sobre a população inteira.
- **Metadados obrigatórios**: `metadata.cwe` no formato que o casamento por
  identificador completo aceita, e `metadata.subcategory` declarando se a regra
  afirma vulnerabilidade ou apenas auditoria.

## Capabilities

### New Capabilities

- `regras-locais-go`: ruleset mantido neste repositório, com o protocolo de
  partição que separa o que foi usado para escrever do que é usado para medir, os
  metadados obrigatórios, e o relatório que preserva a separação.
- `ruleset-composto`: configuração de mais de um ruleset simultâneo, união dos
  catálogos, deduplicação de achados e identidade composta do conjunto. **Delta
  recuperada de `ruleset-gosec`**, que a especificou mas não a implementou, e
  ampliada com o que a implementação resolveu: a identidade do conjunto unitário
  é o nome do ruleset (o que preserva o cache já em disco), e ruleset de
  procedência própria é carregado do repositório, nunca do registry.

### Modified Capabilities

- `cache-simbolico`: a versão do ruleset registrada na entrada passa a
  identificar o **conjunto** de rulesets, não um só.
- `ruleset-alcancabilidade`: o conjunto alcançável passa a ser derivado da união
  dos catálogos configurados.

As duas deltas também vêm do arquivo de `ruleset-gosec`, e foram **fundidas** com
o que `semgrep-pro-entre-arquivos` já aplicou nessas capabilities — identidade do
motor —, não substituindo-o. Os eixos são independentes e o requisito final
registra os três: conjunto de rulesets, regra de pareamento e identidade do
motor.

`cache-simbolico` ganha ainda um requisito que só a implementação revelou: a
identidade do conjunto entra no payload da entrada, não no caminho dela, de modo
que medições sob conjunto distinto precisam de armazenamento próprio para não
apagar o cache da rodada.

## Impact

**Dependência de ordem:** nenhuma pendente. `ruleset-gosec` foi arquivado sem
implementar, e o mecanismo de ruleset composto que ele especificava foi
absorvido por esta change.

**Dependência de resultado:** satisfeita. A medição que a autorizava é a da
Tarefa 1 de `ruleset-gosec` — não a da Tarefa 5, que nunca chegou a rodar: o
portão da Tarefa 1.4 parou a change antes. O resultado é negativo e está em
`docs/MAPA-TCC-O-QUE-REESCREVER.md` §3.6.

**Código:** `regras/go/` (novo), `scripts/particionar_avaliacao.py` (novo),
`scripts/medir_regras_locais.py` (novo) — e, pela absorção do ruleset composto,
`src/fase1_semgrep.py`, `src/ruleset.py` e `src/cache_simbolico.py`. A
afirmação anterior de que nada em `src/` mudaria valia enquanto o mecanismo
viesse pronto de outra change; não vale mais.

**Fases tocadas:** 1, indiretamente, por configuração. Nenhuma fase muda de
código.

**Custo de LLM:** zero. Esta change não chama modelo algum.

**Resultados invalidados:** nenhum. O ruleset local entra por configuração
explícita e o padrão continua sem ele.

**Documentação:** `docs/PIPELINE.md`, `docs/SCRIPTS.md`, e obrigatoriamente
`docs/MAPA-TCC-O-QUE-REESCREVER.md` — porque medir com regra própria muda o que
a monografia pode afirmar, e a distinção entre os dois números precisa aparecer
no texto. A redação do `.tex` acontece em **branch separada**, não nesta.

## Não-objetivos

- **Não** escrever regra para CWE que algum ruleset público já cobre
  adequadamente. Para CWE-22 e CWE-918 isso está medido e nenhum cobre; para
  qualquer CWE que venha a entrar como alvo depois, a verificação se repete.
- **Não** reportar número da partição de desenvolvimento como resultado.
- **Não** substituir o `p/default`. O ruleset local soma.
- **Não** apresentar as regras como contribuição de engenharia. A contribuição,
  se houver, é a análise de lacunas — o que o ruleset precisaria ter para
  detectar aquelas fraquezas —, no modelo do Semgrep\*.
- **Não** editar `.tex`.
