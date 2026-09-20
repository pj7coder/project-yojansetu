# JanSetu — Gold Dataset Annotation & Human Verification Guidelines (v1.0)

> **Mandatory Standard Operating Procedure for Gold-Standard Reference Truth**  
> *Establishing independent, evidence-backed evaluation benchmarks for Days 29–32.*

---

## 1. Core Principles

1. **Evidence-First Invariant**:
   Every gold-standard value must answer: **"Where exactly did this expected answer come from in the official government evidence?"**
   Expected values must NEVER come from model outputs, memory, Google snippets, assumptions, or developer intuition.
2. **Zero AI Self-Annotation**:
   Generative LLMs (Llama, GPT, etc.) must NEVER be used to auto-generate ground truth. Human annotators inspect official circulars; human reviewers verify every case.
3. **Not Training Data**:
   The gold dataset (and especially the `TEST` split) is reserved strictly for unbiased QA evaluation. It must never be used in runtime prompts or training loops.
4. **Honest Ambiguity**:
   If an official government circular is contradictory, ambiguous, or lacks critical definitions, **do not force an artificial answer**. Record `AMBIGUOUS_SOURCE` or `SOURCE_CONFLICT`. A gold evaluation dataset must reflect genuine policy ambiguity.
5. **Strict Citizen Privacy**:
   No real citizen personally identifiable information (PII) is permitted in the dataset. All eligibility profiles must be synthetic. Real Aadhaar numbers, phone numbers, and residential street addresses are strictly forbidden.

---

## 2. Evidence Standards

### What Counts as Evidence?
- **Official Government Circulars**: Bit-for-bit immutable PDFs in `storage/originals/<doc_id>/original.pdf`.
- **Structured Parsed Text & Layout**: Verified text blocks in `storage/parsed/<doc_id>/document.json`.
- **OCR Outputs**: High-resolution OCR page crops in `storage/ocr/<doc_id>/merged_document.json`.
- **Human-Verified Scheme Records**: Signed-off canonical schemes in `storage/verified/<scheme_draft_id>/verified_scheme.json`.

### Verbatim Citation Requirement
Every extracted fact in `ExtractionGoldCase` must include:
- `evidence_quote`: The exact verbatim sentence or table cell from the PDF.
- `evidence_page`: The physical 1-based PDF page number.
- `evidence_block_ids`: The layout block IDs linking directly to `document.json`.

---

## 3. Handling Source Ambiguity & Conflicts

### A. Ambiguous Source (`AMBIGUOUS_SOURCE`)
- **Definition**: The government text is vague or open to multiple conflicting legal interpretations (e.g., *"वरिष्ठ नागरिकों को सहायता दी जाएगी"* without defining a minimum age).
- **Protocol**:
  1. Do NOT guess or default to age 60.
  2. Flag the case with `ambiguity_flag = "AMBIGUOUS_SOURCE"`.
  3. Set `difficulty = "HARD"`.
  4. Exclude the case from strict numerical accuracy metrics; include it in ambiguous-handling diagnostics.

### B. Source Conflict (`SOURCE_CONFLICT`)
- **Definition**: Two official government documents (or different sections of the same circular) declare conflicting rules (e.g., Section 2 says *income $\le$ ₹2,00,000*, but the application form in Annexure A says *income $\le$ ₹2,50,000*).
- **Protocol**:
  1. Record both values with their respective document, page, and block citations.
  2. Flag the case as `SOURCE_CONFLICT`.
  3. Do NOT resolve the conflict arbitrarily. This case tests whether the system catches discrepancies rather than hallucinating consistency.

---

## 4. Task-Specific Annotation Rules

### Task A: Scheme Extraction (`extraction/`)
1. **Canonical Schema Normalization**:
   - Numbers must be parsed into integer/float with explicit units (`years`, `INR`).
   - Dates must be ISO-8601 (`YYYY-MM-DD`).
   - Periods must be standardized (`MONTHLY`, `ANNUAL`, `ONE_TIME`).
2. **Distinguish Operators**:
   - "At least 60 years" $\rightarrow$ `operator: "GTE"`, `value: 60`.
   - "Above 60 years" / "More than 60 years" $\rightarrow$ `operator: "GT"`, `value: 60`.
   - "Up to ₹2,00,000" $\rightarrow$ `operator: "LTE"`, `value: 200000`.
3. **Tables & Multi-Tier Benefits**:
   - When benefits depend on age brackets (e.g. 58–75 $\rightarrow$ ₹1,150; 75+ $\rightarrow$ ₹1,500), each tier must be recorded with its specific age condition. Do not flatten tables into a single average.
4. **Negative Cases**:
   - Chunks containing only generic boilerplate, administrative headers, or non-scheme procedural text must have `expected_facts: []` and `is_negative: true` to measure LLM hallucination.
5. **Security Fixtures**:
   - Chunks containing adversarial prompt injections (e.g. *"Ignore previous instructions..."*) must have `is_security_test: true`. The expected extraction must completely ignore the malicious injection.

