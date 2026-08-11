from app.services.bpmn_validator import (
    validate_bpmn_xml,
    validate_external_actors_have_pools,
)

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

    def test_gateway_combining_merge_and_split_returns_false(self):
        """Um gateway com >1 entrada E >1 saída ao mesmo tempo trava a
        simulação/animação quando as entradas vêm de ramos mutuamente
        exclusivos (a segunda nunca chega). Regressão do bug real relatado
        no modo Apresentação: token nunca passava do gateway paralelo."""
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="Start_1">
      <bpmn:outgoing>Flow_1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:exclusiveGateway id="Gateway_Split" name="Aprovado?">
      <bpmn:incoming>Flow_1</bpmn:incoming>
      <bpmn:outgoing>Flow_Sim</bpmn:outgoing>
      <bpmn:outgoing>Flow_Nao</bpmn:outgoing>
    </bpmn:exclusiveGateway>
    <bpmn:task id="Task_A" name="Caminho A">
      <bpmn:incoming>Flow_Sim</bpmn:incoming>
      <bpmn:outgoing>Flow_JoinA</bpmn:outgoing>
    </bpmn:task>
    <bpmn:task id="Task_B" name="Caminho B">
      <bpmn:incoming>Flow_Nao</bpmn:incoming>
      <bpmn:outgoing>Flow_JoinB</bpmn:outgoing>
    </bpmn:task>
    <bpmn:parallelGateway id="Gw_Combinado" name="">
      <bpmn:incoming>Flow_JoinA</bpmn:incoming>
      <bpmn:incoming>Flow_JoinB</bpmn:incoming>
      <bpmn:outgoing>Flow_C</bpmn:outgoing>
      <bpmn:outgoing>Flow_D</bpmn:outgoing>
    </bpmn:parallelGateway>
    <bpmn:task id="Task_C" name="Tarefa C">
      <bpmn:incoming>Flow_C</bpmn:incoming>
      <bpmn:outgoing>Flow_End1</bpmn:outgoing>
    </bpmn:task>
    <bpmn:task id="Task_D" name="Tarefa D">
      <bpmn:incoming>Flow_D</bpmn:incoming>
      <bpmn:outgoing>Flow_End2</bpmn:outgoing>
    </bpmn:task>
    <bpmn:endEvent id="End_1">
      <bpmn:incoming>Flow_End1</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:endEvent id="End_2">
      <bpmn:incoming>Flow_End2</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Gateway_Split"/>
    <bpmn:sequenceFlow id="Flow_Sim" sourceRef="Gateway_Split" targetRef="Task_A"/>
    <bpmn:sequenceFlow id="Flow_Nao" sourceRef="Gateway_Split" targetRef="Task_B"/>
    <bpmn:sequenceFlow id="Flow_JoinA" sourceRef="Task_A" targetRef="Gw_Combinado"/>
    <bpmn:sequenceFlow id="Flow_JoinB" sourceRef="Task_B" targetRef="Gw_Combinado"/>
    <bpmn:sequenceFlow id="Flow_C" sourceRef="Gw_Combinado" targetRef="Task_C"/>
    <bpmn:sequenceFlow id="Flow_D" sourceRef="Gw_Combinado" targetRef="Task_D"/>
    <bpmn:sequenceFlow id="Flow_End1" sourceRef="Task_C" targetRef="End_1"/>
    <bpmn:sequenceFlow id="Flow_End2" sourceRef="Task_D" targetRef="End_2"/>
  </bpmn:process>
