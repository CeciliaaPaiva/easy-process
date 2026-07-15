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

    combined_gateway_error = _find_combined_gateway(root)
    if combined_gateway_error:
        return False, combined_gateway_error

    return True, ""


_GATEWAY_TAGS = {
    "exclusivegateway",
    "parallelgateway",
    "inclusivegateway",
    "complexgateway",
    "eventbasedgateway",
}


def _find_combined_gateway(root: etree._Element) -> str:
    """Um gateway não deve acumular papel de junção (merge de ramos
    alternativos) e divisão (fork) na mesma forma. Isso é ambíguo em BPMN e
    quebra ferramentas de simulação/animação: se as entradas vêm de ramos
    mutuamente exclusivos, a segunda nunca chega, e o gateway trava esperando
    por ela para sempre em vez de abrir os ramos de saída."""
    for element in root.iter():
        tag = element.tag.split("}")[-1].lower()
        if tag not in _GATEWAY_TAGS:
            continue
        incoming = sum(1 for c in element if c.tag.split("}")[-1] == "incoming")
        outgoing = sum(1 for c in element if c.tag.split("}")[-1] == "outgoing")
        if incoming > 1 and outgoing > 1:
            return (
                f"O gateway '{element.get('id', '?')}' tem {incoming} entradas e "
                f"{outgoing} saídas ao mesmo tempo — um gateway não pode juntar "
                "ramos (merge) e abrir em paralelo/condicional (split) na mesma "
                "forma. Separe em dois gateways do mesmo tipo: um de junção "
                "(join, só com as entradas e uma única saída) seguido por um de "
                "divisão (split, uma única entrada e as saídas)."
            )
    return ""


def _find_shape_overlap(root: etree._Element) -> str:
    # Pools (bpmn:participant) e raias (bpmn:lane) são containers: por
    # definição da notação BPMN, a forma do pool SEMPRE visualmente contém
    # (logo, "sobrepõe" no sentido geométrico) as formas dos elementos do
    # processo dentro dele. Isso não é uma sobreposição inválida — é o
    # comportamento esperado. IDs desses elementos ficam de fora da checagem
    # de colisão par a par.
    container_ids = {
        e.get("id")
        for e in root.iter()
        if e.tag.split("}")[-1] in ("participant", "lane") and e.get("id")
    }

    boxes: list[tuple[str, float, float, float, float]] = []
    for shape in root.iter():
        if not shape.tag.split("}")[-1] == "BPMNShape":
            continue
        element_id = shape.get("bpmnElement", shape.get("id", "?"))
        if element_id in container_ids:
            continue
        bounds = next((c for c in shape if c.tag.split("}")[-1] == "Bounds"), None)
        if bounds is None:
            continue
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
