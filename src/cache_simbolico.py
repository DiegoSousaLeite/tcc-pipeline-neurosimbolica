"""
cache_simbolico.py — persiste o resultado das Fases 1 e 2 por caso.

Por que existe
--------------
A matriz 2x2 avalia a MESMA população sob quatro braços. Sem este cache, cada
braço reexecutaria o Semgrep e a hidratação nos 948 casos — e o Semgrep é o
custo de parede dominante, porque roda inclusive nos `NAO_DETECTADO`, que são a
maioria. Cacheado, os braços 2 a 4 fazem apenas a chamada de LLM.

O ganho secundário é o que de fato importa para a validade do experimento: o
`contexto_hidratado` é gravado como string exata e é ELA que alimenta os quatro
braços. Isso garante contexto byte-a-byte idêntico entre os braços, requisito de
validade interna da comparação pareada — sem isso, uma diferença de veredito
poderia vir de uma diferença de entrada, não do braço.

Por que é separado de `cache/`
------------------------------
`cache/` guarda o CONTEÚDO de um arquivo num commit: a chave é imutável por
construção (um SHA não muda), então aquele cache nunca invalida. O resultado
simbólico depende do conjunto de rulesets do Semgrep, que muda. Misturar os dois
violaria a invariante "o cache de fontes nunca invalida"; por isso a identidade
do conjunto entra no payload e uma divergência invalida a ENTRADA DAQUI, sem
tocar em um único byte de `cache/`.

Chave: `(repo, commit, arquivo, cwe)` — a mesma granularidade de um caso.
"""
import hashlib
import json
import logging
import os

from .config import CACHE_SIMBOLICO_DIR
from .fase1_semgrep import (
    VERSAO_PAREAMENTO,
    identidade_conjunto,
    motor_corrente,
    motor_de_payload,
)

log = logging.getLogger(__name__)

# Versão do formato do payload. Subir isto invalida todas as entradas — use
# quando a estrutura gravada mudar, não quando o ruleset mudar.
#   1 — sem motivo de não-detecção nem versão de pareamento
#   2 — com `versao_pareamento`, `motivo` e `regras_nao_casadas`
VERSAO_FORMATO = 2


