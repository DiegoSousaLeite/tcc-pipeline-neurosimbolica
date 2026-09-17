"""
comparar_filtro_triagem.py — a distância entre os dois braços (tarefa 5b.5).

O roteiro da apresentação anuncia, sem quantificar, que o desenho de filtro puro
tem um teto: o LLM nunca vê o que o Semgrep não emitiu. Com uma rodada de cada
modo sobre a mesma população, o teto passa a ter número. Este script o calcula.

A armadilha: nem toda métrica é comparável entre os modos
----------------------------------------------------------
As duas rodadas avaliam conjuntos de casos DIFERENTES — é justamente o ponto do
braço de triagem. Comparar as colunas da tabela de braços lado a lado produziria
números que parecem dizer algo e não dizem.

- **TRA (taxa de redução de alertas)** mede a fração da pilha de alertas que o
  LLM descartou. No braço de triagem entram casos que **nunca foram alerta**, e
  incluí-los infla ou desinfla a TRA por composição, não por comportamento. Aqui
  a TRA da rodada de triagem é calculada **só sobre a procedência `alerta`** —
  a pilha real —, e é essa que se compara.

- **Recall do componente** (VP / (VP+FN) entre os que receberam veredito) também
  não é comparável direto: no modo filtro o denominador são os 19 positivos que o
  Semgrep achou; no de triagem, os ~797 da população. São perguntas diferentes, e
  as duas são reportadas, cada uma rotulada.

- **Recall do sistema** é o número comparável, e é o que mede o teto. Ele conta
  como falso negativo todo caso de gabarito vulnerável que **não recebeu veredito
  favorável**, inclusive os que nunca chegaram ao LLM — porque, do ponto de vista
  de quem usa a ferramenta, uma vulnerabilidade que o motor não emitiu e o LLM
  nunca viu é uma vulnerabilidade não reportada, igual a uma que o LLM viu e
  descartou. O denominador é a população vulnerável inteira, idêntico nos dois
  modos.

**A distância entre os dois recalls de sistema é o teto de filtro puro.**

E o que ela mistura, que precisa ser declarado
-----------------------------------------------
A diferença NÃO é atribuível só a "quais casos chegam ao LLM". O modo triagem
também entrega um contexto mais pobre (D7: sem identificador de regra, sem
mensagem do motor, sem a linha apontada), para que a procedência não vaze para o
prompt. Os dois efeitos vêm juntos e o script não os separa — ninguém pode.
A saída diz isso, para que o número não seja citado como se fosse só o primeiro.

USO
    python scripts/comparar_filtro_triagem.py \\
        --filtro results/20260908T094808Z-9a00cb2 \\
        --triagem results/rodada-4-triagem
"""
import argparse
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from src.metricas import (  # noqa: E402
    _categoria_llm,
    _fmt,
    _procedencia,
    _tabela,
    carregar,
)

ALERTA = "alerta"


def _casos_vulneraveis(bracos) -> set:
    """`ID_Caso` distintos de gabarito vulnerável na população da rodada.

    Sobre todas as linhas, e não só as avaliadas: um caso que não recebeu
    veredito continua sendo um caso vulnerável da população, e é exatamente ele
    que o recall do sistema precisa contar como perdido.
    """
    return {linha["ID_Caso"] for br in bracos for linha in br.linhas
            if linha.get("Gabarito") == "vulneravel"}


def recall_do_sistema(braco, universo: int) -> dict:
    """VP sobre a população vulnerável inteira, com os não-avaliados como FN."""
    vp = sum(1 for linha in braco.linhas
             if linha.get("Gabarito") == "vulneravel"
             and _categoria_llm(linha.get("Classificacao_LLM", "")) == "VP")
    return {"VP": vp, "universo": universo,
            "recall": vp / universo if universo else float("nan")}


def recall_do_componente(braco) -> dict:
    """VP / (VP+FN) entre os vulneráveis que receberam veredito válido."""
    c = {"VP": 0, "FN": 0}
    for linha in braco.linhas:
        if linha.get("Gabarito") != "vulneravel":
            continue
        cat = _categoria_llm(linha.get("Classificacao_LLM", ""))
        if cat in c:
            c[cat] += 1
    n = c["VP"] + c["FN"]
    return {"VP": c["VP"], "FN": c["FN"], "n": n,
            "recall": c["VP"] / n if n else float("nan")}


def tra_da_pilha(braco, so_alerta: bool) -> dict:
    """Taxa de redução de alertas, restrita à pilha de alertas real.

    `so_alerta` filtra por procedência. Nas rodadas anteriores à coluna de
    procedência ele é False: lá TODA linha avaliada veio de alerta, por
    construção do modo filtro, e filtrar por uma coluna inexistente zeraria a
    conta.
    """
    c = {"VP": 0, "VN": 0, "FP": 0, "FN": 0}
    for linha in braco.linhas:
        if so_alerta and _procedencia(linha) != ALERTA:
            continue
        cat = _categoria_llm(linha.get("Classificacao_LLM", ""))
        if cat in c:
            c[cat] += 1
    total = sum(c.values())
    return {**c, "total": total,
            "tra": (c["VN"] + c["FN"]) / total if total else float("nan")}


