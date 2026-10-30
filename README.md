# AI Data Analyst — Blast Radius Zero

**English** | [Bahasa Indonesia](README.id.md)

---

An autonomous, multi-agent data analytics system featuring extreme security isolation (**Blast Radius Zero**). Users simply upload messy raw datasets (CSV/Excel) and ask questions in natural language. The system autonomously profiles data, plans analysis workflows, cleans data using *self-healing code execution retries*, executes *Exploratory Data Analysis* (EDA), and generates executive reports where every quantitative statement is strictly *grounded* and verifiable against executed sandbox code and outputs.

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Frontend (React + Vite + Nginx)                      │
│        Glassmorphic UI, SSE Streaming, Sandbox Lifecycle Panel         │
│                        (Port 3000 / Port 5173)                         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / SSE Stream
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               Backend Orchestrator (FastAPI + LangGraph)               │
│                  Clean Architecture & SOLID Layers                     │
│  - Schemas (Pydantic DTO)           - Services (Use Cases & Storage)   │
│  - API Routes (Modular Controllers) - LangGraph Agent State Machine    │
│                        (Port 8000, Host Network)                       │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
         LLM API Calls (OpenAI/Azure/Vultr)          │ Docker API (/var/run/docker.sock)
                    ▼                                ▼
       ┌────────────────────────┐      ┌───────────────────────────────┐
       │     External LLM       │      │  Ephemeral Docker Sandbox     │
       │ (Azure OpenAI / Vultr) │      │   (agent-sandbox:latest)      │
       └────────────────────────┘      │ - network_mode="none"         │
                                       │ - user: 1000:1000 (non-root)  │
                                       │ - read-only rootfs            │
                                       │ - strict RAM & CPU limits     │
                                       │ - auto-destroyed on finish    │
                                       └───────────────────────────────┘
```

> **Golden Security Rule**: The code-execution sandbox **NEVER** connects to the internet and **NEVER** communicates directly with the LLM. The Backend Orchestrator serves as a strictly-isolated intermediary that validates all inputs and outputs.

---

## Key Features

1. **Blast Radius Zero Sandbox Security**:
   - Every Python script executes inside a dedicated, single-use (*ephemeral*) Docker container.
   - `network_mode="none"` (zero internet or network access inside the sandbox).
   - Read-only root filesystem, unprivileged non-root user (`1000:1000`), swap disabled, CPU quota limits, strict execution timeout, and all kernel capabilities dropped (`cap_drop=["ALL"]`).
   - Anti-symlink directory traversal protection via `safe_file`.

2. **Multi-Agent Orchestration (LangGraph)**:
   - **Profiler**: Extracts dataset schema, column data types, missing value ratios, and statistical distributions.
   - **Planner**: Dynamically devises the optimal execution path based on the dataset profile and user query.
   - **Cleaner**: Standardizes mixed date formats, parses currency/amount strings, and handles fuzzy string deduplication. Powered by a *self-healing code retry loop* if execution errors occur.
   - **EDA Specialist**: Conducts statistical audits, outlier and anomaly detection, customer/transaction segmentation, and generates executive-grade charts.
   - **Reporter**: Synthesizes analytical findings into a structured executive report with verifiable evidence IDs (*grounded claims*).
   - **Advisor**: Provides system orientation and suggests relevant exploratory questions when inquiries are out-of-scope.

3. **Multi-Turn Chat Context**:
   - Preserves conversation history across turns, enabling seamless follow-up inquiries.

4. **Multi-Dataset Handling**:
   - Supports cross-dataset queries and comparative analysis via a compact dataset popover menu.

5. **Comprehensive Analytical Toolkit**:
   - Pre-installed analytical stack on Python 3.12:
     `pandas`, `numpy`, `matplotlib`, `seaborn`, `scipy`, `openpyxl`, `scikit-learn`, `statsmodels`, `rapidfuzz`, and `xlrd`.

6. **Modern Interactive UI**:
   - Real-time Server-Sent Events (SSE) streaming progress.
   - Interactive *Sandbox Lifecycle* card (inspecting RAM/CPU usage, execution constraints, and container status).
   - Evidence Drawer for verifying claims (viewing exact Python code + raw output).
   - High-resolution Modal Chart Inspector.

---

## Directory Structure (Clean Architecture)

```
agent-analyst/
├── backend/
│   ├── app/
│   │   ├── agents/          # LangGraph agent nodes (profiler, planner, cleaner, eda, reporter, advisor)
│   │   ├── api/             # HTTP presentation layer (deps, routes/health, routes/jobs)
│   │   ├── schemas/         # Pydantic Request/Response DTO models
│   │   ├── services/        # Application business logic (JobService, StorageService)
│   │   ├── agent.py         # Facade Agent wrapper
│   │   ├── config.py        # Environment configuration
│   │   ├── graph.py         # LangGraph StateGraph orchestration
│   │   ├── jobs.py          # JobManager & Job lifecycle state
│   │   ├── llm.py           # OpenAI-compatible client
│   │   ├── main.py          # FastAPI application factory
│   │   ├── prompts.py       # Prompt engineering & system prompts
│   │   └── sandbox.py       # Docker containment & safe execution
│   └── tests/               # Unit & integration test suite (9 test cases)
├── frontend/                # React (Vite) + Tailwind/CSS Glassmorphic UI
├── sandbox-image/           # Dockerfile for analytical sandbox image
├── demo-data/               # Sample CSV datasets for immediate testing
├── docker-compose.yml       # Multi-container Docker orchestration
└── .env.example             # Environment configuration template
```

---

## Quickstart

### 1. Prerequisites
- Docker & Docker Compose installed and running on your system.
- An OpenAI-compatible LLM API Key (e.g., Azure OpenAI, OpenAI, or Vultr Serverless Inference).

### 2. Environment Configuration
Copy the `.env.example` template to `.env`:
```bash
cp .env.example .env
```
Populate your LLM credentials in `.env`:
```ini
LLM_BASE_URL=https://YOUR-RESOURCE.openai.azure.com/openai/v1/
LLM_API_KEY=your_api_key_here
LLM_MODEL=your_deployment_or_model_name
```

### 3. Run the Entire System (One Command)
Run the following command at the repository root:
```bash
docker compose up --build
```
Docker Compose will automatically:
1. Build `sandbox-image` (`agent-sandbox:latest`) with all analytical packages.
2. Build and launch the `backend` service on port `8000`.
3. Build and serve the `frontend` (Nginx) on port `3000`.

**Open your browser at: `http://localhost:3000`**

