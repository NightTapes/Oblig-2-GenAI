#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
(cd backend && uv run --frozen pytest -q)
(cd frontend && npm run typecheck && npm test && npm run build)
