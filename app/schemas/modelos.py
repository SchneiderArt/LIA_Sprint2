from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


# ── Schemas intermediários — BPMN ─────────────────────────────────────────────

class NoJSON(BaseModel):
    id: str
    tipo: str
    nome: str
    raia: str
    documentos_relacionados: list[str] = Field(default_factory=list)
    entradas: list[str] = Field(default_factory=list)
    saidas: list[str] = Field(default_factory=list)
    observacoes: str = ""


class ArestaJSON(BaseModel):
    id: str
    origem: str
    destino: str
    rotulo: str = ""
    condicao: str = ""


class ProcessoJSON(BaseModel):
    process_id: str
    nome: str
    origem_arquivo: str
    raias: list[str]
    nos: list[NoJSON]
    arestas: list[ArestaJSON]
    objetos_de_dados: list[str] = Field(default_factory=list)
    gateways: list[str] = Field(default_factory=list)
    loops_detectados: list[str] = Field(default_factory=list)
    atividades_ordenadas: list[str] = Field(default_factory=list)


# ── Schemas intermediários — PDF ──────────────────────────────────────────────

class DocumentoPDFJSON(BaseModel):
    titulo: str
    unidade_responsavel: str
    descricao: str
    procedimentos: list[str] = Field(default_factory=list)
    amparo_legal: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    indicadores: list[str] = Field(default_factory=list)
    metas: list[str] = Field(default_factory=list)
    responsaveis: list[str] = Field(default_factory=list)
    observacoes: str = ""


# ── Schema de saída — Automação candidata ────────────────────────────────────

class AutomacaoCandidataJSON(BaseModel):
    id: str
    nome: str
    atividades_envolvidas: list[str]
    tipo_automacao: Literal["RPA", "Agente de IA", "Híbrida", "API/Integração"]
    gatilho: str
    entradas: list[str]
    saidas: list[str]
    como_automatizar: str
    justificativa: str
    beneficios: list[str]
    impactos: list[str]
    riscos: list[str]
    metrica_de_sucesso: str
    prioridade: Literal["Baixa", "Média", "Alta", "Muito Alta"]
    prioridade_justificativa: str


class DocumentoAutomacoes(BaseModel):
    nome_processo: str
    arquivo_bpmn: str
    arquivo_pdf: str
    data_analise: str
    unidades_envolvidas: list[str]
    resumo_executivo: str
    automacoes: list[AutomacaoCandidataJSON]


# ── Estado do grafo LangGraph ─────────────────────────────────────────────────

class EstadoGrafo(BaseModel):
    # Entradas
    caminho_bpmn: str = ""
    caminho_pdf: str = ""
    pipeline: Literal["natural", "json", "both"] = "both"

    # Intermediários — Entrega 1 (linguagem natural)
    xml_normalizado: str = ""
    narrativa_bpmn: str = ""
    texto_pdf: str = ""

    # Intermediários — Entrega 2 (JSON estruturado)
    processo_json: ProcessoJSON | None = None
    documento_pdf_json: DocumentoPDFJSON | None = None

    # Prompt enviado ao LLM
    prompt_usado: str = ""

    # Saída validada
    documento_final: DocumentoAutomacoes | None = None

    # Controle
    erros_validacao: list[str] = Field(default_factory=list)
    tentativas_reparo: int = 0
    avisos: list[str] = Field(default_factory=list)