---

## Development Mode (Optional)

If you are actively modifying the React frontend with *Vite Hot-Module-Reloading*:

1. Start the backend and sandbox via Docker:
   ```bash
   docker compose up --build backend
   ```
2. In a separate terminal, run the frontend locally:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
3. Open your browser at: `http://localhost:5173`.

---

## Running Automated Tests

The test suite is built with *Test Doubles* (Mock LLM and LocalSandbox), allowing full end-to-end verification without an active Docker daemon, internet connection, or LLM credits:

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/
```
*All 9 integration and workflow tests pass cleanly (100% pass rate).*

---

## Streaming Event Contract (SSE)

The system streams live execution events via Server-Sent Events (SSE) at `GET /api/jobs/{id}/events`:

| Event Type | Key Payload | Description |
|---|---|---|
| `job_started` / `job_done` | `job_id`, `warnings` | Job lifecycle start and completion |
| `step_started` / `step_finished`| `step`: profile, clean, eda, report | Currently active execution stage |
| `profile_ready` | `profile` (columns, nulls, sample) | Dataset schema digest and characteristics |
| `plan_ready` | `intent`, `steps`, `plan`, `reason` | Dynamic agent execution plan |
| `attempt_started` / `attempt_failed` | `attempt`, `max_attempts`, `error` | Sandbox execution attempt (self-healing retry) |
| `code_generated` | `code` | Python script generated by the LLM |
| `sandbox_created` | `limits`, `network`, `rootfs` | Sandbox isolation parameters |
| `sandbox_started` / `sandbox_destroyed` | `exit_code`, `duration_s`, `peak_mem_mb` | Execution lifecycle metrics |
| `stdout` / `stderr` | `text` | Raw console output from the sandbox |
| `diff_ready` | `rows_before`, `rows_after`, `changes` | Data cleaning changes and before/after diffs |
| `finding` | `id`, `title`, `statement`, `evidence`, `chart` | Specific computed analytical finding |
| `report_ready` | `report`: `verified_claims`, `interpretation`, `recommendations` | Final report with grounded evidence verification |

---

## Roadmap

- [ ] **Database Persistence**: Integrate PostgreSQL/SQLite for cross-session job history storage.
- [ ] **Multi-Tenancy & Auth**: Add user authentication (OAuth2/JWT) and workspace tenant isolation.
- [ ] **Cloud Storage**: Support S3/MinIO for cloud-native artifact and dataset storage.
- [ ] **Hardened Docker Socket**: Implement `docker-socket-proxy` to restrict Docker daemon access in public production environments.