def controles_pareados(bracos_filtro, bracos_triagem) -> dict:
    """Os MESMOS casos, nas duas rodadas: o contraste causal limpo.

    Os positivos que o Semgrep detectou aparecem nas duas rodadas — no modo
    filtro porque o alerta existia, no de triagem porque o emparelhamento tem
    precedência sobre a injeção (D3). São os mesmos `ID_Caso`, o mesmo modelo, o
    mesmo template de prompt e, com `temperature=0` e semente fixa, a mesma
    inferência. **A única coisa que muda entre as duas é o contexto**, que o modo
    triagem normaliza ao código (D7).

    Logo, a diferença de acerto aqui é atribuível ao D7, e não à população nem à
    sorte do modelo. É o experimento controlado que mede o preço da
    normalização — o que nenhuma comparação de recall agregado consegue fazer,
    porque lá as populações diferem.
    """
    por_rotulo = {}
    for rotulo in sorted(set(bracos_filtro) & set(bracos_triagem)):
        f = {ln["ID_Caso"]: ln for ln in bracos_filtro[rotulo].linhas}
        alvo = {ln["ID_Caso"]: ln for ln in bracos_triagem[rotulo].linhas
                if _procedencia(ln) == ALERTA
                and ln.get("Gabarito") == "vulneravel"
                and ln.get("Veredito_LLM") in ("VP", "FP")}
        comuns = [i for i in sorted(alvo)
                  if i in f and f[i].get("Veredito_LLM") in ("VP", "FP")]
        if not comuns:
            continue
        vp_f = sum(1 for i in comuns if f[i]["Veredito_LLM"] == "VP")
        vp_t = sum(1 for i in comuns if alvo[i]["Veredito_LLM"] == "VP")
        perdidos = [i for i in comuns if f[i]["Veredito_LLM"] == "VP"
                    and alvo[i]["Veredito_LLM"] == "FP"]
        ganhos = [i for i in comuns if f[i]["Veredito_LLM"] == "FP"
                  and alvo[i]["Veredito_LLM"] == "VP"]
        por_rotulo[rotulo] = {
            "n": len(comuns), "vp_filtro": vp_f, "vp_triagem": vp_t,
            "perdidos": perdidos, "ganhos": ganhos, "delta": vp_t - vp_f,
        }
    return por_rotulo


def tem_procedencia(bracos) -> bool:
    return any(_procedencia(linha) != "indisponível"
               for br in bracos for linha in br.linhas)


def comparar(dir_filtro: str, dir_triagem: str) -> dict:
    filtro = {br.rotulo: br for br in carregar(dir_filtro)}
    triagem = {br.rotulo: br for br in carregar(dir_triagem)}
    pareados = controles_pareados(filtro, triagem)
    universo = len(_casos_vulneraveis(list(triagem.values())))

    # A rodada de filtro pode ser anterior à coluna de procedência; a de triagem
    # nunca é, porque foi ela que a introduziu.
    filtro_tem_proc = tem_procedencia(list(filtro.values()))

    comuns = sorted(set(filtro) & set(triagem))
    linhas = []
    for rotulo in comuns:
        f, t = filtro[rotulo], triagem[rotulo]
        rf, rt = recall_do_sistema(f, universo), recall_do_sistema(t, universo)
        cf, ct = recall_do_componente(f), recall_do_componente(t)
        tf = tra_da_pilha(f, so_alerta=filtro_tem_proc)
        tt = tra_da_pilha(t, so_alerta=True)
        linhas.append({
            "braco": rotulo,
            "universo_vulneravel": universo,
            "filtro": {"recall_sistema": rf, "recall_componente": cf, "tra": tf},
            "triagem": {"recall_sistema": rt, "recall_componente": ct, "tra": tt},
            "teto": rt["recall"] - rf["recall"],
            "delta_tra": tt["tra"] - tf["tra"],
        })
    return {"universo_vulneravel": universo, "bracos": linhas,
            "controles_pareados": pareados,
            "so_no_filtro": sorted(set(filtro) - set(triagem)),
            "so_na_triagem": sorted(set(triagem) - set(filtro))}


