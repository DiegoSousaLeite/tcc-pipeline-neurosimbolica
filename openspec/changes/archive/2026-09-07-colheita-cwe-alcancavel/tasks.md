## 1. Filtro na colheita

- [x] 1.1 Fazer `extrai()` de `scripts/osv_harvest_go.py` percorrer TODAS as CWEs de `database_specific.cwe_ids` em vez de ficar com `cwes[0]`, devolvendo a que casou com o conjunto alcançável (D3). Verificar: teste da tarefa 2.1 com vuln declarando `["CWE-284","CWE-338"]` registra `CWE-338`.
- [x] 1.2 Aplicar o filtro de alcançabilidade em `extrai()`, usando `cwe_alcancavel` de `src/ruleset.py`, recusando candidata sem nenhuma CWE coberta (D1). Verificar: teste da tarefa 2.1 com vuln de `CWE-284` retorna recusa.
- [x] 1.3 Recusar vulnerabilidade que não declara CWE alguma, em vez de aceitá-la com `"CWE-desconhecida"` como hoje. Verificar: teste da tarefa 2.1 confirma a recusa e a ausência de `CWE-desconhecida` na saída.
- [x] 1.4 Contabilizar cada recusa sob a CWE que a causou, para distinguir "a OSV tem pouca coisa" de "o filtro recusa tudo" (D2). Verificar: execução com `--max-scan` pequeno mostra o contador preenchido.
- [x] 1.5 Substituir o texto "Todos os tipos de CWE" no cabeçalho do script pela descrição do filtro, registrando por que ele existe (70,1% da classe positiva era indetectável por construção). Verificar: `grep -n "Todos os tipos de CWE" scripts/osv_harvest_go.py` não retorna nada.
- [x] 1.6 Gravar a saída em arquivo próprio, sem sobrescrever `tp_fixes_osv.json` (D4). Verificar: após execução curta, `git status` e `sha256sum` mostram `tp_pairs.json` e `tp_pairs_osv.json` inalterados.

## 2. Testes da colheita

- [x] 2.1 Escrever `tests/test_colheita.py` com a API da OSV e o ruleset dublados, cobrindo: CWE alcançável aceita; CWE inalcançável recusada; várias CWEs com uma alcançável registra a que casou; nenhuma CWE declarada é recusa; filtros pré-existentes (sem commit de fix, repo fora do GitHub) continuam valendo. Verificar: `python -m pytest tests/ -q -k colheita` passa.
- [x] 2.2 Rodar a suíte inteira. Verificar: `python -m pytest tests/ -q` passa integralmente.

## 3. Relatório da colheita

- [x] 3.1 Acrescentar ao bloco `=== RESUMO ===` a distribuição de CWEs aceitas e a contagem de recusadas por CWE. Verificar: execução com `--max-scan` pequeno imprime as duas listas.
- [x] 3.2 Incluir no relatório a data de obtenção do snapshot do ruleset, vinda de `src/ruleset.py`, para tornar visível a divergência possível entre registry e Semgrep local. Verificar: a saída mostra a data.
- [x] 3.3 Tornar explícita a colheita vazia, em vez de gravar arquivo vazio em silêncio. Verificar: execução com filtro que recusa tudo imprime aviso claro e não deixa arquivo vazio sem menção.

## 4. Reaproveitamento dos pares já colhidos

- [x] 4.1 Escrever `scripts/pares_alcancaveis.py`, somente leitura, que avalia `tp_pairs.json` e `tp_pairs_osv.json` contra o conjunto alcançável e lista os pares aproveitáveis com a CWE que os torna alcançáveis (D5). Verificar: a execução reporta 4 em `tp_pairs.json` e 13 em `tp_pairs_osv.json`, 17 no total.
- [x] 4.2 Confirmar que a execução não escreve nos pools. Verificar: `sha256sum tp_pairs.json tp_pairs_osv.json` antes e depois coincidem.

## 5. Documentação

- [x] 5.1 Atualizar `docs/SCRIPTS.md`: contrato novo de `scripts/osv_harvest_go.py` (filtro, relatório, CWE registrada é a que casou, saída em arquivo próprio) e o script `scripts/pares_alcancaveis.py`. Verificar: `grep -n "pares_alcancaveis\|alcanç" docs/SCRIPTS.md` retorna as ocorrências.
- [x] 5.2 Registrar em `docs/PIPELINE.md`, na seção de preparação de dados, por que a colheita passou a filtrar — citando os 70,1% de `docs/ANALISE-RODADA-2.md`. Verificar: `grep -n "alcanç" docs/PIPELINE.md` retorna as ocorrências.
