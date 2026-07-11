"""Auto-layout determinístico para diagramas BPMN.

Recebe um XML BPMN 2.0 contendo apenas os elementos semânticos do processo
(startEvent, task, gateway, sequenceFlow, participant/pool, lane/raia,
textAnnotation, ...) — sem bpmndi:BPMNDiagram — e devolve o mesmo XML com um
bloco bpmndi:BPMNDiagram calculado em Python (sem depender do LLM para gerar
coordenadas).

Isso substitui a antiga estratégia de pedir ao Gemini para calcular x/y/waypoints
diretamente no prompt: reduz tokens de saída (o layout costumava ser ~metade do
XML devolvido), elimina sobreposições de forma por construção (grade sem
colisão) e corta os retries causados por erros de layout.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque

from lxml import etree

Box = tuple[int, int, int, int]  # (x, y, width, height)

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
_ANNOTATION_SIZE = (140, 60)
_BLACK_BOX_SIZE = (300, 100)

_HORIZONTAL_GAP = 150
_ROW_HEIGHT = 150
_X_MARGIN = 100
_Y_BASE = 160

_LANE_SUBROW_HEIGHT = 120
_LANE_PADDING = 40
_LANE_MIN_HEIGHT = _LANE_SUBROW_HEIGHT + 2 * _LANE_PADDING
_POOL_MARGIN = 40
_POOL_TOP = 60
_BLACK_BOX_GAP = 40
_ANNOTATION_STRIP_HEIGHT = 100
_ANNOTATION_GAP = 30


class LayoutError(Exception):
    """Erro ao calcular ou injetar o layout automático do diagrama."""


def _local_tag(el: etree._Element) -> str:
    return el.tag.split("}")[-1]


def _node_size(tag: str) -> tuple[int, int]:
    if tag in _EVENT_TAGS:
        return _EVENT_SIZE
    if tag in _GATEWAY_TAGS:
        return _GATEWAY_SIZE
    return _TASK_SIZE


def _parse_root(xml: str) -> etree._Element:
    try:
        return etree.fromstring(xml.encode())
    except etree.XMLSyntaxError as exc:
        raise LayoutError(f"XML malformado: {exc}") from exc


def _parse_graph(
    root: etree._Element,
) -> tuple[dict[str, str], list[tuple[str, str, str]]]:
    nodes: dict[str, str] = {}
    edges: list[tuple[str, str, str]] = []
    for el in root.iter():
        local = _local_tag(el)
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


def _parse_lanes(root: etree._Element) -> dict[str, list[str]]:
    """lane_id -> [ids dos nós atribuídos], na ordem em que as raias aparecem
    no XML (bpmn:laneSet/bpmn:lane/bpmn:flowNodeRef)."""
    lanes: dict[str, list[str]] = {}
    for lane_set in root.iter():
        if _local_tag(lane_set) != "laneSet":
            continue
        for lane in lane_set:
            if _local_tag(lane) != "lane":
                continue
            lane_id = lane.get("id")
            if not lane_id:
                continue
            refs = [
                child.text.strip()
                for child in lane
                if _local_tag(child) == "flowNodeRef" and child.text
            ]
            lanes[lane_id] = refs
    return lanes


def _parse_participants(
    root: etree._Element, process_id: str
) -> tuple[str | None, list[str]]:
    """Retorna (id do pool principal, [ids dos pools caixa-preta]).
    O pool principal é o participant cujo processRef aponta para o processo
    que contém os nós do fluxo; qualquer outro participant é tratado como
    pool caixa-preta (ator externo, sem elementos internos)."""
    main_pool: str | None = None
    black_boxes: list[str] = []
    for el in root.iter():
        if _local_tag(el) != "participant":
            continue
        pid = el.get("id")
        if not pid:
            continue
        if el.get("processRef") == process_id:
            main_pool = pid
        else:
            black_boxes.append(pid)
    return main_pool, black_boxes


def _parse_annotations(
    root: etree._Element,
) -> tuple[list[str], list[tuple[str, str, str]]]:
    annotations: list[str] = []
    associations: list[tuple[str, str, str]] = []
    for el in root.iter():
        local = _local_tag(el)
        el_id = el.get("id")
        if not el_id:
            continue
        if local == "textAnnotation":
            annotations.append(el_id)
        elif local == "association":
            src, tgt = el.get("sourceRef"), el.get("targetRef")
            if src and tgt:
                associations.append((el_id, src, tgt))
    return annotations, associations


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


def _node_shapes(
    nodes: dict[str, str],
    column: dict[str, int],
    row: dict[str, int],
    row_height: int = _ROW_HEIGHT,
    y_base: int = _Y_BASE,
) -> tuple[dict[str, Box], dict[int, int]]:
    col_width: dict[int, int] = defaultdict(lambda: _TASK_SIZE[0])
    for node, col in column.items():
        if node in nodes:
            col_width[col] = max(col_width[col], _node_size(nodes[node])[0])

    x_start: dict[int, int] = {}
    cursor = _X_MARGIN
    for col in sorted(col_width):
        x_start[col] = cursor
        cursor += col_width[col] + _HORIZONTAL_GAP

    shapes: dict[str, Box] = {}
    for node, tag in nodes.items():
        width, height = _node_size(tag)
        x = x_start[column[node]]
        y_center = y_base + row[node] * row_height
        y = y_center - height // 2
        shapes[node] = (x, y, width, height)

    return shapes, x_start


def _edges_geo(
    edges: list[tuple[str, str, str]], shapes: dict[str, Box]
) -> dict[str, tuple[int, int, int, int]]:
    edge_geo: dict[str, tuple[int, int, int, int]] = {}
    for flow_id, src, tgt in edges:
        if src not in shapes or tgt not in shapes:
            continue
        sx, sy, sw, sh = shapes[src]
        tx, ty, _tw, th = shapes[tgt]
        edge_geo[flow_id] = (sx + sw, sy + sh // 2, tx, ty + th // 2)
    return edge_geo


def _bounding_box(shapes: dict[str, Box]) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) da união de todas as shapes."""
    xs1 = [x for x, _y, _w, _h in shapes.values()]
    ys1 = [y for _x, y, _w, _h in shapes.values()]
    xs2 = [x + w for x, _y, w, _h in shapes.values()]
    ys2 = [y + h for _x, y, _w, h in shapes.values()]
    return min(xs1), min(ys1), max(xs2), max(ys2)


