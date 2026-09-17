"""
particionar_avaliacao.py — separa, ANTES de qualquer regra existir, os casos que
podem ser olhados para escrever regra dos casos que só servem para medir.

Por que existe
--------------
Escrever regra do Semgrep olhando os casos em que ela vai ser medida é ajustar
ao conjunto de teste. O número resultante não mede a capacidade da análise
sintática de encontrar a fraqueza em código Go — mede a nossa capacidade de
descrever arquivos que já vimos. Uma banca tem razão de não acreditar num número
produzido assim.

A separação precisa ser ESTRUTURAL, não disciplinar: não basta pretender não
olhar. Este script é a primeira das camadas. As outras são a proveniência
declarada por regra (`regras/go/`) e o relatório que recusa fundir as partições
(`scripts/medir_regras_locais.py`).

Três propriedades, e cada uma fecha um buraco diferente:

- **Determinística, sem semente.** A partição é derivada do identificador do
  caso. Não há semente para trocar até o número melhorar, e quem tiver a
  população reproduz a partição sem precisar confiar em nada nosso.
- **Agrupada por `(CWE, repositório)`.** Pares da mesma CWE no mesmo repositório
  compartilham idioma de código e às vezes o mesmo helper; separá-los vazaria
  informação do desenvolvimento para a avaliação (design.md, D7).
- **Recusa reparticionar.** Reparticionar depois que as regras existem anula a
  separação, e nada no artefato final denunciaria. A ordem — partição antes de
  regra — é auditável no histórico do Git, e só vale enquanto a partição não for
  reescrita.

USO
  python scripts/particionar_avaliacao.py --cwe CWE-22 --cwe CWE-918
  python scripts/particionar_avaliacao.py --selftest   # valida a lógica, sem escrever
  python scripts/particionar_avaliacao.py --forcar     # só antes da primeira regra
"""
import argparse
import collections
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import run_pipeline as rp  # noqa: E402
from src.config import DATA_DIR  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(DATA_DIR, "particao_avaliacao.json")

DESENVOLVIMENTO = "desenvolvimento"
AVALIACAO = "avaliacao"

# Versão do PROTOCOLO de partição. Subir isto muda a partição derivada, e por
# isso só pode acontecer antes de a primeira regra existir — depois, mudar o
# protocolo é reparticionar por outro nome.
VERSAO_PROTOCOLO = 1


class ParticaoJaExisteError(Exception):
    """A partição já está em disco e uma nova foi pedida.

    É erro, e não sobrescrita, porque a sobrescrita é silenciosa: o arquivo novo
    tem a mesma cara do antigo e só o histórico do Git saberia dizer que a
    separação foi refeita depois de as regras existirem — que é exatamente a
    manobra que este protocolo existe para impedir.
    """


def chave_grupo(caso) -> tuple:
    """A unidade que vai inteira para uma partição: `(CWE, repositório)`.

    Não é o caso, e não é o par. O par não se divide porque vulnerável e
    corrigido são o mesmo arquivo em dois commits. O repositório não se divide
    porque casos da mesma CWE no mesmo repositório compartilham idioma (D7).
    """
    return (caso.cwe, caso.repo_name)


def _digest(chave) -> str:
    return hashlib.sha256("|".join(chave).encode("utf-8")).hexdigest()


def particionar(casos, cwes_alvo):
    """`{ID_Caso: partição}` para os casos das CWEs alvo.

    A ordem de percurso é a do digest SHA-256 da chave do grupo — estável,
    reproduzível e diferente da ordem do arquivo, de modo que acrescentar um par
    no fim do pool não empurre todos os outros de lado. Cada grupo vai para a
    partição que estiver menor naquele momento.

    O balanceamento guloso não é enfeite: a alternativa mais simples — paridade
    do digest — desequilibrava por causa dos repositórios de cabeça (CWE-22
    ficava 126 contra 102 casos), e uma partição de avaliação pequena demais
    deixa de servir como denominador.
    """
    alvo = {str(c).upper() for c in cwes_alvo}
    grupos = collections.defaultdict(list)
    for caso in casos:
        if str(caso.cwe).upper() in alvo:
            grupos[chave_grupo(caso)].append(caso.id)

    particao = {}
    for cwe in sorted({k[0] for k in grupos}):
        tamanhos = {DESENVOLVIMENTO: 0, AVALIACAO: 0}
        chaves = sorted((k for k in grupos if k[0] == cwe), key=_digest)
        for chave in chaves:
            lado = (DESENVOLVIMENTO
                    if tamanhos[DESENVOLVIMENTO] <= tamanhos[AVALIACAO]
                    else AVALIACAO)
            ids = sorted(grupos[chave])
            tamanhos[lado] += len(ids)
            for id_caso in ids:
                particao[id_caso] = lado
    return particao


def resumo(casos, particao):
    """`{CWE: {partição: n}}` — o que confirma que a estratificação funcionou."""
    por_cwe = collections.defaultdict(collections.Counter)
    for caso in casos:
        lado = particao.get(caso.id)
        if lado:
            por_cwe[caso.cwe][lado] += 1
    return {cwe: dict(c) for cwe, c in sorted(por_cwe.items())}


def carregar_casos():
    """A população alvo, com os `ID_Caso` que a pipeline realmente usa.

    Os identificadores vêm de `run_pipeline.construir_casos_tp`, importado e não
    reimplementado: uma partição indexada por IDs derivados de outra regra não
    casaria com CSV nenhum, e o erro só apareceria na hora de medir.
    """
    with open(rp.DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)
    return rp.construir_casos_tp(rp.TP_PAIRS_ALCANCAVEL, "TP_alcancavel",
                                 rp._cwe_lookup(dataset), prefixo_id="TPA:")


