# AI Data Analyst — Blast Radius Zero

[English](README.md) | **Bahasa Indonesia**

---

Sistem multi-agent analitik data otonom dengan isolasi keamanan ekstrem (**Blast Radius Zero**). Pengguna cukup mengunggah dataset mentah yang berantakan (CSV/Excel) dan mengajukan pertanyaan dalam bahasa alami. Sistem secara otomatis membuat profil data, merencanakan langkah analisis, membersihkan data dengan *self-healing retry*, menjalankan *Exploratory Data Analysis* (EDA), dan menyusun laporan eksekutif di mana setiap angka dan klaim terbukti (*grounded*) menaut ke kode dan output yang dieksekusi di dalam sandbox.

---

## Arsitektur Sistem

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

> **Aturan Emas Keamanan**: Sandbox eksekusi kode **TIDAK PERNAH** terhubung ke internet dan **TIDAK PERNAH** berkomunikasi langsung dengan LLM. Backend Orchestrator bertindak sebagai perantara yang memvalidasi input/output secara ketat.

---

## Fitur Utama

1. **Blast Radius Zero Sandbox Security**:
   - Setiap eksekusi Python berjalan di dalam container Docker terisolasi satu-kali-pakai (*ephemeral*).
   - `network_mode="none"` (tidak ada akses internet di sandbox).
   - Root filesystem *read-only*, memory tanpa swap, CPU quota, batasan timeout eksekusi, dan `cap_drop=["ALL"]`.
   - Validasi file output anti-symlink traversal via `safe_file`.

2. **Multi-Agent Orchestration (LangGraph)**:
   - **Profiler**: Memindai skema kolom, tipe data, missing values, dan ringkasan statistik awal.
   - **Planner**: Menentukan alur analisis yang optimal berdasarkan profil data dan pertanyaan pengguna.
   - **Cleaner**: Standardisasi format tanggal, pembersihan mata uang Rupiah/angka, dan deduplikasi fuzzy string. Dilengkapi *self-healing code retry loop* jika terjadi error eksekusi.
   - **EDA Specialist**: Melakukan analisis statistik, deteksi anomali, segmentasi, serta visualisasi charts profesional.
   - **Reporter**: Menyintesis temuan analitik menjadi laporan eksekutif terstruktur dengan verifikasi bukti (*grounded claims*).
   - **Advisor**: Memberikan panduan penggunaan sistem dan rekomendasi pertanyaan cerdas jika query pengguna berada di luar cakupan dataset.

3. **Multi-Turn Chat Context**:
   - Percakapan interaktif multi-turn. Agent memahami konteks follow-up dari pertanyaan-pertanyaan sebelumnya.

4. **Multi-Dataset Handling**:
   - Mendukung analisis komparatif beberapa file dataset sekaligus via badge dataset popover yang ringkas.

5. **Analytical Libraries Lengkap**:
   - Sandbox ditenagai oleh Python 3.12 dengan library:
     `pandas`, `numpy`, `matplotlib`, `seaborn`, `scipy`, `openpyxl`, `scikit-learn`, `statsmodels`, `rapidfuzz`, dan `xlrd`.

6. **Interactive Modern UI**:
   - Real-time Server-Sent Events (SSE) streaming progress.
   - Kartu inspeksi *Sandbox Lifecycle* (melihat penggunaan RAM/CPU, batasan sistem, dan kontainer).
   - Modal drawer inspeksi bukti klaim (kode Python yang dijalankan + output aktual).
   - Modal zoom visualisasi chart resolusi tinggi.

---

## Struktur Folder (Clean Architecture)

```
agent-analyst/
├── backend/
│   ├── app/
│   │   ├── agents/          # Node agent LangGraph (profiler, planner, cleaner, eda, reporter, advisor)
│   │   ├── api/             # HTTP presentation layer (deps, routes/health, routes/jobs)
│   │   ├── schemas/         # Pydantic Request/Response DTO models
│   │   ├── services/        # Application business logic (JobService, StorageService)
│   │   ├── agent.py         # Facade Agent wrapper
│   │   ├── config.py        # Environment configuration
│   │   ├── graph.py         # Definisi alur StateGraph LangGraph
│   │   ├── jobs.py          # JobManager & Job lifecycle state
│   │   ├── llm.py           # Client OpenAI-compatible
│   │   ├── main.py          # FastAPI application factory
│   │   ├── prompts.py       # Prompt engineering & system prompts
│   │   └── sandbox.py       # Docker containment & safe execution
│   └── tests/               # Unit & integration test suite (9 test cases)
├── frontend/                # React (Vite) + Tailwind/CSS Glassmorphic UI
├── sandbox-image/           # Dockerfile untuk base image isolasi analitik
├── demo-data/               # Sampel dataset CSV untuk uji coba instan
├── docker-compose.yml       # Orkestrasi multi-container Docker
└── .env.example             # Template konfigurasi environment
```

