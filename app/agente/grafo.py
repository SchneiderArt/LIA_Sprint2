from typing import Literal
from langgraph.graph import StateGraph, END

from app.schemas.modelos import EstadoGrafo
from app.agente.nos.ingestao_arquivos import ingestao_arquivos
from app.agente.nos.analisar_bpmn import analisar_bpmn
from app.agente.nos.extrair_pdf import extrair_pdf
from app.agente.nos.bpmn_para_linguagem_natural import bpmn_para_linguagem_natural
from app.agente.nos.pdf_para_json import pdf_para_json
from app.agente.nos.gerar_candidatas import gerar_candidatas
from app.agente.nos.revisar_critica import revisar_critica
from app.agente.nos.validar_schema import validar_schema
from app.agente.nos.renderizar_saidas import renderizar_saidas


def _decidir_apos_validacao(estado: EstadoGrafo) -> Literal["validar_schema", "renderizar_saidas"]:
    """Retorna ao nó de validação se ainda houver erros e tentativas disponíveis."""
    if estado.erros_validacao and estado.tentativas_reparo < 3:
        return "validar_schema"
    return "renderizar_saidas"


def construir_grafo() -> StateGraph:
    grafo = StateGraph(EstadoGrafo)

    grafo.add_node("ingestao_arquivos", ingestao_arquivos)
    grafo.add_node("analisar_bpmn", analisar_bpmn)
    grafo.add_node("extrair_pdf", extrair_pdf)
    grafo.add_node("bpmn_para_linguagem_natural", bpmn_para_linguagem_natural)
    grafo.add_node("pdf_para_json", pdf_para_json)
    grafo.add_node("gerar_candidatas", gerar_candidatas)
    grafo.add_node("revisar_critica", revisar_critica)
    grafo.add_node("validar_schema", validar_schema)
    grafo.add_node("renderizar_saidas", renderizar_saidas)

    grafo.set_entry_point("ingestao_arquivos")

    grafo.add_edge("ingestao_arquivos", "analisar_bpmn")
    grafo.add_edge("analisar_bpmn", "extrair_pdf")
    grafo.add_edge("extrair_pdf", "bpmn_para_linguagem_natural")
    grafo.add_edge("bpmn_para_linguagem_natural", "pdf_para_json")
    grafo.add_edge("pdf_para_json", "gerar_candidatas")
    grafo.add_edge("gerar_candidatas", "revisar_critica")
    grafo.add_edge("revisar_critica", "validar_schema")

    grafo.add_conditional_edges(
        "validar_schema",
        _decidir_apos_validacao,
        {
            "validar_schema": "validar_schema",
            "renderizar_saidas": "renderizar_saidas",
        },
    )

    grafo.add_edge("renderizar_saidas", END)

    return grafo.compile()
