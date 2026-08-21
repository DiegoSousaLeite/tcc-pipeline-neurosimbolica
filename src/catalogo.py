"""
catalogo.py — carregador do catálogo de triagem por CWE.

O catálogo (`data/catalogo_cwe.json`) é a fonte ÚNICA das duas camadas do
prompt especialista que dependem da CWE: a heurística semântica e o par
few-shot VP/FP. Duas fontes de verdade permitiriam que a heurística e os
exemplos discordassem, e o braço "especialista" deixaria de ser uma condição
experimental bem definida.

Protocolo anti-viés (D5 do design)
----------------------------------
As fichas são escritas à mão a partir da definição da CWE no MITRE e da
documentação da biblioteca padrão de Go, **sem consultar as amostras
avaliadas**. O arquivo é congelado antes da primeira rodada, e o SHA-256 dele
vai para cada linha do CSV (`Hash_Catalogo`) e para o manifesto da rodada. Uma
linha cujo hash difere do arquivo atual foi produzida por outra versão do
catálogo e não pode ser agregada na mesma tabela sem sinalização.
"""
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Optional

from .config import CATALOGO_CWE_PATH

CHAVE_FALLBACK = "__fallback__"

CAMPOS_OBRIGATORIOS = ("definicao", "heuristica_go", "exemplo_vp", "exemplo_fp")
CAMPOS_EXEMPLO = ("codigo", "porque")

# Valores da coluna `Ficha_CWE` do CSV, que permite estratificar os resultados
# entre CWEs com ficha própria e CWEs atendidas pelo fallback.
ORIGEM_ESPECIFICA = "especifica"
ORIGEM_FALLBACK = "fallback"


class CatalogoInvalido(Exception):
    """O arquivo de catálogo não satisfaz o esquema."""


@dataclass(frozen=True)
class Ficha:
    """Uma ficha resolvida, já sabendo se veio de entrada própria ou do fallback."""

    cwe: str
    nome: str
    definicao: str
    heuristica_go: str
    exemplo_vp: dict
    exemplo_fp: dict
    origem: str          # especifica | fallback

    @property
    def especifica(self) -> bool:
        return self.origem == ORIGEM_ESPECIFICA


def _validar(dados: dict, caminho: str):
    if not isinstance(dados, dict) or not dados:
        raise CatalogoInvalido(f"{caminho}: catálogo vazio ou não é objeto JSON")
    if CHAVE_FALLBACK not in dados:
        raise CatalogoInvalido(
            f"{caminho}: falta a ficha '{CHAVE_FALLBACK}'. Sem ela, uma CWE fora "
            f"do catálogo deixaria o prompt especialista com camadas vazias.")
    for chave, ficha in dados.items():
        if not isinstance(ficha, dict):
            raise CatalogoInvalido(f"{caminho}: ficha {chave} não é objeto")
        for campo in CAMPOS_OBRIGATORIOS:
            valor = ficha.get(campo)
            if not valor:
                raise CatalogoInvalido(f"{caminho}: ficha {chave} sem '{campo}'")
        for lado in ("exemplo_vp", "exemplo_fp"):
            for campo in CAMPOS_EXEMPLO:
                if not ficha[lado].get(campo):
                    raise CatalogoInvalido(
                        f"{caminho}: ficha {chave}, {lado} sem '{campo}'")


class Catalogo:
    """Catálogo carregado, com resolução para fallback e hash do arquivo."""

    def __init__(self, dados: dict, sha256: str, caminho: str):
        self.dados = dados
        self.sha256 = sha256
        self.caminho = caminho

    @classmethod
    def carregar(cls, caminho: str = CATALOGO_CWE_PATH) -> "Catalogo":
        """Lê e valida o catálogo, calculando o SHA-256 dos BYTES do arquivo.

        O hash é dos bytes em disco, não de uma serialização normalizada: é o
        arquivo commitado que está sendo congelado, e é ele que a banca pode
        conferir com `sha256sum`.
        """
        if not os.path.exists(caminho):
            raise CatalogoInvalido(f"catálogo não encontrado: {caminho}")
        with open(caminho, "rb") as f:
            bruto = f.read()
        sha256 = hashlib.sha256(bruto).hexdigest()
        try:
            dados = json.loads(bruto.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise CatalogoInvalido(f"{caminho}: JSON inválido ({e})") from e
        _validar(dados, caminho)
        return cls(dados, sha256, caminho)

    # -- consulta ----------------------------------------------------------

    @property
    def cwes_especificas(self) -> list[str]:
        return sorted(c for c in self.dados if c != CHAVE_FALLBACK)

    def tem_ficha(self, cwe: str) -> bool:
        return cwe in self.dados and cwe != CHAVE_FALLBACK

    def ficha(self, cwe: str, cwe_name: str = "") -> Ficha:
        """Ficha da CWE, ou a genérica de fallback.

        Nunca devolve None: uma CWE sem ficha própria cai no fallback e o caso
        roda normalmente, apenas marcado como `fallback` no CSV.
        """
        especifica = self.tem_ficha(cwe)
        bruto = self.dados[cwe] if especifica else self.dados[CHAVE_FALLBACK]
        return Ficha(
            cwe=cwe,
            # O nome do dataset ganha do nome do catálogo quando existe: é o
            # rótulo que a amostra de fato carrega.
            nome=cwe_name or bruto.get("nome", ""),
            definicao=bruto["definicao"],
            heuristica_go=bruto["heuristica_go"],
            exemplo_vp=bruto["exemplo_vp"],
            exemplo_fp=bruto["exemplo_fp"],
            origem=ORIGEM_ESPECIFICA if especifica else ORIGEM_FALLBACK,
        )


_catalogo: Optional[Catalogo] = None


def catalogo_padrao() -> Catalogo:
    """Instância única, carregada na primeira consulta."""
    global _catalogo
    if _catalogo is None:
        _catalogo = Catalogo.carregar()
    return _catalogo
