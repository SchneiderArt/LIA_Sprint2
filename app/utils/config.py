"""
Configuração centralizada de caminhos do projeto — Sprint 2.

Fonte única de verdade sobre onde cada coisa é gravada e lida. A API, a CLI e os
nós devem importar os caminhos daqui, em vez de montar strings soltas como
``Path("saidas")``.

Estrutura, isolada por execução (``run_id``) e separada por abordagem:

    saidas/<run_id>/
    ├── entradas/                    processo.bpmn, descritivo.pdf   (compartilhado)
    ├── intermediarios/
    │   ├── json/                    bpmn_estruturado.json, pdf_estruturado.json, ...
    │   └── natural/                 bpmn_normalizado.xml, narrativa_bpmn.txt, ...
    └── artefatos/
        ├── json/                    documento_final.md, documento_final.pdf, auditoria.json
        ├── natural/                 documento_final.md, documento_final.pdf, auditoria.json
        └── comparativo/             documento_final.md, documento_final.pdf, auditoria.json

Numa execução simples (``json`` ou ``natural``) existe apenas a subpasta daquela
abordagem. No ``both`` existem ``json/``, ``natural/`` e ``comparativo/``.

Os caminhos são RELATIVOS de propósito: o nó ``ingest_files`` rejeita caminhos
absolutos como proteção contra path traversal.
"""
from __future__ import annotations

from pathlib import Path

# ── Raízes ────────────────────────────────────────────────────────────────────
# Caminhos RELATIVOS (à pasta onde o processo roda), como o resto do projeto já
# usa. Importante: o nó ingest_files rejeita caminhos absolutos como proteção
# contra path traversal, então as entradas precisam ser relativas. O guard de
# download resolve para absoluto (.resolve()) só na hora de servir o arquivo.
PASTA_PROMPTS: Path = Path("prompts")
PASTA_SAIDAS: Path = Path("saidas")

# ── Abordagens ────────────────────────────────────────────────────────────────
JSON: str = "json"
NATURAL: str = "natural"
COMPARATIVO: str = "comparativo"

# Abordagens válidas em cada camada (entradas é compartilhada, sem abordagem).
ABORDAGENS_INTERMEDIARIOS: tuple[str, ...] = (JSON, NATURAL)
ABORDAGENS_ARTEFATOS: tuple[str, ...] = (JSON, NATURAL, COMPARATIVO)

# ── Subpastas ─────────────────────────────────────────────────────────────────
SUB_ENTRADAS: str = "entradas"
SUB_INTERMEDIARIOS: str = "intermediarios"
SUB_ARTEFATOS: str = "artefatos"

# ── Nomes de arquivo padronizados ─────────────────────────────────────────────
# Entradas (nome controlado — nunca o nome enviado pelo usuário).
NOME_BPMN_ENTRADA: str = "processo.bpmn"
NOME_PDF_ENTRADA: str = "descritivo.pdf"

# Artefatos finais (mesmos nomes em toda abordagem; a abordagem é a subpasta).
NOME_DOC_MD: str = "documento_final.md"
NOME_DOC_PDF: str = "documento_final.pdf"
NOME_AUDITORIA: str = "auditoria.json"

# Lista canônica dos arquivos que a pasta de artefatos de uma abordagem contém.
# Usada para descrever os códigos válidos na documentação do endpoint.
ARQUIVOS_ARTEFATO: tuple[str, ...] = (NOME_DOC_MD, NOME_DOC_PDF, NOME_AUDITORIA)


# ── Caminhos por execução (run-scoped) ────────────────────────────────────────

def pasta_da_execucao(run_id: str) -> Path:
    """``saidas/<run_id>/``."""
    return PASTA_SAIDAS / run_id


def pasta_entradas(run_id: str) -> Path:
    """``saidas/<run_id>/entradas/`` — arquivos enviados (compartilhados)."""
    return pasta_da_execucao(run_id) / SUB_ENTRADAS


def caminho_bpmn_entrada(run_id: str) -> Path:
    return pasta_entradas(run_id) / NOME_BPMN_ENTRADA


def caminho_pdf_entrada(run_id: str) -> Path:
    return pasta_entradas(run_id) / NOME_PDF_ENTRADA


def pasta_intermediarios(run_id: str, abordagem: str) -> Path:
    """``saidas/<run_id>/intermediarios/<abordagem>/``."""
    return pasta_da_execucao(run_id) / SUB_INTERMEDIARIOS / abordagem


def pasta_artefatos(run_id: str) -> Path:
    """``saidas/<run_id>/artefatos/`` — raiz para o download stateless."""
    return pasta_da_execucao(run_id) / SUB_ARTEFATOS


def pasta_artefatos_abordagem(run_id: str, abordagem: str) -> Path:
    """``saidas/<run_id>/artefatos/<abordagem>/``."""
    return pasta_artefatos(run_id) / abordagem


# ── Códigos de artefato ───────────────────────────────────────────────────────
# O "código" que o endpoint de download recebe É o caminho relativo dentro de
# artefatos/, no formato ``<abordagem>/<arquivo>`` (ex.: "json/documento_final.pdf").

def codigos_artefato(abordagem: str) -> list[str]:
    """Códigos canônicos de uma abordagem, ex.: ['json/documento_final.md', ...]."""
    return [f"{abordagem}/{arq}" for arq in ARQUIVOS_ARTEFATO]


def codigos_por_pipeline(pipeline: str) -> list[str]:
    """
    Códigos que uma execução daquele pipeline tende a produzir — útil para
    descrever, na documentação do endpoint, o que é baixável em cada modo.
    """
    if pipeline == NATURAL:
        return codigos_artefato(NATURAL)
    if pipeline == "both":
        return (
            codigos_artefato(JSON)
            + codigos_artefato(NATURAL)
            + codigos_artefato(COMPARATIVO)
        )
    return codigos_artefato(JSON)


def listar_artefatos(run_id: str) -> dict[str, str]:
    """
    Varre ``saidas/<run_id>/artefatos/`` e devolve ``{código: caminho}`` dos
    arquivos que existem de fato, com o código no formato ``<abordagem>/<arquivo>``.
    Base tanto para o mapa de artefatos da resposta quanto para o download.
    """
    base = pasta_artefatos(run_id)
    if not base.is_dir():
        return {}
    mapa: dict[str, str] = {}
    for caminho in sorted(base.rglob("*")):
        if caminho.is_file():
            codigo = caminho.relative_to(base).as_posix()
            mapa[codigo] = str(caminho)
    return mapa


# ── Criação de pastas ─────────────────────────────────────────────────────────

def garantir(caminho: Path) -> Path:
    """Cria o diretório (e os pais) se necessário e o devolve. Idempotente."""
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def criar_estrutura_execucao(run_id: str) -> Path:
    """
    Cria a pasta da execução e a subpasta ``entradas/`` (o mínimo necessário no
    início do POST). As subpastas de ``intermediarios/`` e ``artefatos/`` são
    criadas sob demanda, por abordagem, quando cada pipeline grava.
    """
    garantir(pasta_entradas(run_id))
    return pasta_da_execucao(run_id)
