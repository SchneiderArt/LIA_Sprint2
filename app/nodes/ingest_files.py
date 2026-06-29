"""
Nó LangGraph: ingest_files
Etapa 6 — Sprint 2, Entrega 2

Responsabilidades (conforme documento da sprint, seções 6.1, 7.1 e 8.2):
  - Receber, validar e registrar metadados dos arquivos de entrada
  - Garantir que há exatamente um BPMN e um PDF (seção 8.1)
  - Validar extensão, tamanho e consistência básica (seção 6.1, passo 2)
  - Bloquear path traversal e nomes absolutos (seção 8.2)
  - Nunca executar conteúdo enviado pelo usuário (seção 8.2)
  - Registrar warnings no estado
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from app.schemas import EstadoGrafo

logger = logging.getLogger(__name__)

# Tamanho máximo por arquivo (padrão 10 MB; sobrescrito por .env)
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_BYTES", 10 * 1024 * 1024))


def _checar_path_traversal(caminho: str) -> bool:
    """
    Retorna True se o caminho for suspeito de path traversal.
    Bloqueia: caminhos absolutos, sequências '..', nomes ocultos.
    Conforme seção 8.2 do documento.
    """
    p = Path(caminho)
    if p.is_absolute():
        return True
    partes = p.parts
    if ".." in partes:
        return True
    # Arquivos ocultos (começam com ponto)
    if any(parte.startswith(".") for parte in partes):
        return True
    return False


def _validar_arquivo(caminho: str, extensao_esperada: str, label: str) -> list[str]:
    """
    Valida um arquivo quanto a: existência, path traversal, extensão e tamanho.
    Retorna lista de erros (vazia se tudo OK).
    """
    erros: list[str] = []

    if _checar_path_traversal(caminho):
        erros.append(
            f"ingest_files: {label} — caminho suspeito (path traversal ou absoluto): {caminho}"
        )
        return erros  # Não continuar validando caminho inseguro

    if not os.path.isfile(caminho):
        erros.append(f"ingest_files: {label} — arquivo não encontrado: {caminho}")
        return erros

    # Validar extensão
    sufixo = Path(caminho).suffix.lower()
    if sufixo != extensao_esperada.lower():
        erros.append(
            f"ingest_files: {label} — extensão inválida '{sufixo}', "
            f"esperado '{extensao_esperada}'"
        )

    # Validar tamanho
    tamanho = os.path.getsize(caminho)
    if tamanho == 0:
        erros.append(f"ingest_files: {label} — arquivo vazio: {caminho}")
    elif tamanho > MAX_FILE_SIZE:
        erros.append(
            f"ingest_files: {label} — arquivo excede limite de "
            f"{MAX_FILE_SIZE // (1024*1024)} MB: {tamanho} bytes"
        )

    return erros


def ingest_files(estado: EstadoGrafo) -> EstadoGrafo:
    """
    Nó LangGraph: valida os arquivos de entrada e registra metadados no estado.

    Garante que há exatamente um BPMN e um PDF (seção 8.1).
    Valida extensão, tamanho, path traversal e existência (seções 6.1 e 8.2).
    Registra erros em estado.erros e avisos em estado.avisos.
    """
    erros_acumulados: list[str] = []

    # --- Verificar que os caminhos foram definidos no estado ---
    if not estado.caminho_bpmn:
        erros_acumulados.append("ingest_files: caminho_bpmn não definido no estado.")
    if not estado.caminho_pdf:
        erros_acumulados.append("ingest_files: caminho_pdf não definido no estado.")

    if erros_acumulados:
        estado.erros.extend(erros_acumulados)
        return estado

    # --- Validar BPMN ---
    erros_bpmn = _validar_arquivo(estado.caminho_bpmn, ".bpmn", "BPMN")
    erros_acumulados.extend(erros_bpmn)

    # --- Validar PDF ---
    erros_pdf = _validar_arquivo(estado.caminho_pdf, ".pdf", "PDF")
    erros_acumulados.extend(erros_pdf)

    if erros_acumulados:
        estado.erros.extend(erros_acumulados)
        return estado

    # --- Registrar metadados no estado como avisos informativos ---
    bpmn_path = Path(estado.caminho_bpmn)
    pdf_path  = Path(estado.caminho_pdf)

    bpmn_kb = os.path.getsize(estado.caminho_bpmn) // 1024
    pdf_kb  = os.path.getsize(estado.caminho_pdf) // 1024

    logger.info(
        "ingest_files: BPMN=%s (%d KB) | PDF=%s (%d KB)",
        bpmn_path.name, bpmn_kb, pdf_path.name, pdf_kb,
    )

    estado.artefatos["bpmn_nome"] = bpmn_path.name
    estado.artefatos["pdf_nome"]  = pdf_path.name

    return estado
