"""regras_locais.py — o ruleset mantido neste repositório, e o que ele exige.

Por que existe
--------------
`regras/go/` é o único ruleset do projeto imune à ameaça de mudança do lado do
servidor. Qualquer ruleset do registry — o `p/default` inclusive — pode mudar sem
que nada no código perceba; este muda apenas por commit, e o manifesto permite
dizer, meses depois, exatamente quais regras produziram cada número.

O preço é que regra nossa levanta uma objeção que regra de terceiros não levanta:
ela **pode** ter sido escrita olhando a população em que vai ser medida. Por isso
cada regra declara sob qual protocolo foi escrita, e o carregamento recusa a que
não declara.

Três metadados são obrigatórios, e cada ausência tem uma consequência diferente:

- **`proveniencia`** — `definicao` ou `desenvolvimento`. Sem ela o relatório não
  sabe qual número pode emitir sobre qual partição, e o caminho de menor
  resistência seria reportar tudo junto.
- **`cwe`** — no formato que o casamento por identificador completo aceita. Sem
  ele a regra dispara, o alerta não emparelha com o caso, a Fase 1 registra
  `ALERTA_OUTRA_CWE` e o esforço se perde de um jeito particularmente difícil de
  diagnosticar, porque a regra *funcionou*.
- **`subcategory`** — sem ela a regra é tratada como auditoria pelo grau de
  alcançabilidade, e a CWE não sobe de grau ainda que a detecção melhore.

Falhar cedo aqui é deliberado, e é o OPOSTO do que `src/ruleset.py` faz com
ruleset de terceiros. Lá, metadado ausente é tratado como auditoria e a execução
segue: não temos controle sobre o que o registry publica, e derrubar a rodada por
isso seria recusar a ferramenta inteira. Aqui, ausência é defeito nosso, e
descobri-lo depois de a rodada varrer a população inteira custa horas.
"""
import os
from typing import NamedTuple

from .fase1_semgrep import _numero_cwe

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRETORIO_PADRAO = os.path.join(BASE_DIR, "regras", "go")

# Protocolos de escrita. São epistemicamente distintos e produzem números com
# força diferente (design.md, D1).
#
# `definicao`       — derivada da definição da CWE e do idioma de Go, sem que
#                     nenhum caso da população tenha sido inspecionado. Pode ser
#                     medida sobre a população inteira.
# `desenvolvimento` — derivada da inspeção da partição de desenvolvimento. Só
#                     pode ser medida sobre a partição de avaliação.
DEFINICAO = "definicao"
DESENVOLVIMENTO = "desenvolvimento"
PROVENIENCIAS = (DEFINICAO, DESENVOLVIMENTO)

# Chave do metadado. Em português porque é metadado NOSSO, e confundi-lo com
# algum campo homônimo do registry seria pior que a inconsistência de idioma.
CHAVE_PROVENIENCIA = "proveniencia"


class RegraLocalInvalidaError(Exception):
    """Uma regra local não declara o que o protocolo exige.

    É erro, e não aviso: a regra defeituosa dispara do mesmo jeito, e o defeito
    só apareceria na hora de emparelhar ou de medir — depois de a rodada ter
    varrido a população inteira.
    """


class RegraLocal(NamedTuple):
    """Uma regra de `regras/go/`, reduzida ao que o protocolo exige dela."""

    id: str
    arquivo: str
    cwes: tuple
    proveniencia: str
    subcategorias: tuple

    def como_dict(self) -> dict:
        """Forma serializável, para o manifesto da rodada."""
        return {
            "id": self.id,
            "arquivo": self.arquivo,
            "cwe": list(self.cwes),
            CHAVE_PROVENIENCIA: self.proveniencia,
            "subcategory": list(self.subcategorias),
        }


def _lista(valor):
    """`cwe` e `subcategory` vêm ora como lista, ora como string única."""
    if valor is None:
        return []
    return [valor] if isinstance(valor, str) else list(valor)


