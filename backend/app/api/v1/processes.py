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
from app.models.process import ChatMessage
from app.schemas.process import (
    BpmnUpdateRequest,
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    DocumentationResponse,
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


@router.get(
    "/processes/{process_id}/versions/{version_number}",
    response_model=ProcessVersionResponse,
)
async def get_process_version(
    process_id: uuid.UUID,
    version_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProcessVersionResponse:
    await _get_process_or_404(db, process_id, current_user.tenant_id)

    result = await db.execute(
        select(ProcessVersion).where(
            ProcessVersion.process_id == process_id,
            ProcessVersion.version == version_number,
        )
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Versão {version_number} não encontrada",
        )
    return ProcessVersionResponse.model_validate(version)


@router.post(
    "/processes/{process_id}/versions/{version_number}/restore",
    response_model=ProcessResponse,
)
async def restore_process_version(
    process_id: uuid.UUID,
    version_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProcessResponse:
    from app.services.bpmn_validator import validate_bpmn_xml

    process = await _get_process_or_404(db, process_id, current_user.tenant_id)

    result = await db.execute(
        select(ProcessVersion).where(
            ProcessVersion.process_id == process_id,
            ProcessVersion.version == version_number,
        )
    )
    old_version = result.scalar_one_or_none()
    if not old_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Versão {version_number} não encontrada",
        )

    valid, err = validate_bpmn_xml(old_version.bpmn_xml)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"BPMN da versão {version_number} inválido: {err}",
        )

    process.version += 1
    process.bpmn_xml = old_version.bpmn_xml

    new_version = ProcessVersion(
        process_id=process_id,
        version=process.version,
        bpmn_xml=old_version.bpmn_xml,
        change_description=f"Restaurado da versão {version_number}",
    )
    db.add(new_version)
    await db.commit()
    await db.refresh(process)
    return ProcessResponse.model_validate(process)


@router.get(
    "/processes/{process_id}/chat",
    response_model=list[ChatMessageResponse],
)
async def get_chat_history(
    process_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessageResponse]:
    await _get_process_or_404(db, process_id, current_user.tenant_id)

    rows = (
        (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.process_id == process_id)
                .order_by(ChatMessage.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [ChatMessageResponse.model_validate(m) for m in rows]


@router.post("/processes/{process_id}/chat", response_model=ChatResponse)
async def send_chat_message(
    process_id: uuid.UUID,
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    from app.services.bpmn_refiner import bpmn_refiner_service

    process = await _get_process_or_404(db, process_id, current_user.tenant_id)

    if process.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Processo não está pronto para refinamento. Status: {process.status}",
        )
    if not process.bpmn_xml:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="BPMN não disponível",
        )

    history_rows = (
        (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.process_id == process_id)
                .order_by(ChatMessage.created_at.asc())
                .limit(40)
            )
        )
        .scalars()
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in history_rows[-20:]]

    user_msg = ChatMessage(
        process_id=process_id,
        role="user",
        content=data.message,
        bpmn_version=process.version,
    )
    db.add(user_msg)
    await db.flush()

    result = await bpmn_refiner_service.refine(
        bpmn_xml=process.bpmn_xml,
        instruction=data.message,
        history=history,
    )

    process.version += 1
    process.bpmn_xml = result.bpmn_xml

    new_version = ProcessVersion(
        process_id=process_id,
        version=process.version,
        bpmn_xml=result.bpmn_xml,
        change_description=result.change_description,
    )
    db.add(new_version)

    assistant_msg = ChatMessage(
        process_id=process_id,
        role="assistant",
        content=result.change_description,
        bpmn_version=process.version,
    )
    db.add(assistant_msg)

    await db.commit()
    await db.refresh(process)
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)

    return ChatResponse(
        bpmn_xml=result.bpmn_xml,
        change_description=result.change_description,
        version=process.version,
        user_message=ChatMessageResponse.model_validate(user_msg),
        assistant_message=ChatMessageResponse.model_validate(assistant_msg),
    )


@router.get("/processes/{process_id}/docs", response_model=DocumentationResponse)
async def get_process_docs(
    process_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentationResponse:
    from app.services.documentation import documentation_service

    process = await _get_process_or_404(db, process_id, current_user.tenant_id)

    if process.status != "ready" or not process.bpmn_xml:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Processo não está pronto. Status: {process.status}",
        )

    doc = await documentation_service.generate(process.bpmn_xml)

    return DocumentationResponse(
        process_id=process_id,
        description=doc.description,
        activities=doc.activities,
        business_rules=doc.business_rules,
        decision_points=doc.decision_points,
        exceptions=doc.exceptions,
    )


@router.post("/processes/{process_id}/docs", response_model=DocumentationResponse)
async def regenerate_process_docs(
    process_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentationResponse:
    return await get_process_docs(process_id, current_user, db)
