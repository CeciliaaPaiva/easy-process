import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ProcessResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    project_id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    status: str
    version: int
    transcription: str | None
    bpmn_xml: str | None
    summary: str | None
    actors: list[Any]
    tasks: list[Any]
    created_at: datetime
    updated_at: datetime


class ProcessVersionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    process_id: uuid.UUID
    version: int
    bpmn_xml: str
    change_description: str | None
    created_at: datetime


class BpmnUpdateRequest(BaseModel):
    bpmn_xml: str
    change_description: str | None = None


class ProcessStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    version: int


class ChatMessageResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    process_id: uuid.UUID
    role: str
    content: str
    bpmn_version: int | None
    created_at: datetime


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    bpmn_xml: str
    change_description: str
    version: int
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse


class DocumentationResponse(BaseModel):
    process_id: uuid.UUID
    description: str
    activities: list[dict]
    business_rules: list[str]
    decision_points: list[dict]
    exceptions: list[str]
