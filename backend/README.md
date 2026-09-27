# YojanSetu Backend (FastAPI)

> **All-India Offline-First Vernacular Public Welfare Discovery & Statutory Eligibility Verification Engine**

The YojanSetu backend is a high-performance Python FastAPI service providing deterministic rule evaluation, document ingestion and extraction, source monitoring, and conversational citizen assistance for National (Central) and State welfare schemes.

---

## 🏛️ Core Capabilities

- **National & State Schemes Knowledge Graph**: Covers Central schemes (e.g., PM-KISAN, Ayushman Bharat PM-JAY, PMAY-G, National Scholarship Portal, DBT Bharat, PM Vishwakarma) and State schemes (e.g., RajSSP, Jan Soochna, Chiranjeevi, e-Mitra).
- **Deterministic Eligibility Engine**: Zero-hallucination statutory rule evaluation with strict logical operators (`AND`, `OR`, `NOT`, comparative thresholds).
- **Official Source Monitoring**: Proactive HTTP conditional checking (ETag, Last-Modified, SHA-256 body/link fingerprints) across registered official portals.
- **Multilingual Vernacular Support**: Conversational Hindi and English dialogue management, STT transcript normalization, and natural voice interaction.
- **Admin & Human-in-the-Loop Review**: Complete operational oversight, conflict resolution, document retry pipelines, and split-screen audit verification.

---

## 🚀 Getting Started

### 1. Environment & Dependencies

Make sure Python 3.11+ is installed. Activate the virtual environment:

```bash
# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

Install requirements:

```bash
pip install -r requirements.txt
```

### 2. Database Setup

Configure PostgreSQL database in `.env` (or use default `127.0.0.1:5432/yojansetu`):

```bash
# Initialize schema and seed verified national and state official sources
python scripts/seed_official_sources.py
```

### 3. Running the Server

Start the development server with live reload:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive API documentation will be available at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 📁 Architecture & Directory Structure

```text
backend/
├── app/
│   ├── admin/             # Operations dashboard, activity feed, and health monitors
│   ├── api/               # Versioned REST API routers (/api/v1)
│   ├── conversation/      # Deterministic citizen multi-turn dialogue manager
│   ├── core/              # Config, security, logging, and application lifecycle
│   ├── database/          # SQLAlchemy models, sessions, and migrations
│   ├── eligibility/       # Statutory canonical rule engine (zero LLM evaluation)
│   ├── ingestion/         # Document ingestion, PDF parsing, OCR fallback
│   ├── monitoring/        # Official source monitoring and change detection
│   ├── stt/               # Speech-to-text normalizers, metric trackers
│   └── tts/               # Text-to-speech audio synthesis endpoints
├── scripts/               # DB seeders and administrative maintenance scripts
└── storage/               # Monitored snapshots, uploaded documents, verified rules
```

---

## 🛡️ Key Principles

1. **Deterministic Verification First**: Citizen eligibility is NEVER decided by an unpredictable generative prompt. All eligibility verdicts are determined by formal statutory AST trees.
2. **Immutable Evidence Trails**: All canonical facts link directly to gazetted circulars or official portal URLs.
3. **Resilient Offline Architecture**: Operates locally with Ollama (`llama3.2:3b`) without hard dependencies on cloud APIs.
