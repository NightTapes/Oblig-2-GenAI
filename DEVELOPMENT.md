# Development and verification

DataLens AI is a local university-project MVP. Source, tests, sample data, lockfiles, CI and optional container deployment are included in this repository.

## Completed phases

1. **UI foundation** — Next.js App Router, React/TypeScript, Tailwind 4, custom shadcn/Radix buttons and dialogs, Inter, Lucide, responsive navy/amber layout, empty workspace and assistant panel. Checked with TypeScript and a production build.
2. **Data processing** — strict CSV validation, common delimiters/encodings, preservation of original cell strings, separate typed view, full-data profiles, pagination/filtering/sorting, bounded disk store, unpredictable session cookies with server-side ownership, deletion and expiry cleanup. Verified by API tests and browser import/explorer flows.
3. **Visualizations** — all six chart types, compatible manual configuration, deterministic recommendations, grouping, zoom/tooltips/legends, actual data preparation, disclosed display sampling, PNG/SVG exports. Verified by API tests for all chart types and browser tests for actual canvas rendering and both export formats.
4. **AI orchestration** — Qwen3-4B/Ollama HTTP integration, separate understanding/recommendation/selection/explanation prompts, JSON schema generation, reasoning handling, validated actions, actual Python/DuckDB/SciPy execution, separate verified/explanation messages, AI-created charts, unsupported/error/retry states and offline fallback. Tested at the HTTP model boundary with deterministic mocks; **initial delivery used HTTP mocks; see the subsequent assistant repair verification below**.
5. **Quality and delivery** — deterministic synthetic samples, user-facing loading/errors, modular source, strict Pydantic inputs, typed frontend client, Zod chart configuration, environment templates, Dockerfiles/Compose, README and CI.

## Verified in the development environment

- Python 3.12.14; Node 24.19.0. Resolved dependency versions are recorded in `backend/uv.lock` and `frontend/package-lock.json`.
- **75 backend tests passed**, covering parsing, invalid files, encodings/delimiters, type inference, original values, missing counts, descriptive statistics, numerical/grouped aggregations, correlations, undefined/constant data, all six charts, chart sampling, unknown columns, invalid actions, session isolation, expiration/deletion, request/storage limits, origin checks and mocked Ollama orchestration/failures.
- **9 frontend tests passed**, covering picker/drop validation, import progress, chart configuration/schema, assistant processing/errors/retry/verified results, offline behavior, server-side table sorting/filtering/pagination.
- `npm run typecheck` and `npm run build` succeeded.
- **2 Chromium Playwright tests passed** against the real API and production frontend: CSV → profile → charts → custom bar chart → PNG/SVG downloads → sorted/filtered/paginated explorer; synthetic sample → mobile layout → navigation → assistant drawer. Browser tests found no JavaScript page errors on the desktop flow and checked mobile page width.
- A 50,000-row synthetic CSV smoke check imported/profiled in about **0.30 seconds**, prepared four recommendations in about **0.34 seconds**, and returned a Pearson correlation using **all 50,000 pairs**. These are observations on this development machine, not performance guarantees.
- Both frontend and backend Docker images built successfully. A Chromium smoke test against the running containers verified health, sample import, four rendered charts, no JavaScript page errors and a 390-pixel mobile layout. Docker Compose configuration validates; the documented Ollama image tag and uv build image tag were checked against their registries.
- Screenshots in `docs/screenshots/` show the actual app with synthetic data, not a separate visual mockup.

## Manual live-model acceptance procedure (required on an Ollama-equipped computer)

At initial delivery, Ollama was not installed in the execution environment. The subsequent repair verification below used real local Qwen inference. No canned model response is presented as a real Qwen response. Automated tests mock the model HTTP boundary while preserving schema validation, actual data operations and response handling.

1. Follow the README to start the backend and frontend. Install/start Ollama and run `ollama pull qwen3:4b`.
2. Confirm `/api/ai/status` reports `available: true`; refresh the assistant indicator.
3. Load **Plant growth experiment** from the welcome screen. Confirm it is labeled synthetic and shows 180 rows and 5 columns.
4. Click **AI recommendations**. Confirm there are additional compatible chart cards labeled AI recommended, and a clearly labeled AI dataset overview. All charts must refer only to existing columns.
5. Ask “Which treatment group has the highest average plant height?” Confirm the verified result contains real group means and eligible sample sizes; compare it to the means from a manually created bar chart (`treatment_group`, `plant_height_cm`, `mean`). Check the explanation agrees with the verified table rather than assuming it is correct.
6. Ask “Create a scatter plot comparing temperature and plant height.” Confirm a new scatter chart is added to the workspace and the explanation avoids a causal claim.
7. Ask “What percentage of the dataset contains missing values?” Confirm **12 missing cells / 900 total cells**, approximately **1.3333%**, in the verified result. This manual fixture check is not hardcoded into the assistant.
8. Load **Environmental monitoring** and ask “Is there a correlation between temperature and humidity?” Confirm the result reports the computed Pearson r, valid paired sample size, omitted rows and limitations. Compare it with `/analyze` using `calculate_correlation` on `temperature_c` and `humidity_percent`.
9. Ask an ambiguous or unsupported question (e.g. “Prove that temperature causes growth”); confirm the assistant declines the inference or requests clarification. Try an invented column and a request to execute Python; no arbitrary operation should run.
10. Stop Ollama. Refresh the status and verify uploads, profiles, the table, manual charts and PNG/SVG export still work. If explanation generation fails after calculation, verify that the calculated result remains visible.

