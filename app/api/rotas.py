"""
Rotas da API FastAPI — a porta de entrada e saída do sistema (Sprint 2).

Endpoints (seção 8 do documento da sprint):
  GET  /health
  POST /analisar-processo                          — recebe BPMN + PDF e roda o pipeline
  GET  /runs/{run_id}                               — consulta o estado de uma execução
  GET  /runs/{run_id}/download/{artefato}           — baixa um artefato gerado

A API reaproveita o mesmo motor da CLI (``app.graph.executar_pipeline``) e
devolve os metadados no formato ``RunMetadata`` (``app/schemas.py``). Os arquivos
já são gravados run-scoped pelos nós (``saidas/<run_id>/...``, via ``config``),
então a API não relocaliza nada: ela lê os artefatos direto do disco.
"""
from __future__ import annotations

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api import armazenamento
from app.api.seguranca import ler_upload_limitado, validar_xml_seguro
from app.schemas import RunMetadata, RunStatus
from app.utils import config

logger = logging.getLogger(__name__)
roteador = APIRouter()

# Registro das execuções em memória — usado por /runs/{run_id} (status/avisos).
# O download NÃO depende dele: lê do disco e sobrevive a reinício do servidor.
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
    metadados (id, status, avisos, erros, contagem e mapa de artefatos).

    O mapa ``artefatos`` traz os códigos baixáveis (ver o endpoint de download).
    """
    # 1. Lê e valida os uploads ANTES de gravar qualquer coisa em disco.
    conteudo_bpmn = await ler_upload_limitado(bpmn_file, ".bpmn")
    conteudo_pdf = await ler_upload_limitado(pdf_file, ".pdf")
    validar_xml_seguro(conteudo_bpmn)

    # 2. Cria a execução isolada e salva as entradas (caminhos relativos).
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    caminho_bpmn, caminho_pdf = armazenamento.salvar_entradas(
        run_id, conteudo_bpmn, conteudo_pdf
    )

    # 3. Roda o mesmo motor da CLI. Import tardio: não acopla o boot da API ao
    #    carregamento do grafo e suas dependências pesadas.
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
            erros=[f"Falha ao processar: {e}"],
        )
        _execucoes[run_id] = meta
        return meta

    # 4. Mapeia EstadoGrafo -> RunMetadata. Os artefatos são lidos do disco
    #    (já estão run-scoped em saidas/<run_id>/artefatos/<abordagem>/).
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
        avisos=estado.avisos,
        erros=estado.erros,
        quantidade_automacoes=quantidade_automacoes,
        artefatos=config.listar_artefatos(run_id),
    )
    _execucoes[run_id] = meta
    logger.info(
        "analisar_processo | run=%s | status=%s | pipeline=%s",
        run_id, status.value, pipeline,
    )
    return meta


@roteador.get("/runs/{run_id}", response_model=RunMetadata)
def consultar_run(run_id: str) -> RunMetadata:
    """Devolve os metadados de uma execução (do registro em memória)."""
    meta = _execucoes.get(run_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    return meta


@roteador.get("/runs/{run_id}/download/{artefato:path}")
def baixar_artefato(run_id: str, artefato: str) -> FileResponse:
    """
    Baixa um artefato gerado por uma execução. Lê direto do disco, então funciona
    mesmo depois de reiniciar o servidor.

    O código do artefato é o caminho relativo dentro de ``artefatos/``, no
    formato ``<abordagem>/<arquivo>``. Códigos válidos por pipeline:

      - json:    ``json/documento_final.md``, ``json/documento_final.pdf``, ``json/auditoria.json``
      - natural: ``natural/documento_final.md``, ``natural/documento_final.pdf``, ``natural/auditoria.json``
      - both:    os de ``json/`` e ``natural/``, mais ``comparativo/documento_final.md``,
                 ``comparativo/documento_final.pdf`` e ``comparativo/auditoria.json``

    Consulte o mapa ``artefatos`` em ``GET /runs/{run_id}`` para ver exatamente o
    que aquela execução produziu.
    """
    base = config.pasta_artefatos(run_id).resolve()
    if not base.is_dir():
        raise HTTPException(status_code=404, detail="Execução não encontrada.")

    caminho = (base / artefato).resolve()
    # Trava anti path traversal: o alvo TEM que estar dentro de artefatos/.
    if base not in caminho.parents:
        raise HTTPException(status_code=404, detail="Código de artefato inválido.")
    if not caminho.is_file():
        disponiveis = ", ".join(config.listar_artefatos(run_id)) or "(nenhum)"
        raise HTTPException(
            status_code=404,
            detail=f"Artefato não encontrado nesta execução. Disponíveis: {disponiveis}",
        )
    return FileResponse(caminho, filename=caminho.name)
