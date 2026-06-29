"""
app/cli.py — Interface de linha de comando
Sprint 2, Entrega 2

Conforme documento da sprint:
  - Seção 4 (camada 7): "Disponibilizar endpoint POST e execução por
    linha de comando para testes reprodutíveis."
  - Seção 8: "A execução por linha de comando também é obrigatória para
    facilitar testes automatizados e avaliação pela coordenação."
  - Seção 8.1: parâmetro pipeline=natural|json|both — mesmo da API.

A CLI usa os mesmos arquivos de entrada que a API (bpmn_file e pdf_file)
e aceita os mesmos parâmetros de pipeline, garantindo que os resultados
sejam idênticos aos produzidos via POST.

Uso:
    python -m app.cli --bpmn <arquivo.bpmn> --pdf <arquivo.pdf> [opções]

    ou via run.py (wrapper na raiz do projeto):
    python run.py --bpmn <arquivo.bpmn> --pdf <arquivo.pdf> [opções]

Exemplos:
    # Pipeline JSON estruturado (Entrega 2) — padrão
    python -m app.cli \\
        --bpmn "entradas/Análise Processual e Tributária/Análise.bpmn" \\
        --pdf  "entradas/Análise Processual e Tributária/analise-processual-e-tributaria.pdf"

    # Escolher pipeline explicitamente
    python -m app.cli --bpmn processo.bpmn --pdf descritivo.pdf --pipeline json

    # Modo dry-run: roda parsing sem chamar o LLM
    python -m app.cli --bpmn processo.bpmn --pdf descritivo.pdf --dry-run

    # Definir run_id manualmente (útil para testes automatizados)
    python -m app.cli --bpmn processo.bpmn --pdf descritivo.pdf --run-id analise-001
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Configuração inicial em INFO — ajustada para DEBUG se --verbose for passado
# IMPORTANTE: basicConfig deve ser chamado antes das importações do app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cli")


def _aplicar_verbose() -> None:
    """
    Eleva o nível de log para DEBUG em todos os loggers do app.
    Chamado antes de qualquer execução quando --verbose está ativo.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for nome in logging.Logger.manager.loggerDict:
        if nome.startswith("app"):
            logging.getLogger(nome).setLevel(logging.DEBUG)

# ---------------------------------------------------------------------------
# Definição dos argumentos
# ---------------------------------------------------------------------------

