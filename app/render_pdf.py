"""
app/render_pdf.py — Renderização do documento final em PDF
Sprint 2, Entrega 2

Conforme documento da sprint, seções 6.1 (passo 10), 7.1 (passo 10) e 12:
  "Gerar o documento final em Markdown e PDF"

Converte o Markdown gerado pelo nó render_outputs em PDF estruturado
usando ReportLab (seção 11: "Markdown + Jinja2, python-docx, ReportLab ou WeasyPrint").

O documento deve ser compreensível para:
  - Unidade administrativa
  - Equipe de gestão de processos
  - Equipe técnica de automação
  (conforme seção 9, primeiro parágrafo)
"""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Paleta de cores
# ---------------------------------------------------------------------------
AZUL_ESCURO = colors.HexColor("#1B3A6B")
AZUL_MEDIO  = colors.HexColor("#2563EB")
AZUL_CLARO  = colors.HexColor("#DBEAFE")
CINZA_CLARO = colors.HexColor("#F3F4F6")
CINZA_BORDA = colors.HexColor("#E5E7EB")
VERDE_BG    = colors.HexColor("#F0FDF4")
VERDE       = colors.HexColor("#166534")
LARANJA_BG  = colors.HexColor("#FFF7ED")
LARANJA     = colors.HexColor("#C2410C")
TEXTO       = colors.HexColor("#1F2937")
BRANCO      = colors.white


# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------

def _estilos():
    base = getSampleStyleSheet()

    titulo_doc = ParagraphStyle("titulo_doc",
        fontSize=20, fontName="Helvetica-Bold",
        textColor=BRANCO, alignment=TA_CENTER,
        spaceAfter=4, leading=26)

    subtitulo_doc = ParagraphStyle("subtitulo_doc",
        fontSize=10, fontName="Helvetica",
        textColor=colors.HexColor("#BFDBFE"), alignment=TA_CENTER,
        spaceAfter=0)

    h1 = ParagraphStyle("h1",
        fontSize=13, fontName="Helvetica-Bold",
        textColor=BRANCO, spaceBefore=0, spaceAfter=0, leading=18)

    h2 = ParagraphStyle("h2",
        fontSize=11, fontName="Helvetica-Bold",
        textColor=AZUL_ESCURO, spaceBefore=10, spaceAfter=4, leading=16)

    h3 = ParagraphStyle("h3",
        fontSize=10, fontName="Helvetica-Bold",
        textColor=AZUL_MEDIO, spaceBefore=8, spaceAfter=3, leading=14)

    corpo = ParagraphStyle("corpo",
        fontSize=9, fontName="Helvetica",
        textColor=TEXTO, spaceBefore=2, spaceAfter=4,
        leading=14, alignment=TA_JUSTIFY)

    item_lista = ParagraphStyle("item_lista",
        fontSize=9, fontName="Helvetica",
        textColor=TEXTO, leftIndent=12, spaceBefore=1,
        spaceAfter=2, leading=13)

    bold_label = ParagraphStyle("bold_label",
        fontSize=9, fontName="Helvetica-Bold",
        textColor=AZUL_ESCURO, spaceBefore=4, spaceAfter=1, leading=13)

    meta_info = ParagraphStyle("meta_info",
        fontSize=8.5, fontName="Helvetica",
        textColor=colors.HexColor("#6B7280"), spaceBefore=1, spaceAfter=1)

    rodape_style = ParagraphStyle("rodape_style",
        fontSize=7.5, fontName="Helvetica",
        textColor=colors.HexColor("#9CA3AF"), alignment=TA_CENTER)

    return {
        "titulo_doc": titulo_doc, "subtitulo_doc": subtitulo_doc,
        "h1": h1, "h2": h2, "h3": h3,
        "corpo": corpo, "item_lista": item_lista,
        "bold_label": bold_label, "meta_info": meta_info,
        "rodape_style": rodape_style,
    }


# ---------------------------------------------------------------------------
# Parser de Markdown → elementos ReportLab
# ---------------------------------------------------------------------------

