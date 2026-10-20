"""Diagnose the real local Ollama pipeline with a tiny disposable dataset.

Run from backend/: uv run python ../scripts/check_ai.py
The same Settings and client used by FastAPI are used here. No mock AI is used.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import httpx
from fastapi import HTTPException

from app.ai.service import ollama
from app.core.config import settings
from app.data.store import DatasetStore


async def check() -> int:
    try:
        base = ollama.base_url()
        print(f"Ollama: {base}")
        print(f"Model: {settings.ollama_model}")
        print(
            f"Timeout: {settings.ai_timeout_seconds:g}s; output limit: {settings.ai_max_output_tokens} tokens"
        )
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            response = await client.get(f"{base}/api/version")
            response.raise_for_status()
            print(f"Ollama version: {response.json().get('version', 'unknown')}")
        status = await ollama.status()
        print(status.message)
        if not status.available:
            return 1
        store = DatasetStore()
        try:
            dataset = store.add(
                b"group,measurement\nA,1\nA,3\nB,5\nB,7\n",
                "connection_check.csv",
                "diagnostic",
            )
            print(
                "Checking action selection, Python calculation, and explanation (may load the model)…",
                flush=True,
            )
            reply = await ollama.chat(
                dataset, "Calculate the mean of measurement for each group."
            )
            print("Verified result:", json.dumps(reply.verified.result))
            if reply.explanation_error:
                print("Explanation failed:", reply.explanation_error)
                return 1
            if reply.verified.action == "unsupported" or not reply.explanation:
                print(
                    "The model connected but did not answer the supported test question. Try again or update Ollama."
                )
                return 1
            groups = reply.verified.result.get("groups", [])
            if {row["group"]: row["value"] for row in groups} != {"A": 2, "B": 6}:
                print(
                    "The model connected but did not select the expected grouped calculation."
                )
                return 1
            print("AI explanation:", reply.explanation)
            print(
                "PASS: local model → validated action → verified calculation → AI explanation."
            )
            return 0
        finally:
            store.close()
    except HTTPException as exc:
        print(f"FAIL: {exc.detail}")
        return 1
    except (httpx.HTTPError, ValueError) as exc:
        print(
            f"FAIL: could not query the local Ollama service ({type(exc).__name__}). Check OLLAMA_URL and ollama serve."
        )
        return 1


if __name__ == "__main__":
    ai_logger = logging.getLogger("datalens.ai")
    ai_logger.setLevel(logging.INFO)
    ai_logger.addHandler(logging.StreamHandler(sys.stdout))
    raise SystemExit(asyncio.run(check()))
