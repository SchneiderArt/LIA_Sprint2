from pathlib import Path
from app.schemas.modelos import EstadoGrafo
from app.agente.logger import get_logger

logger = get_logger(__name__)

TAMANHO_MAXIMO_BYTES = 20 * 1024 * 1024  # 20 MB por arquivo


def ingestao_arquivos(estado: EstadoGrafo) -> dict:
    """Valida existência, extensão e tamanho dos arquivos de entrada."""
    bpmn = Path(estado.caminho_bpmn)
    pdf = Path(estado.caminho_pdf)
    avisos = list(estado.avisos)

    for arquivo, extensao_esperada in [(bpmn, ".bpmn"), (pdf, ".pdf")]:
        if not arquivo.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {arquivo}")
        if arquivo.suffix.lower() != extensao_esperada:
            raise ValueError(f"Extensão inválida para {arquivo.name}: esperado {extensao_esperada}")
        tamanho = arquivo.stat().st_size
        if tamanho == 0:
            raise ValueError(f"Arquivo vazio: {arquivo.name}")
        if tamanho > TAMANHO_MAXIMO_BYTES:
            raise ValueError(f"Arquivo muito grande ({tamanho} bytes): {arquivo.name}")

    logger.info("ingestao_arquivos | BPMN=%s PDF=%s", bpmn.name, pdf.name)
    return {"avisos": avisos}
