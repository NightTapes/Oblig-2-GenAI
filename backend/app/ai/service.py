import asyncio
import json
import logging
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

from app.ai import prompts
from app.ai.responses import ModelOutputError, output_schema, parse_response
from app.analysis.operations import execute
from app.core.config import settings
from app.schemas.models import (
    AIExplanation,
    AIOverview,
    AIRecommendations,
    AIStatus,
    AnalysisAction,
    ChatResponse,
)
from app.visualization.engine import build_chart

logger = logging.getLogger("datalens.ai")


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
            base = self.base_url()
        except HTTPException as exc:
            return AIStatus(available=False, model=settings.ollama_model, message=str(exc.detail))
        try:
            async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
                response = await client.get(f"{base}/api/tags")
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict) or not isinstance(data.get("models"), list):
                    raise ValueError("Invalid model list")
                names = [m.get("name") for m in data["models"] if isinstance(m, dict)]
                ready = settings.ollama_model in names
                return AIStatus(
                    available=ready,
                    model=settings.ollama_model,
                    message="Local model installed. Generation is checked when you ask a question."
                    if ready
                    else f"Model not installed. Run: ollama pull {settings.ollama_model}",
                )
        except (httpx.HTTPError, ValueError):
            return AIStatus(
                available=False,
                model=settings.ollama_model,
                message=f"Cannot reach Ollama at {base}. Start Ollama in the backend's environment and check OLLAMA_URL. Manual analysis remains available.",
            )

    @staticmethod
    def thinking_flag_rejected(response):
        if response.status_code != 400:
            return False
        try:
            error = response.json().get("error", "")
            return isinstance(error, str) and (
                "does not support thinking" in error.lower() or ('unknown field "think"' in error.lower())
            )
        except (ValueError, AttributeError):
            return False

    async def generate(self, system, payload, schema: type[BaseModel], *, stage="analysis"):
        if self.slots.locked():
            raise HTTPException(
                429, "The local model is busy. Try again after the current analysis finishes."
            )
        base = self.base_url()
        async with self.slots:
            wire_schema = output_schema(schema)
            body = {
                "model": settings.ollama_model,
                "stream": False,
                "think": False,
                "messages": [
                    {
                        "role": "system",
                        "content": system
                        + "\nReturn only JSON matching this schema:\n"
                        + json.dumps(wire_schema),
                    },
                    # Qwen's documented soft switch also works with Ollama releases
                    # that ignore the newer API-level think flag. Keep it last.
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False) + "\n/no_think"},
                ],
                # Constrain explanations too: previously they were the only free-text
                # phase and could spend the entire output budget on reasoning/repetition.
                "format": wire_schema,
                "options": {
                    "temperature": 0.2,
                    "top_p": 0.8,
                    "num_predict": settings.ai_max_output_tokens,
                    "num_ctx": 8192,
                },
            }
            logger.info("Ollama request: stage=%s", stage)
            try:
                async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds, trust_env=False) as client:
                    response = await client.post(f"{base}/api/chat", json=body)
                    if self.thinking_flag_rejected(response):
                        logger.info(
                            "Ollama compatibility fallback: stage=%s reason=unsupported_think_flag", stage
                        )
                        body.pop("think")
                        response = await client.post(f"{base}/api/chat", json=body)
                    response.raise_for_status()
                    if len(response.content) > 100_000:
                        raise ModelOutputError("oversized_response")
                    try:
                        data = response.json()
                    except ValueError as exc:
                        raise ModelOutputError("invalid_envelope") from exc
                    parsed = parse_response(data, schema)
                    logger.info("Ollama response validated: stage=%s", stage)
                    return parsed
            except httpx.TimeoutException as exc:
                logger.warning("Ollama failure: stage=%s reason=timeout", stage)
                raise HTTPException(
                    504,
                    f"Ollama timed out during {stage}. The model may still be loading. Retry or increase AI_TIMEOUT_SECONDS in backend/.env.",
                ) from exc
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                logger.warning("Ollama failure: stage=%s reason=http_status status=%s", stage, status)
                if status == 404:
                    detail = f"Ollama could not find {settings.ollama_model}. Run: ollama pull {settings.ollama_model}"
                elif status == 400:
                    detail = f"Ollama rejected the {stage} request (HTTP 400). Update Ollama and check OLLAMA_MODEL; see the Ollama terminal for details."
                else:
                    detail = f"Ollama failed during {stage} (HTTP {status}). Check the Ollama terminal for model-loading or memory errors."
                raise HTTPException(503 if status == 404 else 502, detail) from exc
            except httpx.HTTPError as exc:
                logger.warning("Ollama failure: stage=%s reason=connection", stage)
                raise HTTPException(
                    503,
                    f"Cannot communicate with Ollama at {base} during {stage}. Check that Ollama is running in the backend's environment and OLLAMA_URL is correct.",
                ) from exc
            except ModelOutputError as exc:
                # Log only protocol metadata; never log dataset text, questions,
                # model content or private reasoning, including validation errors.
                logger.warning("Ollama failure: stage=%s reason=%s", stage, exc.reason)
                if exc.reason == "output_limit":
                    detail = f"Ollama reached its output token limit during {stage}. Update Ollama for Qwen3 non-thinking support, or increase AI_MAX_OUTPUT_TOKENS in backend/.env (maximum 4096)."
                elif exc.reason == "no_final_answer":
                    detail = f"Ollama returned no final answer during {stage}. Update Ollama and use qwen3:4b with non-thinking support, then retry."
                else:
                    detail = f"Ollama returned an invalid structured response during {stage}. Retry and check your Ollama version. The backend terminal records the failure category."
                raise HTTPException(502, detail) from exc

    async def chat(self, dataset, message):
        action = await self.generate(
            prompts.SELECT,
            {"metadata": metadata(dataset), "question": message},
            AnalysisAction,
            stage="action selection",
        )
        from starlette.concurrency import run_in_threadpool

        verified = await run_in_threadpool(execute, dataset, action)
        if action.action == "unsupported":
            return ChatResponse(verified=verified, explanation=None)
        result = verified.model_dump(exclude={"chart"})
        if action.action == "describe_dataset":
            result = {"metadata": metadata(dataset), "note": verified.note}
        try:
            explanation = await self.generate(
                prompts.EXPLAIN,
                {"question": message, "verified": result},
                AIExplanation,
                stage="result explanation",
            )
            return ChatResponse(verified=verified, explanation=explanation.explanation)
        except HTTPException as exc:
            return ChatResponse(verified=verified, explanation=None, explanation_error=str(exc.detail))

    async def recommendations(self, dataset):
        summary = await self.generate(
            prompts.UNDERSTAND, metadata(dataset), AIOverview, stage="dataset overview"
        )
        result = await self.generate(
            prompts.RECOMMEND,
            {"metadata": metadata(dataset)},
            AIRecommendations,
            stage="chart recommendations",
        )
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
