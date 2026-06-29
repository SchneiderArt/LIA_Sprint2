"""
Nó LangGraph: build_prompt_context
Etapa 6 — Sprint 2, Entrega 2

Responsabilidades (conforme documento da sprint, seção 7.1, passo 7):
  - Combinar ProcessoJSON e DocumentoPDFJSON em um contexto único para o agente
  - Salvar o prompt montado em /saidas/intermediarios/ para auditoria (seção 8.1)
  - Registrar avisos se algum dos JSONs estiver ausente no estado
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.prompts import montar_contexto_json
from app.schemas import EstadoGrafo

logger = logging.getLogger(__name__)


def build_prompt_context(estado: EstadoGrafo) -> EstadoGrafo:
    """
    Nó LangGraph: monta o contexto combinado (ProcessoJSON + DocumentoPDFJSON)
    que será enviado ao LLM no nó generate_candidates.

    Salva o prompt em /saidas/intermediarios/prompt_usado.txt para auditoria,
    conforme exigido pela seção 8.1 do documento da sprint.
    """
    if estado.processo_json is None:
        estado.erros.append(
            "build_prompt_context: processo_json ausente no estado. "
            "Verifique se o nó parse_bpmn_to_json executou com sucesso."
        )
        return estado

    if estado.documento_pdf_json is None:
        estado.erros.append(
            "build_prompt_context: documento_pdf_json ausente no estado. "
            "Verifique se o nó extract_pdf_to_json executou com sucesso."
        )
        return estado

    # Montar contexto combinado usando o helper do módulo prompts
    contexto = montar_contexto_json(estado.processo_json, estado.documento_pdf_json)

    estado.prompt_usado = contexto
    logger.debug(
        "build_context: processo=%s | candidatos_pdf=%d",
        estado.processo_json.nome if estado.processo_json else "?",
        len(estado.documento_pdf_json.procedimentos) if estado.documento_pdf_json else 0,
    )
    logger.info(
        "build_prompt_context: contexto montado — %d chars", len(contexto)
    )

    # Salvar prompt para auditoria (seção 8.1: "prompt usado" deve ser salvo)
    saida_dir = Path("saidas/intermediarios")
    saida_dir.mkdir(parents=True, exist_ok=True)
    saida_path = saida_dir / "prompt_usado.txt"

    try:
        saida_path.write_text(contexto, encoding="utf-8")
        estado.artefatos["prompt_usado"] = str(saida_path)
        logger.info("prompt_usado.txt salvo em %s", saida_path)
    except OSError as exc:
        estado.avisos.append(
            f"build_prompt_context: não foi possível salvar prompt — {exc}"
        )

    return estado
