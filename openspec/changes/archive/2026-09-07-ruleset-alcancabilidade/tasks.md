## 1. Módulo de alcançabilidade

- [x] 1.1 Criar `src/ruleset.py` com o carregamento do ruleset hoje embutido em `scripts/medir_pareamento.py` (`carregar_regras`, `_lista`), passando a preservar o campo `languages` de cada regra (D1). Verificar: `python -c "from src.ruleset import carregar_regras; r=carregar_regras(); print(len(r)); print(list(r.items())[0])"` imprime 1074 e mostra CWEs e linguagens de uma regra.
- [x] 1.2 Adicionar `cwes_alcancaveis(linguagem)`, devolvendo o conjunto de números de CWE declarados por regras cuja `languages` inclui a linguagem. Verificar: `python -c "from src.ruleset import cwes_alcancaveis as f; c=f('go'); print(len(c), 338 in c, 284 in c)"` imprime `34 True False`.
- [x] 1.3 Adicionar `cwe_alcancavel(cwe, linguagem)` importando `_numero_cwe` de `src/fase1_semgrep.py`, sem reimplementar a comparação (D2). Verificar: `python -c "from src.ruleset import cwe_alcancavel as f; print(f('CWE-338','go'), f('CWE-77','go'), f('CWE-770','go'))"` — `CWE-77` e `CWE-770` não podem dar o mesmo resultado.
  - **Nota da execução:** em Go os dois dão `False` — nenhuma regra Go do `p/default` declara CWE-77 nem CWE-770, então o par não discrimina nessa linguagem. A discriminação foi verificada em Python, onde o ruleset declara CWE-770 e não CWE-77: `f('CWE-77','python')` → `False`, `f('CWE-770','python')` → `True`. O caso sintético equivalente está em `tests/test_ruleset.py::test_prefixo_ausente_nao_e_inventado`.
- [x] 1.4 Expor a data de obtenção do snapshot do ruleset junto do carregamento, para que a divergência entre registry e Semgrep local fique visível (risco registrado no design). Verificar: `python -c "from src.ruleset import metadados_snapshot; print(metadados_snapshot())"` mostra origem e data.
- [x] 1.5 Fazer a ausência simultânea de cache e de rede levantar erro explícito, nunca devolver conjunto vazio (D4). Verificar: teste da tarefa 2.1 que simula as duas ausências e espera exceção.

## 2. Testes

- [x] 2.1 Escrever `tests/test_ruleset.py` sobre ruleset sintético cobrindo: CWE declarada por regra da linguagem é alcançável; CWE declarada só por regra de outra linguagem não é; `metadata.cwe` como string única e como lista; prefixo de CWE (`CWE-77` contra `CWE-770`); zeros à esquerda (`CWE-077`); tag sem CWE alguma; ausência de cache e rede levanta erro. Verificar: `python -m pytest tests/ -q -k ruleset` passa.
- [x] 2.2 Rodar a suíte inteira para garantir que nada regrediu. Verificar: `python -m pytest tests/ -q` passa integralmente (239 testes antes desta mudança).
  - **Nota da execução:** 251 testes passam, 13 deles novos — a suíte anterior tinha 238, não 239.

## 3. Integração com a medição existente

- [x] 3.1 Apontar `scripts/medir_pareamento.py` para `src/ruleset.py`, removendo a duplicação de `carregar_regras` e `_lista`. Verificar: `grep -n "def carregar_regras\|def _lista" scripts/medir_pareamento.py` não retorna nada.
- [x] 3.2 Manter `_casava_por_substring` onde está, com comentário registrando que descreve a regra ANTIGA e existe para reproduzir as medições já documentadas — não deve ser exportada nem reaproveitada (D3). Verificar: `grep -n "_casava_por_substring" scripts/medir_pareamento.py` retorna a função e o comentário.
- [x] 3.3 Confirmar que a medição continua reproduzindo os números já registrados em `docs/ANALISE-RODADA-2.md`. Verificar: `python scripts/medir_pareamento.py` reporta 16 casos caindo por fallback e 0 por prefixo de CWE.
  - **Nota da execução:** o script hoje reporta 791 "continua emparelhado", 0 por fallback e 0 por prefixo. O motivo não é a refatoração: o cache simbólico foi regravado sob a `VERSAO_PAREAMENTO` 2, e o script mede o cache contra a regra corrente — com o cache novo, nada cai. A entrada que produzia 16/0 (o cache antigo) não existe mais. A equivalência foi verificada rodando `git show HEAD:scripts/medir_pareamento.py` sobre o mesmo cache: saída idêntica, à parte a linha nova do snapshot.

## 4. Documentação

- [x] 4.1 Documentar `src/ruleset.py` em `docs/SCRIPTS.md`: o que responde, de onde vem o ruleset, onde fica o cache e por que a alcançabilidade é por linguagem. Verificar: `grep -n "ruleset.py" docs/SCRIPTS.md` retorna as ocorrências.
- [x] 4.2 Verificar se `README.md` menciona o ruleset ou a cobertura de CWEs e atualizar se mencionar. Verificar: `grep -n "p/default\|ruleset" README.md` — se vazio, a tarefa se encerra sem alteração.
