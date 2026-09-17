"""ruleset.py — o que o motor simbólico alcança, e em qual linguagem.

Por que existe
--------------
Três consumidores (colheita de população, trilha TP, rodada da classe positiva)
precisam da mesma resposta: *o motor simbólico tem regra para esta CWE nesta
linguagem?* Sem um lugar único, cada um reimplementa a extração de `metadata.cwe`
e a comparação de identificadores — e a chance de reintroduzir o casamento por
substring recém-corrigido na Fase 1 é alta.

Duas decisões que este módulo materializa:

- **A alcançabilidade é por linguagem.** Nenhuma regra de Python dispara sobre um
  arquivo `.go`. O campo `languages`, que o carregamento anterior descartava, é o
  que separa "o ruleset cobre esta CWE em abstrato" de "o motor a detecta neste
  arquivo".
- **O conjunto é derivado do catálogo, nunca embutido no código.** O ruleset é
  configurável por `SEMGREP_CONFIG`; uma lista fixa passaria a mentir no instante
  em que ele mudasse, e mentiria em silêncio.

O que ele NÃO é: fonte da regra de pareamento. A comparação vem de
`fase1_semgrep._numero_cwe`, importada e não copiada — se a alcançabilidade
aceitasse por um critério e o pareamento recusasse por outro, a colheita
produziria casos que a Fase 1 descartaria.
"""
import json
import os
import re
from datetime import datetime
from typing import NamedTuple

from .config import CACHE_SIMBOLICO_DIR
from .fase1_semgrep import SEMGREP_CONFIG, _numero_cwe


class RulesetIndisponivelError(Exception):
    """Não há cache do ruleset nem como buscá-lo.

    É erro, e não conjunto vazio de propósito: conjunto vazio faria toda CWE
    parecer inalcançável e recusaria a população inteira EM SILÊNCIO — o mesmo
    modo de falha do `settings.yml` corrompido, em que saída vazia virou "nenhum
    achado" e produziu 200 não-detecções falsas.
    """


class Regra(NamedTuple):
    """Uma regra do ruleset, reduzida ao que decide alcançabilidade.

    `subcategorias` e `taint` são os dois eixos do grau (ver `GRAU_*`). Ambos
    vêm declarados na própria regra, e não de julgamento nosso sobre a CWE:
    `subcategory` distingue "isto é uma vulnerabilidade" de "olhe isto", e
    `mode: taint` marca a regra que precisa de origem e destino no mesmo
    arquivo. Trazem valor neutro quando ausentes, para que ruleset sem esses
    metadados degrade ao comportamento binário em vez de quebrar.
    """

    cwes: list
    linguagens: list
    subcategorias: tuple = ()
    taint: bool = False


class Snapshot(NamedTuple):
    """De onde veio o ruleset em uso e quando.

    `obtido_em` é a data de escrita do arquivo de cache. Serve para tornar
    visível a divergência já observada entre o snapshot do registry e o Semgrep
    instalado (`docs/ANALISE-RODADA-2.md` §6.1): as duas fontes são catálogos
    diferentes, e só a data diz quão velho é o daqui.
    """

    origem: str
    caminho: str
    obtido_em: str
    regras: int


def url_registry(config=SEMGREP_CONFIG):
    """URL do ruleset no registry do Semgrep."""
    return f"https://semgrep.dev/c/{config}"


