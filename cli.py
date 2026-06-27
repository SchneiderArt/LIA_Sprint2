"""CLI para executar a análise localmente sem a API."""
import argparse
import sys
from pathlib import Path

from app.agente.grafo import construir_grafo
from app.schemas.modelos import EstadoGrafo


def main():
    parser = argparse.ArgumentParser(description="UFMS Sprint 2 — Análise de Automações")
    parser.add_argument("--bpmn", required=True, help="Caminho para o arquivo .bpmn")
    parser.add_argument("--pdf", required=True, help="Caminho para o arquivo .pdf")
    parser.add_argument(
        "--pipeline",
        choices=["natural", "json", "both"],
        default="both",
        help="Abordagem a executar (padrão: both)",
    )
    args = parser.parse_args()

    bpmn = Path(args.bpmn)
    pdf = Path(args.pdf)

    if not bpmn.exists():
        print(f"[ERRO] Arquivo BPMN não encontrado: {bpmn}")
        sys.exit(1)
    if not pdf.exists():
        print(f"[ERRO] Arquivo PDF não encontrado: {pdf}")
        sys.exit(1)

    print(f"Iniciando análise — pipeline={args.pipeline}")
    print(f"  BPMN: {bpmn}")
    print(f"  PDF:  {pdf}")

    estado_inicial = EstadoGrafo(
        caminho_bpmn=str(bpmn),
        caminho_pdf=str(pdf),
        pipeline=args.pipeline,
    )

    grafo = construir_grafo()
    estado_final: EstadoGrafo = grafo.invoke(estado_inicial)

    if estado_final.documento_final:
        qtd = len(estado_final.documento_final.automacoes)
        print(f"\nConcluído! {qtd} automação(ões) identificada(s).")
    if estado_final.avisos:
        print("\nAvisos:")
        for aviso in estado_final.avisos:
            print(f"  ⚠ {aviso}")
    print("\nArtefatos salvos em: saidas/")


if __name__ == "__main__":
    main()
