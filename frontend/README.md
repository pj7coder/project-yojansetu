# YojanSetu Frontend (Next.js)

> **All-India Offline-First Vernacular Public Welfare Discovery & Statutory Eligibility Verification Web Interface**

The YojanSetu frontend is a modern, responsive web application built with Next.js (App Router), React, TypeScript, and Tailwind CSS. It delivers a conversational voice assistant and deterministic welfare scheme discovery for citizens across India, alongside an administrative operations center.

---

## 🌟 Key Features

- **Hands-Free Conversational Voice Assistant**: Automatic continuous voice turns (Auto-Mic turns microphone back on when speech synthesis finishes) with natural Hindi & English speech synthesis, dynamic conversational cadences, and direct parameter extraction.
- **Citizen Parameters Panel**: Real-time atomic profile updates (Age, Gender, Category, Annual Income, Marital Status, Occupation, Land Holding, Disability) with instant statutory eligibility matching.
- **Benefit Wallet & Actionable Cards**: Instant display of eligible monthly & one-time assistance, near-miss eligibility alerts ("What if I earn slightly less?"), and direct 1-click document preparation checklists (Aadhaar, Income Certificate, etc.).
- **High-Performance Admin Operations**: Zero-latency dashboard transitions powered by in-memory cache pre-warming, request deduplication, and fast fallback timeouts.
- **Multi-Source Registry**: Monitored official government sources (myScheme, PM-KISAN, NSP, DBT Bharat, Ayushman Bharat PM-JAY, PMAY-G, PM Vishwakarma, RajSSP, Jan Soochna, e-Mitra).
- **Split-Screen Human Review**: Auditable fact-level verification workspace for government circulars, OCR checks, and rule reconciliation.

---

## 🚀 Getting Started

### 1. Installation

Ensure Node.js 18+ is installed. Install npm packages:

```bash
npm install
```

### 2. Configuration

Create or update `.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

### 3. Running Development Server

```bash
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to open the application.

---

## 📁 Key Routes

- **`/`**: Citizen landing page and national portal overview.
- **`/citizen`**: Conversational voice & text citizen assistant with real-time parameter refinement panel.
- **`/admin`**: National & State operations control center.
- **`/admin/schemes`**: Scheme registry, rule trees, and canonical versioning.
- **`/admin/sources`**: Monitored official National and State portals with manual sync triggers.
- **`/admin/processing`**: 10-stage document ingestion pipeline and retry manager.
- **`/admin/review`**: Prioritized human review workspace for statutory verification.
- **`/admin/system`**: System health diagnostics (DB, Ollama, pgvector, cache, workers).