---

## Menjalankan Aplikasi

### 1. Prasyarat
- Docker & Docker Compose sudah terpasang dan berjalan di sistem Anda.
- API Key LLM yang kompatibel dengan OpenAI (misalnya Azure OpenAI, OpenAI, atau Vultr Serverless Inference).

### 2. Konfigurasi Environment
Salin template `.env.example` menjadi `.env`:
```bash
cp .env.example .env
```
Isi konfigurasi LLM Anda di file `.env`:
```ini
LLM_BASE_URL=https://YOUR-RESOURCE.openai.azure.com/openai/v1/
LLM_API_KEY=your_api_key_here
LLM_MODEL=your_deployment_or_model_name
```

### 3. Jalankan Seluruh Sistem (One-Command Run)
Jalankan perintah berikut di root repositori:
```bash
docker compose up --build
```
Docker Compose akan secara otomatis:
1. Me-rebuild `sandbox-image` (`agent-sandbox:latest`) dengan semua library analisis.
2. Mem-build dan menjalankan service `backend` di port `8000`.
3. Mem-build dan menjalankan service `frontend` (Nginx) di port `3000`.

**Buka browser Anda di: `http://localhost:3000`**

---

## Menjalankan di Mode Development (Opsional)

Jika Anda ingin melakukan pengembangan UI aktif dengan *Vite Hot-Module-Reloading*:

1. Jalankan backend & sandbox lewat Docker:
   ```bash
   docker compose up --build backend
   ```
2. Di terminal terpisah, jalankan frontend secara lokal:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
3. Buka browser di: `http://localhost:5173`.

---

## Menjalankan Pengujian (Testing)

Pengujian backend dirancang dengan *Test Doubles* (Mock LLM dan LocalSandbox) sehingga dapat dijalankan tanpa memerlukan koneksi internet, API key aktif, maupun Docker daemon:

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/
```
*Seluruh 9 pengujian integrasi dan alur logika dipastikan lulus (100% pass).*

---

## Kontrak Event Streaming (SSE)

Sistem menggunakan Server-Sent Events (SSE) pada endpoint `GET /api/jobs/{id}/events`:

| Event Type | Payload Penting | Deskripsi |
|---|---|---|
| `job_started` / `job_done` | `job_id`, `warnings` | Lifecycle awal & akhir job |
| `step_started` / `step_finished`| `step`: profile, clean, eda, report | Tahapan analisis yang sedang aktif |
| `profile_ready` | `profile` (kolom, missing, sample) | Ringkasan profil dataset |
| `plan_ready` | `intent`, `steps`, `plan`, `reason` | Rencana eksekusi agent |
| `attempt_started` / `attempt_failed` | `attempt`, `max_attempts`, `error` | Upaya eksekusi (self-healing retry) |
| `code_generated` | `code` | Kode Python yang digenerate oleh LLM |
| `sandbox_created` | `limits`, `network`, `rootfs` | Metadata isolasi sandbox |
| `sandbox_started` / `sandbox_destroyed` | `exit_code`, `duration_s`, `peak_mem_mb` | Metrik eksekusi kontainer |
| `stdout` / `stderr` | `text` | Log terminal output dari sandbox |
| `diff_ready` | `rows_before`, `rows_after`, `changes` | Ringkasan perubahan data hasil pembersihan |
| `finding` | `id`, `title`, `statement`, `evidence`, `chart` | Temuan analitik spesifik |
| `report_ready` | `report`: `verified_claims`, `interpretation`, `recommendations` | Laporan akhir dengan bukti terverifikasi |

---

## Roadmap Pengembangan Masa Depan

- [ ] **Database Persistence**: Mengintegrasikan PostgreSQL/SQLite untuk menyimpan riwayat sesi dan job jangka panjang.
- [ ] **Multi-Tenancy & Auth**: Menambahkan autentikasi pengguna (OAuth2/JWT) dan isolasi workspace per-organisasi.
- [ ] **Cloud Storage**: Mendukung penyimpanan artefak dan dataset ke S3/MinIO untuk deployment terdistribusi.
- [ ] **Hardened Docker Socket**: Menggunakan `docker-socket-proxy` untuk membatasi akses API daemon Docker di lingkungan produksi publik.