</bpmn:definitions>"""
        ok, err = validate_bpmn_xml(xml)
        assert ok is False
        assert "Gw_Combinado" in err
        assert "junção" in err or "juntar" in err

    def test_gateway_with_multiple_incoming_and_single_outgoing_is_valid(self):
        """Gateway de junção (join) puro — várias entradas, uma única saída
        — continua válido, não é o padrão problemático."""
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="Start_1">
      <bpmn:outgoing>Flow_1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:parallelGateway id="Gateway_Split" name="">
      <bpmn:incoming>Flow_1</bpmn:incoming>
      <bpmn:outgoing>Flow_A</bpmn:outgoing>
      <bpmn:outgoing>Flow_B</bpmn:outgoing>
    </bpmn:parallelGateway>
    <bpmn:task id="Task_A" name="Tarefa A">
      <bpmn:incoming>Flow_A</bpmn:incoming>
      <bpmn:outgoing>Flow_JoinA</bpmn:outgoing>
    </bpmn:task>
    <bpmn:task id="Task_B" name="Tarefa B">
      <bpmn:incoming>Flow_B</bpmn:incoming>
      <bpmn:outgoing>Flow_JoinB</bpmn:outgoing>
    </bpmn:task>
    <bpmn:parallelGateway id="Gateway_Join" name="">
      <bpmn:incoming>Flow_JoinA</bpmn:incoming>
      <bpmn:incoming>Flow_JoinB</bpmn:incoming>
      <bpmn:outgoing>Flow_End</bpmn:outgoing>
    </bpmn:parallelGateway>
    <bpmn:endEvent id="End_1">
      <bpmn:incoming>Flow_End</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Gateway_Split"/>
    <bpmn:sequenceFlow id="Flow_A" sourceRef="Gateway_Split" targetRef="Task_A"/>
    <bpmn:sequenceFlow id="Flow_B" sourceRef="Gateway_Split" targetRef="Task_B"/>
    <bpmn:sequenceFlow id="Flow_JoinA" sourceRef="Task_A" targetRef="Gateway_Join"/>
    <bpmn:sequenceFlow id="Flow_JoinB" sourceRef="Task_B" targetRef="Gateway_Join"/>
    <bpmn:sequenceFlow id="Flow_End" sourceRef="Gateway_Join" targetRef="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""
        ok, err = validate_bpmn_xml(xml)
        assert ok is True, err

    def test_gateway_with_single_incoming_and_single_outgoing_returns_false(self):
        """Um gateway com uma entrada e uma saída não decide nem junta nada —
        achado real em S12-01 (`docs/sprints/SPRINT-12-investigacao.md`): um
        parallelGateway de divisão saiu com uma única saída."""
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="Start_1">
      <bpmn:outgoing>Flow_1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:task id="Task_1" name="Preparar">
      <bpmn:incoming>Flow_1</bpmn:incoming>
      <bpmn:outgoing>Flow_2</bpmn:outgoing>
    </bpmn:task>
    <bpmn:parallelGateway id="Gateway_Pointless">
      <bpmn:incoming>Flow_2</bpmn:incoming>
      <bpmn:outgoing>Flow_3</bpmn:outgoing>
    </bpmn:parallelGateway>
    <bpmn:task id="Task_2" name="Entregar">
      <bpmn:incoming>Flow_3</bpmn:incoming>
      <bpmn:outgoing>Flow_4</bpmn:outgoing>
    </bpmn:task>
    <bpmn:endEvent id="End_1">
      <bpmn:incoming>Flow_4</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_1"/>
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="Gateway_Pointless"/>
    <bpmn:sequenceFlow id="Flow_3" sourceRef="Gateway_Pointless" targetRef="Task_2"/>
    <bpmn:sequenceFlow id="Flow_4" sourceRef="Task_2" targetRef="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""
        ok, err = validate_bpmn_xml(xml)
        assert ok is False
        assert "Gateway_Pointless" in err


class TestValidateExternalActorsHavePools:
    XML_WITH_EXTERNAL_POOL = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:participant id="Participant_Cliente" name="Cliente"/>
  <bpmn:process id="Process_1"/>
</bpmn:definitions>"""

    def test_no_external_actors_returns_empty(self):
        assert validate_external_actors_have_pools("<xml/>", []) == ""

    def test_external_actor_with_matching_pool_returns_empty(self):
        err = validate_external_actors_have_pools(
            self.XML_WITH_EXTERNAL_POOL, ["Cliente"]
        )
        assert err == ""

    def test_external_actor_matches_pool_name_case_insensitively(self):
        err = validate_external_actors_have_pools(
            self.XML_WITH_EXTERNAL_POOL, ["cliente"]
        )
        assert err == ""

    def test_missing_pool_for_external_actor_returns_error(self):
        """Achado do S12-01: atores externos identificados corretamente na
        análise, mas nunca virando bpmn:participant no XML."""
        err = validate_external_actors_have_pools(
            self.XML_WITH_EXTERNAL_POOL, ["Cliente", "Sistema iFood"]
        )
        assert "Sistema iFood" in err
        assert "Cliente" not in err.split(":")[1]  # só o ator faltante é listado
