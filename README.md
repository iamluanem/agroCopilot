# AgroCopilot

**A farm operations copilot: from the first alert to proof that the fix worked.**

NDVI maps are a commodity by now. What AgroCopilot adds is the closed loop:

> **Detect → Prioritize (R$) → Recommend → Task → Inspect → Intervene → Measure → Remember**

The satellite index is a **signal that tells you where to scout**. It is never a diagnosis. The platform keeps the
observation, the hypotheses (each with a confidence level) and the cause verified in the field separate. Over time it
builds an auditable memory of what worked in each field.

> ⚠️ **Demo data.** Santa Aurora Farm, its field boundaries, NDVI/NDRE, weather and operational history are all
> **synthetic and deterministic**. None of it is a real satellite measurement or a real field operation.
> Every synthetic record has `is_synthetic = true` and is flagged in the interface.

The scenario is set in Brazil (Sorriso, Mato Grosso). Money is shown in **Brazilian reais (R$)** and yield in
**bags/ha**, where one bag is the 60 kg sack Brazilian soybean is traded in.

![Overview: priorities ranked by R$ exposure](docs/screenshots/overview.jpg)

## Status

| Phase | Scope | Status |
|---|---|---|
| 1 · Foundation | Docker Compose, PostGIS, migrations, seed, **Map** screen with fields and management cells colored by risk | ✅ |
| 2 · Intelligence | Hypotheses with evidence and missing data, R$ exposure, prioritization, **Overview** and **Field** screens | ✅ |
| 3 · Copilot | Chat with structured cards, 10 tools over real app data, `DemoProvider` + Claude/OpenAI, inspection proposals that need your confirmation | ✅ |
| 4 · Operational loop | **Tasks** (mobile execution with photos and offline draft), agronomist verification, intervention, post-intervention simulation, **Outcomes**, field memory | ✅ |
| 5 · Polish | Editable **Settings** with recalculation, demo reset, **real Sentinel-2** layer on the map, mobile navigation | ✅ |

## Running it

You need Docker Desktop.

**macOS / Linux**
```bash
cp .env.example .env
docker compose up --build
```

**Windows (PowerShell)**
```powershell
Copy-Item .env.example .env
docker compose up --build
```

On first start the API runs the migrations and the seed (about 20 s). Then open:

- App: http://localhost:3000
- API (OpenAPI): http://localhost:8000/docs

To rebuild the seed from scratch:
```bash
docker compose exec api python -m app.infrastructure.seed.seed --reset
```

Tests. Note that the integration tests call `demo/reset`, which deletes anything created during a demo:
```bash
docker compose exec api pytest -q
```

### Running the API and web app without Docker

```bash
docker compose up -d db
# backend
cd backend && python3.12 -m venv .venv && source .venv/bin/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://agro:agro@localhost:5433/agrocopilot  # PowerShell: $env:DATABASE_URL="..."
alembic upgrade head && python -m app.infrastructure.seed.seed
uvicorn app.api.main:app --reload
# frontend (another terminal)
cd frontend && npm install && npm run dev
```

## Architecture

```mermaid
flowchart LR
  subgraph web["frontend · Next.js"]
    UI[Overview · Map · Fields<br/>Copilot · Tasks · Outcomes · Settings]
  end
  subgraph api["backend · FastAPI"]
    R[api/routers] --> A[application<br/>risk · intelligence · copilot · operations]
    A --> D[domain<br/>risk · hypotheses · economics · copilot contract]
    A --> I[infrastructure<br/>SQLAlchemy/PostGIS · LLM providers · seed]
    T[copilot_tools] --> A
  end
  LLM[(Claude / OpenAI<br/>optional)]
  S2[(Earth Search STAC<br/>Sentinel-2 L2A)]
  DB[(PostgreSQL 16 + PostGIS)]
  M[(media volume<br/>photos · S2 layers)]
  UI -->|REST/JSON| R
  I --> DB
  I -.tool calling.-> LLM
  SC[scripts/fetch_sentinel.py] --> S2
  SC --> M
  R --> M
```

```
backend/
  app/domain/          pure rules (risk engine, hypotheses, economics): no I/O, fully testable
  app/application/     use cases (map queries, risk snapshots, copilot, operations)
  app/infrastructure/  database (models, session), LLM providers and the demo seed
  app/api/             FastAPI routes
  alembic/             migrations
frontend/
  src/app/             routes: / · /map · /fields · /copilot · /tasks · /outcomes · /settings
  src/components/      map, intel, copilot, ops and ui components
tools/record-demo/     Playwright script that records the demo video
```

### Risk engine (phase 1)

For each 30 × 30 m management cell on an observation date:

- `z_hist` compares current NDVI with the **same cell at the same crop stage (days after sowing, DAS)** in previous
  seasons. It discounts the farm-wide shift for this season, so a dry year does not flag the whole farm.
- `z_field` is a robust deviation (median/MAD) from the field median on the same date.
- `score = −(0.6·z_hist + 0.4·z_field)`. Watch ≥ 1.5; critical ≥ 2.5. Both are configurable.
- Confidence comes from agreement between the two references, whether history exists, and how many recent valid
  observations there are.
- Cloudy observations are discarded, and the cell shows as "no data".

### Hypotheses and economics (phase 2)

For each field in watch or critical status, the **zone** (yellow + red cells) is stored in `risk_assessments`, along with
its hypotheses and economic estimate. Tasks and the copilot reference that same record.

