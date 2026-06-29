import uuid

from app.services.bpmn_generator import BpmnGenerationResult
from app.services.transcription import TranscriptionResult
from app.workers.process_audio import process_audio_pipeline
from tests.integration.conftest import register_user

VALID_BPMN_V1 = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1"/>
    <bpmn:task id="Task_1" name="Tarefa V1"/>
    <bpmn:endEvent id="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""

VALID_BPMN_V2 = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1"/>
    <bpmn:task id="Task_1" name="Tarefa V2"/>
    <bpmn:endEvent id="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""


async def _setup_versioned_process(client, mocker) -> tuple[dict, str]:
    auth = await register_user(client)
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "Projeto Versões"},
        headers=auth["headers"],
    )
    project_id = proj.json()["id"]

    mocker.patch("app.api.v1.processes.save_audio", return_value="/tmp/fake/audio.mp3")
    mocker.patch("app.api.v1.processes.process_audio_pipeline")
    mocker.patch(
        "app.workers.process_audio.transcription_service.transcribe",
        return_value=TranscriptionResult(text="Texto do processo.", duration=5.0),
    )
    mocker.patch(
        "app.workers.process_audio.bpmn_generator_service.generate",
        return_value=BpmnGenerationResult(
            bpmn_xml=VALID_BPMN_V1, summary="Processo.", actors=[], tasks=[]
        ),
    )

    upload = await client.post(
        f"/api/v1/projects/{project_id}/processes",
        data={"name": "Processo Versões"},
        files={"audio": ("audio.mp3", b"fake", "audio/mpeg")},
        headers=auth["headers"],
    )
    process_id = upload.json()["id"]
    await process_audio_pipeline(uuid.UUID(process_id))

    # Create version 2
    await client.put(
        f"/api/v1/processes/{process_id}/bpmn",
        json={"bpmn_xml": VALID_BPMN_V2, "change_description": "Versão 2"},
        headers=auth["headers"],
    )

    return auth, process_id


class TestGetVersion:
    async def test_get_version_1_returns_correct_bpmn(self, client, mocker):
        auth, process_id = await _setup_versioned_process(client, mocker)

        resp = await client.get(
            f"/api/v1/processes/{process_id}/versions/1",
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 1
        assert "Tarefa V1" in data["bpmn_xml"]

    async def test_get_version_2_returns_updated_bpmn(self, client, mocker):
        auth, process_id = await _setup_versioned_process(client, mocker)

        resp = await client.get(
            f"/api/v1/processes/{process_id}/versions/2",
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        assert "Tarefa V2" in resp.json()["bpmn_xml"]

    async def test_nonexistent_version_returns_404(self, client, mocker):
        auth, process_id = await _setup_versioned_process(client, mocker)

        resp = await client.get(
            f"/api/v1/processes/{process_id}/versions/99",
            headers=auth["headers"],
        )
        assert resp.status_code == 404

    async def test_other_tenant_returns_404(self, client, mocker):
        auth, process_id = await _setup_versioned_process(client, mocker)
        auth_b = await register_user(client)

        resp = await client.get(
            f"/api/v1/processes/{process_id}/versions/1",
            headers=auth_b["headers"],
        )
        assert resp.status_code == 404


class TestRestoreVersion:
    async def test_restore_creates_new_version_with_old_bpmn(self, client, mocker):
        auth, process_id = await _setup_versioned_process(client, mocker)

        resp = await client.post(
            f"/api/v1/processes/{process_id}/versions/1/restore",
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 3
        assert "Tarefa V1" in data["bpmn_xml"]

    async def test_restore_nonexistent_version_returns_404(self, client, mocker):
        auth, process_id = await _setup_versioned_process(client, mocker)

        resp = await client.post(
            f"/api/v1/processes/{process_id}/versions/99/restore",
            headers=auth["headers"],
        )
        assert resp.status_code == 404

    async def test_restore_other_tenant_returns_404(self, client, mocker):
        auth, process_id = await _setup_versioned_process(client, mocker)
        auth_b = await register_user(client)

        resp = await client.post(
            f"/api/v1/processes/{process_id}/versions/1/restore",
            headers=auth_b["headers"],
        )
        assert resp.status_code == 404