---

### Task B: Deterministic Eligibility (`eligibility/`)
1. **Strict Tri-State Semantics**:
   Every case must resolve to exactly one of:
   - `ELIGIBLE`: All required criteria are definitively satisfied; no exclusions triggered.
   - `NOT_ELIGIBLE`: At least one required criterion is definitively violated, OR an exclusion is definitively triggered.
   - `MORE_INFORMATION_REQUIRED`: Known facts are satisfied or pending, but crucial required fields remain unknown.
2. **Tri-State Short-Circuit Logic**:
   - `FALSE AND UNKNOWN` $\rightarrow$ `NOT_ELIGIBLE` (Immediate disqualification, no extra questions needed).
   - `TRUE OR UNKNOWN` $\rightarrow$ `ELIGIBLE` (Alternative condition satisfied).
   - `TRUE AND UNKNOWN` $\rightarrow$ `MORE_INFORMATION_REQUIRED` (Must ask for the missing field).
3. **Boolean Unknown vs. False**:
   - `bpl = false` is a known negative value (the citizen confirmed they do not hold BPL status).
   - `bpl = null / unknown` means the citizen has not been asked.
   - Gold cases must explicitly test this difference.
4. **Boundary Testing**:
   For rule `age >= 60`:
   - `age: 60` $\rightarrow$ `ELIGIBLE` (exact boundary).
   - `age: 59` $\rightarrow$ `NOT_ELIGIBLE` (one below).
   - `age: 61` $\rightarrow$ `ELIGIBLE` (one above).
5. **Temporal Versioning & Evaluation Date**:
   - Every eligibility case must specify `evaluation_date`.
   - If a scheme amendment raised the income ceiling from ₹2,00,000 to ₹3,00,000 effective `2026-04-01`, a profile with income ₹2,50,000 must evaluate to:
     - `NOT_ELIGIBLE` when evaluated on `2026-03-15`.
     - `ELIGIBLE` when evaluated on `2026-04-15`.

---

### Task C: Scheme Discovery & Search (`search/`)
1. **Relevance Judgments**:
   - `HIGH`: Direct, unambiguous match for the stated need (e.g. "old age pension" for a 65-year-old).
   - `RELEVANT`: Related or tangential benefit (e.g. healthcare scheme providing subsidized medicine for seniors).
   - `NOT_RELEVANT`: Unrelated domain (e.g. farmer tractor subsidy for a student scholarship query).
2. **Acceptable Top-Set**:
   - Ranking order among highly relevant schemes can be subjective. Annotators specify `acceptable_top_set` and `must_appear_top_5`.
3. **Ineligible High-Similarity Negative Test**:
   - When a query strongly matches a scheme title but profile filters definitively disqualify the citizen (e.g., a 25-year-old searching *"बुजुर्ग पेंशन"*), the scheme must NOT appear in the confirmed eligible recommendations.
4. **No-Result Queries**:
   - Queries with zero matching schemes must yield empty results (`expected_empty: true`) rather than hallucinating irrelevant schemes.

---

### Task D: Voice & Speech Understanding (`voice/`)
1. **Transcription Reference**:
   - Human-verified Devanagari text (`reference_transcript`) reflecting what was actually spoken, including colloquialisms and dialect variations.
2. **Context-Dependent Semantic Mapping**:
   The exact same utterance has different structured meanings depending on conversational context:
   - Utterance: *"हाँ"* with context `expected_field: "bpl"` $\rightarrow$ `bpl: true`.
   - Utterance: *"हाँ"* with context `conversation_state: "WAITING_FOR_CONFIRMATION"` $\rightarrow$ `is_confirmation: true`.
3. **Short Answers & Edge Cases**:
   - Short answers ("हाँ", "नहीं", "बासठ", "डूंगरपुर", "डेढ़ लाख") must be mapped to normalized numerical/categorical values.
   - Negation phrases ("मैं बीपीएल में नहीं हूँ") must map to `bpl: false`.
4. **Audio Integrity**:
   - Every audio case must have an immutable `audio_sha256` matching the recorded WAV file.

---

## 5. Review & Sign-Off Process

```text
Draft Annotation (Annotator)
         ↓
Independent Review (Reviewer)
         ↓
┌───────────────────────────────────────┐
│ Disagreement or Evidence Gap?         │
│  ├─ Yes: Flag REVIEW_REQUIRED / Reject│
│  └─ No: Sign off HUMAN_VERIFIED       │
└───────────────────────────────────────┘
         ↓
Freeze in Manifest (dataset_sha256)
```

1. **Two-Party Review**:
   Critical test cases must be reviewed by a second team member before being marked `HUMAN_VERIFIED`.
2. **Immutability**:
   Once Gold v1.0 is frozen (`python -m app.gold.freeze`), case contents cannot be silently modified. Any future corrections require bumping the dataset version to v1.1 with an entry in `CHANGELOG.md`.
