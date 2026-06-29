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

    return True, ""
