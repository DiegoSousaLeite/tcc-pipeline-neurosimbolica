"""
analise_rodada.py — números derivados de uma rodada, para o relatório de análise.

Por que existe
--------------
`src/metricas.py` responde "qual o desempenho de cada braço". Ele não responde
"quantas amostras sustentam esse desempenho", que é a pergunta que o relatório
de análise precisa fazer antes de deixar qualquer número ir para a monografia.
Este script imprime a segunda camada: os degraus do funil que vai das amostras
rotuladas como vulneráveis até as que o LLM de fato julgou, as relações de
conjunto entre os braços, a distribuição dos casos que o motor simbólico não
detectou, a saúde da esteira e a extração dos casos da classe positiva.

Existe como script, e não como one-liner no texto do relatório, porque as
justificativas do LLM no CSV contêm vírgulas, aspas e quebras de linha: qualquer
contagem por `Select-String` ou `split(",")` erra em silêncio. Cada tabela do
relatório cita a invocação exata que a regenera.

Fica fora de `src/metricas.py` de propósito (D3 da mudança `relatorio-rodada-1`):
`metricas.py` é caminho principal, coberto por spec própria e consumido pelo
export LaTeX; números de diagnóstico de uma rodada não pertencem ao contrato
dele. As funções de categorização vêm de lá por importação, para que não existam
duas verdades sobre o que conta como Verdadeiro Positivo.

Garantias
---------
SOMENTE-LEITURA: não escreve, move nem regenera artefato algum.
OFFLINE: nenhuma chamada de rede ou de LLM; tudo sai do disco.
DETERMINÍSTICO: toda ordenação tem chave explícita, nunca ordem de iteração de
conjunto ou de dicionário construído por varredura de diretório.

USO
  python scripts/analise_rodada.py results/<run_id>
  python scripts/analise_rodada.py results/<run_id> --secao funil
  python scripts/analise_rodada.py results/<run_id> --secao positivos --justificativa-completa
"""
import argparse
import glob
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fase1_semgrep import _numero_cwe  # noqa: E402
from src.metricas import (  # noqa: E402
    _categoria_llm,
    _tabela,
    carregar,
    contar,
    mcnemar,
)
from src.ruleset import (  # noqa: E402
    GRAU_BAIXA,
    ORDEM_GRAUS,
    graus_alcancabilidade,
)

# Linguagem do corpus. O grau é por linguagem, como a alcançabilidade.
LINGUAGEM_GRAU = "go"

# Ordem canônica das trilhas de origem, a mesma de `run_pipeline.TRILHAS`.
# Repetida aqui, e não importada, para que a saída não dependa de o
# orquestrador ser importável — as seções que só leem CSV precisam rodar mesmo
# sem `data/`.
TRILHAS = ("FP", "TP_ouro", "TP_prata", "TP_dataset", "TP_alcancavel")

SECOES = ("funil", "nao-detectados", "conjuntos", "esteira", "positivos",
          "regras", "grau")

EPILOGO = """\
seções (na ordem em que saem quando --secao é omitido):
  funil           degraus de 'gabarito vulneravel' até veredito do LLM, com
                  perda absoluta e percentual por degrau e a causa de cada uma
  nao-detectados  casos vulneráveis sem alerta pareado, por CWE e por trilha
  conjuntos       conjuntos de FN/FP/VP por braço, interseção, contenção e a
                  tabela 2x2 de discordâncias entre os braços
  esteira         linhas, status do Semgrep, taxa de erro, denominador efetivo
                  e estatísticas de tokens e de tempo por braço
  positivos       um registro por caso de gabarito vulnerável que chegou ao LLM,
                  com veredito e justificativa de cada braço lado a lado
  regras          quais regras do ruleset de fato dispararam sobre o corpus,
                  com a CWE que cada uma declara e quantos alertas produziu

O script é somente-leitura e offline: nenhuma escrita, nenhuma chamada de rede.
"""

# Truncamento padrão das justificativas na seção `positivos`. Uma justificativa
# inteira tem centenas de caracteres e a tabela vira ilegível; `--justificativa-
# completa` devolve o texto integral para a citação no relatório.
CORTE_JUSTIFICATIVA = 240


def _erro(msg):
    """Encerra com mensagem explícita e código de saída 1.

    Existe para que um diretório errado falhe alto, em vez de produzir tabelas
    vazias que passariam por resultado.
    """
    raise SystemExit(f"analise_rodada: {msg}")


def _pct(n, total):
    return "-" if not total else f"{100.0 * n / total:.1f}%"


def _num(v, casas=4):
    return "N/A" if v is None else f"{v:.{casas}f}"


def _corta(texto, limite):
    texto = " ".join((texto or "").split())
    if limite <= 0 or len(texto) <= limite:
        return texto
    return texto[:limite - 3] + "..."


def _ordem_trilha(nome):
    """Chave de ordenação canônica de trilha, com desconhecidas ao final."""
    return (TRILHAS.index(nome) if nome in TRILHAS else len(TRILHAS), nome)


