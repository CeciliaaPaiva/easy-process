import json
from unittest.mock import AsyncMock

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


class TestBpmnRefinerService:
    @pytest.fixture
    def service(self):
        return BpmnRefinerService()

    @pytest.mark.asyncio
    async def test_refine_returns_valid_result(self, service, mocker):
        mock_content = mocker.MagicMock()
        mock_content.text = json.dumps(MOCK_RESPONSE)
        mock_response = mocker.MagicMock()
        mock_response.content = [mock_content]

        mocker.patch.object(
            service._client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        )

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
    async def test_includes_history_in_messages(self, service, mocker):
        mock_content = mocker.MagicMock()
        mock_content.text = json.dumps(MOCK_RESPONSE)
        mock_response = mocker.MagicMock()
        mock_response.content = [mock_content]

        create_mock = mocker.patch.object(
            service._client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        )

        history = [
            {"role": "user", "content": "Mensagem anterior"},
            {"role": "assistant", "content": "Resposta anterior"},
        ]

        await service.refine(
            bpmn_xml=VALID_BPMN,
            instruction="nova instrução",
            history=history,
        )

        call_messages = create_mock.call_args.kwargs["messages"]
        assert call_messages[0]["role"] == "user"
        assert call_messages[0]["content"] == "Mensagem anterior"
        assert call_messages[1]["role"] == "assistant"
        assert len(call_messages) == 3  # 2 history + 1 nova mensagem com prompt

    @pytest.mark.asyncio
    async def test_retries_on_invalid_bpmn(self, service, mocker):
        bad_content = mocker.MagicMock()
        bad_content.text = '{"bpmn_xml": "invalid", "change_description": ""}'
        good_content = mocker.MagicMock()
        good_content.text = json.dumps(MOCK_RESPONSE)

        bad_resp = mocker.MagicMock()
        bad_resp.content = [bad_content]
        good_resp = mocker.MagicMock()
        good_resp.content = [good_content]

        mocker.patch.object(
            service._client.messages,
            "create",
            new_callable=AsyncMock,
            side_effect=[bad_resp, good_resp],
        )

        result = await service.refine(VALID_BPMN, "instrução", [], max_retries=2)
        assert "startEvent" in result.bpmn_xml

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self, service, mocker):
        bad_content = mocker.MagicMock()
        bad_content.text = "não é json"
        bad_resp = mocker.MagicMock()
        bad_resp.content = [bad_content]

        mocker.patch.object(
            service._client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=bad_resp,
        )

        with pytest.raises(RuntimeError, match="tentativas"):
            await service.refine(VALID_BPMN, "instrução", [], max_retries=2)
