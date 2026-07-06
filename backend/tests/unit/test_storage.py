import io
import uuid
import wave
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from app.services.storage import _probe_duration_seconds, save_audio


def _make_upload_file(filename: str, content: bytes = b"fake audio data") -> UploadFile:
    file = MagicMock(spec=UploadFile)
    file.filename = filename
    file.read = MagicMock(return_value=content)

    async def async_read():
        return content

    file.read = async_read
    return file


def _make_wav_bytes(duration_seconds: float = 1.0, framerate: int = 8000) -> bytes:
    buf = io.BytesIO()
    n_frames = int(duration_seconds * framerate)
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(framerate)
        wav.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


class TestSaveAudio:
    @pytest.mark.asyncio
    async def test_valid_mp3_saves_and_returns_path(self, tmp_path):
        tenant_id = uuid.uuid4()
        process_id = uuid.uuid4()
        upload = _make_upload_file("audio.mp3", b"mp3 content")

        with (
            patch("app.services.storage.settings") as mock_settings,
            patch(
                "app.services.storage._probe_duration_seconds",
                AsyncMock(return_value=60.0),
            ),
        ):
            mock_settings.UPLOAD_DIR = str(tmp_path)
            mock_settings.MAX_UPLOAD_SIZE_MB = 100
            mock_settings.MAX_AUDIO_DURATION_MINUTES = 30

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

    @pytest.mark.asyncio
    async def test_audio_too_long_raises_400(self, tmp_path):
        tenant_id = uuid.uuid4()
        process_id = uuid.uuid4()
        upload = _make_upload_file("long.mp3", b"mp3 content")

        with (
            patch("app.services.storage.settings") as mock_settings,
            patch(
                "app.services.storage._probe_duration_seconds",
                AsyncMock(return_value=3600.0),  # 60min
            ),
        ):
            mock_settings.UPLOAD_DIR = str(tmp_path)
            mock_settings.MAX_UPLOAD_SIZE_MB = 100
            mock_settings.MAX_AUDIO_DURATION_MINUTES = 30

            with pytest.raises(HTTPException) as exc_info:
                await save_audio(upload, tenant_id, process_id)

        assert exc_info.value.status_code == 400
        assert "longo" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_audio_within_limit_saves_ok(self, tmp_path):
        tenant_id = uuid.uuid4()
        process_id = uuid.uuid4()
        upload = _make_upload_file("ok.mp3", b"mp3 content")

        with (
            patch("app.services.storage.settings") as mock_settings,
            patch(
                "app.services.storage._probe_duration_seconds",
                AsyncMock(return_value=25 * 60),  # 25min, dentro do limite de 30min
            ),
        ):
            mock_settings.UPLOAD_DIR = str(tmp_path)
            mock_settings.MAX_UPLOAD_SIZE_MB = 100
            mock_settings.MAX_AUDIO_DURATION_MINUTES = 30

            path = await save_audio(upload, tenant_id, process_id)

        assert path.endswith("audio.mp3")


class TestProbeDurationSeconds:
    @pytest.mark.asyncio
    async def test_valid_wav_returns_duration(self):
        content = _make_wav_bytes(duration_seconds=2.0)
        duration = await _probe_duration_seconds(content, ".wav")
        assert duration == pytest.approx(2.0, abs=0.05)

    @pytest.mark.asyncio
    async def test_invalid_content_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            await _probe_duration_seconds(b"not audio data at all", ".wav")

        assert exc_info.value.status_code == 400
