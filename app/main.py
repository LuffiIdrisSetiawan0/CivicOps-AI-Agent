from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.data_seed import bootstrap
from app.db import SessionLocal
from app.schemas import ChatRequest, ChatResponse, HealthResponse
from app.services.agent import SatuDataOpsAgent
from app.services.eval import run_golden_evaluation
from app.services.sql_tool import dashboard_summary, dataset_preview


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    with SessionLocal() as db:
        bootstrap(db)
    app_instance.state.agent = SatuDataOpsAgent()
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


def _static_asset_version() -> str:
    assets = [static_dir / "index.html", static_dir / "styles.css", static_dir / "app.js"]
    latest_mtime = max(path.stat().st_mtime_ns for path in assets if path.exists())
    return str(latest_mtime)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = (static_dir / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html.replace("__STATIC_VERSION__", _static_asset_version()))


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        openai_configured=bool(settings.openai_api_key),
        default_answer_mode="polish" if settings.openai_api_key else "fast",
        database_url=settings.database_url,
        vector_store=settings.chroma_path,
    )


def get_agent() -> SatuDataOpsAgent:
    return app.state.agent


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, agent: SatuDataOpsAgent = Depends(get_agent)) -> ChatResponse:
    settings = get_settings()
    answer_mode = payload.answer_mode or ("polish" if settings.openai_api_key else "fast")
    return agent.run(
        payload.question,
        include_trace=payload.include_trace,
        answer_mode=answer_mode,
        conversation_history=payload.conversation_history,
    )


@app.get("/api/datasets/preview")
def datasets_preview() -> dict:
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


@app.get("/api/dashboard/summary")
def dashboard_snapshot() -> dict:
    return dashboard_summary()


@app.post("/api/eval/run")
def eval_run(agent: SatuDataOpsAgent = Depends(get_agent)) -> dict:
    return run_golden_evaluation(agent)
