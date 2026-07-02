"""
Armazenamento das ENTRADAS da API — camada fina sobre app/utils/config.py.

Os artefatos NÃO são mais relocados aqui: os nós do pipeline já gravam
run-scoped em ``saidas/<run_id>/artefatos/<abordagem>/`` via config. Esta camada
cuida apenas de salvar os arquivos enviados em ``saidas/<run_id>/entradas/`` com
nome controlado (nunca o nome enviado pelo usuário).
"""
from __future__ import annotations

from app.utils import config


def salvar_entradas(
    run_id: str, conteudo_bpmn: bytes, conteudo_pdf: bytes
) -> tuple[str, str]:
    """
    Salva os uploads em ``saidas/<run_id>/entradas/`` e devolve os caminhos
    RELATIVOS (str) do BPMN e do PDF, prontos para passar ao pipeline. Relativos
    de propósito: o nó ``ingest_files`` rejeita caminhos absolutos (path traversal).
    """
    config.criar_estrutura_execucao(run_id)  # cria a pasta e entradas/

    caminho_bpmn = config.caminho_bpmn_entrada(run_id)
    caminho_pdf = config.caminho_pdf_entrada(run_id)
    caminho_bpmn.write_bytes(conteudo_bpmn)
    caminho_pdf.write_bytes(conteudo_pdf)

    return str(caminho_bpmn), str(caminho_pdf)
