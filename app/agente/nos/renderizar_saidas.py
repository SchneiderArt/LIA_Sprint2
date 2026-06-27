import json
from pathlib import Path
from datetime import datetime

from app.schemas.modelos import EstadoGrafo
from app.agente.logger import get_logger

logger = get_logger(__name__)

PASTA_SAIDAS = Path("saidas")
PASTA_INTERMEDIARIOS = PASTA_SAIDAS / "intermediarios"


def renderizar_saidas(estado: EstadoGrafo) -> dict:
    """Persiste todos os artefatos intermediários e o documento final."""
    PASTA_SAIDAS.mkdir(parents=True, exist_ok=True)
    PASTA_INTERMEDIARIOS.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Intermediários — Entrega 1
    if estado.xml_normalizado:
        (PASTA_INTERMEDIARIOS / "bpmn_normalizado.xml").write_text(
            estado.xml_normalizado, encoding="utf-8"
        )
    if estado.narrativa_bpmn:
        (PASTA_INTERMEDIARIOS / "narrativa_bpmn.txt").write_text(
            estado.narrativa_bpmn, encoding="utf-8"
        )
    if estado.texto_pdf:
        (PASTA_INTERMEDIARIOS / "pdf_texto_extraido.txt").write_text(
            estado.texto_pdf, encoding="utf-8"
        )

    # Intermediários — Entrega 2
    if estado.processo_json:
        (PASTA_INTERMEDIARIOS / "bpmn_estruturado.json").write_text(
            estado.processo_json.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    if estado.documento_pdf_json:
        (PASTA_INTERMEDIARIOS / "pdf_estruturado.json").write_text(
            estado.documento_pdf_json.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # Prompt usado
    if estado.prompt_usado:
        (PASTA_INTERMEDIARIOS / "prompt_usado.txt").write_text(
            estado.prompt_usado, encoding="utf-8"
        )

    if not estado.documento_final:
        raise RuntimeError("renderizar_saidas: documento_final não disponível.")

    doc = estado.documento_final

    # JSON de auditoria
    caminho_json = PASTA_SAIDAS / f"automacoes_{ts}.json"
    caminho_json.write_text(
        doc.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Documento Markdown
    md = _gerar_markdown(doc)
    caminho_md = PASTA_SAIDAS / f"automacoes_{ts}.md"
    caminho_md.write_text(md, encoding="utf-8")

    logger.info(
        "renderizar_saidas | JSON=%s | Markdown=%s",
        caminho_json.name, caminho_md.name,
    )

    return {}


def _gerar_markdown(doc) -> str:
    linhas = [
        f"# Relatório de Automações — {doc.nome_processo}",
        "",
        f"**Arquivo BPMN:** {doc.arquivo_bpmn}  ",
        f"**Arquivo PDF:** {doc.arquivo_pdf}  ",
        f"**Data da análise:** {doc.data_analise}  ",
        f"**Unidades envolvidas:** {', '.join(doc.unidades_envolvidas)}  ",
        "",
        "## Resumo Executivo",
        "",
        doc.resumo_executivo,
        "",
        "## Lista de Automações Candidatas",
        "",
        "| ID | Nome | Tipo | Prioridade |",
        "|----|------|------|------------|",
    ]
    for a in doc.automacoes:
        linhas.append(f"| {a.id} | {a.nome} | {a.tipo_automacao} | {a.prioridade} |")

    for a in doc.automacoes:
        linhas += [
            "",
            f"---",
            "",
            f"## {a.id} — {a.nome}",
            "",
            f"**Tipo:** {a.tipo_automacao}  ",
            f"**Prioridade:** {a.prioridade} — {a.prioridade_justificativa}  ",
            f"**Gatilho:** {a.gatilho}  ",
            "",
            f"**Atividades envolvidas:** {', '.join(a.atividades_envolvidas)}",
            "",
            "**Entradas:**",
            *[f"- {e}" for e in a.entradas],
            "",
            "**Saídas:**",
            *[f"- {s}" for s in a.saidas],
            "",
            "### Como Automatizar",
            "",
            a.como_automatizar,
            "",
            "### Justificativa",
            "",
            a.justificativa,
            "",
            "### Benefícios Administrativos",
            "",
            *[f"- {b}" for b in a.beneficios],
            "",
            "### Impactos na Gestão",
            "",
            *[f"- {i}" for i in a.impactos],
            "",
            "### Riscos e Dependências",
            "",
            *[f"- {r}" for r in a.riscos],
            "",
            f"**Métrica de sucesso:** {a.metrica_de_sucesso}",
        ]

    return "\n".join(linhas)
