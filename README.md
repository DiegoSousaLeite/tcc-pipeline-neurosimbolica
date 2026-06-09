# Pipeline de Triagem Neuro-Simbólica para SAST (Golang)

Este repositório contém o ambiente experimental projetado para avaliar a eficácia de Modelos de Linguagem de Grande Escala (LLMs) na filtragem de alertas Falsos Positivos gerados por ferramentas de Análise Estática (SAST) em projetos Go.

A arquitetura simula uma esteira DevSecOps nativa, dividida em 5 fases de processamento agnóstico.

## ⚙️ Pré-requisitos e Dependências

1.  **CodeQL CLI**: O binário `codeql` deve estar acessível no `PATH` do sistema.
2.  **Git**: Necessário para os comandos de isolamento (`clone` e `checkout`).
3.  **Python 3.9+**

Instale as dependências Python necessárias:
\`\`\`bash
pip install -r requirements.txt
\`\`\`
*(Nota: O `requirements.txt` requer apenas a biblioteca `requests`)*

## 🚀 Configuração e Execução

### Passo 1: Variáveis de Ambiente
Configure a chave da API do modelo de fronteira no seu terminal:

**Windows (PowerShell):**
\`\`\`powershell
$env:GEMINI_API_KEY="SUA_CHAVE_AQUI"
\`\`\`

**Linux/macOS:**
\`\`\`bash
export GEMINI_API_KEY="SUA_CHAVE_AQUI"
\`\`\`

### Passo 2: O Dataset
Certifique-se de que o arquivo resultante do pré-processamento, nomeado `dataset_go_limpo.json`, encontra-se no diretório `data/`.

### Passo 3: Executar a Pipeline
Na raiz do projeto, execute o orquestrador principal:
\`\`\`bash
python main.py
\`\`\`

## 🏗️ Arquitetura do Sistema (`src/`)

O código está isolado nos seguintes módulos:

-   `fase1_codeql.py`: Automatiza a recuperação do código no momento exato da vulnerabilidade (via `git checkout`) e invoca o motor relacional do CodeQL para gerar o `.sarif` bruto.
-   `fase2_middleware.py`: Atua como ponte neuro-simbólica. Navega na árvore JSON do SARIF, isola as rotas críticas de *Taint Analysis* e hidrata os pontos nodais extraindo o código-fonte adjacente diretamente dos arquivos `.go`.
-   `fases3_4_llm.py`: Monta o construto sistêmico (Prompt Especialista) imbuído de semântica técnica do Golang e gerencia a inferência estrita via requisições REST para a nuvem.
-   `fase5_auditoria.py`: Atua de forma isolada na ponta da esteira laboratorial, confrontando as previsões do modelo contra o *Ground Truth* do SastBench para alimentar a Matriz de Confusão do experimento.