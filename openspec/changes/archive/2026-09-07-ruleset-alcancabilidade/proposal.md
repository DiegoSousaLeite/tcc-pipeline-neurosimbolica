## Why

Nada no projeto sabe responder à pergunta *"o motor simbólico tem regra para esta
CWE nesta linguagem?"* — e é dela que dependem as três mudanças seguintes.

Hoje a lógica existe em dois lugares, nenhum reaproveitável:

- `scripts/medir_pareamento.py` carrega o ruleset do registry e extrai
  `metadata.cwe`, mas **descarta o campo `languages`** e compara por
  `_casava_por_substring`, que é a regra **antiga** de casamento (a que fazia
  `CWE-77` casar com `CWE-770`), mantida ali só para medir o histórico.
- `src/fase1_semgrep.py` tem a comparação correta (`_numero_cwe`,
  `_cwe_nas_tags`, `VERSAO_PAREAMENTO = 2`), mas opera sobre as tags de um alerta
  já emitido — não sobre o catálogo de regras.

Sem um lugar único e correto, cada consumidor novo reimplementa, e a chance de
reintroduzir o casamento por substring recém-corrigido é alta.

**Pergunta de pesquisa atendida:** nenhuma diretamente — é **infraestrutura**,
pré-requisito das mudanças `colheita-cwe-alcancavel`, `trilha-tp-alcancavel` e
`rodada-classe-positiva`, que juntas atacam a metade não respondida da Q2.

Motivação de fundo em `docs/ANALISE-RODADA-2.md`: 70,1% dos casos vulneráveis têm
CWE que nenhuma regra Go do `p/default` declara.

## What Changes

- **Módulo novo `src/ruleset.py`**, com o conjunto de CWEs que o ruleset corrente
  alcança numa dada linguagem, derivado do próprio ruleset e não de lista fixa.
- **Preservação do campo `languages`** ao carregar as regras — hoje descartado.
  Uma CWE coberta apenas por regras de Python não é alcançável num arquivo `.go`.
- **Casamento por identificador completo**, reaproveitando a comparação já
  vigente na Fase 1 em vez de reimplementá-la.
- **`scripts/medir_pareamento.py` passa a consumir o módulo**, mantendo
  `_casava_por_substring` onde está: aquela função descreve a regra antiga e
  continua necessária para reproduzir as medições já registradas.

## Capabilities

### New Capabilities
- `ruleset-alcancabilidade`: consulta ao catálogo de regras do motor simbólico
  para determinar quais CWEs ele é capaz de detectar numa dada linguagem.

### Modified Capabilities
<!-- Nenhuma. A mudança extrai e corrige lógica hoje embutida em script, sem
     alterar requisito de nenhuma capacidade existente. -->

## Impact

**Código**
- `src/ruleset.py` — novo
- `scripts/medir_pareamento.py` — passa a importar do módulo; `carregar_regras`
  preserva `languages`
- `src/fase1_semgrep.py` — **sem alteração**, apenas importado

**Rede**
- O módulo busca o ruleset em `https://semgrep.dev/c/<config>` e cacheia em
  `cache_simbolico/_regras_p_default.json`. Com o cache presente, funciona
  offline.

**Resultados**
- Nenhum resultado é invalidado. Nenhuma rodada é reexecutada. A mudança não
  toca em população, prompts, modelo nem métricas.

**Custo de LLM**
- Zero. Não há chamada de LLM nesta mudança.

## Não-objetivos

- **Não fixar o ruleset por versão.** A ameaça de reprodutibilidade registrada em
  `docs/ANALISE-RODADA-2.md` §6.1 — `p/default` é nome de coleção, não versão, e
  o cache não detecta a troca — é real, mas merece mudança própria.
- **Não alterar a Fase 1.** A regra de pareamento fica exatamente como está.
- **Não usar o módulo em lugar nenhum além de `medir_pareamento.py`.** Os
  consumidores reais vêm nas mudanças seguintes.

## Onde isto se encaixa no TCC

Parte 2, como infraestrutura. Não produz número para a monografia por si só.
