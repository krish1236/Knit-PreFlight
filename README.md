# Pre-Flight

Pre-launch quality gate for AI-generated research surveys. Catches survey-side defects — leading questions, infeasible screeners, redundant pairs, low-discriminative wording, fatigue points — *before* a single panelist is paid.

Pre-Flight runs a calibrated swarm of persona-conditioned LLM probes against a draft survey and surfaces a defect-detection report card. Critically: **probes are used for instrument stress-testing, not population response prediction.** Recent literature ([Hullman et al](https://mucollective.northwestern.edu/files/Hullman-llm-behavioral.pdf), [arxiv:2507.02919](https://arxiv.org/pdf/2507.02919)) shows LLM persona simulation suffers from homogenization and structural inconsistency on absolute response prediction. We do not make that claim. We use LLM *sensitivity to wording perturbation* as the signal.

## What it detects

| Signal | Method |
|---|---|
| Leading questions | Counterfactual paraphrase probing — Wasserstein / Jensen-Shannon distance on response distributions across paraphrased variants |
| Low question discrimination | IRT 2PL on the simulated response matrix (relative-within-survey, not absolute) |
| Redundant question pairs | Pairwise Pearson + Spearman correlation across persona responses |
| Skip-logic defects | NetworkX graph analysis: dead branches, cycles, forward references, contradicting screener rules |
| Infeasible quotas | Monte Carlo over ACS PUMS demographic priors |

## Running locally

Requirements: Python 3.12+, Node 20+, Docker.

```bash
# 1. infra
cp .env.example .env
docker compose up -d postgres redis

# 2. backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m preflight.cli seed-samples
uvicorn preflight.main:app --reload &
python -m preflight.worker.main &

# 3. frontend
cd frontend
npm install
npm run dev
```

Then open `http://localhost:3000`.

## Calibration

Pre-Flight ships with a defect-injection calibration harness covering 6 defect classes × 3 severity levels. Each commit's CI run reports F1 against this benchmark — visible at `/calibration` in the live app and in GitHub Actions step summaries.

Synthetic-response calibration is intentional: real-LLM calibration of this corpus would cost thousands of dollars per sweep, while the analyzers' classification logic is what calibration actually tests. Each defect class has a documented synthesis recipe (e.g., leading wording → original-wording skewed up + paraphrases neutralized) so the methodology is auditable.

```bash
python -m preflight.cli calibrate --n-clean 12 --out calibration.json
```

## Architecture

- **API:** FastAPI + async SQLAlchemy + Alembic. Persists runs, exposes REST + SSE.
- **Worker:** Long-running consumer of a Redis Streams job queue. Six-phase state machine (`pending → personas_ready → paraphrases_ready → probing → stats_running → completed`).
- **LLM client:** Anthropic Claude with prompt caching, token-bucket rate limit, rolling-window circuit breaker, and per-call cost ledger.
- **Persona engine:** ACS PUMS-weighted demographic sampling joined with response-style trait sampling (10–20% satisficing per POQ literature, plus acquiescence/extreme-response/social-desirability/reading-level/device traits).
- **Statistical analyzers:** scipy + NetworkX. No LLM in this layer — all five analyzers operate on the persisted response matrix.
- **Frontend:** Next.js 16 + React 19 + Tailwind 4. No external UI library.

## Deployment

**Backend:** Railway. Two services share `Dockerfile` — API (`railway.json`) starts `uvicorn`, Worker (`railway.worker.json`) starts the queue consumer. Postgres and Redis are Railway plugins. Set `ANTHROPIC_API_KEY`.

**Frontend:** Vercel. `frontend/vercel.json` configures the Next.js build. Set `NEXT_PUBLIC_API_BASE` to the deployed Railway API URL.

**CI:** GitHub Actions runs the test suite (backend + frontend typecheck + build) on every PR; calibration sweep nightly + on push to main with F1 in the step summary.
