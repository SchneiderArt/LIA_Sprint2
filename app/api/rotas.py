"""
Rotas da API FastAPI — a porta de entrada e saída do sistema (Sprint 2, Entrega 2).

Endpoints (seção 8 do documento da sprint):
  GET  /health
  POST /analisar-processo                   — recebe BPMN + PDF e roda o pipeline
  GET  /runs/{run_id}                        — consulta o estado de uma execução
  GET  /runs/{run_id}/download/{artefato}    — baixa um artefato gerado

A API reaproveita o mesmo motor da CLI (``app.graph.executar_pipeline``) e
devolve os metadados no formato ``RunMetadata`` já definido em ``app/schemas.py``.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api import armazenamento
from app.api.seguranca import ler_upload_limitado, validar_xml_seguro
from app.schemas import RunMetadata, RunStatus

logger = logging.getLogger(__name__)
roteador = APIRouter()

# Registro das execuções em memória. Suficiente para o escopo do sprint; em
# produção isto seria um banco de dados.
_execucoes: dict[str, RunMetadata] = {}


@roteador.get("/health")
def health() -> dict:
    """Sinaliza que a API está no ar."""
    return {"status": "ok", "versao": "1.0.0"}


@roteador.post("/analisar-processo", response_model=RunMetadata)
async def analisar_processo(
    bpmn_file: UploadFile = File(...),
    pdf_file: UploadFile = File(...),
    pipeline: Literal["natural", "json", "both"] = Form(default="json"),
) -> RunMetadata:
    """
    Recebe o ``.bpmn`` e o ``.pdf`` de um processo, roda o pipeline e devolve os
    metadados da execução (id, status, avisos, erros, contagem e artefatos).
    """
    # 1. Lê e valida os uploads ANTES de gravar qualquer coisa em disco.
    conteudo_bpmn = await ler_upload_limitado(bpmn_file, ".bpmn")
    conteudo_pdf = await ler_upload_limitado(pdf_file, ".pdf")
    validar_xml_seguro(conteudo_bpmn)

    # 2. Cria a execução isolada e salva as entradas com nome controlado. Os
    #    caminhos devolvidos são relativos (ingest_files rejeita absolutos).
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    caminho_bpmn, caminho_pdf = armazenamento.salvar_entradas(
        run_id, conteudo_bpmn, conteudo_pdf
    )

    avisos: list[str] = []

    # 3. Roda o mesmo motor da CLI. Import tardio de propósito: não acopla o boot
    #    da API ao carregamento do grafo e suas dependências pesadas.
    try:
        from app.graph import executar_pipeline

        estado = executar_pipeline(
            caminho_bpmn=caminho_bpmn,
            caminho_pdf=caminho_pdf,
            run_id=run_id,
            pipeline=pipeline,
        )
    except Exception as e:
        logger.error("analisar_processo | run=%s | erro: %s", run_id, e)
        meta = RunMetadata(
            run_id=run_id, status=RunStatus.ERRO, pipeline=pipeline,
            avisos=avisos, erros=[f"Falha ao processar: {e}"],
        )
        _execucoes[run_id] = meta
        return meta

    # 4. Mapeia EstadoGrafo -> RunMetadata, isolando os artefatos por execução.
    artefatos = armazenamento.realocar_artefatos(run_id, estado.artefatos)
    status = RunStatus.ERRO if estado.erros else RunStatus.CONCLUIDO

    if pipeline == "both":
        quantidade_automacoes = {
            "json":    len(estado.candidatos_json),
            "natural": len(estado.candidatos_natural),
        }
    elif pipeline == "natural":
        quantidade_automacoes = {"natural": len(estado.candidatos)}
    else:
        quantidade_automacoes = {"json": len(estado.candidatos)}

    meta = RunMetadata(
        run_id=run_id,
        status=status,
        pipeline=pipeline,
        avisos=avisos + estado.avisos,
        erros=estado.erros,
        quantidade_automacoes=quantidade_automacoes,
        artefatos=artefatos,
    )
    _execucoes[run_id] = meta
    logger.info(
        "analisar_processo | run=%s | status=%s | %d automacao(oes)",
        run_id, status.value, len(estado.candidatos),
    )
    return meta


@roteador.get("/runs/{run_id}", response_model=RunMetadata)
def consultar_run(run_id: str) -> RunMetadata:
    """Devolve os metadados de uma execução."""
    meta = _execucoes.get(run_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    return meta


@roteador.get("/runs/{run_id}/download/{artefato}")
def baixar_artefato(run_id: str, artefato: str) -> FileResponse:
    """Baixa, pela chave, um artefato gerado por uma execução."""
    meta = _execucoes.get(run_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")

    caminho = meta.artefatos.get(artefato)
    if caminho is None:
        raise HTTPException(status_code=404, detail="Artefato não encontrado.")
    return FileResponse(caminho, filename=Path(caminho).name)
