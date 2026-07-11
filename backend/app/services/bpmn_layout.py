"""Auto-layout determinístico para diagramas BPMN.

Recebe um XML BPMN 2.0 contendo apenas os elementos semânticos do processo
(startEvent, task, gateway, sequenceFlow, ...) — sem bpmndi:BPMNDiagram — e
devolve o mesmo XML com um bloco bpmndi:BPMNDiagram calculado em Python
(sem depender do LLM para gerar coordenadas).

Isso substitui a antiga estratégia de pedir ao Gemini para calcular x/y/waypoints
diretamente no prompt: reduz tokens de saída (o layout costumava ser ~metade do
XML devolvido), elimina sobreposições de forma por construção (grade sem
colisão) e corta os retries causados por erros de layout.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque

from lxml import etree

_DI_NAMESPACES = {
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc": "http://www.omg.org/spec/DD/20100524/DC",
    "di": "http://www.omg.org/spec/DD/20100524/DI",
}

_EVENT_TAGS = {
    "startEvent",
    "endEvent",
    "intermediateThrowEvent",
    "intermediateCatchEvent",
    "boundaryEvent",
}
_GATEWAY_TAGS = {
    "exclusiveGateway",
    "parallelGateway",
    "inclusiveGateway",
    "eventBasedGateway",
    "complexGateway",
}
_TASK_TAGS = {
    "task",
    "userTask",
    "serviceTask",
    "scriptTask",
    "manualTask",
    "businessRuleTask",
    "sendTask",
    "receiveTask",
    "subProcess",
    "callActivity",
}
_NODE_TAGS = _EVENT_TAGS | _GATEWAY_TAGS | _TASK_TAGS

_EVENT_SIZE = (36, 36)
_GATEWAY_SIZE = (50, 50)
_TASK_SIZE = (100, 80)

_HORIZONTAL_GAP = 150
_ROW_HEIGHT = 150
_X_MARGIN = 100
_Y_BASE = 160


class LayoutError(Exception):
    """Erro ao calcular ou injetar o layout automático do diagrama."""


def _node_size(tag: str) -> tuple[int, int]:
    if tag in _EVENT_TAGS:
        return _EVENT_SIZE
    if tag in _GATEWAY_TAGS:
        return _GATEWAY_SIZE
    return _TASK_SIZE


def _parse_graph(xml: str) -> tuple[dict[str, str], list[tuple[str, str, str]]]:
    try:
        root = etree.fromstring(xml.encode())
    except etree.XMLSyntaxError as exc:
        raise LayoutError(f"XML malformado: {exc}") from exc

    nodes: dict[str, str] = {}
    edges: list[tuple[str, str, str]] = []
    for el in root.iter():
        local = el.tag.split("}")[-1]
        el_id = el.get("id")
        if not el_id:
            continue
        if local in _NODE_TAGS:
            nodes[el_id] = local
        elif local == "sequenceFlow":
            src, tgt = el.get("sourceRef"), el.get("targetRef")
            if src and tgt:
                edges.append((el_id, src, tgt))

    return nodes, edges


def _extract_process_id(xml: str) -> str:
    match = re.search(r'<[\w]+:process\b[^>]*\bid="([^"]+)"', xml)
    return match.group(1) if match else "Process_1"


def _assign_columns(
    nodes: dict[str, str], edges: list[tuple[str, str, str]]
) -> dict[str, int]:
    """BFS a partir dos startEvents (ou raízes sem entrada) — usa a distância
    mais curta como coluna. Nós já visitados não são reprocessados, então
    ciclos (loops de retrabalho/reprovação) não travam o cálculo."""
    adjacency: dict[str, list[str]] = defaultdict(list)
    has_incoming = set()
    for _flow_id, src, tgt in edges:
        adjacency[src].append(tgt)
        has_incoming.add(tgt)

    starts = [n for n, t in nodes.items() if t == "startEvent"]
    if not starts:
        starts = [n for n in nodes if n not in has_incoming]
    if not starts:
        starts = [next(iter(nodes))]

    column: dict[str, int] = {}
    visited = set(starts)
    queue: deque[tuple[str, int]] = deque((s, 0) for s in starts)

    while queue:
        node, col = queue.popleft()
        column[node] = col
        for target in adjacency.get(node, []):
            if target in nodes and target not in visited:
                visited.add(target)
                queue.append((target, col + 1))

    remaining = [n for n in nodes if n not in column]
    next_col = max(column.values(), default=-1) + 1
    for node in remaining:
        column[node] = next_col

    return column


def _assign_rows(
    nodes: dict[str, str],
    edges: list[tuple[str, str, str]],
    column: dict[str, int],
) -> dict[str, int]:
    """Nós tentam herdar a linha (row) do primeiro predecessor já posicionado —
    mantém o fluxo principal numa única linha horizontal; ramos de gateway
    ficam empurrados para a próxima linha livre na mesma coluna."""
    levels: dict[int, list[str]] = defaultdict(list)
    for node in sorted(nodes, key=lambda n: column[n]):
        levels[column[node]].append(node)

    row: dict[str, int] = {}
    for col in sorted(levels):
        used_rows: set[int] = set()
        for node in levels[col]:
            preds = [src for (_fid, src, tgt) in edges if tgt == node and src in row]
            preferred = row[preds[0]] if preds else 0
            r = preferred
            while r in used_rows:
                r += 1
            row[node] = r
            used_rows.add(r)

    return row


def _compute_layout(
    nodes: dict[str, str], edges: list[tuple[str, str, str]]
) -> tuple[dict[str, tuple[int, int, int, int]], dict[str, tuple[int, int, int, int]]]:
    column = _assign_columns(nodes, edges)
    row = _assign_rows(nodes, edges, column)

    col_width: dict[int, int] = defaultdict(lambda: _TASK_SIZE[0])
    for node, col in column.items():
        col_width[col] = max(col_width[col], _node_size(nodes[node])[0])

    x_start: dict[int, int] = {}
    cursor = _X_MARGIN
    for col in sorted(col_width):
        x_start[col] = cursor
        cursor += col_width[col] + _HORIZONTAL_GAP

    shapes: dict[str, tuple[int, int, int, int]] = {}
    for node, tag in nodes.items():
        width, height = _node_size(tag)
        x = x_start[column[node]]
        y_center = _Y_BASE + row[node] * _ROW_HEIGHT
        y = y_center - height // 2
        shapes[node] = (x, y, width, height)

    edge_geo: dict[str, tuple[int, int, int, int]] = {}
    for flow_id, src, tgt in edges:
        if src not in shapes or tgt not in shapes:
            continue
        sx, sy, sw, sh = shapes[src]
        tx, ty, _tw, th = shapes[tgt]
        edge_geo[flow_id] = (sx + sw, sy + sh // 2, tx, ty + th // 2)

    return shapes, edge_geo


def _build_diagram_xml(
    process_id: str,
    shapes: dict[str, tuple[int, int, int, int]],
    edge_geo: dict[str, tuple[int, int, int, int]],
) -> str:
    shape_xml = "".join(
        f'<bpmndi:BPMNShape id="Shape_{node_id}" bpmnElement="{node_id}">'
        f'<dc:Bounds x="{x}" y="{y}" width="{w}" height="{h}" />'
        "</bpmndi:BPMNShape>"
        for node_id, (x, y, w, h) in shapes.items()
    )
    edge_xml = "".join(
        f'<bpmndi:BPMNEdge id="Edge_{flow_id}" bpmnElement="{flow_id}">'
        f'<di:waypoint x="{x1}" y="{y1}" />'
        f'<di:waypoint x="{x2}" y="{y2}" />'
        "</bpmndi:BPMNEdge>"
        for flow_id, (x1, y1, x2, y2) in edge_geo.items()
    )
    return (
        '<bpmndi:BPMNDiagram id="BPMNDiagram_1">'
        f'<bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="{process_id}">'
        f"{shape_xml}{edge_xml}"
        "</bpmndi:BPMNPlane>"
        "</bpmndi:BPMNDiagram>"
    )


def _strip_existing_diagram(xml: str) -> str:
    return re.sub(
        r"<([\w]+):BPMNDiagram\b.*?</\1:BPMNDiagram>", "", xml, flags=re.DOTALL
    )


def _ensure_di_namespaces(xml: str) -> str:
    match = re.search(r"<([\w]+):definitions\b([^>]*)>", xml)
    if not match:
        return xml

    prefix, attrs = match.group(1), match.group(2)
    additions = [
        f'xmlns:{ns_prefix}="{uri}"'
        for ns_prefix, uri in _DI_NAMESPACES.items()
        if f"xmlns:{ns_prefix}" not in attrs
    ]
    if not additions:
        return xml

    new_tag = f"<{prefix}:definitions{attrs} {' '.join(additions)}>"
    return xml.replace(match.group(0), new_tag, 1)


def apply_layout(xml: str) -> str:
    """Calcula e injeta o bloco bpmndi:BPMNDiagram no XML BPMN semântico
    fornecido. Levanta LayoutError se o XML não puder ser processado."""
    xml = _strip_existing_diagram(xml)
    nodes, edges = _parse_graph(xml)
    if not nodes:
        raise LayoutError(
            "Nenhum elemento reconhecível (startEvent/task/gateway/endEvent) "
            "encontrado no XML para calcular o layout."
        )

    shapes, edge_geo = _compute_layout(nodes, edges)
    process_id = _extract_process_id(xml)
    diagram_xml = _build_diagram_xml(process_id, shapes, edge_geo)

    xml = _ensure_di_namespaces(xml)

    match = re.search(r"</([\w]+):definitions>", xml) or re.search(
        r"</definitions>", xml
    )
    if not match:
        raise LayoutError("Não foi possível localizar o fechamento de <definitions>.")

    closing_tag = match.group(0)
    return xml.replace(closing_tag, diagram_xml + closing_tag, 1)
