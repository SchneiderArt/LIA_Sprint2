from pathlib import Path
from app.schemas.modelos import EstadoGrafo
from app.agente.llm import call_llm
from app.agente.logger import get_logger

logger = get_logger(__name__)

PASTA_PROMPTS = Path("prompts")


def bpmn_para_linguagem_natural(estado: EstadoGrafo) -> dict:
    """Converte o XML normalizado do BPMN em narrativa administrativa em português."""
    prompt_sistema = (PASTA_PROMPTS / "bpmn_para_linguagem_natural.md").read_text(encoding="utf-8")
    prompt_usuario = f"XML BPMN normalizado:\n\n{estado.xml_normalizado}"

    narrativa, tokens = call_llm(prompt_sistema, prompt_usuario, temperature=0.0)

    logger.info("bpmn_para_linguagem_natural | %d tokens usados", tokens)

    return {"narrativa_bpmn": narrativa}