class Rodada:
    """Uma rodada carregada: braços, manifesto e as opções da invocação."""

    def __init__(self, caminho, bracos, manifesto, args):
        self.caminho = caminho
        self.bracos = bracos
        self.manifesto = manifesto
        self.args = args

    @property
    def unicas(self):
        """Uma linha por `ID_Caso`.

        O resultado do Semgrep não depende do braço — a Fase 1 roda uma vez por
        caso e os braços leem o mesmo cache —, então contar cobertura sobre as
        linhas de todos os braços multiplicaria cada caso pelo número de braços.
        """
        vistos, saida = set(), []
        for br in self.bracos:
            for linha in br.linhas:
                if linha["ID_Caso"] not in vistos:
                    vistos.add(linha["ID_Caso"])
                    saida.append(linha)
        return saida

    def num_ctx(self):
        """`num_ctx` declarado no manifesto, se a rodada tiver braço local."""
        locais = (self.manifesto or {}).get("modelos_locais") or {}
        valores = {cfg.get("num_ctx") for cfg in locais.values()
                   if cfg.get("num_ctx")}
        return min(valores) if len(valores) == 1 else None


def _titulo(texto):
    print()
    print("=" * 74)
    print(texto)
    print("=" * 74)


# ---------------------------------------------------------------------------
# Seção: funil
# ---------------------------------------------------------------------------

