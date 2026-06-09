import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env para o sistema
load_dotenv()

# Configurações de Diretórios
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPOS_DIR = os.path.join(BASE_DIR, "repos")

# Arquivos de Entrada e Saída
DATASET_PATH = os.path.join(DATA_DIR, "dataset_go_limpo.json")
REPORT_PATH = os.path.join(BASE_DIR, "resultados_tcc.csv")

# Configurações do LLM (Gemini)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODELO_LLM = os.getenv("LLM_MODEL_VERSION") or "gemini-1.5-flash"
URL_API_GEMINI = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO_LLM}:generateContent?key={GEMINI_API_KEY}"

os.makedirs(REPOS_DIR, exist_ok=True)