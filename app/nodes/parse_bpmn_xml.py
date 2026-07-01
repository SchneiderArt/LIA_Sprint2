"""
Nó LangGraph: parse_bpmn_xml
Entrega 1 — Sprint 2 (responsabilidade: Davi Gaborim)

Lê o .bpmn como XML BPMN 2.0 com defusedxml (sem XXE), normaliza o
conteúdo e salva em /saidas/intermediarios/bpmn_normalizado.xml.

Normalização aplicada:
  - Resolve raia (lane) de cada nó. Os BPMNs de exemplo (exportados pelo
    Bizagi) não preenchem <flowNodeRef> nas lanes; a associação só existe
    via coordenadas no diagrama visual. Aqui essa associação é calculada
    e gravada como <flowNodeRef> de verdade, tornando o XML normalizado
    semanticamente completo mesmo depois de descartar o diagrama.
  - Remove o <BPMNDiagram> (coordenadas, formas, cores — só interessam
    para renderização gráfica).
  - Remove <extensionElements> (metadados proprietários do Bizagi: cor de
    fundo, cor de borda, etc. — não agregam à leitura do processo).
  - Remove o <process> vazio (pool-container sem atividades) e o
    <collaboration>, preservando o nome real do processo no <process>
    principal.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import defusedxml.ElementTree as DET
import xml.etree.ElementTree as ET

from app.schemas import EstadoGrafo

logger = logging.getLogger(__name__)

NS_MODEL = "http://www.omg.org/spec/BPMN/20100524/MODEL"
_NS = f"{{{NS_MODEL}}}"

TAGS_VISUAIS = {"BPMNDiagram", "BPMNPlane", "BPMNShape", "BPMNEdge", "BPMNLabel", "BPMNLabelStyle"}
TAGS_RUIDO = {"extensionElements"}


def _tag_local(el: Any) -> str:
    tag = el.tag
    return tag.split("}", 1)[1] if "}" in tag else tag


def _id(el: Any) -> str:
    return el.get("id", "")


def _nome(el: Any) -> str:
    return (el.get("name") or "").strip()


def _extrair_shapes(root: Any) -> dict[str, dict]:
    shapes: dict[str, dict] = {}
    for el in root.iter():
        if _tag_local(el) != "BPMNShape":
            continue
        bpmn_el = el.get("bpmnElement", "")
        if not bpmn_el:
            continue
        for child in el:
            if _tag_local(child) != "Bounds":
                continue
            try:
                y = float(child.get("y", 0))
                h = float(child.get("height", 0))
                shapes[bpmn_el] = {"y_center": y + h / 2}
            except (ValueError, TypeError):
                pass
    return shapes


def _ids_nos_validos(processo_el: Any) -> set[str]:
    """IDs de filhos diretos do processo que são nós de fluxo (não lane/edge/documentation)."""
    tags_excluidas = {"laneSet", "sequenceFlow", "documentation", "ioSpecification"}
    return {
        _id(c) for c in processo_el
        if _tag_local(c) not in tags_excluidas and _id(c)
    }


def _resolver_lanes(processo_el: Any, root: Any) -> dict[str, list[str]]:
    """
    Retorna {lane_id: [node_id, ...]} já existente (via flowNodeRef nativo)
    ou calculado por coordenada Y do diagrama quando o BPMN não preenche
    flowNodeRef (caso dos exemplos exportados pelo Bizagi).
    """
    lane_sets = list(processo_el.iter(f"{_NS}laneSet"))
    if not lane_sets:
        return {}

    ids_validos = _ids_nos_validos(processo_el)

    mapa: dict[str, list[str]] = {}
    lanes_sem_ref: list[Any] = []
    for lane_set in lane_sets:
        for lane in lane_set.iter(f"{_NS}lane"):
            refs = [r.text.strip() for r in lane.iter(f"{_NS}flowNodeRef") if r.text]
            if refs:
                mapa[_id(lane)] = refs
            else:
                lanes_sem_ref.append(lane)

    if not lanes_sem_ref:
        return mapa

    # Fallback por coordenadas (lanes do Bizagi sem flowNodeRef).
    # Só considera shapes cujo bpmnElement é um nó de fluxo real do processo
    # (evita capturar o shape do pool/participant, que também tem Bounds).
    shapes = {nid: s for nid, s in _extrair_shapes(root).items() if nid in ids_validos}
    lane_shapes = _extrair_shapes_lane(root, {_id(l) for l in lanes_sem_ref})
    for lane in lanes_sem_ref:
        lane_id = _id(lane)
        intervalo = lane_shapes.get(lane_id)
        if not intervalo:
            continue
        y_min, y_max = intervalo
        nos_da_lane = [
            node_id for node_id, s in shapes.items()
            if y_min <= s["y_center"] <= y_max
        ]
        if nos_da_lane:
            mapa[lane_id] = nos_da_lane
    return mapa


def _extrair_shapes_lane(root: Any, lane_ids: set[str]) -> dict[str, tuple[float, float]]:
    intervalos: dict[str, tuple[float, float]] = {}
    for el in root.iter():
        if _tag_local(el) != "BPMNShape":
            continue
        bpmn_el = el.get("bpmnElement", "")
        if bpmn_el not in lane_ids:
            continue
        for child in el:
            if _tag_local(child) != "Bounds":
                continue
            try:
                y = float(child.get("y", 0))
                h = float(child.get("height", 0))
                intervalos[bpmn_el] = (y, y + h)
            except (ValueError, TypeError):
                pass
    return intervalos


def _injetar_flow_node_refs(processo_el: Any, mapa_lanes: dict[str, list[str]]) -> None:
    for lane_set in processo_el.iter(f"{_NS}laneSet"):
        for lane in lane_set.iter(f"{_NS}lane"):
            lane_id = _id(lane)
            ja_tem = any(_tag_local(c) == "flowNodeRef" for c in lane)
            if ja_tem:
                continue
            for node_id in mapa_lanes.get(lane_id, []):
                ref = ET.SubElement(lane, f"{_NS}flowNodeRef")
                ref.text = node_id


def _remover_elementos(raiz: Any, tags_alvo: set[str]) -> None:
    """Remove, em qualquer profundidade, todos os elementos cuja tag local está em tags_alvo."""
    pais_por_filho: dict[Any, Any] = {p: c for p in raiz.iter() for c in list(p)}
    a_remover: list[tuple[Any, Any]] = []
    for el in raiz.iter():
        for filho in list(el):
            if _tag_local(filho) in tags_alvo:
                a_remover.append((el, filho))
    for pai, filho in a_remover:
        pai.remove(filho)


def _remover_documentacao_vazia(raiz: Any) -> None:
    a_remover: list[tuple[Any, Any]] = []
    for el in raiz.iter():
        for filho in list(el):
            if _tag_local(filho) == "documentation" and not (filho.text or "").strip():
                a_remover.append((el, filho))
    for pai, filho in a_remover:
        pai.remove(filho)


def _selecionar_processo_principal(root: Any) -> tuple[Any, list[Any]]:
    processos = root.findall(f"{_NS}process")
    if not processos:
        raise ValueError("Nenhum elemento <process> encontrado no BPMN.")
    processo_el = max(processos, key=lambda p: len(list(p.iter())))
    outros = [p for p in processos if p is not processo_el]
    return processo_el, outros


def _nome_processo(root: Any, processo_el: Any, caminho: Path) -> str:
    for colab in root.findall(f"{_NS}collaboration"):
        nome = _nome(colab)
        if nome:
            return nome
    if _nome(processo_el):
        return _nome(processo_el)
    return caminho.stem.replace("-", " ").replace("_", " ").title()


def normalizar_bpmn(caminho_bpmn: str | Path) -> tuple[str, str, list[str]]:
    """
    Lê e normaliza um arquivo .bpmn.

    Returns:
        (xml_normalizado, nome_processo, avisos)
    """
    caminho = Path(caminho_bpmn)
    avisos: list[str] = []

    try:
        tree = DET.parse(str(caminho))
    except DET.ParseError as exc:
        raise ValueError(f"Arquivo BPMN inválido ou malformado: {exc}") from exc

    root = tree.getroot()
    processo_el, outros_processos = _selecionar_processo_principal(root)
    nome_processo = _nome_processo(root, processo_el, caminho)

    mapa_lanes = _resolver_lanes(processo_el, root)
    _injetar_flow_node_refs(processo_el, mapa_lanes)

    if not list(processo_el.iter(f"{_NS}lane")):
        avisos.append("Nenhuma raia (lane) identificada no processo.")

    nos_no_processo = [
        n for n in processo_el.iter()
        if n is not processo_el and _tag_local(n) not in
        {"laneSet", "lane", "flowNodeRef", "documentation", "childLaneSet", "sequenceFlow"}
    ]
    if not nos_no_processo:
        avisos.append("Nenhum nó (atividade, evento, gateway) encontrado no processo.")

    # Remover processos-container vazios, collaboration e o diagrama visual
    for p in outros_processos:
        root.remove(p)
    for colab in root.findall(f"{_NS}collaboration"):
        root.remove(colab)
    for diagrama in [c for c in root if _tag_local(c) in TAGS_VISUAIS]:
        root.remove(diagrama)

    _remover_elementos(root, TAGS_RUIDO)
    _remover_documentacao_vazia(root)

    if _nome(processo_el) != nome_processo:
        processo_el.set("name", nome_processo)

    ET.register_namespace("", NS_MODEL)
    ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
    ET.register_namespace("xsd", "http://www.w3.org/2001/XMLSchema")
    ET.indent(tree, space="  ")

    xml_normalizado = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ET.tostring(root, encoding="unicode")
    )

    return xml_normalizado, nome_processo, avisos


def parse_bpmn_xml(estado: EstadoGrafo) -> EstadoGrafo:
    """
    Nó LangGraph: normaliza o BPMN e popula estado.bpmn_normalizado_xml.
    Salva o intermediário em /saidas/intermediarios/bpmn_normalizado.xml.
    """
    caminho = estado.caminho_bpmn
    if not caminho:
        estado.erros.append("parse_bpmn_xml: caminho_bpmn não definido no estado.")
        return estado
    if not os.path.isfile(caminho):
        estado.erros.append(f"parse_bpmn_xml: arquivo não encontrado — {caminho}")
        return estado

    try:
        xml_normalizado, nome_processo, avisos = normalizar_bpmn(caminho)
    except ValueError as exc:
        estado.erros.append(f"parse_bpmn_xml: erro de parsing — {exc}")
        return estado
    except Exception as exc:
        estado.erros.append(f"parse_bpmn_xml: erro inesperado — {exc}")
        return estado

    estado.avisos.extend(avisos)

    saida_dir = Path("saidas/intermediarios")
    saida_dir.mkdir(parents=True, exist_ok=True)
    saida_path = saida_dir / "bpmn_normalizado.xml"
    try:
        saida_path.write_text(xml_normalizado, encoding="utf-8")
        estado.artefatos["bpmn_normalizado"] = str(saida_path)
        logger.info("bpmn_normalizado.xml salvo em %s (processo: %s)", saida_path, nome_processo)
    except OSError as exc:
        estado.avisos.append(f"parse_bpmn_xml: não foi possível salvar intermediário — {exc}")

    estado.bpmn_normalizado_xml = xml_normalizado
    estado.artefatos["bpmn_nome_processo"] = nome_processo
    return estado