def _layout_lanes(
    nodes: dict[str, str],
    edges: list[tuple[str, str, str]],
    column: dict[str, int],
    lanes: dict[str, list[str]],
) -> tuple[dict[str, Box], dict[str, Box]]:
    """Layout com raias: cada raia vira uma faixa horizontal empilhada; a
    posição vertical de um nó vem da sua raia + uma sub-linha calculada
    localmente dentro dela (mesma lógica de _assign_rows, restrita às arestas
    internas da raia — arestas entre raias diferentes não influenciam a
    sub-linha, só a coluna global já cuida do alinhamento horizontal)."""
    node_lane: dict[str, str] = {}
    for lane_id, node_ids in lanes.items():
        for nid in node_ids:
            if nid in nodes:
                node_lane[nid] = lane_id

    lane_order = list(lanes.keys())
    lane_top: dict[str, int] = {}
    lane_height: dict[str, int] = {}
    node_row: dict[str, int] = {}

    cursor_y = _POOL_TOP
    for lane_id in lane_order:
        lane_nodes = {n: nodes[n] for n in nodes if node_lane.get(n) == lane_id}
        if lane_nodes:
            local_edges = [
                (fid, s, t)
                for (fid, s, t) in edges
                if s in lane_nodes and t in lane_nodes
            ]
            local_row = _assign_rows(lane_nodes, local_edges, column)
            node_row.update(local_row)
            max_subrow = max(local_row.values(), default=0)
            height = max(
                _LANE_MIN_HEIGHT,
                (max_subrow + 1) * _LANE_SUBROW_HEIGHT + 2 * _LANE_PADDING,
            )
        else:
            height = _LANE_MIN_HEIGHT

        lane_top[lane_id] = cursor_y
        lane_height[lane_id] = height
        cursor_y += height

    # Nós que não pertencem a nenhuma raia (ex.: erro do LLM) caem numa raia
    # implícita extra no final, para nunca perder um elemento do layout.
    orphans = {n: nodes[n] for n in nodes if n not in node_lane}
    if orphans:
        local_row = _assign_rows(orphans, [], column)
        node_row.update(local_row)
        max_subrow = max(local_row.values(), default=0)
        height = max(
            _LANE_MIN_HEIGHT, (max_subrow + 1) * _LANE_SUBROW_HEIGHT + 2 * _LANE_PADDING
        )
        lane_top["__orphans__"] = cursor_y
        lane_height["__orphans__"] = height
        for n in orphans:
            node_lane[n] = "__orphans__"
        cursor_y += height

    shapes, _x_start = _node_shapes(
        nodes, column, node_row, row_height=_LANE_SUBROW_HEIGHT, y_base=0
    )
    # _node_shapes calcula y_center = row * altura; precisamos deslocar cada
    # nó para dentro da faixa da sua raia.
    positioned: dict[str, Box] = {}
    for node, (x, _y, w, h) in shapes.items():
        lane_id = node_lane[node]
        subrow = node_row[node]
        y_center = (
            lane_top[lane_id]
            + _LANE_PADDING
            + subrow * _LANE_SUBROW_HEIGHT
            + (_LANE_SUBROW_HEIGHT // 2)
        )
        positioned[node] = (x, y_center - h // 2, w, h)

    all_lane_ids = [
        *lane_order,
        *(["__orphans__"] if "__orphans__" in lane_top else []),
    ]
    left, _t, right, _b = _bounding_box(positioned)
    pool_x = left - _POOL_MARGIN
    pool_width = (right - left) + 2 * _POOL_MARGIN
    lane_shapes: dict[str, Box] = {
        lane_id: (pool_x, lane_top[lane_id], pool_width, lane_height[lane_id])
        for lane_id in all_lane_ids
    }

    return positioned, lane_shapes


def _compute_layout(
    nodes: dict[str, str], edges: list[tuple[str, str, str]]
) -> tuple[dict[str, Box], dict[str, tuple[int, int, int, int]]]:
    column = _assign_columns(nodes, edges)
    row = _assign_rows(nodes, edges, column)
    shapes, _x_start = _node_shapes(nodes, column, row)
    edge_geo = _edges_geo(edges, shapes)
    return shapes, edge_geo


def _build_diagram_xml(
    process_id: str,
    shapes: dict[str, Box],
    edge_geo: dict[str, tuple[int, int, int, int]],
    container_ids: set[str] | None = None,
) -> str:
    container_ids = container_ids or set()
    shape_xml = "".join(
        f'<bpmndi:BPMNShape id="Shape_{node_id}" bpmnElement="{node_id}"'
        + (' isHorizontal="true"' if node_id in container_ids else "")
        + ">"
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
    root = _parse_root(xml)
    nodes, edges = _parse_graph(root)
    if not nodes:
        raise LayoutError(
            "Nenhum elemento reconhecível (startEvent/task/gateway/endEvent) "
            "encontrado no XML para calcular o layout."
        )

    process_id = _extract_process_id(xml)
    lanes = _parse_lanes(root)
    main_pool_id, black_box_pool_ids = _parse_participants(root, process_id)
    annotation_ids, associations = _parse_annotations(root)

    container_ids: set[str] = set()
    pool_shapes: dict[str, Box] = {}

    if lanes:
        column = _assign_columns(nodes, edges)
        shapes, lane_shapes = _layout_lanes(nodes, edges, column, lanes)
        edge_geo = _edges_geo(edges, shapes)

        # "__orphans__" é uma raia sintética só para o cálculo de posição de
        # nós sem bpmn:lane correspondente — não tem elemento semântico real
        # no XML, então não pode virar um bpmndi:BPMNShape próprio (ficaria
        # com bpmnElement apontando para um id inexistente). Ainda entra no
        # cálculo do bounding box do pool, para o pool continuar contendo
        # visualmente esses nós.
        real_lane_shapes = {
            k: v for k, v in lane_shapes.items() if not k.startswith("__")
        }
        pool_shapes.update(real_lane_shapes)
        container_ids.update(real_lane_shapes)

        if main_pool_id:
            lane_left, lane_top, lane_right, lane_bottom = _bounding_box(lane_shapes)
            pool_shapes[main_pool_id] = (
                lane_left - _POOL_MARGIN,
                lane_top - _POOL_MARGIN,
                (lane_right - lane_left) + 2 * _POOL_MARGIN,
                (lane_bottom - lane_top) + 2 * _POOL_MARGIN,
            )
            container_ids.add(main_pool_id)
    else:
        shapes, edge_geo = _compute_layout(nodes, edges)
        if main_pool_id:
            left, top, right, bottom = _bounding_box(shapes)
            pool_shapes[main_pool_id] = (
                left - _POOL_MARGIN,
                top - _POOL_MARGIN,
                (right - left) + 2 * _POOL_MARGIN,
                (bottom - top) + 2 * _POOL_MARGIN,
            )
            container_ids.add(main_pool_id)

    # Pools "caixa preta" (atores externos, sem elementos internos) — uma
    # abaixo da outra, acima de todo o resto, com a mesma largura do
    # conteúdo principal.
    all_content_shapes = {**shapes, **pool_shapes}
    black_box_shapes: dict[str, Box] = {}
    if black_box_pool_ids:
        left, top, right, _bottom = _bounding_box(all_content_shapes)
        width = max(right - left, _BLACK_BOX_SIZE[0])
        cursor_y = top - _BLACK_BOX_GAP - _BLACK_BOX_SIZE[1]
        for pid in black_box_pool_ids:
            black_box_shapes[pid] = (left, cursor_y, width, _BLACK_BOX_SIZE[1])
            container_ids.add(pid)
            cursor_y -= _BLACK_BOX_GAP + _BLACK_BOX_SIZE[1]

    # Normaliza para coordenadas não-negativas antes de tratar anotações.
    all_shapes = {**shapes, **pool_shapes, **black_box_shapes}
    _left, top, _right, _bottom = _bounding_box(all_shapes)
    if top < 0:
        dy = -top
        shapes = {k: (x, y + dy, w, h) for k, (x, y, w, h) in shapes.items()}
        pool_shapes = {k: (x, y + dy, w, h) for k, (x, y, w, h) in pool_shapes.items()}
        black_box_shapes = {
            k: (x, y + dy, w, h) for k, (x, y, w, h) in black_box_shapes.items()
        }
        edge_geo = {
            fid: (x1, y1 + dy, x2, y2 + dy)
            for fid, (x1, y1, x2, y2) in edge_geo.items()
        }

    association_geo: dict[str, tuple[int, int, int, int]] = {}
    annotation_shapes: dict[str, Box] = {}
    if annotation_ids:
        shapes = {
            k: (x, y + _ANNOTATION_STRIP_HEIGHT, w, h)
            for k, (x, y, w, h) in shapes.items()
        }
        pool_shapes = {
            k: (x, y + _ANNOTATION_STRIP_HEIGHT, w, h)
            for k, (x, y, w, h) in pool_shapes.items()
        }
        black_box_shapes = {
            k: (x, y + _ANNOTATION_STRIP_HEIGHT, w, h)
            for k, (x, y, w, h) in black_box_shapes.items()
        }
        edge_geo = {
            fid: (x1, y1 + _ANNOTATION_STRIP_HEIGHT, x2, y2 + _ANNOTATION_STRIP_HEIGHT)
            for fid, (x1, y1, x2, y2) in edge_geo.items()
        }

        cursor_x = _X_MARGIN
        for ann_id in annotation_ids:
            annotation_shapes[ann_id] = (
                cursor_x,
                0,
                _ANNOTATION_SIZE[0],
                _ANNOTATION_SIZE[1],
            )
            cursor_x += _ANNOTATION_SIZE[0] + _ANNOTATION_GAP

        all_shapes_for_assoc = {
            **shapes,
            **pool_shapes,
            **black_box_shapes,
            **annotation_shapes,
        }
        for assoc_id, src, tgt in associations:
            if src not in all_shapes_for_assoc or tgt not in all_shapes_for_assoc:
                continue
            sx, sy, sw, sh = all_shapes_for_assoc[src]
            tx, ty, tw, th = all_shapes_for_assoc[tgt]
            association_geo[assoc_id] = (
                sx + sw // 2,
                sy + sh // 2,
                tx + tw // 2,
                ty + th // 2,
            )

    all_shapes = {**shapes, **pool_shapes, **black_box_shapes, **annotation_shapes}
    all_edges = {**edge_geo, **association_geo}

    diagram_xml = _build_diagram_xml(process_id, all_shapes, all_edges, container_ids)

    xml = _ensure_di_namespaces(xml)

    match = re.search(r"</([\w]+):definitions>", xml) or re.search(
        r"</definitions>", xml
    )
    if not match:
        raise LayoutError("Não foi possível localizar o fechamento de <definitions>.")

    closing_tag = match.group(0)
    return xml.replace(closing_tag, diagram_xml + closing_tag, 1)
