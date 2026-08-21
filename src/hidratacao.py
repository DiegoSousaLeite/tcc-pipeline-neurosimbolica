import re


def extrai_funcao(linhas, alvo_idx):
    """Extrai a função Go que contém a linha alvo (1-based).
    Sobe até um 'func ...' e faz balanceamento de chaves. Fallback: janela ±25.
    """
    if not linhas:
        return None
    i = min(max(alvo_idx - 1, 0), len(linhas) - 1)
    inicio = None
    for j in range(i, -1, -1):
        if linhas[j].lstrip().startswith("func "):
            inicio = j
            break
    if inicio is None:
        ini = max(0, i - 25)
        fim = min(len(linhas), i + 25)
        return {"metodo": "janela", "linha_inicio": ini + 1, "linha_fim": fim,
                "codigo": "\n".join(linhas[ini:fim])}
    saldo, fim = 0, None
    viu_abre = False
    for j in range(inicio, len(linhas)):
        saldo += linhas[j].count("{") - linhas[j].count("}")
        if "{" in linhas[j]:
            viu_abre = True
        if viu_abre and saldo <= 0:
            fim = j
            break
    if fim is None:
        fim = min(len(linhas), inicio + 60)
    return {"metodo": "funcao", "linha_inicio": inicio + 1, "linha_fim": fim + 1,
            "codigo": "\n".join(linhas[inicio:fim + 1])}


def nome_funcao(codigo):
    """Extrai o nome da função Go da assinatura (1a linha 'func ...')."""
    m = re.search(r"^func\s+(?:\([^)]*\)\s+)?(\w+)", codigo.lstrip(), re.M)
    return m.group(1) if m else None
