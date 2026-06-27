import json
from pathlib import Path
from app.schemas.modelos import EstadoGrafo, DocumentoPDFJSON
from app.agente.llm import call_llm
from app.agente.logger import get_logger

logger = get_logger(__name__)

PASTA_PROMPTS = Path("prompts")


def pdf_para_json(estado: EstadoGrafo) -> dict:
    """Converte o texto extraído do PDF em um DocumentoPDFJSON estruturado."""
    prompt_sistema = (PASTA_PROMPTS / "pdf_para_json.md").read_text(encoding="utf-8")
    prompt_usuario = f"Texto extraído do PDF:\n\n{estado.texto_pdf}"

    resposta, tokens = call_llm(prompt_sistema, prompt_usuario, temperature=0.0)

    try:
        dados = json.loads(resposta)
        documento_pdf_json = DocumentoPDFJSON(**dados)
    except Exception as e:
        logger.error("pdf_para_json | falha ao parsear resposta: %s", e)
        raise RuntimeError(f"pdf_para_json: resposta do LLM não é um JSON válido — {e}")

    logger.info("pdf_para_json | %d tokens usados", tokens)

    return {"documento_pdf_json": documento_pdf_json}
