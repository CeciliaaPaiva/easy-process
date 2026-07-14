import asyncio
import json
import tempfile
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".webm"}


async def _ffprobe_format_duration(path: str) -> float | None:
    """Lê `format.duration` via ffprobe. Retorna None se o container não
    declarar a duração (sem levantar exceção — quem chama decide o que fazer)."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()

    if proc.returncode != 0:
        return None

    try:
        return float(json.loads(stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return None


async def _probe_duration_seconds(content: bytes, ext: str) -> float:
    """Lê a duração do áudio via ffprobe. Levanta HTTPException 400 se o arquivo
    não puder ser decodificado (corrompido ou não é áudio de verdade)."""
    with tempfile.NamedTemporaryFile(suffix=ext) as tmp:
        tmp.write(content)
        tmp.flush()

        probe = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            tmp.name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await probe.communicate()

        if probe.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Não foi possível ler o arquivo de áudio. "
                    "Verifique se não está corrompido."
                ),
            )

        try:
            return float(json.loads(stdout)["format"]["duration"])
        except (KeyError, ValueError, json.JSONDecodeError):
            pass

        # O WebM gravado pelo MediaRecorder do navegador (Chrome/Firefox) é escrito
        # "ao vivo": o navegador nunca faz seek de volta ao início do arquivo para
        # gravar a duração total no cabeçalho, então o container fica sem essa
        # informação — nem aumentar probesize/analyzeduration resolve, o dado
        # simplesmente não existe no arquivo. Remuxar com stream copy (sem
        # recodificar) para um segundo arquivo, esse sim seekable, força o ffmpeg a
        # recalcular a duração real a partir dos pacotes e gravá-la no cabeçalho.
        with tempfile.NamedTemporaryFile(suffix=ext) as remuxed:
            remux = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                tmp.name,
                "-c",
                "copy",
                remuxed.name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            await remux.communicate()

            duration = (
                await _ffprobe_format_duration(remuxed.name)
                if remux.returncode == 0
                else None
            )

        if duration is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não foi possível determinar a duração do áudio.",
            )

        return duration


async def save_audio(
    file: UploadFile,
    tenant_id: uuid.UUID,
    process_id: uuid.UUID,
) -> str:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome do arquivo é obrigatório",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Formato não suportado. Use: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    content = await file.read()

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo vazio",
        )

    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo muito grande. Máximo: {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    duration_seconds = await _probe_duration_seconds(content, ext)
    max_seconds = settings.MAX_AUDIO_DURATION_MINUTES * 60
    if duration_seconds > max_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Áudio muito longo ({duration_seconds / 60:.0f}min). "
                f"Máximo: {settings.MAX_AUDIO_DURATION_MINUTES}min"
            ),
        )

    upload_dir = Path(settings.UPLOAD_DIR) / str(tenant_id) / str(process_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / f"audio{ext}"
    file_path.write_bytes(content)

    return str(file_path)
