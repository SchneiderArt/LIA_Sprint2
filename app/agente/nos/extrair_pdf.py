from pathlib import Path
import fitz  # PyMuPDF

from app.schemas.modelos import EstadoGrafo
from app.agente.logger import get_logger

logger = get_logger(__name__)


def extrair_pdf(estado: EstadoGrafo) -> dict:
    """Extrai texto do PDF preservando estrutura de páginas/seções."""
    caminho = Path(estado.caminho_pdf)
    avisos = list(estado.avisos)

    doc = fitz.open(str(caminho))
    partes: list[str] = []

    for i, pagina in enumerate(doc, start=1):
        texto = pagina.get_text("text").strip()
        if not texto:
            avisos.append(f"PDF: página {i} sem texto — pode precisar de OCR.")
            continue
        partes.append(f"[Página {i}]\n{texto}")

    doc.close()

    texto_completo = "\n\n".join(partes)
    if not texto_completo.strip():
        raise ValueError("PDF não contém texto extraível. Verifique se é um PDF digitalizado.")

    logger.info("extrair_pdf | %d páginas processadas", len(partes))

    return {
        "texto_pdf": texto_completo,
        "avisos": avisos,
    }
