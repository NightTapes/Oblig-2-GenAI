import asyncio
import contextlib
import json
import logging
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.ai.service import ollama
from app.analysis.operations import execute, require_column
from app.core.config import settings
from app.data.store import DatasetStore
from app.schemas.models import (
    AIStatus,
    AnalysisAction,
    AnalysisResult,
    ChartResult,
    ChartSpec,
    ChatRequest,
    ChatResponse,
    DatasetList,
    DatasetProfile,
    Recommendations,
    RowsPage,
    SampleRequest,
)
from app.visualization.engine import build_chart, recommend

logger = logging.getLogger("datalens")


@asynccontextmanager
async def lifespan(app):
    app.state.store = DatasetStore()
    app.state.sessions = {}
    app.state.rates = defaultdict(deque)

    async def sweep():
        while True:
            await asyncio.sleep(30)
            await run_in_threadpool(app.state.store.cleanup)
            now = time.time()
            for key, expires in list(app.state.sessions.items()):
                if expires < now:
                    app.state.sessions.pop(key, None)
                    app.state.rates.pop(key, None)

    worker = asyncio.create_task(sweep())
    yield
    worker.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await worker
    app.state.store.close()


app = FastAPI(title="DataLens AI", version="1.0.0", lifespan=lifespan)
origins = [x.strip() for x in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


class RequestLimits:
    """Bound the body before multipart parsing, including chunked uploads; bound concurrent requests."""

    def __init__(self, app):
        self.app = app
        self.slots = asyncio.Semaphore(8)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        upload = scope["path"] == "/api/datasets/upload"
        limit = settings.max_upload_mb * 1024**2 + 65536 if upload else 32768
        if self.slots.locked():
            return await JSONResponse(
                {"error": {"message": "Server is busy. Try again shortly.", "code": 429}}, 429
            )(scope, receive, send)
        async with self.slots:
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > limit:
                    return await JSONResponse(
                        {"error": {"message": "Request exceeds the configured size limit.", "code": 413}}, 413
                    )(scope, receive, send)
                if not message.get("more_body"):
                    break
            first = True

            async def replay():
                nonlocal first
                if first:
                    first = False
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            await self.app(scope, replay, send)


app.add_middleware(RequestLimits)


@app.middleware("http")
async def session_and_security(request: Request, call_next):
    if (
        request.method in ("POST", "DELETE")
        and request.headers.get("origin")
        and request.headers["origin"] not in origins
    ):
        return JSONResponse({"error": {"message": "This origin is not allowed.", "code": 403}}, 403)
    now = time.time()
    token = request.cookies.get("datalens_session", "")
    sessions = request.app.state.sessions
    new = token not in sessions or sessions.get(token, 0) < now
    if new:
        if len(sessions) >= 1000:
            return JSONResponse(
                {"error": {"message": "Session capacity reached. Try again later.", "code": 429}}, 429
            )
        token = secrets.token_urlsafe(32)
    sessions[token] = now + settings.dataset_ttl_seconds
    request.state.session = token
    rates = request.app.state.rates[token]
    while rates and rates[0] < now - 60:
        rates.popleft()
    if len(rates) >= 120:
        return JSONResponse(
            {"error": {"message": "Too many requests. Please wait a minute.", "code": 429}}, 429
        )
    rates.append(now)
    response = await call_next(request)
    response.set_cookie(
        "datalens_session",
        token,
        max_age=settings.dataset_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api",
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    return JSONResponse({"error": {"message": str(exc.detail), "code": exc.status_code}}, exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    errors = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(
        {
            "error": {
                "message": "Invalid request. Check your fields and try again.",
                "code": 422,
                "fields": errors,
            }
        },
        422,
    )


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logger.error("Request failed (%s)", type(exc).__name__)
    return JSONResponse(
        {
            "error": {
                "message": "The operation could not be completed. Try a smaller dataset or different variables.",
                "code": 500,
            }
        },
        500,
    )


def get_dataset(request, dataset_id):
    return request.app.state.store.get(dataset_id, request.state.session)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "max_upload_mb": settings.max_upload_mb,
        "ttl_seconds": settings.dataset_ttl_seconds,
    }


@app.get("/api/ai/status", response_model=AIStatus)
async def ai_status():
    return await ollama.status()


@app.get("/api/datasets", response_model=DatasetList)
def datasets(request: Request):
    return DatasetList(datasets=request.app.state.store.list(request.state.session))


@app.post("/api/datasets/upload", response_model=DatasetProfile, status_code=201)
async def upload(request: Request, file: UploadFile = File(...)):
    try:
        content = await file.read(settings.max_upload_mb * 1024**2 + 1)
        item = await run_in_threadpool(
            request.app.state.store.add, content, file.filename or "", request.state.session
        )
        return item.profile
    finally:
        await file.close()


@app.post("/api/datasets/sample", response_model=DatasetProfile, status_code=201)
def sample(request: Request, body: SampleRequest):
    name = "plant_growth_synthetic.csv" if body.name == "plants" else "environment_synthetic.csv"
    content = (Path(__file__).resolve().parents[2] / "sample_data" / name).read_bytes()
    return request.app.state.store.add(content, name, request.state.session, True).profile


@app.get("/api/datasets/{dataset_id}/profile", response_model=DatasetProfile)
def profile(request: Request, dataset_id: str):
    return get_dataset(request, dataset_id).profile


@app.get("/api/datasets/{dataset_id}/rows", response_model=RowsPage)
def rows(
    request: Request,
    dataset_id: str,
    page: int = Query(1, ge=1, le=200_000),
    page_size: int = Query(25, ge=1, le=100),
    search: str = Query("", max_length=200),
    sort: str | None = Query(None, max_length=200),
    descending: bool = False,
):
    dataset = get_dataset(request, dataset_id)
    raw = dataset.raw()
    indices = raw.index
    if search:
        mask = raw.apply(lambda c: c.str.contains(search, case=False, regex=False)).any(axis=1)
        indices = raw.index[mask]
    if sort:
        require_column(dataset, sort)
        typed = dataset.frame().loc[indices]
        indices = typed.sort_values(sort, ascending=not descending, kind="stable", na_position="last").index
    selected = raw.loc[indices]
    values = json.loads(selected.iloc[(page - 1) * page_size : page * page_size].to_json(orient="records"))
    return RowsPage(rows=values, total=len(selected), page=page, page_size=page_size)


@app.get("/api/datasets/{dataset_id}/recommendations", response_model=Recommendations)
async def recommendations(request: Request, dataset_id: str, use_ai: bool = False):
    dataset = await run_in_threadpool(get_dataset, request, dataset_id)
    if use_ai:
        try:
            charts, note = await ollama.recommendations(dataset)
            return Recommendations(charts=charts, ai_refined=True, note=note)
        except HTTPException as exc:
            charts = await run_in_threadpool(recommend, dataset)
            return Recommendations(charts=charts, note=f"{exc.detail} Showing deterministic recommendations.")
    return Recommendations(
        charts=await run_in_threadpool(recommend, dataset),
        note="Selected from your column types. Every chart uses actual data.",
    )


@app.post("/api/datasets/{dataset_id}/analyze", response_model=AnalysisResult)
def analyze(request: Request, dataset_id: str, body: AnalysisAction):
    return execute(get_dataset(request, dataset_id), body)


@app.post("/api/datasets/{dataset_id}/charts", response_model=ChartResult, status_code=201)
def charts(request: Request, dataset_id: str, body: ChartSpec):
    return build_chart(get_dataset(request, dataset_id), body)


@app.post("/api/datasets/{dataset_id}/chat", response_model=ChatResponse)
async def chat(request: Request, dataset_id: str, body: ChatRequest):
    dataset = await run_in_threadpool(get_dataset, request, dataset_id)
    return await ollama.chat(dataset, body.message)


@app.delete("/api/datasets/{dataset_id}", status_code=204)
def delete(request: Request, dataset_id: str):
    request.app.state.store.delete(dataset_id, request.state.session)
    return Response(status_code=204)
