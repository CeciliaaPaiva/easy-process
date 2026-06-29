import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from app.services.storage import save_audio


def _make_upload_file(filename: str, content: bytes = b"fake audio data") -> UploadFile:
    file = MagicMock(spec=UploadFile)
    file.filename = filename
    file.read = MagicMock(return_value=content)

    async def async_read():
        return content

    file.read = async_read
    return file


class TestSaveAudio:
    @pytest.mark.asyncio
    async def test_valid_mp3_saves_and_returns_path(self, tmp_path):
        tenant_id = uuid.uuid4()
        process_id = uuid.uuid4()
        upload = _make_upload_file("audio.mp3", b"mp3 content")

        with patch("app.services.storage.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = str(tmp_path)
            mock_settings.MAX_UPLOAD_SIZE_MB = 100

            path = await save_audio(upload, tenant_id, process_id)

        assert path.endswith("audio.mp3")
        assert str(tenant_id) in path
        assert str(process_id) in path

    @pytest.mark.asyncio
    async def test_invalid_extension_raises_400(self, tmp_path):
        tenant_id = uuid.uuid4()
        process_id = uuid.uuid4()
        upload = _make_upload_file("virus.exe", b"bad")

        with patch("app.services.storage.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = str(tmp_path)
            mock_settings.MAX_UPLOAD_SIZE_MB = 100

            with pytest.raises(HTTPException) as exc_info:
                await save_audio(upload, tenant_id, process_id)

        assert exc_info.value.status_code == 400
        assert "suportado" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_empty_file_raises_400(self, tmp_path):
        tenant_id = uuid.uuid4()
        process_id = uuid.uuid4()
        upload = _make_upload_file("empty.mp3", b"")

        with patch("app.services.storage.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = str(tmp_path)
            mock_settings.MAX_UPLOAD_SIZE_MB = 100

            with pytest.raises(HTTPException) as exc_info:
                await save_audio(upload, tenant_id, process_id)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_oversized_file_raises_413(self, tmp_path):
        tenant_id = uuid.uuid4()
        process_id = uuid.uuid4()
        large_content = b"x" * (2 * 1024 * 1024)
        upload = _make_upload_file("big.wav", large_content)

        with patch("app.services.storage.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = str(tmp_path)
            mock_settings.MAX_UPLOAD_SIZE_MB = 1

            with pytest.raises(HTTPException) as exc_info:
                await save_audio(upload, tenant_id, process_id)

        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_no_filename_raises_400(self, tmp_path):
        tenant_id = uuid.uuid4()
        process_id = uuid.uuid4()
        upload = _make_upload_file("", b"data")
        upload.filename = None

        with patch("app.services.storage.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = str(tmp_path)
            mock_settings.MAX_UPLOAD_SIZE_MB = 100

            with pytest.raises(HTTPException) as exc_info:
                await save_audio(upload, tenant_id, process_id)

        assert exc_info.value.status_code == 400
