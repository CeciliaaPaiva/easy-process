from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.bpmn_generator import BpmnGeneratorService

VALID_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1"/>
    <bpmn:task id="Task_1" name="Aprovar solicitação"/>
    <bpmn:endEvent id="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""

MOCK_RESPONSE = {
    "bpmn_xml": VALID_BPMN,
    "summary": "Processo de aprovação de solicitações.",
    "actors": ["Analista", "Gerente"],
    "tasks": [{"name": "Aprovar solicitação", "responsible": "Gerente"}],
}

TRANSCRIPTION = "O analista recebe a solicitação e encaminha para aprovar."


def _make_response(parsed: object) -> MagicMock:
    resp = MagicMock()
    resp.parsed = parsed
    resp.text = "" if parsed is None else "{}"
    resp.usage_metadata = None
    return resp


def _parsed(data: dict) -> MagicMock:
    """Simula o objeto Pydantic retornado em response.parsed pelo google-genai."""
    parsed = MagicMock()
    parsed.bpmn_xml = data["bpmn_xml"]
    parsed.summary = data.get("summary", "")
    parsed.actors = data.get("actors", [])
    parsed.tasks = [
        MagicMock(model_dump=MagicMock(return_value=t)) for t in data.get("tasks", [])
    ]
    return parsed


class TestBpmnGeneratorService:
    @pytest.fixture
    def service(self):
        return BpmnGeneratorService()

    @pytest.fixture
    def mock_generate(self, service, mocker):
        mock = mocker.patch.object(
            service._client.aio.models, "generate_content", new=AsyncMock()
        )
        return mock

    @pytest.mark.asyncio
    async def test_generates_valid_bpmn(self, service, mock_generate):
        mock_generate.return_value = _make_response(_parsed(MOCK_RESPONSE))

        result = await service.generate(TRANSCRIPTION)

        # O LLM devolve só o XML semântico; o layout (bpmndi) é calculado em
        # Python via apply_layout — o resultado final inclui o diagrama.
        assert "Start_1" in result.bpmn_xml
        assert "bpmndi:BPMNDiagram" in result.bpmn_xml
        assert result.summary == MOCK_RESPONSE["summary"]
        assert result.actors == MOCK_RESPONSE["actors"]
        assert result.tasks == MOCK_RESPONSE["tasks"]

    @pytest.mark.asyncio
    async def test_raises_value_error_for_short_transcription(self, service):
        with pytest.raises(ValueError, match="curta"):
            await service.generate("curto")

    @pytest.mark.asyncio
    async def test_retries_on_invalid_bpmn_then_succeeds(self, service, mock_generate):
        mock_generate.side_effect = [
            _make_response(
                _parsed(
                    {
                        "bpmn_xml": "not valid xml",
                        "summary": "",
                        "actors": [],
                        "tasks": [],
                    }
                )
            ),
            _make_response(_parsed(MOCK_RESPONSE)),
        ]

        result = await service.generate(TRANSCRIPTION, max_retries=2)
        assert "startEvent" in result.bpmn_xml or "Start_1" in result.bpmn_xml

    @pytest.mark.asyncio
    async def test_raises_runtime_error_after_max_retries(self, service, mock_generate):
        mock_generate.return_value = _make_response(None)

        with pytest.raises(RuntimeError, match="tentativas"):
            await service.generate(TRANSCRIPTION, max_retries=2)

    @pytest.mark.asyncio
    async def test_retries_when_layout_succeeds_but_bpmn_semantically_invalid(
        self, service, mock_generate
    ):
        """XML sem endEvent tem nós suficientes para o auto-layout calcular
        coordenadas, mas ainda é semanticamente inválido — deve virar retry,
        não sucesso."""
        bpmn_ns = "http://www.omg.org/spec/BPMN/20100524/MODEL"
        missing_end_event = (
            f'<?xml version="1.0"?><bpmn:definitions xmlns:bpmn="{bpmn_ns}" '
            'id="Def_1"><bpmn:process id="Process_1">'
            '<bpmn:startEvent id="Start_1"/><bpmn:task id="Task_1"/>'
            "</bpmn:process></bpmn:definitions>"
        )
        mock_generate.side_effect = [
            _make_response(
                _parsed(
                    {
                        "bpmn_xml": missing_end_event,
                        "summary": "",
                        "actors": [],
                        "tasks": [],
                    }
                )
            ),
            _make_response(_parsed(MOCK_RESPONSE)),
        ]

        result = await service.generate(TRANSCRIPTION, max_retries=2)
        assert "bpmndi:BPMNDiagram" in result.bpmn_xml

    @pytest.mark.asyncio
    async def test_retries_when_no_recognizable_elements_for_layout(
        self, service, mock_generate
    ):
        """Se o LLM devolver um XML sem elementos reconhecíveis para o layout
        automático (LayoutError), o serviço deve tratar como erro retryável,
        não deixar a exceção vazar."""
        bpmn_ns = "http://www.omg.org/spec/BPMN/20100524/MODEL"
        empty_bpmn = (
            f'<?xml version="1.0"?><bpmn:definitions xmlns:bpmn="{bpmn_ns}" '
            'id="Def_1"><bpmn:process id="Process_1"/></bpmn:definitions>'
        )
        mock_generate.side_effect = [
            _make_response(
                _parsed(
                    {"bpmn_xml": empty_bpmn, "summary": "", "actors": [], "tasks": []}
                )
            ),
            _make_response(_parsed(MOCK_RESPONSE)),
        ]

        result = await service.generate(TRANSCRIPTION, max_retries=2)
        assert "bpmndi:BPMNDiagram" in result.bpmn_xml

    @pytest.mark.asyncio
    async def test_retry_prompt_includes_invalid_xml_not_full_history(
        self, service, mock_generate
    ):
        """Cada retry deve ser uma chamada enxuta (contents=str) e não acumular
        turnos anteriores — o retry inclui o XML inválido para correção
        direcionada, sem reenviar toda a conversa."""
        mock_generate.side_effect = [
            _make_response(
                _parsed(
                    {
                        "bpmn_xml": "not valid xml",
                        "summary": "",
                        "actors": [],
                        "tasks": [],
                    }
                )
            ),
            _make_response(_parsed(MOCK_RESPONSE)),
        ]

        await service.generate(TRANSCRIPTION, max_retries=2)

        second_call_contents = mock_generate.call_args_list[1].kwargs["contents"]
        assert isinstance(second_call_contents, str)
        assert "not valid xml" in second_call_contents
