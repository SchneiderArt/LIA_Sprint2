"""
Nó LangGraph: generate_candidates
Sprint 2, Entrega 2

Responsabilidades (conforme documento da sprint, seções 4, 7.1 e 11):
  - Chamar o LLM via OpenRouter (cliente centralizado em app/openrouter.py)
  - Usar o system prompt de system_automation_analyst.md
  - Usar o user prompt de generate_automation_candidates.md
  - A chave OpenRouter vem do .env — nunca hardcoded (seção 11)
  - Armazenar a saída bruta em estado.candidatos_raw para validação posterior
"""

from __future__ import annotations

import logging

from app.openrouter import chamar_llm
from app.prompts import carregar_prompt
from app.schemas import EstadoGrafo

logger = logging.getLogger(__name__)


def generate_candidates(estado: EstadoGrafo) -> EstadoGrafo:
    """
    Nó LangGraph: chama o LLM via OpenRouter para gerar automações candidatas.

    Usa:
      - system_automation_analyst.md como system prompt
      - generate_automation_candidates.md como instrução de geração
      - estado.prompt_usado como contexto (ProcessoJSON + DocumentoPDFJSON)

    Armazena a saída bruta do LLM em estado.candidatos_raw para que
    o nó validate_schema possa validá-la com Pydantic v2.
    """
    if not estado.prompt_usado:
        estado.erros.append(
            "generate_candidates: prompt_usado ausente no estado. "
            "Verifique se o nó build_prompt_context executou com sucesso."
        )
        return estado

    # Carregar prompts versionados (seção 10)
    try:
        system_prompt     = carregar_prompt("system_automation_analyst")
        instrucao_geracao = carregar_prompt("generate_automation_candidates")
    except (KeyError, FileNotFoundError) as exc:
        estado.erros.append(f"generate_candidates: erro ao carregar prompt — {exc}")
        return estado

    # O user prompt combina a instrução de geração com o contexto JSON
    user_prompt = f"{instrucao_geracao}\n\n{estado.prompt_usado}"

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