def _md_para_elementos(markdown: str, estilos: dict) -> list:
    """
    Converte o Markdown gerado pelo nó render_outputs em elementos ReportLab.
    Suporta: # ## ### , listas com - , **bold** , tabelas | , --- (hr), texto.
    """
    elementos = []
    linhas = markdown.splitlines()
    i = 0
    largura_pagina = A4[0] - 5 * cm  # margem total 2.5cm cada lado

    while i < len(linhas):
        linha = linhas[i]
        linha_strip = linha.strip()

        # Ignorar linha vazia
        if not linha_strip:
            elementos.append(Spacer(1, 0.15 * cm))
            i += 1
            continue

        # Seção 1 — cabeçalho azul escuro
        if linha_strip.startswith("# "):
            texto = linha_strip[2:].strip()
            dados = [[Paragraph(texto, estilos["h1"])]]
            t = Table(dados, colWidths=[largura_pagina])
            t.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), AZUL_ESCURO),
                ("TOPPADDING",    (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING",   (0, 0), (-1, -1), 14),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
            ]))
            elementos.append(Spacer(1, 0.3 * cm))
            elementos.append(t)
            elementos.append(Spacer(1, 0.2 * cm))
            i += 1
            continue

        # Seção 2 — cabeçalho azul médio
        if linha_strip.startswith("## "):
            texto = linha_strip[3:].strip()
            dados = [[Paragraph(texto, ParagraphStyle("h2b",
                fontSize=10, fontName="Helvetica-Bold",
                textColor=BRANCO))]]
            t = Table(dados, colWidths=[largura_pagina])
            t.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), AZUL_MEDIO),
                ("TOPPADDING",    (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING",   (0, 0), (-1, -1), 12),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
            ]))
            elementos.append(Spacer(1, 0.25 * cm))
            elementos.append(t)
            elementos.append(Spacer(1, 0.1 * cm))
            i += 1
            continue

        # Seção 3 — cabeçalho azul claro
        if linha_strip.startswith("### "):
            texto = linha_strip[4:].strip()
            dados = [[Paragraph(texto, ParagraphStyle("h3b",
                fontSize=9.5, fontName="Helvetica-Bold",
                textColor=AZUL_ESCURO))]]
            t = Table(dados, colWidths=[largura_pagina])
            t.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), AZUL_CLARO),
                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING",   (0, 0), (-1, -1), 10),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ]))
            elementos.append(Spacer(1, 0.15 * cm))
            elementos.append(t)
            elementos.append(Spacer(1, 0.05 * cm))
            i += 1
            continue

        # Divisor horizontal ---
        if linha_strip == "---":
            elementos.append(Spacer(1, 0.2 * cm))
            elementos.append(HRFlowable(
                width="100%", thickness=1,
                color=CINZA_BORDA, spaceAfter=0.2 * cm))
            i += 1
            continue

        # Tabela Markdown | col | col |
        if linha_strip.startswith("|") and "|" in linha_strip:
            # Coletar todas as linhas da tabela
            linhas_tabela = []
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                l = linhas[i].strip()
                # Pular linha separadora |---|---|
                if not re.match(r"^\|[\s\-|:]+\|$", l):
                    celulas = [c.strip() for c in l.strip("|").split("|")]
                    linhas_tabela.append(celulas)
                i += 1

            if linhas_tabela:
                max_cols = max(len(r) for r in linhas_tabela)
                # Normalizar número de colunas
                linhas_tabela = [
                    r + [""] * (max_cols - len(r)) for r in linhas_tabela
                ]
                col_w = largura_pagina / max_cols

                dados_tabela = []
                for ri, row in enumerate(linhas_tabela):
                    estilo_cel = ParagraphStyle("tcel",
                        fontSize=8, fontName="Helvetica-Bold" if ri == 0 else "Helvetica",
                        textColor=BRANCO if ri == 0 else TEXTO, leading=11)
                    dados_tabela.append([
                        Paragraph(_limpar_md(c), estilo_cel) for c in row
                    ])

                t = Table(dados_tabela, colWidths=[col_w] * max_cols)
                cmds = [
                    ("BACKGROUND",    (0, 0), (-1, 0),  AZUL_ESCURO),
                    ("BACKGROUND",    (0, 1), (-1, -1), CINZA_CLARO),
                    ("ROWBACKGROUNDS",(0, 1), (-1, -1), [BRANCO, CINZA_CLARO]),
                    ("GRID",          (0, 0), (-1, -1), 0.5, CINZA_BORDA),
                    ("TOPPADDING",    (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
                    ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ]
                t.setStyle(TableStyle(cmds))
                elementos.append(t)
                elementos.append(Spacer(1, 0.2 * cm))
            continue

        # Item de lista - texto
        if linha_strip.startswith("- ") or linha_strip.startswith("* "):
            texto = linha_strip[2:].strip()
            texto = _limpar_md(texto)
            elementos.append(Paragraph(
                f"<bullet>&bull;</bullet> {texto}",
                estilos["item_lista"]))
            i += 1
            continue

        # Lista numerada 1. texto
        if re.match(r"^\d+\.", linha_strip):
            texto = re.sub(r"^\d+\.\s*", "", linha_strip)
            texto = _limpar_md(texto)
            num = linha_strip.split(".")[0]
            elementos.append(Paragraph(
                f"<bullet>{num}.</bullet> {texto}",
                estilos["item_lista"]))
            i += 1
            continue

        # Parágrafo normal
        texto = _limpar_md(linha_strip)
        if texto:
            elementos.append(Paragraph(texto, estilos["corpo"]))
        i += 1

    return elementos


def _limpar_md(texto: str) -> str:
    """Remove marcadores Markdown e converte **bold** para tags ReportLab."""
    # **bold** → <b>bold</b>
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    # *italic* → <i>italic</i>
    texto = re.sub(r"\*(.+?)\*", r"<i>\1</i>", texto)
    # `code` → texto normal
    texto = re.sub(r"`(.+?)`", r"\1", texto)
    return texto


# ---------------------------------------------------------------------------
# Cabeçalho e rodapé de página
# ---------------------------------------------------------------------------

class _CabecalhoRodape:
    def __init__(self, titulo: str, unidade: str):
        self.titulo  = titulo
        self.unidade = unidade

    def __call__(self, canvas, doc):
        canvas.saveState()
        w, h = A4

        # Cabeçalho
        canvas.setFillColor(AZUL_ESCURO)
        canvas.rect(0, h - 1.5 * cm, w, 1.5 * cm, fill=True, stroke=False)
        canvas.setFillColor(BRANCO)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(1 * cm, h - 0.9 * cm, self.titulo[:80])
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#BFDBFE"))
        canvas.drawRightString(w - 1 * cm, h - 0.9 * cm, self.unidade[:60])

        # Rodapé
        canvas.setFillColor(CINZA_CLARO)
        canvas.rect(0, 0, w, 0.9 * cm, fill=True, stroke=False)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(1 * cm, 0.3 * cm,
            "UFMS Apoia MDA e MAPA — Meta 3 | Sprint 2 | Entrega 2")
        canvas.drawRightString(w - 1 * cm, 0.3 * cm,
            f"Página {doc.page}")

        canvas.restoreState()


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def gerar_pdf(
    caminho_markdown: str | Path,
    caminho_pdf: str | Path,
    titulo_processo: str = "Processo",
    unidade: str = "",
) -> None:
    """
    Gera o PDF do documento final a partir do Markdown.

    Conforme seção 12 do documento da sprint:
    "Documento final: Markdown e PDF com automações candidatas separadas."

    Args:
        caminho_markdown: caminho do arquivo .md gerado pelo render_outputs
        caminho_pdf:      caminho de saída do PDF
        titulo_processo:  nome do processo para cabeçalho/rodapé
        unidade:          unidade responsável para cabeçalho
    """
    caminho_md  = Path(caminho_markdown)
    caminho_out = Path(caminho_pdf)
    caminho_out.parent.mkdir(parents=True, exist_ok=True)

    markdown = caminho_md.read_text(encoding="utf-8")
    estilos  = _estilos()

    doc = SimpleDocTemplate(
        str(caminho_out),
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.2 * cm,
        bottomMargin=1.8 * cm,
        title=f"Automações — {titulo_processo}",
        author="UFMS Apoia MDA Sprint 2",
        subject="Identificação de automações administrativas",
    )

    # Capa
    story = []
    capa_dados = [[Paragraph(
        f"Automações Candidatas<br/>{titulo_processo}",
        estilos["titulo_doc"])]]
    capa_table = Table(capa_dados, colWidths=[doc.width])
    capa_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), AZUL_ESCURO),
        ("TOPPADDING",    (0, 0), (-1, -1), 20),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
    ]))
    story.append(capa_table)

    sub_dados = [[Paragraph(
        "UFMS Apoia MDA e MAPA — Meta 3 | Sprint 2 | Entrega 2",
        estilos["subtitulo_doc"])]]
    sub_table = Table(sub_dados, colWidths=[doc.width])
    sub_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), AZUL_MEDIO),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
    ]))
    story.append(sub_table)
    story.append(Spacer(1, 0.5 * cm))

    # Conteúdo do Markdown
    story.extend(_md_para_elementos(markdown, estilos))

    cb = _CabecalhoRodape(titulo_processo, unidade)
    doc.build(story, onFirstPage=cb, onLaterPages=cb)
