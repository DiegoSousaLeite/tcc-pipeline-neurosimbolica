"""
metricas.py — métricas do TCC a partir dos CSVs de resultado.

Duas entradas possíveis:
  - uma RODADA inteira (`results/<run_id>/`), com um CSV por braço da matriz;
  - um CSV avulso, inclusive os da Parte 1, que não têm as colunas novas.

As duas matrizes continuam separadas: a de COBERTURA mede o Semgrep contra o
gabarito, a de ACERTO mede o LLM. Misturá-las responderia a pergunta errada —
um ponto cego do Semgrep não é erro do LLM, que sequer foi consultado.

USO
  python src/metricas.py results/<run_id>              # tabela dos braços
  python src/metricas.py results/<run_id> --mcnemar    # + comparação pareada
  python src/metricas.py results/<run_id> --estratificar
  python src/metricas.py results/<run_id> --latex      # exporta os .tex
  python src/metricas.py resultados_tcc.csv            # CSV avulso (Parte 1)
  python src/metricas.py resultados_tcc.csv --por-cwe
"""
import argparse
import csv
import glob
import math
import os
from collections import defaultdict

# Limiar do teste de McNemar: abaixo dele o qui-quadrado é má aproximação e se
# usa o binomial exato.
LIMIAR_EXATO = 25

# Abaixo deste número de amostras vulneráveis avaliadas, qualquer p-valor é
# reportado com aviso: o teste não tem poder para distinguir nada.
MINIMO_VULNERAVEIS = 30


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def _categoria_llm(cls):
    """Classificacao_LLM → célula da matriz de acerto.

    Aceita os rótulos em português (atuais) e os em inglês, que aparecem nos
    CSVs mais antigos da Parte 1 — sem isso aqueles resultados sairiam vazios.
    """
    if "Verdadeiro Positivo" in cls or "True Positive" in cls:
        return "VP"
    if "Verdadeiro Negativo" in cls or "True Negative" in cls:
        return "VN"
    if "Falso Negativo" in cls or "False Negative" in cls:
        return "FN"
    if "Falso Positivo" in cls or "False Positive" in cls:
        return "FP"
    return None  # erros / N/A


def _categoria_semgrep(cls):
    """Classificacao_Semgrep → célula da matriz de cobertura."""
    for cat in ("VP", "VN", "FN", "FP"):
        if f"Semgrep {cat}" in cls:
            return cat
    return None


class Braco:
    """Linhas de um braço `(modelo, tipo de prompt)`, com suas contagens."""

    def __init__(self, modelo, prompt, origem):
        self.modelo = modelo
        self.prompt = prompt
        self.origem = origem          # arquivo de onde veio
        self.linhas = []

    @property
    def rotulo(self):
        return f"{self.modelo} / {self.prompt}"

    @property
    def hashes_catalogo(self):
        return {linha.get("Hash_Catalogo", "") for linha in self.linhas} - {""}

    def custo_total(self):
        total = 0.0
        for linha in self.linhas:
            try:
                total += float(linha.get("Custo_USD") or 0)
            except ValueError:
                pass
        return total

    def tokens(self):
        def _soma(col):
            t = 0
            for linha in self.linhas:
                try:
                    t += int(linha.get(col) or 0)
                except ValueError:
                    pass
            return t
        return _soma("Tokens_Entrada"), _soma("Tokens_Saida")


