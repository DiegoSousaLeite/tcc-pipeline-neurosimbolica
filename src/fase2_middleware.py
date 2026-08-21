import os

from .hidratacao import extrai_funcao


def extrair_e_hidratar_contexto(alerta: dict, caminho_arquivo: str) -> str:
    """Lê o arquivo no commit atual e extrai o contexto ao redor do alerta Semgrep.

    alerta:         alerta normalizado do Semgrep (start.line / check_id / extra.message).
    caminho_arquivo: caminho absoluto do arquivo, já resolvido por src/fonte.py.
    Retorna string vazia se o alerta for None ou o arquivo não for legível.
    """
    if alerta is None:
        return ""

    linha = alerta.get("start", {}).get("line", 1)
    check_id = alerta.get("check_id", "regra desconhecida")
    message = alerta.get("extra", {}).get("message", "")

    try:
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            linhas = f.read().splitlines()
    except (FileNotFoundError, UnicodeDecodeError):
        return ""

    resultado = extrai_funcao(linhas, linha)
    if not resultado:
        return ""

    contexto = (
        f"Alerta Semgrep: {check_id}\n"
        f"Mensagem: {message}\n"
        f"Localização: linha {linha}\n"
        f"\n--- CÓDIGO FONTE RELEVANTE ---\n"
        f"\n[Arquivo: {os.path.basename(caminho_arquivo)} | "
        f"Linhas {resultado['linha_inicio']} a {resultado['linha_fim']}]\n"
        f"{resultado['codigo']}"
    )
    return contexto
