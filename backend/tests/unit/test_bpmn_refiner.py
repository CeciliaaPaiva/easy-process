import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.bpmn_refiner import BpmnRefinerService

VALID_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1"/>
    <bpmn:task id="Task_1" name="Aprovar"/>
    <bpmn:endEvent id="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""

MOCK_RESPONSE = {
    "bpmn_xml": VALID_BPMN,
    "change_description": "Adicionada tarefa de aprovação.",
}


def _make_gemini_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


class TestBpmnRefinerService:
    @pytest.fixture
    def service(self):
        return BpmnRefinerService()

    @pytest.fixture
    def generate_mock(self, service, mocker):
        return mocker.patch.object(
            service._client.aio.models,
            "generate_content",
            new_callable=AsyncMock,
        )

    @pytest.mark.asyncio
    async def test_refine_returns_valid_result(self, service, generate_mock):
        generate_mock.return_value = _make_gemini_response(json.dumps(MOCK_RESPONSE))

        result = await service.refine(
            bpmn_xml=VALID_BPMN,
            instruction="Adicione uma tarefa de aprovação",
            history=[],
        )

        assert result.bpmn_xml == VALID_BPMN
        assert result.change_description == MOCK_RESPONSE["change_description"]

    @pytest.mark.asyncio
    async def test_raises_value_error_for_empty_inputs(self, service):
        with pytest.raises(ValueError):
            await service.refine(bpmn_xml="", instruction="algo", history=[])

        with pytest.raises(ValueError):
            await service.refine(bpmn_xml=VALID_BPMN, instruction="  ", history=[])

    @pytest.mark.asyncio
    async def test_includes_history_in_contents(self, service, generate_mock):
        generate_mock.return_value = _make_gemini_response(json.dumps(MOCK_RESPONSE))

        history = [
            {"role": "user", "content": "Mensagem anterior"},
            {"role": "assistant", "content": "Resposta anterior"},
        ]

        await service.refine(
            bpmn_xml=VALID_BPMN,
            instruction="nova instrução",
            history=history,
        )

        call_contents = generate_mock.call_args.kwargs["contents"]
        # history[0] user, history[1] model, + new user prompt = 3
        assert len(call_contents) == 3
        assert call_contents[0].role == "user"
        assert call_contents[0].parts[0].text == "Mensagem anterior"
        assert call_contents[1].role == "model"

    @pytest.mark.asyncio
    async def test_retries_on_invalid_bpmn(self, service, generate_mock):
        generate_mock.side_effect = [
            _make_gemini_response('{"bpmn_xml": "invalid", "change_description": ""}'),
            _make_gemini_response(json.dumps(MOCK_RESPONSE)),
        ]

        result = await service.refine(VALID_BPMN, "instrução", [], max_retries=2)
        assert "startEvent" in result.bpmn_xml

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self, service, generate_mock):
        generate_mock.return_value = _make_gemini_response("não é json")

        with pytest.raises(RuntimeError, match="tentativas"):
            await service.refine(VALID_BPMN, "instrução", [], max_retries=2)