def ler_linhas(caminho):
    with open(caminho, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def carregar(alvo):
    """Devolve a lista de braços de `alvo`, que pode ser diretório ou CSV.

    Um diretório é uma rodada: cada CSV é um braço. Um CSV avulso é agrupado
    pelas colunas `Modelo_LLM`/`Tipo_Prompt`, que existem desde a Parte 1.
    """
    arquivos = ([alvo] if os.path.isfile(alvo)
                else sorted(glob.glob(os.path.join(alvo, "*.csv"))))
    if not arquivos:
        raise SystemExit(f"nenhum CSV encontrado em {alvo}")

    bracos = {}
    for arq in arquivos:
        for linha in ler_linhas(arq):
            chave = (linha.get("Modelo_LLM", "?"), linha.get("Tipo_Prompt", "?"))
            if chave not in bracos:
                bracos[chave] = Braco(chave[0], chave[1], arq)
            bracos[chave].linhas.append(linha)
    return [bracos[c] for c in sorted(bracos)]


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

def _metricas(vp, vn, fp, fn):
    total = vp + vn + fp + fn
    if total == 0:
        return {}
    nan = float("nan")
    precisao = vp / (vp + fp) if (vp + fp) else nan
    recall = vp / (vp + fn) if (vp + fn) else nan
    f1_den = precisao + recall
    f1 = 2 * precisao * recall / f1_den if f1_den else nan
    mcc_den = math.sqrt((vp + fp) * (vp + fn) * (vn + fp) * (vn + fn))
    mcc = (vp * vn - fp * fn) / mcc_den if mcc_den else nan
    # TRA (Taxa de Redução de Alertas): fração de TODOS os alertas que o LLM
    # descartou como seguros (VN+FN). Mede o volume tirado da pilha do dev;
    # deve ser lida SEMPRE junto da TFN (o custo dos descartes errados).
    tra = (vn + fn) / total
    # Proporção de FP filtrados = especificidade: dos alertas seguros, quantos
    # foram corretamente descartados.
    prop_fp = vn / (vn + fp) if (vn + fp) else nan
    tfn = fn / (vp + fn) if (vp + fn) else nan   # 1 - recall
    return {
        "VP": vp, "VN": vn, "FP": fp, "FN": fn, "Total": total,
        "Precisao": precisao, "Recall": recall, "F1": f1, "MCC": mcc,
        "TRA": tra, "PropFPFiltrados": prop_fp, "TFN": tfn,
    }


def contar(linhas, matriz="llm"):
    categoria = _categoria_llm if matriz == "llm" else _categoria_semgrep
    coluna = "Classificacao_LLM" if matriz == "llm" else "Classificacao_Semgrep"
    c = defaultdict(int)
    for linha in linhas:
        cat = categoria(linha.get(coluna, ""))
        if cat:
            c[cat] += 1
    return _metricas(c["VP"], c["VN"], c["FP"], c["FN"])


def contar_status(linhas):
    c = defaultdict(int)
    for linha in linhas:
        c[linha.get("Status_Semgrep", "?")] += 1
    return dict(c)


# CSVs anteriores à coluna de motivo não sabem dizer qual dos dois produziu a
# não-detecção; são reportados assim em vez de derrubarem a leitura.
MOTIVO_INDISPONIVEL = "indisponível"


def contar_motivos(linhas):
    """Não-detecção discriminada por motivo, sobre linhas já únicas por caso.

    A distinção separa duas afirmações diferentes sobre o motor simbólico: "não
    existe regra que alcance esta fraqueza neste arquivo" e "existem regras que
    dispararam, mas sobre outra fraqueza". Colapsá-las descreveria como ponto
    cego uniforme algo que tem duas causas.

    Cada caso `NAO_DETECTADO` entra exatamente uma vez, então a soma dos motivos
    é igual ao total de `NAO_DETECTADO` e a matriz de cobertura não se move.
    """
    c = defaultdict(int)
    for linha in linhas:
        if linha.get("Status_Semgrep") != "NAO_DETECTADO":
            continue
        motivo = (linha.get("Motivo_Nao_Deteccao") or "").strip()
        c[motivo if motivo and motivo != "N/A" else MOTIVO_INDISPONIVEL] += 1
    return dict(c)


def vulneraveis_avaliadas(linhas):
    """Amostras `gabarito=vulneravel` que chegaram ao LLM com veredito válido.

    É este número, e não o total de casos, que determina o poder do teste: as
    células VP e FN da matriz de acerto saem só daqui.
    """
    return sum(1 for linha in linhas
               if linha.get("Gabarito") == "vulneravel"
               and _categoria_llm(linha.get("Classificacao_LLM", "")) in ("VP", "FN"))


# ---------------------------------------------------------------------------
# McNemar
# ---------------------------------------------------------------------------

def _binomial_bicaudal(b, c):
    """p-valor exato de `b` sucessos em `n=b+c` sob p=0,5, bicaudal.

    Implementado com `math.comb` para não trazer scipy — a decisão do projeto é
    não depender de numpy/scipy, e esta é a única estatística necessária.
    """
    n = b + c
    if n == 0:
        return 1.0
    total = 2 ** n
    k = min(b, c)
    cauda = sum(math.comb(n, i) for i in range(k + 1))
    return min(1.0, 2 * cauda / total)


def _qui_quadrado_yates(b, c):
    """Qui-quadrado com correção de continuidade de Yates e seu p-valor.

    A sobrevivência da qui-quadrado com 1 grau de liberdade é
    `erfc(sqrt(x/2))`, então não é preciso tabelar distribuição alguma.
    """
    if b + c == 0:
        return 0.0, 1.0
    x = (abs(b - c) - 1) ** 2 / (b + c)
    return x, math.erfc(math.sqrt(x / 2))


def mcnemar(braco_a, braco_b):
    """Comparação pareada de dois braços sobre as amostras que ambos julgaram.

    Só entram os `ID_Caso` presentes nos dois com veredito VÁLIDO (VP ou FP):
    um caso que virou erro de esteira em um dos braços não é evidência sobre
    nenhum dos dois.

    Devolve a tabela de discordâncias, a estatística, o p-valor e o n pareado.
    """
    def _acertos(braco):
        acertos = {}
        for linha in braco.linhas:
            veredito = linha.get("Veredito_LLM")
            if veredito not in ("VP", "FP"):
                continue
            cat = _categoria_llm(linha.get("Classificacao_LLM", ""))
            if cat is None:
                continue
            acertos[linha["ID_Caso"]] = cat in ("VP", "VN")
        return acertos

    a, b_ = _acertos(braco_a), _acertos(braco_b)
    comuns = sorted(set(a) & set(b_))

    # b: A acerta e B erra;  c: A erra e B acerta.
    b = sum(1 for i in comuns if a[i] and not b_[i])
    c = sum(1 for i in comuns if not a[i] and b_[i])
    ambos_ok = sum(1 for i in comuns if a[i] and b_[i])
    ambos_erro = sum(1 for i in comuns if not a[i] and not b_[i])

    discordancias = b + c
    if discordancias < LIMIAR_EXATO:
        teste = "binomial exato"
        estatistica = float(discordancias)
        p = _binomial_bicaudal(b, c)
    else:
        teste = "qui-quadrado (Yates)"
        estatistica, p = _qui_quadrado_yates(b, c)

    return {
        "a": braco_a.rotulo, "b": braco_b.rotulo,
        "n_pareado": len(comuns),
        "ambos_acertam": ambos_ok, "ambos_erram": ambos_erro,
        "so_a_acerta": b, "so_b_acerta": c,
        "discordancias": discordancias,
        "teste": teste, "estatistica": estatistica, "p_valor": p,
    }


# ---------------------------------------------------------------------------
# Estratificação
# ---------------------------------------------------------------------------

def _faixa_locations(linha):
    bruto = linha.get("Num_Locations")
    if not bruto:
        return "indisponível"
    try:
        n = int(bruto)
    except ValueError:
        return "indisponível"
    if n == 1:
        return "1 (location única)"
    if n <= 6:
        return "2-6"
    return "7+"


ESTRATOS = {
    "trilha": lambda linha: linha.get("Origem", "?"),
    "num_locations": _faixa_locations,
    "ficha_cwe": lambda linha: linha.get("Ficha_CWE") or "indisponível",
}


def estratificar(linhas, chave, matriz="llm"):
    grupos = defaultdict(list)
    for linha in linhas:
        grupos[ESTRATOS[chave](linha)].append(linha)
    return {g: contar(ls, matriz) for g, ls in sorted(grupos.items())}


# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------

_LABELS = [
    ("Precisao", "Precisao"),
    ("Recall", "Recall"),
    ("F1", "F1"),
    ("MCC", "MCC"),
    ("TRA", "TRA (reducao alertas)"),
    ("PropFPFiltrados", "Prop. FP filtrados"),
    ("TFN", "TFN"),
]


def _fmt(v):
    if isinstance(v, int):
        return str(v)
    return "N/A" if (v is None or math.isnan(v)) else f"{v:.4f}"


def _imprimir_metricas(nome, m):
    if not m:
        print(f"  {nome}: sem dados")
        return
    print(f"\n  {nome} (n={m['Total']})")
    print(f"    Matriz de Confusão: VP={m['VP']}  VN={m['VN']}  "
          f"FP={m['FP']}  FN={m['FN']}")
    for k, lbl in _LABELS:
        print(f"    {lbl:24}: {_fmt(m[k])}")


def _tabela(cabecalho, linhas):
    larguras = [max(len(str(x)) for x in [cabecalho[i]] + [ln[i] for ln in linhas])
                for i in range(len(cabecalho))]
    sep = "  ".join("-" * w for w in larguras)
    print("  " + "  ".join(str(c).ljust(w) for c, w in zip(cabecalho, larguras)))
    print("  " + sep)
    for ln in linhas:
        print("  " + "  ".join(str(x).ljust(w) for x, w in zip(ln, larguras)))


def tabela_bracos(bracos):
    """Uma linha por braço, com as métricas de ACERTO do LLM."""
    cabecalho = ["Modelo", "Prompt", "n", "VP", "VN", "FP", "FN",
                 "Precisao", "Recall", "F1", "MCC", "TRA", "TFN", "Custo USD"]
    linhas = []
    for br in bracos:
        m = contar(br.linhas, "llm")
        if not m:
            linhas.append([br.modelo, br.prompt, 0] + ["-"] * 10 +
                          [f"{br.custo_total():.4f}"])
            continue
        linhas.append([
            br.modelo, br.prompt, m["Total"], m["VP"], m["VN"], m["FP"], m["FN"],
            _fmt(m["Precisao"]), _fmt(m["Recall"]), _fmt(m["F1"]),
            _fmt(m["MCC"]), _fmt(m["TRA"]), _fmt(m["TFN"]),
            f"{br.custo_total():.4f}",
        ])
    return cabecalho, linhas


# ---------------------------------------------------------------------------
# Export LaTeX
# ---------------------------------------------------------------------------

def _escapar_tex(texto):
    for de, para in (("\\", r"\textbackslash{}"), ("_", r"\_"), ("&", r"\&"),
                     ("%", r"\%"), ("#", r"\#")):
        texto = str(texto).replace(de, para)
    return texto


def _tabular(cabecalho, linhas, alinhamento=None):
    align = alinhamento or ("l" * 2 + "r" * (len(cabecalho) - 2))
    out = [f"\\begin{{tabular}}{{{align}}}", "\\hline"]
    out.append(" & ".join(_escapar_tex(c) for c in cabecalho) + " \\\\")
    out.append("\\hline")
    for ln in linhas:
        out.append(" & ".join(_escapar_tex(x) for x in ln) + " \\\\")
    out.append("\\hline")
    out.append("\\end{tabular}")
    return "\n".join(out) + "\n"


def exportar_latex(bracos, comparacoes, destino):
    """Grava `tabela_bracos.tex` e `tabela_mcnemar.tex` prontos para `\\input{}`.

    Só o ambiente `tabular`: quem inclui escolhe `table`, legenda e rótulo, e
    o arquivo compila sem exigir pacote nenhum além dos padrão.
    """
    cabecalho, linhas = tabela_bracos(bracos)
    caminhos = []

    p = os.path.join(destino, "tabela_bracos.tex")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("% Gerado por src/metricas.py — não editar à mão.\n")
        f.write(_tabular(cabecalho, linhas))
    caminhos.append(p)

    cab_mc = ["Comparação", "n", "Ambos ok", "Só A", "Só B", "Ambos erram",
              "Teste", "Estat.", "p"]
    linhas_mc = [[
        f"{c['a']} vs {c['b']}", c["n_pareado"], c["ambos_acertam"],
        c["so_a_acerta"], c["so_b_acerta"], c["ambos_erram"],
        c["teste"], f"{c['estatistica']:.3f}", f"{c['p_valor']:.4f}",
    ] for c in comparacoes]

    p = os.path.join(destino, "tabela_mcnemar.tex")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("% Gerado por src/metricas.py — não editar à mão.\n")
        f.write(_tabular(cab_mc, linhas_mc, alinhamento="l" + "r" * 5 + "lrr"))
    caminhos.append(p)
    return caminhos


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

def avisos(bracos):
    """Avisos que precisam sair ANTES dos números, não em nota de rodapé."""
    saida = []

    hashes = set()
    for br in bracos:
        hashes |= br.hashes_catalogo
    if len(hashes) > 1:
        saida.append(
            f"DIVERGÊNCIA DE CATÁLOGO: {len(hashes)} hashes distintos de "
            f"catalogo_cwe.json nestes resultados. Linhas de versões diferentes "
            f"do catálogo NÃO são comparáveis entre si: "
            f"{', '.join(sorted(h[:12] for h in hashes))}")

    for br in bracos:
        n = vulneraveis_avaliadas(br.linhas)
        if n < MINIMO_VULNERAVEIS:
            saida.append(
                f"PODER ESTATÍSTICO LIMITADO em [{br.rotulo}]: apenas {n} "
                f"amostras vulneráveis chegaram ao LLM com veredito válido "
                f"(mínimo sugerido: {MINIMO_VULNERAVEIS}). Recall, F1, MCC e "
                f"qualquer p-valor sobre este braço são indicativos, não "
                f"conclusivos.")
    return saida


def relatorio(alvo, por_cwe=False, com_mcnemar=False, com_estratos=False,
              latex=False):
    bracos = carregar(alvo)

    print("=" * 74)
    print("MÉTRICAS DA PIPELINE NEURO-SIMBÓLICA")
    print(f"Fonte: {alvo}  |  braços: {len(bracos)}")
    print("=" * 74)

    for aviso in avisos(bracos):
        print(f"\n  [!] {aviso}")

    print("\n--- Comparação entre braços (matriz de ACERTO do LLM) ---\n")
    _tabela(*tabela_bracos(bracos))

    print("\n--- Cobertura do Semgrep (matriz SIMBÓLICA, separada) ---")
    print("    Não depende do braço: o Semgrep roda uma vez por caso.")
    todas = [linha for br in bracos for linha in br.linhas]
    vistos, unicas = set(), []
    for linha in todas:
        if linha["ID_Caso"] not in vistos:
            vistos.add(linha["ID_Caso"])
            unicas.append(linha)
    _imprimir_metricas("Global", contar(unicas, "semgrep"))
    print(f"\n    Status: {contar_status(unicas)}")
    motivos = contar_motivos(unicas)
    if motivos:
        print(f"    NAO_DETECTADO por motivo: {motivos}")

    if com_estratos:
        print("\n--- Estratificação (matriz de ACERTO do LLM) ---")
        for br in bracos:
            print(f"\n  [{br.rotulo}]")
            for chave in ESTRATOS:
                print(f"\n    por {chave}:")
                for grupo, m in estratificar(br.linhas, chave).items():
                    if m:
                        print(f"      {grupo:22} n={m['Total']:<5} "
                              f"F1={_fmt(m['F1'])}  MCC={_fmt(m['MCC'])}  "
                              f"TFN={_fmt(m['TFN'])}")
                    else:
                        print(f"      {grupo:22} sem dados")

    comparacoes = []
    if com_mcnemar:
        print("\n--- Teste de McNemar (pareado, só vereditos válidos) ---")
        if len(bracos) < 2:
            print("  (menos de dois braços: nada a comparar)")
        for i in range(len(bracos)):
            for j in range(i + 1, len(bracos)):
                c = mcnemar(bracos[i], bracos[j])
                comparacoes.append(c)
                print(f"\n  {c['a']}  vs  {c['b']}")
                print(f"    n pareado: {c['n_pareado']}")
                print(f"    tabela 2x2: ambos acertam={c['ambos_acertam']}  "
                      f"só A={c['so_a_acerta']}  só B={c['so_b_acerta']}  "
                      f"ambos erram={c['ambos_erram']}")
                print(f"    discordâncias b+c={c['discordancias']} -> {c['teste']}")
                print(f"    estatística={c['estatistica']:.4f}  "
                      f"p-valor={c['p_valor']:.4f}")
                if c["n_pareado"] == 0:
                    print("    [!] nenhuma amostra pareada: o teste não diz nada.")
                elif c["discordancias"] == 0:
                    print("    [!] zero discordâncias: os braços decidiram igual "
                          "em tudo que puderam comparar.")

    if por_cwe:
        print("\n--- Por CWE (matriz de ACERTO do LLM) ---")
        for br in bracos:
            print(f"\n  [{br.rotulo}]")
            grupos = defaultdict(list)
            for linha in br.linhas:
                grupos[linha.get("CWE", "?")].append(linha)
            for cwe in sorted(grupos):
                m = contar(grupos[cwe], "llm")
                if m:
                    print(f"    {cwe:14} n={m['Total']:<5} F1={_fmt(m['F1'])}  "
                          f"MCC={_fmt(m['MCC'])}")

    if latex:
        destino = alvo if os.path.isdir(alvo) else os.path.dirname(alvo) or "."
        if not comparacoes and len(bracos) >= 2:
            comparacoes = [mcnemar(bracos[i], bracos[j])
                           for i in range(len(bracos))
                           for j in range(i + 1, len(bracos))]
        for p in exportar_latex(bracos, comparacoes, destino):
            print(f"\n[+] LaTeX: {p}")

    print("\n" + "=" * 74)


def main():
    ap = argparse.ArgumentParser(
        description="Calcula métricas de uma rodada (results/<run_id>/) ou de "
                    "um CSV avulso.")
    ap.add_argument("alvo", help="Diretório da rodada ou caminho de um CSV.")
    ap.add_argument("--por-cwe", action="store_true",
                    help="Breakdown por CWE.")
    ap.add_argument("--mcnemar", action="store_true",
                    help="Teste de McNemar entre todos os pares de braços.")
    ap.add_argument("--estratificar", action="store_true",
                    help="Estratifica por trilha, Num_Locations e ficha de CWE.")
    ap.add_argument("--latex", action="store_true",
                    help="Exporta tabela_bracos.tex e tabela_mcnemar.tex.")
    args = ap.parse_args()
    relatorio(args.alvo, args.por_cwe, args.mcnemar, args.estratificar,
              args.latex)


if __name__ == "__main__":
    main()
