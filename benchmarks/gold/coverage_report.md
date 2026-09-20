# YojanSetu — Gold Dataset Coverage Report (v1.0)

> **Comprehensive Coverage Audit & Explicit Limitation Disclosure**  
> *Generated on 2026-09-07 as part of Day 28 Milestone.*

---

## 1. Executive Summary

- **Total Cases**: 280
- **Tasks Covered**: 5 (Extraction, Eligibility, Search, Voice, Conversation)
- **Manifest Checksum**: `14467fd3edbe21f63a3a16b104089f845e194ce116ea0a2e563a85a7c686b46e`
- **Review Status**: 100% `HUMAN_VERIFIED`

| Dimension | Scope in Gold v1.0 | Status |
| :--- | :--- | :---: |
| **Government Evidence Provenance** | All extraction and eligibility cases reference real circulars or verified scheme records | ✅ Complete |
| **Tri-State Eligibility Logic** | Comprehensive testing of `ELIGIBLE`, `NOT_ELIGIBLE`, and `MORE_INFORMATION_REQUIRED` | ✅ Complete |
| **Boundary Value Analysis** | Exact minimums/maximums, +1 unit, and -1 unit tested for age and income | ✅ Complete |
| **Temporal Versioning** | Same profile tested against pre- and post-effective amendment dates | ✅ Complete |
| **Data Leakage Protection** | Evaluator loader strips expected answers for runtime inference | ✅ Complete |
| **Citizen Privacy** | Zero real citizen PII; automated regex scanner validates all profiles | ✅ Complete |

---

## 2. Task & Split Distribution Matrix

| Task | DEV | VALIDATION | TEST | TOTAL | % of Dataset |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Extraction** | 15 | 19 | 26 | **60** | 21.4% |
| **Eligibility** | 30 | 30 | 60 | **120** | 42.9% |
| **Search** | 15 | 15 | 20 | **50** | 17.9% |
| **Voice** | 10 | 12 | 20 | **42** | 15.0% |
| **Conversation** | 2 | 2 | 4 | **8** | 2.8% |
| **TOTAL** | **72** | **78** | **130** | **280** | **100.0%** |

---

## 3. Extraction Task Coverage Details

| Category | Cases | Evidence / Notes |
| :--- | :---: | :--- |
| **Clean Digital PDF Text** | 10 | Core senior citizen pension circular (`DOC-72FF2711-CHUNK-0002`) |
| **Markdown Tables** | 10 | Tiered pension benefit table (`DOC-72FF2711-CHUNK-0003`) |
| **Scanned OCR Pages** | 10 | PaddleOCR extracted table crops (`DOC-BCF2C569-CHUNK-0003`) |
| **Mandatory Documents** | 10 | Jan Aadhaar, Bank Passbook, Age Proof (`DOC-72FF2711-CHUNK-0004`) |
| **Negative / No-Fact Chunks** | 10 | Procedural/sanitation circulars (`DOC-18F745FB-CHUNK-0001`, expected `[]`) |
| **Devanagari Hindi Circulars** | 9 | Age, income ceilings, domicile, e-Mitra channel in Hindi text |
| **Prompt Injection Security** | 1 | Adversarial injection fixture (`EXT-RJ-051`, `SECURITY_TEST`) |

---

## 4. Eligibility Task Coverage Details

