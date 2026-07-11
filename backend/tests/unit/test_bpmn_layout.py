import pytest

from app.services.bpmn_layout import LayoutError, apply_layout
from app.services.bpmn_validator import validate_bpmn_xml

BPMN_NS = 'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"'


def _wrap(process_body: str, process_id: str = "Process_1") -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<bpmn:definitions {BPMN_NS} id="Def_1">'
        f'<bpmn:process id="{process_id}">{process_body}</bpmn:process>'
        "</bpmn:definitions>"
    )


def _wrap_collaboration(
    process_body: str,
    participants_xml: str = "",
    process_id: str = "Process_1",
    extra_root_xml: str = "",
) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<bpmn:definitions {BPMN_NS} id="Def_1">'
        f'<bpmn:collaboration id="Collab_1">{participants_xml}</bpmn:collaboration>'
        f'<bpmn:process id="{process_id}">{process_body}</bpmn:process>'
        f"{extra_root_xml}"
        "</bpmn:definitions>"
    )


LINEAR_PROCESS = _wrap(
    '<bpmn:startEvent id="Start_1"/>'
    '<bpmn:task id="Task_1" name="Revisar pedido"/>'
    '<bpmn:endEvent id="End_1"/>'
    '<bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_1"/>'
    '<bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="End_1"/>'
)

BRANCHING_PROCESS = _wrap(
    '<bpmn:startEvent id="Start_1"/>'
    '<bpmn:exclusiveGateway id="Gateway_1"/>'
    '<bpmn:task id="Task_Approve" name="Aprovar"/>'
    '<bpmn:task id="Task_Reject" name="Rejeitar"/>'
    '<bpmn:endEvent id="End_1"/>'
    '<bpmn:endEvent id="End_2"/>'
    '<bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Gateway_1"/>'
    '<bpmn:sequenceFlow id="Flow_2" sourceRef="Gateway_1" targetRef="Task_Approve"/>'
    '<bpmn:sequenceFlow id="Flow_3" sourceRef="Gateway_1" targetRef="Task_Reject"/>'
    '<bpmn:sequenceFlow id="Flow_4" sourceRef="Task_Approve" targetRef="End_1"/>'
    '<bpmn:sequenceFlow id="Flow_5" sourceRef="Task_Reject" targetRef="End_2"/>'
)

LOOP_PROCESS = _wrap(
    '<bpmn:startEvent id="Start_1"/>'
    '<bpmn:task id="Task_Review" name="Revisar"/>'
    '<bpmn:exclusiveGateway id="Gateway_1"/>'
    '<bpmn:endEvent id="End_1"/>'
    '<bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_Review"/>'
    '<bpmn:sequenceFlow id="Flow_2" sourceRef="Task_Review" targetRef="Gateway_1"/>'
    '<bpmn:sequenceFlow id="Flow_3" sourceRef="Gateway_1" targetRef="Task_Review"/>'
    '<bpmn:sequenceFlow id="Flow_4" sourceRef="Gateway_1" targetRef="End_1"/>'
)


