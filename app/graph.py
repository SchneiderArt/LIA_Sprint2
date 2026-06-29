"""
Grafo LangGraph — Sprint 2, Entrega 2
app/graph.py

Estrutura do grafo (conforme documento da sprint, seções 4, 7.1 e 10):

  START
    │
    ▼
  ingest_files          ← valida arquivos, bloqueia path traversal
    │
    ▼
  parse_bpmn_to_json    ← BPMN → ProcessoJSON + bpmn_estruturado.json
    │
    ▼
  extract_pdf_to_json   ← PDF  → DocumentoPDFJSON + pdf_estruturado.json
    │
    ▼
  build_prompt_context  ← combina os dois JSONs + salva prompt_usado.txt
    │
    ▼
  generate_candidates   ← LLM gera automações candidatas (OpenRouter)
    │
    ▼
  critic_review         ← LLM verifica lacunas, generalizações, duplicidades
    │
    ▼
  validate_schema       ── OK ──► render_outputs ──► END
    │                                    ▲
    │ ERRO (< MAX_REPAIR_ATTEMPTS)       │
    ▼                                   │
  repair_output ─────────────────────────┘
    │
    │ ERRO (≥ MAX_REPAIR_ATTEMPTS)
    ▼
    END (com erros registrados)

Propriedades obrigatórias (seção 4, camada 5):
  - Estado tipado: EstadoGrafo (Pydantic BaseModel)
  - Tratamento de erro entre nós: verificado em cada nó pelo campo estado.erros
  - Nó de reparo: repair_output → validate_schema (loop controlado)
"""

from __future__ import annotations

import logging
import os
from typing import Literal

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from app.nodes.build_prompt_context import build_prompt_context
from app.nodes.critic_review_node import critic_review_node
from app.nodes.extract_pdf_to_json import extract_pdf_to_json
from app.nodes.generate_candidates import generate_candidates
from app.nodes.ingest_files import ingest_files
from app.nodes.parse_bpmn_to_json import parse_bpmn_to_json
from app.nodes.render_outputs import render_outputs
from app.nodes.validate_schema import repair_output, validate_schema
from app.schemas import EstadoGrafo

# Carregar variáveis de ambiente do .env (seção 11: "Execução Docker e .env")
load_dotenv()

logger = logging.getLogger(__name__)

MAX_REPAIR_ATTEMPTS = int(os.getenv("MAX_REPAIR_ATTEMPTS", 3))


# ---------------------------------------------------------------------------
# Funções de roteamento condicional
# ---------------------------------------------------------------------------

def _get_erros(state: dict) -> list:
    """Helper: extrai lista de erros do estado (dict nativo do LangGraph)."""
    return state.get("erros", [])


def _get_erros_validacao(state: dict) -> list:
    return state.get("erros_validacao", [])


def _get_tentativas(state: dict) -> int:
    return state.get("tentativas_reparo", 0)


def _rota_apos_ingest(state: dict) -> Literal["parse_bpmn_to_json", "__end__"]:
    """Para o grafo se ingest_files registrou erros."""
    erros = _get_erros(state)
    if erros:
        logger.error("Grafo interrompido após ingest_files: %s", erros)
        return END
    return "parse_bpmn_to_json"


def _rota_apos_parse_bpmn(state: dict) -> Literal["extract_pdf_to_json", "__end__"]:
    """Para o grafo se parse_bpmn_to_json registrou erros."""
    erros = _get_erros(state)
    if erros:
        logger.error("Grafo interrompido após parse_bpmn_to_json: %s", erros)
        return END
    return "extract_pdf_to_json"


def _rota_apos_extract_pdf(state: dict) -> Literal["build_prompt_context", "__end__"]:
    """Para o grafo se extract_pdf_to_json registrou erros."""
    erros = _get_erros(state)
    if erros:
        logger.error("Grafo interrompido após extract_pdf_to_json: %s", erros)
        return END
    return "build_prompt_context"


def _rota_apos_build_context(state: dict) -> Literal["generate_candidates", "__end__"]:
    """Para o grafo se build_prompt_context registrou erros."""
    erros = _get_erros(state)
    if erros:
        logger.error("Grafo interrompido após build_prompt_context: %s", erros)
        return END
    return "generate_candidates"


def _rota_apos_generate(state: dict) -> Literal["critic_review", "__end__"]:
    """Para o grafo se generate_candidates registrou erros."""
    erros = _get_erros(state)
    if erros:
        logger.error("Grafo interrompido após generate_candidates: %s", erros)
        return END
    return "critic_review"


def _rota_apos_critic(state: dict) -> Literal["validate_schema", "__end__"]:
    """Prossegue para validate_schema; para só em erros graves."""
    erros = _get_erros(state)
    if erros:
        logger.error("Grafo interrompido após critic_review: %s", erros)
        return END
    return "validate_schema"