def _criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description=(
            "Sprint 2 — Identificação de automações a partir de BPMN e PDF\n"
            "UFMS Apoia MDA e MAPA — Meta 3"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
exemplos:
  # Pipeline JSON (Entrega 2) — padrão atual
  python -m app.cli --bpmn "entradas/Análise Processual e Tributária/Análise.bpmn" \\
                    --pdf  "entradas/Análise Processual e Tributária/analise-processual-e-tributaria.pdf"

  # Dry-run (sem LLM)
  python -m app.cli --bpmn processo.bpmn --pdf descritivo.pdf --dry-run

  # Run-id personalizado (útil para testes automatizados)
  python -m app.cli --bpmn processo.bpmn --pdf descritivo.pdf --run-id analise-001
        """,
    )

    # Argumentos obrigatórios
    parser.add_argument(
        "--bpmn",
        required=True,
        metavar="ARQUIVO.bpmn",
        help="Caminho para o arquivo .bpmn do processo institucional.",
    )
    parser.add_argument(
        "--pdf",
        required=True,
        metavar="ARQUIVO.pdf",
        help="Caminho para o arquivo .pdf descritivo do processo.",
    )

    # Parâmetro de pipeline — mesmo da API (seção 8.1)
    parser.add_argument(
        "--pipeline",
        choices=["json", "natural", "both"],
        default="json",
        help=(
            "Abordagem a executar (padrão: json).\n"
            "  json    — Pipeline JSON estruturado (Entrega 2) [implementado]\n"
            "  natural — Pipeline linguagem natural (Entrega 1) [em desenvolvimento]\n"
            "  both    — Executa as duas abordagens e compara [em desenvolvimento]"
        ),
    )

    # Argumentos opcionais
    parser.add_argument(
        "--run-id",
        default=None,
        metavar="ID",
        help="Identificador da execução (gerado automaticamente se omitido).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Executa apenas parsing e extração sem chamar o LLM. "
            "Útil para validar os arquivos de entrada sem consumir créditos."
        ),
    )
    parser.add_argument(
        "--saida",
        default="saidas",
        metavar="PASTA",
        help="Pasta de saída dos artefatos (padrão: saidas/).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Exibe logs detalhados de cada nó do grafo.",
    )

    return parser


# ---------------------------------------------------------------------------
# Execução do pipeline JSON (Entrega 2)
# ---------------------------------------------------------------------------

def _executar_json(args: argparse.Namespace, run_id: str) -> int:
    """
    Executa o pipeline da Entrega 2 (JSON estruturado).
    Retorna 0 em sucesso, 1 em erro.
    """
    from app.graph import executar_pipeline

    print()
    print("  Pipeline: JSON estruturado (Entrega 2)")
    print("  (pode levar 30–120 segundos dependendo do LLM)\n")

    try:
        estado = executar_pipeline(
            caminho_bpmn=args.bpmn,
            caminho_pdf=args.pdf,
            run_id=run_id,
        )
    except Exception as exc:
        print(f"\n❌ Erro fatal no pipeline: {exc}")
        return 1

    _imprimir_resultado(estado, "json")
    return 0 if not estado.erros else 1


def _executar_natural(args: argparse.Namespace, run_id: str) -> int:
    """
    Placeholder para o pipeline da Entrega 1 (linguagem natural).
    Será implementado pelo responsável pela Entrega 1.
    """
    print()
    print("  ⚠  Pipeline 'natural' (Entrega 1) ainda não implementado nesta branch.")
    print("     Execute com --pipeline json para usar a Entrega 2.")
    return 1


def _executar_both(args: argparse.Namespace, run_id: str) -> int:
    """
    Executa os dois pipelines em sequência e exibe comparação.
    O modo 'both' gera intermediários e documento final para cada abordagem,
    conforme seção 8.1 do documento da sprint.
    """
    print()
    print("  Pipeline: both (Entrega 2 JSON + Entrega 1 Natural)")
    print()

    # Entrega 2 — JSON
    print("  ── Entrega 2: JSON estruturado ─────────────────────")
    codigo_json = _executar_json(args, f"{run_id}-json")

    # Entrega 1 — Natural (placeholder)
    print()
    print("  ── Entrega 1: Linguagem natural ────────────────────")
    codigo_natural = _executar_natural(args, f"{run_id}-natural")

    return 0 if codigo_json == 0 else 1


# ---------------------------------------------------------------------------
# Dry-run — sem LLM
# ---------------------------------------------------------------------------

def _executar_dry_run(args: argparse.Namespace, run_id: str) -> int:
    """
    Executa apenas ingest → parse_bpmn → extract_pdf → build_context.
    Não chama o LLM. Útil para validar arquivos sem consumir créditos.
    """
    from app.nodes.build_prompt_context import build_prompt_context
    from app.nodes.extract_pdf_to_json import extract_pdf_to_json
    from app.nodes.ingest_files import ingest_files
    from app.nodes.parse_bpmn_to_json import parse_bpmn_to_json
    from app.schemas import EstadoGrafo

    print()
    print("  Modo: DRY-RUN (sem chamada ao LLM)\n")

    estado = EstadoGrafo(
        run_id=run_id,
        caminho_bpmn=args.bpmn,
        caminho_pdf=args.pdf,
    )

    etapas = [
        ("ingest_files",         ingest_files),
        ("parse_bpmn_to_json",   parse_bpmn_to_json),
        ("extract_pdf_to_json",  extract_pdf_to_json),
        ("build_prompt_context", build_prompt_context),
    ]

    for nome, func in etapas:
        print(f"  ▶ {nome}...", end=" ", flush=True)
        estado = func(estado)
        if estado.erros:
            print("❌")
            for e in estado.erros:
                print(f"    ERRO: {e}")
            return 1
        print("✅")

    # Resumo
    print()
    print("  ── Resumo do DRY-RUN ──────────────────────────────")
    if estado.processo_json:
        proc = estado.processo_json
        atividades = [n for n in proc.nodes if n.tipo.value == "atividade"]
        chamadas   = [n for n in proc.nodes if n.tipo.value == "chamada"]
        print(f"  Processo      : {proc.nome}")
        print(f"  Raias         : {proc.lanes}")
        print(f"  Atividades    : {len(atividades)}")
        print(f"  Subprocessos  : {len(chamadas)}")
        print(f"  Gateways      : {len(proc.gateways)}")
        print(f"  Loops         : {len(proc.loops_detectados)}")

    if estado.documento_pdf_json:
        doc = estado.documento_pdf_json
        print(f"  Título PDF    : {doc.titulo}")
        print(f"  Unidade       : {doc.unidade_responsavel}")
        print(f"  Procedimentos : {len(doc.procedimentos)}")
        print(f"  Amparo legal  : {len(doc.amparo_legal)}")
        print(f"  Indicadores   : {len(doc.indicadores)}")

    if estado.avisos:
        print()
        for av in estado.avisos:
            print(f"  ⚠  {av}")

    print()
    print("  Intermediários salvos:")
    for nome_art, caminho in estado.artefatos.items():
        if Path(caminho).is_file():
            kb = Path(caminho).stat().st_size // 1024
            print(f"    📄 {nome_art:<25} {caminho}  ({kb} KB)")

    print()
    print("  Prompt montado:", f"{len(estado.prompt_usado or '')} chars")
    print()
    print("✅ DRY-RUN concluído. Remova --dry-run para executar o pipeline completo.")
    return 0


# ---------------------------------------------------------------------------
# Impressão do resultado
# ---------------------------------------------------------------------------

def _imprimir_resultado(estado, pipeline: str) -> None:
    """Imprime o resultado final da execução de forma padronizada."""
    print()
    print("  ── Resultado ──────────────────────────────────────")

    if estado.erros:
        print(f"❌ Pipeline '{pipeline}' finalizado com erros:")
        for e in estado.erros:
            print(f"   {e}")
        return

    print(f"✅ {len(estado.candidatos)} automação(ões) identificada(s)")

    if estado.avisos:
        print()
        print("  Avisos:")
        for av in estado.avisos:
            print(f"    ⚠  {av}")

    print()
    print("  Automações:")
    for cand in estado.candidatos:
        print(
            f"    [{cand.prioridade.value.upper():9}] "
            f"{cand.id} — {cand.nome}"
        )
        print(f"               Tipo: {cand.tipo_automacao.value}")

    print()
    print("  Artefatos gerados:")
    for nome_art, caminho in estado.artefatos.items():
        if Path(caminho).is_file():
            kb = Path(caminho).stat().st_size // 1024
            print(f"    📄 {nome_art:<30} {caminho}  ({kb} KB)")

    print()
    if "documento_final_md" in estado.artefatos:
        print(f"  Documento final (Markdown): {estado.artefatos['documento_final_md']}")
    if "documento_final_pdf" in estado.artefatos:
        print(f"  Documento final (PDF):      {estado.artefatos['documento_final_pdf']}")
    if "auditoria_json" in estado.artefatos:
        print(f"  JSON de auditoria:          {estado.artefatos['auditoria_json']}")


# ---------------------------------------------------------------------------
# Ponto de entrada principal
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """
    Ponto de entrada da CLI.
    Retorna 0 em sucesso, 1 em erro (compatível com scripts de CI/CD).
    """
    parser = _criar_parser()
    args = parser.parse_args(argv)

    run_id = args.run_id or f"run-{uuid.uuid4().hex[:8]}"

    if args.verbose:
        _aplicar_verbose()

    # Cabeçalho
    print()
    print("=" * 60)
    print("  Sprint 2 — Pipeline de Automação Inteligente")
    print("=" * 60)
    print(f"  run_id   : {run_id}")
    print(f"  BPMN     : {args.bpmn}")
    print(f"  PDF      : {args.pdf}")
    print(f"  pipeline : {args.pipeline}")
    if args.dry_run:
        print(f"  modo     : dry-run")
    print("=" * 60)

    # Dry-run ignora o parâmetro --pipeline
    if args.dry_run:
        return _executar_dry_run(args, run_id)

    # Despachar para o pipeline escolhido
    if args.pipeline == "json":
        return _executar_json(args, run_id)
    elif args.pipeline == "natural":
        return _executar_natural(args, run_id)
    elif args.pipeline == "both":
        return _executar_both(args, run_id)

    return 1


if __name__ == "__main__":
    sys.exit(main())