class TestApplyLayout:
    def test_injects_bpmndi_diagram(self):
        result = apply_layout(LINEAR_PROCESS)
        assert "bpmndi:BPMNDiagram" in result
        assert "bpmndi:BPMNPlane" in result

    def test_result_is_valid_bpmn(self):
        result = apply_layout(LINEAR_PROCESS)
        valid, err = validate_bpmn_xml(result)
        assert valid, err

    def test_declares_di_namespaces(self):
        result = apply_layout(LINEAR_PROCESS)
        assert "xmlns:bpmndi=" in result
        assert "xmlns:dc=" in result
        assert "xmlns:di=" in result

    def test_creates_shape_for_every_node(self):
        result = apply_layout(LINEAR_PROCESS)
        for node_id in ("Start_1", "Task_1", "End_1"):
            assert f'bpmnElement="{node_id}"' in result

    def test_creates_edge_for_every_sequence_flow(self):
        result = apply_layout(LINEAR_PROCESS)
        for flow_id in ("Flow_1", "Flow_2"):
            assert f'bpmnElement="{flow_id}"' in result

    def test_branching_process_has_no_overlap(self):
        result = apply_layout(BRANCHING_PROCESS)
        valid, err = validate_bpmn_xml(result)
        assert valid, err

    def test_loop_process_terminates_and_is_valid(self):
        """Processos com laços de retrabalho (comuns em entrevistas reais) não
        podem travar o cálculo de layout nem gerar sobreposição."""
        result = apply_layout(LOOP_PROCESS)
        valid, err = validate_bpmn_xml(result)
        assert valid, err

    def test_strips_existing_diagram_before_injecting(self):
        xml_with_stale_diagram = LINEAR_PROCESS.replace(
            "</bpmn:definitions>",
            '<bpmndi:BPMNDiagram id="Old"><bpmndi:BPMNPlane id="OldPlane" '
            'bpmnElement="Process_1"/></bpmndi:BPMNDiagram></bpmn:definitions>',
        )
        result = apply_layout(xml_with_stale_diagram)
        assert result.count("bpmndi:BPMNDiagram") == 2  # abre + fecha, uma única vez
        assert 'id="Old"' not in result

    def test_raises_layout_error_when_no_recognizable_nodes(self):
        empty = _wrap("")
        with pytest.raises(LayoutError):
            apply_layout(empty)

    def test_raises_layout_error_on_malformed_xml(self):
        with pytest.raises(LayoutError):
            apply_layout("not xml at all")

    def test_uses_process_id_on_plane(self):
        result = apply_layout(LINEAR_PROCESS)
        assert 'bpmnElement="Process_1"' in result


LANED_PROCESS = _wrap_collaboration(
    '<bpmn:startEvent id="Start_1"/>'
    '<bpmn:userTask id="Task_Fill" name="Preencher formulário"/>'
    '<bpmn:exclusiveGateway id="Gateway_1"/>'
    '<bpmn:userTask id="Task_Approve" name="Aprovar"/>'
    '<bpmn:manualTask id="Task_Reject" name="Arquivar fisicamente"/>'
    '<bpmn:endEvent id="End_1"/>'
    '<bpmn:endEvent id="End_2"/>'
    '<bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_Fill"/>'
    '<bpmn:sequenceFlow id="Flow_2" sourceRef="Task_Fill" targetRef="Gateway_1"/>'
    '<bpmn:sequenceFlow id="Flow_3" sourceRef="Gateway_1" targetRef="Task_Approve"/>'
    '<bpmn:sequenceFlow id="Flow_4" sourceRef="Gateway_1" targetRef="Task_Reject"/>'
    '<bpmn:sequenceFlow id="Flow_5" sourceRef="Task_Approve" targetRef="End_1"/>'
    '<bpmn:sequenceFlow id="Flow_6" sourceRef="Task_Reject" targetRef="End_2"/>'
    '<bpmn:laneSet id="LaneSet_1">'
    '<bpmn:lane id="Lane_Analista" name="Analista">'
    "<bpmn:flowNodeRef>Start_1</bpmn:flowNodeRef>"
    "<bpmn:flowNodeRef>Task_Fill</bpmn:flowNodeRef>"
    "<bpmn:flowNodeRef>Gateway_1</bpmn:flowNodeRef>"
    "<bpmn:flowNodeRef>Task_Reject</bpmn:flowNodeRef>"
    "<bpmn:flowNodeRef>End_2</bpmn:flowNodeRef>"
    "</bpmn:lane>"
    '<bpmn:lane id="Lane_Gerente" name="Gerente">'
    "<bpmn:flowNodeRef>Task_Approve</bpmn:flowNodeRef>"
    "<bpmn:flowNodeRef>End_1</bpmn:flowNodeRef>"
    "</bpmn:lane>"
    "</bpmn:laneSet>",
    participants_xml='<bpmn:participant id="Participant_1" processRef="Process_1"/>',
)

BLACK_BOX_PROCESS = _wrap_collaboration(
    '<bpmn:startEvent id="Start_1"/>'
    '<bpmn:serviceTask id="Task_Notify" name="Notificar cliente"/>'
    '<bpmn:endEvent id="End_1"/>'
    '<bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_Notify"/>'
    '<bpmn:sequenceFlow id="Flow_2" sourceRef="Task_Notify" targetRef="End_1"/>',
    participants_xml=(
        '<bpmn:participant id="Participant_Main" processRef="Process_1"/>'
        '<bpmn:participant id="Participant_Client" name="Cliente"/>'
    ),
)

