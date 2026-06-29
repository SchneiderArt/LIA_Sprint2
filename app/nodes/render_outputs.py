"""
Nó LangGraph: render_outputs
Etapa 6 — Sprint 2, Entrega 2

Responsabilidades (conforme documento da sprint, seções 7.1 passo 10 e seção 9):
  - Gerar documento final em Markdown com as 7 seções obrigatórias (seção 9)
  - Gerar JSON de auditoria com automações candidatas e evidências (seção 12)
  - Salvar todos os intermediários para auditoria (seção 8.1)
  - O documento final deve ser compreensível para unidade administrativa,
    equipe de gestão e equipe técnica (seção 9, primeiro parágrafo)
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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Geração do documento final em Markdown
# Estrutura obrigatória definida na seção 9 do documento da sprint
# ---------------------------------------------------------------------------

def _md_secao(nivel: int, titulo: str) -> str:
    return f"{'#' * nivel} {titulo}\n\n"


def _md_tabela(cabecalhos: list[str], linhas: list[list[str]]) -> str:
    sep = " | ".join("---" for _ in cabecalhos)
    cab = " | ".join(cabecalhos)
    corpo = "\n".join(
        " | ".join(str(c) for c in linha) for linha in linhas
    )
    return f"| {cab} |\n| {sep} |\n" + "\n".join(f"| {' | '.join(str(c) for c in l)} |" for l in linhas) + "\n\n"


def _gerar_markdown(
    processo: ProcessoJSON,
    documento: DocumentoPDFJSON,
    candidatos: list[AutomationCandidateJSON],
    bpmn_nome: str,
    pdf_nome: str,
) -> str:
    """
    Gera o documento final em Markdown com as 7 seções obrigatórias
    definidas na seção 9 do documento da sprint.
    """
    data_analise = datetime.now().strftime("%d/%m/%Y %H:%M")
    linhas: list[str] = []

    # -----------------------------------------------------------------------
    # Seção 1: Identificação do processo
    # Conteúdo obrigatório: nome, arquivos, data, unidade(s), resumo executivo
    # -----------------------------------------------------------------------
    linhas.append(_md_secao(1, "1. Identificação do Processo"))
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

    # -----------------------------------------------------------------------
    # Seção 2: Leitura do BPMN
    # Conteúdo: raias, atividades, gateways, documentos, sequência, pontos de retorno
    # -----------------------------------------------------------------------
    linhas.append(_md_secao(1, "2. Leitura do BPMN"))

    linhas.append(_md_secao(2, "2.1 Raias identificadas"))
    for raia in processo.lanes:
        linhas.append(f"- {raia}\n")
    linhas.append("\n")

    atividades = [n for n in processo.nodes if n.tipo.value == "atividade"]
    linhas.append(_md_secao(2, f"2.2 Atividades ({len(atividades)})"))
    for i, atv in enumerate(atividades, 1):
        lane_str = f" *(raia: {atv.lane})*" if atv.lane else ""
        docs_str = f" — documentos: {', '.join(atv.documentos_relacionados)}" if atv.documentos_relacionados else ""
        linhas.append(f"{i}. **{atv.nome}**{lane_str}{docs_str}\n")
    linhas.append("\n")

    if processo.gateways:
        linhas.append(_md_secao(2, "2.3 Gateways e decisões"))
        for gw in processo.gateways:
            conds = ", ".join(f'"{c}"' for c in gw.get("condicoes_saida", []))
            linhas.append(
                f"- **{gw['nome']}** *(tipo: {gw['tipo']})*"
                f"{f' → condições: {conds}' if conds else ''}\n"
            )
        linhas.append("\n")

    if processo.data_objects:
        linhas.append(_md_secao(2, "2.4 Documentos e objetos de dados"))
        for do_ in processo.data_objects:
            linhas.append(f"- {do_}\n")
        linhas.append("\n")

    if processo.loops_detectados:
        linhas.append(_md_secao(2, "2.5 Pontos de retorno (loops)"))
        linhas.append(
            f"Foram detectados **{len(processo.loops_detectados)} ciclo(s)** "
            f"no fluxo do processo.\n\n"
        )
        for i, ciclo in enumerate(processo.loops_detectados, 1):
            nos_nomes = []
            id_para_nome = {n.id: n.nome for n in processo.nodes}
            for nid in ciclo:
                nos_nomes.append(id_para_nome.get(nid, nid))
            linhas.append(f"- Ciclo {i}: {' → '.join(nos_nomes)}\n")
        linhas.append("\n")

    # -----------------------------------------------------------------------
    # Seção 3: Leitura do PDF
    # Conteúdo: descrição, procedimentos, normas, indicadores, metas, observações
    # -----------------------------------------------------------------------
    linhas.append(_md_secao(1, "3. Leitura do Descritivo do Processo (PDF)"))

    linhas.append(_md_secao(2, "3.1 Descrição administrativa"))
    linhas.append(f"{documento.descricao}\n\n")

    if documento.procedimentos:
        linhas.append(_md_secao(2, "3.2 Procedimentos"))
        for proc in documento.procedimentos:
            linhas.append(f"- {proc}\n")
        linhas.append("\n")

    if documento.amparo_legal:
        linhas.append(_md_secao(2, "3.3 Amparo legal"))
        for norma in documento.amparo_legal:
            linhas.append(f"- {norma}\n")
        linhas.append("\n")

    if documento.indicadores:
        linhas.append(_md_secao(2, "3.4 Indicadores de desempenho"))
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
        linhas.append(_md_secao(2, "3.5 Metas gerais"))
        for meta in documento.metas:
            linhas.append(f"- {meta}\n")
        linhas.append("\n")

    if documento.observacoes:
        linhas.append(_md_secao(2, "3.6 Observações relevantes"))
        linhas.append(f"{documento.observacoes}\n\n")

    # -----------------------------------------------------------------------
    # Seção 4: Tabela-resumo das automações candidatas
    # Conteúdo: id, nome, tipo, tarefas envolvidas, prioridade, impacto esperado
    # -----------------------------------------------------------------------
    linhas.append(_md_secao(1, "4. Lista de Automações Candidatas"))

    cab = ["ID", "Nome", "Tipo", "Prioridade", "Atividades envolvidas", "Impacto esperado"]
    rows = []
    for c in candidatos:
        ativs = ", ".join(c.atividades_envolvidas[:2])
        if len(c.atividades_envolvidas) > 2:
            ativs += f" (+{len(c.atividades_envolvidas)-2})"
        impacto = c.impactos[0] if c.impactos else "—"
        rows.append([c.id, c.nome, c.tipo_automacao.value, c.prioridade.value, ativs, impacto])
    linhas.append(_md_tabela(cab, rows))

    # -----------------------------------------------------------------------
    # Seção 5: Seção individual por automação
    # Conteúdo obrigatório: todos os 13 campos da seção 9.1
    # -----------------------------------------------------------------------
    linhas.append(_md_secao(1, "5. Detalhamento das Automações Candidatas"))

    for cand in candidatos:
        linhas.append(_md_secao(2, f"{cand.id} — {cand.nome}"))

        linhas.append(f"**Tipo de automação:** {cand.tipo_automacao.value}  \n")
        linhas.append(f"**Prioridade:** {cand.prioridade.value} — {cand.justificativa_prioridade}  \n\n")

        linhas.append(_md_secao(3, "Atividades do BPMN cobertas"))
        for atv in cand.atividades_envolvidas:
            linhas.append(f"- {atv}\n")
        linhas.append("\n")

        linhas.append(_md_secao(3, "Proposta"))
        linhas.append(f"{cand.proposta}\n\n")

        linhas.append(_md_secao(3, "Gatilho"))
        linhas.append(f"{cand.gatilho}\n\n")

        linhas.append(_md_secao(3, "Entradas"))
        for ent in cand.entradas:
            linhas.append(f"- {ent}\n")
        linhas.append("\n")

        linhas.append(_md_secao(3, "Saídas"))
        for sai in cand.saidas:
            linhas.append(f"- {sai}\n")
        linhas.append("\n")

        linhas.append(_md_secao(3, "Como automatizar"))
        linhas.append(f"{cand.como_automatizar}\n\n")

        linhas.append(_md_secao(3, "Justificativa"))
        linhas.append(f"{cand.justificativa}\n\n")

        linhas.append(_md_secao(3, "Benefícios administrativos"))
        for ben in cand.beneficios:
            linhas.append(f"- {ben}\n")
        linhas.append("\n")

        linhas.append(_md_secao(3, "Impactos na gestão"))
        for imp in cand.impactos:
            linhas.append(f"- {imp}\n")
        linhas.append("\n")

        linhas.append(_md_secao(3, "Riscos e dependências"))
        for risco in cand.riscos:
            linhas.append(f"- {risco}\n")
        linhas.append("\n")

        linhas.append(_md_secao(3, "Métricas de sucesso"))
        for met in cand.metricas:
            linhas.append(f"- {met}\n")
        linhas.append("\n")

        linhas.append("---\n\n")

    # -----------------------------------------------------------------------
    # Seção 6: Riscos e limitações gerais
    # -----------------------------------------------------------------------
    linhas.append(_md_secao(1, "6. Riscos e Limitações Gerais"))
    linhas.append(
        "- **Dependências técnicas:** Sistemas como SIAFI, SEI, SIAPE e SGP podem "
        "exigir autenticação com MFA, dificultando automação via RPA.\n"
        "- **Sistemas legados:** Alguns sistemas não possuem API oficial disponível, "
        "limitando opções de integração.\n"
        "- **Qualidade documental:** A qualidade dos documentos recebidos no processo "
        "pode variar, exigindo validação humana em casos ambíguos.\n"
        "- **Necessidade de humano no ciclo:** Decisões com impacto jurídico ou financeiro "
        "devem manter validação humana mesmo após automação.\n"
        "- **Dados sensíveis:** Processos envolvendo dados pessoais de servidores exigem "
        "atenção à LGPD e normas de privacidade.\n"
        "- **Pontos não inferíveis:** Regras de negócio implícitas não documentadas no BPMN "
        "ou no PDF não foram consideradas nesta análise.\n\n"
    )

    # -----------------------------------------------------------------------
    # Seção 7: Recomendações de priorização
    # -----------------------------------------------------------------------
    linhas.append(_md_secao(1, "7. Recomendações de Priorização"))

    # Ordenar por prioridade (muito alta > alta > média > baixa)
    ordem_prioridade = {"muito alta": 0, "alta": 1, "média": 2, "baixa": 3}
    candidatos_ord = sorted(
        candidatos,
        key=lambda c: ordem_prioridade.get(c.prioridade.value, 99),
    )

    linhas.append(
        "A ordem de implementação sugerida considera volume de ocorrências, "
        "grau de repetitividade e impacto nos indicadores do processo:\n\n"
    )
    for i, cand in enumerate(candidatos_ord, 1):
        linhas.append(
            f"{i}. **{cand.id} — {cand.nome}** *(prioridade: {cand.prioridade.value})*  \n"
            f"   {cand.justificativa_prioridade}  \n"
            f"   Métrica de acompanhamento: {cand.metricas[0] if cand.metricas else '—'}  \n\n"
        )

    return "".join(linhas)


# ---------------------------------------------------------------------------
# Nó render_outputs
# ---------------------------------------------------------------------------

def render_outputs(estado: EstadoGrafo) -> EstadoGrafo:
    """
    Nó LangGraph: gera os artefatos finais da Entrega 2.

    Conforme seção 7.1 (passo 10) e seção 12 do documento:
      - Documento final em Markdown (saidas/documento_final.md)
      - JSON de auditoria (saidas/auditoria.json)
      - Todos os intermediários já foram salvos pelos nós anteriores
    """
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

    saida_dir = Path("saidas")
    saida_dir.mkdir(parents=True, exist_ok=True)

    bpmn_nome = estado.artefatos.get("bpmn_nome", "processo.bpmn")
    pdf_nome  = estado.artefatos.get("pdf_nome",  "descritivo.pdf")

    # --- Documento final em Markdown ---
    try:
        markdown = _gerar_markdown(
            estado.processo_json,
            estado.documento_pdf_json,
            estado.candidatos,
            bpmn_nome,
            pdf_nome,
        )
        md_path = saida_dir / "documento_final.md"
        md_path.write_text(markdown, encoding="utf-8")
        estado.artefatos["documento_final_md"] = str(md_path)
        logger.info("documento_final.md salvo — %d chars", len(markdown))
    except Exception as exc:
        estado.erros.append(f"render_outputs: erro ao gerar Markdown — {exc}")
        return estado

    # --- Documento final em PDF ---
    # Conforme secoes 6.1 (passo 10), 7.1 (passo 10) e 12 do documento da sprint:
    # "Gerar o documento final em Markdown e PDF"
    try:
        from app.render_pdf import gerar_pdf
        pdf_saida = saida_dir / "documento_final.pdf"
        gerar_pdf(
            caminho_markdown=md_path,
            caminho_pdf=pdf_saida,
            titulo_processo=estado.processo_json.nome,
            unidade=estado.documento_pdf_json.unidade_responsavel,
        )
        estado.artefatos["documento_final_pdf"] = str(pdf_saida)
        logger.info("documento_final.pdf salvo — %d bytes", pdf_saida.stat().st_size)
    except Exception as exc:
        # PDF e adicional — registrar aviso mas nao bloquear o pipeline
        estado.avisos.append(f"render_outputs: nao foi possivel gerar PDF — {exc}")
        logger.warning("render_outputs: erro ao gerar PDF — %s", exc)

    # --- JSON de auditoria ---
    # Conforme seção 12: "Lista estruturada das automações e evidências usadas"
    try:
        auditoria = {
            "run_id":          estado.run_id,
            "data_analise":    datetime.now().isoformat(),
            "processo":        estado.processo_json.model_dump(),
            "documento_pdf":   estado.documento_pdf_json.model_dump(),
            "candidatos":      [c.model_dump() for c in estado.candidatos],
            "avisos":          estado.avisos,
            "artefatos":       estado.artefatos,
            "tentativas_reparo": estado.tentativas_reparo,
        }
        audit_path = saida_dir / "auditoria.json"
        with open(audit_path, "w", encoding="utf-8") as f:
            json.dump(auditoria, f, ensure_ascii=False, indent=2)
        estado.artefatos["auditoria_json"] = str(audit_path)
        logger.info("auditoria.json salvo.")
    except Exception as exc:
        estado.erros.append(f"render_outputs: erro ao gerar JSON de auditoria — {exc}")
        return estado

    logger.info(
        "render_outputs: concluído — %d automações | artefatos: %s",
        len(estado.candidatos), list(estado.artefatos.keys()),
    )

    return estado
