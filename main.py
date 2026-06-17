import json
import sys
import os
import time
import glob
import csv
from datetime import timedelta
from src.config import DATASET_PATH, REPORT_PATH, GEMINI_API_KEY, REPOS_DIR
from src.fase1_codeql import (
    executar_codeql,
    CloneError, CheckoutError, CodeQLBuildError, CodeQLTimeoutError, SarifMissingError,
)
from src.fase2_middleware import extrair_e_hidratar_contexto
from src.fases3_4_llm import avaliar_vulnerabilidade
from src.fase5_auditoria import inicializar_relatorio, registrar_resultado

def definir_nome_relatorio_unico(caminho_padrao):
    """Garante que nenhum relatório seja sobrescrito."""
    if not os.path.exists(caminho_padrao):
        return caminho_padrao

    nome_base, extensao = os.path.splitext(caminho_padrao)
    contador = 1
    
    while True:
        novo_caminho = f"{nome_base}_{contador}{extensao}"
        if not os.path.exists(novo_caminho):
            return novo_caminho
        contador += 1

def carregar_processados_globais():
    """Lê todos os CSVs antigos e retorna um Set com os IDs já processados para pular."""
    processados = set()
    pasta_atual = os.path.dirname(os.path.abspath(__file__))
    arquivos_csv = glob.glob(os.path.join(pasta_atual, "resultados_tcc*.csv"))
    
    for arquivo in arquivos_csv:
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None) # Pula o cabeçalho
                for row in reader:
                    if row: processados.add(row[0]) # Adiciona o ID do Alerta
        except: pass
    return processados

def executar_pipeline():
    if not GEMINI_API_KEY:
        print("[ERRO FATAL] A variável de ambiente GEMINI_API_KEY não está configurada.")
        sys.exit(1)

    caminho_relatorio_atual = definir_nome_relatorio_unico(REPORT_PATH)
    nome_arquivo_exibicao = os.path.basename(caminho_relatorio_atual)

    print("=== INICIANDO PIPELINE NEURO-SIMBÓLICA ===")
    print(f"[+] Alvo de escrita definido: {nome_arquivo_exibicao}")
    
    # --- ACIONANDO O CHECKPOINT ---
    processados = carregar_processados_globais()
    if processados:
        print(f"[+] RECUPERAÇÃO ATIVA: {len(processados)} alertas já processados. Eles serão pulados instantaneamente!")
    print("=========================================================")
    
    with open(DATASET_PATH, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    inicializar_relatorio(caminho_relatorio_atual)
    
    total_alertas = len(dataset)
    tempo_inicio = time.time()
    alertas_efetivamente_processados = 0
    
    for indice, alerta in enumerate(dataset):
        repo_name = alerta['repo_name'].split('/')[-1]
        cwe = alerta['metadata']['cwe_id']
        finding_id = alerta['finding_id']

        # Se já foi processado antes, pula e não gasta tempo
        if finding_id in processados:
            print(f"\n[{indice + 1}/{total_alertas}] [PULADO] {repo_name} | CWE: {cwe} (Recuperado do CSV)")
            continue

        repo_url = alerta['repo_url']
        commit = alerta['commit_hash']
        arquivo_alvo = alerta['to_analyzer']['locations'][0]['file']
        ground_truth = alerta['ground_truth']

        print(f"\n[{indice + 1}/{total_alertas}] Processando: {repo_name} | CWE: {cwe}")

        tempo_alerta_inicio = time.time()
        try:
            # FASE 1
            caminho_sarif = executar_codeql(repo_url, commit, repo_name)

            # FASE 2
            caminho_repo = f"{REPOS_DIR}/{repo_name}"
            contexto = extrair_e_hidratar_contexto(caminho_sarif, arquivo_alvo, caminho_repo)

            if not contexto:
                # PONTO CEGO SIMBÓLICO: o CodeQL não emitiu o alerta.
                # NÃO é decisão do LLM -> entra apenas na matriz de COBERTURA.
                print("    [!] CodeQL não detectou o alerta (cobertura simbólica, fora da matriz do LLM).")
                registrar_resultado(
                    caminho_relatorio_atual, finding_id, repo_name, cwe, ground_truth,
                    status_codeql="NAO_DETECTADO",
                    tempo_exec=time.time() - tempo_alerta_inicio,
                )
            else:
                # FASE 3 e 4
                resposta_ia = avaliar_vulnerabilidade(contexto, cwe)

                # FASE 5 — CodeQL detectou: vale para cobertura E para a matriz do LLM.
                status = "API_ERROR" if resposta_ia.get("verdict") == "ERROR" else "DETECTADO"
                registrar_resultado(
                    caminho_relatorio_atual, finding_id, repo_name, cwe, ground_truth,
                    status_codeql=status,
                    tempo_exec=time.time() - tempo_alerta_inicio,
                    resposta_llm=resposta_ia,
                    erro_msg=resposta_ia.get("reasoning") if status == "API_ERROR" else None,
                )

        except (CloneError, CheckoutError, CodeQLBuildError,
                CodeQLTimeoutError, SarifMissingError) as e:
            categoria = {
                CloneError: "CLONE_FAIL",
                CheckoutError: "CHECKOUT_FAIL",
                CodeQLBuildError: "CODEQL_DB_FAIL",
                CodeQLTimeoutError: "CODEQL_TIMEOUT",
                SarifMissingError: "SARIF_MISSING",
            }[type(e)]
            print(f"    [FALHA DE ESTEIRA] {categoria}: {str(e)[:200]}")
            registrar_resultado(
                caminho_relatorio_atual, finding_id, repo_name, cwe, ground_truth,
                status_codeql=categoria,
                tempo_exec=time.time() - tempo_alerta_inicio,
                erro_msg=str(e),
            )

        except Exception as e:
            print(f"    [ERRO INESPERADO] {str(e)[:200]}")
            registrar_resultado(
                caminho_relatorio_atual, finding_id, repo_name, cwe, ground_truth,
                status_codeql="ERRO_DESCONHECIDO",
                tempo_exec=time.time() - tempo_alerta_inicio,
                erro_msg=str(e),
            )

        # Telemetria recalibrada para ignorar os arquivos pulados
        alertas_efetivamente_processados += 1
        tempo_decorrido_segundos = time.time() - tempo_inicio
        tempo_medio = tempo_decorrido_segundos / alertas_efetivamente_processados
        tempo_restante_segundos = (total_alertas - (indice + 1)) * tempo_medio

        str_decorrido = str(timedelta(seconds=int(tempo_decorrido_segundos)))
        str_restante = str(timedelta(seconds=int(tempo_restante_segundos)))
        print(f"    ⏳ [Telemetria] Sessão atual: {str_decorrido} | Previsão: {str_restante}")

    print(f"\n[+] Execução concluída. Relatório consolidado em: {caminho_relatorio_atual}")
    print(f"[+] Tempo Total da Sessão: {str(timedelta(seconds=int(time.time() - tempo_inicio)))}")

if __name__ == "__main__":
    executar_pipeline()