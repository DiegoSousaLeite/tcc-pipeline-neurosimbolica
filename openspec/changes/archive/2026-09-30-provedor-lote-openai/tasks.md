## 1. Síncrono e preço

- [x] 1.1 `reasoning_effort: "none"` para `gpt-6-luna` e `gpt-6-sol`, com
      `temperature: 0`. Verificar: teste do payload do Luna e teste de que o
      `gpt-4o-mini` não recebe o parâmetro; testes antigos do provedor passam
      sem edição.
- [x] 1.2 Preço do `gpt-6-luna` (US$ 0,10 / 0,50 por 1 M) na tabela, com data de
      consulta própria no manifesto. Verificar: `modelos_sem_preco` vazio e
      `data_consulta_por_modelo` com o Luna.

## 2. Provedor de lote

- [x] 2.1 `ProvedorOpenAILote`: upload JSONL, criação com `metadata.rotulo`,
      estado, localização por rótulo, recuperação dos arquivos de saída e de
      erro. Verificar: testes contra fornecedor dublado no formato documentado.
- [x] 2.2 `batch_expired` vira `EXPIRADO` sem custo; `status_code` ≠ 200 e
      veredito fora do domínio viram `ERROR`. Verificar: há teste para os três.
- [x] 2.3 Paridade com o síncrono. Verificar: a mesma resposta bruta produz
      `RespostaLLM` idêntica nos dois caminhos.
- [x] 2.4 Rodada inteira pelo runner. Verificar: `executar_matriz` em lote com
      o provedor da OpenAI grava cada veredito na linha certa com respostas em
      ordem inversa.
- [x] 2.5 `scripts/validar_lote.py --modelo`. Verificar: `--help` mostra a
      opção; `docs/SCRIPTS.md` traz o comando com `gpt-6-luna`.

## 3. Validação real (exige `OPENAI_API_KEY` e crédito)

- [x] 3.1 Rodar `scripts/validar_lote.py --modelo gpt-6-luna` em duas etapas
      (`--parar-apos-submissao`, depois retomada). Verificar: o resumo final sai
      `RESULTADO: OK` — 20 requisições com linha, nenhuma duplicada, a inválida
      como `API_ERROR`, uma submissão só — e o custo faturado está registrado
      aqui, com data.
      **Registro 2026-09-30 — `RESULTADO: OK`.** Chamada síncrona prévia
      aceitou `reasoning_effort: "none"` com `temperature: 0`. Lote
      `batch_6abd8f5cb06881909553d5f4e8eb40f2`, 20 requisições (10 casos ×
      baseline/especialista, `results/validacao-luna/`):
      - etapa 1: submetido; `localizar` pelo rótulo achou o mesmo lote na API
        real; processo morto com `os._exit(9)` com o lote `PENDENTE`;
      - etapa 2: retomada pelo `lote.json`, **sem nova submissão** (a OpenAI
        lista um único lote com o rótulo `validacao-luna*`); concluído em
        ~2 min; 20/20 com linha, 0 faltando, 0 duplicada, 0 órfã;
      - erro proposital: o modelo respondeu `"TALVEZ"` e a linha saiu
        `API_ERROR`, nunca `FP`; as outras 19 com veredito válido;
      - linha certa: cada justificativa trata do código do próprio caso
        (`math/rand` no CWE-338, cookie sem `Secure` no CWE-614, `exec` no
        CWE-94…);
      - custo: 15.181 tokens de entrada / 1.853 de saída; tabela US$ 0,0024;
        **faturado US$ 0,0012 ≈ R$ 0,006** (desconto de lote de 50 %).

      **Contraprova síncrona (2026-09-30).** Os mesmos 10 casos, pelo modo
      síncrono, duas vezes (`results/validacao-luna-sincrono`, `-2`):
      - 20/20 com veredito válido; tokens de entrada **idênticos** aos do lote
        nas 19 requisições comparáveis — o prompt é o mesmo nos dois modos;
      - vereditos: síncrono × lote 16/19 iguais; **síncrono × síncrono 17/20**.
        O modelo discorda de si mesmo na mesma taxa em que discorda do lote:
        a diferença é do modelo, não do modo de envio;
      - as trocas caem em casos de fronteira, quase todas no especialista
        (CWE-601 `fix` e `vuln`, CWE-79 do `TP_dataset`);
      - **o `gpt-6-luna` não é determinístico com temperatura 0 e raciocínio
        `none`** — 3 de 20 vereditos mudaram entre duas execuções idênticas.
        A amostra é pequena demais para estimar a taxa; basta para saber que
        ela não é zero. Consequência para a rodada: `rodada-comercial`, D5.
- [x] 3.2 Registrar em `envio-em-lote-comercial` se esta validação fecha as
      tarefas 5.1–5.3 de lá (que nomeiam o `gemini-2.5-flash-lite`).
      Verificar: a decisão dos autores está escrita no `tasks.md` de lá.
      2026-09-30: os autores descartaram o Gemini; a validação com o Luna fecha
      as 5.1–5.3 de lá, e o registro está na seção 5 daquele `tasks.md`.
