"""
prompts.py — renderização dos templates de prompt versionados.

Os prompts saem do código e vão para `prompts/*.md` porque eles são a variável
experimental do eixo horizontal da matriz 2x2. Um f-string embutido não tem
versão: qualquer ajuste no texto altera silenciosamente o experimento e nenhum
resultado já gravado sabe disso. Em arquivo, o hash do template vai para o CSV
(`Versao_Prompt`) e a alteração fica detectável.

Renderização por `str.format` com placeholders nomeados. Sem engine de
template: `format` basta e não adiciona dependência — a única consequência é
que chaves literais no texto precisam ser dobradas (`{{` e `}}`), o que os dois
templates já fazem no contrato de saída JSON.
"""
import hashlib
import os

from .catalogo import Ficha, catalogo_padrao
from .config import PROMPTS_DIR

BASELINE = "baseline"
ESPECIALISTA = "especialista"
TIPOS = (BASELINE, ESPECIALISTA)

# Trecho que define o contrato de saída. Tem que ser idêntico nos dois
# templates: a diferença entre os braços precisa estar no CONTEÚDO, não no
# formato exigido — senão parte da diferença medida é a dificuldade de acertar
# o formato, não a qualidade da triagem.
MARCADOR_CONTRATO = "RESPONDA ESTRITAMENTE EM JSON"


class PromptInvalido(Exception):
    """Template ausente, tipo desconhecido ou placeholder não fornecido."""


_cache: dict[str, str] = {}


def caminho_template(tipo: str) -> str:
    if tipo not in TIPOS:
        raise PromptInvalido(f"tipo de prompt desconhecido: {tipo!r} (use {TIPOS})")
    return os.path.join(PROMPTS_DIR, f"{tipo}.md")


def carregar_template(tipo: str) -> str:
    """Texto cru do template, lido uma vez por processo."""
    if tipo not in _cache:
        caminho = caminho_template(tipo)
        if not os.path.exists(caminho):
            raise PromptInvalido(f"template não encontrado: {caminho}")
        with open(caminho, encoding="utf-8") as f:
            _cache[tipo] = f.read()
    return _cache[tipo]


def versao_prompt(tipo: str) -> str:
    """Hash curto do template, gravado no CSV como `Versao_Prompt`.

    Inclui o nome do tipo para que a coluna seja legível sem consultar o
    repositório: `especialista:8f3a1c9d`.
    """
    digest = hashlib.sha256(carregar_template(tipo).encode("utf-8")).hexdigest()
    return f"{tipo}:{digest[:8]}"


def secao_contrato(tipo: str) -> str:
    """Trecho do template a partir do marcador do contrato de saída."""
    texto = carregar_template(tipo)
    pos = texto.find(MARCADOR_CONTRATO)
    if pos < 0:
        raise PromptInvalido(
            f"template {tipo} não declara o contrato de saída "
            f"({MARCADOR_CONTRATO!r})")
    return texto[pos:].strip()


def montar_prompt(tipo: str, contexto: str, cwe_id: str, cwe_name: str = "",
                  description: str = "", ficha: Ficha = None) -> str:
    """Renderiza o prompt do tipo pedido.

    `baseline` recebe apenas o contexto — é a condição de controle e não pode
    ver nenhuma camada da metodologia, nem mesmo o nome da CWE. `especialista`
    recebe as três camadas, todas vindas da mesma ficha do catálogo.

    `description` (a descrição da CWE que vem do dataset) NÃO entra em nenhum
    dos dois: no baseline contaminaria o controle, e no especialista competiria
    com a definição do catálogo, que é a fonte única declarada.
    """
    template = carregar_template(tipo)

    if tipo == BASELINE:
        return template.format(contexto=contexto)

    ficha = ficha or catalogo_padrao().ficha(cwe_id, cwe_name)
    cabecalho = f"{cwe_id} — {ficha.nome}" if ficha.nome else cwe_id
    return template.format(
        cwe_header=cabecalho,
        definicao=ficha.definicao,
        heuristica_go=ficha.heuristica_go,
        exemplo_vp_codigo=ficha.exemplo_vp["codigo"],
        exemplo_vp_porque=ficha.exemplo_vp["porque"],
        exemplo_fp_codigo=ficha.exemplo_fp["codigo"],
        exemplo_fp_porque=ficha.exemplo_fp["porque"],
        contexto=contexto,
    )
