from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.data_seed import bootstrap
from app.db import SessionLocal, get_db
from app.schemas import ChatRequest, ChatResponse, HealthResponse
from app.services.agent import SatuDataOpsAgent
from app.services.eval import run_golden_evaluation
from app.services.sql_tool import dataset_preview

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    with SessionLocal() as db:
        bootstrap(db)
    yield


app = FastAPI(
    title="SatuData Ops Agent",
    description="Multi-agent portfolio MVP over SQL, policy documents, logs, and mock APIs.",
    version="0.1.0",
    lifespan=lifespan,
)

static_dir = Path("static")
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        openai_configured=bool(settings.openai_api_key),
        database_url=settings.database_url,
        vector_store=settings.chroma_path,
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    bootstrap(db)
    return SatuDataOpsAgent().run(payload.question, include_trace=payload.include_trace)


@app.get("/api/datasets/preview")
def datasets_preview(db: Session = Depends(get_db)) -> dict:
    bootstrap(db)
    docs = []
    for path in sorted(Path("data/policies").glob("*.md")):
        docs.append(
            {
                "source": path.name,
                "size_bytes": path.stat().st_size,
                "title": path.read_text(encoding="utf-8").splitlines()[0].replace("#", "").strip(),
            }
        )
    return {"tables": dataset_preview(), "documents": docs}


@app.post("/api/eval/run")
def eval_run(db: Session = Depends(get_db)) -> dict:
    bootstrap(db)
    return run_golden_evaluation()