def secao_funil(rodada):
    """Da amostra rotulada vulnerável até o veredito do LLM, degrau a degrau."""
    _titulo("FUNIL DE RECALL — da amostra vulnerável ao veredito do LLM")

    unicas = rodada.unicas
    vul = [ln for ln in unicas if ln.get("Gabarito") == "vulneravel"]
    topo = len(vul)
    status = Counter(ln.get("Status_Semgrep", "?") for ln in vul)
    detectado = status.get("DETECTADO", 0)
    nao_detectado = status.get("NAO_DETECTADO", 0)
    erro = topo - detectado - nao_detectado

    print(f"\n  Topo do funil: {topo} amostras com Gabarito = vulneravel "
          f"(de {len(unicas)} casos únicos na rodada).")
    print("\n  Status do Semgrep sobre a classe positiva:")
    for st, n in sorted(status.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    {st:16} {n:>5}  ({_pct(n, topo)})")

    print("\n  Degraus (perda medida sobre o topo do funil):\n")
    cabecalho = ["#", "degrau", "restam", "% do topo", "perda", "% perdido",
                 "causa da perda"]
    linhas = [
        ["1", "rotuladas vulneráveis", topo, _pct(topo, topo), 0, _pct(0, topo),
         "-"],
        ["2", "com alerta pareado (DETECTADO)", detectado, _pct(detectado, topo),
         nao_detectado + erro, _pct(nao_detectado + erro, topo),
         "não-detecção do motor simbólico"],
    ]

    # Do degrau 3 em diante o funil deixa de ser comum aos braços: um erro de
    # esteira derruba o caso em um braço e não no outro.
    for br in rodada.bracos:
        vul_braco = [ln for ln in br.linhas if ln.get("Gabarito") == "vulneravel"]
        avaliadas = [ln for ln in vul_braco
                     if _categoria_llm(ln.get("Classificacao_LLM", "")) in ("VP", "FN")]
        vp = sum(1 for ln in avaliadas
                 if _categoria_llm(ln.get("Classificacao_LLM", "")) == "VP")
        linhas.append([
            "3", f"avaliadas pelo LLM [{br.prompt}]", len(avaliadas),
            _pct(len(avaliadas), topo), detectado - len(avaliadas),
            _pct(detectado - len(avaliadas), topo), "falha de esteira (API_ERROR)",
        ])
        linhas.append([
            "4", f"julgadas vulneráveis pelo LLM [{br.prompt}]", vp,
            _pct(vp, topo), len(avaliadas) - vp, _pct(len(avaliadas) - vp, topo),
            "julgamento do modelo (Falso Negativo)",
        ])
    _tabela(cabecalho, linhas)

    print("\n  Recall medido contra recall de ponta a ponta:\n")
    cabecalho = ["braço", "VP", "FN", "n avaliadas", "recall medido",
                 "recall ponta a ponta"]
    linhas = []
    for br in rodada.bracos:
        m = contar(br.linhas, "llm")
        avaliadas = m["VP"] + m["FN"]
        linhas.append([
            br.prompt, m["VP"], m["FN"], avaliadas,
            _num(m["VP"] / avaliadas if avaliadas else None),
            _num(m["VP"] / topo if topo else None),
        ])
    _tabela(cabecalho, linhas)
    print("\n  O recall medido tem como denominador as amostras que chegaram ao")
    print("  LLM; o de ponta a ponta, o topo do funil. A distância entre os dois")
    print("  é o que a matriz de acerto não enxerga.")

    print("\n  ATENÇÃO: o degrau 2 conta como 'detectado' todo caso em que a Fase 1")
    print("  emparelhou ALGUM alerta ao gabarito. Se o emparelhamento é o certo é")
    print("  julgamento por caso — ver a seção `positivos` e o relatório.")


# ---------------------------------------------------------------------------
# Seção: nao-detectados
# ---------------------------------------------------------------------------

def secao_nao_detectados(rodada):
    """Distribuição dos casos vulneráveis sem alerta pareado."""
    _titulo("NÃO DETECTADOS — casos vulneráveis que não chegaram ao LLM")

    nd = [ln for ln in rodada.unicas
          if ln.get("Gabarito") == "vulneravel"
          and ln.get("Status_Semgrep") == "NAO_DETECTADO"]
    total = len(nd)
    por_cwe = Counter(ln.get("CWE", "?") for ln in nd)
    por_trilha = Counter(ln.get("Origem", "?") for ln in nd)

    print(f"\n  {total} casos NAO_DETECTADO na classe positiva, "
          f"em {len(por_cwe)} CWEs distintas.\n")

    print("  Por trilha de origem:\n")
    _tabela(["trilha", "n", "% dos não detectados"],
            [[t, n, _pct(n, total)]
             for t, n in sorted(por_trilha.items(),
                                key=lambda kv: _ordem_trilha(kv[0]))])

    print("\n  Por CWE (contagem decrescente, desempate alfabético):\n")
    _tabela(["CWE", "n", "% dos não detectados"],
            [[c, n, _pct(n, total)]
             for c, n in sorted(por_cwe.items(), key=lambda kv: (-kv[1], kv[0]))])

    # O ruleset `p/default` declara as CWEs que cobre; o catálogo de triagem do
    # projeto declara as que a Fase 3 sabe explicar. Uma CWE fora das duas listas
    # não é lacuna de configuração, é fraqueza fora do alcance da ferramenta.
    catalogo = ((rodada.manifesto or {}).get("catalogo_cwe") or {})
    especificas = set(catalogo.get("cwes_especificas") or [])
    if especificas:
        dentro = sorted(c for c in por_cwe if c in especificas)
        fora = sorted(c for c in por_cwe if c not in especificas)
        n_dentro = sum(por_cwe[c] for c in dentro)
        print(f"\n  Contra as {len(especificas)} CWEs com ficha própria no "
              f"catálogo de triagem:")
        print(f"    com ficha : {n_dentro:>3} casos em {len(dentro)} CWEs "
              f"({', '.join(dentro) or '—'})")
        print(f"    sem ficha : {total - n_dentro:>3} casos em {len(fora)} CWEs")

    # A pergunta que separa "o ruleset não tem regra para esta fraqueza" de "tem
    # regra e ela não disparou neste arquivo" — duas afirmações diferentes sobre
    # o motor, que a tabela por CWE sozinha colapsa.
    cobertas = _cwes_cobertas_por_regras_go()
    if cobertas:
        com = sorted(c for c in por_cwe if c in cobertas)
        sem = sorted(c for c in por_cwe if c not in cobertas)
        n_com = sum(por_cwe[c] for c in com)
        print(f"\n  Contra as CWEs que o ruleset declara cobrir em Go "
              f"({len(cobertas)} CWEs em regras de linguagem `go`):\n")
        _tabela(["situação", "CWEs", "casos", "% dos não detectados"],
                [["ruleset tem regra para a CWE", len(com), n_com,
                  _pct(n_com, total)],
                 ["ruleset não tem regra para a CWE", len(sem), total - n_com,
                  _pct(total - n_com, total)]])
        print(f"\n    com regra : {', '.join(com) or '—'}")
        print(f"    sem regra : {', '.join(sem) or '—'}")
        print("\n  A primeira linha são falhas DENTRO do escopo declarado do")
        print("  ruleset; a segunda são fraquezas que ele não promete alcançar.")

    print("\n  A leitura desta tabela está no relatório: cauda longa de CWEs de")
    print("  intenção (controle de acesso, autorização, exaustão de recurso) é")
    print("  argumento de limite da classe de ferramenta, não de ruleset mal")
    print("  escolhido.")


# ---------------------------------------------------------------------------
# Seção: conjuntos
# ---------------------------------------------------------------------------

def _conjuntos_por_categoria(braco):
    """`{categoria: set(ID_Caso)}` para VP, VN, FP e FN de um braço."""
    saida = defaultdict(set)
    for linha in braco.linhas:
        cat = _categoria_llm(linha.get("Classificacao_LLM", ""))
        if cat:
            saida[cat].add(linha["ID_Caso"])
    return saida


def _relacao(a, b, nome_a, nome_b):
    """Descreve a relação de conjunto entre dois conjuntos, com direção.

    Sem símbolo de subconjunto: a saída precisa sobreviver a um console cp1252,
    que é o padrão do Windows e onde `U+2282` derruba o script no meio da
    tabela.
    """
    if a == b:
        return "identicos"
    if a < b:
        return f"contencao estrita: {nome_a} dentro de {nome_b}"
    if b < a:
        return f"contencao estrita: {nome_b} dentro de {nome_a}"
    return "sobreposicao parcial (nenhum contem o outro)"


def secao_conjuntos(rodada):
    """Relações de conjunto entre os braços, por ID_Caso."""
    _titulo("CONJUNTOS — quem erra o quê, e se um braço contém o outro")

    if len(rodada.bracos) < 2:
        print("\n  (menos de dois braços: não há relação a estabelecer)")
        return

    cats = {br.prompt: _conjuntos_por_categoria(br) for br in rodada.bracos}

    print("\n  Tamanho dos conjuntos por braço:\n")
    linhas = []
    for br in rodada.bracos:
        c = cats[br.prompt]
        vp, vn, fp, fn = (len(c[k]) for k in ("VP", "VN", "FP", "FN"))
        negativos = vn + fp
        julgados = vp + vn + fp + fn
        linhas.append([
            br.prompt, vp, vn, fp, fn,
            # Especificidade: dos alertas de gabarito seguro, quantos o filtro
            # descartou. É a única métrica desta rodada cujo numerador e
            # denominador vivem inteiros na classe negativa.
            _num(vn / negativos) if negativos else "N/A", negativos,
            # Taxa de veredito "vulnerável": separa "discriminou melhor" de
            # "ficou conservador" quando lida entre braços.
            _num((vp + fp) / julgados) if julgados else "N/A",
        ])
    _tabela(["braço", "VP", "VN", "FP", "FN", "especificidade",
             "n da classe negativa", "taxa de veredito 'vulneravel'"], linhas)

    for i in range(len(rodada.bracos)):
        for j in range(i + 1, len(rodada.bracos)):
            a, b = rodada.bracos[i], rodada.bracos[j]
            ca, cb = cats[a.prompt], cats[b.prompt]
            print(f"\n  --- {a.prompt}  vs  {b.prompt} ---\n")
            _tabela(["categoria", f"só {a.prompt}", "interseção",
                     f"só {b.prompt}", "relação"],
                    [[cat, len(ca[cat] - cb[cat]), len(ca[cat] & cb[cat]),
                      len(cb[cat] - ca[cat]),
                      _relacao(ca[cat], cb[cat], a.prompt, b.prompt)]
                     for cat in ("VP", "FN", "FP", "VN")])

            # Tabela 2x2 construída aqui a partir de `Classificacao_LLM`, e não
            # reaproveitada de `mcnemar()`, que parte de `Veredito_LLM`. São dois
            # caminhos independentes até o mesmo número: divergirem é sinal de
            # que uma das duas leituras do CSV está errada.
            acerto_a = ca["VP"] | ca["VN"]
            acerto_b = cb["VP"] | cb["VN"]
            julgados_a = acerto_a | ca["FP"] | ca["FN"]
            julgados_b = acerto_b | cb["FP"] | cb["FN"]
            comuns = julgados_a & julgados_b
            so_a = len((acerto_a & comuns) - acerto_b)
            so_b = len((acerto_b & comuns) - acerto_a)
            ambos_ok = len(acerto_a & acerto_b & comuns)
            ambos_erro = len(comuns - acerto_a - acerto_b)

            print(f"\n  Discordâncias sobre os {len(comuns)} casos julgados "
                  f"pelos dois braços:\n")
            _tabela(["ambos acertam", f"só {a.prompt} acerta",
                     f"só {b.prompt} acerta", "ambos erram", "discordâncias"],
                    [[ambos_ok, so_a, so_b, ambos_erro, so_a + so_b]])

            mc = mcnemar(a, b)
            print("\n  Conferência contra src.metricas.mcnemar (caminho "
                  "independente, via Veredito_LLM):")
            print(f"    n pareado={mc['n_pareado']}  ambos ok={mc['ambos_acertam']}  "
                  f"só A={mc['so_a_acerta']}  só B={mc['so_b_acerta']}  "
                  f"ambos erram={mc['ambos_erram']}")
            bate = (mc["n_pareado"], mc["ambos_acertam"], mc["so_a_acerta"],
                    mc["so_b_acerta"], mc["ambos_erram"]) == (
                len(comuns), ambos_ok, so_a, so_b, ambos_erro)
            print(f"    {'confere' if bate else 'DIVERGE — investigar'}")
            print(f"    teste={mc['teste']}  estatística={mc['estatistica']:.4f}  "
                  f"p-valor={mc['p_valor']:.4f}")

            if so_a == 0 and so_b > 0:
                print(f"\n  Aninhamento estrito: não há um único caso em que "
                      f"{a.prompt} acerta e {b.prompt} erra.")
            elif so_b == 0 and so_a > 0:
                print(f"\n  Aninhamento estrito: não há um único caso em que "
                      f"{b.prompt} acerta e {a.prompt} erra.")


# ---------------------------------------------------------------------------
# Seção: esteira
# ---------------------------------------------------------------------------

def _estatisticas(valores):
    """Mínimo, mediana, máximo e soma, ou `None` se a coluna veio vazia."""
    if not valores:
        return None
    return {
        "min": min(valores), "mediana": statistics.median(valores),
        "max": max(valores), "soma": sum(valores),
    }


def _coluna_numerica(linhas, coluna, tipo=int):
    saida = []
    for linha in linhas:
        bruto = linha.get(coluna)
        if bruto in (None, "", "N/A"):
            continue
        try:
            saida.append(tipo(bruto))
        except ValueError:
            continue
    return saida


def secao_esteira(rodada):
    """Saúde da execução: status, erros, denominador efetivo, tokens e tempo."""
    _titulo("ESTEIRA — status da execução, denominadores, tokens e tempo")

    status_todos = sorted({ln.get("Status_Semgrep", "?")
                           for br in rodada.bracos for ln in br.linhas})

    print("\n  Linhas e status do Semgrep por braço:\n")
    _tabela(["braço", "linhas"] + status_todos,
            [[br.prompt, len(br.linhas)] +
             [sum(1 for ln in br.linhas if ln.get("Status_Semgrep") == st)
              for st in status_todos]
             for br in rodada.bracos])

    print("\n  Denominador efetivo e taxa de erro de esteira:\n")
    linhas = []
    for br in rodada.bracos:
        n = len(br.linhas)
        detectado = sum(1 for ln in br.linhas
                        if ln.get("Status_Semgrep") == "DETECTADO")
        erros = sum(1 for ln in br.linhas
                    if "ERROR" in (ln.get("Status_Semgrep") or ""))
        m = contar(br.linhas, "llm")
        linhas.append([br.prompt, n, detectado, m["Total"], erros,
                       _pct(erros, n), _pct(erros, detectado + erros)])
    _tabela(["braço", "linhas", "DETECTADO", "classificados", "erros",
             "erro / linhas", "erro / chamadas"], linhas)
    print("\n  'classificados' é o denominador de toda métrica de acerto: só")
    print("  entram as linhas com veredito válido. Braços com denominadores")
    print("  diferentes não comparam proporções sem que isso seja declarado.")

    num_ctx = rodada.num_ctx()
    print(f"\n  Tokens de entrada por braço"
          f"{f' (num_ctx declarado no manifesto: {num_ctx})' if num_ctx else ''}:\n")
    linhas = []
    for br in rodada.bracos:
        # Zero é o que o CSV grava quando não houve chamada (NAO_DETECTADO,
        # erro de esteira). Entrar na mediana como se fosse um prompt curto
        # deslocaria a estatística para baixo em ~15% dos casos.
        vals = [v for v in _coluna_numerica(br.linhas, "Tokens_Entrada") if v > 0]
        est = _estatisticas(vals)
        acima = sum(1 for v in vals if num_ctx and v > num_ctx)
        linhas.append([
            br.prompt, len(vals),
            est["min"] if est else "-",
            _num(est["mediana"], 1) if est else "-",
            est["max"] if est else "-", est["soma"] if est else "-",
            acima if num_ctx else "n/d",
        ])
    _tabela(["braço", "n (com chamada)", "mín", "mediana", "máx", "soma",
             "acima de num_ctx"], linhas)

    print("\n  Tempo de execução por chamada (segundos):\n")
    linhas = []
    for br in rodada.bracos:
        vals = [v for v in
                _coluna_numerica(br.linhas, "Tempo_Execucao_s", float) if v > 0]
        est = _estatisticas(vals)
        linhas.append([
            br.prompt, len(vals),
            _num(est["min"], 2) if est else "-",
            _num(est["mediana"], 2) if est else "-",
            _num(est["max"], 2) if est else "-",
            _num(est["soma"], 1) if est else "-",
        ])
    _tabela(["braço", "n (com chamada)", "mín", "mediana", "máx", "soma"], linhas)

    if rodada.manifesto:
        m = rodada.manifesto
        print(f"\n  Manifesto: run_id={m.get('run_id')}  commit={m.get('commit')}  "
              f"duração={m.get('duracao_s')}s")
        semgrep = m.get("semgrep") or {}
        print(f"    semgrep {semgrep.get('versao')} / ruleset "
              f"{semgrep.get('ruleset')}")
        for rotulo, versao in sorted((m.get("prompts") or {}).items()):
            print(f"    prompt {rotulo}: {versao}")


# ---------------------------------------------------------------------------
# Seção: positivos
# ---------------------------------------------------------------------------

def _indice_casos():
    """`ID_Caso` → caso construído, para resolver arquivo, commit e location.

    Reconstrói a população pelos MESMOS construtores de `run_pipeline.py`: um
    índice próprio reimplementaria a regra de formação do ID e passaria a errar
    silenciosamente na primeira vez que ela mudasse. Devolve `{}` quando os
    artefatos de dados não estão no clone — a seção degrada para o que o CSV
    sozinho informa, em vez de falhar.
    """
    try:
        from run_pipeline import (  # noqa: E501
            construir_casos_fp,
            construir_casos_tp,
            construir_casos_tp_dataset,
        )
        from src.config import DATASET_PATH
        with open(DATASET_PATH, encoding="utf-8") as f:
            dataset = json.load(f)
    except (ImportError, OSError, ValueError) as exc:
        print(f"  [!] índice de casos indisponível ({exc.__class__.__name__}): "
              f"a seção sai sem arquivo-alvo nem regra do Semgrep.")
        return {}

    casos = (construir_casos_fp(dataset) + construir_casos_tp_dataset(dataset)
             + construir_casos_tp("tp_pairs.json", "TP_ouro", {})
             + construir_casos_tp("tp_pairs_osv.json", "TP_prata", {}))
    return {c.id: c for c in casos}


def _carregar_ruleset():
    """Ruleset baixado por `scripts/medir_pareamento.py`, ou `{}`.

    Lido se existir, ignorado se não: este script não faz rede, e as seções que
    dependem do ruleset degradam em vez de falhar.
    """
    destino = os.path.join("cache_simbolico", "_regras_p_default.json")
    if not os.path.exists(destino):
        return {}
    try:
        with open(destino, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _cwes_declaradas(regra):
    """`metadata.cwe` normalizado em lista — o registry ora manda str, ora lista."""
    cwe = (regra.get("metadata") or {}).get("cwe")
    if cwe is None:
        return []
    return [cwe] if isinstance(cwe, str) else list(cwe)


def _regras_do_ruleset():
    """`check_id` → CWEs declaradas, do ruleset já baixado."""
    return {r["id"]: _cwes_declaradas(r)
            for r in _carregar_ruleset().get("rules", [])}


def _cwes_cobertas_por_regras_go():
    """CWEs que o ruleset declara cobrir em regras de linguagem `go`.

    Separa duas afirmações que a distribuição por CWE sozinha confunde: uma CWE
    ausente daqui é fraqueza que o ruleset não promete alcançar em Go; uma CWE
    presente e mesmo assim não detectada é falha dentro do escopo declarado.
    """
    saida = set()
    for regra in _carregar_ruleset().get("rules", []):
        if "go" not in [str(lg).lower() for lg in (regra.get("languages") or [])]:
            continue
        for cwe in _cwes_declaradas(regra):
            saida.add(str(cwe).split(":")[0].strip().upper())
    return saida


def _alerta_cacheado(dir_cache, caso):
    """Payload do cache simbólico do caso, ou `None`."""
    if not caso:
        return None
    from src.cache_simbolico import CacheSimbolico
    destino = CacheSimbolico(dir_cache).caminho(
        caso.repo_name, caso.commit, caso.arquivo, caso.cwe)
    if not os.path.exists(destino):
        return None
    try:
        with open(destino, encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError):
        return None
    payload["_caminho"] = destino
    return payload


def secao_positivos(rodada):
    """Um registro por caso de gabarito vulnerável que chegou ao LLM."""
    _titulo("POSITIVOS — casos de gabarito vulnerável avaliados pelo LLM")

    por_id = defaultdict(dict)
    for br in rodada.bracos:
        for linha in br.linhas:
            if (linha.get("Gabarito") == "vulneravel"
                    and linha.get("Status_Semgrep") == "DETECTADO"):
                por_id[linha["ID_Caso"]][br.prompt] = linha

    indice = _indice_casos()
    regras = _regras_do_ruleset()
    corte = 0 if rodada.args.justificativa_completa else CORTE_JUSTIFICATIVA

    ordenados = sorted(
        por_id.items(),
        key=lambda kv: (_ordem_trilha(next(iter(kv[1].values())).get("Origem", "?")),
                        kv[0]))
    print(f"\n  {len(ordenados)} casos. Cache simbólico consultado em "
          f"`{rodada.args.cache}`.")
    if not regras:
        print("  [!] ruleset local ausente: as CWEs declaradas pela regra que")
        print("      disparou não aparecem (rode scripts/medir_pareamento.py).")

    for pos, (id_caso, linhas) in enumerate(ordenados, 1):
        qualquer = next(iter(linhas.values()))
        caso = indice.get(id_caso)
        payload = _alerta_cacheado(rodada.args.cache, caso)
        print("\n" + "-" * 74)
        print(f"  [{pos:>2}/{len(ordenados)}] {id_caso}")
        print(f"       CWE={qualquer.get('CWE')}  trilha={qualquer.get('Origem')}  "
              f"repo={qualquer.get('Repositorio')}")
        print(f"       Semgrep: {qualquer.get('Classificacao_Semgrep')}")
        if caso:
            print(f"       arquivo: {caso.arquivo}  @ {caso.commit[:12]}")
        if payload:
            alerta = payload.get("alerta") or {}
            check_id = alerta.get("check_id", "?")
            linha_alerta = (alerta.get("start") or {}).get("line", "?")
            declaradas = regras.get(check_id)
            print(f"       regra   : {check_id}  (linha {linha_alerta})")
            if declaradas is not None:
                print(f"       a regra declara: {declaradas or '[]'}")
            print(f"       payload : {payload['_caminho']}  "
                  f"(versao_pareamento={payload.get('versao_pareamento')})")
        for prompt in sorted(linhas):
            linha = linhas[prompt]
            print(f"       [{prompt}] veredito={linha.get('Veredito_LLM')}  "
                  f"-> {linha.get('Classificacao_LLM')}")
            print(f"          {_corta(linha.get('Justificativa'), corte)}")

    print("\n" + "-" * 74)
    print("  A atribuição de causa (erro de gabarito, de emparelhamento ou de")
    print("  julgamento) é julgamento humano e vive no relatório, não aqui: ela")
    print("  exige comparar a location do alerta com a do gabarito caso a caso.")


# ---------------------------------------------------------------------------
# Seção: regras
# ---------------------------------------------------------------------------

def _primeira_cwe(declaradas):
    """Só o identificador da primeira CWE declarada, para caber na tabela."""
    if not declaradas:
        return "-"
    return str(declaradas[0]).split(":")[0].strip()


def secao_regras(rodada):
    """Quais regras do ruleset de fato disparam sobre este corpus.

    Serve à pergunta de viabilidade do relatório: minerar casos a partir das
    regras que o motor possui só faz sentido se o espaço de regras ativas for
    conhecido. O número sai do cache simbólico, porque o CSV da rodada não grava
    qual regra produziu o alerta.
    """
    _titulo("REGRAS — o que o ruleset efetivamente dispara sobre este corpus")

    indice = _indice_casos()
    if not indice:
        print("  (sem índice de casos: seção indisponível)")
        return
    declaradas = _regras_do_ruleset()

    alertas = Counter()
    casa_gabarito = Counter()
    em_vulneravel = Counter()
    casa_em_vulneravel = Counter()
    versoes = Counter()
    sem_cache = 0
    for linha in rodada.unicas:
        payload = _alerta_cacheado(rodada.args.cache, indice.get(linha["ID_Caso"]))
        if payload is None:
            sem_cache += 1
            continue
        versoes[payload.get("versao_pareamento")] += 1
        if payload.get("status_semgrep") != "DETECTADO":
            continue
        check_id = (payload.get("alerta") or {}).get("check_id", "?")
        alertas[check_id] += 1
        cwe = linha.get("CWE", "")
        exato = any(cwe.upper() == str(t).split(":")[0].strip().upper()
                    for t in declaradas.get(check_id, []))
        vulneravel = linha.get("Gabarito") == "vulneravel"
        if exato:
            casa_gabarito[check_id] += 1
        if vulneravel:
            em_vulneravel[check_id] += 1
        if exato and vulneravel:
            casa_em_vulneravel[check_id] += 1

    total = sum(alertas.values())

    # Espaço de regras do ruleset, não só o que disparou: é ele que dimensiona
    # a mineração guiada por regra discutida no relatório.
    ruleset = _carregar_ruleset().get("rules", [])
    if ruleset:
        go = [r for r in ruleset
              if "go" in [str(lg).lower() for lg in (r.get("languages") or [])]]
        com_cwe = [r for r in go if _cwes_declaradas(r)]
        print(f"\n  Ruleset `{(rodada.manifesto or {}).get('semgrep', {}).get('ruleset', '?')}`: "
              f"{len(ruleset)} regras no total, {len(go)} de linguagem `go`, "
              f"{len(com_cwe)} delas com CWE declarada, cobrindo "
              f"{len(_cwes_cobertas_por_regras_go())} CWEs distintas.")

    print(f"\n  {len(alertas)} regras distintas dispararam, produzindo {total} "
          f"alertas pareados sobre {len(rodada.unicas)} casos únicos.")
    if sem_cache:
        print(f"  [!] {sem_cache} casos sem entrada em `{rodada.args.cache}`: "
              f"fora da contagem.")
    if not declaradas:
        print("  [!] ruleset local ausente: as colunas de CWE saem vazias.")

    # Uma entrada regravada sob regra de pareamento posterior descreve outra
    # pipeline, não esta rodada. O aviso existe porque a diferença é invisível
    # na tabela: ela só encolhe silenciosamente as contagens.
    print(f"  versao_pareamento das entradas lidas: "
          f"{ {k: v for k, v in sorted(versoes.items(), key=lambda kv: str(kv[0]))} }")
    if len(versoes) > 1:
        print("  [!] cache MISTO: parte das entradas foi regravada depois da "
              "rodada.\n      Use --cache cache_simbolico_pre_estrito para ler "
              "o estado da rodada.")

    print("\n  Ordem: contagem decrescente, desempate alfabético.\n")
    _tabela(["regra", "CWE declarada", "alertas", "% dos alertas",
             "CWE bate com o gabarito", "sobre gabarito vulnerável"],
            [[regra, _primeira_cwe(declaradas.get(regra)), n, _pct(n, total),
              casa_gabarito[regra], em_vulneravel[regra]]
             for regra, n in sorted(alertas.items(),
                                    key=lambda kv: (-kv[1], kv[0]))])

    bate = sum(casa_gabarito.values())
    print(f"\n  Alertas cuja regra declara a MESMA CWE do gabarito do caso: "
          f"{bate} de {total} ({_pct(bate, total)}).")
    print("  Os demais foram pareados pelo fallback de alerta único da regra de")
    print("  pareamento vigente na rodada — o alerta é o único do arquivo, não")
    print("  o alerta daquela fraqueza.")

    # A mesma contagem separada por classe de gabarito. É a tabela decisiva do
    # relatório: o fallback é quase inofensivo na classe negativa e devastador
    # na positiva, porque a negativa foi construída A PARTIR de achados do
    # Semgrep e a positiva a partir de CVEs.
    vul_bate = sum(casa_em_vulneravel.values())
    vul_total = sum(em_vulneravel.values())
    print("\n  Mesma contagem, separada por classe de gabarito:\n")
    _tabela(["classe", "alertas", "pareamento exato", "pareamento por fallback",
             "% por fallback"],
            [["negativa (gabarito seguro)", total - vul_total,
              bate - vul_bate, (total - vul_total) - (bate - vul_bate),
              _pct((total - vul_total) - (bate - vul_bate), total - vul_total)],
             ["positiva (gabarito vulneravel)", vul_total, vul_bate,
              vul_total - vul_bate, _pct(vul_total - vul_bate, vul_total)]])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Seção: grau de alcançabilidade
# ---------------------------------------------------------------------------

# Trilha cujos casos vêm da colheita filtrada. É a única em que o grau tem o que
# medir: as demais foram colhidas sem consultar o ruleset.
TRILHA_FILTRADA = "TP_alcancavel"


def _agrega_por_grau(linhas, graus, excluir=None):
    """`{grau: (cwes, pares, deteccoes)}`, agregando somas — não médias.

    A agregação é por grupo de propósito: uma CWE com 3 pares não pode pesar o
    mesmo que uma com 124, e a média das taxas por CWE deixaria a escala à mercê
    das caudas pequenas.
    """
    pares, deteccoes, cwes = Counter(), Counter(), {}
    for linha in linhas:
        cwe = linha.get("CWE", "")
        n = _numero_cwe(cwe)
        if n is None or n == excluir:
            continue
        grau = graus.get(n)
        if grau is None:
            continue
        cwes.setdefault(grau, set()).add(n)
        pares[grau] += 1
        if linha.get("Status_Semgrep") == "DETECTADO":
            deteccoes[grau] += 1
    return {g: (len(cwes.get(g, ())), pares[g], deteccoes[g])
            for g in reversed(ORDEM_GRAUS)}


def _linha_taxa(grau, dados):
    cwes, pares, det = dados
    taxa = (100 * det / pares) if pares else 0.0
    return f"  {grau:<7s} {cwes:>5d} {pares:>7d} {det:>7d} {taxa:>8.2f}%"


def secao_grau(rodada):
    """Separação da taxa de detecção entre os graus de alcançabilidade.

    Sem esta medição o grau seria afirmação não verificada. Com ela, qualquer
    rodada devolve a separação real — e é o que permite testar o critério FORA
    da amostra que o gerou, que é a ressalva registrada no design da mudança
    `alcancabilidade-ponderada`.
    """
    _titulo("GRAU — separação da detecção por grau de alcançabilidade")

    linhas = [x for x in rodada.unicas
              if x.get("Origem") == TRILHA_FILTRADA
              and x.get("Gabarito") == "vulneravel"]
    if not linhas:
        print(f"  (rodada sem casos vulneráveis da trilha {TRILHA_FILTRADA}: "
              f"seção indisponível)")
        return

    try:
        graus = graus_alcancabilidade(LINGUAGEM_GRAU)
    except Exception as e:                                   # noqa: BLE001
        print(f"  (ruleset indisponível, seção pulada: {str(e)[:80]})")
        return

    agregado = _agrega_por_grau(linhas, graus)
    print(f"  amostra: {len(linhas)} casos vulneráveis da trilha "
          f"{TRILHA_FILTRADA}")
    print()
    print(f"  {'grau':<7s} {'CWEs':>5s} {'pares':>7s} {'detec.':>7s} {'taxa':>9s}")
    print("  " + "-" * 40)
    for grau, dados in agregado.items():
        print(_linha_taxa(grau, dados))

    # Ganho de densidade: quanto se concentra ao recusar o grau mais baixo.
    _, p_baixa, d_baixa = agregado.get(GRAU_BAIXA, (0, 0, 0))
    p_acima = sum(v[1] for g, v in agregado.items() if g != GRAU_BAIXA)
    d_acima = sum(v[2] for g, v in agregado.items() if g != GRAU_BAIXA)
    t_baixa = (100 * d_baixa / p_baixa) if p_baixa else 0.0
    t_acima = (100 * d_acima / p_acima) if p_acima else 0.0
    print()
    print(f"  acima de {GRAU_BAIXA}: {p_acima} pares, {d_acima} detecções "
          f"({t_acima:.2f}%)")
    print(f"  em {GRAU_BAIXA}     : {p_baixa} pares, {d_baixa} detecções "
          f"({t_baixa:.2f}%)")
    if t_baixa:
        print(f"  ganho de densidade: {t_acima / t_baixa:.1f}x  "
              f"(detecções perdidas se recusasse: {d_baixa})")
    elif d_baixa == 0:
        print(f"  ganho de densidade: grau {GRAU_BAIXA} não produziu detecção "
              f"alguma em {p_baixa} pares")

    # Robustez: a separação depende de uma única CWE?
    por_cwe = Counter()
    for linha in linhas:
        if linha.get("Status_Semgrep") == "DETECTADO":
            n = _numero_cwe(linha.get("CWE", ""))
            if n is not None:
                por_cwe[n] += 1
    if por_cwe:
        dominante, quantas = por_cwe.most_common(1)[0]
        sem = _agrega_por_grau(linhas, graus, excluir=dominante)
        p2 = sum(v[1] for g, v in sem.items() if g != GRAU_BAIXA)
        d2 = sum(v[2] for g, v in sem.items() if g != GRAU_BAIXA)
        _, pb2, db2 = sem.get(GRAU_BAIXA, (0, 0, 0))
        t2 = (100 * d2 / p2) if p2 else 0.0
        tb2 = (100 * db2 / pb2) if pb2 else 0.0
        print()
        print(f"  robustez — sem CWE-{dominante} (a que mais detecta, "
              f"{quantas} de {sum(por_cwe.values())}):")
        print(f"      acima de {GRAU_BAIXA}: {t2:.2f}%  |  em {GRAU_BAIXA}: "
              f"{tb2:.2f}%"
              + (f"  |  ganho {t2 / tb2:.1f}x" if tb2 else "  |  ganho: baixa "
                 "segue sem detecção"))

    print()
    print("  RESSALVA: o critério do grau foi derivado OLHANDO a taxa desta")
    print("  rodada. A separação acima é OBSERVADA nesta amostra, não prevista.")
    print("  Validá-lo exige repetir esta seção sobre uma rodada que não o gerou.")


DESPACHO = {
    "funil": secao_funil,
    "nao-detectados": secao_nao_detectados,
    "conjuntos": secao_conjuntos,
    "esteira": secao_esteira,
    "positivos": secao_positivos,
    "regras": secao_regras,
    "grau": secao_grau,
}


def _ler_manifesto(caminho):
    destino = os.path.join(caminho, "manifesto.json")
    if not os.path.exists(destino):
        return None
    try:
        with open(destino, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(
        description="Números derivados de uma rodada, para o relatório de "
                    "análise. Somente-leitura e offline.",
        epilog=EPILOGO,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rodada", help="Diretório da rodada (results/<run_id>/).")
    ap.add_argument("--secao", choices=SECOES,
                    help="Imprime só esta seção. Omitido, imprime todas na "
                         "ordem fixa.")
    ap.add_argument("--cache", default="cache_simbolico",
                    help="Diretório do cache simbólico consultado pela seção "
                         "`positivos` (padrão: cache_simbolico). Use "
                         "cache_simbolico_pre_estrito para ler o cache como "
                         "estava na rodada, se a regra de pareamento mudou "
                         "depois dela.")
    ap.add_argument("--justificativa-completa", action="store_true",
                    help="Não trunca as justificativas do LLM na seção "
                         "`positivos`.")
    args = ap.parse_args()

    if not os.path.isdir(args.rodada):
        _erro(f"{args.rodada!r} não é um diretório. Esperado o diretório de "
              f"uma rodada, como results/<run_id>/.")
    if not glob.glob(os.path.join(args.rodada, "*.csv")):
        _erro(f"nenhum CSV de rodada em {args.rodada!r}. Uma rodada tem um CSV "
              f"por braço; confira o caminho.")

    rodada = Rodada(args.rodada, carregar(args.rodada),
                    _ler_manifesto(args.rodada), args)

    print(f"rodada: {args.rodada}  |  braços: "
          f"{', '.join(br.rotulo for br in rodada.bracos)}")
    for nome in ([args.secao] if args.secao else SECOES):
        DESPACHO[nome](rodada)
    print()


if __name__ == "__main__":
    main()
