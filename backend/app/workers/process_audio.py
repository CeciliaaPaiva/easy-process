import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.process import Process, ProcessVersion
from app.services.bpmn_generator import bpmn_generator_service
from app.services.transcription import transcription_service

logger = logging.getLogger(__name__)


async def process_audio_pipeline(process_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        process = await _get_process(db, process_id)
        if not process:
            logger.error("Processo %s não encontrado", process_id)
            return

        try:
            await _update_status(db, process, "transcribing")
            logger.info("Iniciando transcrição do processo %s", process_id)

            transcription = await transcription_service.transcribe(process.audio_path)
            process.transcription = transcription.text
            await db.commit()

            await _update_status(db, process, "generating")
            logger.info("Gerando BPMN para o processo %s", process_id)

            result = await bpmn_generator_service.generate(transcription.text)

            process.bpmn_xml = result.bpmn_xml
            process.summary = result.summary
            process.actors = result.actors
            process.tasks = result.tasks
            process.version = 1

            version = ProcessVersion(
                process_id=process.id,
                version=1,
                bpmn_xml=result.bpmn_xml,
                change_description="Versão inicial gerada por IA",
            )
            db.add(version)
            await db.commit()

            await _update_status(db, process, "ready")
            logger.info("Processo %s pronto", process_id)

        except Exception:
            logger.exception("Erro no pipeline do processo %s", process_id)
            process.status = "error"
            await db.commit()


async def _get_process(db: AsyncSession, process_id: uuid.UUID) -> Process | None:
    result = await db.execute(select(Process).where(Process.id == process_id))
    return result.scalar_one_or_none()


async def _update_status(db: AsyncSession, process: Process, status: str) -> None:
    process.status = status
    await db.commit()
    await db.refresh(process)