| Logic Pattern | Count | Example Case | Outcome |
| :--- | :---: | :--- | :---: |
| **Age Exact Minimum** | 1 | `ELG-RJ-001` (Age 60, Income 150k) | `ELIGIBLE` |
| **Age One Below Minimum** | 1 | `ELG-RJ-002` (Age 59, Income 150k) | `NOT_ELIGIBLE` |
| **Age One Above Minimum** | 1 | `ELG-RJ-003` (Age 61, Income 150k) | `ELIGIBLE` |
| **Income Exact Maximum** | 1 | `ELG-RJ-004` (Age 65, Income 200k) | `ELIGIBLE` |
| **Income One Above Maximum**| 1 | `ELG-RJ-005` (Age 65, Income 200,001) | `NOT_ELIGIBLE` |
| **Income One Below Maximum**| 1 | `ELG-RJ-006` (Age 65, Income 199,999) | `ELIGIBLE` |
| **Short-Circuit: False & Unknown** | 1 | `ELG-RJ-007` (Age 52, Income unknown) | `NOT_ELIGIBLE` |
| **Missing Info: True & Unknown** | 1 | `ELG-RJ-008` (Age 67, Income unknown) | `MORE_INFORMATION_REQUIRED` |
| **Boolean: BPL False vs Unknown** | 2 | `ELG-RJ-009` (bpl=false), `ELG-RJ-010` (bpl=unknown) | `ELIGIBLE` |
| **Exclusion: Govt Employee** | 1 | `ELG-RJ-011` (is_government_employee=true) | `NOT_ELIGIBLE` |
| **Exclusion: Income Tax Payer** | 1 | `ELG-RJ-012` (is_income_tax_payer=true) | `NOT_ELIGIBLE` |
| **Income Type: Personal vs Family**| 1 | `ELG-RJ-013` (Personal 50k, Family 280k) | `NOT_ELIGIBLE` |
| **Domicile vs Residence** | 1 | `ELG-RJ-014` (Resident in RJ, Domicile Haryana) | `NOT_ELIGIBLE` |
| **Temporal: Pre-Amendment Date** | 1 | `ELG-RJ-015` (Date: 2026-03-15, Income 250k) | `NOT_ELIGIBLE` |
| **Temporal: Post-Amendment Date** | 1 | `ELG-RJ-016` (Date: 2026-04-15, Income 250k) | `ELIGIBLE` |
| **Standard Multi-District & Occupation Profiles** | 104 | `ELG-RJ-017` to `ELG-RJ-120` | Varied |

---

## 5. Voice Acoustic & Linguistic Coverage

| Category | Cases | Audio Files / Examples |
| :--- | :---: | :--- |
| **Short Answers** | 5 | "हाँ" (`hi_short_001.wav`), "नहीं" (`hi_short_002.wav`), "बासठ", "डूंगरपुर", "डेढ़ लाख" |
| **Age Utterances** | 5 | "मेरी उम्र बासठ वर्ष है", "मैं अट्ठावन साल का हूँ", "साठ से ऊपर" |
| **Income Utterances** | 6 | "परिवार की आय डेढ़ लाख रुपये है", "दो लाख से कम है" |
| **District Utterances** | 9 | "जयपुर", "उदयपुर", "डूंगरपुर", "बांसवाड़ा", "जोधपुर", "बीकानेर", etc. |
| **Negation Utterances** | 3 | "मैं बीपीएल में नहीं हूँ", "सरकारी नौकरी में नहीं हूँ" |
| **Multi-Entity Utterance** | 1 | "मैं उदयपुर का किसान हूँ, मेरी उम्र पैंतालीस साल है, और परिवार की आय डेढ़ लाख है।" |
| **Acoustic Noise (Fan / Street)** | 2 | Speech recorded under simulated ambient noise |
| **Dialect-Influenced Phrasing** | 3 | Marwari/Mewari phrasing recorded in Rajasthan vernacular domain |
| **VAD Silence & Noise Tests** | 2 | Pure silence (`silence.wav`) and ambient white noise (`noise_only.wav`) |

---

## 6. Explicit Coverage Limitations & Future Work

As required by Day 28 guidelines, we explicitly document all current dataset limitations rather than exaggerating coverage:

1. `LIMITED_GENUINE_DIALECT_AUDIO`:
   The current voice gold dataset includes 3 dialect-style recordings (`RAJ-DIA-001` to `003`). While authentic to regional phrasing, this does not constitute full linguistic coverage across all 7 major dialects of Rajasthan (e.g. Shekhawati, Dhundhari, Harauti).
2. `LOW_OCR_TABLE_COUNT`:
   OCR table cases currently represent 10 cases from `DOC-BCF2C569-CHUNK-0003`. Expanding to additional multi-column complex tables with handwritten notes is planned for v1.1.
3. `SCHEME_DOMAIN_CONCENTRATION`:
   The verified schemes currently available in storage focus primarily on social security pensions (Mukhyamantri Vridhjan Samman Pension) and agricultural assistance. Additional verified schemes in education (scholarships) and health (Ayushman/Chiranjeevi) should be ingested in future iterations to expand search diversity.
