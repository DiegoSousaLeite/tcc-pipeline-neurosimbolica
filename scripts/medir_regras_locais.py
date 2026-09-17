"""
medir_regras_locais.py — quanto as regras de `regras/go/` detectam, por partição.

Por que existe
--------------
O relatório é a última das três camadas que separam escrever de medir. A
primeira é a partição, gravada antes de qualquer regra
(`scripts/particionar_avaliacao.py`); a segunda é a proveniência declarada por
regra (`src/regras_locais.py`); esta é a que **recusa emitir o número que não se
pode defender**.

A recusa é explícita, e não um aviso, porque aviso não impede citação. A
experiência do projeto com métricas é que o número mais fácil de copiar é o que
acaba no texto, e um agregado que mistura a partição em que as regras foram
escritas com a partição em que elas são medidas é exatamente o número
indefensável. Recusar produzi-lo é a única mitigação que ainda funciona meses
depois, quando o contexto tiver se perdido.

A exceção é deliberada: se TODAS as regras carregadas forem de proveniência
`definicao`, o agregado sai. Nenhum caso da população informou a escrita delas,
então não há o que contaminar — e preservar os 114 casos de CWE-22 como
denominador é justamente o que torna o protocolo `definicao` preferível.

Cada número sai rotulado com a partição e o protocolo que o sustentam, na mesma
linha, para que copiá-lo sem a ressalva seja desconfortável.

USO
  python scripts/medir_regras_locais.py                  # por partição
  python scripts/medir_regras_locais.py --agregado       # só se tudo for `definicao`
  python scripts/medir_regras_locais.py --limite 20      # amostra, para ensaiar
  python scripts/medir_regras_locais.py --selftest       # valida a lógica, sem motor
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import run_pipeline as rp  # noqa: E402
from src import regras_locais  # noqa: E402
from src.cache_simbolico import CacheSimbolico  # noqa: E402
from src.config import CACHE_SIMBOLICO_DIR  # noqa: E402
from src.fase1_semgrep import (  # noqa: E402
    SemgrepError,
    SemgrepFileNotFoundError,
    SemgrepTimeoutError,
    executar_semgrep,
    identidade_conjunto,
)
from src.fonte import ArquivoInexistente, FetchError, obter_arquivo  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from particionar_avaliacao import (  # noqa: E402
    AVALIACAO,
    DESENVOLVIMENTO,
    carregar_particao,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# O ruleset medido é SÓ o local. Medir com `p/default` junto responderia outra
# pergunta — quanto o conjunto detecta —, e a lacuna que esta change existe para
# preencher já está medida: zero, nas duas CWEs alvo.
RULESET_LOCAL = "regras/go"

# Cache PRÓPRIO, e não o compartilhado. O caminho de uma entrada de cache não
# carrega a identidade do ruleset — só o motor entra no nome —, então gravar a
# medição no cache comum SOBRESCREVE, no mesmo caminho, a entrada de
# `p/default` daquele caso. A entrada sobrescrita não seria servida por engano
# (a identidade diverge e ela é recomputada), mas se perderia, e recompor as
# ~1.900 entradas da população custa horas de Semgrep.
#
# Diretório próprio em vez de identidade no caminho: pôr o ruleset no nome do
# arquivo invalidaria por caminho todas as entradas já em disco, que é
# exatamente o que a identidade do conjunto unitário foi desenhada para evitar.
CACHE_MEDICAO = os.path.join(CACHE_SIMBOLICO_DIR, "_regras_locais")

VULNERAVEL = "vulneravel"
SEGURO = "seguro"


class AgregadoNaoReportavelError(Exception):
    """Pediram um número sobre a população inteira com regra `desenvolvimento`.

    O número da partição de desenvolvimento é diagnóstico interno: diz se a
    regra faz o que se pretendia. O da partição de avaliação é o resultado.
    Somá-los produz a estatística que não se pode defender.
    """


class Medicao(collections.namedtuple(
        "Medicao", "cwe particao gabarito total detectados")):
    """Um número, e tudo de que ele precisa para não ser citado sozinho."""

    @property
    def taxa(self):
        return (self.detectados / self.total) if self.total else 0.0


def _protocolos(proveniencias) -> str:
    return "+".join(sorted(proveniencias)) if proveniencias else "sem regra"


def agregar(resultados, particao):
    """`[(cwe, partição, gabarito)] -> Medicao`, a partir dos casos medidos.

    `resultados` é uma sequência de `(caso, detectado)`. A agregação é separada
    da execução do motor para que o `--selftest` possa exercitar a decisão sem
    invocar Semgrep algum.
    """
    contagem = collections.defaultdict(lambda: [0, 0])
    for caso, detectado in resultados:
        lado = particao.get(caso.id)
        if lado is None:
            continue
        chave = (caso.cwe, lado, caso.gabarito)
        contagem[chave][0] += 1
        contagem[chave][1] += int(bool(detectado))
    return [Medicao(cwe, lado, gabarito, total, det)
            for (cwe, lado, gabarito), (total, det) in sorted(contagem.items())]


def agregar_populacao_inteira(resultados, proveniencias):
    """O número sobre a população inteira — se o protocolo permitir.

    Levanta `AgregadoNaoReportavelError` quando há qualquer regra
    `desenvolvimento` carregada. Não devolve `None`, não avisa e não emite
    parcial: um agregado recusado precisa ser impossível de citar por engano.
    """
    if regras_locais.DESENVOLVIMENTO in proveniencias:
        raise AgregadoNaoReportavelError(
            "há regra de proveniência 'desenvolvimento' carregada: o número "
            "sobre a população inteira não é reportável, porque parte dos casos "
            "informou a escrita das regras. Reporte a partição de avaliação, "
            "rotulada, e a de desenvolvimento como diagnóstico interno.")
    contagem = collections.defaultdict(lambda: [0, 0])
    for caso, detectado in resultados:
        contagem[(caso.cwe, caso.gabarito)][0] += 1
        contagem[(caso.cwe, caso.gabarito)][1] += int(bool(detectado))
    return [Medicao(cwe, "populacao inteira", gabarito, total, det)
            for (cwe, gabarito), (total, det) in sorted(contagem.items())]


def linhas_do_relatorio(medicoes, proveniencias):
    """Uma linha por número, com partição e protocolo na MESMA linha.

    Não é formatação: é o que torna o número desconfortável de copiar sem a
    ressalva. Um relatório que imprimisse a ressalva num cabeçalho distante
    seria copiado sem ela na primeira vez que alguém recortasse uma tabela.
    """
    protocolo = _protocolos(proveniencias)
    linhas = []
    for m in medicoes:
        papel = ("detecção" if m.gabarito == VULNERAVEL
                 else "disparo na versão corrigida")
        linhas.append(
            f"{m.cwe:9s} | partição: {m.particao:18s} | protocolo: {protocolo:26s}"
            f" | {papel}: {m.detectados}/{m.total} ({m.taxa:.1%})")
    return linhas


# -- execução ---------------------------------------------------------------

def casos_alvo(cwes_alvo, particao, limite=None):
    """Os casos das CWEs alvo que a partição conhece."""
    with open(rp.DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)
    casos = rp.construir_casos_tp(rp.TP_PAIRS_ALCANCAVEL, "TP_alcancavel",
                                  rp._cwe_lookup(dataset), prefixo_id="TPA:")
    alvo = {str(c).upper() for c in cwes_alvo}
    selecao = [c for c in casos
               if str(c.cwe).upper() in alvo and c.id in particao]
    selecao.sort(key=lambda c: c.id)
    return selecao[:limite] if limite else selecao


def medir(casos, diretorio_regras=None, cache=None, verboso=False):
    """`[(caso, detectado)]`, rodando o ruleset local sobre cada caso.

    Detecção é o mesmo critério da Fase 1: a regra que emitiu o alerta declara a
    CWE do gabarito. Reaproveitar o critério não é economia — é o que impede que
    o número desta medição signifique algo diferente do número da pipeline.
    """
    configs = (diretorio_regras or RULESET_LOCAL,)
    cache = cache if cache is not None else CacheSimbolico(
        diretorio=CACHE_MEDICAO, versao_ruleset=identidade_conjunto(configs))
    resultados, falhas = [], []
    for i, caso in enumerate(casos, 1):
        payload = cache.ler(caso.repo_name, caso.commit, caso.arquivo, caso.cwe)
        if payload is not None:
            resultados.append((caso, payload["status_semgrep"] == "DETECTADO"))
            continue
        try:
            caminho = obter_arquivo(caso.repo_name, caso.commit, caso.arquivo)
            r = executar_semgrep(caminho, caso.cwe, configs=configs)
        except (ArquivoInexistente, FetchError, SemgrepError,
                SemgrepTimeoutError, SemgrepFileNotFoundError) as e:
            # Falha de esteira não é não-detecção, e não pode ser cacheada como
            # tal: viraria ponto cego permanente atribuído às regras.
            falhas.append((caso.id, type(e).__name__))
            continue
        detectado = r.alerta is not None
        cache.gravar(caso.repo_name, caso.commit, caso.arquivo, caso.cwe,
                     "DETECTADO" if detectado else "NAO_DETECTADO",
                     alerta=r.alerta, motivo=r.motivo,
                     regras_nao_casadas=r.regras_nao_casadas)
        resultados.append((caso, detectado))
        if verboso:
            print(f"  [{i}/{len(casos)}] {caso.id}: "
                  f"{'DETECTADO' if detectado else 'nao'}")
    return resultados, falhas


# -- selftest ---------------------------------------------------------------

class _CasoFalso(collections.namedtuple("_CasoFalso", "id cwe gabarito")):
    pass


def selftest():
    """Cobre as duas situações: só `definicao`, e com `desenvolvimento`."""
    falhas = []

    def checa(rotulo, ok, detalhe=""):
        print(f"  {'ok  ' if ok else 'FALHA'} {rotulo}{detalhe}")
        if not ok:
            falhas.append(rotulo)

    print("=== SELFTEST (não invoca o motor) ===")
    casos = [_CasoFalso(f"TPA:r:CWE-22:f{i}:vuln", "CWE-22", VULNERAVEL)
             for i in range(10)]
    particao = {c.id: (DESENVOLVIMENTO if i < 5 else AVALIACAO)
                for i, c in enumerate(casos)}
    # 4 detecções no desenvolvimento, 1 na avaliação: o desequilíbrio que o
    # agregado esconderia.
    detectados = {c.id for c in casos[:4]} | {casos[5].id}
    resultados = [(c, c.id in detectados) for c in casos]

    print("-- números por partição --")
    medicoes = {(m.particao): m for m in agregar(resultados, particao)}
    checa("desenvolvimento: 4/5",
          (medicoes[DESENVOLVIMENTO].detectados,
           medicoes[DESENVOLVIMENTO].total) == (4, 5))
    checa("avaliação: 1/5",
          (medicoes[AVALIACAO].detectados, medicoes[AVALIACAO].total) == (1, 5))

    print("-- cada número carrega a sua ressalva --")
    linhas = linhas_do_relatorio(agregar(resultados, particao),
                                 {regras_locais.DEFINICAO})
    checa("partição e protocolo na mesma linha",
          all("partição:" in ln and "protocolo:" in ln for ln in linhas))

    print("-- só `definicao`: o agregado sai --")
    try:
        agregado = agregar_populacao_inteira(resultados,
                                             {regras_locais.DEFINICAO})
        checa("agregado emitido sobre os 10 casos",
              (agregado[0].detectados, agregado[0].total) == (5, 10))
    except AgregadoNaoReportavelError:
        checa("agregado emitido sobre os 10 casos", False)

    print("-- com `desenvolvimento`: o agregado é recusado --")
    try:
        agregar_populacao_inteira(resultados, {regras_locais.DEFINICAO,
                                               regras_locais.DESENVOLVIMENTO})
        checa("agregado recusado com erro explícito", False)
    except AgregadoNaoReportavelError as e:
        checa("agregado recusado com erro explícito",
              "não é reportável" in str(e))

    print("\n" + ("SELFTEST OK" if not falhas else f"SELFTEST FALHOU: {falhas}"))
    return 0 if not falhas else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1],
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--cwe", action="append", metavar="CWE",
                    help="CWE alvo (repetível). Padrão: as da partição.")
    ap.add_argument("--regras", default=RULESET_LOCAL,
                    help="diretório do ruleset local.")
    ap.add_argument("--limite", type=int, metavar="N",
                    help="mede só os N primeiros casos, para ensaiar.")
    ap.add_argument("--agregado", action="store_true",
                    help="pede o número sobre a população inteira.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verboso", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    particao_payload = carregar_particao()
    if particao_payload is None:
        print("[!] partição ausente. Rode scripts/particionar_avaliacao.py "
              "ANTES de medir — e antes de escrever regra.")
        return 1
    particao = particao_payload["particao"]
    cwes = args.cwe or particao_payload["cwes_alvo"]

    proveniencias = regras_locais.proveniencias(
        args.regras if os.path.isabs(args.regras)
        else os.path.join(BASE, args.regras))
    if not proveniencias:
        print(f"[!] nenhuma regra local em {args.regras}.")
        return 1

    casos = casos_alvo(cwes, particao, limite=args.limite)
    print(f"[+] medindo {len(casos)} casos | ruleset {args.regras} | "
          f"protocolo {_protocolos(proveniencias)}")
    resultados, falhas = medir(casos, args.regras, verboso=args.verboso)

    medicoes = agregar(resultados, particao)
    saida = {
        "ruleset": args.regras,
        "protocolos": sorted(proveniencias),
        "casos_medidos": len(resultados),
        "falhas_de_esteira": len(falhas),
        "por_particao": [m._asdict() | {"taxa": round(m.taxa, 4)}
                         for m in medicoes],
    }

    print()
    for linha in linhas_do_relatorio(medicoes, proveniencias):
        print("  " + linha)

    if args.agregado:
        print()
        try:
            agregado = agregar_populacao_inteira(resultados, proveniencias)
        except AgregadoNaoReportavelError as e:
            print(f"  [RECUSADO] {e}")
            saida["agregado"] = {"recusado": str(e)}
            if args.json:
                print(json.dumps(saida, ensure_ascii=False, indent=1))
            return 1
        for linha in linhas_do_relatorio(agregado, proveniencias):
            print("  " + linha)
        saida["agregado"] = [m._asdict() | {"taxa": round(m.taxa, 4)}
                             for m in agregado]

    if falhas:
        print(f"\n  [!] {len(falhas)} falhas de esteira (não contadas como "
              f"não-detecção): {falhas[:3]}")
    if args.json:
        print(json.dumps(saida, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
