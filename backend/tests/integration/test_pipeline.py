import uuid

from app.services.bpmn_generator import BpmnGenerationResult
from app.services.transcription import TranscriptionResult
from app.workers.process_audio import process_audio_pipeline

VALID_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1"/>
    <bpmn:task id="Task_1" name="Processar"/>
    <bpmn:endEvent id="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""


class TestPipeline:
    async def test_full_pipeline_sets_status_ready(self, client, mocker):
        from tests.integration.conftest import register_user

        auth = await register_user(client)
        create_project = await client.post(
            "/api/v1/projects",
            json={"name": "Pipeline Test"},
            headers=auth["headers"],
        )
        project_id = create_project.json()["id"]

        mocker.patch(
            "app.workers.process_audio.transcription_service.transcribe",
            return_value=TranscriptionResult(
                text="O analista recebe o pedido e encaminha para aprovação.",
                duration=10.0,
            ),
        )
        mocker.patch(
            "app.workers.process_audio.bpmn_generator_service.generate",
            return_value=BpmnGenerationResult(
                bpmn_xml=VALID_BPMN,
                summary="Processo de aprovação simples.",
                actors=["Analista"],
                tasks=[{"name": "Aprovar", "responsible": "Analista"}],
            ),
        )
        mocker.patch(
            "app.api.v1.processes.save_audio",
            return_value="/tmp/fake/audio.mp3",
        )
        mocker.patch("app.api.v1.processes.process_audio_pipeline")

        upload_resp = await client.post(
            f"/api/v1/projects/{project_id}/processes",
            data={"name": "Processo Pipeline"},
            files={"audio": ("audio.mp3", b"fake", "audio/mpeg")},
            headers=auth["headers"],
        )
        assert upload_resp.status_code == 201
        process_id = uuid.UUID(upload_resp.json()["id"])

        await process_audio_pipeline(process_id)

        status_resp = await client.get(
            f"/api/v1/processes/{process_id}",
            headers=auth["headers"],
        )
        data = status_resp.json()

        assert data["status"] == "ready"
        assert data["transcription"] is not None
        assert data["bpmn_xml"] == VALID_BPMN
        assert data["summary"] == "Processo de aprovação simples."
        assert data["actors"] == ["Analista"]
        assert data["version"] == 1

    async def test_pipeline_sets_error_on_failure(self, client, mocker):
        from tests.integration.conftest import register_user

        auth = await register_user(client)
        create_project = await client.post(
            "/api/v1/projects",
            json={"name": "Pipeline Error Test"},
            headers=auth["headers"],
        )
        project_id = create_project.json()["id"]

        mocker.patch(
            "app.workers.process_audio.transcription_service.transcribe",
            side_effect=RuntimeError("Whisper falhou"),
        )
        mocker.patch(
            "app.api.v1.processes.save_audio",
            return_value="/tmp/fake/audio.mp3",
        )
        mocker.patch("app.api.v1.processes.process_audio_pipeline")

        upload_resp = await client.post(
            f"/api/v1/projects/{project_id}/processes",
            data={"name": "Processo Erro"},
            files={"audio": ("audio.mp3", b"fake", "audio/mpeg")},
            headers=auth["headers"],
        )
        assert upload_resp.status_code == 201
        process_id = uuid.UUID(upload_resp.json()["id"])

        await process_audio_pipeline(process_id)

        status_resp = await client.get(
            f"/api/v1/processes/{process_id}",
            headers=auth["headers"],
        )
        assert status_resp.json()["status"] == "error"
