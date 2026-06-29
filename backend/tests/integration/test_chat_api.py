from app.services.bpmn_generator import BpmnGenerationResult
from app.services.bpmn_refiner import BpmnRefinementResult
from app.services.transcription import TranscriptionResult
from app.workers.process_audio import process_audio_pipeline
from tests.integration.conftest import register_user

VALID_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1"/>
    <bpmn:task id="Task_1" name="Tarefa"/>
    <bpmn:endEvent id="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""

REFINED_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1"/>
    <bpmn:task id="Task_1" name="Tarefa"/>
    <bpmn:task id="Task_2" name="Aprovação"/>
    <bpmn:endEvent id="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""


async def _ready_process(client, mocker) -> tuple[dict, str]:
    """Cria um processo no estado 'ready' via pipeline mockado."""
    auth = await register_user(client)
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "Projeto Chat"},
        headers=auth["headers"],
    )
    project_id = proj.json()["id"]

    mocker.patch("app.api.v1.processes.save_audio", return_value="/tmp/fake/audio.mp3")
    mocker.patch("app.api.v1.processes.process_audio_pipeline")
    mocker.patch(
        "app.workers.process_audio.transcription_service.transcribe",
        return_value=TranscriptionResult(text="Texto de teste para o processo.", duration=5.0),
    )
    mocker.patch(
        "app.workers.process_audio.bpmn_generator_service.generate",
        return_value=BpmnGenerationResult(
            bpmn_xml=VALID_BPMN, summary="Processo simples.", actors=[], tasks=[]
        ),
    )

    upload = await client.post(
        f"/api/v1/projects/{project_id}/processes",
        data={"name": "Processo Chat"},
        files={"audio": ("audio.mp3", b"fake", "audio/mpeg")},
        headers=auth["headers"],
    )
    import uuid
    process_id = upload.json()["id"]
    await process_audio_pipeline(uuid.UUID(process_id))

    return auth, process_id


class TestGetChatHistory:
    async def test_empty_history_returns_list(self, client, mocker):
        auth, process_id = await _ready_process(client, mocker)

        resp = await client.get(
            f"/api/v1/processes/{process_id}/chat",
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_other_tenant_returns_404(self, client, mocker):
        auth, process_id = await _ready_process(client, mocker)
        auth_b = await register_user(client)

        resp = await client.get(
            f"/api/v1/processes/{process_id}/chat",
            headers=auth_b["headers"],
        )
        assert resp.status_code == 404


class TestSendChatMessage:
    async def test_send_updates_bpmn_and_version(self, client, mocker):
        auth, process_id = await _ready_process(client, mocker)

        mocker.patch(
            "app.services.bpmn_refiner.bpmn_refiner_service.refine",
            return_value=BpmnRefinementResult(
                bpmn_xml=REFINED_BPMN,
                change_description="Adicionada tarefa de aprovação.",
            ),
        )

        resp = await client.post(
            f"/api/v1/processes/{process_id}/chat",
            json={"message": "Adicione uma tarefa de aprovação"},
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["bpmn_xml"] == REFINED_BPMN
        assert data["change_description"] == "Adicionada tarefa de aprovação."
        assert data["version"] == 2
        assert data["user_message"]["role"] == "user"
        assert data["assistant_message"]["role"] == "assistant"

    async def test_history_persisted_after_send(self, client, mocker):
        auth, process_id = await _ready_process(client, mocker)

        mocker.patch(
            "app.services.bpmn_refiner.bpmn_refiner_service.refine",
            return_value=BpmnRefinementResult(
                bpmn_xml=REFINED_BPMN,
                change_description="Ajuste realizado.",
            ),
        )

        await client.post(
            f"/api/v1/processes/{process_id}/chat",
            json={"message": "Ajuste X"},
            headers=auth["headers"],
        )

        hist = await client.get(
            f"/api/v1/processes/{process_id}/chat",
            headers=auth["headers"],
        )
        messages = hist.json()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    async def test_chat_on_pending_process_returns_400(self, client, mocker):
        auth = await register_user(client)
        proj = await client.post(
            "/api/v1/projects",
            json={"name": "P"},
            headers=auth["headers"],
        )
        project_id = proj.json()["id"]
        mocker.patch("app.api.v1.processes.save_audio", return_value="/tmp/fake/audio.mp3")
        mocker.patch("app.api.v1.processes.process_audio_pipeline")

        upload = await client.post(
            f"/api/v1/projects/{project_id}/processes",
            data={"name": "Pendente"},
            files={"audio": ("audio.mp3", b"fake", "audio/mpeg")},
            headers=auth["headers"],
        )
        process_id = upload.json()["id"]

        resp = await client.post(
            f"/api/v1/processes/{process_id}/chat",
            json={"message": "Teste"},
            headers=auth["headers"],
        )
        assert resp.status_code == 400

    async def test_chat_other_tenant_returns_404(self, client, mocker):
        auth, process_id = await _ready_process(client, mocker)
        auth_b = await register_user(client)

        resp = await client.post(
            f"/api/v1/processes/{process_id}/chat",
            json={"message": "Teste"},
            headers=auth_b["headers"],
        )
        assert resp.status_code == 404
