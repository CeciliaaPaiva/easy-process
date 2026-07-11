from app.services.bpmn_validator import validate_bpmn_xml

VALID_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="Start_1">
      <bpmn:outgoing>Flow_1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:task id="Task_1" name="Executar tarefa">
      <bpmn:incoming>Flow_1</bpmn:incoming>
      <bpmn:outgoing>Flow_2</bpmn:outgoing>
    </bpmn:task>
    <bpmn:endEvent id="End_1">
      <bpmn:incoming>Flow_2</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_1"/>
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""


class TestValidateBpmnXml:
    def test_valid_bpmn_returns_true(self):
        ok, err = validate_bpmn_xml(VALID_BPMN)
        assert ok is True
        assert err == ""

    def test_empty_string_returns_false(self):
        ok, err = validate_bpmn_xml("")
        assert ok is False
        assert "vazio" in err.lower()

    def test_malformed_xml_returns_false(self):
        ok, err = validate_bpmn_xml("<unclosed>")
        assert ok is False
        assert "malformado" in err.lower()

    def test_non_bpmn_xml_returns_false(self):
        ok, err = validate_bpmn_xml('<?xml version="1.0"?><root><child/></root>')
        assert ok is False
        assert "BPMN" in err

    def test_bpmn_without_start_event_returns_false(self):
        start_tag = (
            '<bpmn:startEvent id="Start_1">\n'
            "      <bpmn:outgoing>Flow_1</bpmn:outgoing>\n"
            "    </bpmn:startEvent>"
        )
        xml = VALID_BPMN.replace(start_tag, "")
        ok, err = validate_bpmn_xml(xml)
        assert ok is False
        assert "startEvent" in err

    def test_bpmn_without_end_event_returns_false(self):
        end_tag = (
            '<bpmn:endEvent id="End_1">\n'
            "      <bpmn:incoming>Flow_2</bpmn:incoming>\n"
            "    </bpmn:endEvent>"
        )
        xml = VALID_BPMN.replace(end_tag, "")
        ok, err = validate_bpmn_xml(xml)
        assert ok is False
        assert "endEvent" in err

    def test_duplicate_ids_returns_false(self):
        xml = VALID_BPMN.replace('id="End_1"', 'id="Start_1"')
        ok, err = validate_bpmn_xml(xml)
        assert ok is False
        assert "duplicados" in err.lower()

    def test_overlapping_peer_shapes_returns_false(self):
        """Duas formas de processo (não pool/raia) sobrepostas continuam
        sendo detectadas como erro real de layout."""
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
    xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
    xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" id="Def_1">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="Start_1"/>
    <bpmn:task id="Task_1" name="Executar tarefa"/>
    <bpmn:endEvent id="End_1"/>
    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_1"/>
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="End_1"/>
  </bpmn:process>
  <bpmndi:BPMNDiagram id="Diagram_1">
    <bpmndi:BPMNPlane id="Plane_1" bpmnElement="Process_1">
      <bpmndi:BPMNShape id="Shape_Start" bpmnElement="Start_1">
        <dc:Bounds x="100" y="100" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Task" bpmnElement="Task_1">
        <dc:Bounds x="110" y="100" width="100" height="80" />
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>"""
        ok, err = validate_bpmn_xml(xml)
        assert ok is False
        assert "sobrepõem" in err

    def test_participant_pool_overlapping_children_is_valid(self):
        """Um pool (bpmn:participant) SEMPRE contém visualmente (logo
        'sobrepõe') as formas dos elementos dentro dele — isso é a notação
        BPMN correta, não um erro de layout. Regressão do bug real: o
        refinamento travava tentando satisfazer uma restrição impossível
        (pool sem sobrepor o startEvent que ele contém)."""
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
    xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
    xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" id="Def_1">
  <bpmn:collaboration id="Collab_1">
    <bpmn:participant id="Participant_1" processRef="Process_1"/>
  </bpmn:collaboration>
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="Start_1">
      <bpmn:outgoing>Flow_1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:task id="Task_1" name="Executar tarefa">
      <bpmn:incoming>Flow_1</bpmn:incoming>
      <bpmn:outgoing>Flow_2</bpmn:outgoing>
    </bpmn:task>
    <bpmn:endEvent id="End_1">
      <bpmn:incoming>Flow_2</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_1"/>
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="End_1"/>
  </bpmn:process>
  <bpmndi:BPMNDiagram id="Diagram_1">
    <bpmndi:BPMNPlane id="Plane_1" bpmnElement="Collab_1">
      <bpmndi:BPMNShape id="Shape_Participant" bpmnElement="Participant_1"
          isHorizontal="true">
        <dc:Bounds x="80" y="80" width="500" height="200" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Start" bpmnElement="Start_1">
        <dc:Bounds x="120" y="160" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Task" bpmnElement="Task_1">
        <dc:Bounds x="300" y="140" width="100" height="80" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_End" bpmnElement="End_1">
        <dc:Bounds x="500" y="160" width="36" height="36" />
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>"""
        ok, err = validate_bpmn_xml(xml)
        assert ok is True, err
