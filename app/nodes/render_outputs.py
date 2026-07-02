"""
Nó LangGraph: render_outputs
Entrega 2 — pipeline JSON (Sprint 2)

Gera os artefatos finais a partir dos dados estruturados (ProcessoJSON +
DocumentoPDFJSON + candidatos validados):
  - documento_final.md  — relatório completo em Markdown (7 seções obrigatórias)
  - documento_final.pdf — versão PDF do relatório
  - auditoria.json      — dados estruturados para rastreabilidade
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from app.schemas import (
    AutomationCandidateJSON,
    DocumentoPDFJSON,
    EstadoGrafo,
    ProcessoJSON,
)
from app.utils import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers compartilhados (importados por render_outputs_natural e _both)
# ---------------------------------------------------------------------------

def md_secao(nivel: int, titulo: str) -> str:
    return f"{'#' * nivel} {titulo}\n\n"


def md_tabela(cabecalhos: list[str], linhas: list[list[str]]) -> str:
    sep  = " | ".join("---" for _ in cabecalhos)
    cab  = " | ".join(cabecalhos)
    rows = "\n".join(f"| {' | '.join(str(c) for c in l)} |" for l in linhas)
    return f"| {cab} |\n| {sep} |\n{rows}\n\n"


def md_secoes_candidatos(candidatos: list[AutomationCandidateJSON]) -> str:
    """Seções 4–7 idênticas nos três pipelines."""
    ordem = {"muito alta": 0, "alta": 1, "média": 2, "baixa": 3}
    linhas: list[str] = []

    # Seção 4
    linhas.append(md_secao(1, "4. Lista de Automações Candidatas"))
    cab  = ["ID", "Nome", "Tipo", "Prioridade", "Atividades envolvidas", "Impacto esperado"]
    rows = []
    for c in candidatos:
        ativs = ", ".join(c.atividades_envolvidas[:2])
        if len(c.atividades_envolvidas) > 2:
            ativs += f" (+{len(c.atividades_envolvidas) - 2})"
        rows.append([c.id, c.nome, c.tipo_automacao.value, c.prioridade.value,
                     ativs, c.impactos[0] if c.impactos else "—"])
    linhas.append(md_tabela(cab, rows))

    # Seção 5
    linhas.append(md_secao(1, "5. Detalhamento das Automações Candidatas"))
    for cand in candidatos:
        linhas.append(md_secao(2, f"{cand.id} — {cand.nome}"))
        linhas.append(f"**Tipo:** {cand.tipo_automacao.value}  \n")
        linhas.append(f"**Prioridade:** {cand.prioridade.value} — {cand.justificativa_prioridade}  \n\n")
        linhas.append(md_secao(3, "Atividades do BPMN cobertas"))
        for a in cand.atividades_envolvidas:
            linhas.append(f"- {a}\n")
        linhas.append("\n")
        linhas.append(md_secao(3, "Proposta"))
        linhas.append(f"{cand.proposta}\n\n")
        linhas.append(md_secao(3, "Gatilho"))
        linhas.append(f"{cand.gatilho}\n\n")
        linhas.append(md_secao(3, "Entradas"))
        for e in cand.entradas:
            linhas.append(f"- {e}\n")
        linhas.append("\n")
        linhas.append(md_secao(3, "Saídas"))
        for s in cand.saidas:
            linhas.append(f"- {s}\n")
        linhas.append("\n")
        linhas.append(md_secao(3, "Como automatizar"))
        linhas.append(f"{cand.como_automatizar}\n\n")
        linhas.append(md_secao(3, "Justificativa"))
        linhas.append(f"{cand.justificativa}\n\n")
        linhas.append(md_secao(3, "Benefícios administrativos"))
        for b in cand.beneficios:
            linhas.append(f"- {b}\n")
        linhas.append("\n")
        linhas.append(md_secao(3, "Impactos na gestão"))
        for i in cand.impactos:
            linhas.append(f"- {i}\n")
        linhas.append("\n")
        linhas.append(md_secao(3, "Riscos e dependências"))
        for r in cand.riscos:
            linhas.append(f"- {r}\n")
        linhas.append("\n")
        linhas.append(md_secao(3, "Métricas de sucesso"))
        for m in cand.metricas:
            linhas.append(f"- {m}\n")
        linhas.append("\n---\n\n")

    # Seção 6
    linhas.append(md_secao(1, "6. Riscos e Limitações Gerais"))
    linhas.append(
        "- **Dependências técnicas:** Sistemas como SIAFI, SEI, SIAPE e SGP podem "
        "exigir autenticação com MFA, dificultando automação via RPA.\n"
        "- **Sistemas legados:** Alguns sistemas não possuem API oficial disponível, "
        "limitando opções de integração.\n"
        "- **Qualidade documental:** A qualidade dos documentos recebidos pode variar, "
        "exigindo validação humana em casos ambíguos.\n"
        "- **Necessidade de humano no ciclo:** Decisões com impacto jurídico ou financeiro "
        "devem manter validação humana mesmo após automação.\n"
        "- **Dados sensíveis:** Processos com dados pessoais de servidores exigem atenção "
        "à LGPD e normas de privacidade.\n"
        "- **Pontos não inferíveis:** Regras de negócio implícitas não documentadas no BPMN "
        "ou no PDF não foram consideradas nesta análise.\n\n"
    )

    # Seção 7
    linhas.append(md_secao(1, "7. Recomendações de Priorização"))
    linhas.append(
        "A ordem de implementação sugerida considera volume de ocorrências, "
        "grau de repetitividade e impacto nos indicadores do processo:\n\n"
    )
    for i, cand in enumerate(sorted(candidatos, key=lambda c: ordem.get(c.prioridade.value, 99)), 1):
        linhas.append(
            f"{i}. **{cand.id} — {cand.nome}** *(prioridade: {cand.prioridade.value})*  \n"
            f"   {cand.justificativa_prioridade}  \n"
            f"   Métrica: {cand.metricas[0] if cand.metricas else '—'}  \n\n"
        )

    return "".join(linhas)


# ---------------------------------------------------------------------------
# Geração do documento Markdown — Entrega 2 (JSON)
# ---------------------------------------------------------------------------

def _gerar_markdown(
    processo: ProcessoJSON,
    documento: DocumentoPDFJSON,
    candidatos: list[AutomationCandidateJSON],
    bpmn_nome: str,
    pdf_nome: str,
) -> str:
    data_analise = datetime.now().strftime("%d/%m/%Y %H:%M")
    linhas: list[str] = []

    # Seção 1
    linhas.append(md_secao(1, "1. Identificação do Processo"))
    linhas.append(f"**Nome do processo:** {processo.nome}  \n")
    linhas.append(f"**Arquivo BPMN:** `{bpmn_nome}`  \n")
    linhas.append(f"**Arquivo PDF:** `{pdf_nome}`  \n")
    linhas.append(f"**Data da análise:** {data_analise}  \n")
    linhas.append(f"**Unidade responsável:** {documento.unidade_responsavel}  \n\n")
    linhas.append("**Resumo executivo:**  \n")
    linhas.append(
        f"{documento.descricao[:500]}{'...' if len(documento.descricao) > 500 else ''}  \n\n"
    )
    linhas.append(
        f"Esta análise identificou **{len(candidatos)} automação(ões) candidata(s)** "
        f"no processo **{processo.nome}**.\n\n"
    )

    # Seção 2
    linhas.append(md_secao(1, "2. Leitura do BPMN"))
    linhas.append(md_secao(2, "2.1 Raias identificadas"))
    for raia in processo.lanes:
        linhas.append(f"- {raia}\n")
    linhas.append("\n")

    atividades = [n for n in processo.nodes if n.tipo.value == "atividade"]
    linhas.append(md_secao(2, f"2.2 Atividades ({len(atividades)})"))
    for i, atv in enumerate(atividades, 1):
        lane_str = f" *(raia: {atv.lane})*" if atv.lane else ""
        docs_str = f" — documentos: {', '.join(atv.documentos_relacionados)}" if atv.documentos_relacionados else ""
        linhas.append(f"{i}. **{atv.nome}**{lane_str}{docs_str}\n")
    linhas.append("\n")

    if processo.gateways:
        linhas.append(md_secao(2, "2.3 Gateways e decisões"))
        for gw in processo.gateways:
            conds = ", ".join(f'"{c}"' for c in gw.get("condicoes_saida", []))
            linhas.append(
                f"- **{gw['nome']}** *(tipo: {gw['tipo']})*"
                f"{f' → condições: {conds}' if conds else ''}\n"
            )
        linhas.append("\n")

    if processo.data_objects:
        linhas.append(md_secao(2, "2.4 Documentos e objetos de dados"))
        for do_ in processo.data_objects:
            linhas.append(f"- {do_}\n")
        linhas.append("\n")

    if processo.loops_detectados:
        linhas.append(md_secao(2, "2.5 Pontos de retorno (loops)"))
        id_para_nome = {n.id: n.nome for n in processo.nodes}
        for i, ciclo in enumerate(processo.loops_detectados, 1):
            nos = [id_para_nome.get(nid, nid) for nid in ciclo]
            linhas.append(f"- Ciclo {i}: {' → '.join(nos)}\n")
        linhas.append("\n")

    # Seção 3
    linhas.append(md_secao(1, "3. Leitura do Descritivo do Processo (PDF)"))
    linhas.append(md_secao(2, "3.1 Descrição administrativa"))
    linhas.append(f"{documento.descricao}\n\n")

    if documento.procedimentos:
        linhas.append(md_secao(2, "3.2 Procedimentos"))
        for p in documento.procedimentos:
            linhas.append(f"- {p}\n")
        linhas.append("\n")

    if documento.amparo_legal:
        linhas.append(md_secao(2, "3.3 Amparo legal"))
        for n in documento.amparo_legal:
            linhas.append(f"- {n}\n")
        linhas.append("\n")

    if documento.indicadores:
        linhas.append(md_secao(2, "3.4 Indicadores de desempenho"))
        for ind in documento.indicadores:
            linhas.append(f"**{ind.nome}**  \n")
            if ind.formula:
                linhas.append(f"- Fórmula: {ind.formula}  \n")
            if ind.fonte_dados:
                linhas.append(f"- Fonte: {ind.fonte_dados}  \n")
            if ind.frequencia:
                linhas.append(f"- Frequência: {ind.frequencia}  \n")
            if ind.metas:
                linhas.append(f"- Metas: {', '.join(ind.metas)}  \n")
            linhas.append("\n")

    if documento.metas:
        linhas.append(md_secao(2, "3.5 Metas gerais"))
        for m in documento.metas:
            linhas.append(f"- {m}\n")
        linhas.append("\n")

    if documento.observacoes:
        linhas.append(md_secao(2, "3.6 Observações relevantes"))
        linhas.append(f"{documento.observacoes}\n\n")

    linhas.append(md_secoes_candidatos(candidatos))
    return "".join(linhas)


# ---------------------------------------------------------------------------
# Nó render_outputs — Entrega 2
# ---------------------------------------------------------------------------

def render_outputs(estado: EstadoGrafo) -> EstadoGrafo:
    """Nó LangGraph: gera os artefatos finais do pipeline JSON (Entrega 2)."""
    if not estado.candidatos:
        estado.erros.append(
            "render_outputs: lista de candidatos vazia. "
            "Verifique se validate_schema executou com sucesso."
        )
        return estado

    if estado.processo_json is None or estado.documento_pdf_json is None:
        estado.erros.append(
            "render_outputs: processo_json ou documento_pdf_json ausente no estado."
        )
        return estado

    # Artefatos finais (Entrega 2 / JSON) — run-scoped via config
    saida_dir = config.garantir(config.pasta_artefatos_abordagem(estado.run_id, config.JSON))

    bpmn_nome = estado.artefatos.get("bpmn_nome", "processo.bpmn")
    pdf_nome  = estado.artefatos.get("pdf_nome",  "descritivo.pdf")

    # Markdown
    try:
        markdown = _gerar_markdown(
            estado.processo_json,
            estado.documento_pdf_json,
            estado.candidatos,
            bpmn_nome,
            pdf_nome,
        )
        md_path = saida_dir / config.NOME_DOC_MD
        md_path.write_text(markdown, encoding="utf-8")
        estado.artefatos["documento_final_md"] = str(md_path)
        logger.info("%s salvo — %d chars", md_path, len(markdown))
    except Exception as exc:
        estado.erros.append(f"render_outputs: erro ao gerar Markdown — {exc}")
        return estado

    # PDF
    try:
        from app.render_pdf import gerar_pdf
        pdf_saida = saida_dir / config.NOME_DOC_PDF
        gerar_pdf(
            caminho_markdown=md_path,
            caminho_pdf=pdf_saida,
            titulo_processo=estado.processo_json.nome,
            unidade=estado.documento_pdf_json.unidade_responsavel,
        )
        estado.artefatos["documento_final_pdf"] = str(pdf_saida)
        logger.info("%s salvo — %d bytes", pdf_saida, pdf_saida.stat().st_size)
    except Exception as exc:
        estado.avisos.append(f"render_outputs: não foi possível gerar PDF — {exc}")

    # Auditoria JSON
    try:
        auditoria = {
            "run_id":            estado.run_id,
            "pipeline":          "json",
            "data_analise":      datetime.now().isoformat(),
            "processo":          estado.processo_json.model_dump(),
            "documento_pdf":     estado.documento_pdf_json.model_dump(),
            "candidatos":        [c.model_dump() for c in estado.candidatos],
            "avisos":            estado.avisos,
            "artefatos":         estado.artefatos,
            "tentativas_reparo": estado.tentativas_reparo,
        }
        audit_path = saida_dir / config.NOME_AUDITORIA
        audit_path.write_text(json.dumps(auditoria, ensure_ascii=False, indent=2), encoding="utf-8")
        estado.artefatos["auditoria_json"] = str(audit_path)
        logger.info("%s salvo.", audit_path)
    except Exception as exc:
        estado.erros.append(f"render_outputs: erro ao gerar JSON de auditoria — {exc}")
        return estado

    logger.info(
        "render_outputs (json): concluído — %d automações | artefatos: %s",
        len(estado.candidatos), list(estado.artefatos.keys()),
    )
    return estado
