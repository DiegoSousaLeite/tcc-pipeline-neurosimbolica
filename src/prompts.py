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

# Variantes DIRETAS, para o braço de triagem.
#
# Os dois templates originais abrem com "abaixo está um alerta emitido por uma
# ferramenta de análise estática... decida se o alerta é VP ou FP". No braço de
# triagem isso é uma pressuposição FALSA para o candidato injetado: não houve
# alerta nenhum. Pedir para validar um alerta inexistente e receber "falso
# positivo" é uma resposta coerente com a pergunta feita — e isso contamina a
# medição de recall sem que o grupo de controle consiga acusar, porque o
# enquadramento é uniforme nas duas procedências.
#
# As variantes diretas perguntam pelo CÓDIGO em vez de pelo alerta. Elas NÃO
# acrescentam informação: o `especialista` já recebia a CWE do gabarito nas três
# camadas, e o `baseline_direto` continua sem ver CWE alguma, como o controle
# exige. Muda a forma da pergunta, não a evidência.
#
# São ARQUIVOS NOVOS, e não edição dos originais, porque `Versao_Prompt` é o que
# torna uma alteração de prompt detectável nos resultados já gravados: mexer nos
# originais tornaria as Rodadas 1-4 irreproduzíveis em silêncio.
BASELINE_DIRETO = "baseline_direto"
ESPECIALISTA_DIRETO = "especialista_direto"

# Variantes v2 dos dois especialistas: o original mais UM parágrafo pedindo que
# o modelo não presuma mitigação ausente do trecho. Existem porque o especialista
# respondeu VP zero vezes na rodada 20260908T094808Z-9a00cb2 — as fichas
# ensinam, sobretudo, quando o alerta NÃO é fraqueza. O parágrafo é idêntico nas
# duas, para que o efeito medido nos dois modos seja o da mesma instrução; e são
# arquivos novos pelo mesmo motivo das variantes diretas: `Versao_Prompt` dos
# originais precisa continuar batendo com as rodadas já gravadas.
ESPECIALISTA_V2 = "especialista_v2"
ESPECIALISTA_DIRETO_V2 = "especialista_direto_v2"

TIPOS = (BASELINE, ESPECIALISTA, BASELINE_DIRETO, ESPECIALISTA_DIRETO,
         ESPECIALISTA_V2, ESPECIALISTA_DIRETO_V2)

# Tipos que NÃO recebem a ficha do catálogo: são as condições de controle, e ver
# qualquer camada da metodologia — inclusive o nome da CWE — as descaracteriza.
TIPOS_SEM_FICHA = (BASELINE, BASELINE_DIRETO)

# Tipos que perguntam pelo código em vez de pelo alerta.
TIPOS_DIRETOS = (BASELINE_DIRETO, ESPECIALISTA_DIRETO, ESPECIALISTA_DIRETO_V2)

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

    Os tipos de `TIPOS_SEM_FICHA` recebem apenas o contexto — são as condições
    de controle e não podem ver nenhuma camada da metodologia, nem mesmo o nome
    da CWE. Os demais recebem as três camadas, todas vindas da mesma ficha do
    catálogo.

    As variantes `_direto` diferem das originais só no ENQUADRAMENTO da pergunta
    (pelo código, não pelo alerta); os placeholders são os mesmos.

    `description` (a descrição da CWE que vem do dataset) NÃO entra em nenhum
    dos dois: no baseline contaminaria o controle, e no especialista competiria
    com a definição do catálogo, que é a fonte única declarada.
    """
    template = carregar_template(tipo)

    if tipo in TIPOS_SEM_FICHA:
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
