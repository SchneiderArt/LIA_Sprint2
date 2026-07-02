"""
Nó LangGraph: extract_pdf_text
Entrega 1 — Sprint 2 (responsabilidade: Davi Gaborim)

Extrai o texto do PDF descritivo do processo com PyMuPDF, organizado por
página, e salva em /saidas/intermediarios/pdf_texto_extraido.txt.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import fitz  # PyMuPDF

from app.schemas import EstadoGrafo
from app.utils import config

logger = logging.getLogger(__name__)

# Abaixo de quantos caracteres uma página é considerada "vazia"/sem texto
# útil (provável página só com imagem/tabela escaneada — sem OCR nesta
# sprint, só geramos aviso). Ajuste se os PDFs reais tiverem páginas
# legitimamente curtas (ex: capas) sendo sinalizadas à toa.
LIMIAR_PAGINA_VAZIA = 20


def extrair_texto_pdf(caminho_pdf: str | Path) -> tuple[str, list[str]]:
    """
    Lê um .pdf e retorna (texto_completo, avisos).
    O texto é organizado por página com marcadores "--- Página N ---".
    """
    caminho = Path(caminho_pdf)
    avisos: list[str] = []

    try:
        documento = fitz.open(str(caminho))
    except Exception as exc:
        raise ValueError(f"Arquivo PDF inválido ou corrompido: {exc}") from exc

    if documento.page_count == 0:
        documento.close()
        raise ValueError("PDF sem páginas.")

    blocos: list[str] = []
    paginas_vazias = 0
    for i, pagina in enumerate(documento, start=1):
        texto = pagina.get_text("text").strip()
        if len(texto) < LIMIAR_PAGINA_VAZIA:
            paginas_vazias += 1
        blocos.append(f"--- Página {i} ---\n{texto}")

    documento.close()

    if paginas_vazias:
        avisos.append(
            f"extract_pdf_text: {paginas_vazias} página(s) com pouco ou "
            "nenhum texto extraído (possível necessidade de OCR)."
        )

    texto_completo = "\n\n".join(blocos)
    if not texto_completo.strip():
        avisos.append("extract_pdf_text: nenhum texto extraído do PDF.")

    return texto_completo, avisos


def extract_pdf_text(estado: EstadoGrafo) -> EstadoGrafo:
    """
    Nó LangGraph: extrai o texto do PDF e popula estado.pdf_texto_extraido.
    Salva o intermediário em /saidas/intermediarios/pdf_texto_extraido.txt.
    """
    caminho = estado.caminho_pdf
    if not caminho:
        estado.erros.append("extract_pdf_text: caminho_pdf não definido no estado.")
        return estado
    if not os.path.isfile(caminho):
        estado.erros.append(f"extract_pdf_text: arquivo não encontrado — {caminho}")
        return estado

    try:
        texto, avisos = extrair_texto_pdf(caminho)
    except ValueError as exc:
        estado.erros.append(f"extract_pdf_text: erro de extração — {exc}")
        return estado
    except Exception as exc:
        estado.erros.append(f"extract_pdf_text: erro inesperado — {exc}")
        return estado

    estado.avisos.extend(avisos)

    saida_dir = config.garantir(config.pasta_intermediarios(estado.run_id, config.NATURAL))
    saida_path = saida_dir / "pdf_texto_extraido.txt"
    try:
        saida_path.write_text(texto, encoding="utf-8")
        estado.artefatos["pdf_texto_extraido"] = str(saida_path)
        logger.info("pdf_texto_extraido.txt salvo em %s (%d chars)", saida_path, len(texto))
    except OSError as exc:
        estado.avisos.append(f"extract_pdf_text: não foi possível salvar intermediário — {exc}")

    estado.pdf_texto_extraido = texto
    return estado
