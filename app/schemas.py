from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class SessionCreated(BaseModel):
    id: str
    created_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    role: str
    content: str
    tokens: int
    created_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    max_history_messages: int | None = Field(default=None, ge=1, le=200)


class UsageOut(BaseModel):
    sessions: int
    messages: int
    input_tokens: int
    output_tokens: int
    estimated_cost: float
