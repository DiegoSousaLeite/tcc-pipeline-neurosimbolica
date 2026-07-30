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
simbólico depende da versão do ruleset do Semgrep, que muda. Misturar os dois
violaria a invariante "o cache de fontes nunca invalida"; por isso a versão do
ruleset entra no payload e uma divergência invalida a ENTRADA DAQUI, sem tocar
em um único byte de `cache/`.

Chave: `(repo, commit, arquivo, cwe)` — a mesma granularidade de um caso.
"""
import hashlib
import json
import logging
import os

from .config import CACHE_SIMBOLICO_DIR
from .fase1_semgrep import SEMGREP_CONFIG

log = logging.getLogger(__name__)

# Versão do formato do payload. Subir isto invalida todas as entradas — use
# quando a estrutura gravada mudar, não quando o ruleset mudar.
VERSAO_FORMATO = 1


class CacheSimbolico:
    """Leitura e gravação do resultado simbólico, indexado por caso.

    `versao_ruleset` identifica o ruleset do Semgrep vigente. Uma entrada
    gravada sob outro ruleset é ignorada (não apagada): ela continua sendo
    evidência do que aquele ruleset produziu.
    """

    def __init__(self, diretorio: str = CACHE_SIMBOLICO_DIR,
                 versao_ruleset: str = SEMGREP_CONFIG, ativo: bool = True):
        self.diretorio = diretorio
        self.versao_ruleset = versao_ruleset
        self.ativo = ativo
        self.leituras = 0
        self.gravacoes = 0

    # -- caminho ------------------------------------------------------------

    def caminho(self, repo_name: str, commit: str, arquivo: str, cwe: str) -> str:
        """`<dir>/<owner>__<repo>/<commit12>/<hash-do-caminho>__<cwe>.json`.

        O caminho do arquivo vira hash porque um caminho Go aninhado somado ao
        prefixo do repositório estoura o limite de ~260 chars do Windows.
        """
        slug = repo_name.replace("/", "__")
        dig = hashlib.sha1(arquivo.encode("utf-8")).hexdigest()[:12]
        return os.path.join(self.diretorio, slug, commit[:12],
                            f"{dig}__{cwe}.json")

    # -- leitura ------------------------------------------------------------

    def ler(self, repo_name: str, commit: str, arquivo: str, cwe: str):
        """Devolve o payload gravado, ou None se ausente/inválido.

        Retorna None quando a versão do ruleset ou do formato diverge: o caso
        precisa ser recomputado, porque o alerta pode ter mudado.
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
        if payload.get("versao_ruleset") != self.versao_ruleset:
            log.debug("ruleset divergente (%s != %s), recomputando: %s",
                      payload.get("versao_ruleset"), self.versao_ruleset, destino)
            return None

        self.leituras += 1
        return payload

    # -- gravação -----------------------------------------------------------

    def gravar(self, repo_name: str, commit: str, arquivo: str, cwe: str,
               status_semgrep: str, alerta=None, contexto_hidratado: str = ""):
        """Grava o resultado das Fases 1 e 2.

        `NAO_DETECTADO` também é gravado, de propósito: é a maioria dos casos e
        é justamente onde o Semgrep gasta tempo sem produzir chamada de LLM.
        """
        if not self.ativo:
            return
        destino = self.caminho(repo_name, commit, arquivo, cwe)
        payload = {
            "versao_formato": VERSAO_FORMATO,
            "versao_ruleset": self.versao_ruleset,
            "repo_name": repo_name,
            "commit": commit,
            "arquivo": arquivo,
            "cwe": cwe,
            "status_semgrep": status_semgrep,
            "alerta": alerta,
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
