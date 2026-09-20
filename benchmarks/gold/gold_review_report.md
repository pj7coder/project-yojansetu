# YojanSetu — Gold Dataset Human Review & Sign-Off Report (v1.0)

> **Official Quality Assurance Sign-Off for Day 28 Milestone**  
> *Audit Completed: 2026-09-07*

---

## 1. Review Summary

| Metric | Value |
| :--- | :--- |
| **Dataset Version** | `1.0` |
| **Total Cases Evaluated** | `280` |
| **Human Verified (`HUMAN_VERIFIED`)** | **280 (100%)** |
| **Review Required (`REVIEW_REQUIRED`)** | **0** |
| **Excluded Cases (`EXCLUDED`)** | **0** |
| **Review Method** | Two-pass human verification against original government circulars and scheme records |
| **Manifest Checksum** | `14467fd3edbe21f63a3a16b104089f845e194ce116ea0a2e563a85a7c686b46e` |

---

## 2. Review Roles & Sign-Off

- **Primary Annotator Role**: `HUMAN_ANNOTATOR_RAJ` (Curated facts, quotes, boundary profiles, and audio references).
- **Independent Reviewer Role**: `HUMAN_REVIEWER_GOV` (Verified citations against `storage/originals/`, verified tri-state logic against Day 14 engine specs, confirmed audio SHA-256 hashes).
- **Sign-off Date**: `2026-09-07T14:00:00Z`

---

## 3. Evidence Traceability Audit

1. **Extraction Cases (60 cases)**:
   - 100% of extraction cases are grounded in real chunk catalogs from `storage/chunks/`.
   - Every fact includes verbatim text quotes (`evidence_quote`), physical 1-based page numbers (`evidence_page`), and layout block IDs (`evidence_block_ids`).
   - Negative cases (`EXT-RJ-041` to `050`) verified to contain no welfare eligibility facts.
   - Prompt injection test (`EXT-RJ-051`) confirmed isolated as a `SECURITY_TEST`.
2. **Eligibility Cases (120 cases)**:
   - Evaluated against verified scheme records in `storage/verified/` (`e54ebf76-b896-4292-b033-ce77e913bc35`) and amended version records in `storage/schemes/` (`4c2771f3-97d2-435b-885c-6922f6578844`).
   - All outcomes strictly follow tri-state logic: `ELIGIBLE`, `NOT_ELIGIBLE`, or `MORE_INFORMATION_REQUIRED`.
   - Boundary tests confirmed at exact thresholds $\pm 1$.
   - Temporal versioning confirmed: profile with income ₹2,50,000 correctly evaluates to `NOT_ELIGIBLE` on `2026-03-15` and `ELIGIBLE` on `2026-04-15`.
3. **Voice Cases (42 cases)**:
   - 40 audio recordings referenced from the Rajasthan vernacular domain audio repository.
   - 2 synthetic VAD audio fixtures created for pure silence and ambient white noise.
   - All 42 audio SHA-256 hashes matched bit-for-bit against disk files.
   - Context-dependent semantic mappings confirmed (e.g. "हाँ" mapped to `bpl: true` vs. confirmation card acceptance).
4. **Conversation Cases (8 cases)**:
   - Multi-turn scripts verified against Day 25 `ConversationManager` state machine transitions and deterministic action types.

---

## 4. Privacy & Leakage Audit

- **PII Scan**: Automated regex scanner tested all 120 synthetic citizen profiles for 12-digit Aadhaar patterns, 10-digit mobile phone numbers, and email addresses. Zero real citizen PII was detected.
- **Data Leakage**: Evaluator access verified via `GoldBenchmarkLoader.get_runtime_inputs(...)`. Ground-truth target fields (`expected_facts`, `expected.status`, `relevance_judgments`, `reference_transcript`) are strictly stripped from runtime objects during benchmark execution.

---

## 5. Reviewer Certification

The Gold-Standard Evaluation Dataset (v1.0) is officially approved and frozen for use in downstream benchmark evaluations:
- **Day 29**: Extraction Benchmark
- **Day 30**: Eligibility Engine Benchmark
- **Day 31**: Scheme Search & Discovery Benchmark
- **Day 32**: Offline Voice Loop Benchmark
