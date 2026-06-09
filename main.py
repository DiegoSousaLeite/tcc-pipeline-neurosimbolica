import json
import sys
from src.config import DATASET_PATH, REPORT_PATH, GEMINI_API_KEY, REPOS_DIR
from src.fase1_codeql import executar_codeql
from src.fase2_middleware import extrair_e_hidratar_contexto
from src.fases3_4_llm import avaliar_vulnerabilidade
from src.fase5_auditoria import inicializar_relatorio, registrar_resultado

def executar_pipeline():
    if not GEMINI_API_KEY:
        print("[ERRO FATAL] A variável de ambiente GEMINI_API_KEY não está configurada.")
        sys.exit(1)

    print("=== INICIANDO PIPELINE NEURO-SIMBÓLICA (EXPERIMENTO) ===")
    
    with open(DATASET_PATH, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    inicializar_relatorio(REPORT_PATH)
    
    # for indice, alerta in enumerate(dataset):
    for indice, alerta in enumerate(dataset[0:1]):
        repo_url = alerta['repo_url']
        commit = alerta['commit_hash']
        repo_name = alerta['repo_name'].split('/')[-1]
        arquivo_alvo = alerta['to_analyzer']['locations'][0]['file']
        cwe = alerta['metadata']['cwe_id']
        ground_truth = alerta['ground_truth']
        finding_id = alerta['finding_id']

        print(f"\n[{indice + 1}/{len(dataset)}] Processando: {repo_name} | CWE: {cwe}")
        
        try:
            # FASE 1
            caminho_sarif = executar_codeql(repo_url, commit, repo_name)
            
            # FASE 2
            caminho_repo = f"{REPOS_DIR}/{repo_name}"
            contexto = extrair_e_hidratar_contexto(caminho_sarif, arquivo_alvo, caminho_repo)
            
            if not contexto:
                print("    [!] Aviso: CodeQL não encontrou rastros correspondentes para este alerta.")
                continue

            # FASE 3 e 4
            resposta_ia = avaliar_vulnerabilidade(contexto, cwe)
            
            # FASE 5
            registrar_resultado(REPORT_PATH, finding_id, repo_name, cwe, ground_truth, resposta_ia)

        except Exception as e:
            print(f"    [ERRO] Falha ao processar repositório: {str(e)}")
            continue

    print(f"\n[+] Execução concluída. Relatório consolidado em: {REPORT_PATH}")

if __name__ == "__main__":
    executar_pipeline()