class CacheSimbolico:
    """Leitura e gravação do resultado simbólico, indexado por caso.

    `versao_ruleset` identifica o CONJUNTO de rulesets vigente e
    `versao_pareamento` a regra que decide qual alerta pertence ao caso. Uma
    entrada gravada sob qualquer uma das duas divergente é ignorada (não
    apagada): ela continua sendo evidência do que aquele conjunto e aquela regra
    produziram.

    O eixo é o conjunto, e não um ruleset isolado, porque acrescentar um segundo
    ruleset muda o que o motor emite tanto quanto trocar o primeiro. Se a
    identidade registrada descrevesse apenas um deles, uma rodada composta seria
    servida do disco com os alertas da rodada unitária — e o experimento
    reportaria como resultado do conjunto novo aquilo que o conjunto antigo
    produziu. A invalidação alcança os `NAO_DETECTADO` com mais razão ainda: é
    neles que o ruleset acrescentado pode produzir resultado diferente, e
    aceitá-los do disco esconderia o único ganho que justifica acrescentá-lo.

    A identidade do conjunto unitário é o nome do próprio ruleset, então as
    entradas gravadas quando a configuração era um ruleset só continuam válidas
    enquanto ele continuar sendo a configuração — e a ordem dos rulesets não
    invalida nada, porque não altera a união dos achados.

    Os dois eixos não são redundantes. O ruleset muda quando o Semgrep passa a
    enxergar coisas diferentes; a regra de pareamento muda quando a pipeline
    passa a aceitar como do caso um conjunto diferente de alertas. Uma alteração
    da regra de pareamento não muda a estrutura do payload, e sem eixo próprio
    alguém teria de lembrar de subir a versão de FORMATO por um motivo que não é
    de formato.
    """

    def __init__(self, diretorio: str = CACHE_SIMBOLICO_DIR,
                 versao_ruleset: str = None, ativo: bool = True,
                 versao_pareamento: int = VERSAO_PAREAMENTO,
                 motor=None):
        self.diretorio = diretorio
        # Derivada na construção, e não no import: a configuração vazia é erro,
        # e um erro no import derrubaria até quem só quisesse ler o módulo.
        self.versao_ruleset = (identidade_conjunto()
                               if versao_ruleset is None else versao_ruleset)
        self.versao_pareamento = versao_pareamento
        self.motor = motor if motor is not None else motor_corrente()
        self.ativo = ativo
        self.leituras = 0
        self.gravacoes = 0

    # -- caminho ------------------------------------------------------------

    def caminho(self, repo_name: str, commit: str, arquivo: str, cwe: str) -> str:
        """`<dir>/<owner>__<repo>/<commit12>/<hash-do-caminho>__<cwe>[__pro].json`.

        O caminho do arquivo vira hash porque um caminho Go aninhado somado ao
        prefixo do repositório estoura o limite de ~260 chars do Windows.

        O sufixo do motor entra no NOME, e não num diretório próprio por motor
        (recusado na D2, que duplicaria a lógica de leitura e tornaria a
        comparação entre motores um problema de caminho). Ele existe porque a
        D2 também exige que as entradas dos dois motores COEXISTAM para o mesmo
        caso: num caminho único a segunda gravação sobrescreveria a primeira, e
        a comparação CE×Pro sobre os mesmos casos — que é o ganho declarado de
        manter as duas — exigiria reexecutar um dos dois.

        O motor CE sem modo entre-arquivos mantém o nome EXATO de antes desta
        mudança: as ~1.700 entradas já em disco continuam sendo encontradas,
        em vez de virarem lixo silencioso ao lado de um cache vazio.
        """
        slug = repo_name.replace("/", "__")
        dig = hashlib.sha1(arquivo.encode("utf-8")).hexdigest()[:12]
        sufixo = "__pro" if self.motor.entre_arquivos else ""
        return os.path.join(self.diretorio, slug, commit[:12],
                            f"{dig}__{cwe}{sufixo}.json")

    # -- leitura ------------------------------------------------------------

    def ler(self, repo_name: str, commit: str, arquivo: str, cwe: str):
        """Devolve o payload gravado, ou None se ausente/inválido.

        Retorna None quando a versão do formato, do ruleset ou da regra de
        pareamento diverge: o caso precisa ser recomputado, porque o alerta pode
        ter mudado.
        """
        if not self.ativo:
            return None
        destino = self.caminho(repo_name, commit, arquivo, cwe)
        if not os.path.exists(destino):
            return None
        try:
            with open(destino, encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            log.debug("cache simbólico ilegível, recomputando: %s", destino)
            return None

        if payload.get("versao_formato") != VERSAO_FORMATO:
            log.debug("formato divergente (%s), recomputando: %s",
                      payload.get("versao_formato"), destino)
            return None
        # Conjunto de rulesets divergente. `p/default` e `p/default+regras/go`
        # são conjuntos distintos e têm identidades distintas — entrada de um
        # não serve para o outro, inclusive quando um contém o outro.
        if payload.get("versao_ruleset") != self.versao_ruleset:
            log.debug("conjunto de rulesets divergente (%s != %s), recomputando: %s",
                      payload.get("versao_ruleset"), self.versao_ruleset, destino)
            return None
        # Ausente é o estado das entradas gravadas antes deste campo existir:
        # tratá-las como divergentes é o ponto, não um efeito colateral. A
        # invalidação alcança também os `NAO_DETECTADO`, cujo status continuaria
        # correto — endurecer o pareamento nunca transforma não-detecção em
        # detecção —, mas que não sabem informar qual motivo os produziu.
        if payload.get("versao_pareamento") != self.versao_pareamento:
            log.debug("regra de pareamento divergente (%s != %s), recomputando: %s",
                      payload.get("versao_pareamento"), self.versao_pareamento,
                      destino)
            return None
        # Terceiro eixo, independente dos outros dois: o mesmo ruleset, sob a
        # mesma regra de pareamento, produz conjuntos de alertas diferentes
        # conforme o motor rastreie fluxo só dentro do arquivo ou também entre
        # arquivos. Sem esta checagem, ligar o modo não invalidaria nada e a
        # rodada seria servida do disco com os alertas do motor anterior —
        # reportando como resultado do motor novo o que o antigo produziu, em
        # silêncio.
        #
        # Ausência é tratada como CE sem modo entre-arquivos (D3), o OPOSTO da
        # regra de pareamento logo acima: lá a ausência significava que o
        # conteúdo podia estar errado sob a regra nova; aqui significa só que o
        # campo não existia, e o conteúdo continua correto para o CE.
        gravado = motor_de_payload(payload)
        if (gravado.edicao != self.motor.edicao
                or gravado.entre_arquivos != self.motor.entre_arquivos):
            log.debug("motor divergente (%s/%s != %s/%s), recomputando: %s",
                      gravado.edicao, gravado.entre_arquivos,
                      self.motor.edicao, self.motor.entre_arquivos, destino)
            return None

        self.leituras += 1
        return payload

    # -- gravação -----------------------------------------------------------

    def gravar(self, repo_name: str, commit: str, arquivo: str, cwe: str,
               status_semgrep: str, alerta=None, contexto_hidratado: str = "",
               motivo: str = "N/A", regras_nao_casadas=()):
        """Grava o resultado das Fases 1 e 2.

        `NAO_DETECTADO` também é gravado, de propósito: é a maioria dos casos e
        é justamente onde o Semgrep gasta tempo sem produzir chamada de LLM.

        O motivo da não-detecção e as regras que dispararam sem casar entram no
        payload porque são produto da Fase 1 como qualquer outro: sem eles, uma
        rodada servida do cache perderia o diagnóstico de cobertura simbólica e
        só o recuperaria reexecutando o Semgrep sobre a população inteira —
        exatamente o custo que este cache existe para evitar.
        """
        if not self.ativo:
            return
        destino = self.caminho(repo_name, commit, arquivo, cwe)
        payload = {
            "versao_formato": VERSAO_FORMATO,
            "versao_ruleset": self.versao_ruleset,
            "versao_pareamento": self.versao_pareamento,
            # Produto da Fase 1 como qualquer outro, e não recuperável depois:
            # sem ele a entrada não sabe dizer se descreve o que o CE viu ou o
            # que o motor com análise entre arquivos viu.
            "motor": self.motor.como_dict(),
            "repo_name": repo_name,
            "commit": commit,
            "arquivo": arquivo,
            "cwe": cwe,
            "status_semgrep": status_semgrep,
            "alerta": alerta,
            "motivo": motivo,
            "regras_nao_casadas": list(regras_nao_casadas),
            "contexto_hidratado": contexto_hidratado,
        }
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        # ensure_ascii=False preserva o contexto hidratado legível em revisão;
        # a leitura é sempre por json.load, então não muda a semântica.
        with open(destino, "w", encoding="utf-8", newline="") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        self.gravacoes += 1

    def resumo(self) -> str:
        return f"cache simbólico: {self.leituras} reaproveitados, {self.gravacoes} gravados"
