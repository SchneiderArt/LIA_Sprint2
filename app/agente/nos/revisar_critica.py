import json
from pathlib import Path

from app.schemas.modelos import EstadoGrafo, AutomacaoCandidataJSON
from app.agente.llm import call_llm
from app.agente.logger import get_logger

logger = get_logger(__name__)

PASTA_PROMPTS = Path("prompts")


def revisar_critica(estado: EstadoGrafo) -> dict:
    """Verifica lacunas, duplicidades e generalizações nas automações candidatas."""
    if not estado.documento_final:
        raise RuntimeError("revisar_critica: documento_final está vazio.")

    prompt_sistema = (PASTA_PROMPTS / "revisar_critica.md").read_text(encoding="utf-8")
    candidatas_json = json.dumps(
        [a.model_dump() for a in estado.documento_final.automacoes],
        ensure_ascii=False,
        indent=2,
    )
    prompt_usuario = f"Automações candidatas para revisão:\n\n{candidatas_json}"

    resposta, tokens = call_llm(prompt_sistema, prompt_usuario, temperature=0.0)

    try:
        dados = json.loads(resposta)
        automacoes_revisadas = [AutomacaoCandidataJSON(**a) for a in dados.get("automacoes", [])]
    except Exception as e:
        logger.warning("revisar_critica | não foi possível aplicar revisão: %s", e)
        return {}  # mantém as candidatas originais se a revisão falhar

    documento_atualizado = estado.documento_final.model_copy(
        update={"automacoes": automacoes_revisadas}
    )

    logger.info("revisar_critica | %d automações após revisão | %d tokens", len(automacoes_revisadas), tokens)

    return {"documento_final": documento_atualizado}
