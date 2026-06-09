import subprocess
import os
from .config import REPOS_DIR

def executar_codeql(repo_url: str, commit_hash: str, repo_name: str) -> str:
    """Clona o repositório, volta no tempo e gera o arquivo SARIF via CodeQL."""
    caminho_repo = os.path.join(REPOS_DIR, repo_name)
    
    # 1. Isolamento do Código (Clone e Checkout)
    if not os.path.exists(caminho_repo):
        print(f"    -> Clonando {repo_name}...")
        subprocess.run(["git", "clone", repo_url, caminho_repo])
    
    subprocess.run(["git", "checkout", commit_hash, "--force"], cwd=caminho_repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 2. Execução do CodeQL
    db_path = f"db_codeql"
    sarif_output = f"resultados_{repo_name}.sarif"
    caminho_sarif = os.path.join(caminho_repo, sarif_output)
    
    # Limpeza de execuções anteriores para evitar conflitos
    if os.path.exists(os.path.join(caminho_repo, db_path)):
        subprocess.run(["rm", "-rf", db_path], cwd=caminho_repo)

    print("    -> Construindo base de dados relacional (CodeQL)...")
    cmd_create = ["codeql", "database", "create", db_path, "--language=go"]
    res_create = subprocess.run(cmd_create, cwd=caminho_repo, capture_output=True)
    
    if res_create.returncode != 0:
        raise RuntimeError("Falha na criação do banco de dados do CodeQL.")

    print("    -> Executando queries de segurança e gerando trilhas...")
    cmd_analyze = [
        "codeql", "database", "analyze", db_path, 
        "go-security-extended.qls", 
        "--format=sarif-latest", 
        f"--output={sarif_output}"
    ]
    subprocess.run(cmd_analyze, cwd=caminho_repo, capture_output=True)
    
    if not os.path.exists(caminho_sarif):
        raise FileNotFoundError("O arquivo SARIF não foi gerado pelo CodeQL.")
        
    return caminho_sarif