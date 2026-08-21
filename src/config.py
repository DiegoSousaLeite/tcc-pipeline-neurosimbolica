import os

from dotenv import load_dotenv

load_dotenv()

# Configurações de Diretórios
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPOS_DIR = os.path.join(BASE_DIR, "repos")
# Cache de arquivos-alvo (repo+commit+arquivo). Substitui o clone completo:
# a pipeline só consome um arquivo por caso. Ver src/fonte.py.
CACHE_DIR = os.path.join(BASE_DIR, "cache")
# Cache do RESULTADO simbólico (alerta do Semgrep + contexto hidratado). Fica
# separado do de fontes porque depende da versão do ruleset, que muda — o de
# fontes é imutável por construção e nunca invalida. Ver src/cache_simbolico.py.
CACHE_SIMBOLICO_DIR = os.path.join(BASE_DIR, "cache_simbolico")

# Arquivos de Entrada e Saída
DATASET_PATH = os.path.join(DATA_DIR, "dataset_go_limpo.json")
REPORT_PATH = os.path.join(BASE_DIR, "resultados_tcc.csv")
# Catálogo de triagem por CWE: fonte única da heurística e dos exemplos
# few-shot do prompt especialista. Congelado por hash. Ver src/catalogo.py.
CATALOGO_CWE_PATH = os.path.join(DATA_DIR, "catalogo_cwe.json")
# Templates de prompt versionados (baseline e especialista). Ver src/prompts.py.
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
# Saída das rodadas: results/<run_id>/ com um CSV por braço + manifesto.json.
RESULTS_DIR = os.path.join(BASE_DIR, "results")

# Configurações do LLM
# A chave NÃO entra em nenhuma URL: os provedores a enviam em header
# (`x-goog-api-key` / `Authorization: Bearer`). Na Parte 1 ela ia na query
# string de URL_API_GEMINI, onde vazava em log de URL, traceback e proxy.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODELO_LLM = os.getenv("LLM_MODEL_VERSION") or "gemini-2.5-flash-lite"

# Variáveis experimentais (estáticas na Parte 1 / MVP; serão iteradas na Parte 2).
# Registradas em cada linha do CSV para permitir o cruzamento futuro entre
# modelos (GPT vs Gemini) e estratégias de prompt (baseline vs especialista).
PROMPT_TYPE = os.getenv("PROMPT_TYPE") or "especialista"

# repos/ é opcional: se existir, src/fonte.py o usa como fonte barata (git show).
# Não criamos o diretório — a pipeline funciona só com o cache.
os.makedirs(CACHE_DIR, exist_ok=True)