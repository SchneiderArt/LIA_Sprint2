"""
run.py — Wrapper de linha de comando (raiz do projeto)
Sprint 2, Entrega 2

Conforme documento da sprint, seção 8:
  "A execução por linha de comando também é obrigatória para facilitar
   testes automatizados e avaliação pela coordenação."

Este arquivo é o ponto de entrada principal para execução via CLI.
Delega toda a lógica para app/cli.py.

Uso:
    python run.py --bpmn <arquivo.bpmn> --pdf <arquivo.pdf> [opções]

    ou equivalentemente:
    python -m app.cli --bpmn <arquivo.bpmn> --pdf <arquivo.pdf> [opções]

Exemplos:
    python run.py --bpmn "entradas/Análise Processual e Tributária/Análise.bpmn" ^
                  --pdf  "entradas/Análise Processual e Tributária/analise-processual-e-tributaria.pdf"

    python run.py --bpmn processo.bpmn --pdf descritivo.pdf --pipeline json
    python run.py --bpmn processo.bpmn --pdf descritivo.pdf --dry-run
    python run.py --bpmn processo.bpmn --pdf descritivo.pdf --run-id analise-001
"""

import sys
from app.cli import main

if __name__ == "__main__":
    sys.exit(main())
