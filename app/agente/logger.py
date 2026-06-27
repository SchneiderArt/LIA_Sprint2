import logging
import json
import uuid
from datetime import datetime

# Gera um ID único para cada vez que o script rodar
EXECUTION_ID = str(uuid.uuid4())[:8]

class JsonFormatter(logging.Formatter):
    """Formatador personalizado para gerar logs em formato JSON estrito."""
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "exec_id": EXECUTION_ID,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }
        return json.dumps(log_record)

def get_logger(name: str) -> logging.Logger:
    """
    Retorna uma instância de logger configurada para saídas duplas:
    - Terminal (texto legível)
    - Arquivo JSON (estruturado para auditoria)
    """
    logger = logging.getLogger(name)
    
    # Previne a duplicação de logs se a função for chamada várias vezes
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # 1. Handler para o Console (Terminal)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO) 
        console_formatter = logging.Formatter(f'%(asctime)s | %(levelname)s | %(name)s | %(message)s', datefmt='%H:%M:%S')
        console_handler.setFormatter(console_formatter)
        
        # 2. Handler para Arquivo (Log estruturado JSON)
        # Salva na pasta 'saidas', conforme padrão do projeto
        import os
        os.makedirs("saidas", exist_ok=True)
        file_handler = logging.FileHandler("saidas/execucao_agente.log", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JsonFormatter())
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
    return logger