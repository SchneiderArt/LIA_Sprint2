from pathlib import Path
from xml.etree import ElementTree as ET
import defusedxml.ElementTree as defused_ET
import networkx as nx

from app.schemas.modelos import EstadoGrafo, ProcessoJSON, NoJSON, ArestaJSON
from app.agente.logger import get_logger

logger = get_logger(__name__)

# Namespaces comuns no BPMN 2.0
NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmn2": "http://www.omg.org/spec/BPMN/20100524/MODEL",
}


def _tag_local(element: ET.Element) -> str:
    """Remove namespace da tag, retornando só o nome local."""
    return element.tag.split("}")[-1] if "}" in element.tag else element.tag


def analisar_bpmn(estado: EstadoGrafo) -> dict:
    """Lê o arquivo BPMN, extrai nós, arestas, raias e gateways."""
    caminho = Path(estado.caminho_bpmn)
    avisos = list(estado.avisos)

    arvore = defused_ET.parse(str(caminho))
    raiz = arvore.getroot()

    # Salva XML normalizado (sem elementos visuais)
    xml_normalizado = ET.tostring(raiz, encoding="unicode")

    nos: list[NoJSON] = []
    arestas: list[ArestaJSON] = []
    raias: list[str] = []
    gateways: list[str] = []
    objetos_de_dados: list[str] = []
    mapa_raia: dict[str, str] = {}  # elemento_id → nome_raia

    # Descobre raias (lanes)
    for lane in raiz.iter():
        if _tag_local(lane) == "lane":
            nome_raia = lane.get("name", lane.get("id", "Sem nome"))
            raias.append(nome_raia)
            for ref in lane:
                if _tag_local(ref) == "flowNodeRef":
                    mapa_raia[ref.text or ""] = nome_raia

    # Descobre nós
    tipos_no = {
        "task", "userTask", "serviceTask", "manualTask", "scriptTask",
        "sendTask", "receiveTask", "businessRuleTask", "callActivity",
        "subProcess", "startEvent", "endEvent", "intermediateCatchEvent",
        "intermediateThrowEvent", "boundaryEvent",
    }
    tipos_gateway = {
        "exclusiveGateway", "inclusiveGateway", "parallelGateway",
        "eventBasedGateway", "complexGateway",
    }

    for elem in raiz.iter():
        tag = _tag_local(elem)
        elem_id = elem.get("id", "")
        nome = elem.get("name", "")

        if tag in tipos_no:
            nos.append(NoJSON(
                id=elem_id,
                tipo=tag,
                nome=nome or elem_id,
                raia=mapa_raia.get(elem_id, "Desconhecida"),
            ))
        elif tag in tipos_gateway:
            label = f"{nome} ({tag})" if nome else tag
            gateways.append(label)
            nos.append(NoJSON(
                id=elem_id,
                tipo=tag,
                nome=nome or tag,
                raia=mapa_raia.get(elem_id, "Desconhecida"),
            ))
        elif tag == "dataObject" or tag == "dataObjectReference":
            objetos_de_dados.append(nome or elem_id)
        elif tag == "sequenceFlow":
            arestas.append(ArestaJSON(
                id=elem_id,
                origem=elem.get("sourceRef", ""),
                destino=elem.get("targetRef", ""),
                rotulo=nome,
                condicao="",
            ))

    # Detecta loops com networkx
    grafo = nx.DiGraph()
    for a in arestas:
        grafo.add_edge(a.origem, a.destino)
    loops_detectados = [str(ciclo) for ciclo in nx.simple_cycles(grafo)]

    # Ordem topológica das atividades (ignora ciclos)
    try:
        ordem = list(nx.topological_sort(grafo))
        mapa_nos = {n.id: n.nome for n in nos}
        atividades_ordenadas = [mapa_nos[i] for i in ordem if i in mapa_nos]
    except nx.NetworkXUnfeasible:
        atividades_ordenadas = [n.nome for n in nos]
        avisos.append("Ciclo detectado no BPMN — ordenação topológica não foi possível.")

    processo_json = ProcessoJSON(
        process_id=raiz.get("id", caminho.stem),
        nome=raiz.get("name", caminho.stem),
        origem_arquivo=caminho.name,
        raias=raias,
        nos=nos,
        arestas=arestas,
        objetos_de_dados=objetos_de_dados,
        gateways=gateways,
        loops_detectados=loops_detectados,
        atividades_ordenadas=atividades_ordenadas,
    )

    logger.info(
        "analisar_bpmn | %d nós, %d arestas, %d raias",
        len(nos), len(arestas), len(raias),
    )

    return {
        "xml_normalizado": xml_normalizado,
        "processo_json": processo_json,
        "avisos": avisos,
    }
