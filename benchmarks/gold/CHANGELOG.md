# Gold Dataset Changelog

All notable changes to the YojanSetu Gold Benchmark Evaluation Dataset will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-09-07

### Initial Release (Day 28)
- **Manifest Hash (SHA-256)**: `14467fd3edbe21f63a3a16b104089f845e194ce116ea0a2e563a85a7c686b46e`
- **Total Cases**: 280 cases across 5 tasks.

#### Task Subsets:
- **Extraction (60 cases)**:
  - Clean digital PDF text and Devanagari Hindi circulars.
  - Markdown table extraction preserving tiered age brackets (Age 58–75 vs. 75+).
  - Scanned page OCR extractions via PaddleOCR evidence.
  - Mandatory document criteria (Jan Aadhaar Card, Bank Passbook, Age Proof).
  - Negative cases (pure administrative circulars with zero scheme facts, expected `[]`).
  - Isolated prompt injection security test fixture (`EXT-RJ-051`).
- **Eligibility (120 cases)**:
  - Strict tri-state evaluation (`ELIGIBLE`, `NOT_ELIGIBLE`, `MORE_INFORMATION_REQUIRED`).
  - Boundary value tests for minimum age (59, 60, 61) and maximum income (199k, 200k, 201k).
  - Short-circuiting logic (`FALSE AND UNKNOWN -> FALSE`, `TRUE OR UNKNOWN -> TRUE`).
  - Boolean distinction (`bpl = false` vs. `bpl = unknown`).
  - Personal income vs. family income discrepancy tests.
  - Domicile vs. residency tests.
  - Exclusion condition triggers (government employee, income tax payer).
  - Temporal version cases: same profile evaluated before amendment date (`2026-03-15`) vs. after amendment date (`2026-04-15`) against Scheme 4c2771f3.
- **Search (50 cases)**:
  - Queries in Hindi, English, and Hinglish across keyword, natural sentence, problem-driven, and beneficiary-driven styles.
  - Profile-assisted queries with SQL filtering and unknown field high recall tests.
  - Ranking-negative cases: query matches scheme description, but citizen profile is definitively ineligible (scheme forbidden from top-K).
  - Zero-result / no-query tests (measuring hallucination resistance).
- **Voice (42 cases)**:
  - Ground truth for 40 Rajasthan vernacular audio recordings (`tests/stt_benchmark/audio/`) covering clean Hindi, accented speech, Marwari/Mewari phrasing, short answers ("हाँ", "नहीं", "बासठ", "डूंगरपुर", "डेढ़ लाख"), negation, and noisy audio.
  - 2 synthetic VAD audio fixtures (pure silence and ambient white noise).
  - Context-dependent semantic interpretation ("हाँ" in BPL context vs. "हाँ" in confirmation card context).
  - VAD speech boundary truth.
- **Conversation (8 cases)**:
  - Scripted multi-turn dialogue test cases covering standard pension flow, immediate disqualification, in-conversation correction, "why is this asked" interruption, farmer assistance, ambiguous input clarification, English dialogue, and text/voice hybrid continuity.

#### Governance & Tooling:
- Added `backend/app/gold/` Python subsystem with Pydantic schemas, validation engine, and data-leakage protected benchmark loader (`GoldBenchmarkLoader`).
- Added CLI tools: `python -m app.gold.validate`, `python -m app.gold.summary`, and `python -m app.gold.freeze`.
- Published `annotation/GUIDELINES.md` detailing verbatim quote standards, `AMBIGUOUS_SOURCE` and `SOURCE_CONFLICT` handling, and zero-PII synthetic data enforcement.
