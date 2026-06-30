"""
Regras de segurança aplicadas aos arquivos recebidos pela API.

A API é a porta de entrada de arquivos vindos de fora, e quem envia pode mandar
qualquer coisa. Estas funções garantem que só entrem arquivos do tipo certo,
dentro do tamanho permitido, e que o ``.bpmn`` (que é um XML) seja seguro de ler.
O conteúdo enviado é sempre tratado como dado — nunca é executado.

O limite de tamanho usa a mesma variável de ambiente do nó ``ingest_files``
(``MAX_FILE_SIZE_BYTES``), para a API e o grafo concordarem.
"""
from __future__ import annotations

import os

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring as _analisar_xml
from fastapi import HTTPException, UploadFile

# Mesmo limite usado por app/nodes/ingest_files.py (padrão 10 MB).
TAMANHO_MAXIMO_BYTES: int = int(os.getenv("MAX_FILE_SIZE_BYTES", 10 * 1024 * 1024))
# Lemos o upload em blocos para abortar cedo, sem carregar tudo na memória.
_TAMANHO_BLOCO: int = 1 * 1024 * 1024  # 1 MB


async def ler_upload_limitado(arquivo: UploadFile, extensao_esperada: str) -> bytes:
    """
    Lê um arquivo enviado e devolve seu conteúdo em bytes, com proteção.

    Faz, nesta ordem:
      1. confere a extensão (``.bpmn`` ou ``.pdf``);
      2. lê em blocos, interrompendo assim que passar do tamanho máximo;
      3. recusa arquivo vazio.

    Levanta ``HTTPException`` (400 ou 413) quando algo está fora das regras.
    """
    nome = (arquivo.filename or "").lower()
    if not nome.endswith(extensao_esperada):
        raise HTTPException(
            status_code=400,
            detail=f"Arquivo inválido: esperado um arquivo {extensao_esperada}.",
        )

    conteudo = bytearray()
    while bloco := await arquivo.read(_TAMANHO_BLOCO):
        conteudo.extend(bloco)
        if len(conteudo) > TAMANHO_MAXIMO_BYTES:
            limite_mb = TAMANHO_MAXIMO_BYTES // (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"Arquivo excede o tamanho máximo de {limite_mb} MB.",
            )

    if not conteudo:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    return bytes(conteudo)


def validar_xml_seguro(conteudo_bpmn: bytes) -> None:
    """
    Confere que o ``.bpmn`` é um XML bem-formado e seguro de processar.

    Usa ``defusedxml``: além de detectar XML quebrado, bloqueia os ataques
    clássicos de XML — entidades externas (XXE) e expansão de entidades
    ("billion laughs") — que um leitor de XML comum aceitaria. O conteúdo é
    apenas analisado, nunca executado.

    Levanta ``HTTPException(400)`` se o XML for inválido ou contiver construções
    não permitidas. Não retorna nada quando o arquivo está OK.
    """
    try:
        _analisar_xml(conteudo_bpmn)
    except DefusedXmlException:
        raise HTTPException(
            status_code=400,
            detail="O arquivo .bpmn contém construções XML não permitidas (entidades/DTD externas).",
        )
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="O arquivo .bpmn não é um XML válido.",
        )