Record model version, hardware, latency and any interpretation failures when performing this live check. Small models may request clarification or choose an unsuitable action; the validator must reject incompatible actions and the UI must make a retry/manual alternative available.

## Known limits and deliberate scope

- Live verification now covers a small real-model regression smoke test, described below. It does not establish accuracy for every natural-language question, dataset or hardware configuration. No GPU benchmark was performed. Model weights remain a separate local download, not a repository dependency.
- No accounts or multi-user authentication. Session cookies are bearer capabilities; tabs share a session. Server-side session and dataset metadata require **one backend process/worker**. This is not a public production service.
- Temporary data and frontend chat/chart state are not durable. Switching datasets/reloading resets chart arrangements and conversation. Backend restarts invalidate all dataset metadata. Graceful shutdown and expiry remove files; abrupt crashes can leave an orphan temporary process directory until OS cleanup.
- Supported limits: default 20 MB, 200,000 rows, 100 columns, 5 datasets/session, 100/server, 500 MB serialized storage, 40 groups, first 16 numeric heatmap variables and 2,000 scatter/line display points. These bounds are configurable and documented. No external database or distributed workers are included.
- Calculation jobs run in bounded thread/request concurrency; the service has model timeouts and input/memory bounds, without hard OS-level CPU preemption. Total model workflows can use more than one inference timeout because action selection and explanation are separate calls.
- Type/date inference is conservative but not domain-aware. Numeric-looking identifiers can be inferred as measurements; review them. Missing-value policy is blank/whitespace only; arbitrary NA sentinels need source cleanup. Dates normalize to UTC, with ambiguous conventions explained in quality notes and the README.
- Statistical operations are descriptive only. There is no regression, imputation, causal inference or automatic significance testing. Pearson r may be unsuitable for nonlinear or outlier-dominated data. Box whiskers are full range, not Tukey outlier fences.
- AI questions are standalone. History is displayed but not sent back as analytical context. AI explanations are generated text and may misstate verified output; review the separately displayed numerical results.
- Inter is installed locally via `@fontsource`; no font CDN is required. Downloads of packages, container images and model weights are required during setup, not during normal local analysis.


## Assistant repair branch — subsequent verification

The reported UI error followed a verified result. That locates the failure **after** model action selection and Python calculation, in the separate explanation request. The original service collapsed connection failures, invalid envelopes, empty/reasoning-only output, malformed structured output and token-budget exhaustion into the same generic message. Its explanation request used unstructured greedy text generation, unlike action selection and recommendations. The exact cause of an individual failure on another machine cannot be recovered from that original generic message alone.

Changes on `fix/ollama-assistant-response`:

- Give the model the response schema in both its prompt and Ollama's `format`; require a bounded, validated explanation object and continue returning the same explanation string to the frontend.
- Request Qwen non-thinking mode through `think: false` and its documented `/no_think` marker. Keep low, nonzero sampling temperature. Handle a server explicitly rejecting the API flag with one bounded compatibility retry using the prompt marker.
- Require the model to consider every response argument, using null for unused nullable fields. The live test caught omission of `group_by`; the stricter generation schema plus explicit field descriptions/examples preserve the requested grouping. Existing API request defaults remain unchanged.
- Safely handle separate thinking content, closing-only reasoning tags, complete JSON code fences, malformed envelopes and incomplete responses. Reject invalid output without executing an analytical action.
- Report and log the failing phase and category, without logging dataset text, questions or private reasoning. Expose a bounded `AI_MAX_OUTPUT_TOKENS` setting (default 2048, supported maximum 4096).
- Keep verified results visible and provide **Retry question** for explanation failures. Clarify that refreshing connection status checks installation, not successful inference.
- Add `scripts/check_ai.py` to exercise real connectivity, action selection, calculation and explanation from the same environment/configuration as FastAPI.

Verification:

- **93 backend tests passed**, including 17 additional response/compatibility/error regressions and one generation-schema test.
- **10 frontend tests passed**, including preservation of verified numerical results and retry after explanation failure.
- Type checks, the production build, both Chromium end-to-end tests and Compose configuration validation passed.
- **Actual local inference passed with Ollama 0.40.6**, matching the reported server version, and official `Qwen/Qwen3-4B-GGUF` Q4_K_M weights imported into Ollama as `qwen3:4b`. Ollama 0.40.6 used the model's embedded Qwen chat template. No paid or remote inference API was used.
- The real smoke test asked for the mean measurement per group on four disposable rows. Qwen selected the grouped aggregation, Python calculated B = 6 (n=2), A = 2 (n=2), total n=4, and Qwen returned an explanation agreeing with those results. The diagnostic exited with `PASS`. CPU-only testing used a 180-second per-call timeout; this is not a latency guarantee for other machines.

Try the fix by fetching/checking out the repair branch and restarting **both** local development servers. From `backend/`, run `uv run python ../scripts/check_ai.py`. This verifies the local machine's actual configured endpoint/model rather than only checking its model list. See the README troubleshooting section for phase-specific failure messages and optional timeout/output-limit settings. The full original manual acceptance procedure remains useful for broader model-quality evaluation.
