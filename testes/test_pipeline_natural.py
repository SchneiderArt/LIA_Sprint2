"""
Testes dos nós da Entrega 1 (linguagem natural) — responsabilidade Davi Gaborim.

Cobre parse_bpmn_xml, extract_pdf_text e build_prompt_context_natural com os
arquivos de exemplo em /entradas. bpmn_to_natural_language não é testado aqui
por depender do LLM (custo de créditos OpenRouter) — ver `_LLM_DISPONIVEL`.
"""

from __future__ import annotations

import glob
import os

import pytest

from app.nodes.build_prompt_context_natural import (
    build_prompt_context_natural,
    montar_contexto_natural,
)
from app.nodes.extract_pdf_text import extract_pdf_text, extrair_texto_pdf
from app.nodes.parse_bpmn_xml import normalizar_bpmn, parse_bpmn_xml
from app.schemas import EstadoGrafo

BPMNS_EXEMPLO = sorted(glob.glob("entradas/**/*.bpmn", recursive=True))
PDFS_EXEMPLO = sorted(glob.glob("entradas/**/*.pdf", recursive=True))

BPMN_TESTE = "entradas/Análise Processual e Tributária/Análise.bpmn"
PDF_TESTE = "entradas/Análise Processual e Tributária/analise-processual-e-tributaria.pdf"

# Roda os testes de LLM só se a chave estiver configurada de verdade.
_LLM_DISPONIVEL = bool(os.getenv("OPENROUTER_API_KEY", "")) and not os.getenv(
    "OPENROUTER_API_KEY", ""
).startswith("sk-or-v1-substitua")


# ---------------------------------------------------------------------------
# parse_bpmn_xml
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("caminho", BPMNS_EXEMPLO)
def test_normalizar_bpmn_nao_falha_em_nenhum_exemplo(caminho):
    xml, nome, avisos = normalizar_bpmn(caminho)
    assert xml.startswith("<?xml")
    assert nome
    assert "extensionElements" not in xml
    assert "BPMNShape" not in xml


def test_normalizar_bpmn_resolve_lanes_por_coordenada():
    xml, _, _ = normalizar_bpmn(BPMN_TESTE)
    assert "<flowNodeRef>" in xml


def test_normalizar_bpmn_arquivo_inexistente():
    with pytest.raises(Exception):
        normalizar_bpmn("entradas/nao-existe.bpmn")


def test_parse_bpmn_xml_node_popula_estado():
    estado = EstadoGrafo(run_id="teste-1", caminho_bpmn=BPMN_TESTE)
    estado = parse_bpmn_xml(estado)
    assert not estado.erros
    assert estado.bpmn_normalizado_xml
    assert "bpmn_normalizado" in estado.artefatos


def test_parse_bpmn_xml_node_caminho_ausente():
    estado = EstadoGrafo(run_id="teste-2")
    estado = parse_bpmn_xml(estado)
    assert estado.erros


# ---------------------------------------------------------------------------
# extract_pdf_text
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("caminho", PDFS_EXEMPLO)
def test_extrair_texto_pdf_nao_falha_em_nenhum_exemplo(caminho):
    texto, avisos = extrair_texto_pdf(caminho)
    assert texto.strip()
    assert "--- Página 1 ---" in texto


def test_extract_pdf_text_node_popula_estado():
    estado = EstadoGrafo(run_id="teste-3", caminho_pdf=PDF_TESTE)
    estado = extract_pdf_text(estado)
    assert not estado.erros
    assert estado.pdf_texto_extraido
    assert "pdf_texto_extraido" in estado.artefatos


def test_extract_pdf_text_node_caminho_ausente():
    estado = EstadoGrafo(run_id="teste-4")
    estado = extract_pdf_text(estado)
    assert estado.erros


# ---------------------------------------------------------------------------
# build_prompt_context_natural
# ---------------------------------------------------------------------------

def test_montar_contexto_natural():
    contexto = montar_contexto_natural("narrativa X", "texto Y")
    assert "[NARRATIVA_BPMN]" in contexto
    assert "[TEXTO_PDF]" in contexto
    assert "narrativa X" in contexto
    assert "texto Y" in contexto


def test_build_prompt_context_natural_sem_narrativa():
    estado = EstadoGrafo(run_id="teste-5", pdf_texto_extraido="texto")
    estado = build_prompt_context_natural(estado)
    assert estado.erros


def test_build_prompt_context_natural_node_completo():
    estado = EstadoGrafo(
        run_id="teste-6",
        narrativa_bpmn="narrativa de teste",
        pdf_texto_extraido="texto de teste",
    )
    estado = build_prompt_context_natural(estado)
    assert not estado.erros
    assert estado.prompt_usado_natural
    assert "prompt_usado_natural" in estado.artefatos


# ---------------------------------------------------------------------------
# Pipeline ponta a ponta (sem LLM): ingest -> parse_bpmn_xml -> extract_pdf_text
# ---------------------------------------------------------------------------

def test_pipeline_natural_sem_llm():
    estado = EstadoGrafo(run_id="teste-pipeline", caminho_bpmn=BPMN_TESTE, caminho_pdf=PDF_TESTE)
    estado = parse_bpmn_xml(estado)
    assert not estado.erros
    estado = extract_pdf_text(estado)
    assert not estado.erros
    assert estado.bpmn_normalizado_xml
    assert estado.pdf_texto_extraido


@pytest.mark.skipif(not _LLM_DISPONIVEL, reason="OPENROUTER_API_KEY não configurada")
def test_pipeline_natural_completo_com_llm():
    from app.nodes.bpmn_to_natural_language import bpmn_to_natural_language

    estado = EstadoGrafo(run_id="teste-pipeline-llm", caminho_bpmn=BPMN_TESTE, caminho_pdf=PDF_TESTE)
    estado = parse_bpmn_xml(estado)
    estado = extract_pdf_text(estado)
    estado = bpmn_to_natural_language(estado)
    assert not estado.erros
    estado = build_prompt_context_natural(estado)
    assert not estado.erros
    assert estado.prompt_usado_natural
