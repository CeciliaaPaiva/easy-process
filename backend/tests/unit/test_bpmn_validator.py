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
