"""
Nó LangGraph: critic_review_node
Sprint 2, Entrega 2

Responsabilidades (conforme documento da sprint, seções 6.1 e 10):
  - Verificar se cada automação tem tarefas envolvidas, meio de automatizar e impacto
  - Verificar lacunas, generalizações, duplicidades e ausência de impacto administrativo
  - Usar o prompt critic_review.md (seção 10)
  - Chamar o LLM via OpenRouter (cliente centralizado em app/openrouter.py)
  - Atualizar estado.candidatos_raw com a saída revisada
"""

from __future__ import annotations

import logging

from app.openrouter import chamar_llm
from app.prompts import carregar_prompt, montar_contexto_critica
from app.schemas import EstadoGrafo

logger = logging.getLogger(__name__)


def critic_review_node(estado: EstadoGrafo) -> EstadoGrafo:
    """
    Nó LangGraph: revisa criticamente as automações candidatas geradas.

    Usa o prompt critic_review.md para verificar:
      - Se cada automação tem tarefas envolvidas, meio de automatizar e impacto
      - Lacunas, generalizações, duplicidades e ausência de impacto administrativo

    Recebe estado.candidatos_raw (saída bruta do generate_candidates) e
    devolve saída revisada em estado.candidatos_raw para validação posterior.
    """
    if not estado.candidatos_raw:
        estado.erros.append(
            "critic_review: candidatos_raw ausente no estado. "
            "Verifique se o nó generate_candidates executou com sucesso."
        )
        return estado

    if estado.processo_json is None or estado.documento_pdf_json is None:
        estado.erros.append(
            "critic_review: processo_json ou documento_pdf_json ausente no estado."
        )
        return estado

    candidatos_para_revisao = estado.candidatos if estado.candidatos else []

    # Montar contexto para o nó de crítica (seção 10 e critic_review.md)
    contexto_critica = montar_contexto_critica(
        estado.processo_json,
        estado.documento_pdf_json,
        candidatos_para_revisao,
    )

    # Se não há candidatos validados ainda, injetar o raw no contexto
    if not candidatos_para_revisao:
        contexto_critica += (
            f"\n\n[CANDIDATOS_RAW]\n{estado.candidatos_raw}\n[/CANDIDATOS_RAW]"
        )

    # Carregar prompts versionados (seção 10)
    try:
        system_prompt     = carregar_prompt("system_automation_analyst")
        instrucao_critica = carregar_prompt("critic_review")
    except (KeyError, FileNotFoundError) as exc:
        estado.erros.append(f"critic_review: erro ao carregar prompt — {exc}")
        return estado

    user_prompt = f"{instrucao_critica}\n\n{contexto_critica}"

    logger.info(
        "critic_review: chamando LLM para revisão | candidatos=%d",
        len(candidatos_para_revisao),
    )

    try:
        saida_revisada = chamar_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperatura=0.1,   # Ainda mais baixa na revisão — foco em correção
            max_tokens=8000,
        )
    except ValueError as exc:
        estado.avisos.append(
            f"critic_review: erro na chamada LLM — {exc}. "
            "Mantendo candidatos originais sem revisão."
        )
        return estado  # Não bloquear o pipeline — aviso e continua

    estado.candidatos_raw = saida_revisada
    logger.info(
        "critic_review: revisão concluída — %d chars", len(saida_revisada)
    )

    return estado
