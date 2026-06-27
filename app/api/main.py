from fastapi import FastAPI
from app.api.rotas import roteador

app = FastAPI(title="UFMS Apoia MDA — Sprint 2", version="1.0.0")
app.include_router(roteador)