def gravar(destino, particao, casos, cwes_alvo, forcar=False):
    if os.path.exists(destino) and not forcar:
        raise ParticaoJaExisteError(
            f"{os.path.relpath(destino, BASE)} já existe. Reparticionar depois "
            "de escrever regra anula a separação entre o que foi usado para "
            "escrever e o que é usado para medir. Se a partição ainda não "
            "precede regra alguma, use --forcar; se já precede, não use.")
    payload = {
        "versao_protocolo": VERSAO_PROTOCOLO,
        "derivada_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "populacao": os.path.relpath(rp.TP_PAIRS_ALCANCAVEL, BASE),
        "cwes_alvo": sorted(str(c).upper() for c in cwes_alvo),
        "unidade": "(CWE, repositorio)",
        "resumo": resumo(casos, particao),
        "particao": dict(sorted(particao.items())),
    }
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return destino


def carregar_particao(destino=DESTINO):
    """A partição gravada, ou `None` se ainda não existe."""
    if not os.path.exists(destino):
        return None
    with open(destino, encoding="utf-8") as f:
        return json.load(f)


# -- selftest ---------------------------------------------------------------

class _CasoFalso:
    def __init__(self, id, cwe, repo_name):
        self.id, self.cwe, self.repo_name = id, cwe, repo_name


def _populacao_sintetica():
    """Dois repositórios de cabeça e uma cauda, em duas CWEs."""
    casos = []
    for cwe, repos in (("CWE-22", 8), ("CWE-918", 6)):
        for i in range(repos):
            # O primeiro repositório de cada CWE concentra vários pares: é o
            # caso que o agrupamento por repositório existe para proteger.
            pares = 5 if i == 0 else 1
            for j in range(pares):
                for versao in ("vuln", "fix"):
                    casos.append(_CasoFalso(f"TPA:r{i}:{cwe}:f{j}:{versao}",
                                            cwe, f"org/repo{i}"))
    return casos


def selftest():
    """Valida determinismo, estratificação e integridade do grupo, sem escrever."""
    falhas = []

    def checa(rotulo, ok, detalhe=""):
        print(f"  {'ok  ' if ok else 'FALHA'} {rotulo}{detalhe}")
        if not ok:
            falhas.append(rotulo)

    print("=== SELFTEST (não escreve em disco) ===")
    casos = _populacao_sintetica()
    alvo = ["CWE-22", "CWE-918"]
    a = particionar(casos, alvo)
    b = particionar(list(reversed(casos)), alvo)

    print("-- determinismo --")
    checa("mesma população, mesmo resultado", a == b)
    checa("a ordem da população não altera a partição",
          all(a[k] == b[k] for k in a))

    print("-- estratificação por CWE --")
    r = resumo(casos, a)
    for cwe in alvo:
        lados = r.get(cwe, {})
        checa(f"{cwe} tem casos nas duas partições",
              lados.get(DESENVOLVIMENTO, 0) > 0 and lados.get(AVALIACAO, 0) > 0,
              f": {lados}")

    print("-- integridade do grupo --")
    por_grupo = collections.defaultdict(set)
    for caso in casos:
        por_grupo[chave_grupo(caso)].add(a[caso.id])
    checa("nenhum (CWE, repositório) atravessa as duas partições",
          all(len(v) == 1 for v in por_grupo.values()))

    por_par = collections.defaultdict(set)
    for caso in casos:
        por_par[caso.id.rsplit(":", 1)[0]].add(a[caso.id])
    checa("vulnerável e corrigido do mesmo par caem juntos",
          all(len(v) == 1 for v in por_par.values()))

    print("-- recusa de reparticionamento --")
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        destino = os.path.join(tmp, "particao.json")
        gravar(destino, a, casos, alvo)
        try:
            gravar(destino, a, casos, alvo)
            checa("segunda gravação falha", False)
        except ParticaoJaExisteError:
            checa("segunda gravação falha com erro explícito", True)

    print("\n" + ("SELFTEST OK" if not falhas
                  else f"SELFTEST FALHOU: {falhas}"))
    return 0 if not falhas else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1],
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--cwe", action="append", metavar="CWE",
                    help="CWE alvo (repetível). Padrão: CWE-22 e CWE-918.")
    ap.add_argument("--destino", default=DESTINO)
    ap.add_argument("--forcar", action="store_true",
                    help="sobrescreve a partição — só antes da primeira regra.")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    cwes = args.cwe or ["CWE-22", "CWE-918"]
    casos = carregar_casos()
    particao = particionar(casos, cwes)
    if not particao:
        print(f"[!] nenhum caso para {cwes} na população.")
        return 1

    try:
        destino = gravar(args.destino, particao, casos, cwes,
                         forcar=args.forcar)
    except ParticaoJaExisteError as e:
        # Mensagem, e não traceback: a recusa é resultado esperado do protocolo,
        # não defeito do script.
        print(f"[!] {e}")
        return 1
    print(f"[+] partição gravada: {os.path.relpath(destino, BASE)}")
    for cwe, lados in resumo(casos, particao).items():
        print(f"    {cwe}: " + " | ".join(f"{k} {v}" for k, v in
                                          sorted(lados.items())))
    print("[!] COMMITE ESTE ARQUIVO SOZINHO, antes de escrever qualquer regra.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
