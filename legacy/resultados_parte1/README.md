# Resultados da Parte 1 (PoC) — arquivados

Estes CSVs são o registro da **prova de conceito da Parte 1**: um único braço
(`gemini-2.5-flash-lite` + prompt especialista embutido no código) sobre a
população de então.

## Não são comparáveis com os resultados da Parte 2

Três coisas mudaram entre as duas:

1. **A população.** A Parte 2 acrescenta a trilha `TP_dataset` (57 casos com
   `gabarito=vulneravel`), levando o total de 891 para 948 casos.
2. **O cabeçalho do CSV.** Faltam aqui `Num_Locations`, `Ficha_CWE`,
   `Versao_Prompt`, `Hash_Catalogo`, `Tokens_Entrada`, `Tokens_Saida` e
   `Custo_USD`. Sem `Hash_Catalogo` não há como saber qual versão do catálogo
   de CWE produziu cada linha.
3. **O prompt.** O texto era f-string no código, sem versão registrada; hoje
   vem de `prompts/*.md` com hash gravado em cada linha.

Alguns arquivos ainda carregam rótulos de classificação em inglês (`True
Positive (Acerto)`), de uma versão anterior à padronização em português.
`src/metricas.py` lê os dois formatos.

## O que ainda vale

- São evidência válida da PoC e podem ser citados como tal no texto.
- `run_pipeline.py` continua lendo estes arquivos no checkpoint, atribuindo
  suas linhas ao braço `(gemini-2.5-flash-lite, especialista)`. Nenhum deles é
  modificado ou apagado.
- `python src/metricas.py legacy/resultados_parte1/resultados_tcc.csv` funciona.

## Conteúdo

| Arquivo | Origem |
|---|---|
| `resultados_tcc*.csv` | rodadas da Parte 1 que estavam soltas na raiz |
| `poc_resultados.csv` | recorte da PoC inicial |

Os resultados da Parte 2 vão para `results/<run_id>/`, com `manifesto.json`.
