from lxml import etree


def validate_bpmn_xml(xml: str) -> tuple[bool, str]:
    """Returns (is_valid, error_message)."""
    if not xml or not xml.strip():
        return False, "XML vazio"

    try:
        root = etree.fromstring(xml.encode())
    except etree.XMLSyntaxError as exc:
        return False, f"XML malformado: {exc}"

    # Verifica se é um documento BPMN pela tag raiz ou namespace
    tag = root.tag.lower()
    nsmap_values = " ".join(str(v) for v in root.nsmap.values()).lower()
    if "bpmn" not in tag and "bpmn" not in nsmap_values:
        return False, "Não é um documento BPMN válido"

    # Coleta todas as tags sem namespace
    local_tags = {e.tag.split("}")[-1].lower() for e in root.iter()}

    if "startevent" not in local_tags:
        return False, "Falta startEvent"

    if "endevent" not in local_tags:
        return False, "Falta endEvent"

    ids = [e.get("id") for e in root.iter() if e.get("id")]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        return False, (
            "IDs duplicados encontrados: "
            f"{', '.join(sorted(duplicates))}. Cada elemento (incluindo bpmndi:BPMNShape "
            "e bpmndi:BPMNEdge) deve ter um id único, diferente do id do elemento "
            "semântico correspondente (ex: use 'Edge_SequenceFlow_1' em vez de "
            "'SequenceFlow_1' para o BPMNEdge)."
        )

    overlap_error = _find_shape_overlap(root)
    if overlap_error:
        return False, overlap_error

    return True, ""


def _find_shape_overlap(root: etree._Element) -> str:
    boxes: list[tuple[str, float, float, float, float]] = []
    for shape in root.iter():
        if not shape.tag.split("}")[-1] == "BPMNShape":
            continue
        bounds = next(
            (c for c in shape if c.tag.split("}")[-1] == "Bounds"), None
        )
        if bounds is None:
            continue
        element_id = shape.get("bpmnElement", shape.get("id", "?"))
        x, y = float(bounds.get("x", 0)), float(bounds.get("y", 0))
        w, h = float(bounds.get("width", 0)), float(bounds.get("height", 0))
        boxes.append((element_id, x, y, x + w, y + h))

    for i in range(len(boxes)):
        id_a, ax1, ay1, ax2, ay2 = boxes[i]
        for j in range(i + 1, len(boxes)):
            id_b, bx1, by1, bx2, by2 = boxes[j]
            overlap_x = min(ax2, bx2) - max(ax1, bx1)
            overlap_y = min(ay2, by2) - max(ay1, by1)
            if overlap_x > 0 and overlap_y > 0:
                return (
                    f"As formas '{id_a}' e '{id_b}' se sobrepõem no diagrama "
                    "(bpmndi:BPMNShape com Bounds colidindo). Recalcule as "
                    "posições x/y de todas as formas para que fiquem "
                    "espaçadas sem sobreposição."
                )
    return ""
