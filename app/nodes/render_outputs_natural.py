"""
Nó LangGraph: render_outputs_natural
Entrega 1 — pipeline de linguagem natural (Sprint 2)

Gera os artefatos finais a partir da narrativa BPMN e do texto bruto do PDF:
  - documento_final.md  — relatório completo em Markdown (7 seções obrigatórias)
  - documento_final.pdf — versão PDF do relatório
  - auditoria.json      — dados para rastreabilidade
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from app.nodes.render_outputs import md_secao, md_secoes_candidatos
from app.schemas import AutomationCandidateJSON, EstadoGrafo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Geração do documento Markdown — Entrega 1 (linguagem natural)
# ---------------------------------------------------------------------------

def _gerar_markdown_natural(
    narrativa_bpmn: str,
    pdf_texto: str,
    candidatos: list[AutomationCandidateJSON],
    bpmn_nome: str,
    pdf_nome: str,
    nome_processo: str,
) -> str:
    data_analise = datetime.now().strftime("%d/%m/%Y %H:%M")
    linhas: list[str] = []

    # Seção 1 — Identificação
    linhas.append(md_secao(1, "1. Identificação do Processo"))
    linhas.append(f"**Nome do processo:** {nome_processo}  \n")
    linhas.append(f"**Arquivo BPMN:** `{bpmn_nome}`  \n")
    linhas.append(f"**Arquivo PDF:** `{pdf_nome}`  \n")
    linhas.append(f"**Data da análise:** {data_analise}  \n\n")
    linhas.append(
        f"Esta análise identificou **{len(candidatos)} automação(ões) candidata(s)** "
        f"no processo **{nome_processo}**.\n\n"
    )

    # Seção 2 — narrativa gerada pelo LLM a partir do BPMN normalizado
    linhas.append(md_secao(1, "2. Leitura do BPMN"))
    linhas.append(narrativa_bpmn.strip())
    linhas.append("\n\n")

    # Seção 3 — texto bruto extraído do PDF página a página
    linhas.append(md_secao(1, "3. Leitura do Descritivo do Processo (PDF)"))
    linhas.append(pdf_texto.strip())
    linhas.append("\n\n")

    # Seções 4–7 — idênticas ao pipeline JSON
    linhas.append(md_secoes_candidatos(candidatos))

    return "".join(linhas)


# ---------------------------------------------------------------------------
# Nó render_outputs_natural — Entrega 1
# ---------------------------------------------------------------------------

def render_outputs_natural(estado: EstadoGrafo) -> EstadoGrafo:
    """Nó LangGraph: gera os artefatos finais do pipeline de linguagem natural (Entrega 1)."""
    if not estado.candidatos:
        estado.erros.append(
            "render_outputs_natural: lista de candidatos vazia. "
            "Verifique se validate_schema executou com sucesso."
        )
        return estado

    if estado.narrativa_bpmn is None or estado.pdf_texto_extraido is None:
        estado.erros.append(
            "render_outputs_natural: narrativa_bpmn ou pdf_texto_extraido ausente. "
            "Verifique se bpmn_to_natural_language e extract_pdf_text executaram."
        )
        return estado

    saida_dir = Path("saidas")
    saida_dir.mkdir(parents=True, exist_ok=True)

    bpmn_nome     = estado.artefatos.get("bpmn_nome", "processo.bpmn")
    pdf_nome      = estado.artefatos.get("pdf_nome",  "descritivo.pdf")
    nome_processo = estado.artefatos.get("bpmn_nome_processo", bpmn_nome)
    nome          = estado.nome_saida

    # Markdown
    try:
        markdown = _gerar_markdown_natural(
            estado.narrativa_bpmn,
            estado.pdf_texto_extraido,
            estado.candidatos,
            bpmn_nome,
            pdf_nome,
            nome_processo,
        )
        md_path = saida_dir / f"{nome}.md"
        md_path.write_text(markdown, encoding="utf-8")
        estado.artefatos["documento_final_md"] = str(md_path)
        logger.info("%s.md salvo — %d chars", nome, len(markdown))
    except Exception as exc:
        estado.erros.append(f"render_outputs_natural: erro ao gerar Markdown — {exc}")
        return estado

    # PDF
    try:
        from app.render_pdf import gerar_pdf
        pdf_saida = saida_dir / f"{nome}.pdf"
        gerar_pdf(
            caminho_markdown=md_path,
            caminho_pdf=pdf_saida,
            titulo_processo=nome_processo,
            unidade="",
        )
        estado.artefatos["documento_final_pdf"] = str(pdf_saida)
        logger.info("%s.pdf salvo — %d bytes", nome, pdf_saida.stat().st_size)
    except Exception as exc:
        estado.avisos.append(f"render_outputs_natural: não foi possível gerar PDF — {exc}")

    # Auditoria JSON
    try:
        auditoria = {
            "run_id":             estado.run_id,
            "pipeline":           "natural",
            "data_analise":       datetime.now().isoformat(),
            "narrativa_bpmn":     estado.narrativa_bpmn,
            "pdf_texto_extraido": estado.pdf_texto_extraido,
            "candidatos":         [c.model_dump() for c in estado.candidatos],
            "avisos":             estado.avisos,
            "artefatos":          estado.artefatos,
            "tentativas_reparo":  estado.tentativas_reparo,
        }
        audit_path = saida_dir / f"{nome}_auditoria.json"
        audit_path.write_text(json.dumps(auditoria, ensure_ascii=False, indent=2), encoding="utf-8")
        estado.artefatos["auditoria_json"] = str(audit_path)
        logger.info("%s_auditoria.json salvo.", nome)
    except Exception as exc:
        estado.erros.append(f"render_outputs_natural: erro ao gerar JSON de auditoria — {exc}")
        return estado

    logger.info(
        "render_outputs_natural: concluído — %d automações | artefatos: %s",
        len(estado.candidatos), list(estado.artefatos.keys()),
    )
    return estado