def _rota_apos_validate(
    state: dict,
) -> Literal["render_outputs", "repair_output", "__end__"]:
    """
    Roteamento central do loop de validação/reparo (seção 10):
      - Sem erros de validação → render_outputs
      - Com erros E tentativas restantes → repair_output
      - Com erros E sem tentativas → END (com erros registrados)
    """
    erros            = _get_erros(state)
    erros_validacao  = _get_erros_validacao(state)
    tentativas       = _get_tentativas(state)

    if erros:
        logger.error("Grafo interrompido após validate_schema: %s", erros)
        return END

    if not erros_validacao:
        return "render_outputs"

    if tentativas < MAX_REPAIR_ATTEMPTS:
        logger.warning(
            "validate_schema falhou (%d/%d tentativas) — acionando repair_output.",
            tentativas, MAX_REPAIR_ATTEMPTS,
        )
        return "repair_output"

    logger.error("Limite de %d tentativas de reparo atingido.", MAX_REPAIR_ATTEMPTS)
    return END


def _rota_apos_repair(state: dict) -> Literal["validate_schema", "__end__"]:
    """Após reparo, sempre retorna para validate_schema (salvo erro grave)."""
    erros = _get_erros(state)
    if erros:
        logger.error("Grafo interrompido após repair_output: %s", erros)
        return END
    return "validate_schema"


def _rota_apos_render(state: dict) -> Literal["__end__"]:
    """Render sempre vai para END."""
    erros = _get_erros(state)
    if erros:
        logger.error("render_outputs finalizou com erros: %s", erros)
    return END


# ---------------------------------------------------------------------------
# Construção do grafo
# ---------------------------------------------------------------------------

def construir_grafo() -> StateGraph:
    """
    Constrói e retorna o grafo LangGraph compilado da Entrega 2.

    Nós organizados (seção 4, camada 5):
      ingest_files → parse_bpmn_to_json → extract_pdf_to_json →
      build_prompt_context → generate_candidates → critic_review →
      validate_schema ⇄ repair_output → render_outputs

    Estado tipado: EstadoGrafo (Pydantic BaseModel).
    Tratamento de erro: verificado por funções de roteamento após cada nó.
    """
    # Usar dict como estado do LangGraph (EstadoGrafo serializado)
    # O LangGraph opera sobre dicts; os nós recebem/devolvem EstadoGrafo
    builder = StateGraph(dict)

    # --- Registrar nós ---
    builder.add_node("ingest_files",          _nó(ingest_files))
    builder.add_node("parse_bpmn_to_json",    _nó(parse_bpmn_to_json))
    builder.add_node("extract_pdf_to_json",   _nó(extract_pdf_to_json))
    builder.add_node("build_prompt_context",  _nó(build_prompt_context))
    builder.add_node("generate_candidates",   _nó(generate_candidates))
    builder.add_node("critic_review",         _nó(critic_review_node))
    builder.add_node("validate_schema",       _nó(validate_schema))
    builder.add_node("repair_output",         _nó(repair_output))
    builder.add_node("render_outputs",        _nó(render_outputs))

    # --- Aresta de entrada ---
    builder.add_edge(START, "ingest_files")

    # --- Arestas condicionais ---
    builder.add_conditional_edges("ingest_files",         _rota_apos_ingest)
    builder.add_conditional_edges("parse_bpmn_to_json",   _rota_apos_parse_bpmn)
    builder.add_conditional_edges("extract_pdf_to_json",  _rota_apos_extract_pdf)
    builder.add_conditional_edges("build_prompt_context", _rota_apos_build_context)
    builder.add_conditional_edges("generate_candidates",  _rota_apos_generate)
    builder.add_conditional_edges("critic_review",        _rota_apos_critic)
    builder.add_conditional_edges("validate_schema",      _rota_apos_validate)
    builder.add_conditional_edges("repair_output",        _rota_apos_repair)
    builder.add_conditional_edges("render_outputs",       _rota_apos_render)

    return builder.compile()


def _nó(func):
    """
    Wrapper que adapta nós que recebem/devolvem EstadoGrafo para o
    formato dict que o StateGraph do LangGraph espera.
    """
    def wrapper(state_dict: dict) -> dict:
        estado = EstadoGrafo.model_validate(state_dict)
        estado_atualizado = func(estado)
        return estado_atualizado.model_dump()
    wrapper.__name__ = func.__name__
    return wrapper


# ---------------------------------------------------------------------------
# Função de execução do pipeline
# ---------------------------------------------------------------------------

def executar_pipeline(
    caminho_bpmn: str,
    caminho_pdf: str,
    run_id: str,
) -> EstadoGrafo:
    """
    Executa o pipeline completo da Entrega 2.

    Args:
        caminho_bpmn: caminho para o arquivo .bpmn
        caminho_pdf:  caminho para o arquivo .pdf
        run_id:       identificador único da execução

    Returns:
        EstadoGrafo com todos os resultados, artefatos, avisos e erros.
    """
    grafo = construir_grafo()

    estado_inicial = EstadoGrafo(
        run_id=run_id,
        caminho_bpmn=caminho_bpmn,
        caminho_pdf=caminho_pdf,
    )

    logger.info(
        "Iniciando pipeline | run_id=%s | BPMN=%s | PDF=%s",
        run_id, caminho_bpmn, caminho_pdf,
    )

    resultado_dict = grafo.invoke(estado_inicial.model_dump())
    return EstadoGrafo.model_validate(resultado_dict)
