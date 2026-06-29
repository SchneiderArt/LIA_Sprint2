"""
Nós LangGraph: validate_schema e repair_output
Sprint 2, Entrega 2

Responsabilidades (conforme documento da sprint, seções 7.1, passo 9, e seção 10):

validate_schema:
  - Validar a saída do LLM com Pydantic v2 (seção 4, camada 5)
  - Se válida: popular estado.candidatos com lista de AutomationCandidateJSON
  - Se inválida: registrar erros em estado.erros_validacao e incrementar
    estado.tentativas_reparo

repair_output:
  - Enviar ao LLM a lista de erros de schema e solicitar correção (seção 10)
  - "sem alterar o conteúdo substantivo" (seção 10, citação direta)
  - Atualizar estado.candidatos_raw com a saída corrigida
  - Respeitar o limite MAX_REPAIR_ATTEMPTS do .env
"""

from __future__ import annotations

import json
import logging
import os
import re

from pydantic import ValidationError

from app.openrouter import chamar_llm
from app.prompts import carregar_prompt, montar_prompt_reparo
from app.schemas import AutomationCandidateJSON, EstadoGrafo

logger = logging.getLogger(__name__)

MAX_REPAIR_ATTEMPTS = int(os.getenv("MAX_REPAIR_ATTEMPTS", 3))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _limpar_json(texto: str) -> str:
    """Remove blocos de código markdown e texto antes do JSON."""
    texto = re.sub(r"```(?:json)?\s*", "", texto)
    texto = re.sub(r"```", "", texto)
    inicio = min(
        texto.find("[") if "[" in texto else len(texto),
        texto.find("{") if "{" in texto else len(texto),
    )
    if inicio < len(texto):
        texto = texto[inicio:]
    return texto.strip()


def _parsear_candidatos(texto: str) -> tuple[list[AutomationCandidateJSON], list[str]]:
    """
    Tenta parsear o texto JSON e validar com Pydantic v2.
    Retorna (lista_validada, lista_de_erros).
    """
    erros: list[str] = []
    texto_limpo = _limpar_json(texto)

    try:
        dados = json.loads(texto_limpo)
    except json.JSONDecodeError as exc:
        erros.append(f"JSON inválido: {exc}")
        return [], erros

    if isinstance(dados, dict):
        for chave in ("automacoes", "candidatos", "automations", "items", "data"):
            if chave in dados and isinstance(dados[chave], list):
                dados = dados[chave]
                break
        else:
            erros.append(
                "Saída do LLM é um objeto, não um array. "
                "Esperado: array de AutomationCandidateJSON."
            )
            return [], erros

    if not isinstance(dados, list):
        erros.append(
            f"Saída do LLM não é um array JSON. Tipo recebido: {type(dados).__name__}"
        )
        return [], erros

    if len(dados) == 0:
        erros.append("Array de automações está vazio.")
        return [], erros

    candidatos: list[AutomationCandidateJSON] = []
    for i, item in enumerate(dados):
        try:
            candidatos.append(AutomationCandidateJSON.model_validate(item))
        except ValidationError as exc:
            for err in exc.errors():
                campo    = " → ".join(str(loc) for loc in err["loc"])
                mensagem = err["msg"]
                erros.append(f"Item {i} | campo '{campo}': {mensagem}")

    return candidatos, erros


# ---------------------------------------------------------------------------
# Nó validate_schema
# ---------------------------------------------------------------------------

def validate_schema(estado: EstadoGrafo) -> EstadoGrafo:
    """
    Nó LangGraph: valida a saída do LLM com Pydantic v2.

    Se válida:  popula estado.candidatos e limpa estado.erros_validacao.
    Se inválida: registra erros em estado.erros_validacao e incrementa
                 estado.tentativas_reparo para acionar o nó repair_output.
    """
    if not estado.candidatos_raw:
        estado.erros.append("validate_schema: candidatos_raw ausente no estado.")
        return estado

    candidatos, erros = _parsear_candidatos(estado.candidatos_raw)

    if not erros:
        estado.candidatos      = candidatos
        estado.erros_validacao = []
        logger.info(
            "validate_schema: %d automações validadas com sucesso.", len(candidatos)
        )
    else:
        estado.erros_validacao  = erros
        estado.tentativas_reparo += 1
        logger.warning(
            "validate_schema: %d erro(s) de schema na tentativa %d/%d.",
            len(erros), estado.tentativas_reparo, MAX_REPAIR_ATTEMPTS,
        )
        if estado.tentativas_reparo >= MAX_REPAIR_ATTEMPTS:
            estado.erros.append(
                f"validate_schema: limite de {MAX_REPAIR_ATTEMPTS} tentativas de reparo "
                f"atingido. Erros: {erros}"
            )

    return estado


# ---------------------------------------------------------------------------
# Nó repair_output
# ---------------------------------------------------------------------------

def repair_output(estado: EstadoGrafo) -> EstadoGrafo:
    """
    Nó LangGraph: aciona o LLM para corrigir erros de schema.

    Conforme seção 10 do documento:
    "O LangGraph deve acionar um nó de reparo de saída, enviando ao modelo
     a lista de erros de schema e solicitando correção sem alterar o
     conteúdo substantivo."
    """
    if not estado.erros_validacao:
        estado.avisos.append("repair_output: chamado sem erros de validação.")
        return estado

    if not estado.candidatos_raw:
        estado.erros.append("repair_output: candidatos_raw ausente.")
        return estado

    try:
        system_prompt = carregar_prompt("system_automation_analyst")
    except (KeyError, FileNotFoundError) as exc:
        estado.erros.append(f"repair_output: erro ao carregar prompt — {exc}")
        return estado

    # Montar prompt de reparo (seção 10)
    user_prompt = montar_prompt_reparo(
        estado.candidatos_raw,
        estado.erros_validacao,
    )

    logger.info(
        "repair_output: tentativa %d/%d — %d erros a corrigir.",
        estado.tentativas_reparo, MAX_REPAIR_ATTEMPTS, len(estado.erros_validacao),
    )

    try:
        saida_reparada = chamar_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperatura=0.0,   # Zero temperatura no reparo — apenas corrigir schema
            max_tokens=8000,
        )
    except ValueError as exc:
        estado.erros.append(f"repair_output: erro na chamada LLM — {exc}")
        return estado

    estado.candidatos_raw = saida_reparada
    logger.info("repair_output: saída reparada — %d chars", len(saida_reparada))

    return estado
