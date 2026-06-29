"""
app/openrouter.py — Cliente OpenRouter centralizado
Sprint 2, Entrega 2

Conforme documento da sprint:
  - Seção 11: "Fornecedor LLM: OpenRouter — Acesso padronizado aos modelos de linguagem"
  - Seção 11: "Execução Docker e .env — Ambiente reprodutível sem vazar chave do OpenRouter"
  - Seção 12: "Integração OpenRouter — Chamada de LLM parametrizada por .env e documentada"
  - Seção 11.1: OpenRouter quickstart — https://openrouter.ai/docs/quickstart

Implementação baseada no quickstart oficial do OpenRouter:
  O OpenRouter é compatível com a API da OpenAI. Basta apontar o base_url
  para https://openrouter.ai/api/v1 e usar o SDK openai normalmente.

Uso nos nós do LangGraph:
    from app.openrouter import chamar_llm

    resposta = chamar_llm(
        system_prompt="Você é um especialista em...",
        user_prompt="Analise este processo...",
    )
"""

from __future__ import annotations

import logging
import os

from openai import OpenAI, APIStatusError, APIConnectionError, APITimeoutError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração via .env — nunca hardcoded (seção 11)
# Todas as variáveis têm valores padrão documentados para facilitar setup
# ---------------------------------------------------------------------------

OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL    = os.getenv("OPENROUTER_MODEL",    "openai/gpt-4o-mini")
OPENROUTER_TIMEOUT  = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "120"))

# Headers de identificação recomendados pelo OpenRouter
# (permitem rastrear uso no dashboard e evitar bloqueios de rate limit)
OPENROUTER_APP_URL  = os.getenv("OPENROUTER_APP_URL",  "https://github.com/ufms-sprint2")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "UFMS Apoia MDA Sprint 2")


def _get_client() -> OpenAI:
    """
    Cria e retorna um cliente OpenAI apontado para o OpenRouter.

    Conforme OpenRouter quickstart (https://openrouter.ai/docs/quickstart):
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
    """
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY.startswith("sk-or-v1-substitua"):
        raise ValueError(
            "OPENROUTER_API_KEY não configurada. "
            "Abra o arquivo .env e substitua o placeholder pela sua chave real. "
            "Obtenha sua chave em: https://openrouter.ai/keys"
        )

    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
        timeout=OPENROUTER_TIMEOUT,
        default_headers={
            # Headers recomendados pelo OpenRouter para identificação da aplicação
            "HTTP-Referer": OPENROUTER_APP_URL,
            "X-Title":      OPENROUTER_APP_NAME,
        },
    )


def chamar_llm(
    system_prompt: str,
    user_prompt: str,
    temperatura: float = 0.2,
    max_tokens: int = 8000,
    modelo: str | None = None,
) -> str:
    """
    Chama o LLM via OpenRouter e retorna o texto da resposta.

    Parâmetros configuráveis via .env:
        OPENROUTER_MODEL           — modelo padrão (ex: openai/gpt-4o-mini)
        OPENROUTER_TIMEOUT_SECONDS — timeout em segundos (padrão: 120)

    Args:
        system_prompt: prompt de sistema (papel do agente)
        user_prompt:   prompt de usuário (contexto + instrução)
        temperatura:   controla aleatoriedade (0.0 = determinístico, 1.0 = criativo)
        max_tokens:    limite de tokens na resposta
        modelo:        sobrescreve OPENROUTER_MODEL para esta chamada específica

    Returns:
        Texto completo da resposta do LLM.

    Raises:
        ValueError: se a chave não estiver configurada ou a API retornar erro.
    """
    modelo_usado = modelo or OPENROUTER_MODEL
    client = _get_client()

    logger.info(
        "openrouter: chamando LLM | model=%s | system=%d chars | user=%d chars | temp=%.1f",
        modelo_usado, len(system_prompt), len(user_prompt), temperatura,
    )

    try:
        resposta = client.chat.completions.create(
            model=modelo_usado,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=temperatura,
            max_tokens=max_tokens,
        )
    except APIStatusError as exc:
        raise ValueError(
            f"OpenRouter retornou erro HTTP {exc.status_code}: {exc.message}"
        ) from exc
    except APIConnectionError as exc:
        raise ValueError(
            f"Erro de conexão com OpenRouter: {exc}"
        ) from exc
    except APITimeoutError as exc:
        raise ValueError(
            f"Timeout na chamada ao OpenRouter (limite: {OPENROUTER_TIMEOUT}s): {exc}"
        ) from exc

    conteudo = resposta.choices[0].message.content or ""

    logger.info(
        "openrouter: resposta recebida | %d chars | model=%s | tokens_usados=%s",
        len(conteudo),
        resposta.model,
        resposta.usage.total_tokens if resposta.usage else "n/a",
    )

    return conteudo
