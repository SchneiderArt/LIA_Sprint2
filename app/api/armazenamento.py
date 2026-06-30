"""
Caminhos e armazenamento dos artefatos da API.

A API isola cada execução em ``saidas/<run_id>/``: os arquivos enviados ficam em
``entradas/`` e os artefatos produzidos pelo pipeline são copiados para a raiz da
pasta da execução. Assim, duas chamadas à API nunca sobrescrevem os resultados
uma da outra.

Observação: o nó ``render_outputs`` do projeto grava em ``saidas/`` (global).
Aqui não alteramos esse nó — apenas realocamos cópias por execução depois que o
pipeline termina. (Se no futuro o render passar a gravar usando ``estado.run_id``,
esta realocação deixa de ser necessária.)

Os caminhos de entrada são RELATIVOS de propósito: o nó ``ingest_files`` rejeita
caminhos absolutos como proteção contra path traversal.
"""
from __future__ import annotations

import shutil
from pathlib import Path

PASTA_SAIDAS = Path("saidas")
NOME_BPMN = "processo.bpmn"
NOME_PDF = "descritivo.pdf"


def pasta_da_execucao(run_id: str) -> Path:
    """Pasta isolada da execução: ``saidas/<run_id>/`` (relativa)."""
    return PASTA_SAIDAS / run_id


def pasta_entradas(run_id: str) -> Path:
    """Onde os arquivos enviados são salvos: ``saidas/<run_id>/entradas/``."""
    return pasta_da_execucao(run_id) / "entradas"


def salvar_entradas(
    run_id: str, conteudo_bpmn: bytes, conteudo_pdf: bytes
) -> tuple[str, str]:
    """
    Salva os arquivos enviados na pasta da execução, com nome controlado (nunca
    o nome enviado pelo usuário), e devolve os caminhos RELATIVOS (str) do BPMN e
    do PDF, prontos para passar ao pipeline.
    """
    entradas = pasta_entradas(run_id)
    entradas.mkdir(parents=True, exist_ok=True)

    caminho_bpmn = entradas / NOME_BPMN
    caminho_pdf = entradas / NOME_PDF
    caminho_bpmn.write_bytes(conteudo_bpmn)
    caminho_pdf.write_bytes(conteudo_pdf)

    return str(caminho_bpmn), str(caminho_pdf)


def realocar_artefatos(run_id: str, artefatos: dict[str, str]) -> dict[str, str]:
    """
    Copia para ``saidas/<run_id>/`` os artefatos que são arquivos reais e devolve
    o mapa ``{chave: caminho_isolado}``. Entradas que não apontam para um arquivo
    (ex.: 'bpmn_nome', que guarda só o nome) são ignoradas.
    """
    destino = pasta_da_execucao(run_id)
    destino.mkdir(parents=True, exist_ok=True)

    resultado: dict[str, str] = {}
    for chave, valor in artefatos.items():
        origem = Path(valor)
        if not origem.is_file():
            continue
        alvo = destino / origem.name
        if origem.resolve() != alvo.resolve():
            shutil.copyfile(origem, alvo)
        resultado[chave] = str(alvo)
    return resultado
