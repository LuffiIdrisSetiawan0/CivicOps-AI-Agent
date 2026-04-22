from typing import Literal

from pydantic import BaseModel, Field


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    include_trace: bool = True
    answer_mode: Literal["chat", "fast", "polish"] | None = None
    conversation_history: list[ChatHistoryMessage] = Field(default_factory=list)


class ToolTrace(BaseModel):
    agent: str
    tool: str
    input: str
    output_preview: str
    status: str = "ok"
    duration_ms: float | None = None


class Citation(BaseModel):
    source: str
    title: str
    snippet: str
    score: float | None = None


class SQLPreview(BaseModel):
    query: str
    columns: list[str]
    rows: list[dict]


class ChatResponse(BaseModel):
    answer: str
    route: str
    confidence: float
    citations: list[Citation] = Field(default_factory=list)
    sql: SQLPreview | None = None
    trace: list[ToolTrace] = Field(default_factory=list)
    model: str
    used_openai: bool
    answer_mode: Literal["chat", "fast", "polish"] = "chat"
    latency_ms: float = 0.0


class HealthResponse(BaseModel):
    status: str
    app: str
    openai_configured: bool
    default_answer_mode: Literal["chat", "fast", "polish"]
    database_url: str
    vector_store: str
