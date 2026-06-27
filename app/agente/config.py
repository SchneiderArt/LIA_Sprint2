import os
from dotenv import load_dotenv

# Carrega as variáveis definidas no arquivo .env na raiz do projeto
load_dotenv()

# Captura a chave da API
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# Captura o modelo ou define um padrão seguro e econômico
LLM_MODEL = os.environ.get("LLM_MODEL", "google/gemma-4-31b-it")

# Validação rápida para evitar falhas silenciosas
if not OPENROUTER_API_KEY:
    print("AVISO: OPENROUTER_API_KEY não foi encontrada no ambiente.")

