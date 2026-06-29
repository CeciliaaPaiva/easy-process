import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.process import Process, ProcessVersion
from app.models.project import Project
from app.models.user import User
from app.schemas.process import (
    BpmnUpdateRequest,
    ProcessResponse,
    ProcessStatusResponse,
    ProcessVersionResponse,
)
from app.services.storage import save_audio
from app.workers.process_audio import process_audio_pipeline

router = APIRouter(tags=["processes"])


async def _get_project_or_404(
    db: AsyncSession, project_id: uuid.UUID, tenant_id: uuid.UUID
) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == tenant_id,
            Project.status != "archived",
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado"
        )
    return project


async def _get_process_or_404(
    db: AsyncSession, process_id: uuid.UUID, tenant_id: uuid.UUID
) -> Process:
    result = await db.execute(
        select(Process).where(
            Process.id == process_id,
            Process.tenant_id == tenant_id,
        )
    )
    process = result.scalar_one_or_none()
    if not process:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado"
        )
    return process


@router.get(
    "/projects/{project_id}/processes",
    response_model=list[ProcessResponse],
)
async def list_processes(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProcessResponse]:
    await _get_project_or_404(db, project_id, current_user.tenant_id)

    rows = (
        (
            await db.execute(
                select(Process)
                .where(
                    Process.project_id == project_id,
                    Process.tenant_id == current_user.tenant_id,
                )
                .order_by(Process.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [ProcessResponse.model_validate(p) for p in rows]


@router.post(
    "/projects/{project_id}/processes",
    status_code=status.HTTP_201_CREATED,
    response_model=ProcessResponse,
)
async def upload_audio(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    name: str = Form(..., min_length=1, max_length=255),
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProcessResponse:
    await _get_project_or_404(db, project_id, current_user.tenant_id)

    process = Process(
        project_id=project_id,
        tenant_id=current_user.tenant_id,
        name=name,
        status="pending",
    )
    db.add(process)
    await db.flush()

    audio_path = await save_audio(audio, current_user.tenant_id, process.id)
    process.audio_path = audio_path

    await db.commit()
    await db.refresh(process)

    background_tasks.add_task(process_audio_pipeline, process.id)

    return ProcessResponse.model_validate(process)


@router.get("/processes/{process_id}/status", response_model=ProcessStatusResponse)
async def get_process_status(
    process_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProcessStatusResponse:
    process = await _get_process_or_404(db, process_id, current_user.tenant_id)
    return ProcessStatusResponse(
        id=process.id,
        status=process.status,
        version=process.version,
    )


@router.get("/processes/{process_id}", response_model=ProcessResponse)
async def get_process(
    process_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProcessResponse:
    process = await _get_process_or_404(db, process_id, current_user.tenant_id)
    return ProcessResponse.model_validate(process)


@router.get("/processes/{process_id}/bpmn")
async def get_bpmn(
    process_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    process = await _get_process_or_404(db, process_id, current_user.tenant_id)
    if process.status != "ready" or not process.bpmn_xml:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"BPMN ainda não disponível. Status atual: {process.status}",
        )
    return {"bpmn_xml": process.bpmn_xml, "version": process.version}


@router.put("/processes/{process_id}/bpmn", response_model=ProcessResponse)
async def update_bpmn(
    process_id: uuid.UUID,
    data: BpmnUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProcessResponse:
    from app.services.bpmn_validator import validate_bpmn_xml

    process = await _get_process_or_404(db, process_id, current_user.tenant_id)

    valid, err = validate_bpmn_xml(data.bpmn_xml)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"BPMN inválido: {err}",
        )

    process.version += 1
    process.bpmn_xml = data.bpmn_xml

    version = ProcessVersion(
        process_id=process.id,
        version=process.version,
        bpmn_xml=data.bpmn_xml,
        change_description=data.change_description,
    )
    db.add(version)
    await db.commit()
    await db.refresh(process)
    return ProcessResponse.model_validate(process)


@router.get(
    "/processes/{process_id}/versions",
    response_model=list[ProcessVersionResponse],
)
async def list_versions(
    process_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProcessVersionResponse]:
    await _get_process_or_404(db, process_id, current_user.tenant_id)

    rows = (
        (
            await db.execute(
                select(ProcessVersion)
                .where(ProcessVersion.process_id == process_id)
                .order_by(ProcessVersion.version.desc())
            )
        )
        .scalars()
        .all()
    )

    return [ProcessVersionResponse.model_validate(v) for v in rows]


@router.get("/processes/{process_id}/export")
async def export_bpmn(
    process_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    process = await _get_process_or_404(db, process_id, current_user.tenant_id)

    if process.status != "ready" or not process.bpmn_xml:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Processo não está pronto para exportação",
        )

    filename = process.name.replace(" ", "_") + ".bpmn"
    return Response(
        content=process.bpmn_xml,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
