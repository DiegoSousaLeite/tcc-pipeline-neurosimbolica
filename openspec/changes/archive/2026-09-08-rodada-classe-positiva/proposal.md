## Why

As três mudanças anteriores entregam ferramenta, filtro e caminho na pipeline —
mas nenhuma delas produz um número. A classe positiva continua com **1 caso
chegando ao LLM**, e `src/metricas.py` continua emitindo o aviso de poder
estatístico limitado.

Enquanto isso, `Recall`, `Precisão`, `F1`, `MCC` e `TFN` não podem ser reportados:
com uma amostra, o resultado só pode ser 0% ou 100%, e o acaso explica qualquer um
dos dois.

**Pergunta de pesquisa atendida:** a metade não respondida da **Q2** —
*"Em que proporção a arquitetura neuro-simbólica consegue reduzir o volume de
falsos positivos **sem introduzir falsos negativos**?"* (`introducao.tex:38`). A
primeira metade já está respondida (TRA 0,9874; McNemar p < 0,0001). Também
dependem desta rodada o objetivo específico 5 (*"retenção de vulnerabilidades
reais"*, `introducao.tex:54`) e a meta de `metodologia.tex:309` (*"manter a TFN
próxima a zero"*).

**Depende de:** `ruleset-alcancabilidade`, `colheita-cwe-alcancavel` e
`trilha-tp-alcancavel`.

## What Changes

Esta mudança é de **execução e verificação**, não de código de produto.

- **Colheita executada** com o filtro ligado, com inspeção do relatório antes de
  prosseguir — a reconstrução de pares é cara em rede e tempo, e a decisão de
  alvo depende do que a colheita revelar.
- **Pares reconstruídos** com `fetch_raso.py` e `tp_reconstruct.py`, e cache de
  fontes preenchido para que a rodada não dependa de rede na Fase 1.
- **Rodada nova** sob `run_id` próprio, braço local, baseline e especialista.
- **Critério de aceite objetivo:** o aviso de poder estatístico limitado
  desaparecer, ou seja, ao menos **30 casos vulneráveis com veredito válido do
  LLM** — medido na chegada ao LLM, não na colheita.
- **Rendimento isolado por procedência**, para saber se o ganho veio da colheita
  filtrada ou apenas do reaproveitamento.
- **Registro técnico** em `docs/ANALISE-RODADA-3.md`, no formato da Rodada 2.

## Capabilities

### New Capabilities
- `suficiencia-classe-positiva`: definição de quando a classe positiva é
  suficiente para sustentar conclusão, medida onde importa — na chegada ao LLM —
  e verificação de que a amostra obtida atende ao limiar.

### Modified Capabilities
<!-- Nenhuma. `metricas-comparativas` já emite o aviso de poder estatístico
     limitado com o limiar de 30; esta mudança o adota como critério de aceite,
     sem alterar requisito algum. -->

## Impact

**Código**
- Nenhuma alteração em `src/` ou `run_pipeline.py`. Esta mudança **executa** o
  que as anteriores construíram.

**Dados** (artefatos de fase 0, não versionados)
- Pool da colheita filtrada — gerado
- `cache/` — cresce com os alvos novos; chave imutável, nada invalida
- `cache_simbolico/` — a classe negativa continua servida do cache; só os
  vulneráveis novos pagam varredura de Semgrep
- `tp_pairs.json` e `tp_pairs_osv.json` — **preservados**

**Resultados**
- `results/<run_id_novo>` — novo
- `results/20260731T140000Z-af9bc32` e `results/20260730T180648Z-14d6af8` —
  **preservadas e ainda válidas**. Nenhuma é invalidada: a população **cresce**,
  não muda de definição.
- A rodada nova **não é comparável caso a caso** com as anteriores, porque a
  população difere. A comparação legítima é entre braços dentro dela.

**Custo de LLM**
- **Zero em dinheiro e em cota.** O braço é local (`ollama:qwen2.5-coder:7b`),
  sem API e sem consumo do tier do Gemini.

**Tempo e rede**
- Colheita da OSV: dezenas de minutos, dominadas por rede.
- Rodada: a parte neural deve ficar abaixo da anterior (cerca de 1h10 para 948
  casos), mais a varredura de Semgrep dos alvos novos.

## Não-objetivos

- **Não escrever nada no TCC.** Nenhum arquivo `.tex` é tocado. Responder à Q2 no
  texto, registrar os 70,1% no capítulo de limitações e fechar o item A3 da banca
  fica para depois, com os números em mãos. O único documento produzido aqui é o
  registro técnico da rodada.
- **Não alterar código de produto.** Se algum defeito aparecer durante a
  execução, ele vira mudança própria em vez de ser corrigido aqui de passagem.
- **Não alterar prompts, modelo, semente, métricas ou a classe negativa.**
- **Não remover os casos de CWE inalcançável.**

## Onde isto se encaixa no TCC

Parte 2 — é a rodada que produz os números da bateria completa de métricas. Se o
critério de aceite for atingido, `Recall`, `F1`, `MCC` e `TFN` do eixo neural
passam a ser reportáveis pela primeira vez.
