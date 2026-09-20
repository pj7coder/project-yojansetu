# JanSetu (जनसेतु)

> **Offline-first vernacular government-scheme discovery assistant for Rajasthan.**

**Current Status**: Day 29 — Extraction Accuracy Evaluation + Failure Analysis

---

## 1. Overview

JanSetu is designed to empower citizens of Rajasthan—especially rural, elderly, and Hindi-first users—to discover and understand eligible government welfare schemes using natural voice and vernacular language, functioning reliably offline without cloud API lock-in.

### Critical Architecture Principle:
```text
Normalization ≠ Validation ≠ Verification ≠ Human Approval ≠ Publication
```
- **Normalization (Day 10)**: Transforms raw heterogeneous extractions into a structured, machine-readable canonical schema, preserving verbatim source text and evidence references.
- **Validation (Day 11)**: Deterministically verifies that data is internally consistent, structurally well-formed, logically possible, and provenance-linked using Python/Pydantic/rules. (Zero LLM).
- **Verification (Day 12)**: Second-pass verification challenging individual canonical facts against exact government source evidence using deterministic checks and local Llama 3.2 3B (`SUPPORTED`, `CONTRADICTED`, `NOT_ENOUGH_EVIDENCE`).
- **Human Review (Day 13)**: Authorized reviewer inspects warnings, contradictions, and OCR risk in split-screen PDF review workspace and makes auditable, field-level decisions (`APPROVE`, `EDIT`, `REJECT`).
- **Publication (Future)**: Controlled promotion to production citizen-facing corpus.

> **Important Guarantee**: Passing Day 11 validation checks structure. Day 12 evidence verification challenges factual support against official text. Even **100% SUPPORTED ≠ HUMAN VERIFIED**. Furthermore, **HUMAN_VERIFIED ≠ CITIZEN PUBLISHED**. A scheme draft is NEVER automatically published to production without explicit promotion.

---

## 2. Processing Pipeline Architecture

```text
Government PDF
      ↓
Ingestion (Day 4)
      ↓
Duplicate & Version Detection (Day 5)
      ↓
Structured MinerU Parser (Day 6)
      ↓
Selective PaddleOCR Fallback (Day 7)
      ↓
Canonical Merged Document
      ↓
Semantic Document Chunking (Day 8)
      ↓
Llama 3.2 3B Raw Extraction & Substring Evidence (Day 9)
      ↓
Canonical Normalization & Rule Trees (Day 10)
      ↓
Deterministic Validation Engine (Day 11)
      ↓
Second-Pass Evidence Verification (Day 12)
      ↓
READY_FOR_HUMAN_REVIEW (Day 13 Input)
      ↓
Admin Review Workspace (/admin/review/[draftId])
      ↓
Physical PDF + Exact Evidence + Canonical Field Comparison
      ↓
Field Decisions: APPROVE / EDIT / REJECT / NOT_APPLICABLE
      ↓
Automatic Revalidation & Re-verification on Edit
      ↓
Strict Backend Completion Guards Enforced
      ↓
HUMAN_VERIFIED (or HUMAN_REJECTED)
      ↓
Sealed Verified Artifact (storage/verified/<draft_id>/)
```

---

## 3. Ollama Setup & Offline Execution

