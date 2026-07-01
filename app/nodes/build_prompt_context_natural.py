"""
Nó LangGraph: build_prompt_context_natural
Entrega 1 — Sprint 2 (responsabilidade: Davi Gaborim)

Combina narrativa do BPMN (estado.narrativa_bpmn) e texto extraído do PDF
(estado.pdf_texto_extraido) em um único contexto para o nó
generate_candidates, no mesmo espírito de app/nodes/build_prompt_context.py
(versão JSON, da Entrega 2).

Nota para integração: generate_automation_candidates.md hoje só descreve o
formato de entrada [PROCESSO_JSON]/[DOCUMENTO_PDF_JSON] (Entrega 2). Para a
Entrega 1 usar o mesmo nó generate_candidates, esse prompt precisa também
descrever o formato [NARRATIVA_BPMN]/[TEXTO_PDF] usado aqui.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.schemas import EstadoGrafo

logger = logging.getLogger(__name__)


def montar_contexto_natural(narrativa_bpmn: str, pdf_texto: str) -> str:
    return (
        f"[NARRATIVA_BPMN]\n{narrativa_bpmn}\n[/NARRATIVA_BPMN]\n\n"
        f"[TEXTO_PDF]\n{pdf_texto}\n[/TEXTO_PDF]"
    )


def build_prompt_context_natural(estado: EstadoGrafo) -> EstadoGrafo:
    """
    Nó LangGraph: monta o contexto combinado (narrativa BPMN + texto PDF)
    da Entrega 1. Salva em /saidas/intermediarios/prompt_usado_natural.txt.
    """
    if estado.narrativa_bpmn is None:
        estado.erros.append(
            "build_prompt_context_natural: narrativa_bpmn ausente no estado. "
            "Verifique se o nó bpmn_to_natural_language executou com sucesso."
        )
        return estado

    if estado.pdf_texto_extraido is None:
        estado.erros.append(
            "build_prompt_context_natural: pdf_texto_extraido ausente no estado. "
            "Verifique se o nó extract_pdf_text executou com sucesso."
        )
        return estado

    contexto = montar_contexto_natural(estado.narrativa_bpmn, estado.pdf_texto_extraido)
    estado.prompt_usado_natural = contexto
    logger.info("build_prompt_context_natural: contexto montado — %d chars", len(contexto))

    saida_dir = Path("saidas/intermediarios")
    saida_dir.mkdir(parents=True, exist_ok=True)
    saida_path = saida_dir / "prompt_usado_natural.txt"
    try:
        saida_path.write_text(contexto, encoding="utf-8")
        estado.artefatos["prompt_usado_natural"] = str(saida_path)
        logger.info("prompt_usado_natural.txt salvo em %s", saida_path)
    except OSError as exc:
        estado.avisos.append(
            f"build_prompt_context_natural: não foi possível salvar prompt — {exc}"
        )

    return estado