- **Rule-based hypotheses** (`domain/hypotheses.py`): water stress, pest/disease, nutrient deficiency and stand failure.
  Each is scored on context: the run of days without rain, soil texture, spatial pattern (contiguous sector, linear
  strip, scattered patches), when in the cycle the anomaly began, recurrence and past inspections. Each hypothesis lists
  its **evidence** (including evidence against it) and the **data still needed** to confirm it. Without a field
  inspection, no hypothesis goes above *moderate* confidence.
- **Exposure** (`domain/economics.py`): `affected area × bags/ha × R$/bag × loss range`. The affected area is the
  critical area plus 50% of the watch area. Exposure is shown as a range with visible assumptions, and is never
  presented as a confirmed loss or as realized savings.
- **Priority** = mid exposure × urgency (crop stage + trend) × confidence weight.

### Copilot (phase 3)

The copilot has its own **Copilot** page and a drawer on the **Map** that uses the selected field as context. Every
answer follows the `CopilotAnswer` schema (Pydantic): `summary`, `evidence`, `confidence`, `missing_data`,
`next_action`, `sources` and `warnings`. It can also include a `proposed_task`, which becomes a real task only after the
user confirms it.

| Provider | When it is used |
|---|---|
| `DemoProvider` | Default when no key is set. Deterministic rules over the **same tools**, which makes it ideal for recording the demo |
| Claude | `ANTHROPIC_API_KEY` is set (model in `ANTHROPIC_MODEL`) |
| OpenAI | `OPENAI_API_KEY` is set (model in `OPENAI_MODEL`) |

`LLM_PROVIDER=auto|demo|anthropic|openai` forces a choice. If the LLM call fails, the answer falls back to demo mode
with a warning. The LLM can read data only through tools (`get_farm_summary`, `get_field_risk`, `get_memory`,
`estimate_economics`, `get_intervention_outcomes`, `propose_inspection`…). It finishes by calling `respond`, and the
answer is validated against the schema.

To use Claude, put your key in `.env` (`ANTHROPIC_API_KEY=...`) and run `docker compose up -d api`.

### Operational loop (phase 4)

`pending → assigned → in progress → inspection completed → verified (agronomist) → intervention → outcome`

- The inspection form records findings, the **verified cause** and up to 6 photos (resized on the device). The draft is
  kept in `localStorage` while it is being filled in.
- An intervention is accepted only after the agronomist verifies the inspection. Any action involving a chemical
  product also requires confirming that a prescription was issued.
- **Simulate post-intervention observations (demo)** generates 3 synthetic scenes (5, 10 and 15 days later), labeled
  `post_intervention_simulation`. The outcome is measured with difference-in-differences against the rest of the field.
- Every step becomes an event in the field's memory, and the copilot can then answer questions about the new outcome.
- `POST /api/demo/reset` removes everything created during the demo.

## Video script (60–90 s)

1. **Overview**: F04 is priority #1, with its exposure in R$.
2. **Map**: colored cells, switching dates, layer opacity.
3. Click a red cell in F04 to see hypotheses, confidence, missing data and economic assumptions.
4. **Copilot** (drawer): "Why is Field 04 red?"
5. Then: "Has this happened in this field before? What worked?"
6. Field panel → **Create inspection for this zone**.
7. On the phone (`/tasks/<id>`): start, describe, set the cause to water stress, add a photo, complete.
8. Verify as the agronomist, then record the intervention with its cost.
9. **Simulate post-intervention observations** → the **Outcomes** report (before/after, method, limitations).
10. **Fields → F04**: the field memory now shows the complete new cycle.

The recording is automated in `tools/record-demo` (see its README). To reset before re-recording:
`curl -X POST localhost:8000/api/demo/reset` (PowerShell: `Invoke-RestMethod -Method Post localhost:8000/api/demo/reset`).

### Demo scenario

Santa Aurora Farm, Sorriso-MT (Brazil), soybean, ~1,191 ha, 5 fields, seasons 2023/24, 2024/25 and 2025/26 (current).
Reference date: Jan 9, 2026 (DAS 95).

- **F04 (center pivot):** NDVI drop in the southwest sector (~38 ha critical) after 14 days without rain.
  In the 2024/25 season the same sector had a similar anomaly. The inspection confirmed water stress (clogged
  sprinklers), the intervention was recorded and the outcome was measured against a comparison area.
- **F03:** a strip with an irregular stand (watch).
- **F01, F02, F05:** healthy, with natural spatial variation.

Basemap: Esri World Imagery (no key needed). Field boundaries are synthetic and do not correspond to a real property.

### Settings and Sentinel-2 (phase 5)

- **Settings:** economic assumptions, risk thresholds and history weight, copilot provider, and **Reset demo**.
  Assessments are versioned by their assumptions, so changing a value creates a new version without breaking tasks
  and outcomes that already exist.
- **Real Sentinel-2:** `docker compose exec api python scripts/fetch_sentinel.py` searches Earth Search for the least
  cloudy scene over the farm in the last 120 days. It applies scale/offset and the SCL mask (cloud, shadow, cirrus),
  computes NDVI (B08/B04) and NDRE (B8A/B05) and writes layers in EPSG:4326. The map then offers a **Real Sentinel-2**
  option showing the date, cloud % and valid pixels. Field boundaries remain synthetic; the layer demonstrates the
  real-data pipeline. Options: `--start YYYY-MM-DD --end YYYY-MM-DD --max-cloud 10 --bbox W S E N`.
  For a scene during the soybean season use a January window, e.g. `--start 2026-01-01 --end 2026-02-28`.

## Out of scope (roadmap)

Automatic field-boundary detection · manual georeferencing of JPEG/PNG maps · offline sync ·
WhatsApp/voice · multi-tenant and authentication · drone imagery · async job queue (Celery/Redis).
