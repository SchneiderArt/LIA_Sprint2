"""
Aplicação FastAPI — Sprint 2, Entrega 2 (UFMS Apoia MDA / MAPA — Meta 3).

Subir localmente:
    uvicorn app.api.main:app --reload

Documentação interativa em http://127.0.0.1:8000/docs após subir o servidor.
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI

from app.api.rotas import roteador

app = FastAPI(
    title="UFMS Apoia MDA — Sprint 2 (Entrega 2)",
    description="Identificação de automações candidatas a partir de BPMN + PDF.",
    version="1.0.0",
)
app.include_router(roteador)
