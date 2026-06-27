import json
from datetime import date
from pathlib import Path

from app.schemas.modelos import EstadoGrafo, DocumentoAutomacoes, AutomacaoCandidataJSON
from app.agente.llm import call_llm
from app.agente.logger import get_logger

logger = get_logger(__name__)

PASTA_PROMPTS = Path("prompts")


def _montar_contexto_natural(estado: EstadoGrafo) -> str:
    return (
        f"## Narrativa do processo (BPMN)\n\n{estado.narrativa_bpmn}\n\n"
        f"## Descritivo do processo (PDF)\n\n{estado.texto_pdf}"
    )


def _montar_contexto_json(estado: EstadoGrafo) -> str:
    bpmn_str = estado.processo_json.model_dump_json(indent=2) if estado.processo_json else "{}"
    pdf_str = estado.documento_pdf_json.model_dump_json(indent=2) if estado.documento_pdf_json else "{}"
    return (
        f"## Processo BPMN (JSON estruturado)\n\n{bpmn_str}\n\n"
        f"## Descritivo PDF (JSON estruturado)\n\n{pdf_str}"
    )


def gerar_candidatas(estado: EstadoGrafo) -> dict:
    """Envia o contexto ao LLM e obtém as automações candidatas."""
    prompt_sistema = (PASTA_PROMPTS / "gerar_automacoes_candidatas.md").read_text(encoding="utf-8")

    if estado.pipeline == "natural":
        contexto = _montar_contexto_natural(estado)
    elif estado.pipeline == "json":
        contexto = _montar_contexto_json(estado)
    else:  # both — usa JSON quando disponível, natural como fallback
        contexto = _montar_contexto_json(estado) if estado.processo_json else _montar_contexto_natural(estado)

    resposta, tokens = call_llm(prompt_sistema, contexto, temperature=0.2)

    try:
        dados = json.loads(resposta)
        automacoes = [AutomacaoCandidataJSON(**a) for a in dados.get("automacoes", [])]
        nome_processo = dados.get("nome_processo", estado.processo_json.nome if estado.processo_json else "Processo")
        unidades = dados.get("unidades_envolvidas", [])
        resumo = dados.get("resumo_executivo", "")
    except Exception as e:
        logger.error("gerar_candidatas | falha ao parsear resposta: %s", e)
        raise RuntimeError(f"gerar_candidatas: resposta inválida — {e}")

    documento = DocumentoAutomacoes(
        nome_processo=nome_processo,
        arquivo_bpmn=Path(estado.caminho_bpmn).name,
        arquivo_pdf=Path(estado.caminho_pdf).name,
        data_analise=str(date.today()),
        unidades_envolvidas=unidades,
        resumo_executivo=resumo,
        automacoes=automacoes,
    )

    logger.info("gerar_candidatas | %d automações geradas | %d tokens", len(automacoes), tokens)

    return {
        "documento_final": documento,
        "prompt_usado": f"[SISTEMA]\n{prompt_sistema}\n\n[USUÁRIO]\n{contexto}",
    }
