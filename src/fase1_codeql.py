import subprocess
import os
import sys
import time
from .config import REPOS_DIR


# --- Exceções categorizadas da esteira simbólica ---
# Permitem que o orquestrador (main.py) classifique a falha no CSV em vez de
# perder a amostra silenciosamente (requisito C).
class CloneError(Exception):
    """Falha ao clonar o repositório open-source."""


class CheckoutError(Exception):
    """Falha ao reverter o repositório para o commit histórico."""


class CodeQLBuildError(Exception):
    """Falha na criação da base de dados relacional do CodeQL (ex.: build quebrado)."""


class CodeQLTimeoutError(Exception):
    """O CodeQL excedeu o tempo máximo (criação do banco ou análise)."""


class SarifMissingError(Exception):
    """O CodeQL terminou mas não gerou o artefato SARIF esperado."""


def executar_codeql(repo_url: str, commit_hash: str, repo_name: str) -> str:
    """Clona o repositório, volta no tempo e gera o arquivo SARIF via CodeQL."""
    caminho_repo = os.path.join(REPOS_DIR, repo_name)

    # 1. Isolamento do Código
    if not os.path.exists(caminho_repo):
        print(f"    -> Clonando {repo_name}...")
        res_clone = subprocess.run(["git", "clone", repo_url, caminho_repo],
                                   capture_output=True)
        if res_clone.returncode != 0:
            raise CloneError(res_clone.stderr.decode("utf-8", errors="ignore").strip())

    res_checkout = subprocess.run(["git", "checkout", commit_hash, "--force"],
                                  cwd=caminho_repo, capture_output=True)
    if res_checkout.returncode != 0:
        raise CheckoutError(res_checkout.stderr.decode("utf-8", errors="ignore").strip())
    
    # 2. Execução do CodeQL
    db_path = "db_codeql"
    sarif_output = f"resultados_{repo_name}.sarif"
    caminho_sarif = os.path.join(caminho_repo, sarif_output)
    caminho_banco_completo = os.path.join(caminho_repo, db_path)
    
    # Limpeza Agressiva para Windows
    if os.path.exists(caminho_banco_completo):
        if sys.platform == "win32":
            subprocess.run(f'rmdir /s /q "{caminho_banco_completo}"', shell=True)
        else:
            subprocess.run(["rm", "-rf", caminho_banco_completo])
        time.sleep(2) 

    print("    -> Construindo base de dados relacional (CodeQL)...")
    
    # CORREÇÃO: Caminho absoluto para o Windows nunca mais dar "File Not Found"
    exec_codeql = r"C:\WS\WS-UnB\tcc-pipeline-neurosimbolica\codeql\codeql.cmd" if sys.platform == "win32" else "codeql"
    
    cmd_create = [exec_codeql, "database", "create", db_path, "--language=go", "--threads=0"]
    
    # TIMEOUT 1: 20 minutos máximos para criar o banco
    try:
        res_create = subprocess.run(cmd_create, cwd=caminho_repo, capture_output=True, timeout=1200)
        if res_create.returncode != 0:
            raise CodeQLBuildError(res_create.stderr.decode("utf-8", errors="ignore").strip())
    except subprocess.TimeoutExpired:
        raise CodeQLTimeoutError("O CodeQL excedeu 20 minutos ao criar o banco de dados.")

    print("    -> Executando queries de segurança e gerando trilhas...")
    cmd_analyze = [
        exec_codeql, "database", "analyze", db_path, 
        "go-security-extended.qls", 
        "--format=sarif-latest", 
        f"--output={sarif_output}",
        "--threads=0"
    ]
    
    # TIMEOUT 2: 30 minutos máximos para a análise (Salva a pipeline de repositórios gigantes)
    try:
        subprocess.run(cmd_analyze, cwd=caminho_repo, capture_output=True, timeout=1800)
    except subprocess.TimeoutExpired:
        raise CodeQLTimeoutError("A análise do CodeQL excedeu 30 minutos.")

    if not os.path.exists(caminho_sarif):
        raise SarifMissingError("O arquivo SARIF não foi gerado pelo CodeQL.")

    return caminho_sarif