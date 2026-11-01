# Spatial-Financial Startup Feasibility and Location Recommendation System

<!-- readme-sync-bot:toc:start -->
## Table of Contents

- [Current Verified Status — 15 October 2026](#current-verified-status-15-october-2026)
- [1. Project Overview](#1-project-overview)
- [2. System Architecture and Core Engines](#2-system-architecture-and-core-engines)
- [3. Current Progress and Workspace State](#3-current-progress-and-workspace-state)
- [4. Planned Directory and File Structure](#4-planned-directory-and-file-structure)
- [5. Phased Milestone Roadmap](#5-phased-milestone-roadmap)
- [6. Tech Stack and Architectural Justification](#6-tech-stack-and-architectural-justification)
- [📋 Recommended Sections Checklist](#-recommended-sections-checklist)
<!-- readme-sync-bot:toc:end -->

**Decision Support System (DSS) for F&B / Cafés**

## Current Verified Status — 15 October 2026

Steps 1–7 are implemented: the Financial Feasibility Engine, Diagnostic Risk Engine, Geospatial POI Module, TOPSIS Recommender, FastAPI Backend, React/Tailwind Frontend, and end-to-end scenario validation with viva/demo documentation. The complete Python unit and integration suite currently passes: **64 tests** (`python -m unittest discover tests -v`).

### One-command local development

From the workspace root, install Python requirements in the active environment and frontend dependencies if needed, then start both services together:

```powershell
python -m pip install -r requirements.txt
cd frontend
npm install
cd ..
python run_project.py
```

`run_project.py` uses the workspace `.venv` interpreter when present, otherwise the Python interpreter used to launch the script. It checks the required backend modules, npm, and `frontend/node_modules` before starting FastAPI on port 8000 and Vite on port 5173. Press **Ctrl+C** to stop both services.

For a production frontend bundle, run `npm run build` from `frontend/`. The current production build completes cleanly, and an interactive dashboard smoke test confirmed the full-feasibility request returned HTTP 200 and rendered the financial summary, diagnostics, live POI counts, and TOPSIS rankings.

To resume local development, open two terminals:

**Terminal 1 — from the workspace root (backend):**

```powershell
uvicorn app.main:app --reload
```

**Terminal 2 — frontend:**

```powershell
cd frontend
npm run dev
```

The frontend dependencies are already declared in `frontend/package.json`; on a fresh checkout, run `npm install` from `frontend/` before starting Vite.

**Milestones:** Steps 1–7 are complete. Step 7 added API-level full-pipeline scenario tests and the examiner-ready [`docs/viva_defense_guide.md`](./docs/viva_defense_guide.md). The spatial engine is mocked in automated tests; live Overpass behavior and browser interaction are not automated end-to-end tests.

## 1. Project Overview

Small food-and-beverage businesses can fail even when the founders are motivated and the product is appealing. Common planning weaknesses include:

- **Unsound unit economics:** sales assumptions do not cover variable costs and fixed overhead.
- **Spatial saturation or weak demand proxies:** a proposed site may be surrounded by similar businesses or lack nearby demand anchors.
- **Rental burden:** rent may be too high relative to the revenue the site can realistically support.
- **Insufficient working capital:** the business may run out of cash before reaching a sustainable operating level.

This project is an explainable **Spatial-Financial Decision Support System**, initially scoped to cafés and similar F&B businesses. It combines deterministic financial calculations, transparent domain-based risk checks, and open geospatial data to help entrepreneurs stress-test a proposed plan and compare locations.

The system is **not** a black-box predictor of business success. It will not claim that a business has a precise probability of success or predict a guaranteed profit. Such claims would require reliable, representative outcome labels and would still be unable to account for execution, product quality, service, and future market changes. Instead, the system exposes its inputs, assumptions, calculations, and limitations so that users can challenge and revise them.

## 2. System Architecture and Core Engines

The intended processing flow is:

```text
Entrepreneur inputs
        |
        v
Typed request validation
        |
        +----------------------+------------------------+
        |                      |                        |
        v                      v                        v
Financial feasibility   Geospatial processing   Diagnostic risk checks
        |                      |                        |
        +----------------------+------------------------+
                               |
                               v
                 Alternative location ranking
                               |
                               v
                  API response and dashboard
```

### Financial Feasibility Engine

The first implementation is a deterministic cost-volume-profit (CVP) model. It calculates contribution per cover, break-even volume, physical seating capacity, a capacity-constrained operating projection, monthly operating profit or loss, and cash runway under the supplied assumptions.

For the current implementation:

- `Contribution per cover = Average ticket size - Variable cost per cover`
- `Monthly fixed costs = Monthly rent + Other monthly fixed costs`
- `Break-even covers per month = Monthly fixed costs / Contribution per cover`, when contribution is positive
- `Break-even covers per day = Break-even covers per month / Operating days per month`
- `Maximum covers per day = Seats × Operating hours per day × Seat turnovers per seat per hour`
- `Projected covers per day = min(Expected covers per day, Maximum covers per day)`
- `Projected monthly operating profit = Projected covers per day × Operating days × Contribution per cover - Monthly fixed costs`
- `Monthly cash burn = max(0, -Projected monthly operating profit)`
- `Cash runway in months = Initial working capital / Monthly cash burn`, when monthly cash burn is positive

If contribution per cover is zero or negative, break-even volume is undefined and the engine reports that break-even is not achievable under the supplied unit economics. If projected operations are profitable or break even, runway is represented as `None`, because the current model does not project depletion of working capital in that case.

These are planning calculations, not a full accounting or cash-flow forecast. The current engine does not model taxes, debt service, seasonality, opening costs, working-capital cycles, or changes in demand over time. Inputs and outputs should therefore be interpreted as an explicit scenario rather than a guarantee.

### Diagnostic and Risk Engine

The diagnostic layer turns calculated metrics into explainable warnings. Rules are:

- **Rental stress:** emit a warning from **15% through 18%** rent-to-revenue and a critical flag above **18%**. The 15% warning floor reflects the documented 12–15% sustainable range.
- **Capacity deficit:** flag when break-even covers per day exceed maximum physical covers per day, or when unit economics make break-even undefined.
- **Short runway:** flag when estimated cash runway is less than **3 months**.
- **Low contribution margin:** flag when contribution margin is below **50%**.

Thresholds are domain heuristics, not universal laws. They should be documented, configurable only when justified, and presented alongside the underlying values and assumptions. Rental burden is monthly rent divided by projected monthly revenue, where projected revenue is projected covers per day multiplied by average ticket size and operating days per month. Positive rent with zero projected revenue is treated as critical because the ratio cannot be finite. These diagnostics are implemented in `src/risk_engine.py`; validated contracts are in `src/schemas.py`.

### Geospatial Processing Engine

The spatial engine retrieves relevant points of interest (POIs) from OpenStreetMap (OSM) using the Overpass API and processes them into location features. The implementation in `src/geo_engine.py` retrieves:

- **Competitors:** cafés and relevant restaurants or quick-service outlets.
- **Demand anchors:** universities, offices, and transit stations, subject to available OSM tags and local data quality.
- **Spatial indicators:** competitor and anchor counts within requested distance buffers. Distances use the haversine formula over WGS84 coordinates; these are radial buffers, not street-network walking catchments.

Responses are cached as JSON under the configured local cache directory, keyed by Overpass endpoint and bounding box. A fresh cache avoids a network request; expired entries are refreshed from Overpass. Cache metadata records the source, retrieval time, query bounding box, ODbL license, and attribution. Malformed cache data and service failures are surfaced as errors rather than silently treated as empty results. The current engine does not fall back to expired cache entries when refresh fails.

OSM is an open, community-maintained dataset. Coverage, freshness, and tagging completeness vary by area; POI indicators are proxies and must not be presented as measured footfall or guaranteed demand. The Overpass service may rate-limit requests or be unavailable; valid cached results can be reused within their configured time-to-live, while expired results require a successful refresh. OSM-derived data use is subject to the Open Database License (ODbL), including applicable attribution and share-alike obligations.

### Alternative Location Recommender

The recommender ranks a defined set of candidate locations using **Multi-Criteria Decision Analysis (MCDA)**, specifically TOPSIS (Technique for Order Preference by Similarity to Ideal Solution). Supported candidate criteria are competitor count, anchor count, average rent per square foot, and accessibility score (0–1). For each run, callers explicitly provide criterion weights and designate each criterion as a benefit or cost.

For each criterion column `j`, TOPSIS vector normalization calculates `r_ij = x_ij / sqrt(sum_i(x_ij^2))`; a zero-norm column is normalized to zero. Weighted normalized values are `v_ij = w_j * r_ij`. The ideal best and worst use the maximum and minimum weighted values for benefit criteria, and reverse those values for cost criteria. Euclidean distances `S_i+` and `S_i-` from each candidate to those ideals produce relative closeness `C_i = S_i- / (S_i+ + S_i-)`; candidates rank by descending `C_i`. Weights must sum to 1 within `1e-6`.

The result includes weighted normalized values, ideal solutions, separation distances, scores, ranks, and structured explanations comparing the winner with each lower-ranked option. Explanations list measured criterion advantages and disadvantages with their configured weights. A TOPSIS score is a relative ranking among the evaluated candidates—not an absolute feasibility probability or proof that the top-ranked location will succeed. One candidate or identical rows produce a neutral `0.5` score when both ideal distances are zero; tied scores retain input order.

### Presentation and API Layer

The implemented backend API uses FastAPI for typed HTTP endpoints, request validation, and OpenAPI documentation. Validation errors return HTTP 422, invalid engine parameters return HTTP 400, and upstream Overpass errors return HTTP 502. Unexpected server errors are logged and returned as a generic HTTP 500 response. CORS allows only the local Vite origins `http://localhost:5173` and `http://127.0.0.1:5173`.

| Method and endpoint | Purpose |
|---|---|
| `GET /health` | Return service and engine status. |
| `POST /api/v1/financial/evaluate` | Evaluate a validated café business input and return financial metrics plus risk diagnostics. |
| `POST /api/v1/spatial/analyze` | Query OSM POIs for a selected coordinate and bounding box; return buffer counts and source/cache/license metadata. |
| `POST /api/v1/recommender/rank` | Rank caller-supplied candidate locations and criteria with TOPSIS. |
| `POST /api/v1/feasibility/full` | Combine the financial analysis, selected-site spatial analysis, and TOPSIS ranking of supplied alternatives. |

The full-feasibility request requires alternative candidates with their criteria already supplied. It does not generate candidate micro-locations, derive their metrics from OSM, or estimate rent; this keeps the API from inventing market data. Spatial requests can access Overpass and may return HTTP 502 if the service fails and no fresh cache is available. The API continues to report OSM attribution and license metadata in spatial responses.

The frontend interface is implemented in `frontend/` and consists of:

- **Frontend:** a React dashboard with a Leaflet map for site selection and spatial context, financial inputs, break-even and runway metrics, diagnostic cards, and TOPSIS alternatives.

The dashboard calls `/api/v1/feasibility/full`, shows backend health, and keeps API estimates and OSM attribution visible. Its included Bengaluru benchmark values are illustrative UI inputs supplied for this project, not independently verified current market data.

## 3. Current Progress and Workspace State

The workspace currently contains the completed financial, typed-contract, diagnostic-risk, geospatial, location-recommendation, API, and frontend milestones:

- [`src/financial_engine.py`](./src/financial_engine.py) defines immutable café assumptions and results, validates inputs, and calculates CVP metrics, seat-capacity constraints, projected operating profit, monthly cash burn, and runway.
- [`src/schemas.py`](./src/schemas.py) defines Pydantic v2 input, financial-result, and risk-assessment contracts.
- [`src/risk_engine.py`](./src/risk_engine.py) evaluates rental stress, capacity deficit, short runway, and low contribution margin using explainable thresholds.
- [`src/geo_engine.py`](./src/geo_engine.py) retrieves OSM POIs, caches responses with provenance, and calculates competitor and demand-anchor buffer counts.
- [`src/recommender.py`](./src/recommender.py) performs vector-normalized, weighted TOPSIS ranking and generates structured candidate trade-off explanations.
- [`app/main.py`](./app/main.py) exposes health, financial, spatial, recommender, and full-feasibility endpoints, with request validation, CORS, and explicit error responses.
- [`run_project.py`](./run_project.py) checks local Python/Node dependencies and starts the API and frontend development servers together, with coordinated shutdown.
- [`frontend/src/App.jsx`](./frontend/src/App.jsx) orchestrates business inputs, map selection, API health, loading/error states, and full-feasibility analysis.
- [`frontend/src/components/`](./frontend/src/components/) contains the header, business form, Leaflet map, financial summary, risk cards, and recommendations table.
- [`frontend/src/data/presets.js`](./frontend/src/data/presets.js) provides the illustrative Bangalore candidate benchmark inputs and default café assumptions.
- [`frontend/vite.config.js`](./frontend/vite.config.js) configures Tailwind CSS and proxies frontend API calls to FastAPI on port 8000.
- [`tests/test_financial_engine.py`](./tests/test_financial_engine.py) covers hand-checkable calculations, capacity limits, non-positive contribution, profitable and loss-making scenarios, and invalid inputs.
- [`tests/test_risk_engine.py`](./tests/test_risk_engine.py) tests risk rules, threshold boundaries, schema validation, and a healthy baseline.
- [`tests/test_geo_engine.py`](./tests/test_geo_engine.py) validates query construction, parsing, cache behavior, buffer counts, and error handling with mocked Overpass responses.
- [`tests/test_recommender.py`](./tests/test_recommender.py) verifies hand-calculated TOPSIS values, benefit/cost direction, degenerate cases, invalid configurations, and explanations.
- [`tests/test_api.py`](./tests/test_api.py) tests the HTTP endpoints, validation, CORS, and integrated pipeline using a mocked spatial dependency.
- [`tests/test_e2e_scenarios.py`](./tests/test_e2e_scenarios.py) exercises golden-baseline, extreme-rent, zero/negative-contribution, short-runway, tied-ranking, and incomplete-alternative scenarios through the full-feasibility endpoint with mocked spatial data.
- [`docs/viva_defense_guide.md`](./docs/viva_defense_guide.md) documents the architecture defense, equations, three reproducible illustrative case studies, examiner Q&A, and a sub-five-minute dashboard demo.

Install frontend dependencies and start the Vite development server from the frontend directory:

```powershell
cd frontend
npm install
npm run dev
```

In a separate terminal, start the FastAPI backend from the workspace root:

```powershell
uvicorn app.main:app --reload
```

Vite serves the dashboard at `http://localhost:5173` and proxies `/api` and `/health` requests to `http://localhost:8000`. To bypass the proxy, set `VITE_API_BASE_URL` to an API prefix such as `http://localhost:8000/api` before starting Vite. The health check uses that URL's origin. Build the frontend for production with `cd frontend; npm run build`.

Run the test suite from the workspace root:

```powershell
python -m unittest discover tests -v
```

Run the local development API server from the workspace root:

```powershell
uvicorn app.main:app --reload
```

The interactive API docs are available at `http://127.0.0.1:8000/docs`. Set `SPATIAL_DSS_CACHE_DIR` to change the local OSM cache directory; by default it is `data/cache`.

The source, API, and tests use the following layout:

## 4. Planned Directory and File Structure

As the project grows, organize production code, tests, data, and documentation into clear top-level areas:

```text
.
├── app/
│   ├── __init__.py
│   └── main.py                 # FastAPI application and route registration
├── run_project.py              # Unified local API and frontend launcher
├── src/
│   ├── __init__.py
│   ├── financial_engine.py     # Deterministic café feasibility calculations
│   ├── schemas.py              # Pydantic request and response contracts
│   ├── risk_engine.py          # Explainable threshold-based diagnostics
│   ├── geo_engine.py           # OSM retrieval, caching, and spatial features
│   └── recommender.py          # TOPSIS location ranking
├── frontend/
│   ├── src/
│   │   ├── components/         # Forms, map, metrics, diagnostics, recommendations
│   │   ├── data/presets.js     # Illustrative candidate and business defaults
│   │   └── App.jsx             # Dashboard and API orchestration
│   ├── package.json
│   └── vite.config.js           # Tailwind and FastAPI development proxy
├── tests/
│   ├── test_financial_engine.py
│   ├── test_risk_engine.py
│   ├── test_geo_engine.py
│   ├── test_recommender.py
│   ├── test_api.py
│   ├── test_e2e_scenarios.py
│   └── ...
├── data/
│   ├── cache/                  # Ignored transient Overpass cache; curated seed JSONs may live in seed/
│   └── benchmarks/             # Documented local benchmark inputs
├── docs/
│   ├── mathematical-formulation.md
│   ├── data-sources.md
│   └── viva_defense_guide.md
├── README.md
├── requirements.txt            # Runtime Python dependencies
└── pyproject.toml              # Python project metadata and dependencies (planned)
```

The layout is a target structure. Do not assume modules have already been moved or that planned files and dependencies exist.

## 5. Phased Milestone Roadmap

### Step 1: Core Financial Feasibility Engine — **COMPLETED**

Implement and test deterministic café CVP calculations, contribution, monthly and daily break-even covers, seating-capacity constraints, projected operating profit, cash burn, and working-capital runway.

**Current files:** `src/financial_engine.py`, `tests/test_financial_engine.py`.

### Step 2: Typed Schemas and Diagnostic Risk Engine — **COMPLETED**

Pydantic v2 request and response contracts are defined in `src/schemas.py`. The explainable benchmark rules in `src/risk_engine.py` include rental warnings from 15% through 18% and critical rental stress above 18%, capacity deficits, runway below 3 months, and contribution margin below 50%. `tests/test_risk_engine.py` covers the rule behavior and threshold boundaries.

### Step 3: Geospatial POI Extraction and Local Caching

**COMPLETED.** `src/geo_engine.py` extracts relevant competitor and demand-anchor POIs from Overpass, computes radial buffer counts, and caches results keyed by endpoint, query, and bounding box. Cache records include retrieval time, geographic coverage, OSM source, license, and attribution. `tests/test_geo_engine.py` verifies query construction, POI parsing, attribution, cache hits and expiry, exact buffer boundaries, invalid inputs, and service/cache failures using mocked Overpass responses; no live API is needed for the suite. Expired cache is refreshed online; stale-cache fallback is not enabled.

### Step 4: Spatial MCDA Recommender Engine — **COMPLETED**

`src/schemas.py` defines validated candidate, criterion, ranking, and structured trade-off contracts. `src/recommender.py` implements vector normalization, weight application, direction-aware ideals, Euclidean separation, relative closeness, and stable descending ranking. Weight totals are accepted within `1e-6` of 1. Zero-norm criteria normalize to zero; a zero total separation yields a neutral `0.5` score. Explanations compare the top candidate against each other candidate and report criterion-level advantages and disadvantages. The accessibility score uses a validated 0–1 scale.

`tests/test_recommender.py` verifies normalization and hand-calculated scores/distances, benefit and cost criteria, ties, single-candidate and zero-norm behavior, large finite inputs, validation, and structured explanations. The complete suite passes with 46 tests using `python -m unittest discover tests -v`.

The recommender ranks candidate records supplied by its caller. It does not generate candidate areas, infer criterion weights, retrieve rental benchmarks, or automatically construct candidate metrics from the geospatial engine.

### Step 5: FastAPI Backend API Layer — **COMPLETED**

`app/main.py` exposes the health, financial-evaluation, spatial-analysis, recommender-ranking, and full-feasibility endpoints. Pydantic request models enforce input constraints and recommendation weight totals. The full endpoint combines financial diagnostics, a spatial analysis at the selected site, and TOPSIS ranking of caller-supplied alternative locations. CORS is limited to the two configured local Vite origins; GeoEngine is provided through FastAPI dependency injection for testing and deployment configuration.

Validation errors return 422, invalid runtime parameters return 400, Overpass failures return 502, and unexpected errors are logged and returned as generic 500 responses. `tests/test_api.py` covers endpoint responses, invalid inputs and weights, upstream errors, CORS, and full-pipeline composition using mocked spatial data.

Install runtime and development-server dependencies with `python -m pip install -r requirements.txt`. Run `python -m unittest discover tests -v` for the full suite (64 passing tests), or start the API with `uvicorn app.main:app --reload`.

Candidate generation, candidate-specific spatial/rental metric enrichment, persistence, authentication, and production deployment configuration are outside this milestone.

### Step 6: Frontend Dashboard with Interactive Map and Sliders — **COMPLETED**

`frontend/` contains the Vite + React SPA, Tailwind CSS v4 integration, Leaflet/React-Leaflet map, and Lucide icons. It includes the requested editable financial sliders and operating assumptions, draggable/clickable proposed site, 500 m and 1 km rings, selectable benchmark candidate pins, financial summary, capacity warning, severity-coded risk cards, and ranked TOPSIS recommendations with trade-off notes.

The UI sends validated full-feasibility requests to the FastAPI backend, polls `/health`, and presents loading, validation, upstream, and backend-unreachable states. Run it using `cd frontend; npm install; npm run dev`, with `uvicorn app.main:app --reload` in a separate workspace-root terminal. Vite proxies API and health traffic to `localhost:8000`. `npm run build` creates the production bundle; `npm run lint` checks the frontend source.

The included candidate counts, rent-per-square-foot values, and accessibility scores are illustrative benchmark inputs, not verified live market data. OSM marker and tile availability requires network access. The map circles show straight-line radii, not walking catchments. The dashboard sends the selected site for live POI analysis, while alternative TOPSIS criteria are the supplied preset values; the API does not enrich each alternative from OSM or a verified rental dataset.

### Step 7: End-to-End Validation, Edge Cases, and Viva/Demo Documentation — **COMPLETED**

`tests/test_e2e_scenarios.py` runs golden-baseline, extreme-rent, zero/negative-contribution, cash-depleted, tied-alternative, and incomplete-alternative scenarios through `POST /api/v1/feasibility/full`. The test client injects a mocked geospatial engine, so validation is repeatable without Overpass or external network access. Existing API and engine tests cover input validation, upstream failures, cache behavior, capacity limits, and TOPSIS degeneracy. The complete suite passes with **64 tests** using `python -m unittest discover tests -v`.

[`docs/viva_defense_guide.md`](./docs/viva_defense_guide.md) includes the architectural rationale, financial and TOPSIS equations, three fully calculated illustrative case studies, five examiner questions with answers, and a timed dashboard demonstration script. Scenario data are explicitly illustrative rather than presented as audited accounts or verified market measurements.

**Lifecycle status:** Steps 1–7 are complete. Automated end-to-end coverage currently reaches the full-feasibility HTTP/API pipeline with spatial dependencies mocked; it does not constitute live Overpass validation or browser automation. A live dashboard demonstration still requires the backend, frontend, and an available Overpass service or fresh spatial cache.

The root `.gitignore` excludes Python caches and virtual environments, frontend dependencies/build output, local environment files, OS/editor artifacts, and transient files under `data/cache/`. Curated JSON seed fixtures under `data/cache/seed/` are explicitly allowed. No seed fixtures currently exist in the workspace.

## 6. Tech Stack and Architectural Justification

| Component | Planned technology | Role and rationale |
|---|---|---|
| Language | Python 3.11+ (target) | Core modeling and data-processing language. The current engine and its tests have also been verified with the workspace's Python 3.10.3 runtime; establish and enforce the target version when project packaging is added. |
| Input/output contracts | Pydantic v2 | Typed validation and explicit API schemas, implemented in `src/schemas.py`. |
| Spatial processing | Python standard library (haversine) | Radial distance-buffer counts without heavyweight geospatial dependencies in the initial POI pipeline. Network-based isochrones remain future work. |
| Backend API | FastAPI | Typed HTTP API, request validation integration, and interactive API documentation. |
| Frontend | React | Component-based interactive dashboard. |
| Mapping | Leaflet | Lightweight map display and site selection. |
| Styling | Tailwind CSS | Utility-based responsive UI styling. |
| Spatial data | OpenStreetMap / Overpass API via `requests` | Open POI data for initial competitor and demand-anchor proxies, subject to coverage and ODbL terms; local JSON cache supports repeatable requests. |
| Location ranking | TOPSIS / MCDA | Transparent, criteria-based comparison with inspectable weights and trade-offs. |

### Why deterministic modeling and spatial MCDA instead of black-box ML?

Pre-launch small-business success labels and detailed financial outcomes are difficult to obtain in a representative, reliable, and legally usable dataset. Training a classifier on synthetic or biased labels would produce metrics without credible real-world validation. Post-launch signals such as reviews also do not answer the pre-launch feasibility question.

The initial problem is better served by methods whose assumptions can be inspected:

- **Deterministic CVP calculations** directly relate user-supplied costs, prices, volume, and capacity to break-even requirements.
- **Rule-based diagnostics** show which benchmark was crossed and by how much.
- **Spatial indicators** use observable mapped POIs as explicitly limited proxies rather than claiming access to private footfall measurements.
- **TOPSIS** compares candidate locations through visible criteria, normalization, and weights instead of returning an opaque prediction.

This approach does not eliminate uncertainty. It makes the uncertainty, assumptions, and limits easier to explain, test, and revise—and avoids presenting unsupported success probabilities as facts.

<!-- readme-sync-bot:checklist:start -->
## 📋 Recommended Sections Checklist

_The bot can't write these automatically — they need your judgment, not a diff. This list updates itself as you add them:_

- [ ] License
- [ ] Author / Contact
- [ ] Contributing Guidelines
- [ ] Acknowledgements
- [ ] Testing
- [ ] Deployment
<!-- readme-sync-bot:checklist:end -->
