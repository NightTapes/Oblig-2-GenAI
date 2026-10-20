import asyncio
import json
import re
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from app.ai import prompts
from app.core.config import settings
from app.schemas.models import AIOverview, AIRecommendations, AIStatus, AnalysisAction, ChatResponse
from app.analysis.operations import execute
from app.visualization.engine import build_chart


def without_reasoning(text):
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def metadata(dataset):
    # No row samples, raw records, or categorical cell contents are sent to the model.
    p = dataset.profile
    return {
        "rows": p.row_count,
        "missing_percent": p.missing_percent,
        "synthetic": p.synthetic,
        "columns": [
            {"name": c.name, "type": c.kind, "unique": c.unique_count, "missing": c.missing_count}
            for c in p.columns
        ],
    }


class Ollama:
    def __init__(self):
        self.slots = asyncio.Semaphore(2)

    def base_url(self):
        url = urlparse(settings.ollama_url)
        if (
            url.scheme not in ("http", "https")
            or url.hostname not in ("localhost", "127.0.0.1", "::1", "ollama", "host.docker.internal")
            or url.username
            or url.password
        ):
            raise HTTPException(
                503, "Ollama must use localhost or the documented local Docker service address."
            )
        return settings.ollama_url.rstrip("/")

    async def status(self):
        try:
            async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
                response = await client.get(f"{self.base_url()}/api/tags")
                response.raise_for_status()
                names = [m.get("name") for m in response.json().get("models", [])]
                ready = settings.ollama_model in names
                return AIStatus(
                    available=ready,
                    model=settings.ollama_model,
                    message="Local model ready. First inference may need time to load."
                    if ready
                    else f"Model not installed. Run: ollama pull {settings.ollama_model}",
                )
        except (httpx.HTTPError, ValueError, HTTPException):
            return AIStatus(
                available=False,
                model=settings.ollama_model,
                message="Ollama is unavailable. Start Ollama to enable AI; data exploration and charts remain available.",
            )

    async def generate(self, system, payload, schema=None):
        if self.slots.locked():
            raise HTTPException(
                429, "The local model is busy. Try again after the current analysis finishes."
            )
        async with self.slots:
            body = {
                "model": settings.ollama_model,
                "stream": False,
                "think": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "options": {"temperature": 0, "num_predict": 1800, "num_ctx": 8192},
            }
            if schema:
                body["format"] = schema.model_json_schema()
            try:
                async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds, trust_env=False) as client:
                    response = await client.post(f"{self.base_url()}/api/chat", json=body)
                    if response.status_code == 404:
                        raise HTTPException(
                            503, f"Install the local model with: ollama pull {settings.ollama_model}"
                        )
                    response.raise_for_status()
                    if len(response.content) > 100_000:
                        raise ValueError("Oversized model output")
                    data = response.json()
                    if data.get("done_reason") == "length":
                        raise ValueError("Truncated model response")
                    content = without_reasoning(data["message"]["content"])
                    if not content or "<think>" in content:
                        raise ValueError("Incomplete final response")
                    return schema.model_validate_json(content) if schema else content[:6000]
            except httpx.TimeoutException as exc:
                raise HTTPException(
                    504,
                    "The local model timed out while loading or generating. Try again, or use manual analysis.",
                ) from exc
            except (httpx.HTTPError, KeyError, ValueError, ValidationError) as exc:
                raise HTTPException(
                    503,
                    "The local model is unavailable or returned invalid output. Retry, or create a chart manually.",
                ) from exc

    async def chat(self, dataset, message):
        action = await self.generate(
            prompts.SELECT, {"metadata": metadata(dataset), "question": message}, AnalysisAction
        )
        # Pure CPU/IO analysis runs in a bounded worker thread rather than blocking the event loop.
        from starlette.concurrency import run_in_threadpool

        verified = await run_in_threadpool(execute, dataset, action)
        if action.action == "unsupported":
            return ChatResponse(verified=verified, explanation=None)
        result = verified.model_dump(exclude={"chart"})
        if action.action == "describe_dataset":
            result = {"metadata": metadata(dataset), "note": verified.note}
        try:
            explanation = await self.generate(prompts.EXPLAIN, {"question": message, "verified": result})
            return ChatResponse(verified=verified, explanation=explanation)
        except HTTPException as exc:
            return ChatResponse(verified=verified, explanation=None, explanation_error=str(exc.detail))

    async def recommendations(self, dataset):
        summary = await self.generate(prompts.UNDERSTAND, metadata(dataset), AIOverview)
        result = await self.generate(prompts.RECOMMEND, {"metadata": metadata(dataset)}, AIRecommendations)
        from starlette.concurrency import run_in_threadpool

        charts = []
        for spec in result.charts:
            try:
                charts.append(await run_in_threadpool(build_chart, dataset, spec, "ai"))
            except (HTTPException, ValueError):
                continue
        if not charts:
            raise HTTPException(
                503,
                "The model did not recommend compatible charts. Deterministic recommendations remain available.",
            )
        return charts, summary.summary


ollama = Ollama()
