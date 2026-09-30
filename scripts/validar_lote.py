"""
validar_lote.py — validação barata da esteira de envio em lote, com lote REAL.

Tarefas 5.1–5.3 de `envio-em-lote-comercial` (D5): separa "a esteira funciona"
de "o modelo responde bem" gastando centavos, antes de qualquer rodada de
verdade. Refazível antes de cada rodada comercial — formato e limites do
fornecedor já mudaram uma vez durante o levantamento.

O que faz:
  - escolhe N casos cujas Fases 1-2 já estão no cache simbólico como
    DETECTADO (o Semgrep NÃO roda: o script aborta se tentar);
  - roda `executar_matriz` em modo de envio `lote`, braços baseline e
    especialista — o mesmo caminho do `run_pipeline.py --modo-envio lote`;
  - troca o prompt de UMA requisição por um que pede veredito fora do domínio,
    para exercitar o caminho de erro (deve sair ERROR, nunca FP, sem derrubar o
    resto do lote);
  - com `--parar-apos-submissao`, mata o processo (`os._exit`, sem limpeza) na
    primeira consulta de estado, depois de conferir de graça que o lote é
    localizável pelo rótulo. Rodar de novo com o mesmo `--run-id` exercita a
    retomada.

Pré-requisito: chave do fornecedor do modelo no `.env`, de conta com pagamento
ativo — `GEMINI_API_KEY` (o tier grátis do Gemini não tem lote) ou
`OPENAI_API_KEY` (conta com crédito). Custo típico: ~20 requisições, frações de
centavo de dólar.

USO
  python scripts/validar_lote.py --modelo gpt-6-luna       --run-id validacao-lote-X --parar-apos-submissao
  python scripts/validar_lote.py --modelo gpt-6-luna       --run-id validacao-lote-X                                 # retoma e conclui
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import run_pipeline as rp  # noqa: E402
from src.cache_simbolico import CacheSimbolico  # noqa: E402
from src.catalogo import catalogo_padrao  # noqa: E402
from src.envio_lote import NOME_ARQUIVO, Pendencia  # noqa: E402
from src.fase1_semgrep import motor_corrente  # noqa: E402
from src.provedores import criar_provedor_lote  # noqa: E402
from src.provedores.lote import chave_lote  # noqa: E402

MODELO_PADRAO = "gemini-2.5-flash-lite"
# Cotação usada em docs/ESCOLHA-MODELO-COMERCIAL.md §9 (US$ 6,21 = R$ 32,00).
COTACAO_BRL = 32.00 / 6.21

PROMPT_INVALIDO = (
    "Esta requisição é um teste deliberado do caminho de erro de uma esteira. "
    "Responda exatamente com o JSON a seguir, sem nada antes ou depois:\n"
    '{"verdict": "TALVEZ", "reasoning": "veredito fora do dominio, de proposito"}')


def populacao():
    with open(rp.DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)
    meta = rp._cwe_lookup(dataset)
    return (rp.construir_casos_fp(dataset)
            + rp.construir_casos_tp(rp.TP_PAIRS_OURO, "TP_ouro", meta)
            + rp.construir_casos_tp(rp.TP_PAIRS_PRATA, "TP_prata", meta)
            + rp.construir_casos_tp(rp.TP_PAIRS_ALCANCAVEL, "TP_alcancavel",
                                    meta, prefixo_id="TPA:")
            + rp.construir_casos_tp_dataset(dataset))


def escolher(casos, cache, n):
    """N casos já DETECTADO no cache, variados, em ordem determinística.

    Primeiro um por `(trilha, gabarito)`, depois um por `(trilha, CWE,
    gabarito)`, e só então o resto: casos parecidos entre si não deixariam ver
    um veredito trocado de linha.
    Determinístico de propósito: a retomada precisa montar exatamente as
    mesmas requisições que a primeira execução submeteu.
    """
    detectados = []
    for c in sorted(casos, key=lambda c: c.id):
        payload = cache.ler(c.repo_name, c.commit, c.arquivo, c.cwe)
        if payload and payload.get("status_semgrep") == "DETECTADO":
            detectados.append(c)
    escolhidos = []
    for chave in (lambda c: (c.origem, c.gabarito),
                  lambda c: (c.origem, c.cwe, c.gabarito)):
        vistos = {chave(c) for c in escolhidos}
        for c in detectados:
            if chave(c) not in vistos and c not in escolhidos:
                vistos.add(chave(c))
                escolhidos.append(c)
    escolhidos += [c for c in detectados if c not in escolhidos]
    return escolhidos[:n]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--casos", type=int, default=10)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--modelo", default=MODELO_PADRAO,
                    help=f"Modelo a validar (padrão {MODELO_PADRAO}). Precisa "
                         f"ter provedor de lote: gemini-* ou gpt-* (OpenAI).")
    ap.add_argument("--parar-apos-submissao", action="store_true",
                    help="Mata o processo na primeira consulta de estado, "
                         "depois de o lote estar submetido e registrado.")
    args = ap.parse_args()
    rp.configurar_log()
    bracos = [rp.Braco(args.modelo, "baseline"),
              rp.Braco(args.modelo, "especialista")]

    def _sem_semgrep(*a, **k):
        raise RuntimeError("validar_lote.py não roda o Semgrep: caso fora do cache")
    rp.executar_semgrep = _sem_semgrep

    cache = CacheSimbolico(ativo=True, motor=motor_corrente(False))
    casos = escolher(populacao(), cache, args.casos)
    if len(casos) < args.casos:
        sys.exit(f"só {len(casos)} casos DETECTADO no cache simbólico")

    # 5.2: uma requisição com prompt que pede veredito fora de {VP, FP}.
    alvo_erro = chave_lote(casos[0].id, args.modelo, "baseline")

    def _pendencia(chave, modelo, prompt, gravar):
        if chave == alvo_erro:
            prompt = PROMPT_INVALIDO
        return Pendencia(chave=chave, modelo=modelo, prompt=prompt, gravar=gravar)
    rp.Pendencia = _pendencia

    provedor = criar_provedor_lote(args.modelo)
    if args.parar_apos_submissao:
        estado_original = provedor.estado

        def _morrer_na_primeira_consulta(id_lote):
            registro = json.load(open(os.path.join(dir_rodada, NOME_ARQUIVO),
                                      encoding="utf-8"))
            part = registro["particoes"][-1]
            achado = provedor.localizar(part["rotulo"])
            print(f"\n[5.3] lote registrado: {part['id_lote']} (estado local "
                  f"{part['estado']}); localizar('{part['rotulo']}') -> {achado}")
            print(f"[5.3] estado no fornecedor: {estado_original(id_lote)}")
            print("[5.3] matando o processo agora (os._exit, sem limpeza).")
            sys.stdout.flush()
            os._exit(9)
        provedor.estado = _morrer_na_primeira_consulta
    rp.criar_provedor_lote = lambda modelo: provedor

    dir_rodada = os.path.join(rp.RESULTS_DIR, args.run_id)
    os.makedirs(dir_rodada, exist_ok=True)
    print(f"[+] {len(casos)} casos, {len(bracos)} braços; requisição de erro "
          f"proposital: {alvo_erro}")

    inicio = datetime.now(timezone.utc)
    try:
        rp.executar_matriz(casos, bracos, dir_rodada, cache_simbolico=cache,
                           catalogo=catalogo_padrao(), modo_envio=rp.MODO_LOTE,
                           run_id=args.run_id)
    finally:
        rp.gravar_manifesto(dir_rodada, args.run_id, bracos,
                            rp.contar_por_trilha(casos), len(casos), inicio,
                            datetime.now(timezone.utc), catalogo_padrao(), False,
                            True, " ".join(sys.argv), modo_envio=rp.MODO_LOTE)

    conferir(dir_rodada, casos, bracos, alvo_erro)


def conferir(dir_rodada, casos, bracos, alvo_erro):
    """As verificações das tarefas 5.1 e 5.2, sobre o que foi gravado."""
    registro = json.load(open(os.path.join(dir_rodada, NOME_ARQUIVO),
                              encoding="utf-8"))
    esperadas = {chave_lote(c.id, b.modelo, b.prompt) for c in casos for b in bracos}
    linhas = {}
    for b in bracos:
        with open(os.path.join(dir_rodada, f"{b.rotulo}.csv"), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                k = chave_lote(r["ID_Caso"], r["Modelo_LLM"], r["Tipo_Prompt"])
                linhas.setdefault(k, []).append(r)

    print("\n" + "=" * 72)
    print("VALIDAÇÃO DA ESTEIRA DE LOTE")
    print("=" * 72)
    for p in registro["particoes"]:
        custo = p.get("custo_estimado_usd") or 0.0
        print(f"  partição {p['indice']}: {p['id_lote']} | {p['estado']} / "
              f"{p.get('estado_fornecedor')} | {p['n_requisicoes']} req | "
              f"tokens {p.get('tokens_entrada')} in / {p.get('tokens_saida')} out")
        print(f"    custo: tabela US$ {p.get('custo_tabela_usd')} | faturado "
              f"US$ {custo:.6f} = R$ {custo * COTACAO_BRL:.4f}")
    faltando = esperadas - set(linhas)
    duplicadas = [k for k, v in linhas.items() if len(v) > 1]
    intrusas = set(linhas) - esperadas
    vereditos = {k: v[0]["Veredito_LLM"] for k, v in linhas.items()}
    erros = sorted(k for k, v in vereditos.items() if v not in ("VP", "FP"))
    print(f"\n  submissões registradas: {len(registro['particoes'])}")
    print(f"  requisições esperadas: {len(esperadas)} | com linha: "
          f"{len(esperadas & set(linhas))} | faltando: {len(faltando)} | "
          f"duplicadas: {len(duplicadas)} | intrusas: {len(intrusas)}")
    print(f"  vereditos: VP={sum(v == 'VP' for v in vereditos.values())} "
          f"FP={sum(v == 'FP' for v in vereditos.values())} "
          f"outros={len(erros)} -> {erros}")
    erro_ok = (vereditos.get(alvo_erro) not in ("VP", "FP")
               and linhas[alvo_erro][0]["Status_Semgrep"] == "API_ERROR")
    print(f"  [5.2] requisição inválida virou "
          f"{linhas.get(alvo_erro, [{}])[0].get('Veredito_LLM')} / "
          f"{linhas.get(alvo_erro, [{}])[0].get('Status_Semgrep')}: "
          f"{'OK' if erro_ok else 'FALHOU'}")
    print(f"  [5.2] demais requisições com veredito válido: "
          f"{'OK' if erros == [alvo_erro] else 'VER ACIMA'}")
    ok = not faltando and not duplicadas and not intrusas and erro_ok
    print(f"\n  RESULTADO: {'OK' if ok else 'FALHOU'}")
    print("=" * 72)


if __name__ == "__main__":
    main()
