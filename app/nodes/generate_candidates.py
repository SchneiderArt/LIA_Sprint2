"""
Nó LangGraph: generate_candidates
Sprint 2 — compartilhado entre Entrega 1 e Entrega 2

Aceita o contexto de qualquer pipeline:
  - Entrega 2 (JSON):    lê estado.prompt_usado       (ProcessoJSON + DocumentoPDFJSON)
  - Entrega 1 (natural): lê estado.prompt_usado_natural (narrativa BPMN + texto PDF)
"""

from __future__ import annotations

import logging

from app.openrouter import chamar_llm
from app.prompts import carregar_prompt
from app.schemas import EstadoGrafo

logger = logging.getLogger(__name__)


def generate_candidates(estado: EstadoGrafo) -> EstadoGrafo:
    """Nó LangGraph: chama o LLM para gerar automações candidatas."""
    # Aceita contexto da Entrega 2 (prompt_usado) ou da Entrega 1 (prompt_usado_natural)
    contexto = estado.prompt_usado or estado.prompt_usado_natural
    if not contexto:
        estado.erros.append(
            "generate_candidates: nenhum contexto disponível no estado "
            "(prompt_usado e prompt_usado_natural estão ausentes). "
            "Verifique se build_prompt_context ou build_prompt_context_natural executou."
        )
        return estado

    # Carregar prompts versionados (seção 10)
    try:
        system_prompt     = carregar_prompt("system_automation_analyst")
        instrucao_geracao = carregar_prompt("generate_automation_candidates")
    except (KeyError, FileNotFoundError) as exc:
        estado.erros.append(f"generate_candidates: erro ao carregar prompt — {exc}")
        return estado

    user_prompt = f"{instrucao_geracao}\n\n{contexto}"

    try:
        saida_bruta = chamar_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperatura=0.2,   # Baixa temperatura para saída estruturada consistente
            max_tokens=8000,
        )
    except ValueError as exc:
        estado.erros.append(f"generate_candidates: erro na chamada LLM — {exc}")
        return estado

    estado.candidatos_raw = saida_bruta
    return estado
