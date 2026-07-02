"""
render_outputs_both
Pipeline "both" — Sprint 2

Combina os documentos gerados pela Entrega 1 (linguagem natural) e
Entrega 2 (JSON estruturado) em um único documento comparativo:
  - documento_final.md      — relatório unificado com as duas entregas
  - documento_final.pdf     — versão PDF do relatório unificado
  - auditoria_both.json     — auditoria consolidada das duas execuções

Não é um nó LangGraph — é chamado diretamente por executar_pipeline
após os dois grafos individuais concluírem.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from app.schemas import EstadoGrafo
from app.utils import config

logger = logging.getLogger(__name__)


def render_outputs_both(
    estado_json: EstadoGrafo,
    estado_natural: EstadoGrafo,
) -> None:
    """
    Lê os documentos individuais de cada pipeline e os une em
    documento_final.md com separação clara entre as duas entregas.

    Estrutura do documento combinado:
      Capa / identificação
      ──────────────────────────────────────
      ENTREGA 1 — Análise por Linguagem Natural
        [documento_final_natural.md completo]
      ──────────────────────────────────────
      ENTREGA 2 — Análise por JSON Estruturado
        [documento_final_json.md completo]
    """
    # Artefato comparativo (both) — run-scoped via config. Lê os documentos
    # individuais já gerados em artefatos/json/ e artefatos/natural/ e grava o
    # combinado em artefatos/comparativo/.
    saida_dir    = config.garantir(config.pasta_artefatos_abordagem(estado_json.run_id, config.COMPARATIVO))
    path_natural = config.pasta_artefatos_abordagem(estado_json.run_id, config.NATURAL) / config.NOME_DOC_MD
    path_json    = config.pasta_artefatos_abordagem(estado_json.run_id, config.JSON) / config.NOME_DOC_MD

    data_analise  = datetime.now().strftime("%d/%m/%Y %H:%M")
    run_id        = estado_json.run_id
    bpmn_nome     = estado_json.artefatos.get("bpmn_nome", "processo.bpmn")
    pdf_nome      = estado_json.artefatos.get("pdf_nome",  "descritivo.pdf")
    nome_processo = (
        estado_json.processo_json.nome
        if estado_json.processo_json
        else estado_json.artefatos.get("bpmn_nome_processo", bpmn_nome)
    )
    total_natural = len(estado_natural.candidatos)
    total_json    = len(estado_json.candidatos)

    cabecalho = (
        f"# Relatório Comparativo de Automações\n\n"
        f"**Processo:** {nome_processo}  \n"
        f"**Arquivo BPMN:** `{bpmn_nome}`  \n"
        f"**Arquivo PDF:** `{pdf_nome}`  \n"
        f"**Data da análise:** {data_analise}  \n"
        f"**Execução:** `{run_id}`  \n\n"
        f"| Pipeline | Automações identificadas |\n"
        f"| --- | --- |\n"
        f"| Entrega 1 — Linguagem Natural | {total_natural} |\n"
        f"| Entrega 2 — JSON Estruturado  | {total_json} |\n"
        f"| **Total** | **{total_natural + total_json}** |\n\n"
    )

    separador = "\n\n---\n\n"

    secao_natural = (
        "# ENTREGA 1 — Análise por Linguagem Natural\n\n"
        + (path_natural.read_text(encoding="utf-8").strip() if path_natural.exists()
           else "*Documento da Entrega 1 não foi gerado.*")
    )

    secao_json = (
        "# ENTREGA 2 — Análise por JSON Estruturado\n\n"
        + (path_json.read_text(encoding="utf-8").strip() if path_json.exists()
           else "*Documento da Entrega 2 não foi gerado.*")
    )

    combinado = cabecalho + separador + secao_natural + separador + secao_json

    md_path = saida_dir / config.NOME_DOC_MD
    md_path.write_text(combinado, encoding="utf-8")
    logger.info("documento_final.md (both) salvo — %d chars", len(combinado))

    # PDF combinado
    try:
        from app.render_pdf import gerar_pdf
        pdf_saida = saida_dir / config.NOME_DOC_PDF
        gerar_pdf(
            caminho_markdown=md_path,
            caminho_pdf=pdf_saida,
            titulo_processo=nome_processo,
            unidade="",
        )
        logger.info("documento_final.pdf (both) salvo — %d bytes", pdf_saida.stat().st_size)
    except Exception as exc:
        logger.warning("render_outputs_both: não foi possível gerar PDF — %s", exc)

    # Auditoria consolidada
    try:
        auditoria = {
            "run_id":       run_id,
            "pipeline":     "both",
            "data_analise": datetime.now().isoformat(),
            "entrega_1": {
                "candidatos":         [c.model_dump() for c in estado_natural.candidatos],
                "narrativa_bpmn":     estado_natural.narrativa_bpmn,
                "pdf_texto_extraido": estado_natural.pdf_texto_extraido,
                "avisos":             estado_natural.avisos,
                "erros":              estado_natural.erros,
                "tentativas_reparo":  estado_natural.tentativas_reparo,
            },
            "entrega_2": {
                "candidatos":    [c.model_dump() for c in estado_json.candidatos],
                "processo":      estado_json.processo_json.model_dump() if estado_json.processo_json else None,
                "documento_pdf": estado_json.documento_pdf_json.model_dump() if estado_json.documento_pdf_json else None,
                "avisos":        estado_json.avisos,
                "erros":         estado_json.erros,
                "tentativas_reparo": estado_json.tentativas_reparo,
            },
        }
        audit_path = saida_dir / config.NOME_AUDITORIA
        audit_path.write_text(json.dumps(auditoria, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("auditoria_both.json salvo.")
    except Exception as exc:
        logger.warning("render_outputs_both: erro ao gerar auditoria — %s", exc)
