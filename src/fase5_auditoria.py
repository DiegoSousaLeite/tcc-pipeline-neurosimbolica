import csv
from typing import Dict

def inicializar_relatorio(caminho_csv: str):
    """Cria o cabeçalho do arquivo CSV se for uma nova execução."""
    with open(caminho_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ID_Alerta', 'Repositorio', 'CWE', 'Gabarito_SastBench', 'Veredito_LLM', 'Classificacao', 'Justificativa'])

def registrar_resultado(caminho_csv: str, id_alerta: str, repo_name: str, cwe: str, ground_truth: str, resposta_llm: Dict):
    """Cruza o resultado e salva na base de dados final do experimento."""
    verdict_llm = resposta_llm.get('verdict', 'ERROR')
    
    previsao = "true_positive" if verdict_llm == "TP" else "false_positive" if verdict_llm == "FP" else "ERROR"
    
    if previsao == "ERROR":
        classificacao = "Erro de Inferência"
    elif ground_truth == "true_positive" and previsao == "true_positive":
        classificacao = "True Positive (Acerto)"
    elif ground_truth == "false_positive" and previsao == "false_positive":
        classificacao = "True Negative (Acerto)"
    elif ground_truth == "true_positive" and previsao == "false_positive":
        classificacao = "False Negative (Falha Crítica)"
    else:
        classificacao = "False Positive (Ruído Mantido)"

    with open(caminho_csv, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([id_alerta, repo_name, cwe, ground_truth, previsao, classificacao, resposta_llm.get('reasoning')])
        
    print(f"    [Matriz] {ground_truth} vs {previsao} => {classificacao}")