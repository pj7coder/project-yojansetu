# YojanSetu — Gold-Standard Evaluation Dataset (v1.0)

> **Human-Verified Reference Truth for Independent Benchmark Evaluation**  
> *Establishing ground truth for Extraction (Day 29), Eligibility (Day 30), Search (Day 31), and Voice/Conversation (Day 32).*

---

## 1. Overview & Core Architecture

The YojanSetu Gold Dataset establishes the immutable expected truth across the four critical layers of the system:

```text
                 OFFICIAL GOVERNMENT EVIDENCE
                            ↓
                     HUMAN ANNOTATION
                            ↓
                       HUMAN REVIEW
                            ↓
                ┌────────────────────┐
                │ GOLD DATASET v1.0  │
                └─────────┬──────────┘
                          │
       ┌──────────────────┼──────────────────┐
       │                  │                  │
   Extraction         Eligibility         Search
    Day 29             Day 30            Day 31
       │                  │                  │
       └──────────────────┼──────────────────┘
                          ↓
                      Voice QA
                       Day 32
```

### Invariant Rules:
1. **Zero AI Self-Annotation**: The system being evaluated does not create its own expected answers. All gold facts are derived directly from official government circulars, verified scheme versions, or human-curated audio fixtures.
2. **Strict Data-Leakage Protection**: The `GoldBenchmarkLoader.get_runtime_inputs(...)` interface provides evaluators with input-only structures, stripping expected labels to prevent test-set contamination.
3. **No Real Citizen PII**: All eligibility citizen profiles are strictly synthetic. An automated PII validator checks for real 12-digit Aadhaar numbers, 10-digit mobile numbers, and email addresses.

---

## 2. Dataset Versioning & Manifest

- **Dataset Version**: `1.0`
- **Canonical Manifest Hash (SHA-256)**: `14467fd3edbe21f63a3a16b104089f845e194ce116ea0a2e563a85a7c686b46e`
- **Total Cases**: `280`

### Task & Split Breakdown:

| Task | Subsystem | DEV | VALIDATION | TEST | TOTAL | Purpose |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Extraction** | Document Intelligence | 15 | 19 | 26 | **60** | PDF parsing, OCR text, tables, provisos, negative chunks, injection test |
| **Eligibility** | Deterministic Engine | 30 | 30 | 60 | **120** | Tri-state logic, boundaries, short-circuiting, temporal version amendments |
| **Search** | Discovery & Ranking | 15 | 15 | 20 | **50** | Hindi/English/Hinglish queries, profile filtering, negative ranking |
| **Voice** | STT & Audio Pipeline | 10 | 12 | 20 | **42** | 40 Rajasthan recordings + silence & noise, context semantics, VAD |
| **Conversation**| State Machine | 2 | 2 | 4 | **8** | Scripted multi-turn flows, disqualification, correction, why-asked |
| **TOTAL** | | **72** | **78** | **130** | **280** | |

---

## 3. Directory Structure

```text
benchmarks/gold/
├── README.md
├── CHANGELOG.md
├── coverage_report.md
├── gold_review_report.md
└── v1/
    ├── manifest.json
    ├── annotation/
    │   └── GUIDELINES.md
    ├── references/
    │   └── schemes_catalog.json
    ├── extraction/
    │   └── cases/
    │       ├── dev/
    │       ├── validation/
    │       └── test/
    ├── eligibility/
    │   └── cases/
    │       ├── dev/
    │       ├── validation/
    │       └── test/
    ├── search/
    │   └── cases/
    │       ├── dev/
    │       ├── validation/
    │       └── test/
    ├── voice/
    │   ├── audio/              # 42 WAV recordings (16kHz 16-bit mono)
    │   └── cases/
    │       ├── dev/
    │       ├── validation/
    │       └── test/
    └── conversation/
        └── cases/
            ├── dev/
            ├── validation/
            └── test/
```

---

## 4. CLI Commands

Validate the entire dataset against schemas, evidence references, audio hashes, and PII filters:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.gold.validate --version v1
```

Display task counts, split distributions, and coverage tags:
```powershell
python -m app.gold.summary --version v1
```

Freeze the dataset manifest and calculate canonical SHA-256:
```powershell
python -m app.gold.freeze --version v1.0
```
