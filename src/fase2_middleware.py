import json
import os

def extrair_e_hidratar_contexto(caminho_sarif: str, arquivo_alvo_sastbench: str, caminho_repo: str) -> str:
    """Extrai a trilha do CodeQL e anexa o código-fonte adjacente."""
    with open(caminho_sarif, 'r', encoding='utf-8') as f:
        sarif_data = json.load(f)
    
    contexto = ""
    linhas_criticas = set()
    
    # Busca a trilha de dados (Code Flow)
    for run in sarif_data.get('runs', []):
        for result in run.get('results', []):
            locations = result.get('locations', [])
            if not locations: continue
            
            caminho_codeql = locations[0].get('physicalLocation', {}).get('artifactLocation', {}).get('uri', '')
            nome_arquivo_codeql = caminho_codeql.split('/')[-1]
            nome_arquivo_alvo = arquivo_alvo_sastbench.split('/')[-1]
            
            if nome_arquivo_alvo == nome_arquivo_codeql:
                contexto += f"Alerta CodeQL: {result.get('ruleId')} - {result.get('message', {}).get('text')}\n"
                code_flows = result.get('codeFlows', [])
                
                if code_flows:
                    contexto += "Fluxo de Dados (Taint Analysis):\n"
                    for threadFlow in code_flows[0].get('threadFlows', []):
                        for loc in threadFlow.get('locations', []):
                            ph_loc = loc.get('location', {}).get('physicalLocation', {})
                            uri = ph_loc.get('artifactLocation', {}).get('uri', '')
                            linha = ph_loc.get('region', {}).get('startLine')
                            if uri and linha:
                                contexto += f" -> [Passo] {uri} na Linha {linha}\n"
                                linhas_criticas.add((uri, linha))
                break 

    if not contexto:
        return "" # O CodeQL não encontrou o bug especificado pelo SastBench

    # Hidratação: Lê o código-fonte real
    contexto += "\n--- CÓDIGO FONTE RELEVANTE ---\n"
    for uri, linha in list(linhas_criticas)[:3]: 
        caminho_arquivo_go = os.path.join(caminho_repo, uri)
        try:
            with open(caminho_arquivo_go, 'r', encoding='utf-8') as f_go:
                todas_linhas = f_go.readlines()
                inicio = max(0, linha - 10)
                fim = min(len(todas_linhas), linha + 15)
                
                contexto += f"\n[Arquivo: {uri} | Linhas {inicio+1} a {fim}]\n"
                contexto += "".join(todas_linhas[inicio:fim])
        except FileNotFoundError:
            continue

    return contexto