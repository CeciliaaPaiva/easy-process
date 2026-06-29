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


def _make_openai_response(text: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = text
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestBpmnRefinerService:
    @pytest.fixture
    def service(self):
        return BpmnRefinerService()

    @pytest.fixture
    def create_mock(self, service, mocker):
        return mocker.patch.object(
            service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
        )

    @pytest.mark.asyncio
    async def test_refine_returns_valid_result(self, service, create_mock):
        create_mock.return_value = _make_openai_response(json.dumps(MOCK_RESPONSE))

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
    async def test_includes_history_in_messages(self, service, create_mock):
        create_mock.return_value = _make_openai_response(json.dumps(MOCK_RESPONSE))

        history = [
            {"role": "user", "content": "Mensagem anterior"},
            {"role": "assistant", "content": "Resposta anterior"},
        ]

        await service.refine(
            bpmn_xml=VALID_BPMN,
            instruction="nova instrução",
            history=history,
        )

        # messages kwarg = [system, history[0], history[1], new_user_prompt]
        call_messages = create_mock.call_args.kwargs["messages"]
        assert call_messages[0]["role"] == "system"
        assert call_messages[1]["role"] == "user"
        assert call_messages[1]["content"] == "Mensagem anterior"
        assert call_messages[2]["role"] == "assistant"
        assert len(call_messages) == 4  # system + 2 history + 1 nova mensagem

    @pytest.mark.asyncio
    async def test_retries_on_invalid_bpmn(self, service, create_mock):
        create_mock.side_effect = [
            _make_openai_response('{"bpmn_xml": "invalid", "change_description": ""}'),
            _make_openai_response(json.dumps(MOCK_RESPONSE)),
        ]

        result = await service.refine(VALID_BPMN, "instrução", [], max_retries=2)
        assert "startEvent" in result.bpmn_xml

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self, service, create_mock):
        create_mock.return_value = _make_openai_response("não é json")

        with pytest.raises(RuntimeError, match="tentativas"):
            await service.refine(VALID_BPMN, "instrução", [], max_retries=2)