def _validar(regra, arquivo) -> RegraLocal:
    """Aplica as três exigências a uma regra, nomeando-a em cada falha."""
    rid = regra.get("id") or f"(sem id, em {os.path.basename(arquivo)})"
    metadata = regra.get("metadata") or {}

    proveniencia = metadata.get(CHAVE_PROVENIENCIA)
    if proveniencia is None:
        raise RegraLocalInvalidaError(
            f"regra local '{rid}' ({os.path.basename(arquivo)}) não declara "
            f"'{CHAVE_PROVENIENCIA}'. Sem o selo, o relatório não sabe se o "
            "número dela pode sair da população inteira ou só da partição de "
            f"avaliação. Valores aceitos: {', '.join(PROVENIENCIAS)}.")
    if proveniencia not in PROVENIENCIAS:
        raise RegraLocalInvalidaError(
            f"regra local '{rid}' ({os.path.basename(arquivo)}) declara "
            f"'{CHAVE_PROVENIENCIA}: {proveniencia}', fora do vocabulário. "
            f"Valores aceitos: {', '.join(PROVENIENCIAS)}. Vocabulário "
            "desconhecido não é tratado como um dos válidos: adivinhar qual "
            "seria o mais parecido escolheria por nós qual número é reportável.")

    cwes = _lista(metadata.get("cwe"))
    if not cwes:
        raise RegraLocalInvalidaError(
            f"regra local '{rid}' ({os.path.basename(arquivo)}) não declara "
            "'metadata.cwe'. Ela dispararia, e o alerta não emparelharia com "
            "caso nenhum — a Fase 1 registraria ALERTA_OUTRA_CWE e o esforço se "
            "perderia com a regra funcionando.")
    for tag in cwes:
        if _numero_cwe(tag) is None:
            raise RegraLocalInvalidaError(
                f"regra local '{rid}' ({os.path.basename(arquivo)}) declara "
                f"'metadata.cwe: {tag}', que a comparação por identificador "
                "completo não reconhece. O formato aceito começa com "
                "'CWE-<número>', como em 'CWE-22: Path Traversal'.")

    subcategorias = _lista(metadata.get("subcategory"))
    if not subcategorias:
        raise RegraLocalInvalidaError(
            f"regra local '{rid}' ({os.path.basename(arquivo)}) não declara "
            "'metadata.subcategory'. O padrão conservador de tratar ausência "
            "como auditoria vale para ruleset de terceiros, sobre o qual não "
            "temos controle — não para regra nossa, que a CWE deixaria de subir "
            "de grau em silêncio.")

    return RegraLocal(id=rid, arquivo=os.path.basename(arquivo),
                      cwes=tuple(cwes), proveniencia=proveniencia,
                      subcategorias=tuple(subcategorias))


def arquivos_de_regra(diretorio=None):
    """Os YAML de `regras/go/`, em ordem estável."""
    diretorio = diretorio or DIRETORIO_PADRAO
    if not os.path.isdir(diretorio):
        return []
    return [os.path.join(diretorio, n) for n in sorted(os.listdir(diretorio))
            if n.endswith((".yaml", ".yml"))]


def carregar(diretorio=None):
    """`id` -> `RegraLocal`, validando cada regra do diretório.

    Levanta `RegraLocalInvalidaError` na primeira regra que não cumpre o
    protocolo, nomeando-a. Não acumula defeitos: a primeira já prova que o
    ruleset não está pronto para medir, e uma lista longa convida a ignorar o
    fim dela.
    """
    import yaml

    regras = {}
    for arquivo in arquivos_de_regra(diretorio):
        with open(arquivo, encoding="utf-8") as f:
            documento = yaml.safe_load(f) or {}
        for regra in documento.get("rules") or []:
            local = _validar(regra, arquivo)
            regras[local.id] = local
    return regras


def proveniencias(diretorio=None) -> set:
    """Quais protocolos estão carregados — é o que decide se o agregado sai."""
    return {r.proveniencia for r in carregar(diretorio).values()}


def para_manifesto(diretorio=None, commit=None) -> dict:
    """Cada regra local usada, sua proveniência e o commit que as define.

    O commit não é enfeite: `regras/go/` muda apenas por commit, e é ele que
    permite dizer, meses depois, exatamente quais regras produziram cada número.
    """
    diretorio = diretorio or DIRETORIO_PADRAO
    regras = carregar(diretorio)
    return {
        "diretorio": os.path.relpath(diretorio, BASE_DIR).replace("\\", "/"),
        "commit": commit if commit is not None else _commit_atual(),
        "regras": [r.como_dict() for r in sorted(regras.values(),
                                                 key=lambda r: r.id)],
    }


def _commit_atual() -> str:
    import subprocess
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=15,
                           cwd=BASE_DIR)
        return r.stdout.strip() or "desconhecido"
    except (OSError, subprocess.SubprocessError):
        return "desconhecido"
