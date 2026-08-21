import os

import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY", "").strip()

print("=== CONSULTANDO O GOOGLE AI STUDIO ===")
url_list = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

response = requests.get(url_list)

if response.status_code == 200:
    modelos = response.json().get('models', [])
    print("\n[+] Modelos 'Flash' disponíveis e compatíveis com a sua chave:")
    print("-" * 50)
    for m in modelos:
        nome_completo = m.get('name') # Ex: models/gemini-1.5-flash-002
        metodos = m.get('supportedGenerationMethods', [])
        
        if 'flash' in nome_completo.lower() and 'generateContent' in metodos:
            nome_limpo = nome_completo.replace('models/', '')
            print(f" -> {nome_limpo}")
    print("-" * 50)
else:
    print(f"\n[FALHA] Não foi possível listar os modelos. Erro: {response.text}")