ANNOTATED_PROCESS = _wrap(
    '<bpmn:startEvent id="Start_1"/>'
    '<bpmn:exclusiveGateway id="Gateway_1"/>'
    '<bpmn:task id="Task_1" name="Aprovar"/>'
    '<bpmn:endEvent id="End_1"/>'
    '<bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Gateway_1"/>'
    '<bpmn:sequenceFlow id="Flow_2" sourceRef="Gateway_1" targetRef="Task_1"/>'
    '<bpmn:sequenceFlow id="Flow_3" sourceRef="Task_1" targetRef="End_1"/>'
    '<bpmn:textAnnotation id="Note_1">'
    "<bpmn:text>Valor &gt; R$ 1000?</bpmn:text>"
    "</bpmn:textAnnotation>"
    '<bpmn:association id="Assoc_1" sourceRef="Gateway_1" targetRef="Note_1"/>'
)


class TestApplyLayoutWithPools:
    def test_lanes_produce_valid_bpmn_without_overlap(self):
        result = apply_layout(LANED_PROCESS)
        valid, err = validate_bpmn_xml(result)
        assert valid, err

    def test_lanes_and_pool_have_shapes(self):
        result = apply_layout(LANED_PROCESS)
        for element_id in ("Participant_1", "Lane_Analista", "Lane_Gerente"):
            assert f'bpmnElement="{element_id}"' in result

    def test_pool_and_lanes_marked_horizontal(self):
        result = apply_layout(LANED_PROCESS)
        assert 'bpmnElement="Participant_1" isHorizontal="true"' in result
        assert 'bpmnElement="Lane_Analista" isHorizontal="true"' in result

    def test_black_box_pool_present_and_valid(self):
        result = apply_layout(BLACK_BOX_PROCESS)
        valid, err = validate_bpmn_xml(result)
        assert valid, err
        assert 'bpmnElement="Participant_Main"' in result
        assert 'bpmnElement="Participant_Client"' in result

    def test_annotation_and_association_present_and_valid(self):
        result = apply_layout(ANNOTATED_PROCESS)
        valid, err = validate_bpmn_xml(result)
        assert valid, err
        assert 'bpmnElement="Note_1"' in result
        assert 'bpmnElement="Assoc_1"' in result

    def test_annotation_shape_does_not_overlap_process_shapes(self):
        result = apply_layout(ANNOTATED_PROCESS)
        # A validação de sobreposição do bpmn_validator já cobre isso (teste
        # acima), mas confirmamos aqui que a anotação está numa faixa própria
        # acima do conteúdo principal (y menor que qualquer nó do processo).
        import re

        note_match = re.search(
            r'bpmnElement="Note_1">\s*<dc:Bounds[^/]*y="(\d+)"', result
        )
        start_match = re.search(
            r'bpmnElement="Start_1">\s*<dc:Bounds[^/]*y="(\d+)"', result
        )
        assert note_match and start_match
        assert int(note_match.group(1)) < int(start_match.group(1))

    def test_orphan_node_outside_any_lane_is_still_placed(self):
        """Se o LLM criar um laneSet mas esquecer de referenciar algum nó,
        o layout não pode perder esse elemento nem travar."""
        flow_6 = (
            '<bpmn:sequenceFlow id="Flow_6" sourceRef="Task_Reject" targetRef="End_2"/>'
        )
        flow_7 = (
            '<bpmn:sequenceFlow id="Flow_7" sourceRef="Task_Reject" '
            'targetRef="Task_Orphan"/>'
        )
        xml_with_orphan = LANED_PROCESS.replace(
            '<bpmn:endEvent id="End_2"/>',
            '<bpmn:endEvent id="End_2"/><bpmn:task id="Task_Orphan" name="Sem raia"/>',
        ).replace(flow_6, flow_6 + flow_7)
        result = apply_layout(xml_with_orphan)
        valid, err = validate_bpmn_xml(result)
        assert valid, err
        assert 'bpmnElement="Task_Orphan"' in result
