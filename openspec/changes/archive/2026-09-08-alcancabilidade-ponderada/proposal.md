## Why

O critério de alcançabilidade é **binário**: uma CWE é alcançável se ao menos uma
regra do ruleset a declara. A Rodada 3 mostrou que isso superestima a cobertura.

Medido sobre os 690 pares da trilha `TP_alcancavel`
(`docs/ANALISE-RODADA-3.md` §3):

| grupo de CWEs | pares | detecções | taxa |
|---|---|---|---|
| com ao menos uma regra `subcategory: vuln` | 354 | 17 | **4,80 %** |
| só com regras `subcategory: audit` | 336 | **1** | **0,30 %** |

**Dezesseis vezes de diferença**, e o critério que a separa é campo declarado pelo
próprio Semgrep: `audit` significa "olhe isto", `vuln` significa "isto é uma
vulnerabilidade". Metade do orçamento de colheita foi gasta em CWEs cujas regras a
ferramenta nunca afirmou serem detectoras.

Contagem de regras **não** prevê (r = +0,16): CWE-327 tem 8 regras Go e 0 %;
CWE-601 tem 1 e 30 %. O que prevê é o grau declarado da regra.

**Pergunta de pesquisa atendida:** dá suporte quantitativo à distinção entre *"a
ferramenta declara cobrir"* e *"a ferramenta encontra"*, que é o achado central da
Rodada 3 e material direto da discussão do TCC.

## What Changes

- **Grau ordinal de alcançabilidade por CWE**, em três níveis derivados de campos
  declarados do ruleset (`metadata.subcategory` e `mode`), com as taxas medidas:

  | grau | critério | taxa medida |
  |---|---|---|
  | `alta` | ao menos uma regra `vuln` que **não** é de *taint* | 11,30 % |
  | `media` | ao menos uma regra `vuln`, todas de *taint* | 1,67 % |
  | `baixa` | só regras `audit` | 0,30 % |

- **Relatório da colheita passa a exibir o grau** ao lado da contagem, para que o
  rendimento seja previsível **antes** de gastar rede e disco.
- **Restrição por grau é opcional e explícita** (`--grau-minimo`). O padrão não
  muda: continua aceitando toda CWE alcançável.
- **Comando de validação** que recalcula a separação sobre os CSVs de qualquer
  rodada, permitindo testar o critério **fora da amostra** que o gerou.

## Capabilities

### Modified Capabilities
- `ruleset-alcancabilidade`: acrescenta o grau ordinal e a leitura dos campos que
  o sustentam, preservando a consulta binária existente.

### New Capabilities
- `validacao-do-grau`: o procedimento que mede a separação entre graus sobre uma
  rodada, sem o qual o grau seria afirmação não verificada.

## Impact

**Código**
- `src/ruleset.py` — grau ordinal e leitura de `subcategory` / `mode`
- `scripts/osv_harvest_go.py` — grau no relatório; `--grau-minimo` opcional
- `scripts/analise_rodada.py` — seção de validação do grau
- `tests/test_ruleset.py` — cobertura do grau

**Dados e resultados**
- **Nenhum artefato é regenerado e nenhuma rodada é reinterpretada.** A população
  da Rodada 3 continua definida pelo critério binário sob o qual foi colhida.

**Custo**
- Zero em rede e LLM. O ruleset já está em cache.

## Não-objetivos

- **Não redefinir a população de nenhuma rodada existente.** O grau é diagnóstico
  e prospectivo; aplicá-lo retroativamente trocaria o denominador de um recall já
  publicado.
- **Não excluir CWEs da colheita por padrão.** Colher só onde a ferramenta acerta
  mediria a seleção, não a ferramenta.
- **Não substituir a consulta binária.** `cwe_alcancavel` continua sendo a
  fronteira que a Fase 1 respeita.
- **Não tocar em arquivo `.tex`.**

## Onde isto se encaixa no TCC

Parte 2 — instrumentação da discussão. Não produz rodada nova; produz o
argumento, quantificado, de por que restringir a colheita às CWEs declaradas
cobertas não abriu o funil.
