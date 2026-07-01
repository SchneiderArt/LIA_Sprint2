"""
Loader de prompts versionados — Sprint 2, Entrega 2

Os prompts ficam versionados em arquivos .md separados na pasta /prompts,
conforme exigido pela seção 10 do documento da sprint:

  prompts/system_automation_analyst.md
  prompts/bpmn_to_natural_language.md   (Entrega 1 — ambos os times)
  prompts/bpmn_to_json.md               (Entrega 2 — ambos os times)
  prompts/pdf_to_json.md                (Entrega 2 — ambos os times)
  prompts/generate_automation_candidates.md
  prompts/critic_review.md

Uso:
    from app.prompts import carregar_prompt, montar_contexto_json

    system  = carregar_prompt("system_automation_analyst")
    usuario = montar_contexto_json(processo_json, documento_pdf_json)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Diretório base dos prompts (relativo ao projeto)
PROMPTS_DIR = Path("prompts")

# Mapeamento nome_lógico → arquivo
ARQUIVOS_PROMPT: dict[str, str] = {
    "system_automation_analyst":    "system_automation_analyst.md",
    "bpmn_to_natural_language":     "bpmn_to_natural_language.md",
    "bpmn_to_json":                 "bpmn_to_json.md",
    "pdf_to_json":                  "pdf_to_json.md",
    "generate_automation_candidates": "generate_automation_candidates.md",
    "critic_review":                "critic_review.md",
}


def carregar_prompt(nome: str) -> str:
    """
    Carrega o conteúdo de um arquivo de prompt pelo nome lógico.

    Args:
        nome: chave lógica do prompt (ex: "system_automation_analyst")

    Returns:
        Conteúdo do arquivo .md como string.

    Raises:
        KeyError: se o nome não estiver mapeado.
        FileNotFoundError: se o arquivo não existir.
    """
    if nome not in ARQUIVOS_PROMPT:
        chaves = ", ".join(ARQUIVOS_PROMPT.keys())
        raise KeyError(
            f"Prompt '{nome}' não encontrado. Disponíveis: {chaves}"
        )

    caminho = PROMPTS_DIR / ARQUIVOS_PROMPT[nome]
    if not caminho.exists():
        raise FileNotFoundError(
            f"Arquivo de prompt não encontrado: {caminho}. "
            "Verifique se a pasta /prompts está presente e o arquivo foi criado."
        )

    return caminho.read_text(encoding="utf-8")


def montar_contexto_json(
    processo_json: Any,
    documento_pdf_json: Any,
) -> str:
    """
    Monta o contexto de usuário para o nó generate_automation_candidates.
    Combina ProcessoJSON e DocumentoPDFJSON em um único prompt de usuário,
    conforme o formato especificado no arquivo generate_automation_candidates.md.

    Args:
        processo_json: instância ou dict de ProcessoJSON.
        documento_pdf_json: instância ou dict de DocumentoPDFJSON.

    Returns:
        String de contexto formatada com tags [PROCESSO_JSON] e [DOCUMENTO_PDF_JSON].
    """
    # Aceitar tanto instâncias Pydantic quanto dicts
    if hasattr(processo_json, "model_dump"):
        proc_dict = processo_json.model_dump()
    else:
        proc_dict = dict(processo_json)

    if hasattr(documento_pdf_json, "model_dump"):
        doc_dict = documento_pdf_json.model_dump()
    else:
        doc_dict = dict(documento_pdf_json)

    proc_str = json.dumps(proc_dict, ensure_ascii=False, indent=2)
    doc_str  = json.dumps(doc_dict,  ensure_ascii=False, indent=2)

    return (
        f"[PROCESSO_JSON]\n{proc_str}\n[/PROCESSO_JSON]\n\n"
        f"[DOCUMENTO_PDF_JSON]\n{doc_str}\n[/DOCUMENTO_PDF_JSON]"
    )


def montar_contexto_critica(
    candidatos: list[Any],
    processo_json: Any = None,
    documento_pdf_json: Any = None,
    narrativa_bpmn: str | None = None,
    pdf_texto_extraido: str | None = None,
) -> str:
    """
    Monta o contexto para o nó critic_review.

    Aceita contexto de qualquer pipeline:
      - Entrega 2 (JSON):    processo_json + documento_pdf_json
      - Entrega 1 (natural): narrativa_bpmn + pdf_texto_extraido
    """
    cands_list = [
        c.model_dump() if hasattr(c, "model_dump") else dict(c)
        for c in candidatos
    ]
    cands_str = json.dumps(cands_list, ensure_ascii=False, indent=2)

    if processo_json is not None and documento_pdf_json is not None:
        proc_dict = processo_json.model_dump() if hasattr(processo_json, "model_dump") else dict(processo_json)
        doc_dict  = documento_pdf_json.model_dump() if hasattr(documento_pdf_json, "model_dump") else dict(documento_pdf_json)
        contexto_processo = (
            f"[PROCESSO_JSON]\n{json.dumps(proc_dict, ensure_ascii=False, indent=2)}\n[/PROCESSO_JSON]\n\n"
            f"[DOCUMENTO_PDF_JSON]\n{json.dumps(doc_dict, ensure_ascii=False, indent=2)}\n[/DOCUMENTO_PDF_JSON]"
        )
    else:
        narrativa  = narrativa_bpmn or ""
        texto_pdf  = pdf_texto_extraido or ""
        contexto_processo = (
            f"[NARRATIVA_BPMN]\n{narrativa}\n[/NARRATIVA_BPMN]\n\n"
            f"[TEXTO_PDF]\n{texto_pdf}\n[/TEXTO_PDF]"
        )

    return f"{contexto_processo}\n\n[CANDIDATOS]\n{cands_str}\n[/CANDIDATOS]"


def montar_prompt_reparo(
    candidatos_raw: str,
    erros_validacao: list[str],
) -> str:
    """
    Monta o prompt de reparo quando a validação Pydantic falha.
    Conforme seção 10: o LangGraph aciona reparo enviando a lista de erros
    de schema ao modelo e solicitando correção sem alterar conteúdo substantivo.

    Args:
        candidatos_raw: saída bruta do LLM que falhou na validação.
        erros_validacao: lista de erros retornados pelo Pydantic v2.

    Returns:
        String do prompt de reparo.
    """
    erros_str = "\n".join(f"- {e}" for e in erros_validacao)
    return (
        "A saída anterior falhou na validação de schema. "
        "Corrija **apenas os erros de schema** listados abaixo, "
        "sem alterar o conteúdo substantivo das automações.\n\n"
        f"## Erros de validação Pydantic\n{erros_str}\n\n"
        f"## Saída que deve ser corrigida\n{candidatos_raw}\n\n"
        "Responda somente com o JSON corrigido, sem texto adicional."
    )
