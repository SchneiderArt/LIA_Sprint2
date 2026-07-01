"""
Nó LangGraph: bpmn_to_natural_language
Entrega 1 — Sprint 2 (responsabilidade: Davi Gaborim)

Transforma o XML normalizado (estado.bpmn_normalizado_xml) em narrativa
administrativa, usando o prompt prompts/bpmn_to_natural_language.md e o
mesmo cliente OpenRouter (app/openrouter.py) usado pelo restante do grafo.
Salva o resultado em /saidas/intermediarios/narrativa_bpmn.txt.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.openrouter import chamar_llm
from app.prompts import carregar_prompt
from app.schemas import EstadoGrafo

logger = logging.getLogger(__name__)


def montar_prompt_narrativa(xml_normalizado: str) -> str:
    instrucao = carregar_prompt("bpmn_to_natural_language")
    return f"{instrucao}\n\n[BPMN_XML]\n{xml_normalizado}\n[/BPMN_XML]"


def bpmn_to_natural_language(estado: EstadoGrafo) -> EstadoGrafo:
    """
    Nó LangGraph: chama o LLM via OpenRouter para narrar o XML normalizado.
    Popula estado.narrativa_bpmn e salva o intermediário em disco.
    """
    if not estado.bpmn_normalizado_xml:
        estado.erros.append(
            "bpmn_to_natural_language: bpmn_normalizado_xml ausente no estado. "
            "Verifique se o nó parse_bpmn_xml executou com sucesso."
        )
        return estado

    try:
        system_prompt = carregar_prompt("system_automation_analyst")
        user_prompt = montar_prompt_narrativa(estado.bpmn_normalizado_xml)
    except (KeyError, FileNotFoundError) as exc:
        estado.erros.append(f"bpmn_to_natural_language: erro ao carregar prompt — {exc}")
        return estado

    try:
        narrativa = chamar_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperatura=0.2,
            max_tokens=8000,
        )
    except ValueError as exc:
        estado.erros.append(f"bpmn_to_natural_language: erro na chamada LLM — {exc}")
        return estado

    if not narrativa.strip():
        estado.erros.append("bpmn_to_natural_language: o LLM retornou narrativa vazia.")
        return estado

    estado.narrativa_bpmn = narrativa

    saida_dir = Path("saidas/intermediarios")
    saida_dir.mkdir(parents=True, exist_ok=True)
    saida_path = saida_dir / "narrativa_bpmn.txt"
    try:
        saida_path.write_text(narrativa, encoding="utf-8")
        estado.artefatos["narrativa_bpmn"] = str(saida_path)
        logger.info("narrativa_bpmn.txt salvo em %s (%d chars)", saida_path, len(narrativa))
    except OSError as exc:
        estado.avisos.append(f"bpmn_to_natural_language: não foi possível salvar intermediário — {exc}")

    return estado
