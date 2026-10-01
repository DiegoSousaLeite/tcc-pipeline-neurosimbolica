"""Rodada comercial (gpt-6-luna) contra os modelos locais, braço a braço.

Fonte dos números de docs/ANALISE-RODADA-COMERCIAL.md.

Só se comparam braços com o MESMO modo de montagem e o MESMO enquadramento de
prompt, porque as Rodadas 4 e 5 mostraram que o enquadramento sozinho muda o
resultado:

- **Filtro** (enquadramento de alerta, catálogo por CWE): Luna contra o
  `qwen2.5-coder:7b` da Rodada 3 e o `gemma2:9b` da Rodada 7 (`baseline`) e 7b
  (`especialista`, catálogo por CWE).
- **Triagem, enquadramento de alerta**: Luna contra o `qwen2.5-coder:7b` da
  Rodada 4 — a única rodada local de triagem com os mesmos prompts.
- **Triagem, enquadramento direto** (`*_direto`): Luna contra o
  `qwen2.5-coder:7b` da Rodada 5 e o `gemma2:9b` da Rodada 6 — a comparação de
  `tab:modelos` (design D7 da change `rodada-comercial`).

As métricas saem sobre os casos que TODOS os braços do bloco julgaram com
veredito válido (comparação pareada), e na triagem separadas por procedência
(`alerta` = pilha real do Semgrep; `gabarito` = positivos injetados), como em
`tab:modelos`. McNemar pareado entre o Luna e cada modelo local, por prompt e
por execução do Luna.

Uso:
    python scripts/comparar_comercial_locais.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.metricas import (_categoria_llm, _metricas, _procedencia,  # noqa: E402
                          carregar, mcnemar)

RP2 = "resultados_parte2"

FILTRO = {
    "luna-1": f"{RP2}/rodada-comercial-luna-filtro",
    "luna-2": f"{RP2}/rodada-comercial-luna-filtro-2",
    "qwen (R3)": f"{RP2}/20260908T094808Z-9a00cb2",
    "gemma (R7/7b)": None,  # montado abaixo: baseline da R7, especialista da 7b
}
TRIAGEM = {
    "luna-1": f"{RP2}/rodada-comercial-luna-triagem",
    "luna-2": f"{RP2}/rodada-comercial-luna-triagem-2",
    "qwen (R4)": f"{RP2}/rodada-4-triagem",
}
TRIAGEM_DIRETO = {
    "luna-1": f"{RP2}/rodada-comercial-luna-triagem-direto",
    "luna-2": f"{RP2}/rodada-comercial-luna-triagem-direto-2",
    "qwen (R5)": f"{RP2}/rodada-5-direto",
    "gemma (R6)": f"{RP2}/rodada-6-gemma",
}
PROMPTS = ("baseline", "especialista")
PROMPTS_DIRETO = ("baseline_direto", "especialista_direto")


def _braco(diretorio, prompt):
    for br in carregar(diretorio):
        if br.prompt == prompt:
            return br
    raise SystemExit(f"sem braço {prompt} em {diretorio}")


def bracos_do_bloco(bloco, prompt):
    saida = {}
    for rotulo, d in bloco.items():
        if d is None:
            d = (f"{RP2}/rodada-7-filtro-gemma" if prompt == "baseline"
                 else f"{RP2}/rodada-7b-filtro-gemma-cwe")
        saida[rotulo] = _braco(d, prompt)
    return saida


def validos(braco):
    """{ID_Caso: linha} dos casos com veredito válido (categoria definida)."""
    return {l["ID_Caso"]: l for l in braco.linhas
            if l.get("Veredito_LLM") in ("VP", "FP")
            and _categoria_llm(l.get("Classificacao_LLM", ""))}


def metricas_em(linhas):
    c = {"VP": 0, "VN": 0, "FP": 0, "FN": 0}
    for l in linhas:
        c[_categoria_llm(l["Classificacao_LLM"])] += 1
    return _metricas(c["VP"], c["VN"], c["FP"], c["FN"])


def _f(v, pct=False):
    if v != v:  # nan
        return "—"
    return f"{100 * v:.2f}%" if pct else f"{v:+.3f}"


def tabela(bracos, comuns, procedencia=None):
    print(f"  {'braço':<15} {'n':>5} {'VP':>4} {'FP':>4} {'FN':>4} {'VN':>4} "
          f"{'Recall':>8} {'Precisão':>9} {'MCC':>7} {'TRA':>8}")
    for rotulo, br in bracos.items():
        v = validos(br)
        linhas = [v[i] for i in comuns
                  if procedencia is None or _procedencia(v[i]) == procedencia]
        m = metricas_em(linhas)
        print(f"  {rotulo:<15} {m['Total']:>5} {m['VP']:>4} {m['FP']:>4} "
              f"{m['FN']:>4} {m['VN']:>4} {_f(m['Recall'], True):>8} "
              f"{_f(m['Precisao'], True):>9} {_f(m['MCC']):>7} "
              f"{_f(m['TRA'], True):>8}")


def mcnemar_restrito(a, b, comuns):
    """McNemar de `src.metricas` sobre o conjunto pareado do bloco."""
    class _Recorte:
        def __init__(self, br):
            v = validos(br)
            self.linhas = [v[i] for i in comuns]
            self.rotulo = br.rotulo
    return mcnemar(_Recorte(a), _Recorte(b))


def bloco(nome, definicao, por_procedencia, prompts=PROMPTS):
    print(f"\n{'=' * 78}\n{nome}\n{'=' * 78}")
    for prompt in prompts:
        bracos = bracos_do_bloco(definicao, prompt)
        comuns = sorted(set.intersection(*(set(validos(b)) for b in bracos.values())))
        print(f"\n[{prompt}] casos pareados (veredito válido em todos): {len(comuns)}")
        if por_procedencia:
            for proc in ("alerta", "gabarito"):
                print(f"\n  procedência = {proc}")
                tabela(bracos, comuns, proc)
        else:
            tabela(bracos, comuns)
        locais = [r for r in bracos if not r.startswith("luna")]
        print("\n  McNemar (acerto), Luna × local:")
        for luna in ("luna-1", "luna-2"):
            for local in locais:
                r = mcnemar_restrito(bracos[luna], bracos[local], comuns)
                print(f"    {luna} × {local:<14} só Luna {r['so_a_acerta']:>4} | "
                      f"só local {r['so_b_acerta']:>4} | p = {r['p_valor']:.4g}")


def main():
    bloco("BRAÇO DE FILTRO (enquadramento de alerta, catálogo por CWE)", FILTRO,
          por_procedencia=False)
    bloco("BRAÇO DE TRIAGEM (enquadramento de alerta) — Luna × Rodada 4", TRIAGEM,
          por_procedencia=True)
    if all(os.path.isdir(d) for d in TRIAGEM_DIRETO.values()):
        bloco("BRAÇO DE TRIAGEM (enquadramento direto) — Luna × Rodadas 5 e 6",
              TRIAGEM_DIRETO, por_procedencia=True, prompts=PROMPTS_DIRETO)


if __name__ == "__main__":
    main()
