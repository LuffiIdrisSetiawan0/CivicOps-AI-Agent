from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    include_trace: bool = True


class ToolTrace(BaseModel):
    agent: str
    tool: str
    input: str
    output_preview: str
    status: str = "ok"


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
    citations: list[Citation] = []
    sql: SQLPreview | None = None
    trace: list[ToolTrace] = []
    model: str
    used_openai: bool


class HealthResponse(BaseModel):
    status: str
    app: str
    openai_configured: bool
    database_url: str
    vector_store: str

