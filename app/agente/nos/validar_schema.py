import json
from pathlib import Path

from pydantic import ValidationError
from app.schemas.modelos import EstadoGrafo, DocumentoAutomacoes
from app.agente.llm import call_llm
from app.agente.logger import get_logger

logger = get_logger(__name__)

PASTA_PROMPTS = Path("prompts")
MAX_TENTATIVAS = 3


def validar_schema(estado: EstadoGrafo) -> dict:
    """Valida o documento final com Pydantic. Em caso de falha, solicita reparo ao LLM."""
    if not estado.documento_final:
        raise RuntimeError("validar_schema: documento_final está vazio.")

    tentativas = estado.tentativas_reparo

    try:
        DocumentoAutomacoes.model_validate(estado.documento_final.model_dump())
        logger.info("validar_schema | validação OK")
        return {"erros_validacao": []}
    except ValidationError as e:
        erros = [str(err) for err in e.errors()]
        logger.warning("validar_schema | %d erros de schema (tentativa %d)", len(erros), tentativas + 1)

        if tentativas >= MAX_TENTATIVAS:
            raise RuntimeError(f"validar_schema: máximo de tentativas de reparo atingido. Erros: {erros}")

        # Solicita reparo ao LLM
        prompt_sistema = (PASTA_PROMPTS / "gerar_automacoes_candidatas.md").read_text(encoding="utf-8")
        prompt_reparo = (
            f"A saída anterior continha erros de schema Pydantic. Corrija APENAS a estrutura, "
            f"sem alterar o conteúdo. Erros:\n{json.dumps(erros, ensure_ascii=False)}\n\n"
            f"Documento com erro:\n{estado.documento_final.model_dump_json(indent=2)}"
        )

        resposta, tokens = call_llm(prompt_sistema, prompt_reparo, temperature=0.0)
        logger.info("validar_schema | reparo solicitado | %d tokens", tokens)

        try:
            dados = json.loads(resposta)
            documento_reparado = DocumentoAutomacoes(**dados)
        except Exception as parse_err:
            raise RuntimeError(f"validar_schema: reparo retornou JSON inválido — {parse_err}")

        return {
            "documento_final": documento_reparado,
            "erros_validacao": erros,
            "tentativas_reparo": tentativas + 1,
        }
