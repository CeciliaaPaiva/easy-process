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