def imprimir(resultado: dict, dir_filtro: str, dir_triagem: str):
    print("=" * 78)
    print("TETO DO DESENHO DE FILTRO PURO — braço filtro vs braço triagem")
    print(f"  filtro : {dir_filtro}")
    print(f"  triagem: {dir_triagem}")
    print(f"  população de gabarito vulnerável: "
          f"{resultado['universo_vulneravel']} casos")
    print("=" * 78)

    if not resultado["bracos"]:
        print("\n  Nenhum braço em comum entre as duas rodadas: não há "
              "comparação pareada a fazer.")
        return
    for faltante, onde in (("so_no_filtro", "só na rodada de filtro"),
                           ("so_na_triagem", "só na rodada de triagem")):
        if resultado[faltante]:
            print(f"\n  [!] braços {onde}, fora da comparação: "
                  f"{', '.join(resultado[faltante])}")

    print("\n--- Recall do SISTEMA (o número comparável) ---")
    print("    VP sobre a população vulnerável inteira. Caso que nunca chegou ao")
    print("    LLM conta como perdido: para quem usa a ferramenta, uma")
    print("    vulnerabilidade não reportada é uma vulnerabilidade não")
    print("    reportada, tenha o LLM opinado ou não.\n")
    _tabela(["Braço", "VP filtro", "Recall filtro", "VP triagem",
             "Recall triagem", "TETO (diferença)"],
            [[b["braco"], b["filtro"]["recall_sistema"]["VP"],
              _fmt(b["filtro"]["recall_sistema"]["recall"]),
              b["triagem"]["recall_sistema"]["VP"],
              _fmt(b["triagem"]["recall_sistema"]["recall"]),
              f"{b['teto']:+.4f}"] for b in resultado["bracos"]])

    print("\n--- Recall do COMPONENTE (perguntas diferentes, não comparar) ---")
    print("    No filtro, denominador = positivos que o Semgrep achou.")
    print("    Na triagem, denominador = positivos da população.\n")
    _tabela(["Braço", "n filtro", "Recall filtro", "n triagem",
             "Recall triagem"],
            [[b["braco"], b["filtro"]["recall_componente"]["n"],
              _fmt(b["filtro"]["recall_componente"]["recall"]),
              b["triagem"]["recall_componente"]["n"],
              _fmt(b["triagem"]["recall_componente"]["recall"])]
             for b in resultado["bracos"]])

    print("\n--- TRA sobre a PILHA DE ALERTAS (procedência `alerta` só) ---")
    print("    Casos injetados nunca foram alerta e ficam de fora, senão a TRA")
    print("    mudaria por composição e não por comportamento.\n")
    _tabela(["Braço", "n filtro", "TRA filtro", "n triagem", "TRA triagem",
             "Diferença"],
            [[b["braco"], b["filtro"]["tra"]["total"],
              _fmt(b["filtro"]["tra"]["tra"]), b["triagem"]["tra"]["total"],
              _fmt(b["triagem"]["tra"]["tra"]), f"{b['delta_tra']:+.4f}"]
             for b in resultado["bracos"]])

    pareados = resultado.get("controles_pareados") or {}
    if pareados:
        print("\n--- CONTROLE PAREADO: o preço da normalização de contexto ---")
        print("    Os MESMOS `ID_Caso` nas duas rodadas (os positivos que o")
        print("    Semgrep detectou), mesmo modelo, mesmo template, semente")
        print("    fixa e temperatura 0. A única variável é o contexto, que o")
        print("    modo triagem normaliza ao código (D7).\n")
        _tabela(["Braço", "n", "VP contexto do alerta", "VP contexto só código",
                 "Delta", "VP perdidos", "VP ganhos"],
                [[r, d["n"], d["vp_filtro"], d["vp_triagem"],
                  f"{d['delta']:+d}", len(d["perdidos"]), len(d["ganhos"])]
                 for r, d in pareados.items()])
        print("\n    Delta muito negativo significa que o braço de triagem")
        print("    daquele prompt NÃO mede 'o mesmo componente sobre mais")
        print("    casos': mede um tratamento mais pobre, e o número agregado")
        print("    dele não é comparável com o do braço de filtro.")

    print("\n  [!] O TETO mistura DOIS efeitos e não os separa: quais casos")
    print("      chegam ao LLM, e quanto contexto cada um traz. O modo triagem")
    print("      entrega contexto mais pobre de propósito (D7), para que a")
    print("      procedência não vaze para o prompt. Citar o número como se")
    print("      fosse só o primeiro efeito seria exagerá-lo.")
    print("=" * 78)


def main():
    ap = argparse.ArgumentParser(
        description="Distância entre o braço de filtro e o de triagem (5b.5).")
    ap.add_argument("--filtro", required=True, metavar="DIR",
                    help="Diretório da rodada do braço de filtro.")
    ap.add_argument("--triagem", required=True, metavar="DIR",
                    help="Diretório da rodada do braço de triagem.")
    args = ap.parse_args()
    imprimir(comparar(args.filtro, args.triagem), args.filtro, args.triagem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