JanSetu uses [Ollama](https://ollama.com/) to run `llama3.2:3b` locally on CPU or GPU.

### 1. Install & Start Ollama
Download and install Ollama from [ollama.com](https://ollama.com/download). Start the Ollama background daemon:
```bash
ollama serve
```

### 2. Pull Llama 3.2 3B Model
Download the official model once (offline use thereafter):
```bash
ollama pull llama3.2:3b
```
Verify the model is installed:
```bash
ollama list
# Output should display:
# NAME             ID              SIZE      MODIFIED
# llama3.2:3b      a80c4f17acd5    2.0 GB    ...
```

### 3. Verify Health via JanSetu API
```bash
curl http://localhost:8000/api/v1/system/llm-health
# Output:
# {"status":"ok","provider":"ollama","model":"llama3.2:3b","model_available":true,"installed_models":["llama3.2:3b"]}
```

---

## 4. Storage Hierarchy

```text
storage/
├── incoming/             # Monitored landing folder for new files
├── originals/            # Untouched original government PDFs
│   └── <document_id>/
│       └── original.pdf  # Deterministic, read-only original file
├── parsed/               # Structured parsed outputs (Day 6)
│   └── <document_id>/
│       ├── document.json # Standardized JanSetu JSON schema
│       └── document.md   # Clean Markdown for human review
├── ocr/                  # Corrective OCR outputs (Day 7)
│   └── <document_id>/
│       ├── pages/        # Rendered 250 DPI PNGs (only for OCR'd pages)
│       └── merged_document.json # Canonical merged document for chunking
├── chunks/               # Semantic Chunking Storage (Day 8)
│   └── <document_id>/
│       ├── chunks.json   # Master chunk catalog with diagnostics
│       └── chunks/       # Rendered prompt text files per chunk
├── extracted/            # Local LLM Extractions (Day 9)
│   └── <document_id>/
│       ├── document_extractions.json # Document-level aggregation catalog
│       └── <chunk_id>/               # Per-chunk extraction artifacts
│           ├── request_metadata.json # Prompt version, options, token estimates
│           ├── raw_response.txt      # Exact verbatim text returned by LLM
│           ├── extraction.json       # Validated Pydantic ChunkExtractionResult
│           └── validation.json       # Deterministic evidence verification report
├── normalized/           # Canonical Scheme Drafts (Day 10)
│   └── <document_id>/<draft_id>/
│       ├── canonical.json            # Machine-readable canonical scheme draft
│       ├── conflicts.json            # Identified factual contradictions
│       └── normalization_report.json # Diagnostic aggregation report
├── validation/           # Deterministic Validation Reports (Day 11)
│   └── <scheme_draft_id>/
│       ├── validation_report.json    # Complete validation issues & audit
│       └── validation_summary.json   # Blockers/errors/warnings summary
├── fingerprints/         # Text fingerprint cache for duplicate detection
├── failed/               # Quarantined corrupted/invalid files
└── archived/             # Historical, deprecated, or superseded documents
```

---

## 5. Configuration Settings

Configurable in `backend/.env`:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `VALIDATOR_VERSION` | `1.0` | Validation engine implementation version |
| `VALIDATION_SCHEMA_VERSION` | `1.0` | Validation schema specification version |
| `MAX_REASONABLE_AGE` | `125` | Maximum age boundary before raising `AGE_SUSPICIOUS` |
| `MAX_RULE_DEPTH` | `20` | Maximum allowable depth for nested boolean rule trees |
| `CANONICAL_SCHEMA_VERSION` | `1.0` | Canonical scheme schema specification version |
| `NORMALIZER_VERSION` | `1.0` | Normalization engine version |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Base URL for local Ollama API |
| `OLLAMA_MODEL` | `llama3.2:3b` | Target local model identifier |
| `STORAGE_ROOT` | `./storage` | Base filesystem directory for all storage tiers |

---

## 6. Running the Background Services

### Deterministic Scheme Validation Worker (Day 11):
```bash
### Evidence Verification Worker (Day 12):
```bash
cd backend
.\.venv\Scripts\activate

# Continuous polling for READY_FOR_EVIDENCE_VERIFICATION drafts:
python -m app.verification.worker --loop

# Process all pending drafts in batch:
python -m app.verification.worker --all

# Verify single scheme draft (force re-verification):
python -m app.verification.worker --draft-id <UUID> --force
```

### Deterministic Validation Worker (Day 11):
```bash
cd backend
.\.venv\Scripts\activate

# Continuous polling for READY_FOR_VALIDATION drafts:
python -m app.validation.worker --loop

# Process all ready drafts in batch:
python -m app.validation.worker --all

# Validate single scheme draft (force bypass of cache):
python -m app.validation.worker --draft-id <UUID> --force
```

### Canonical Normalization Worker (Day 10):
```bash
python -m app.normalization.worker --loop
```

### Document Extraction Worker (Day 9):
```bash
python -m app.extraction.worker
```

### Document Chunking Worker (Day 8):
```bash
python -m app.chunking.worker
```

### Document OCR Worker (Day 7):
```bash
python -m app.ocr.worker
```

### Document Parser Worker (Day 6):
```bash
python -m app.parser.worker
```

### Duplicate Detection Worker (Day 5):
```bash
python -m app.duplicate_detection.worker
```

---

## 7. Validation Lifecycle & Severity Model

### Lifecycle States:
```text
READY_FOR_VALIDATION
        ↓
    VALIDATING
        ↓
┌────────────────────────┬────────────────────────┐
│                        │                        │
VALIDATION_PASSED   VALIDATION_REVIEW_REQUIRED   VALIDATION_FAILED
        │
        ↓
READY_FOR_EVIDENCE_VERIFICATION (Day 12)
```

### Severity Levels:
- **INFO**: Informational notice (e.g. `DUPLICATE_DOCUMENT_REQUIREMENT`, `CUSTOM_FIELD_REQUIRED`, `REDUNDANT_RULE`). Does not impede progression.
- **WARNING**: Suspicious condition (e.g. `AGE_SUSPICIOUS`, `INCOME_PERIOD_MISMATCH`, `UNSUPPORTED_FOR_AUTOMATIC_ELIGIBILITY`). Moves draft to `VALIDATION_REVIEW_REQUIRED`.
- **ERROR**: Serious violation or contradiction (e.g. `AGE_NEGATIVE`, `INCOME_NEGATIVE`, `CONTRADICTORY_RULES`, `UNRESOLVED_CRITICAL_CONFLICT`, `OPERATOR_INCOMPATIBLE`). Moves draft to `VALIDATION_REVIEW_REQUIRED`.
- **BLOCKER**: Structural or provenance failure (e.g. `SCHEMA_INVALID`, `EVIDENCE_REGISTRY_MISSING`, `DOCUMENT_MISMATCH`, `RULE_DEPTH_EXCEEDED`, `APPLICATION_URL_UNSAFE`). Immediately causes `VALIDATION_FAILED`.

---

## 8. Second-Pass Evidence Verification (Day 12)

### What Evidence Verification Does
Validation (Day 11) checks structure, schema bounds, and internal consistency.
Evidence verification (Day 12) challenges individual canonical facts against the exact official government evidence to detect LLM extraction hallucinations, number discrepancies, operator inversions, and missing support.

### Strict Three-Result Classification:
- **SUPPORTED**: The government source evidence directly and unequivocally supports the canonical fact without altering its meaning.
- **CONTRADICTED**: The government source evidence directly conflicts with the fact (e.g. source says ₹2 lakh, fact asserts ₹3 lakh; or source says strictly `> 60`, fact asserts `>= 60`).
- **NOT_ENOUGH_EVIDENCE**: The evidence does not mention the fact, is ambiguous, incomplete, requires missing context, or supports only part of a compound statement.

> **CRITICAL RULE**: `SUPPORTED ≠ HUMAN VERIFIED`. Even a draft with 100% supported facts is **never** automatically published to production. It advances strictly to `READY_FOR_HUMAN_REVIEW` for Day 13 human verification.

### Deterministic Priority
Deterministic checks (numbers, operators, monthly vs annual, personal vs family income) are executed before calling the LLM. **Deterministic contradictions always override the LLM.**

---

## 9. Human Verification Workflow & Admin Review System (Day 13)

### Core Philosophy
No government scheme becomes trusted production data merely because an LLM extracted it, validation passed, and evidence verification supported it. A human reviewer remains the final verification authority before publication.

> **Central Principle**: Human approval must itself be completely traceable and auditable. We record **who reviewed**, **what they reviewed**, **what value existed before**, **what value exists after**, **why it was changed**, **when it was changed**, and **which evidence supported it**.

### Lifecycle Transitions
```text
READY_FOR_HUMAN_REVIEW
          ↓ (Reviewer starts review)
    IN_HUMAN_REVIEW
          ↓
┌───────────────────────────────────────┐
│ Admin Review Workspace                │
│ • Physical PDF viewer with page jump  │
│ • Canonical vs Raw vs Evidence        │
│ • Day 11 Validation issues            │
│ • Day 12 Verification status & OCR    │
│ • Side-by-side Conflict Resolution    │
│ • Structured Field Editing            │
└───────────────────────────────────────┘
          ↓
Approve / Edit / Reject Facts
          ↓
Automatic Revalidation & Re-verification on Edit
          ↓
Completion Guards Enforced
          ↓
   HUMAN_VERIFIED (or HUMAN_REJECTED)
          ↓
Sealed Verified Artifact (storage/verified/<draft_id>/)
```

> **Important Boundary**: `HUMAN_VERIFIED ≠ PUBLISHED TO CITIZENS`. Final publication to the citizen corpus remains a controlled future operation. Production `schemes` table records are not automatically inserted upon verification.

### Field-Level Review Decisions
Reviews are strictly field-level across scheme identity, eligibility rules, exclusions, benefits, required documents, application channels, and important dates:
- **`APPROVE`**: Fact confirmed. Overriding `CONTRADICTED` or `NOT_ENOUGH_EVIDENCE` strictly requires a mandatory audit `override_reason`.
- **`EDIT`**: Reviewer modifies canonical value. Requires mandatory `edit_reason`. Automatically modifies canonical JSON on disk, updates SHA-256, increments `review_version`, marks prior reports `STALE`, and reruns deterministic validation and evidence verification!
- **`REJECT`**: Excludes spurious or repealed facts from the verified artifact while preserving full audit history.
- **`NOT_APPLICABLE`**: Flags non-scheme or extraneous extracted fields without silent deletion.

### Conflict Resolution
Side-by-side resolution for conflicting extractions (e.g. ₹2 lakh vs ₹3 lakh):
- **`SELECT_VALUE`**: Choose Candidate A or Candidate B with mandatory rationale.
- **`KEEP_CONDITIONAL`**: Preserve both branches if non-conflicting (e.g. General ₹2L, SC/ST ₹3L).
- **`REJECT_FIELD`**: Disqualify both candidates.

### Strict Completion Guards
A scheme draft CANNOT be finalized as `HUMAN_VERIFIED` if:
1. Any mandatory fact remains `PENDING`.
2. Any unresolved `BLOCKER` validation issues remain.
3. Any unaddressed `CONTRADICTED` fact remains without an explicit override reason.
4. Canonical artifact SHA-256 is stale.
5. Optimistic concurrency version mismatch occurs.

### Sealed Verified Artifacts
Upon successful signoff, verified artifacts are sealed under:
```text
storage/verified/<scheme_draft_id>/
├── verified_scheme.json   # Approved canonical structure + signoff metadata
├── review_summary.json    # Summary metrics (approved, edited, rejected counts)
└── audit_snapshot.json    # Chronological immutable event history
```

---

## 10. Deterministic Citizen Eligibility Engine (Day 14)

JanSetu evaluates citizen eligibility using pure, deterministic Python rule execution over sealed `HUMAN_VERIFIED` government scheme rules.

```text
Citizen Profile (Partial / Full)
              +
Human-Verified Scheme Rules (AST)
              ↓
Deterministic Eligibility Engine
              ↓
┌─────────────────────────────────┐
│ ELIGIBLE                        │
│ NOT_ELIGIBLE                    │
│ MORE_INFORMATION_REQUIRED       │
└─────────────────────────────────┘
              ↓
Structured Reasons & Minimal Missing Fields
```

### Core Philosophy
1. **Verified Government Rule + Python = Decision**: Eligibility decisions strictly evaluate compiled rule trees. Artificial Intelligence / LLMs are never used to decide citizen eligibility.
2. **Three Discrete Outcomes**:
   - `ELIGIBLE`: Positive criteria definitively satisfied, no exclusions triggered.
   - `NOT_ELIGIBLE`: Mandatory criterion definitively violated or exclusion triggered.
   - `MORE_INFORMATION_REQUIRED`: Incomplete citizen information prevents a definitive decision without assuming falsehood.
3. **Three-State Kleene Logic**:
   - `AND`: `FALSE + anything -> FALSE` (short-circuit rejection); `TRUE + UNKNOWN -> UNKNOWN`.
   - `OR`: `TRUE + anything -> TRUE` (short-circuit satisfaction); `FALSE + UNKNOWN -> UNKNOWN`.
   - `NOT`: `NOT TRUE -> FALSE`, `NOT FALSE -> TRUE`, `NOT UNKNOWN -> UNKNOWN`.
4. **Minimal Missing Fields**: When an `OR` branch is satisfied or an `AND` branch fails, unneeded missing fields are omitted through safe short-circuiting.
5. **Strict Data Privacy**: Citizen profiles are **never permanently stored** in the database by default. Evaluation occurs purely in memory. No sensitive citizen attributes (income, caste, disability) are logged.

---

## 11. Candidate Filtering & Semantic Ranking (Day 15)

JanSetu resolves the challenge of scaling eligibility evaluation across thousands of verified schemes using a two-tier retrieval architecture:
1. **Coarse Candidate Filtering (Fast SQL)**: High-recall, conservative PostgreSQL filtering narrowing verified schemes by jurisdiction, dates, and geographic scope.
2. **Authoritative Decision**: Day 14 deterministic `EligibilityEngine` evaluates the candidates into `ELIGIBLE`, `MORE_INFORMATION_REQUIRED`, and `NOT_ELIGIBLE` (pruned).
3. **Multilingual Relevance Ranking (FastEmbed / PGVector)**: Dense multilingual vector embeddings (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions) ranking eligible schemes by citizen need relevance.

```text
Citizen Profile + Need Text
            ↓
CandidateFilterService (Fast SQL on search metadata)
            ↓
Candidate Scheme Set (~50)
            ↓
EligibilityEngine (Day 14 Deterministic Python AST)
            ↓
┌─────────────────────────────────┐
│ ELIGIBLE                        │
│ MORE_INFORMATION_REQUIRED       │
│ NOT_ELIGIBLE (Excluded)         │
└─────────────────────────────────┘
            ↓
SemanticSchemeRanker (Cosine similarity on candidate vectors)
            ↓
DiscoveryResponse (Top Relevant Schemes in separate buckets)
```

### Critical Rules
- **Semantic similarity does NOT decide eligibility**: Vector similarity is used solely for relevance ordering among schemes that are already deemed `ELIGIBLE` or `MORE_INFORMATION_REQUIRED`.
- **High Recall Invariant**: Unknown citizen profile fields never filter out valid candidates (e.g. unknown citizen district preserves district-specific schemes).
- **Offline Embeddings**: Local ONNX model execution via `fastembed` with no external API dependency.
- **Privacy Guaranteed**: Citizen profiles and search need texts are processed in-memory and **never permanently stored** in the database by default.

---

## 12. Scheme Discovery REST APIs

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/schemes/discover` | Discover and rank relevant verified schemes for a citizen profile and need |
| `GET` | `/api/v1/admin/search-index/status` | Diagnostic inspection of search metadata and embedding index |
| `POST` | `/api/v1/admin/search-index/rebuild` | Trigger indexing and batch embedding of verified schemes |

#### Example Request:
```json
POST /api/v1/schemes/discover
{
  "profile": {
    "age": 66,
    "state": "Rajasthan",
    "occupation": "FARMER",
    "family_income": 180000
  },
  "need_text": "मुझे खेती और फसल के लिए आर्थिक सहायता चाहिए",
  "limit": 5
}
```

#### Example Response:
```json
{
  "eligible": [
    {
      "scheme_id": "RJ-FARM-001",
      "scheme_name": "Kisan Krishi Sahayata Yojana",
      "scheme_name_hi": "किसान कृषि सहायता योजना",
      "eligibility_status": "ELIGIBLE",
      "semantic_similarity": 0.8842,
      "matched_signals": ["FARMER", "AGRICULTURE"]
    }
  ],
  "more_information_required": [
    {
      "scheme_id": "RJ-LAND-002",
      "scheme_name": "Small Farmer Subsidy Scheme",
      "eligibility_status": "MORE_INFORMATION_REQUIRED",
      "missing_fields": ["land_holding"],
      "semantic_similarity": 0.8120
    }
  ],
  "meta": {
    "candidates_before_filter": 5000,
    "sql_candidates": 48,
    "evaluated_count": 48,
    "eligible_count": 1,
    "more_information_required_count": 1,
    "not_eligible_count": 46,
    "semantic_ranking_used": true,
    "evaluation_duration_ms": 115.4
  },
  "engine_version": "1.0"
}
```

### Embedding Generation CLI
To rebuild search metadata and vector embeddings from verified schemes:
```bash
python -m app.search.build_embeddings --batch-size 32
```

---

## 12. Citizen Multi-Turn Sessions & Intelligent Question Selection (Day 16)

JanSetu features a stateful, privacy-preserving conversational discovery architecture:

```text
               Verified Schemes (PostgreSQL)
                            ↓
               Compiled Rule Cache (In-Process RAM)
                            ↓
Citizen → Ephemeral Session → Structured Facts
                            ↓
              Candidate Discovery (Fast SQL)
                            ↓
              Eligibility Engine (Deterministic AST)
                            ↓
              ┌─────────────┴────────────┐
              │                          │
           ELIGIBLE              MORE INFORMATION
              │                          │
              │                  Missing Field Analysis
              │                          ↓
              └────────────→ NextQuestionSelector (Information-Gain)
                                         ↓
                                 Best Next Field
```

### Critical Architecture Guarantees
- **Backend Controls Session State**: Structured profile facts are tracked deterministically in process RAM (`CitizenSessionManager`). The LLM does **NOT** maintain session memory.
- **Zero Database Profile Persistence**: Citizen profiles are ephemeral in-memory objects; no citizen database tables exist. Sessions automatically expire after `CITIZEN_SESSION_TTL_MINUTES` (default 45 minutes) and can be explicitly cleared at any time.
- **Privacy-Preserving Logs**: Internal logs record session IDs, lifecycle events, and field keys, but **never personal citizen values** (income, caste, disability, etc.).
- **Compiled Rule RAM Cache (`VerifiedRuleCache`)**: Active human-verified rule trees are compiled into immutable Python ASTs and cached in RAM. Recompilation on repeated requests is eliminated, with automatic cache refreshes when schemes are verified or updated in review.
- **Deterministic Next-Question Selection (`NextQuestionSelector`)**: The system calculates the information gain of each missing attribute across candidate schemes:
  $$U(f) = \sum_{s \in \text{Candidates}(f)} \left( w_{\text{rel}}(s) + B_{\text{one-away}}(s) \right) - P_{\text{repeat}}(f) - C_{\text{sens}}(f)$$
  - Prioritizes fields affecting the largest number of high-relevance candidates.
  - Grants an **immediate resolution bonus** (+2.0) to schemes that are only 1 field away from a decision.
  - Penalizes repeatedly asked questions to prevent interrogation fatigue.
  - Applies sensitivity tie-breaking to favor less invasive questions (e.g. district over income).
  - Stops asking questions once target confirmed schemes are reached (`ENOUGH_CONFIRMED_RESULTS`) or when all required fields are declined (`CANNOT_RESOLVE_WITH_AVAILABLE_INFORMATION`).
  - Fully respects Day 14 Boolean short-circuits (e.g., `BPL OR income <= 200000` with `BPL=True` prunes income so it is never requested).

---

## 13. Citizen Sessions & Cache REST APIs

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/citizen/sessions` | Create a new ephemeral citizen session with secure UUID |
| `GET` | `/api/v1/citizen/sessions/{id}` | Retrieve session summary (known fields, declined fields, TTL) |
| `GET` | `/api/v1/citizen/sessions/{id}/profile` | Inspect structured session profile facts (development/UI) |
| `PATCH` | `/api/v1/citizen/sessions/{id}/profile` | Apply partial profile updates (patch semantics, correction support) |
| `POST` | `/api/v1/citizen/sessions/{id}/decline-field` | Record citizen refusal to answer a specific field |
| `POST` | `/api/v1/citizen/sessions/{id}/discover` | Run candidate discovery and receive deterministic next question |
| `DELETE` | `/api/v1/citizen/sessions/{id}` | Explicitly delete/reset citizen session from memory |
| `GET` | `/api/v1/admin/cache/rules` | Inspect rule cache metrics (hits, misses, loads, refreshes) |
| `POST` | `/api/v1/admin/cache/rules/refresh` | Trigger on-demand cache refresh for a scheme or entire cache |

#### Multi-Turn Discovery Example:

**Turn 1:** Citizen provides age and state:
```json
PATCH /api/v1/citizen/sessions/3e8a4d7f.../profile
{
  "profile": {
    "age": 64,
    "state": "Rajasthan"
  }
}
```

Request discovery and next question:
```json
POST /api/v1/citizen/sessions/3e8a4d7f.../discover
{
  "need_text": "मुझे खेती के लिए सहायता चाहिए"
}
```

Response:
```json
{
  "session_id": "3e8a4d7f...",
  "eligible": [],
  "more_information_required": [
    {
      "scheme_id": "RJ-FARM-001",
      "scheme_name": "Kisan Krishi Sahayata Yojana",
      "missing_fields": ["family_income"]
    },
    {
      "scheme_id": "RJ-FARM-002",
      "scheme_name": "Small Farmer Subsidy",
      "missing_fields": ["family_income"]
    }
  ],
  "next_question": {
    "field": "family_income",
    "reason_code": "RESOLVES_MOST_RELEVANT_SCHEMES",
    "affected_scheme_count": 2,
    "display_name_en": "Annual Family Income",
    "display_name_hi": "वार्षिक पारिवारिक आय",
    "data_type": "currency"
  }
}
```

**Turn 2:** Citizen answers `family_income = 120000`:
```json
PATCH /api/v1/citizen/sessions/3e8a4d7f.../profile
{
  "profile": {
    "family_income": 120000
  }
}
```
Subsequent discovery immediately promotes the agricultural schemes to `ELIGIBLE`.

---

## 14. Eligibility REST APIs

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/eligibility/evaluate/{scheme_id}` | Deterministically evaluate citizen profile against a verified scheme |
| `POST` | `/api/v1/eligibility/evaluate` | Batch evaluate citizen profile across multiple verified schemes |

---

## 15. Human Review REST APIs

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/review/queue` | Paginated, priority-ordered review queue (contradictions, OCR risks, conflicts) |
| `POST` | `/api/v1/scheme-drafts/{draft_id}/review/start` | Start or resume active review session |
| `GET` | `/api/v1/scheme-drafts/{draft_id}/review` | Consolidated review workspace detail (facts, validation, verification, audit) |
| `POST` | `/api/v1/review-items/{item_id}/decision` | Submit field decision (`APPROVE`, `EDIT`, `REJECT`, `NOT_APPLICABLE`) |
| `POST` | `/api/v1/review-items/{item_id}/approve` | Convenience route to approve item |
| `POST` | `/api/v1/review-items/{item_id}/reject` | Convenience route to reject item |
| `POST` | `/api/v1/scheme-drafts/{draft_id}/conflicts/{id}/resolve` | Resolve candidate contradiction side-by-side |
| `POST` | `/api/v1/scheme-drafts/{draft_id}/review/complete` | Enforce completion guards and seal verified scheme artifact |
| `POST` | `/api/v1/scheme-drafts/{draft_id}/review/reject` | Reject scheme draft completely with mandatory reason (`HUMAN_REJECTED`) |
| `POST` | `/api/v1/scheme-drafts/{draft_id}/review/reopen` | Reopen verified draft creating new versioned session |

---

## 16. Evidence Verification REST APIs

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/scheme-drafts/{draft_id}/verify-evidence` | Execute second-pass evidence verification on draft |
| `GET` | `/api/v1/scheme-drafts/{draft_id}/evidence-verification` | Get latest verification run summary and metrics |
| `GET` | `/api/v1/scheme-drafts/{draft_id}/fact-verifications` | Query fact evaluations (filterable by `result`, `fact_type`, `risk_level`, `verification_method`) |
| `GET` | `/api/v1/fact-verifications/{id}` | Inspect single atomic fact verification detail |
| `GET` | `/api/v1/evidence-verification-runs/{run_id}` | Retrieve specific verification run details |

---

## 17. Validation REST APIs

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/scheme-drafts/{draft_id}/validate` | Execute deterministic validation on scheme draft |
| `GET` | `/api/v1/scheme-drafts/{draft_id}/validation` | Get latest validation run summary and metrics |
| `GET` | `/api/v1/scheme-drafts/{draft_id}/validation/issues` | Query validation issues (filterable by severity, rule_code, status) |
| `GET` | `/api/v1/validation-runs/{run_id}` | Retrieve specific validation run details |

---

## 18. Smart Government Source Monitoring & Change Detection (Day 17)

JanSetu monitors approved Rajasthan government webpages to answer:
> **"Has this official government source changed since the last successful check?"**

### Architectural Flow:
```text
Official Rajasthan Source Registry (Day 3 sources + source_urls)
                    ↓
        Due Approved URLs (enabled=True, crawl_allowed=True)
                    ↓
          Monitoring Scheduler (SKIP LOCKED Claim)
                    ↓
        Conditional HTTP Checks (If-None-Match, If-Modified-Since)
                    ↓
┌───────────────────┼────────────────────────┐
│                   │                        │
ETag          Last-Modified            Fingerprints
│                   │                        │
└───────────────────┼────────────────────────┘
                    ↓
                Changed?
              /          \
            NO            YES
            ↓              ↓
       Reschedule    Change Event (PENDING_ANALYSIS)
                           ↓
                      Day 18 Pipeline
```

### Core Principles & Boundaries:
- **Change Detector, Not Full Crawler**: Day 17 detects change cheaply. It does NOT recursively crawl links, does NOT download discovered PDFs, does NOT parse documents, and does NOT execute LLM classification.
- **Source Allowlists Only**: Input is strictly controlled by registered `sources` and `source_urls` where `enabled=true` and `crawl_allowed=true`. Never arbitrarily crawls `.rajasthan.gov.in`.
- **First Check Baseline**: The initial check saves an immutable baseline snapshot and records `BASELINE_CREATED`. It never triggers a false `CHANGED` alert.
- **Staged Conditional HTTP**: Uses `ETag` (`If-None-Match`) and `Last-Modified` (`If-Modified-Since`). A `304 Not Modified` immediately classifies `UNCHANGED` without body parsing or transfer.
- **Deterministic Fingerprints**:
  - `body_fingerprint`: SHA-256 over normalized HTML (collapses whitespace, normalizes CRLF, strips comments).
  - `link_fingerprint`: SHA-256 over canonicalized, sorted, deduplicated absolute URLs (resolves relative links against base URL, strips `#fragments`, preserves query parameters like `?id=101`).
  - Detects same-length content modifications, link-set additions, sitemaps, direct PDFs, and RSS feeds.
- **Adaptive Scheduling & Safety**:
  - Priority intervals: TIER_1 (60m), TIER_2 (360m), TIER_3 (1440m), TIER_4 (10080m).
  - Stable sources back off exponentially (1.5x at $\ge 5$ unchanged checks, 2.25x at $\ge 10$ unchanged checks, up to 7-day cap). Detected changes reset to base interval. Failures apply exponential backoff.
  - Scheduling jitter ($\pm 10\%$) prevents server spikes.
  - Rate limiting: strictly enforces per-host concurrency (`MONITOR_MAX_CONCURRENT_PER_HOST = 1`) and global concurrency (`MONITOR_MAX_CONCURRENT_REQUESTS = 5`).
  - SSRF Protection: rejects loopback (`127.0.0.0/8`), private RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), cloud metadata (`169.254.169.254`), non-HTTP schemes, and unsafe redirects.
  - Response capping: 5MB maximum response size protection (`MONITOR_MAX_HTML_BYTES`).
  - Immutable snapshots stored in `storage/monitoring/<source_url_id>/baseline/` and `changes/<event_id>/`.
- **Day 18 Boundary**: Day 17 queues `SourceChangeEvent` with status `PENDING_ANALYSIS`. Day 18 consumes these events to perform cleaned HTML diffing, link/document discovery, and handoff to Day 4 `DocumentIngestionService`.

### Background Worker Daemon:
```bash
# Continuous polling loop with DB row locking (SKIP LOCKED)
python -m app.monitoring.worker --poll-interval 10 --batch-size 5

# One-pass batch mode (ideal for cron or test runner)
python -m app.monitoring.worker --once
```

### Source Monitoring REST APIs:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/admin/sources/{source_url_id}/check` | Manually trigger immediate monitoring check on approved URL (rejects arbitrary URLs) |
| `GET` | `/api/v1/admin/source-monitoring` | Paginated operational states (filterable by `status`, `priority`, `due_only`) |
| `GET` | `/api/v1/admin/source-monitoring/health-summary` | Aggregated health metrics (healthy, failing, blocked, never checked, pending changes) |
| `GET` | `/api/v1/admin/source-monitoring/{source_url_id}` | Detailed operational state and recent audit runs for a specific URL |
| `GET` | `/api/v1/admin/source-change-events` | Paginated change events queued for Day 18 analysis (filterable by `processing_status`, `change_type`) |

---

## 19. Day 18: Changed-Page Analysis + Structured HTML Diff + Document Discovery + Playwright Fallback

Day 17 answers: *Did an approved government source change?*
Day 18 answers: *What changed, and is any new or modified content relevant to Rajasthan government schemes?*

### Critical Architectural Pipeline:
```text
source_change_event (PENDING_ANALYSIS)
      ↓
Claim Event (FOR UPDATE SKIP LOCKED with stale lease recovery)
      ↓
Load Snapshots (Baseline/Previous + Current from storage/monitoring/)
      ↓
Clean Meaningful HTML (HtmlContentCleaner)
      ↓
[If HTTP Insufficient (< 300 chars or JS shell) → Playwright Fallback Renderer]
      ↓
Structured Block Diff (WebpageDiffService)
  - LINK_ADDED, LINK_REMOVED, LINK_CHANGED
  - TEXT_ADDED, TEXT_REMOVED, TEXT_CHANGED
  - NUMERIC_CHANGE_SIGNAL (₹ amounts, percentages, ages, dates)
  - High Priority Signals
      ↓
Link Discovery (LinkDiscoveryService, Depth = 1)
  - Canonical URL normalization & fragment stripping
  - Resource type classification (PDF, HTML_PAGE, DOCX, etc.)
  - Candidate deduplication & per-event limits
      ↓
Deterministic Relevance Classification (DeterministicRelevanceClassifier)
  - Hindi + English positive scheme terms vs. negative exclusions
  - Negative filters: tenders (निविदा), recruitments (भर्ती), vacancies, auctions, RTI
  - High recall: Ambiguous orders tagged AMBIGUOUS_ORDER → UNCERTAIN
  - Optional local Llama 3.2 3B fallback only for UNCERTAIN candidates
      ↓
Safe Resource Fetcher (DiscoveredResourceFetcher)
  - SSRF defense: loopback, RFC 1918, cloud metadata blocked
  - Redirect safety: all hops validated against SSRF rules
  - Domain allowlist policy (approved official domains only)
  - Chunked streaming download with 50MB hard cap
      ↓
Unified Ingestion Handoff:
  - PDF: Handed to Day 4 DocumentIngestionService(ingestion_method='WEB_MONITOR')
         → Status set to READY_FOR_DUPLICATE_CHECK
         → Day 5 DuplicateDetectionService remains sole authority on duplicates
  - HTML: Cleaned and preserved as WebContentArtifact(READY_FOR_WEB_CONTENT_PROCESSING)
      ↓
Analysis Record Persisted (SourceChangeAnalysis) → Status: ANALYZED
```

### Background Worker Daemon:
```bash
# Run change analysis background worker daemon
python -m app.crawler.worker --interval 5.0

# One-pass batch mode (processes waiting events and exits)
python -m app.crawler.worker --once
```

### Change Analysis & Discovered Resource Admin APIs:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/admin/change-analyses` | Paginated change analysis audit records (filterable by `status`) |
| `GET` | `/api/v1/admin/change-analyses/{analysis_id}` | Detailed diff summary, numeric indicators, and resource counts |
| `GET` | `/api/v1/admin/discovered-resources` | Paginated discovered resources (filterable by `relevance_status`, `resource_type`, `fetch_status`, `change_event_id`, `source_url_id`) |
| `PATCH` | `/api/v1/admin/discovered-resources/{resource_id}/relevance` | Manual admin override for uncertain resource classification |
| `POST` | `/api/v1/admin/discovered-resources/{resource_id}/fetch` | Manually trigger download and ingestion of an approved discovered resource |

---

## 20. Day 19: Scheme Versioning + Amendment / Corrigendum / Supersession Detection

Government scheme rules are temporal and evolving. In Rajasthan administration:
- Guidelines are amended, corrigenda are issued, application deadlines are extended, and notifications supersede earlier orders.
- A new government notification that changes an eligibility threshold (e.g., family income ceiling raised from ₹2,00,000 to ₹3,00,000) must **never overwrite or erase** the historical rule.
- A 1-page amendment document contains only the changed clause; it does **not** restate the 19 unchanged rules. Therefore, an amendment document is never treated as a complete replacement scheme.
- A newer document date or filename (e.g. `revised-scheme.pdf`) does not automatically establish legal supersession. Legal relationships must be supported by government evidence and human confirmation before citizen-facing rules change.

### Versioning Philosophy:
```text
Scheme Identity (Permanent Government Program)
      ↓
Version 1 (Original Guideline, valid_from: 2025-01-01, valid_until: 2026-06-30)
      ↓
Version 2 (Approved Amendment Applied, valid_from: 2026-07-01, valid_until: None)
      ↓
Version 3 (Subsequent Corrigendum / Extension...)
```

### Controlled Relationship Types:
| Relationship Type | Legal Semantics |
| :--- | :--- |
| `AMENDS` | Changes only specified provisions. Old document remains relevant except for modified clauses. |
| `SUPERSEDES` | New document explicitly replaces previous document and rules with legal citation. |
| `CORRIGENDUM_TO` | Corrects typographical or factual error in earlier document (e.g., "₹20,000 shall be read as ₹2,00,000"). |
| `ADDENDUM_TO` | Adds provisions without necessarily replacing original. |
| `CLARIFIES` | Provides official clarification without altering legal conditions. |
| `EXTENDS` | Extends application deadline or policy validity dates (`EXTEND_VALIDITY`). |
| `REFERENCES` | Cites previous notification as background reference without modification. |

### Partial Amendment Patch Architecture:
```text
Base Version (10 conditions)
     +
Approved Change Set (1 condition modified: income ceiling <= ₹3,00,000)
     =
New Version (10 conditions: 9 inherited from Base + 1 amended with source provenance)
```
- **Omission is NOT Removal**: In partial amendments, omitting an existing condition does not mean it was revoked.
- **Full Replacement**: Only when a document explicitly supersedes/replaces the entire guideline are omitted conditions flagged for removal.

### Background Worker Daemon:
```bash
# Run versioning background worker daemon
python -m app.versioning.worker --poll-interval 10

# One-pass batch mode
python -m app.versioning.worker --once
```

### Admin REST APIs:
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/admin/schemes/{scheme_id}/versions` | Version timeline and anomaly detection (`OVERLAP`, `GAP`) |
| `GET` | `/api/v1/admin/scheme-versions/{version_id}` | Complete version details, canonical snapshot, and field provenance |
| `GET` | `/api/v1/admin/scheme-change-sets` | Filterable list of proposed change sets (`status`, `scheme_id`, `critical_only`) |
| `GET` | `/api/v1/admin/scheme-change-sets/{id}` | Side-by-side structured diff with old values, new values, and evidence links |
| `POST` | `/api/v1/admin/scheme-change-sets/{id}/approve` | Approve change set and construct new immutable `SchemeVersion` |
| `POST` | `/api/v1/admin/scheme-change-sets/{id}/reject` | Reject change set with audit reason |
| `POST` | `/api/v1/admin/scheme-versions/{version_id}/activate` | Activate verified version, invalidate Day 16 RAM cache and Day 15 search index |
| `GET` | `/api/v1/schemes/{scheme_id}/active-version` | Query legally active version for citizens by evaluation date |

---

## 21. Day 20: Citizen Text Interface + End-to-End Scheme Discovery Flow

Day 20 delivers the first complete citizen-facing product flow of JanSetu. Citizens can find schemes relevant to their personal circumstances without understanding eligibility rules, JSON, government portals, or vector databases.

```text
                 Citizen
                    ↓
             Text Interface (/citizen)
                    ↓
        Temporary Session (RAM-only backend, sessionStorage browser)
                    ↓
            Known Citizen Profile Facts
                    ↓
             Best Next Question (Information Gain / Entropy Reduction)
                    ↓
              PostgreSQL Candidate Filter (Spatial, Demographic, Hard Invariants)
                    ↓
        Active Human-Verified Version (Day 19: get_active_scheme_version)
                    ↓
         Deterministic AST Eligibility Engine (Day 14: Zero LLM Hallucination)
                    ↓
            Relevant Scheme Results (Visually Separated: Eligible vs Potential)
                    ↓
     Benefits / Documents / Application Guidance / Verified Official Source
```

### Core Architecture & Privacy Guarantees:
1. **Presentation/Input Layer Separation**: The Next.js frontend is strictly a presentation and input layer. Frontend JavaScript NEVER evaluates or reimplements eligibility rules. The deterministic AST engine in FastAPI backend is the sole authority.
2. **Zero LLM Eligibility**: No large language model ever decides citizen eligibility. All decisions derive deterministically from human-verified scheme condition AST trees.
3. **Strict Ephemeral Privacy**: Citizen facts are stored in ephemeral server process RAM and client `sessionStorage`. Zero citizen profile facts are permanently stored in PostgreSQL, logs, or analytics. Starting over immediately purges the session.
4. **Current Active Version Only**: Scheme cards and details strictly resolve through Day 19 `get_active_scheme_version(evaluation_date)`. Superseded, unverified, draft, and future-dated amendments are completely shielded from citizens.
5. **No Similarity Scores**: Semantic search vector similarities (pgvector) remain internal ranking signals and are NEVER displayed as "percentages" (e.g. "87% Match") to citizens.
6. **Bilingual Accessibility**: Instant Hindi/English toggle. Language switching alters only visible labels, questions, and translations—it NEVER alters citizen profile facts or eligibility outcomes.

### Citizen Discovery REST APIs:
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/citizen/sessions` | Create ephemeral discovery session in server RAM with 30-min sliding TTL |
| `GET` | `/api/v1/citizen/sessions/{id}` | Retrieve session summary metadata |
| `GET` | `/api/v1/citizen/sessions/{id}/profile` | Retrieve known facts for profile review and inline correction |
| `PATCH` | `/api/v1/citizen/sessions/{id}/profile` | Update profile facts in RAM, re-triggering deterministic discovery |
| `POST` | `/api/v1/citizen/sessions/{id}/decline-field` | Record citizen decline to answer sensitive field (prevents re-prompting) |
| `POST` | `/api/v1/citizen/sessions/{id}/discover` | Multi-turn discovery returning citizen-safe cards and best next question |
| `DELETE` | `/api/v1/citizen/sessions/{id}` | Explicitly terminate session and purge profile from memory |
| `GET` | `/api/v1/citizen/schemes/{scheme_id}` | Citizen-safe detail DTO: overview, why eligible, benefits, documents, application |
| `GET` | `/api/v1/citizen/districts` | Active 50-district registry of Rajasthan with Hindi & English names |

### How to Run Locally:
```bash
# 1. Start Backend FastAPI Server (runs on http://localhost:8000)
cd backend
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000

# 2. Start Frontend Next.js Server (runs on http://localhost:3000)
cd frontend
npm run dev
```

Citizen flow route: [http://localhost:3000/citizen](http://localhost:3000/citizen)

---

## 22. Day 21: Admin Dashboard + System Operations Control Center

Day 21 delivers an administrative operations control center over JanSetu's 20-day backend subsystems (Sources, Monitoring, Document Processing, Human Review, Schemes, Versions, Conflicts, Search Index, Rule Cache, and Workers).

```text
                               Admin Operator
                                     ↓
                    Admin UI (/admin/*, Next.js App Router)
                                     ↓
                 Operations REST APIs (/api/v1/admin/*)
                                     ↓
 ┌───────────────────┬───────────────────┬───────────────────┐
 │  Pipeline Engine  │ Conflict Center   │  System Health    │
 │  - 10-stage queue │ - Contradictions  │  - PostgreSQL     │
 │  - Stuck detector │ - Validation errs │  - Ollama 3.2 3B  │
 │  - Context retries│ - Version changes │  - pgvector index │
 └───────────────────┼───────────────────┼───────────────────┘
                     │ Audit Logging     │
                     │ - Worker Liveness │
                     │ - Admin Ops Event │
                     └───────────────────┘
```

### Core Operations & Privacy Guarantees:
1. **Strict Privacy Boundary (Zero Citizen Data)**: The admin dashboard monitors document ingestion, validation, extraction, verification, scheme versions, and system components. It NEVER displays citizen profile facts, queries, or temporary session identifiers.
2. **Deterministic Health States**: Explicit observable states (`HEALTHY`, `WARNING`, `CRITICAL`), never arbitrary fake percentages.
3. **Privileged Safe Actions**: Only authorized contextual stage retries (e.g. `OCR_FAILED` -> Retry OCR, `CHUNK_FAILED` -> Retry Chunking). Terminal states like `EXACT_DUPLICATE` are rejected. Every administrative action is logged to `admin_operation_events`.
4. **No Direct Shell Execution**: Operators cannot execute arbitrary shell commands via the web interface. All actions invoke typed, safe backend services.
5. **No Duplicate Business Logic**: The dashboard is an observability and operations layer over existing backend services. It does NOT implement duplicate validation or LLM decisions.

### Admin Operations REST APIs:
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/admin/overview` | Aggregated metric counters (sources, docs, reviews, schemes, conflicts) |
| `GET` | `/api/v1/admin/pipeline` | 10-stage queue breakdown, stuck-item detection (>30m), stage failure rates |
| `POST` | `/api/v1/admin/pipeline/retry-document` | Contextual safe stage retry with audit logging |
| `GET` | `/api/v1/admin/system/status` | Deep health check (DB, Ollama, Search Index, Rule Cache, Storage, Workers) |
| `POST` | `/api/v1/admin/system/refresh-cache` | Safe in-memory verified rule cache reload |
| `POST` | `/api/v1/admin/system/reindex-search` | Safe search index embedding sync for stale verified schemes |
| `POST` | `/api/v1/admin/system/worker-heartbeat` | Background worker liveness check-in |
| `GET` | `/api/v1/admin/activity` | Operational event stream (zero citizen facts) |
| `GET` | `/api/v1/admin/conflicts` | Aggregated conflicts across normalization, validation, and versioning |
| `GET` | `/api/v1/admin/documents` | Paginated documents table with stage, method, duplicate filters |
| `GET` | `/api/v1/admin/schemes` | Paginated schemes table with verified version counters and change sets |
| `GET` | `/api/v1/admin/sources` | Monitored source portals table with failure counters and frequency |
| `POST` | `/api/v1/admin/sources/{id}/check-now` | Safe manual source crawl check trigger |
| `GET` | `/api/v1/admin/search` | Global admin search across schemes, documents, and source portals |

### Admin Frontend Routes:
- `/admin` — System Overview, operational KPI cards, critical blockers, pipeline queue visualizer, recent activity feed.
- `/admin/sources` — Monitored source portals, crawl status, priority, and "Check Now" manual trigger.
- `/admin/documents` — Unified document operations, stage/method filters, upload modal, contextual retries.
- `/admin/processing` — Pipeline stage queue distribution and 30-minute stuck-item detection alerts.
- `/admin/schemes` — Schemes catalog, verified versions, pending change sets.
- `/admin/versions` — Version management timeline, change sets diff, amendment explanation.
- `/admin/conflicts` — Centralized conflict resolution hub across evidence contradictions, validation errors, and version diffs.
- `/admin/system` — Live component health (PostgreSQL, Ollama, pgvector, rule cache, workers, storage counts).

---

## 23. Day 22: Local STT Benchmark — Whisper vs AI4Bharat IndicConformer

Day 22 delivers an offline-first Speech-to-Text (STT) benchmark evaluation suite for JanSetu's vernacular welfare domain in Rajasthan. Before integrating voice models into the production citizen flow or adding voice activity detection (VAD), we benchmark candidate local STT backends directly against domain-specific speech patterns, accents, dialects, and eligibility-critical entities.

```text
Citizen Speech (Future Voice Flow)
      ↓
[STT Provider — Selected via Benchmark]
      ↓
Raw Transcript (Immutable Verbatim Text)
      ↓
Profile Extraction (Conversational Fact Collection)
      ↓
Deterministic Eligibility Engine (Verified Rule Cache)
```

```text
                                Benchmark Dataset (tests/stt_benchmark/)
                                                  │
                                    ┌─────────────┴─────────────┐
                                    │                           │
                            Whisper (CTranslate2)       Indic ASR (PyTorch)
                                    │                           │
                                    └─────────────┬─────────────┘
                                                  ↓
                                          Raw Transcripts
                                                  ↓
                                   ┌──────────────┼──────────────┐
                                   │              │              │
                                  WER            CER       Critical Fields
                                                                │
                                                  ┌─────────────┼─────────────┐
                                                  │             │             │
                                                 Age          Income       District
                                                  │             │             │
                                                  └─────────────┼─────────────┘
                                                                ↓
                                                     Latency & Resource Use
                                                                ↓
                                                          Recommendation
```

### Core Benchmark Principles:
1. **Critical Entity Accuracy > Generic WER**: An ASR model with acceptable Word Error Rate can still be dangerous if it confuses `62` with `26` or `1.5 lakh` with `2.5 lakh`. JanSetu measures literal transcription (`WER`, `CER`) and task-semantic critical fields (`AGE_ACCURACY`, `INCOME_ACCURACY`, `DISTRICT_ACCURACY`, `NEGATION_ACCURACY`, `GOV_TERM_ACCURACY`) separately.
2. **Immutable Raw Transcripts**: Raw transcripts are never overwritten. Metric normalization (Devanagari digit conversion, whitespace, punctuation stripping) is applied strictly on separate comparison copies.
3. **Zero LLM Post-Correction**: Transcripts are benchmarked directly against ground truth without post-hoc LLM fixing.
4. **Startup Isolation**: STT models are heavy and are NEVER loaded on standard FastAPI backend startup. Loading is isolated strictly to explicit CLI runs or provider initialization.
5. **Fault Isolation**: Audio corruption or single-sample inference failures never abort the benchmark run. Failures are captured with diagnostic logs in `critical_failures.json`.

### STT Provider Architecture:
- `SpeechToTextProvider` (`app.stt.interface`): Common abstract contract (`provider_id`, `model_name`, `device`, `load()`, `transcribe()`, `unload()`, `is_available()`).
- `WhisperSTTProvider` (`app.stt.providers.whisper`): Faster-Whisper / CTranslate2 implementation with INT8 CPU inference, segment timestamps, and optional Devanagari prompt conditioning.
- `IndicASRSTTProvider` (`app.stt.providers.indic_asr`): AI4Bharat / Hugging Face CTC acoustic model adapter with greedy decoding and automatic processor / tokenizer fallback.
- `AudioNormalizer` (`app.stt.audio_normalizer`): Converts input audio (WAV, MP3, M4A, FLAC) to canonical baseline: 16 kHz, mono, 16-bit PCM WAV using PyAV and SoundFile.

### Benchmark Dataset Manifest (`tests/stt_benchmark/manifest.json`):
40 standardized audio fixtures across 10 evaluation categories:
- `AGE`: Explicit ages (e.g. 62, 58, 60, 26).
- `INCOME`: Annual and monthly amounts (1.5L, 2.5L, 2.0L, 1.8L, 15k/mo).
- `DISTRICT`: Canonical Rajasthan districts (Udaipur, Dungarpur, Chittorgarh, Banswara, Jhalawar, Pratapgarh, Jaisalmer, Sri Ganganagar, Sawai Madhopur).
- `SHORT_ANSWER`: Single-word utterances ("हाँ", "नहीं", "डूंगरपुर", "बासठ", "डेढ़ लाख").
- `NEGATION`: BPL assertion status ("बीपीएल में नहीं हूँ" vs "बीपीएल में हूँ").
- `CODE_MIXED`: English-Hindi loanwords ("family income दो लाख", "farmer subsidy", "e-Mitra apply").
- `GOVERNMENT_TERMS`: Jan Aadhaar, Pension, Scholarship ("जन आधार", "वृद्धावस्था पेंशन", "छात्रवृत्ति").
- `RAJASTHANI_DIALECT_STYLE`: Marwari/Mewari vernacular phrasing.
- `HINDI_NOISY`: Calibrated ambient noise (fan hum + low-frequency background rumble).
- `LONG_MULTI_ENTITY`: Multi-clause turn containing age, income, and district in a single utterance.

### Benchmark CLI Commands:
```bash
# Run Whisper benchmark on CPU
python -m app.stt.benchmark --provider whisper --model tiny --device cpu

# Run with Devanagari domain prompt conditioning
python -m app.stt.benchmark --provider whisper --model tiny --device cpu --initial-prompt "नमस्ते राजस्थान सरकार योजना"

# Run Indic ASR benchmark
python -m app.stt.benchmark --provider indic_asr --device cpu

# Run all providers
python -m app.stt.benchmark --provider all --device cpu
```

Artifacts are saved to: `storage/benchmarks/stt/<run_id>/`:
- `summary.json`: Run metadata, resource usage, WER/CER, and entity accuracies.
- `samples.jsonl`: Detailed per-sample transcripts and evaluation results.
- `critical_failures.json`: Extracted actionable domain errors.
- `report.md`: Human-readable summary report with category breakdowns.

---

## 25. Day 25: Deterministic Conversation Manager & State Machine

JanSetu features a **fully deterministic conversation brain** driving multi-turn citizen interactions across both typed text and speech-to-text transcripts.

### Core Principle
> **The LLM may understand a sentence, but it never controls the conversation state.**
> **The backend state machine decides what happens next.**
> **Conversation flow is deterministic even when language understanding uses an LLM.**

```text
                    Citizen Input
                         │
              ┌──────────┴──────────┐
              │                     │
            TEXT              STT TRANSCRIPT
              │                     │
              └──────────┬──────────┘
                         ↓
                ConversationManager
                         ↓
               Current Session State
                         ↓
                 CitizenInputRouter
                         ↓
        ┌────────────────┼────────────────┐
        │                │                │
  Profile Answer     Confirmation      User Query
        │                │                │
        ↓                ↓                ↓
 Day 24 Extractor    Pending Update    Verified Data
        │                │                │
        └────────────────┼────────────────┘
                         ↓
                  Session Update
                         ↓
                     Discovery
                         ↓
               NextQuestionSelector
                         ↓
                 State Transition
                         ↓
              Structured Next Action
```

---

### Controlled Conversation States
1. `NEW_SESSION`: Session freshly created, ready for need statement.
2. `WAITING_FOR_NEED`: Awaiting initial citizen need / goal statement.
3. `WAITING_FOR_PROFILE_VALUE`: Awaiting answer for a dynamically selected question field (`expected_field`).
4. `WAITING_FOR_CONFIRMATION`: Pending critical STT numeric or profile correction requires explicit citizen confirmation (`हाँ` / `नहीं`).
5. `PROCESSING_DISCOVERY`: Evaluating eligibility rules and ranking candidate schemes.
6. `SHOWING_RESULTS`: Displaying confirmed eligible schemes and potential schemes needing more info.
7. `WAITING_FOR_RESULT_ACTION`: Viewing scheme details or selecting schemes from results.
8. `HANDLING_CITIZEN_QUERY`: Explaining "Why is this asked?", field glossary definitions, privacy policies, or verified scheme benefits.
9. `NEED_CLARIFICATION`: Handling ambiguous or approximate responses (e.g. "दो लाख से थोड़ा ऊपर").
10. `NO_RESULTS`: No eligible schemes found after discovery.
11. `CANNOT_RESOLVE`: Potential schemes remain, but all discriminative fields are declined or unknown.
12. `COMPLETED`: Conversation explicitly finished by citizen or thank you statement.
13. `ERROR`: Recoverable technical error without corrupting conversation state.

---

### State Machine Transition Table

| Current State | Event | Next State | Action Selected |
| :--- | :--- | :--- | :--- |
| `NEW_SESSION` | `SESSION_STARTED` | `WAITING_FOR_NEED` | `ASK_NEED` |
| `WAITING_FOR_NEED` | `NEED_PROVIDED` | `PROCESSING_DISCOVERY` → `WAITING_FOR_PROFILE_VALUE` | `ASK_PROFILE_FIELD` |
| `WAITING_FOR_NEED` | `ELIGIBLE_RESULTS_FOUND` | `SHOWING_RESULTS` | `SHOW_RESULTS` |
| `WAITING_FOR_PROFILE_VALUE` | `PROFILE_VALUE_EXTRACTED` | `PROCESSING_DISCOVERY` → `WAITING_FOR_PROFILE_VALUE` | `ASK_PROFILE_FIELD` |
| `WAITING_FOR_PROFILE_VALUE` | `VALUE_CONFIRMATION_REQUIRED` | `WAITING_FOR_CONFIRMATION` | `CONFIRM_PROFILE_VALUE` |
| `WAITING_FOR_PROFILE_VALUE` | `CLARIFICATION_REQUIRED` | `NEED_CLARIFICATION` | `CLARIFY_PROFILE_VALUE` |
| `WAITING_FOR_PROFILE_VALUE` | `CITIZEN_QUERY_RECEIVED` | `HANDLING_CITIZEN_QUERY` | `ANSWER_FIELD_HELP` |
| `WAITING_FOR_PROFILE_VALUE` | `PROFILE_VALUE_UNKNOWN` | `PROCESSING_DISCOVERY` → `WAITING_FOR_PROFILE_VALUE` | `ASK_PROFILE_FIELD` (next field) |
| `WAITING_FOR_PROFILE_VALUE` | `PROFILE_VALUE_DECLINED` | `PROCESSING_DISCOVERY` → `WAITING_FOR_PROFILE_VALUE` | `ASK_PROFILE_FIELD` (next field) |
| `WAITING_FOR_CONFIRMATION` | `PROFILE_VALUE_CONFIRMED` | `PROCESSING_DISCOVERY` → `SHOWING_RESULTS` | `SHOW_RESULTS` |
| `WAITING_FOR_CONFIRMATION` | `PROFILE_VALUE_REJECTED` | `WAITING_FOR_PROFILE_VALUE` | `ASK_PROFILE_FIELD` (re-prompt field) |
| `WAITING_FOR_CONFIRMATION` | `CITIZEN_QUERY_RECEIVED` | `HANDLING_CITIZEN_QUERY` | `ANSWER_FIELD_HELP` (preserves pending) |
| `HANDLING_CITIZEN_QUERY` | Any input answering resume field | Restored `resume_state` | `CONFIRM_PROFILE_VALUE` or `ASK_PROFILE_FIELD` |
| `NEED_CLARIFICATION` | `CLARIFICATION_PROVIDED` | `WAITING_FOR_PROFILE_VALUE` / `WAITING_FOR_CONFIRMATION` | Processed clarified value |
| `SHOWING_RESULTS` | `PROFILE_VALUE_CORRECTED` | `WAITING_FOR_CONFIRMATION` | `CONFIRM_PROFILE_VALUE` (correction) |
| `SHOWING_RESULTS` | `SCHEME_SELECTED` | `SHOWING_RESULTS` | Focused scheme view |
| Any State | `START_OVER_REQUESTED` | `WAITING_FOR_NEED` | `ASK_NEED` (clears profile) |
| Any State | `END_CONVERSATION_REQUESTED` | `COMPLETED` | `END_CONVERSATION` |

---

### Yes/No Context Safety
- **During Questioning (`WAITING_FOR_PROFILE_VALUE`, field=`bpl_status`)**:
  - `नहीं` maps to `bpl_status = False`.
  - `हाँ` maps to `bpl_status = True`.
- **During Confirmation (`WAITING_FOR_CONFIRMATION`, field=`age`, proposed=62)**:
  - `नहीं` **rejects** the candidate 62 without setting `age = False`.
  - `हाँ` **confirms** and applies `age = 62`.

---

### Unified Text & STT Input Path
Both typed text and speech-to-text transcripts enter the same `ConversationManager`:
```json
{
  "type": "TEXT" | "STT_TRANSCRIPT" | "STRUCTURED_VALUE" | "ACTION",
  "text": "बासठ",
  "client_turn_id": "turn-12345"
}
```
Speech transcripts automatically trigger critical-value confirmation for numerical/demographic fields according to Day 24 confirmation policies, while typed text accepts direct unambiguous inputs safely.

---

### Session Privacy & Zero Permanent Transcripts
- **Ephemeral RAM Sessions**: All citizen facts and conversation states remain exclusively in server memory (`CitizenSession`) with automatic TTL expiry (45 min).
- **No Database Transcripts**: No citizen conversation turns or raw audio texts are stored in PostgreSQL tables.
- **Privacy-Safe Logs**: Logs record transition events, turn counts, and action keys without printing sensitive attributes (incomes, categories, disabilities).

---

### Citizen Conversation API Endpoints
- `POST /api/v1/citizen/sessions/{session_id}/turn`: Submit a conversation turn (typed text, STT transcript, button value, or action).
- `GET /api/v1/citizen/sessions/{session_id}/conversation`: Retrieve current conversation state for seamless browser refresh restoration.
- `POST /api/v1/citizen/sessions/{session_id}/start-over`: Reset session state and transition back to `WAITING_FOR_NEED`.
- `POST /api/v1/citizen/sessions/{session_id}/end`: Mark conversation as `COMPLETED` and prepare session for immediate expiration.

---

---

## 27. Day 26 — Offline Hindi TTS Benchmark, Voice Selection & Safe Speech Rendering Layer

Day 26 introduces the outbound speech synthesis rendering layer for JanSetu, enabling fully local, offline Hindi voice responses for citizen-facing conversation turns.

```text
                 Citizen Speech Input
                          ↓
                    Day 23 VAD
                          ↓
                    Day 22 STT
                          ↓
             Day 24 Profile Extraction
                          ↓
            Day 25 ConversationManager
                          ↓
                 Structured Response
                          ↓
             ConversationSpeechPolicy
                          ↓
               SpeechTextNormalizer
                          ↓
                TextToSpeechProvider
                          ↓
                    Audio Output
                          ↓
                        Citizen
```

### Core Architectural Principle
> **TTS is strictly a voice rendering layer, not an intelligence layer.**
> Audio generation must never alter backend truth, eligibility, question selection, profile extraction, or conversation state.

### Key Components

1. **TextToSpeechProvider Abstraction (`app/tts/interface.py`)**:
   Unified abstract contract for candidate synthesis engines returning immutable `TTSResult` metadata (duration, synthesis latency, sample rate, audio path).

2. **SpeechTextNormalizer (`app/tts/speech_normalizer.py`)**:
   Deterministic text pre-processor maintaining strict separation between canonical `display_text` (visual cards) and phonetically accurate `speech_text` (audio voice):
   - **Indian Currency**: `₹1,50,000` → `एक लाख पचास हजार रुपये`
   - **Demographics & Ages**: `62 वर्ष` → `बासठ वर्ष`
   - **Percentages**: `40%` → `चालीस प्रतिशत`
   - **Dates**: `31 मार्च 2027` → `इकतीस मार्च दो हजार सत्ताईस`
   - **Boundary Conditions**: `<= ₹2,00,000` → `दो लाख रुपये या उससे कम` (never drops semantic boundaries)
   - **Acronyms & Aliases**: `BPL` → `बी पी एल`, `SSO` → `एस एस ओ`, `e-Mitra` → `ई-मित्र`
   - **Rajasthan Districts**: Controlled Devanagari pronunciation for all 33 districts
   - **URLs & Links**: Screen announcement (`आधिकारिक वेबसाइट का लिंक स्क्रीन पर दिया गया है।`) instead of synthesising raw URLs.

3. **ConversationSpeechPolicy (`app/tts/speech_policy.py`)**:
   Maps Day 25 structured actions (`ASK_PROFILE_FIELD`, `CONFIRM_PROFILE_VALUE`, `SHOW_RESULTS`, `SHOW_DOCUMENTS`, `ERROR`) to clean, speakable Hindi responses without echoing bulky rule tables or private metadata.

4. **Privacy & Ephemeral Audio Storage (`app/tts/temp_storage.py` & `app/tts/cache.py`)**:
   - **Zero Permanent Citizen Audio**: Synthesized responses containing sensitive citizen parameters (income, disability, age) are saved to temporary files with UUIDs and destroyed immediately after serving.
   - **Generic Prompt Cache**: Only non-sensitive, static system questions (`आपकी आयु क्या है?`, `क्या यह सही है?`) are cached via SHA-256 hash keys, accelerating response latency for recurring prompts.

5. **Local Candidates Benchmarked**:
   - **Meta MMS-TTS Hindi (`facebook/mms-tts-hin`)**: Lightweight 145MB VITS architecture running on PyTorch CPU, fast RTF (< 1.0), 16kHz sampling rate.
   - **Piper ONNX Hindi (`hi_IN-pratham-medium` & `hi_IN-priyamvada-medium`)**: 63.5MB ONNX runtime models, 22.05kHz sampling rate, calm neutral tone.
   - **Mock Provider**: Zero-dependency synthetic tone generator for headless CI and instant fallback tests.

### Offline CLI Commands
```powershell
cd backend
.\.venv\Scripts\Activate.ps1

# Synthesize a single sentence:
python -m app.tts.synthesize --text "आपने अपनी आयु 62 वर्ष बताई है। क्या यह सही है?" --output test.wav

# Run the automated benchmark across all installed engines:
python -m app.tts.benchmark --all
```

```

---

## 28. Day 27 — Complete Offline Voice Loop + Half-Duplex State Control

Day 27 connects the complete vernacular offline voice loop for JanSetu, integrating Day 23 Audio/VAD, Day 22 Selected STT (faster-whisper-tiny INT8 CPU), Day 24 Profile Extraction, Day 25 Deterministic ConversationManager, and Day 26 Selected TTS into a unified, safe, half-duplex voice interface.

### Architectural Invariant
Voice is strictly an input/output transport layer to the deterministic `ConversationManager`. STT converts speech to text, deterministic Python rules evaluate eligibility and profile updates, and TTS only speaks verified system responses. No separate LLM voice brain is created.

```text
Citizen Speaks
      ↓
LISTENING
      ↓ (Push-to-talk stop or silence heuristic)
PROCESSING_AUDIO
      ↓ (Silero VAD)
TRANSCRIBING
      ↓ (Whisper tiny INT8 CPU)
PROCESSING_TURN
      ↓ (Day 25 ConversationManager)
SYNTHESIZING
      ↓ (Day 26 Hindi TTS)
SPEAKING (Microphone OFF to prevent acoustic feedback)
      ↓ (Playback completes)
READY
```

### Key Technical Pillars
1. **Half-Duplex Safety**: While JanSetu is `SPEAKING`, the microphone is strictly disabled. Direct transitions from `SPEAKING` to `LISTENING` without playback completion or explicit cancellation are forbidden, eliminating acoustic self-capture on laptop speakers and phones.
2. **Orthogonal State Machines**:
   - **Voice Transport State**: `IDLE`, `READY`, `LISTENING`, `PROCESSING_AUDIO`, `TRANSCRIBING`, `PROCESSING_TURN`, `SYNTHESIZING`, `SPEAKING`, `RECOVERABLE_ERROR`, `STOPPED`.
   - **Semantic Conversation State**: `WAITING_FOR_NEED`, `WAITING_FOR_PROFILE_VALUE`, `WAITING_FOR_CONFIRMATION`, `SHOWING_RESULTS`, `SHOWING_DOCUMENTS`.
3. **Turn Idempotency & Session Concurrency**:
   - Every voice turn includes a unique `voice_turn_id` and expected `conversation_version`.
   - In-memory per-session asyncio concurrency locks reject simultaneous voice turns with HTTP 409 (`VOICE_TURN_ALREADY_ACTIVE`).
   - Duplicate turn submissions return cached results without re-executing conversation rules.
4. **Privacy & Ephemeral Audio**:
   - Citizen uploaded voice recordings are processed in-memory / temporary files and deleted immediately after turn transcription.
   - Synthesized response audio files have a strict 5-minute TTL (`VOICE_AUDIO_RESPONSE_TTL_SECONDS=300`) with automatic expiry cleanup.
   - Raw audio and full transcripts are never permanently stored.
5. **Text/Voice Hybrid Continuity**:
   - Citizens can seamlessly switch between Text and Voice modes within the same session without losing verified profile facts or conversation progress.

### Voice API Endpoints
- `POST /api/v1/citizen/sessions/{session_id}/voice-turn` — Submit recorded audio turn (multipart/form-data)
- `GET /api/v1/citizen/sessions/{session_id}/voice/responses/{response_id}/audio` — Stream synthesized response audio
- `POST /api/v1/citizen/sessions/{session_id}/voice/replay` — Re-synthesize and replay the last spoken turn without advancing state
- `GET /api/v1/citizen/sessions/{session_id}/voice/status` — Inspect voice transport state and model availability

---

## 30. Day 28 — Gold-Standard Evaluation Dataset & Human-Verified Test Truth

Day 28 builds the independent, versioned, evidence-backed evaluation ground truth for JanSetu across Extraction, Eligibility, Search, and Voice/Conversation, establishing the benchmark truth for Days 29 through 32.

### Architectural Evaluation Pipeline:
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

### Key Invariants:
1. **Zero AI Self-Annotation**: Expected facts are extracted and verified purely from official circulars, verified scheme records, and human-curated audio fixtures.
2. **Strict Data-Leakage Protection**: Evaluator loader (`GoldBenchmarkLoader.get_runtime_inputs(...)`) returns pure input fixtures with target labels stripped to prevent test-set contamination.
3. **Tri-State Semantics**: Eligibility gold cases strictly evaluate to `ELIGIBLE`, `NOT_ELIGIBLE`, or `MORE_INFORMATION_REQUIRED`, testing boundary values ($\pm 1$), short-circuiting, and temporal version dates.
4. **Privacy & Zero Citizen PII**: All eligibility citizen profiles are synthetic. An automated PII validator checks for real 12-digit Aadhaar patterns, 10-digit mobile numbers, and email addresses.
5. **Frozen Manifest & Staleness Detection**: Manifest hash `14467fd3edbe21f63a3a16b104089f845e194ce116ea0a2e563a85a7c686b46e` detects any modification to underlying source chunks, scheme JSONs, or audio recordings.

### Dataset Overview:
- **Total Cases**: 280
- **Extraction (60 cases)**: Clean digital PDFs, Devanagari Hindi circulars, Markdown tables, PaddleOCR scanned crops, mandatory documents, negative chunks, prompt injection security test fixture.
- **Eligibility (120 cases)**: Exact age/income boundaries, Boolean `unknown` vs `false`, tri-state short circuiting, personal vs family income, domicile vs residence, temporal version amendments.
- **Search (50 cases)**: Hindi, English, Hinglish queries, profile-assisted search, negative ranking filter tests, zero-result queries.
- **Voice (42 cases)**: 40 Rajasthan vernacular audio recordings + 2 VAD synthetic silence/noise fixtures, context-dependent semantic mapping ("हाँ" in BPL context vs confirmation card context).
- **Conversation (8 cases)**: Scripted multi-turn dialogue state transitions, action selections, and stable message keys.

### Gold Dataset CLI Commands:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1

# Validate entire gold dataset against schemas, evidence, audio hashes, and PII checks
python -m app.gold.validate --version v1

# Output task and split distributions, coverage tags, and review status
python -m app.gold.summary --version v1

# Freeze manifest and compute canonical SHA-256
python -m app.gold.freeze --version v1.0
```

---

## 31. Document Extraction Evaluation Engine (Day 29)

Day 29 builds the evaluation and failure analysis system connecting the Day 28 human-verified frozen gold dataset (`benchmarks/gold/v1/extraction/`) to the real production pipeline (`SchemeExtractionService`, `CanonicalSchemeNormalizationService`, `EvidenceValidator`).

```text
                  DAY 28 FROZEN GOLD DATASET
                              ↓
                    Gold Extraction Cases
                              ↓
              Runtime Stripping (Zero Leakage)
                              ↓
                     Production Pipeline
                  (MinerU / OCR → Chunking
                    → LLM → Normalization)
                              ↓
                       System Output
                              ↓
                     Exact vs Gold Match
       ┌──────────────────────┼──────────────────────┐
       │                      │                      │
   Field / Value            Rules                 Evidence
(Precision, Recall,    (Operators, Trees,     (Grounding Rate,
  Normalized Match)    Commutative Logic)      Hallucinations)
       │                      │                      │
       └──────────────────────┼──────────────────────┘
                              ↓
                  Pipeline-Stage Attribution
              (OCR vs Chunk vs LLM vs Normalizer)
                              ↓
                     Severity Classification
                 (CRITICAL, HIGH, MEDIUM, LOW)
                              ↓
                    Storage Run Artifacts
                 (storage/benchmarks/extraction/)
                              ↓
                       Final QA Report
```

### Key Capabilities:
1. **Multi-Dimensional Metrics**: Separately measures field detection (Precision/Recall/F1), exact value accuracy, normalized semantic value equivalence (e.g. ₹2 lakh $\equiv$ 200000 INR), operator boundary accuracy (LTE vs LT), rule tree equivalence under commutative child ordering ($A \land B \equiv B \land A$), evidence reference validity, semantic support, and hallucination rates.
2. **Safety-Critical Severity**: Categorizes errors into `CRITICAL` (wrong age/income threshold, AND $\leftrightarrow$ OR swap, lost NOT, missed/invented exclusion, wrong benefit amount), `HIGH` (wrong document, wrong channel, wrong deadline), `MEDIUM` (missing qualifier, contact info), and `LOW`.
3. **Pipeline-Stage Attribution**: Pinpoints the earliest failing stage in the pipeline:
   - `PARSING_OCR`: Digit corruption, table structure destruction.
   - `CHUNKING`: Clause boundary truncations, context loss.
   - `LLM_EXTRACTION`: Omission, hallucination, wrong operator, wrong value.
   - `NORMALIZATION`: Number parser error, unit conversion mistake.
   - `EVIDENCE_VERIFICATION`: Ungrounded references.
4. **Data-Leakage Protection**: Evaluator runs only against runtime inputs (`GoldBenchmarkLoader.get_runtime_inputs(...)`) with all expected ground-truth answers stripped.
5. **Immutable Benchmark Artifacts**: Every run generates a standalone directory under `storage/benchmarks/extraction/<run_id>/` containing `run_manifest.json`, `summary.json`, `cases.jsonl`, `failures.jsonl`, `critical_failures.json`, `category_metrics.json`, `report.md`, and operator confusion matrices.

### Extraction Benchmark CLI Commands:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1

# Run benchmark on DEV split (15 cases)
python -m app.evaluation.extraction --gold-version v1 --split DEV

# Run benchmark on VALIDATION split (19 cases)
python -m app.evaluation.extraction --gold-version v1 --split VALIDATION

# Run official benchmark on frozen TEST split (26 cases)
python -m app.evaluation.extraction --gold-version v1 --split TEST

# Single case deep-dive diagnostic inspection
python -m app.evaluation.extraction --case EXT-RJ-001 --verbose

# Run with tag filters (e.g. OCR or TABLE cases)
python -m app.evaluation.extraction --split TEST --tag OCR
python -m app.evaluation.extraction --split TEST --tag TABLE
```

---

## 32. Testing & Regression Verification

Run Day 29 extraction evaluation tests:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest tests/test_extraction_evaluation.py -v
```

Run full regression test suite across Days 1 through 29:
```powershell
python -m pytest -q
```

Verify frontend TypeScript types and production build:
```powershell
cd frontend
npx tsc --noEmit
npm run build
```




