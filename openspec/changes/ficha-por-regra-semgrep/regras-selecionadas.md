# Regras selecionadas para ficha própria

Gerado em 2026-09-22 por `python scripts/auditar_regras_ficha.py --minimo 1`, que
lê do cache simbólico só o `check_id` do alerta e a CWE do caso — nunca o código
hidratado. População: as 791 detecções do cache (39 regras distintas).

Critério (D6): pelo menos 5 detecções **e** alvo da regra diferente da API
central da ficha da CWE (ou CWE atendida só pelo fallback).

## Selecionadas (16 fichas, 522 das 791 detecções)

| detecções | CWE | regra | por que a ficha da CWE não serve |
|---|---|---|---|
| 93 | CWE-327 | `missing-ssl-minversion` | ficha ensina `md5`/`sha1` em senha; a regra aponta `tls.Config` sem `MinVersion` |
| 89 | CWE-94 | `dangerous-exec-command` | ficha ensina texto de template vindo de entrada; a regra aponta `exec.Command` não constante |
| 3 | CWE-94 | `dangerous-exec-cmd` | **exceção ao corte de 5**: mesma família da anterior (literal `exec.Cmd`), e a ficha da CWE-94 é inadequada para ela |
| 62 | CWE-665 | `invalid-usage-of-modified-variable` | ficha ensina chave zerada em `aes`/`hmac`; a regra é de corretude (uso de variável no bloco de erro) |
| 13 | CWE-665 | `iterate-over-empty-map` | idem; a regra é de corretude (`range` sobre mapa recém-criado) |
| 54 | CWE-79 | `import-text-template` | ficha ensina `template.HTML`; a regra aponta só o import de `text/template` |
| 53 | CWE-79 | `no-direct-write-to-responsewriter` | ficha ensina `template.HTML`; a regra aponta `w.Write` |
| 12 | CWE-79 | `no-fprintf-to-responsewriter` | a heurística cita `Fprintf`, mas o par de exemplos é todo de `template.HTML` |
| 42 | CWE-319 | `bypass-tls-verification` | ficha ensina URL `http://`; a regra aponta `InsecureSkipVerify: true` |
| 42 | CWE-319 | `use-tls` | ficha ensina URL `http://` em cliente; a regra aponta servidor `http.ListenAndServe` |
| 18 | CWE-115 | `reverseproxy-director` | ficha ensina `strconv.ParseInt` com base 0; a regra aponta `ReverseProxy.Director` |
| 17 | CWE-352 | `websocket-missing-origin-check` | ficha ensina `SameSite` de cookie; a regra aponta `Upgrader.Upgrade` sem `CheckOrigin` |
| 7 | CWE-300 | `grpc-server-insecure-connection` | CWE sem ficha: caía no fallback genérico |
| 6 | CWE-400 | `potential-dos-via-decompression-bomb` | CWE sem ficha: caía no fallback genérico |
| 6 | CWE-489 | `pprof-debug-exposure` | CWE sem ficha: caía no fallback genérico |
| 5 | CWE-89 | `string-formatted-query` | CWE sem ficha: caía no fallback genérico |

## Não selecionadas (≥ 5 detecções, ficha da CWE já descreve a regra)

| detecções | CWE | regra | motivo |
|---|---|---|---|
| 81 | CWE-338 | `math-random-used` | ficha é de `math/rand` |
| 30 / 11 | CWE-328 | `use-of-md5` / `use-of-sha1` | ficha é de hash rápido em segredo |
| 27 | CWE-614 | `cookie-missing-secure` | ficha é de `http.Cookie` sem `Secure` |
| 25 | CWE-601 | `open-redirect` | ficha é de `http.Redirect` com destino externo |
| 19 | CWE-470 | `unsafe-reflect-by-name` | ficha é de `reflect.MethodByName` |
| 18 | CWE-681 | `string-to-int-signedness-cast` | ficha é de conversão estreitante de inteiro |
| 15 | CWE-1004 | `cookie-missing-httponly` | ficha é de `http.Cookie` sem `HttpOnly` |
| 13 | CWE-667 | `missing-unlock-before-return` | ficha é de `Unlock` sem `defer` |

As regras com menos de 5 detecções continuam na ficha da CWE (ou no fallback).

## Fontes usadas na escrita

- YAML oficial de cada regra: `semgrep/semgrep-rules` (branch `develop`) e
  `trailofbits/semgrep-rules` (branch `main`), baixados em 2026-09-22 — padrões,
  exclusões (`pattern-not`) e mensagem.
- Documentação da stdlib de Go e release notes: padrão de TLS 1.2 no cliente
  desde Go 1.18 e no servidor desde Go 1.22 (conferido em go.dev/doc/go1.18 e
  go.dev/doc/go1.22); remoção de cabeçalhos hop-by-hop depois do `Director` na
  documentação de `httputil.ReverseProxy`; checagem padrão de origem do
  `gorilla/websocket` quando `CheckOrigin` é nil.
- Nenhum trecho do cache de fontes, do cache simbólico, do dataset ou de CSV.
  O teste `test_nenhum_exemplo_reproduz_trecho_das_amostras` confere isso
  (nenhum par de linhas distintivas consecutivas dos exemplos aparece nos
  arquivos das amostras).

## Autoria e ressalva de contaminação (tarefa 4.1)

As 16 fichas de regra e a reescrita das 15 heurísticas de CWE foram redigidas
com o Claude Code, a pedido dos autores, em 2026-09-22.

Ressalva de contaminação: quem redigiu as fichas leu, durante o diagnóstico
que motivou esta mudança, quatro contextos hidratados de amostras do argo-cd
(`InteractiveEdit` com `$EDITOR`, `secretToRepository`, `getResourceTree`, o
handler de logout). As fichas evitam deliberadamente essas construções — o FP de
`dangerous-exec-command` usa lista fixa, não editor de variável de ambiente; os
exemplos das regras da Trail of Bits usam funções e fluxos diferentes — e o
teste de não contaminação passa. A exposição fica declarada mesmo assim.

## Versões dos modelos locais (tarefa 5.1)

| modelo | digest local | referência | confere |
|---|---|---|---|
| `qwen2.5-coder:7b` | `dae161e27b0e` | rodada `20260908T094808Z-9a00cb2` (`dae161e27b0e…`) | sim |
| `gemma2:9b` | `ff02c3702f32` | Rodada 6 (`ff02c3702f32`) | sim |

Semente 42, temperatura 0, `num_ctx` 8192 e `num_predict` 512 são os padrões do
provedor, iguais aos da referência. Ruleset `p/default` (sem `SEMGREP_CONFIG` no
ambiente).
