"""
Nó LangGraph: parse_bpmn_to_json
Etapa 3 da Entrega 2 — Sprint 2

Responsabilidades (conforme documento da sprint, seções 4, 7 e 7.1):
  - Ler o .bpmn como XML BPMN 2.0 com defusedxml (parsing seguro, sem entidades externas)
  - Identificar: processo, raias, atividades, eventos, gateways,
    documentos (dataObjects), objetos de dados e sequência dos fluxos
  - Usar networkx para: ordenação topológica das atividades e detecção de loops
  - Produzir um ProcessoJSON validado por Pydantic v2
  - Salvar o JSON em /saidas/intermediarios/bpmn_estruturado.json
  - Registrar warnings no estado quando necessário
  - Nunca executar conteúdo enviado pelo usuário
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import defusedxml.ElementTree as ET
import networkx as nx

from app.schemas import (
    EdgeJSON,
    EstadoGrafo,
    NodeJSON,
    ProcessoJSON,
    TipoGateway,
    TipoNo,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Namespace BPMN 2.0 padrão
# ---------------------------------------------------------------------------
NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
_NS = f"{{{NS}}}"

# ---------------------------------------------------------------------------
# Mapeamento de tag XML → TipoNo
# ---------------------------------------------------------------------------
TAG_PARA_TIPO: dict[str, TipoNo] = {
    "task": TipoNo.ATIVIDADE,
    "userTask": TipoNo.ATIVIDADE,
    "serviceTask": TipoNo.ATIVIDADE,
    "manualTask": TipoNo.ATIVIDADE,
    "scriptTask": TipoNo.ATIVIDADE,
    "sendTask": TipoNo.ATIVIDADE,
    "receiveTask": TipoNo.ATIVIDADE,
    "businessRuleTask": TipoNo.ATIVIDADE,
    "callActivity": TipoNo.CHAMADA,
    "subProcess": TipoNo.SUBPROCESSO,
    "startEvent": TipoNo.EVENTO_INICIO,
    "endEvent": TipoNo.EVENTO_FIM,
    "intermediateCatchEvent": TipoNo.EVENTO_INTERMEDIARIO,
    "intermediateThrowEvent": TipoNo.EVENTO_INTERMEDIARIO,
    "exclusiveGateway": TipoNo.GATEWAY,
    "inclusiveGateway": TipoNo.GATEWAY,
    "parallelGateway": TipoNo.GATEWAY,
    "eventBasedGateway": TipoNo.GATEWAY,
    "complexGateway": TipoNo.GATEWAY,
    "dataObject": TipoNo.OBJETO_DADO,
    "dataObjectReference": TipoNo.OBJETO_DADO,
}

TAG_PARA_GATEWAY: dict[str, TipoGateway] = {
    "exclusiveGateway": TipoGateway.EXCLUSIVO,
    "inclusiveGateway": TipoGateway.INCLUSIVO,
    "parallelGateway": TipoGateway.PARALELO,
    "eventBasedGateway": TipoGateway.BASEADO_EVENTO,
    "complexGateway": TipoGateway.COMPLEXO,
}

# Tags visuais/diagramáticas a ignorar (seção 6.1 do documento: "removendo elementos visuais")
TAGS_VISUAIS = {
    "BPMNDiagram", "BPMNPlane", "BPMNShape", "BPMNEdge",
    "BPMNLabel", "BPMNLabelStyle", "Bounds", "Font", "waypoint",
}

TAGS_IGNORADAS = TAGS_VISUAIS | {
    "documentation", "extensionElements", "definitions", "process",
    "laneSet", "lane", "childLaneSet", "collaboration", "participant",
    "dataState", "ioSpecification", "inputSet", "outputSet",
}


# ---------------------------------------------------------------------------
# Extração de shapes do diagrama para resolver atribuição de lane
# (BPMNs exportados pelo Bizagi não usam flowNodeRef; a associação
#  lane ↔ nó é inferida pelas coordenadas Y dos BPMNShapes)
# ---------------------------------------------------------------------------

def _extrair_shapes(root: Any) -> dict[str, dict]:
    """
    Percorre todos os BPMNShape e coleta suas Bounds.
    Retorna {bpmnElement_id: {y, h, x, w, y_center}}.
    """
    shapes: dict[str, dict] = {}
    for el in root.iter():
        tag = el.tag.split("}", 1)[1] if "}" in el.tag else el.tag
        if tag != "BPMNShape":
            continue
        bpmn_el = el.attrib.get("bpmnElement", "")
        if not bpmn_el:
            continue
        for child in el:
            ctag = child.tag.split("}", 1)[1] if "}" in child.tag else child.tag
            if ctag == "Bounds":
                try:
                    y = float(child.attrib.get("y", 0))
                    h = float(child.attrib.get("height", 0))
                    x = float(child.attrib.get("x", 0))
                    w = float(child.attrib.get("width", 0))
                    shapes[bpmn_el] = {
                        "y": y, "h": h, "x": x, "w": w,
                        "y_center": y + h / 2,
                    }
                except (ValueError, TypeError):
                    pass
    return shapes


def _construir_mapa_lane_por_coordenadas(
    process_el: Any,
    root: Any,
) -> dict[str, str]:
    """
    Constrói {node_id: lane_name} usando coordenadas Y dos BPMNShapes.

    Para cada lane, obtém seu intervalo [y, y+h] via BPMNShape.
    Para cada nó, verifica se seu y_center cai dentro do intervalo de alguma lane.
    Este método é necessário para BPMNs gerados pelo Bizagi, que não usam
    o elemento flowNodeRef padrão do BPMN 2.0.
    """
    shapes = _extrair_shapes(root)

    # Coletar lanes e seus intervalos Y
    lanes_intervalos: list[tuple[str, str, float, float]] = []  # (lane_id, lane_name, y_min, y_max)
    for lane_set in process_el.iter(f"{_NS}laneSet"):
        for lane in lane_set.iter(f"{_NS}lane"):
            lane_id = lane.get("id", "")
            lane_name = lane.get("name", "")
            if lane_id in shapes:
                s = shapes[lane_id]
                lanes_intervalos.append((lane_id, lane_name, s["y"], s["y"] + s["h"]))

    mapa: dict[str, str] = {}
    for node_id, shape in shapes.items():
        # Ignorar os próprios shapes de lane
        if any(node_id == lid for lid, _, _, _ in lanes_intervalos):
            continue
        y_c = shape["y_center"]
        for lane_id, lane_name, y_min, y_max in lanes_intervalos:
            if y_min <= y_c <= y_max:
                mapa[node_id] = lane_name
                break

    # Fallback: tentar flowNodeRef padrão para BPMNs que o implementam
    for lane_set in process_el.iter(f"{_NS}laneSet"):
        for lane in lane_set.iter(f"{_NS}lane"):
            lane_name = lane.get("name", "")
            for ref in lane.iter(f"{_NS}flowNodeRef"):
                if ref.text:
                    node_ref = ref.text.strip()
                    if node_ref not in mapa:
                        mapa[node_ref] = lane_name

    return mapa


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def _tag_local(element: Any) -> str:
    tag = element.tag
    return tag.split("}", 1)[1] if "}" in tag else tag


def _nome(element: Any) -> str:
    return (element.get("name") or "").strip()


def _id(element: Any) -> str:
    return element.get("id", "")


def _textos_filhos(element: Any, tag: str) -> list[str]:
    return [
        child.text.strip()
        for child in element
        if _tag_local(child) == tag and child.text
    ]


def _extrair_data_objects(process_el: Any) -> tuple[list[str], set[str]]:
    """Retorna (nomes_legíveis, conjunto_de_ids) dos objetos de dados."""
    nomes: list[str] = []
    ids: set[str] = set()
    for tag in ("dataObject", "dataObjectReference"):
        for el in process_el.iter(f"{_NS}{tag}"):
            eid = _id(el)
            nome = _nome(el)
            ids.add(eid)
            if nome and nome not in nomes:
                nomes.append(nome)
    return nomes, ids


def _extrair_edges(process_el: Any) -> list[EdgeJSON]:
    edges: list[EdgeJSON] = []
    for sf in process_el.iter(f"{_NS}sequenceFlow"):
        edge_id = _id(sf)
        source = sf.get("sourceRef", "")
        target = sf.get("targetRef", "")
        label = _nome(sf) or None
        condicao: str | None = None
        cond_el = sf.find(f"{_NS}conditionExpression")
        if cond_el is not None and cond_el.text:
            condicao = cond_el.text.strip()
        elif label:
            condicao = label
        edges.append(EdgeJSON(
            id=edge_id, source=source, target=target,
            label=label, condicao=condicao,
        ))
    return edges


def _extrair_nos(
    process_el: Any,
    mapa_lane: dict[str, str],
    data_objects_ids: set[str],
    edges_map: dict[str, tuple[str, str]],
) -> list[NodeJSON]:
    nos: list[NodeJSON] = []
    vistos: set[str] = set()

    for element in process_el.iter():
        tag = _tag_local(element)
        if tag in TAGS_IGNORADAS:
            continue
        tipo = TAG_PARA_TIPO.get(tag)
        if tipo is None:
            continue
        node_id = _id(element)
        if not node_id or node_id in vistos:
            continue
        vistos.add(node_id)

        entradas_flow = _textos_filhos(element, "incoming")
        saidas_flow = _textos_filhos(element, "outgoing")
        entradas_nos = [edges_map[f][0] for f in entradas_flow if f in edges_map]
        saidas_nos = [edges_map[f][1] for f in saidas_flow if f in edges_map]

        # dataOutputAssociation → documentos relacionados (por nome, não ID)
        docs_relacionados: list[str] = []
        for assoc in element.iter(f"{_NS}dataOutputAssociation"):
            for target_ref in assoc.iter(f"{_NS}targetRef"):
                if target_ref.text:
                    ref_id = target_ref.text.strip()
                    # Tentar resolver ID → nome via dataObjects no processo
                    nome_doc = _resolver_nome_objeto(process_el, ref_id)
                    if nome_doc and nome_doc not in docs_relacionados:
                        docs_relacionados.append(nome_doc)
                    elif ref_id not in docs_relacionados:
                        docs_relacionados.append(ref_id)

        nos.append(NodeJSON(
            id=node_id,
            tipo=tipo,
            nome=_nome(element) or tag,
            lane=mapa_lane.get(node_id),
            documentos_relacionados=docs_relacionados,
            entradas=entradas_nos,
            saidas=saidas_nos,
            observacoes=None,
        ))

    return nos


def _resolver_nome_objeto(process_el: Any, ref_id: str) -> str | None:
    """Resolve um ID de dataObject/dataObjectReference para seu nome legível."""
    for tag in ("dataObject", "dataObjectReference"):
        for el in process_el.iter(f"{_NS}{tag}"):
            if _id(el) == ref_id:
                nome = _nome(el)
                return nome if nome else None
    return None


def _extrair_gateways(process_el: Any, edges: list[EdgeJSON]) -> list[dict]:
    edge_labels_por_source: dict[str, list[str]] = {}
    for e in edges:
        edge_labels_por_source.setdefault(e.source, [])
        if e.label:
            edge_labels_por_source[e.source].append(e.label)

    gateways: list[dict] = []
    for tag, tipo_gw in TAG_PARA_GATEWAY.items():
        for gw in process_el.iter(f"{_NS}{tag}"):
            gw_id = _id(gw)
            gateways.append({
                "id": gw_id,
                "tipo": tipo_gw.value,
                "nome": _nome(gw) or tag,
                "condicoes_saida": edge_labels_por_source.get(gw_id, []),
            })
    return gateways


def _analisar_grafo(
    nos: list[NodeJSON],
    edges: list[EdgeJSON],
) -> tuple[list[list[str]], list[str]]:
    G = nx.DiGraph()
    ids_nos = {n.id for n in nos}
    G.add_nodes_from(ids_nos)
    for e in edges:
        if e.source in ids_nos and e.target in ids_nos:
            G.add_edge(e.source, e.target)

    loops: list[list[str]] = []
    try:
        loops = list(nx.simple_cycles(G))
    except Exception as exc:
        logger.warning("Erro ao detectar ciclos: %s", exc)

    atividades_ordenadas: list[str] = []
    if not loops:
        try:
            atividades_ordenadas = list(nx.topological_sort(G))
        except nx.NetworkXUnfeasible:
            logger.warning("Ordenação topológica não possível: grafo contém ciclos.")
    else:
        logger.warning(
            "Processo contém %d ciclo(s). Ordenação topológica parcial omitida.", len(loops)
        )

    return loops, atividades_ordenadas


# ---------------------------------------------------------------------------
# Função principal de parsing
# ---------------------------------------------------------------------------

def parsear_bpmn(caminho_bpmn: str | Path) -> tuple[ProcessoJSON, list[str]]:
    """
    Lê um arquivo .bpmn e retorna (ProcessoJSON, lista_de_avisos).

    Usa defusedxml para parsing seguro (sem entidades externas, sem XXE).
    Compatível com BPMNs exportados pelo Bizagi Modeler (que não usam flowNodeRef).
    """
    caminho = Path(caminho_bpmn)
    avisos: list[str] = []

    try:
        tree = ET.parse(str(caminho))
    except ET.ParseError as exc:
        raise ValueError(f"Arquivo BPMN inválido ou malformado: {exc}") from exc

    root = tree.getroot()

    # Selecionar o processo com mais conteúdo (ignora o processo vazio de colaboração)
    processos = root.findall(f"{_NS}process") or root.findall("process")
    if not processos:
        raise ValueError("Nenhum elemento <process> encontrado no BPMN.")

    processo_el = max(processos, key=lambda p: len(list(p.iter())))
    process_id = _id(processo_el)
    # Fallback: usar nome do arquivo sem extensão quando o BPMN não define name
    nome_do_arquivo = caminho.stem.replace("-", " ").replace("_", " ").title()
    process_nome = _nome(processo_el) or nome_do_arquivo

    # Raias
    lanes: list[str] = []
    for lane_set in processo_el.iter(f"{_NS}laneSet"):
        for lane in lane_set.iter(f"{_NS}lane"):
            nome_lane = _nome(lane)
            if nome_lane and nome_lane not in lanes:
                lanes.append(nome_lane)
    if not lanes:
        avisos.append("Nenhuma raia (lane) identificada no processo.")

    # Mapa lane por coordenadas Y (compatível com Bizagi)
    mapa_lane = _construir_mapa_lane_por_coordenadas(processo_el, root)

    # Data Objects
    data_objects, data_objects_ids = _extrair_data_objects(processo_el)

    # Edges
    edges = _extrair_edges(processo_el)
    edges_map: dict[str, tuple[str, str]] = {e.id: (e.source, e.target) for e in edges}

    # Nós
    nos = _extrair_nos(processo_el, mapa_lane, data_objects_ids, edges_map)
    if not nos:
        avisos.append("Nenhum nó (atividade, evento, gateway) extraído do processo.")

    # Gateways
    gateways = _extrair_gateways(processo_el, edges)

    # Análise de grafo
    loops_detectados, atividades_ordenadas = _analisar_grafo(nos, edges)
    if loops_detectados:
        avisos.append(
            f"Processo contém {len(loops_detectados)} ciclo(s) detectado(s) pelo networkx."
        )

    logger.debug(
        "parse_bpmn: %d nós | %d edges | %d gateways | lanes=%s",
        len(nos), len(edges), len(gateways), lanes,
    )
    logger.debug(
        "parse_bpmn: atividades=%s",
        [n.nome for n in nos if n.tipo.value == "atividade"],
    )
    processo_json = ProcessoJSON(
        process_id=process_id,
        nome=process_nome,
        origem_arquivo=caminho.name,
        lanes=lanes,
        nodes=nos,
        edges=edges,
        data_objects=data_objects,
        gateways=gateways,
        loops_detectados=loops_detectados,
        atividades_ordenadas=atividades_ordenadas,
    )

    return processo_json, avisos


# ---------------------------------------------------------------------------
# Nó do LangGraph
# ---------------------------------------------------------------------------

def parse_bpmn_to_json(estado: EstadoGrafo) -> EstadoGrafo:
    """
    Nó LangGraph: parseia o BPMN e popula estado.processo_json.
    Salva intermediário em /saidas/intermediarios/bpmn_estruturado.json.
    """
    caminho = estado.caminho_bpmn
    if not caminho:
        estado.erros.append("parse_bpmn_to_json: caminho_bpmn não definido no estado.")
        return estado
    if not os.path.isfile(caminho):
        estado.erros.append(f"parse_bpmn_to_json: arquivo não encontrado — {caminho}")
        return estado

    try:
        processo_json, avisos = parsear_bpmn(caminho)
    except ValueError as exc:
        estado.erros.append(f"parse_bpmn_to_json: erro de parsing — {exc}")
        return estado
    except Exception as exc:
        estado.erros.append(f"parse_bpmn_to_json: erro inesperado — {exc}")
        return estado

    estado.avisos.extend(avisos)

    # Salvar intermediário
    saida_dir = Path("saidas/intermediarios")
    saida_dir.mkdir(parents=True, exist_ok=True)
    saida_path = saida_dir / "bpmn_estruturado.json"
    try:
        with open(saida_path, "w", encoding="utf-8") as f:
            json.dump(processo_json.model_dump(), f, ensure_ascii=False, indent=2)
        estado.artefatos["bpmn_estruturado"] = str(saida_path)
        logger.info("bpmn_estruturado.json salvo em %s", saida_path)
    except OSError as exc:
        estado.avisos.append(f"parse_bpmn_to_json: não foi possível salvar intermediário — {exc}")

    estado.processo_json = processo_json
    return estado