def caminho_cache(config=SEMGREP_CONFIG):
    """Cache do ruleset, com o nome derivado da configuração.

    O nome carrega a configuração (`p/default` -> `_regras_p_default.json`)
    porque um nome fixo serviria o catálogo de `p/default` depois de trocar
    `SEMGREP_CONFIG`, sem nada denunciar a troca.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "_", str(config)).strip("_")
    return os.path.join(CACHE_SIMBOLICO_DIR, f"_regras_{slug}.json")


def _lista(cwe):
    """`metadata.cwe` vem ora como lista, ora como string única no registry.

    Tratar a string como iterável percorreria CARACTERES e nenhuma regra
    casaria — a alcançabilidade sairia vazia sem erro algum.
    """
    if cwe is None:
        return []
    return [cwe] if isinstance(cwe, str) else list(cwe)


# Graus de alcançabilidade, em ordem crescente.
#
# A consulta binária responde "existe regra?". Medido sobre os 690 pares da
# trilha `TP_alcancavel` da rodada `20260908T094808Z-9a00cb2`, essa resposta
# comporta realidades muito diferentes:
#
#     alta  →  115 pares,  13 detecções  (11,30 %)
#     media →  239 pares,   4 detecções  ( 1,67 %)
#     baixa →  336 pares,   1 detecção   ( 0,30 %)
#
# A escala é ordinal e não contínua de propósito: 18 detecções não pagam a
# precisão que um score sugeriria. E a separação foi observada DENTRO da amostra
# que a gerou — validar fora dela depende de rodada futura
# (`scripts/analise_rodada.py --secao grau`).
GRAU_BAIXA = "baixa"
GRAU_MEDIA = "media"
GRAU_ALTA = "alta"
ORDEM_GRAUS = (GRAU_BAIXA, GRAU_MEDIA, GRAU_ALTA)

# Vocabulário do `metadata.subcategory` que afirma detecção de vulnerabilidade.
# Qualquer outro valor — inclusive ausência — conta como auditoria, que é o lado
# conservador: erra para o grau baixo, nunca para o alto.
_SUBCATEGORIA_VULN = "vuln"


def _obter_ruleset(url):
    """Busca o ruleset no registry. Isolada para que o teste possa derrubá-la."""
    import requests

    resp = requests.get(url, timeout=120, headers={"User-Agent": "semgrep"})
    resp.raise_for_status()
    return resp.content


def _garantir_cache(destino, url):
    if os.path.exists(destino):
        return
    try:
        conteudo = _obter_ruleset(url)
    except Exception as e:
        raise RulesetIndisponivelError(
            f"sem cache do ruleset em {destino} e sem como buscar {url}: {e}"
        ) from e
    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    with open(destino, "wb") as f:
        f.write(conteudo)


# Releitura do JSON (2 MB) a cada consulta custaria caro num laço sobre a
# população inteira. A chave inclui mtime e tamanho: refazer a busca invalida a
# memória sozinha, sem que o consumidor precise saber que ela existe.
_MEMORIA = {}


def carregar_regras(destino=None, config=SEMGREP_CONFIG):
    """`check_id` -> `Regra(cwes, linguagens)`, do cache ou do registry."""
    destino = os.path.abspath(destino or caminho_cache(config))
    _garantir_cache(destino, url_registry(config))

    st = os.stat(destino)
    chave = (destino, st.st_mtime_ns, st.st_size)
    if chave in _MEMORIA:
        return _MEMORIA[chave]

    with open(destino, encoding="utf-8") as f:
        dados = json.load(f)
    regras = {
        r["id"]: Regra(
            cwes=_lista((r.get("metadata") or {}).get("cwe")),
            linguagens=list(r.get("languages") or []),
            subcategorias=tuple(
                _lista((r.get("metadata") or {}).get("subcategory"))),
            taint=(r.get("mode") == "taint"),
        )
        for r in dados.get("rules", [])
    }
    _MEMORIA.clear()          # só interessa o snapshot corrente
    _MEMORIA[chave] = regras
    return regras


class Alcancaveis(frozenset):
    """Conjunto de CWEs alcançáveis, que também sabe dizer se é piso.

    Herda de `frozenset` — e não de `NamedTuple` — porque a qualificação é
    informação EXTRA sobre um conjunto, não uma estrutura nova. Como tupla, ela
    quebrava `== {77, 918}`, união, diferença e tudo mais que os três
    consumidores já fazem com a resposta; a marcação de incerteza não pode
    custar a semântica de conjunto, senão ela é removida na primeira vez que
    alguém precisar comparar dois resultados.
    """

    def __new__(cls, cwes=(), limite_inferior=False):
        obj = super().__new__(cls, cwes)
        obj.limite_inferior = bool(limite_inferior)
        return obj


def cwes_alcancaveis(linguagem, destino=None, config=SEMGREP_CONFIG,
                     entre_arquivos=False):
    """CWEs que alguma regra DA LINGUAGEM declara, com a incerteza declarada.

    Devolve números inteiros, não strings: `CWE-077` e `CWE-77` são a mesma
    fraqueza escrita de duas formas, e comparar texto as separaria.

    Sob o modo entre-arquivos o conjunto é marcado como **limite inferior**. As
    regras próprias desse modo não constam do catálogo público do registry, e
    não há como derivá-las honestamente daqui. Duas saídas erradas foram
    descartadas: estimar a cobertura extra (inventaria número) e tratar o
    conjunto aberto como exato (recusaria, na colheita, população que o motor
    detectaria — o defeito exato que esta capability existe para prevenir).
    Declarar a incerteza é a única saída que não mente.

    Isso foi confirmado na prática: na etapa real do portão, o Pro emitiu
    alertas de regras que o CE não tinha — `gin-command-injection-taint`,
    `gin-tainted-url-host`, `jwt-hardcoded-jwt-key` — nenhuma delas derivável
    do catálogo aberto.
    """
    alvo = str(linguagem).casefold()
    numeros = set()
    for regra in carregar_regras(destino, config).values():
        if not any(str(lin).casefold() == alvo for lin in regra.linguagens):
            continue
        for tag in regra.cwes:
            numero = _numero_cwe(tag)
            if numero is not None:
                numeros.add(numero)
    return Alcancaveis(numeros, limite_inferior=entre_arquivos)


def cwe_alcancavel(cwe, linguagem, destino=None, config=SEMGREP_CONFIG,
                   entre_arquivos=False):
    """Alguma regra da linguagem declara ESTA CWE?

    O casamento é pelo número inteiro, com `_numero_cwe` da Fase 1: `CWE-77` e
    `CWE-770` são fraquezas distintas e ambas estão na população.

    A resposta continua binária de propósito. Sob modo entre-arquivos ela é
    conservadora — um `False` significa "não consta do catálogo aberto", e não
    "o motor não detecta": use `cwes_alcancaveis(...).limite_inferior` quando a
    diferença importar.
    """
    alvo = cwe if isinstance(cwe, int) else _numero_cwe(cwe)
    if alvo is None:
        return False
    return alvo in cwes_alcancaveis(linguagem, destino, config, entre_arquivos)


def _afirma_vulnerabilidade(regra):
    """A regra declara detectar vulnerabilidade, ou apenas sinalizar auditoria?

    Ausência e vocabulário desconhecido contam como auditoria: `subcategory` é
    metadado do registry, não contrato, e tratá-lo como ausente-é-vulnerável
    inflaria o grau justamente onde não há informação.
    """
    return any(_SUBCATEGORIA_VULN in str(s).lower()
               for s in regra.subcategorias)


def graus_alcancabilidade(linguagem, destino=None, config=SEMGREP_CONFIG,
                          entre_arquivos=False):
    """`{numero_da_cwe: grau}` para as CWEs alcançáveis naquela linguagem.

    Devolve o mapa inteiro, e não uma consulta por vez, porque o relatório da
    colheita precisa do grau de todas as CWEs de uma vez e refazer a leitura por
    CWE percorreria o ruleset uma vez por consulta.

    `entre_arquivos` muda o eixo de TAINT, e só ele. A justificativa escrita do
    grau intermediário é *"o motor não rastreia fluxo entre arquivos"* — é uma
    afirmação sobre o MOTOR, não sobre a CWE. Sob um motor que rastreia,
    mantê-la faria a escala descrever uma limitação extinta, e a colheita
    continuaria evitando CWE-918, que é precisamente o que a troca de motor
    pretende destravar.

    A validação empírica da escala (alta 11,30 %, media 1,67 %, baixa 0,30 %)
    foi medida sob o CE e NÃO transfere: sob o modo entre-arquivos a escala
    precisa ser revalidada do zero.
    """
    alvo = str(linguagem).lower()
    melhor = {}
    for regra in carregar_regras(destino, config).values():
        if alvo not in {str(x).lower() for x in regra.linguagens}:
            continue
        if _afirma_vulnerabilidade(regra):
            # Sob modo entre-arquivos o rebaixamento por taint deixa de fazer
            # sentido: o motivo dele era o alcance, e o alcance mudou.
            rebaixa = regra.taint and not entre_arquivos
            grau = GRAU_MEDIA if rebaixa else GRAU_ALTA
        else:
            # O eixo de AUDITORIA não é afetado pelo motor: nenhuma análise de
            # fluxo transforma regra de auditoria em afirmação de
            # vulnerabilidade.
            grau = GRAU_BAIXA
        for c in regra.cwes:
            n = _numero_cwe(c)
            if n is None:
                continue
            # O grau da CWE é o da MELHOR regra que a cobre: basta uma regra
            # capaz para que o motor tenha chance de alcançá-la.
            atual = melhor.get(n)
            if atual is None or ORDEM_GRAUS.index(grau) > ORDEM_GRAUS.index(atual):
                melhor[n] = grau
    return melhor


def grau_alcancabilidade(cwe, linguagem, destino=None, config=SEMGREP_CONFIG,
                         entre_arquivos=False):
    """Grau de uma CWE, ou `None` quando ela não é alcançável de forma alguma.

    `None` e `GRAU_BAIXA` são estados diferentes e não devem ser confundidos:
    o primeiro é "nenhuma regra declara esta CWE", o segundo é "há regra, mas
    nenhuma afirma detectar vulnerabilidade". A colheita recusa o primeiro e
    aceita o segundo.
    """
    n = _numero_cwe(cwe)
    if n is None:
        return None
    return graus_alcancabilidade(linguagem, destino, config,
                                 entre_arquivos).get(n)


def metadados_snapshot(destino=None, config=SEMGREP_CONFIG):
    """Origem, caminho e data do snapshot do ruleset em uso.

    A data é a de escrita do arquivo — um `git checkout` a reescreveria. Ela diz
    "não mais velho que isto", que é o suficiente para o desvio ficar visível.
    """
    destino = os.path.abspath(destino or caminho_cache(config))
    regras = carregar_regras(destino, config)
    obtido_em = datetime.fromtimestamp(
        os.path.getmtime(destino)).astimezone().isoformat(timespec="seconds")
    return Snapshot(origem=url_registry(config), caminho=destino,
                    obtido_em=obtido_em, regras=len(regras))
