"""
Grafo LangGraph — Sprint 2
app/graph.py

Três pipelines disponíveis via parâmetro ``pipeline``:

  pipeline="json"    — Entrega 2: BPMN e PDF → JSON → candidatos → render_outputs
  pipeline="natural" — Entrega 1: BPMN → narrativa, PDF → texto → candidatos → render_outputs_natural
  pipeline="both"    — Executa os dois grafos e combina via render_outputs_both

Fluxo Entrega 2 (JSON):
  START → ingest_files → parse_bpmn_to_json → extract_pdf_to_json →
  build_prompt_context → generate_candidates → critic_review →
  validate_schema ⇄ repair_output → render_outputs → END

Fluxo Entrega 1 (Linguagem Natural):
  START → ingest_files → parse_bpmn_xml → extract_pdf_text →
  bpmn_to_natural_language → build_prompt_context_natural →
  generate_candidates → critic_review →
  validate_schema ⇄ repair_output → render_outputs_natural → END
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from typing import Literal

from app.nodes.bpmn_to_natural_language import bpmn_to_natural_language
from app.nodes.build_prompt_context import build_prompt_context
from app.nodes.build_prompt_context_natural import build_prompt_context_natural
from app.nodes.critic_review_node import critic_review_node
from app.nodes.extract_pdf_text import extract_pdf_text
from app.nodes.extract_pdf_to_json import extract_pdf_to_json
from app.nodes.generate_candidates import generate_candidates
from app.nodes.ingest_files import ingest_files
from app.nodes.parse_bpmn_to_json import parse_bpmn_to_json
from app.nodes.parse_bpmn_xml import parse_bpmn_xml
from app.nodes.render_outputs import render_outputs
from app.nodes.render_outputs_natural import render_outputs_natural
from app.nodes.render_outputs_both import render_outputs_both
from app.nodes.validate_schema import repair_output, validate_schema
from app.schemas import EstadoGrafo

load_dotenv()

logger = logging.getLogger(__name__)

MAX_REPAIR_ATTEMPTS = int(os.getenv("MAX_REPAIR_ATTEMPTS", 3))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_erros(state: dict) -> list:
    return state.get("erros", [])

def _get_erros_validacao(state: dict) -> list:
    return state.get("erros_validacao", [])

def _get_tentativas(state: dict) -> int:
    return state.get("tentativas_reparo", 0)


# ---------------------------------------------------------------------------
# Roteamento — Entrega 2 (JSON)
# ---------------------------------------------------------------------------

def _rota_apos_ingest(state: dict) -> Literal["parse_bpmn_to_json", "__end__"]:
    return END if _get_erros(state) else "parse_bpmn_to_json"

def _rota_apos_parse_bpmn(state: dict) -> Literal["extract_pdf_to_json", "__end__"]:
    return END if _get_erros(state) else "extract_pdf_to_json"

def _rota_apos_extract_pdf(state: dict) -> Literal["build_prompt_context", "__end__"]:
    return END if _get_erros(state) else "build_prompt_context"

def _rota_apos_build_context(state: dict) -> Literal["generate_candidates", "__end__"]:
    return END if _get_erros(state) else "generate_candidates"


# ---------------------------------------------------------------------------
# Roteamento — Entrega 1 (Linguagem Natural)
# ---------------------------------------------------------------------------

def _rota_apos_ingest_natural(state: dict) -> Literal["parse_bpmn_xml", "__end__"]:
    return END if _get_erros(state) else "parse_bpmn_xml"

def _rota_apos_parse_bpmn_xml(state: dict) -> Literal["extract_pdf_text", "__end__"]:
    return END if _get_erros(state) else "extract_pdf_text"

def _rota_apos_extract_pdf_text(state: dict) -> Literal["bpmn_to_natural_language", "__end__"]:
    return END if _get_erros(state) else "bpmn_to_natural_language"

def _rota_apos_bpmn_to_nl(state: dict) -> Literal["build_prompt_context_natural", "__end__"]:
    return END if _get_erros(state) else "build_prompt_context_natural"

def _rota_apos_build_context_natural(state: dict) -> Literal["generate_candidates", "__end__"]:
    return END if _get_erros(state) else "generate_candidates"


# ---------------------------------------------------------------------------
# Roteamento — compartilhado (generate → render)
# ---------------------------------------------------------------------------

def _rota_apos_generate(state: dict) -> Literal["critic_review", "__end__"]:
    return END if _get_erros(state) else "critic_review"

def _rota_apos_critic(state: dict) -> Literal["validate_schema", "__end__"]:
    return END if _get_erros(state) else "validate_schema"

def _rota_apos_validate_json(
    state: dict,
) -> Literal["render_outputs", "repair_output", "__end__"]:
    return _rota_validate(state, destino_ok="render_outputs")

def _rota_apos_validate_natural(
    state: dict,
) -> Literal["render_outputs_natural", "repair_output", "__end__"]:
    return _rota_validate(state, destino_ok="render_outputs_natural")

def _rota_validate(state: dict, destino_ok: str) -> str:
    erros           = _get_erros(state)
    erros_validacao = _get_erros_validacao(state)
    tentativas      = _get_tentativas(state)

    if erros:
        return END
    if not erros_validacao:
        return destino_ok
    if tentativas < MAX_REPAIR_ATTEMPTS:
        logger.warning(
            "validate_schema falhou (%d/%d) — acionando repair_output.",
            tentativas, MAX_REPAIR_ATTEMPTS,
        )
        return "repair_output"
    logger.error("Limite de %d tentativas de reparo atingido.", MAX_REPAIR_ATTEMPTS)
    return END

def _rota_apos_repair(state: dict) -> Literal["validate_schema", "__end__"]:
    return END if _get_erros(state) else "validate_schema"

def _rota_apos_render(state: dict) -> Literal["__end__"]:
    return END


# ---------------------------------------------------------------------------
# Wrapper EstadoGrafo ↔ dict
# ---------------------------------------------------------------------------

def _nó(func):
    def wrapper(state_dict: dict) -> dict:
        estado = EstadoGrafo.model_validate(state_dict)
        return func(estado).model_dump()
    wrapper.__name__ = func.__name__
    return wrapper


# ---------------------------------------------------------------------------
# Nós compartilhados entre os dois grafos
# ---------------------------------------------------------------------------

_NOS_COMPARTILHADOS = {
    "generate_candidates": _nó(generate_candidates),
    "critic_review":       _nó(critic_review_node),
    "repair_output":       _nó(repair_output),
}


# ---------------------------------------------------------------------------
# Construção dos grafos
# ---------------------------------------------------------------------------

def construir_grafo_json() -> StateGraph:
    """Entrega 2 — pipeline JSON."""
    builder = StateGraph(dict)

    builder.add_node("ingest_files",         _nó(ingest_files))
    builder.add_node("parse_bpmn_to_json",   _nó(parse_bpmn_to_json))
    builder.add_node("extract_pdf_to_json",  _nó(extract_pdf_to_json))
    builder.add_node("build_prompt_context", _nó(build_prompt_context))
    builder.add_node("validate_schema",      _nó(validate_schema))
    builder.add_node("render_outputs",       _nó(render_outputs))
    for nome, func in _NOS_COMPARTILHADOS.items():
        builder.add_node(nome, func)

    builder.add_edge(START, "ingest_files")
    builder.add_conditional_edges("ingest_files",         _rota_apos_ingest)
    builder.add_conditional_edges("parse_bpmn_to_json",   _rota_apos_parse_bpmn)
    builder.add_conditional_edges("extract_pdf_to_json",  _rota_apos_extract_pdf)
    builder.add_conditional_edges("build_prompt_context", _rota_apos_build_context)
    builder.add_conditional_edges("generate_candidates",  _rota_apos_generate)
    builder.add_conditional_edges("critic_review",        _rota_apos_critic)
    builder.add_conditional_edges("validate_schema",      _rota_apos_validate_json)
    builder.add_conditional_edges("repair_output",        _rota_apos_repair)
    builder.add_conditional_edges("render_outputs",       _rota_apos_render)

    return builder.compile()


def construir_grafo_natural() -> StateGraph:
    """Entrega 1 — pipeline de linguagem natural."""
    builder = StateGraph(dict)

    builder.add_node("ingest_files",                 _nó(ingest_files))
    builder.add_node("parse_bpmn_xml",               _nó(parse_bpmn_xml))
    builder.add_node("extract_pdf_text",             _nó(extract_pdf_text))
    builder.add_node("bpmn_to_natural_language",     _nó(bpmn_to_natural_language))
    builder.add_node("build_prompt_context_natural", _nó(build_prompt_context_natural))
    builder.add_node("validate_schema",              _nó(validate_schema))
    builder.add_node("render_outputs_natural",       _nó(render_outputs_natural))
    for nome, func in _NOS_COMPARTILHADOS.items():
        builder.add_node(nome, func)

    builder.add_edge(START, "ingest_files")
    builder.add_conditional_edges("ingest_files",                 _rota_apos_ingest_natural)
    builder.add_conditional_edges("parse_bpmn_xml",               _rota_apos_parse_bpmn_xml)
    builder.add_conditional_edges("extract_pdf_text",             _rota_apos_extract_pdf_text)
    builder.add_conditional_edges("bpmn_to_natural_language",     _rota_apos_bpmn_to_nl)
    builder.add_conditional_edges("build_prompt_context_natural", _rota_apos_build_context_natural)
    builder.add_conditional_edges("generate_candidates",          _rota_apos_generate)
    builder.add_conditional_edges("critic_review",                _rota_apos_critic)
    builder.add_conditional_edges("validate_schema",              _rota_apos_validate_natural)
    builder.add_conditional_edges("repair_output",                _rota_apos_repair)
    builder.add_conditional_edges("render_outputs_natural",       _rota_apos_render)

    return builder.compile()


def construir_grafo() -> StateGraph:
    """Alias para compatibilidade com código legado."""
    return construir_grafo_json()


# ---------------------------------------------------------------------------
# Execução do pipeline
# ---------------------------------------------------------------------------

def executar_pipeline(
    caminho_bpmn: str,
    caminho_pdf: str,
    run_id: str,
    pipeline: str = "json",
) -> EstadoGrafo:
    """
    Executa o pipeline selecionado.

    Args:
        caminho_bpmn: caminho para o arquivo .bpmn
        caminho_pdf:  caminho para o arquivo .pdf
        run_id:       identificador único da execução
        pipeline:     "json" (Entrega 2), "natural" (Entrega 1) ou "both"

    Returns:
        EstadoGrafo com todos os resultados, artefatos, avisos e erros.
    """
    logger.info(
        "Iniciando pipeline | run_id=%s | pipeline=%s | BPMN=%s | PDF=%s",
        run_id, pipeline, caminho_bpmn, caminho_pdf,
    )

    if pipeline == "natural":
        grafo = construir_grafo_natural()
        resultado = grafo.invoke(
            EstadoGrafo(
                run_id=run_id,
                caminho_bpmn=caminho_bpmn,
                caminho_pdf=caminho_pdf,
            ).model_dump()
        )
        return EstadoGrafo.model_validate(resultado)

    if pipeline == "both":
        grafo_json    = construir_grafo_json()
        grafo_natural = construir_grafo_natural()

        # Cada grafo usa nome_saida próprio para não sobrescrever o do outro
        estado_json = EstadoGrafo.model_validate(
            grafo_json.invoke(
                EstadoGrafo(
                    run_id=run_id,
                    caminho_bpmn=caminho_bpmn,
                    caminho_pdf=caminho_pdf,
                    nome_saida="documento_final_json",
                ).model_dump()
            )
        )
        estado_natural = EstadoGrafo.model_validate(
            grafo_natural.invoke(
                EstadoGrafo(
                    run_id=run_id + "-natural",
                    caminho_bpmn=caminho_bpmn,
                    caminho_pdf=caminho_pdf,
                    nome_saida="documento_final_natural",
                ).model_dump()
            )
        )

        # Gera o documento comparativo unificado
        render_outputs_both(estado_json, estado_natural)

        # Estado final consolida metadados dos dois pipelines
        estado_json.avisos  += estado_natural.avisos
        estado_json.erros   += estado_natural.erros
        estado_json.artefatos.update(estado_natural.artefatos)
        estado_json.artefatos["documento_final_md"]  = str(Path("saidas") / "documento_final.md")
        estado_json.artefatos["documento_final_pdf"] = str(Path("saidas") / "documento_final.pdf")
        estado_json.artefatos["auditoria_json"]      = str(Path("saidas") / "auditoria_both.json")
        # Preserva intermediários da Entrega 1 no estado final
        estado_json.bpmn_normalizado_xml = estado_natural.bpmn_normalizado_xml
        estado_json.pdf_texto_extraido   = estado_natural.pdf_texto_extraido
        estado_json.narrativa_bpmn       = estado_natural.narrativa_bpmn
        estado_json.prompt_usado_natural = estado_natural.prompt_usado_natural

        logger.info(
            "Pipeline 'both' concluído | run_id=%s | natural=%d | json=%d candidatos",
            run_id, len(estado_natural.candidatos), len(estado_json.candidatos),
        )
        return estado_json

    # Padrão: pipeline "json" (Entrega 2)
    grafo = construir_grafo_json()
    resultado = grafo.invoke(
        EstadoGrafo(
            run_id=run_id,
            caminho_bpmn=caminho_bpmn,
            caminho_pdf=caminho_pdf,
        ).model_dump()
    )
    return EstadoGrafo.model_validate(resultado)
