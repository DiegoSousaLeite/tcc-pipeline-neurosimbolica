"""
fase2_middleware.py — Fase 2: monta o candidato e hidrata o contexto do LLM.

Um CANDIDATO é o que a Fase 3 vai perguntar ao modelo: um ponto de um arquivo,
sob uma CWE. Ele tem duas procedências possíveis, e a distinção é o eixo desta
parte do experimento:

- `alerta`   — veio de um alerta do Semgrep emparelhado ao caso. É o único
               caminho do modo de montagem `filtro`, em que o LLM é filtro puro
               do motor simbólico.
- `gabarito` — veio da localização declarada no gabarito, sem exigir que o motor
               tenha emitido alerta. Só existe no modo `triagem`, e só para caso
               de gabarito vulnerável.

Os dois caminhos convergem para a MESMA estrutura (`Candidato`) antes da
hidratação. Se o candidato injetado chegasse com forma distinguível — um campo a
mais, uma mensagem de formato diferente, ausência de identificador de regra —, o
modelo poderia condicionar o veredito na forma em vez do código, e o experimento
mediria a pista, não o julgamento.

Por que o modo `triagem` não imprime os campos do alerta
--------------------------------------------------------
Nenhum preenchimento neutro torna os dois candidatos indistinguíveis no texto:

- `check_id`: o candidato de gabarito não tem regra. Um `N/A` ao lado de um
  `go.lang.security.audit.*` real É a pista; sintetizar um identificador
  plausível seria fabricar evidência.
- `Mensagem`: idem, e o texto do Semgrep costuma nomear a fraqueza.
- `Localização: linha N`: a mais sutil. No candidato de gabarito, `N` é sempre o
  início da função recortada; no de alerta, quase sempre cai no meio dela.
  Bastaria comparar `N` com o cabeçalho `[Arquivo: ... | Linhas A a B]` para
  separar os grupos.

Então no modo `triagem` o contexto é normalizado ao CÓDIGO: as duas procedências
recebem o mesmo recorte, produzido pelo mesmo algoritmo, sob o mesmo cabeçalho de
arquivo e faixa de linhas. O modo `filtro` não muda um byte — é o que mantém as
Rodadas 1-3 reproduzíveis. Ver D7 em
`openspec/changes/braco-triagem-classe-positiva/design.md`.
"""
import os
from dataclasses import asdict, dataclass

from .hidratacao import extrai_funcao

# Eixo de montagem do candidato, ortogonal a modelo e tipo de prompt.
MODO_FILTRO = "filtro"
MODO_TRIAGEM = "triagem"
MODOS_MONTAGEM = (MODO_FILTRO, MODO_TRIAGEM)

# Procedências. `N/A` é o valor das linhas que não produziram candidato algum
# (não-detecção no modo filtro, falha de esteira) e o das linhas dos CSVs
# anteriores a esta coluna.
ALERTA = "alerta"
GABARITO = "gabarito"
PROCEDENCIA_NA = "N/A"

# Preenchimento dos campos que o candidato de gabarito não tem. Preenchido, e
# não omitido: é o conjunto de chaves que precisa ser idêntico entre os dois
# caminhos, porque é ele que a normalização garante.
VALOR_NEUTRO = "N/A"


class ProcedenciaVazada(Exception):
    """Candidato de gabarito prestes a ser renderizado com cabeçalho de alerta.

    É erro, e não aviso, porque o dano é silencioso e irrecuperável: a rodada
    sairia com a procedência impressa no prompt, o LLM poderia tê-la usado, e
    nada no CSV denunciaria. Só acontece por erro de programação — o modo é
    uniforme na rodada e decidido num lugar só.
    """


@dataclass(frozen=True)
class Candidato:
    """O que a Fase 3 vai submeter ao LLM, já normalizado.

    Estrutura única para as duas procedências: `campos()` devolve exatamente o
    mesmo conjunto de chaves venha o candidato de onde vier.
    """

    procedencia: str        # alerta | gabarito
    linha: int              # linha-alvo do recorte, sempre real
    check_id: str           # identificador da regra, ou VALOR_NEUTRO
    mensagem: str           # mensagem do motor, ou VALOR_NEUTRO

    def campos(self) -> dict:
        return asdict(self)


def candidato_de_alerta(alerta) -> "Candidato | None":
    """Candidato a partir do alerta normalizado do Semgrep."""
    if alerta is None:
        return None
    return Candidato(
        procedencia=ALERTA,
        linha=alerta.get("start", {}).get("line", 1),
        check_id=alerta.get("check_id", "regra desconhecida"),
        mensagem=alerta.get("extra", {}).get("message", ""),
    )


def candidato_de_gabarito(linha) -> "Candidato | None":
    """Candidato a partir da localização declarada no gabarito.

    `linha` é o início da função vulnerável — `vulneravel.linha_inicio` do par
    TP, ou `line_start` da location na trilha `TP_dataset`. Com ela,
    `extrai_funcao` sobe até o `func ` daquela mesma linha e devolve exatamente a
    função que a CVE corrigiu; sem ela, cairia na primeira função do arquivo.

    Devolve None quando a linha falta: não há candidato, e inventar uma
    localização seria fabricar evidência (D6).
    """
    if not linha:
        return None
    return Candidato(
        procedencia=GABARITO,
        linha=int(linha),
        check_id=VALOR_NEUTRO,
        mensagem=VALOR_NEUTRO,
    )


def extrair_e_hidratar_contexto(candidato, caminho_arquivo: str,
                                modo: str = MODO_FILTRO) -> str:
    """Lê o arquivo no commit atual e recorta a função ao redor do candidato.

    candidato:       `Candidato`, ou o alerta cru do Semgrep (compatibilidade
                     com os chamadores anteriores a esta estrutura).
    caminho_arquivo: caminho absoluto do arquivo, já resolvido por src/fonte.py.
    modo:            `filtro` imprime o cabeçalho do alerta; `triagem` normaliza
                     ao código, para que a procedência não chegue ao prompt.

    Retorna string vazia se não houver candidato ou o arquivo não for legível.
    """
    if candidato is None:
        return ""
    if isinstance(candidato, dict):
        candidato = candidato_de_alerta(candidato)

    if modo == MODO_FILTRO and candidato.procedencia == GABARITO:
        raise ProcedenciaVazada(
            "candidato de gabarito não pode ser renderizado no modo filtro: o "
            "cabeçalho do alerta revelaria a procedência no prompt")

    try:
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            linhas = f.read().splitlines()
    except (FileNotFoundError, UnicodeDecodeError):
        return ""

    resultado = extrai_funcao(linhas, candidato.linha)
    if not resultado:
        return ""

    if modo == MODO_FILTRO:
        cabecalho = (
            f"Alerta Semgrep: {candidato.check_id}\n"
            f"Mensagem: {candidato.mensagem}\n"
            f"Localização: linha {candidato.linha}\n"
        )
    else:
        cabecalho = ""

    return (
        f"{cabecalho}"
        f"\n--- CÓDIGO FONTE RELEVANTE ---\n"
        f"\n[Arquivo: {os.path.basename(caminho_arquivo)} | "
        f"Linhas {resultado['linha_inicio']} a {resultado['linha_fim']}]\n"
        f"{resultado['codigo']}"
    )
