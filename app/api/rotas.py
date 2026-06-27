import uuid
import shutil
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse

from app.agente.grafo import construir_grafo
from app.schemas.modelos import EstadoGrafo
from app.agente.logger import get_logger

logger = get_logger(__name__)
roteador = APIRouter()

# Registro em memória dos runs (em produção, usar banco de dados)
_runs: dict[str, dict] = {}

PASTA_SAIDAS = Path("saidas")
TAMANHO_MAXIMO = 20 * 1024 * 1024  # 20 MB


def _validar_upload(arquivo: UploadFile, extensao: str):
    if not arquivo.filename or not arquivo.filename.lower().endswith(extensao):
        raise HTTPException(400, detail=f"Arquivo inválido: esperado extensão {extensao}")


@roteador.get("/health")
def health():
    return {"status": "ok", "versao": "1.0.0"}


@roteador.post("/analisar-processo")
async def analisar_processo(
    bpmn_file: UploadFile = File(...),
    pdf_file: UploadFile = File(...),
    pipeline: Literal["natural", "json", "both"] = Form(default="both"),
):
    _validar_upload(bpmn_file, ".bpmn")
    _validar_upload(pdf_file, ".pdf")

    run_id = str(uuid.uuid4())[:8]
    pasta_run = PASTA_SAIDAS / run_id
    pasta_run.mkdir(parents=True, exist_ok=True)

    # Salva uploads em pasta isolada
    caminho_bpmn = pasta_run / "processo.bpmn"
    caminho_pdf = pasta_run / "descritivo.pdf"

    conteudo_bpmn = await bpmn_file.read()
    conteudo_pdf = await pdf_file.read()

    if len(conteudo_bpmn) > TAMANHO_MAXIMO or len(conteudo_pdf) > TAMANHO_MAXIMO:
        raise HTTPException(413, detail="Arquivo excede o tamanho máximo de 20 MB.")

    caminho_bpmn.write_bytes(conteudo_bpmn)
    caminho_pdf.write_bytes(conteudo_pdf)

    _runs[run_id] = {"status": "processando", "pipeline": pipeline, "avisos": [], "artefatos": {}}

    try:
        estado_inicial = EstadoGrafo(
            caminho_bpmn=str(caminho_bpmn),
            caminho_pdf=str(caminho_pdf),
            pipeline=pipeline,
        )
        grafo = construir_grafo()
        estado_final: EstadoGrafo = grafo.invoke(estado_inicial)

        # Registra artefatos gerados
        artefatos = {
            f.name: str(f)
            for f in PASTA_SAIDAS.glob("*.json")
        }
        artefatos.update({
            f.name: str(f)
            for f in PASTA_SAIDAS.glob("*.md")
        })

        qtd_automacoes = len(estado_final.documento_final.automacoes) if estado_final.documento_final else 0

        _runs[run_id].update({
            "status": "concluido",
            "avisos": estado_final.avisos,
            "artefatos": artefatos,
            "qtd_automacoes": qtd_automacoes,
        })

        logger.info("analisar_processo | run=%s | %d automações", run_id, qtd_automacoes)

    except Exception as e:
        _runs[run_id].update({"status": "erro", "erro": str(e)})
        logger.error("analisar_processo | run=%s | erro: %s", run_id, e)
        raise HTTPException(500, detail=str(e))

    return {
        "run_id": run_id,
        "status": _runs[run_id]["status"],
        "pipeline": pipeline,
        "qtd_automacoes": _runs[run_id].get("qtd_automacoes", 0),
        "avisos": _runs[run_id]["avisos"],
        "artefatos": _runs[run_id]["artefatos"],
    }


@roteador.get("/runs/{run_id}")
def consultar_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(404, detail="Run não encontrado.")
    return _runs[run_id]


@roteador.get("/runs/{run_id}/download/{artefato}")
def baixar_artefato(run_id: str, artefato: str):
    if run_id not in _runs:
        raise HTTPException(404, detail="Run não encontrado.")
    caminhos = _runs[run_id].get("artefatos", {})
    if artefato not in caminhos:
        raise HTTPException(404, detail="Artefato não encontrado.")
    return FileResponse(caminhos[artefato], filename=artefato)
