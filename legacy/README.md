# Legacy — Pipeline CodeQL (anterior)

Este diretório preserva os **resultados** do fluxo original baseado em CodeQL
(`resultados_parte1/`), citados pela monografia.

O **código** daquele fluxo vive apenas no histórico do Git, não em cópia aqui:

```bash
git show HEAD:main.py               # orquestrador original (5 fases via CodeQL)
git show HEAD:src/fase1_codeql.py   # Fase 1: clone + database create + analyze → SARIF
```

## Por que foi arquivado

O pivô para Semgrep ocorreu por três razões verificadas empiricamente:

1. **Alinhamento baixo com o dataset**: no piloto, apenas ~1/48 alertas do
   CodeQL casavam com os FPs marcados no dataset (que são de origem Semgrep).
2. **Compatibilidade Windows**: o Semgrep roda nativamente sem build step;
   o CodeQL exige compilação Go que falha em repositórios com dependências
   complexas.
3. **Reconhecimento de CWE**: o Semgrep é *sanitizer-aware* e localiza o
   alerta na linha exata, enquanto o CodeQL emite trilhas de fluxo que
   raramente correspondem ao arquivo apontado pelo dataset.

O fluxo Semgrep atual está em `src/` e `run_pipeline.py`.
