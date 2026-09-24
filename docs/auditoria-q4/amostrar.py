"""Sorteia a amostra da auditoria qualitativa da Q4 (ver CRITERIO.md).

Reproduzível: `python docs/auditoria-q4/amostrar.py` gera `amostra.csv` nesta
pasta, com o contexto exato que cada veredito recebeu (lido do cache simbólico)
e colunas vazias para a classificação.
"""
import csv
import json
import os
import random
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, BASE)

import run_pipeline as rp  # noqa: E402
from src.cache_simbolico import CacheSimbolico  # noqa: E402

RODADA = os.path.join(BASE, "results", "20260908T094808Z-9a00cb2")
SEMENTE = 42
N_FN, N_VN_BFP = 5, 5


def ler(prompt):
    arq = os.path.join(RODADA, f"ollama-qwen2.5-coder-7b__{prompt}.csv")
    with open(arq, encoding="utf-8") as f:
        return {r["ID_Caso"]: r for r in csv.DictReader(f)}


def celula(r):
    if r["Status_Semgrep"] != "DETECTADO" or r["Veredito_LLM"] not in ("VP", "FP"):
        return None
    vuln = r["Gabarito"] == "vulneravel"
    manteve = r["Veredito_LLM"] == "VP"
    return {(True, True): "VP", (True, False): "FN",
            (False, True): "FP", (False, False): "VN"}[(vuln, manteve)]


def main():
    esp, base = ler("especialista"), ler("baseline")
    estratos = {"E-VP": [], "E-FP": [], "E-FN": [], "E-VN/B-FP": []}
    for cid in sorted(esp):
        ce = celula(esp[cid])
        cb = celula(base[cid]) if cid in base else None
        if ce in ("VP", "FP", "FN"):
            estratos[f"E-{ce}"].append(cid)
        elif ce == "VN" and cb == "FP":
            estratos["E-VN/B-FP"].append(cid)

    rnd = random.Random(SEMENTE)
    amostra = {
        "E-VP": estratos["E-VP"],
        "E-FP": estratos["E-FP"],
        "E-FN": sorted(rnd.sample(estratos["E-FN"], N_FN)),
        "E-VN/B-FP": sorted(rnd.sample(estratos["E-VN/B-FP"], N_VN_BFP)),
    }
    for k, v in estratos.items():
        print(f"{k}: populacao {len(v)}, sorteados {len(amostra[k])}")

    # Contexto exato entregue ao modelo: o cache simbólico da rodada.
    with open(rp.DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)
    meta = rp._cwe_lookup(dataset)
    casos = (rp.construir_casos_fp(dataset)
             + rp.construir_casos_tp(rp.TP_PAIRS_OURO, "TP_ouro", meta)
             + rp.construir_casos_tp(rp.TP_PAIRS_PRATA, "TP_prata", meta)
             + rp.construir_casos_tp(rp.TP_PAIRS_ALCANCAVEL, "TP_alcancavel",
                                     meta, prefixo_id="TPA:")
             + rp.construir_casos_tp_dataset(dataset))
    por_id = {c["id"]: c for c in casos}
    cache = CacheSimbolico()

    saida = os.path.join(os.path.dirname(__file__), "amostra.csv")
    campos = ["Estrato", "ID_Caso", "Repositorio", "CWE", "Gabarito",
              "Tipo_Prompt", "Veredito_LLM", "Celula", "Justificativa",
              "Contexto", "Eixo1_Fundamento", "Eixo2_SeguroDeFato", "Nota",
              "Status_Classificacao"]
    with open(saida, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for estrato, ids in amostra.items():
            for cid in ids:
                c = por_id[cid]
                payload = cache.ler(c["repo_name"], c["commit"], c["arquivo"], c["cwe"])
                ctx = payload["contexto_hidratado"] if payload else ""
                for prompt, tab in (("baseline", base), ("especialista", esp)):
                    r = tab[cid]
                    w.writerow({
                        "Estrato": estrato, "ID_Caso": cid,
                        "Repositorio": r["Repositorio"], "CWE": r["CWE"],
                        "Gabarito": r["Gabarito"], "Tipo_Prompt": prompt,
                        "Veredito_LLM": r["Veredito_LLM"], "Celula": celula(r),
                        "Justificativa": r["Justificativa"], "Contexto": ctx,
                        "Eixo1_Fundamento": "", "Eixo2_SeguroDeFato": "",
                        "Nota": "", "Status_Classificacao": "",
                    })
    print("gravado:", saida)


if __name__ == "__main__":
    main()
