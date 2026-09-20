# JanSetu (जनसेतु) — Quick Start & User Manual

An offline-first, vernacular assistant for Rajasthan citizens to discover government welfare schemes via voice and text, powered by an automated document extraction and verification pipeline.

---

## 🚀 1. How to Start

### Option A: 1-Click Launcher (Recommended)
Simply **double-click** `Start.cmd` in the project root folder.
> It will automatically check prerequisites, start the Backend API (:8000), start the Frontend Web App (:3000), wait for health verification, and launch the Citizen Portal directly in your default web browser!

---

### Option B: Manual Two-Terminal Startup

#### Step 1: Start Backend (Terminal 1)
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```
> API running at: **http://localhost:8000** | Interactive Swagger Docs: **http://localhost:8000/docs**

### Step 3: Start Frontend (Terminal 2)
```powershell
cd frontend
npm run dev
```
> Web Portal running at: **http://localhost:3000**

---

## 🌐 2. Key URLs

| Portal | URL | Description |
| :--- | :--- | :--- |
| **Citizen Discovery** | [http://localhost:3000/citizen](http://localhost:3000/citizen) | For citizens: find schemes via text or voice in Hindi / English. |
| **Admin Operations** | [http://localhost:3000/admin](http://localhost:3000/admin) | For admins: upload documents, monitor pipeline, review drafts. |
| **Document Review** | [http://localhost:3000/admin/review](http://localhost:3000/admin/review) | Split-screen PDF vs extracted data verification workspace. |
| **API Documentation** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive testing for all backend endpoints. |

---

## 📖 3. How to Use

### A. Citizen Experience (Discover Schemes)
1. Open **[http://localhost:3000/citizen](http://localhost:3000/citizen)**.
2. Select language (**हिन्दी** or **English**).
3. **State Your Need**:
   - **Text Mode**: Type your situation (e.g. *"मुझे वृद्धावस्था पेंशन चाहिए"* or *"I need financial help for farming"*).
   - **Voice Mode**: Click **"🎤 Voice Mode"**, push to speak in Hindi, and release. The system transcribes and responds with spoken audio.
4. **Answer Dynamic Questions**: The system asks only what's necessary (e.g., age, income, category, land size).
5. **View Eligible Schemes**: Instantly see matching schemes, exact benefit amounts, required documents, and how to apply.

### B. Admin Experience (Direct Upload & Scheme Management)
1. **Method 1: Direct Web Upload**:
   - Navigate to **[http://localhost:3000/admin/documents](http://localhost:3000/admin/documents)**.
   - Click **"Upload Document"** and select a Rajasthan government PDF circular.
   - The document is automatically processed through deduplication, parsing, OCR, chunking, LLM extraction, normalization, and validation, and is **directly published into the database as an ACTIVE scheme** without requiring human verification.

2. **Method 2: Automated Watch Folder (Hot Drop)**:
   - Simply drop any PDF circular into the `backend/storage/watch_folder/` directory.
   - The backend automatically detects the file, ingests it, runs the pipeline, and publishes the scheme into the database.
   - You can also click **"Scan Watch Folder Now"** in the Documents portal for on-demand processing.

3. **Inspect & In-Place Edit Any Scheme**:
   - Navigate to **[http://localhost:3000/admin/schemes](http://localhost:3000/admin/schemes)**.
   - View all live schemes currently in the database with their benefits, criteria, and statuses.
   - Click **"Inspect & Edit Details →"** on any scheme to view or modify:
     - **Overview**: Scheme Name (English/Hindi), Code/ID, Category, Department, Origin, Status, Description.
     - **Benefits**: Exact cash, pensions, or subsidies + add/remove benefits.
     - **Eligibility**: Min/max age, income cap, gender, land holding, rule conditions, and exclusions.
     - **Required Documents**: Jan Aadhaar, Aadhaar, certificates, mandatory toggles.
     - **Application**: Official portal URLs, department offices, step-by-step instructions, and fees.
     - **PDF Provenance**: Original circular PDF filename and verbatim extracted evidence snippets.
   - Click **"Save Changes to Database"** to immediately update the scheme, vector search indices, and RAM rule cache.

---

## 🧪 4. Quick Verification Commands

From `backend/` directory:
```powershell
# Run core health & database checks
python -m pytest tests/test_health.py tests/test_database.py -q

# Run citizen conversation and eligibility tests
python -m pytest tests/test_citizen_flow.py -q
```

---

## ❓ 5. Quick Troubleshooting

- **Database Connection Error**: Verify PostgreSQL is running on port 5432 and credentials match `.env` (default: `POSTGRES_DB=jansetu`, `POSTGRES_USER=postgres`).
- **Port Conflict (8000 or 3000)**: Close background instances or run on alternate ports:
  - Backend: `uvicorn app.main:app --port 8001`
  - Frontend: `npm run dev -- -p 3001`
- **PowerShell Script Execution Error**: Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in PowerShell before activating `.venv`.
