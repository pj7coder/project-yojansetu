# JanSetu — Architecture Documentation

## Overview

JanSetu is an offline-first vernacular government-scheme discovery assistant for Rajasthan.

---

## Complete Pipeline (Day 1 – Day 9)

```text
Upload / Monitored Folder
         ↓
  Document Ingestion (Day 4)
  ├─ PDF Integrity & Magic Bytes Validation
  ├─ Streaming SHA-256 Hashing
  └─ Deterministic Storage (storage/originals/<doc_id>/original.pdf)
         ↓
READY_FOR_DUPLICATE_CHECK
         ↓
Duplicate & Version Detection (Day 5)
  ├─ 1. Exact Binary SHA-256 Check
  ├─ 2. Normalized Text Fingerprint (Unicode NFC)
  ├─ 3. Content Duplicate Check (Normalized Text Hash)
  ├─ 4. Candidate Narrowing (Page count range, source)
  └─ 5. Shingle Jaccard Similarity + Unified Line Diffing
         ↓
READY_FOR_PARSING
         ↓
Structured PDF Parsing (Day 6)
  ├─ 1. Parser Interface & Adapter (MinerU / BuiltinLayoutParser)
  ├─ 2. Physical 1-Based Page Indexing & Sequential Reading Order
  ├─ 3. Structured Block Classification (Heading, Paragraph, List, Table)
  ├─ 4. Quality Diagnostics (TEXT_OK, LOW_TEXT, NO_TEXT)
  └─ 5. Atomic Storage (storage/parsed/<doc_id>/document.json, document.md)
         ↓
READY_FOR_OCR_CHECK
         ↓
Corrective OCR Fallback (Day 7)
  ├─ 1. Selective Scanned/Low-Quality Page Detection
  ├─ 2. PaddleOCR on 250 DPI Page Crops
  ├─ 3. Numeric Risk & Hindi Devanagari Integrity
  └─ 4. Canonical Merged Document (storage/ocr/<doc_id>/merged_document.json)
         ↓
READY_FOR_CHUNKING
         ↓
Semantic Document Chunking (Day 8)
  ├─ 1. Bilingual Heading & Section Classification (14 types)
  ├─ 2. Legal Proviso & Exception Context Bonding
  ├─ 3. Token-Calibrated Sizing (3,000–8,000 tokens)
  ├─ 4. Dual-Tier Storage (chunks.json + individual chunk_XXXX.txt)
  └─ 5. Coverage Invariance (0 unassigned blocks)
         ↓
READY_FOR_EXTRACTION
         ↓
Local LLM Extraction with Llama 3.2 3B + Ollama (Day 9)
  ├─ 1. LLMProvider Abstraction (Ollama / Mock)
  ├─ 2. Anti-Prompt Injection Delimiters (BEGIN/END_SOURCE_DOCUMENT)
  ├─ 3. Strict Schema Enforced via Pydantic & JSON repair retry
  ├─ 4. Substring Evidence Validation (Unicode NFC + Whitespace Normalization)
  ├─ 5. Physical Page and Source Block Verification
  ├─ 6. Raw Value Preservation (No premature normalization)
  ├─ 7. Atomic 4-Part Artifact Storage (storage/extracted/<doc_id>/<chunk_id>/)
  └─ 8. Document Extraction Aggregator (storage/extracted/<doc_id>/document_extractions.json)
         ↓
READY_FOR_NORMALIZATION (Day 10 Input)
```

---

## Day 6 Architecture: Structured PDF Parsing with MinerU

### 1. Architectural Principles

- **Separation of Structure vs. Semantic Meaning**:
  Day 6 answers: *"What text and tables are in this PDF, and on which page and in what reading order do they appear?"* It does **NOT** attempt to determine eligibility, income criteria, or scheme benefits (which belong to later LLM extraction).
- **Original PDF Immutability**:
  The original government circular remains bit-for-bit immutable in `storage/originals/<doc_id>/original.pdf`. No in-place editing or overwriting ever occurs.
- **Parser Abstraction Boundary**:
  Business logic interacts solely with `DocumentParserService` via the `BaseParser` interface. The `MinerUAdapter` can be swapped or upgraded without modifying upstream callers.
- **Physical Page Linkage**:
  Every block strictly references its 1-based canonical physical PDF page number (`page_number`). This ensures future citizen-facing evidence citations ("See Page 4, Section 2") remain completely traceable.

---

### 2. Parser Component Architecture

```text
                  [ DocumentParserService ]
                              │
                              ▼
                     [ BaseParser Interface ]
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
      [ MinerUAdapter ]              [ BuiltinLayoutParser ]
   (CLI / magic-pdf Subprocess)      (Local PyMuPDF Layout Engine)
             │                                 │
             └────────────────┬────────────────┘
                              ▼
                      [ RawPageData ]
                              │
                              ▼
                 [ Document Normalizer ]
                 ├── build_normalized_document()
                 ├── generate_document_markdown()
                 └── write_parsed_artifacts_atomically()
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
[ storage/parsed/<doc_id>/ ]             [ PostgreSQL ]
├── document.json (Schema 1.0)           └── parsed_documents Table
├── document.md (Inspection)                 ├── parse_status = PARSED
└── mineru_raw/                              ├── pages_with_text
    └── raw_blocks.json                      └── READY_FOR_OCR_CHECK
```

---

### 3. Document Processing State Machine

```text
                  ┌───────────────────────────┐
                  │ READY_FOR_DUPLICATE_CHECK │
                  └─────────────┬─────────────┘
                                │ Duplicate check
                                ▼
                  ┌───────────────────────────┐
                  │     READY_FOR_PARSING     │
                  └─────────────┬─────────────┘
                                │ Worker picks up / POST /parse
                                ▼
                  ┌───────────────────────────┐
                  │          PARSING          │
                  └─────────────┬─────────────┘
         Parse failure          │          Parse success
     ┌──────────────────────────┴──────────────────────────┐
     ▼                                                     ▼
┌─────────────────────────┐               ┌───────────────────────────┐
│     PARSING_FAILED      │               │    READY_FOR_OCR_CHECK    │
│(Original PDF preserved) │               │(Page diagnostics captured)│
└─────────────────────────┘               └───────────────────────────┘
```

---

### 4. Normalized Document Schema (`document.json`)

```json
{
  "schema_version": "1.0",
  "document_id": "c61b2e8e-a9b0-4c1d-8f2e-123456789abc",
  "parser": {
    "name": "mineru",
    "version": "mineru-fallback (pymupdf-1.24.14)"
  },
  "page_count": 2,
  "pages": [
    {
      "page_number": 1,
      "status": "TEXT_OK",
      "text_character_count": 520,
      "block_count": 3,
      "blocks": [
        {
          "block_id": "blk_p1_000",
          "document_id": "c61b2e8e-a9b0-4c1d-8f2e-123456789abc",
          "page_number": 1,
          "order_index": 0,
          "block_type": "HEADING",
          "text": "राजस्थान सरकार सामाजिक न्याय विभाग",
          "section_path": ["राजस्थान सरकार सामाजिक न्याय विभाग"],
          "metadata": {"font_size": 16.0}
        },
        {
          "block_id": "blk_p1_001",
          "document_id": "c61b2e8e-a9b0-4c1d-8f2e-123456789abc",
          "page_number": 1,
          "order_index": 1,
          "block_type": "PARAGRAPH",
          "text": "योजना अंतर्गत पात्र विद्यार्थियों को छात्रवृत्ति प्रदान की जाएगी।",
          "section_path": ["राजस्थान सरकार सामाजिक न्याय विभाग"],
          "metadata": {"font_size": 11.5}
        },
        {
          "block_id": "blk_p1_002",
          "document_id": "c61b2e8e-a9b0-4c1d-8f2e-123456789abc",
          "page_number": 1,
          "order_index": 2,
          "block_type": "TABLE",
          "text": "Table: श्रेणी, आय सीमा",
          "section_path": ["राजस्थान सरकार सामाजिक न्याय विभाग"],
          "headers": ["श्रेणी", "आय सीमा"],
          "rows": [
            ["सामान्य", "₹2,00,000"],
            ["अन्य पिछड़ा वर्ग", "₹2,50,000"]
          ],
          "metadata": {"row_count": 2, "col_count": 2}
        }
      ]
    }
  ],
  "diagnostics": {
    "total_pages": 2,
    "pages_with_text": 2,
    "pages_without_text": 0,
    "pages_low_text": 0,
    "total_text_characters": 850,
    "total_blocks": 5,
    "total_tables": 1,
    "needs_ocr": false,
    "quality_assessment": "DIGITAL_COMPLETE"
  }
}
```

---

### 5. Quality Diagnostics & Page Categorization

| Page Text Status | Character Threshold | Diagnostic Interpretation | Action for Day 7 OCR |
| :--- | :--- | :--- | :--- |
| `TEXT_OK` | $\ge 100$ characters | Clean digital text extracted | Does not require OCR |
| `LOW_TEXT` | $1 \dots 99$ characters | Minimal text (e.g. stamp, signature, cover) | Candidate for supplemental OCR |
| `NO_TEXT` | $0$ characters | Scanned page or image-only | **Target for full OCR pipeline** |
| `PARSE_ERROR` | Corrupted | Garbled encoding or decompression failure | Target for image-based recovery |

---

### 6. Database Entity Relationship (`parsed_documents` and `ocr_runs`)

```text
┌────────────────────────────────────────┐
│               documents                │
├────────────────────────────────────────┤
│ id: UUID (PK)                          │
│ document_code: VARCHAR(64) (Unique)    │
│ storage_path: VARCHAR(500)             │
│ processing_status: VARCHAR(40)         │
│   - READY_FOR_PARSING                  │
│   - PARSING                            │
│   - READY_FOR_OCR_CHECK                │
│   - OCR_CHECKING                       │
│   - OCR_PROCESSING                     │
│   - READY_FOR_CHUNKING                 │
│   - OCR_FAILED                         │
│ sha256: VARCHAR(64)                    │
│ page_count: INTEGER                    │
└──────────────┬──────────────────┬──────┘
               │ 1                │ 1
               │                  │
               │ *                │ *
┌──────────────▼────────┐  ┌──────▼──────────────────────────────┐
│   parsed_documents    │  │               ocr_runs              │
├───────────────────────┤  ├─────────────────────────────────────┤
│ id: UUID (PK)         │  │ id: UUID (PK)                       │
│ document_id: UUID (FK)│  │ document_id: UUID (FK -> documents) │
│ parser_name: VARCHAR  │  │ ocr_engine: VARCHAR(50)             │
│ parse_status: VARCHAR │  │ ocr_version: VARCHAR(50)            │
│ page_count: INTEGER   │  │ status: VARCHAR(40)                 │
│ pages_with_text: INT  │  │   - COMPLETED                       │
│ pages_without_text:INT│  │   - SKIPPED_NOT_NEEDED              │
│ total_blocks: INTEGER │  │   - PARTIAL_FAILURE                 │
│ output_path: VARCHAR  │  │   - FAILED                          │
│ artifact_sha256: VAR  │  │ pages_total: INTEGER                │
│ created_at: TIMESTAMP │  │ pages_checked: INTEGER              │
└───────────────────────┘  │ pages_ocr_required: INTEGER         │
                           │ pages_ocr_success: INTEGER          │
                           │ pages_ocr_failed: INTEGER           │
                           │ low_confidence_numeric_regions: INT │
                           │ output_path: VARCHAR(500)           │
                           │ chunking_source_path: VARCHAR(500)  │
                           │ diagnostics: JSONB                  │
                           │ duration_ms: INTEGER                │
                           │ started_at: TIMESTAMP WITH TIME ZONE│
                           │ completed_at: TIMESTAMP WITH TIME Z │
                           │ created_at: TIMESTAMP WITH TIME ZONE│
                           └─────────────────────────────────────┘
```

---

## Day 7 Architecture: OCR Detection + PaddleOCR Fallback

### 1. Architectural Core Principle
> **MinerU remains the primary parser. PaddleOCR is strictly a page-level corrective fallback.**

Never replace the entire MinerU output because one page is scanned. High-quality digital extractions from MinerU are preserved untouched, while only deficient pages are rendered at 250 DPI and recognized via local OCR.

```text
Original Government PDF
          ↓
        MinerU
          ↓
   Page Quality Assessment
          ↓
 ┌────────┴────────┐
 │                 │
GOOD PAGE       BAD/SCAN PAGE
 │                 │
KEEP             PaddleOCR
 │                 │
 └────────┬────────┘
          ↓
     Safe Merge
          ↓
Merged Structured Document
with Page + Extraction Provenance
          ↓
READY_FOR_CHUNKING
```

### 2. Page-Level OCR Decision Signals
The decision to OCR a page is computed deterministically using observable signals:
- `text_character_count`: Sum of extracted characters on page.
- `image_count`: Number of raster images embedded in the page.
- `garbled_ratio`: Proportion of unprintable control chars or Unicode replacement characters (`\ufffd`).
- `status`: Parser status (`TEXT_OK`, `LOW_TEXT`, `NO_TEXT`, `PARSE_ERROR`).

**Conservative Rules (Avoiding False Triggers):**
1. `NO_TEXT` + `image_count > 0` $\to$ `needs_ocr = True` (`reason = "NO_TEXT_WITH_IMAGE"`)
2. `NO_TEXT` + `image_count == 0` (blank separator) $\to$ `needs_ocr = False` (`reason = "BLANK_DIVIDER"`)
3. `LOW_TEXT` (< 50 chars) + `image_count > 0` $\to$ `needs_ocr = True` (`reason = "LIKELY_SCANNED"`)
4. `LOW_TEXT` (< 50 chars) + `image_count == 0` (heading/signature) $\to$ `needs_ocr = False` (`reason = "TEXT_OK"`)
5. `garbled_ratio > 0.15` or replacement chars $\ge 3$ $\to$ `needs_ocr = True` (`reason = "GARBLED_TEXT"`)
6. `status == "PARSE_ERROR"` $\to$ `needs_ocr = True` (`reason = "PARSE_ERROR"`)
7. Standard text ($\ge 50$ chars) $\to$ `needs_ocr = False` (`reason = "TEXT_OK"`)

### 3. Merging & Provenance Preservation
- Merged document written to `storage/ocr/<doc_id>/merged_document.json`.
- Original PDF (`storage/originals/<doc_id>/original.pdf`) and MinerU output (`storage/parsed/<doc_id>/document.json`) remain strictly immutable.
- Every block retains explicit provenance:
  ```json
  {
    "block_id": "blk_p1_000",
    "extraction_method": "MINERU",
    "text": "..."
  },
  {
    "block_id": "blk_ocr_p2_000",
    "extraction_method": "PADDLEOCR",
    "text": "...",
    "ocr_confidence": 0.96,
    "metadata": {
      "bbox": [50.0, 70.0, 550.0, 100.0],
      "is_numeric": true,
      "low_confidence_numeric": false
    }
  }
  ```
- **Page Count Invariance**: `len(merged_pages) == original_page_count`.
- **Chunking Source Selection**:
  - If 0 pages required OCR: `chunking_source_path = storage/parsed/<doc_id>/document.json`
  - If pages required OCR: `chunking_source_path = storage/ocr/<doc_id>/merged_document.json`
  - Document status updates to `READY_FOR_CHUNKING` for Day 8.

---

## Day 8 Architecture: Semantic Document Chunking for Scheme Extraction

### 1. Why Logical Chunks Instead of Entire PDFs or Fixed Windows?

Government scheme documents are legally dense administrative circulars containing definitions, qualifications, benefits, document checklists, and exceptions. 

- **Why Not Entire PDFs?**
  A 40-page circular exceeds single-prompt LLM sweet spots, dilutes attention on specific eligibility clauses, and prevents fine-grained, evidence-backed page citations for citizens.
- **Why Not Fixed Character/Page Windows (e.g., every 3,000 chars or 5 pages)?**
  Fixed windows blindly slice through critical legal conditions. For instance, separating an eligibility clause on Page 7 from its proviso (*"Provided that..."*) or exception on Page 8 produces hallucinated or misleading eligibility advice.
- **The JanSetu Principle:**
  > **Structure-Aware + Page-Aware + Token-Aware = Semantically Complete Chunks.**
  > A slightly larger coherent chunk that preserves legal context is always preferred over an arbitrarily fragmented chunk that severs a rule from its caveat.

```text
Merged Structured Document
            ↓
    Structure Analysis
            ↓
  Bilingual Section Detection
            ↓
  Proviso & Exception Bonding
            ↓
    Token Sizing & Splitting
            ↓
┌─────────────────────────────────┐
│ Chunk 1: Overview               │
│ Chunk 2: Eligibility + Provisos │
│ Chunk 3: Benefits + Table       │
│ Chunk 4: Required Documents     │
│ Chunk 5: Application Process    │
└─────────────────────────────────┘
            ↓
Coverage & Continuity Validation
            ↓
READY_FOR_EXTRACTION (Day 9 Target)
```

### 2. Controlled Section Taxonomy

Sections are classified deterministically using bilingual Hindi and English regex dictionaries:

| Section Type | Common English Signals | Common Hindi Signals |
| :--- | :--- | :--- |
| `OVERVIEW` | Overview, Introduction, Background | परिचय, संक्षिप्त विवरण, पृष्ठभूमि |
| `DEFINITIONS` | Definitions, Interpretations, Meanings | परिभाषाएं, अर्थ, शब्दावली |
| `ELIGIBILITY` | Eligibility, Criteria, Who Can Apply | पात्रता, योग्यता, शर्तें, नियम एवं शर्तें |
| `EXCLUSIONS` | Exclusions, Ineligibility, Disqualifications | अपात्रता, बहिष्करण, अयोग्यता |
| `BENEFITS` | Benefits, Assistance, Allowance, Subsidy | लाभ, सहायता राशि, अनुदान, पेंशन |
| `DOCUMENTS_REQUIRED`| Required Documents, Enclosures, Checklist | आवश्यक दस्तावेज, संलग्नक, प्रमाण पत्र |
| `APPLICATION_PROCESS`| Application Process, How to Apply, Portal | आवेदन प्रक्रिया, आवेदन कैसे करें, पोर्टल |
| `DATES` | Important Dates, Deadlines, Timelines | महत्वपूर्ण तिथियां, अंतिम तिथि, समय सीमा |
| `FINANCIAL_RULES` | Financial Limits, Budget, Allocation | वित्तीय नियम, आय सीमा, बजट |
| `CONTACTS` | Helpline, Contacts, Nodal Officers | संपर्क, हेल्पलाइन, नोडल अधिकारी |
| `ANNEXURE` | Annexure, Schedule, Appendix | परिशिष्ट, अनुसूची, प्रपत्र |
| `AMENDMENT` | Amendment, Corrigendum, Notification | संशोधन, शुद्धिपत्र, अधिसूचना |
| `GENERAL` | General Terms, Administration | सामान्य निर्देश, प्रशासनिक |
| `UNKNOWN` | Unrecognized structural headings | - |

### 3. Legal Context & Proviso Protection

Legal exceptions and provisos are bonded directly to preceding rule blocks. The system enforces:
- Blocks matching `PROVISO_EXCEPTION_REGEX` (*provided that*, *except*, *however*, *subject to*, *परंतु*, *किन्तु*, *बशर्ते*, *अपवाद*, *लागू नहीं होगा*) **CANNOT** initiate new section groups.
- Oversized section splitting is prohibited from cutting immediately before or within a proviso block.
- Surrounding context windows are unified into the parent candidate chunk.

### 4. Calibrated Token Sizing & Splitting Controls

- **Token Estimator**: Calibrated specifically for Llama 3.2 tokenization, accounting for Devanagari subwords (~1.5 tokens/word in Hindi, ~1.3 tokens/word in English).
- **Target Size**: 4,000–6,000 tokens (range 3,000–8,000).
- **Hard Max**: 8,000 tokens. Sections exceeding 8,000 tokens split at logical block boundaries with 200-token overlap, flagging `overlap_from_previous = true`.
- **Min Size**: 300 tokens. Minor trailing orphan paragraphs merge with adjacent same-section chunks without crossing topic boundaries.

### 5. Invariant Validation & Provenance

Before a document is marked `READY_FOR_EXTRACTION`, `ChunkValidator` enforces:
1. **100% Coverage Invariance**: `unassigned_blocks == 0`. Every meaningful block must be assigned to a chunk; running headers, footers, and page numbers are accounted for as `excluded_boilerplate_blocks`.
2. **Page Continuity**: `page_start <= page_end`, and every block's physical page lies within that range.
3. **Traceability**: Every chunk retains `source_block_ids`, `page_start`, `page_end`, `contains_table`, and `contains_ocr`.
4. **Idempotency**: Running `DocumentChunkingService` or `ChunkingWorker` multiple times cleans previous chunk artifacts and database rows without duplication.

---

## Day 9 Architecture: Local LLM Extraction with Llama 3.2 3B + Ollama

### 1. Architectural Principles

- **Extractor, Not an Authority**:
  The LLM is an extraction instrument, never a decision-maker. It does NOT decide citizen eligibility, does NOT invent missing fields, and does NOT normalize values into final rule trees. The government source document remains the sole authoritative truth.
- **Strict Evidence Citation**:
  Every extracted factual item (eligibility condition, benefit, document requirement, exception, financial rule) MUST be accompanied by an `evidence` object containing verbatim `evidence_text`, `page_numbers`, `source_block_ids`, and `chunk_id`.
- **Preservation of Raw Values**:
  Values such as `"₹2,00,000"`, `"60 वर्ष से अधिक"`, `"राजस्थान का मूल निवासी"`, `"40% disability"` are retained in raw, un-coerced format. Machine normalization into rule operators belongs strictly to Day 10.
- **Provider Abstraction**:
  Business logic interacts solely with `LLMProvider` (`OllamaProvider` for local offline inference, `MockLLMProvider` for deterministic testing). No direct `requests` or `curl` calls are scattered across services.
- **Anti-Prompt Injection Enclosure**:
  Source documents are treated as untrusted data and strictly bounded inside `BEGIN_SOURCE_DOCUMENT` and `END_SOURCE_DOCUMENT` tags, with explicit instructions to ignore instructions embedded inside source circulars.
- **Mechanical Evidence Verification**:
  Every extracted item is verified by `EvidenceValidator` using deterministic Unicode NFC and whitespace normalized substring matching against the source chunk text. Mismatches are marked `EVIDENCE_MATCH_FAILED` / `REVIEW_REQUIRED`.

---

### 2. Component Architecture

```text
               [ DocumentChunk ] (READY_FOR_EXTRACTION)
                       │
                       ▼
           [ SchemeExtractionService ]
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
[ Extraction Prompt Builder ]   [ LLMProvider (Ollama) ]
├─ System rules                 ├─ llama3.2:3b local
├─ Injection delimiters         ├─ temperature: 0.0
└─ Chunk text + page markers    └─ format: "json"
       │                               │
       └───────────────┬───────────────┘
                       ▼
               [ Raw LLM JSON ]
                       │
                       ▼
           [ Pydantic Schema Validation ]
           (ChunkExtractionResult, SchemeRawExtraction)
                       │
                       ▼
             [ EvidenceValidator ]
             ├─ Substring containment check
             ├─ Page number validation
             └─ Source block ID verification
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
[ File System Artifacts ]       [ PostgreSQL Database ]
storage/extracted/<doc_id>/<chunk_id>/
├─ request_metadata.json        extraction_runs Table
├─ raw_response.txt             ├─ status: EXTRACTED
├─ extraction.json              ├─ prompt_version: "1.0"
└─ validation.json              └─ duration_ms, tokens
                       │
                       ▼
         [ DocumentExtractionAggregator ]
         ├─ Verifies all chunks processed
         ├─ Builds document_extractions.json
         └─ Updates document status -> READY_FOR_NORMALIZATION
```

---

### 3. Data Schema & Evidence Object

```json
{
  "schema_version": "1.0",
  "document_id": "c61b2e8e-a9b0-4c1d-8f2e-123456789abc",
  "chunk_id": "e4a5bc12-8d91-4c12-b185-3b95a32b0f50",
  "section_type": "ELIGIBILITY",
  "schemes": [
    {
      "scheme_name": "मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना",
      "department": "सामाजिक न्याय एवं अधिकारिता विभाग",
      "purpose": ["वृद्ध नागरिकों को आर्थिक संबल प्रदान करना"],
      "target_beneficiaries": ["वृद्धजन (पुरुष 58+ वर्ष, महिला 55+ वर्ष)"],
      "eligibility_conditions": [
        {
          "field": "residence",
          "condition": "राजस्थान का मूल निवासी होना अनिवार्य है।",
          "logical_connector": "AND",
          "evidence": {
            "value": "राजस्थान का मूल निवासी",
            "evidence_text": "आवेदक राजस्थान का मूल निवासी होना चाहिए",
            "page_numbers": [2],
            "source_block_ids": ["blk_p2_001"],
            "chunk_id": "e4a5bc12-8d91-4c12-b185-3b95a32b0f50",
            "extraction_method": "LLM"
          }
        }
      ],
      "exclusions": [
        {
          "exclusion": "अन्य किसी सरकारी पेंशन का लाभार्थी न हो।",
          "evidence": {
            "value": "अन्य पेंशन लाभार्थी अपात्र",
            "evidence_text": "आवेदक पूर्व से अन्य किसी योजनान्तर्गत पेंशन प्राप्त न कर रहा हो",
            "page_numbers": [2],
            "source_block_ids": ["blk_p2_003"],
            "chunk_id": "e4a5bc12-8d91-4c12-b185-3b95a32b0f50",
            "extraction_method": "LLM"
          }
        }
      ],
      "benefits": [
        {
          "benefit_type": "pension",
          "raw_amount": "₹1,000 प्रति माह",
          "frequency_text": "प्रति माह",
          "description": "75 वर्ष से कम आयु के लाभार्थियों को ₹1,000 प्रति माह",
          "evidence": {
            "value": "₹1,000 प्रति माह",
            "evidence_text": "75 वर्ष से कम आयु के पेंशनरों को ₹1,000 प्रति माह देय होगी",
            "page_numbers": [3],
            "source_block_ids": ["blk_p3_002"],
            "chunk_id": "e4a5bc12-8d91-4c12-b185-3b95a32b0f50",
            "extraction_method": "LLM"
          }
        }
      ],
      "required_documents": [
        {
          "document_name": "जन आधार कार्ड",
          "is_mandatory": true,
          "evidence": {
            "value": "जन आधार कार्ड",
            "evidence_text": "जन आधार कार्ड की प्रति संलग्न करना अनिवार्य है",
            "page_numbers": [3],
            "source_block_ids": ["blk_p3_005"],
            "chunk_id": "e4a5bc12-8d91-4c12-b185-3b95a32b0f50",
            "extraction_method": "LLM"
          }
        }
      ]
    }
  ]
}
```

---

### 4. Database Model (`extraction_runs`)

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` (PK) | Primary key for run |
| `document_id` | `UUID` (FK) | Reference to parent `documents.id` (CASCADE) |
| `chunk_id` | `UUID` (FK) | Reference to `document_chunks.id` (CASCADE) |
| `chunk_id_str` | `VARCHAR(100)` | Readable chunk identifier (e.g. `DOC-XXXX-CHUNK-0001`) |
| `model_provider` | `VARCHAR(50)` | LLM provider name (`ollama`, `mock`) |
| `model_name` | `VARCHAR(100)` | Model identifier (`llama3.2:3b`) |
| `prompt_version` | `VARCHAR(20)` | Prompt template version (`1.0`) |
| `schema_version` | `VARCHAR(20)` | Output schema version (`1.0`) |
| `status` | `VARCHAR(50)` | `EXTRACTED`, `EXTRACTION_REVIEW_REQUIRED`, `EXTRACTION_FAILED` |
| `artifact_path` | `VARCHAR(500)` | File storage path to extraction artifacts |
| `input_token_estimate` | `INTEGER` | Estimated input prompt tokens |
| `output_tokens` | `INTEGER` | Reported output generation tokens |
| `duration_ms` | `INTEGER` | Total end-to-end execution time in milliseconds |
| `failure_reason` | `VARCHAR(255)` | Error code if failed (`MODEL_UNAVAILABLE`, `INVALID_JSON`) |
| `diagnostics` | `JSONB` | Detailed evidence validation and quality diagnostics |
| `started_at` | `TIMESTAMP` | Execution start timestamp |
| `completed_at` | `TIMESTAMP` | Execution completion timestamp |
| `created_at` | `TIMESTAMP` | Record creation timestamp |

---

### 5. Document Aggregation Lifecycle

```text
All chunks for Document
       │
       ▼
[ Query Chunks in DB ]
       │
  ┌────┴──────────────────────────────┐
  ▼                                   ▼
All Chunks Successful           Any Chunk Failed
(status == EXTRACTED            (status == EXTRACTION_FAILED)
 or REVIEW_REQUIRED)                  │
  │                                   ▼
  ▼                             Document status ->
Document status ->              EXTRACTION_PARTIAL_FAILURE
READY_FOR_NORMALIZATION         (Retry via POST /api/v1/chunks/{id}/reextract)
```

---

## 10. Evaluation Truth Architecture (Days 28–32)

To ensure scientific rigor, avoid self-fulfilling validation, and prevent AI hallucinations from polluting benchmark truth, JanSetu decouples system implementation from reference ground truth.

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

### Core Architecture Invariants:
1. **The System Does Not Grade Itself**: The extraction pipeline, eligibility engine, search rankings, and voice models do not generate their own evaluation answers. All gold facts are derived from official circulars and human verification.
2. **Data-Leakage Protected Evaluation**: The `GoldBenchmarkLoader` exposes `get_runtime_inputs(...)` which strips all target facts, statuses, and reference transcripts, guaranteeing that runtime evaluators receive input-only objects.
3. **Tri-State Deterministic Logic**: Eligibility ground truth strictly adheres to `ELIGIBLE`, `NOT_ELIGIBLE`, and `MORE_INFORMATION_REQUIRED`, evaluating boundary conditions, short-circuiting, and temporal version dates.
4. **Zero Citizen PII**: All citizen profiles are synthetic; an automated PII detector scans for Aadhaar, phone, and email patterns.
5. **Frozen Manifest Checksum**: Version 1.0 is sealed with SHA-256 `14467fd3edbe21f63a3a16b104089f845e194ce116ea0a2e563a85a7c686b46e` across 280 cases.

---

## 11. Document Extraction Evaluation & Pipeline Attribution (Day 29)

Day 29 implements the extraction accuracy benchmark layer measuring field detection, semantic value equivalence, operator boundary accuracy, logical connector trees, and evidence grounding.

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

### 1. Multi-Dimensional Dimensions
- **Field Detection**: Computes Precision, Recall, and F1 over canonical field identifiers.
- **Value Normalization**: Deterministic semantic normalization for currency, percentages, age, and Devanagari numerals ($₹2\text{ लाख} \equiv 200000\text{ INR}$).
- **Operator Exact Accuracy**: Boundary sensitivity ensuring inclusive ($\le, \ge$) and strict ($<, >$) relational operators are not conflated.
- **Rule-Tree Canonicalization**: Structural boolean AST equivalence under commutative ordering ($A \land B \equiv B \land A$ and $A \lor B \equiv B \lor A$).
- **Evidence Reference Validity & Support**: Distinguishes textual reference existence from genuine semantic factual support.
- **Hallucination Rate**: Identifies ungrounded factual inventions and critical hallucinations (invented income limits, age limits, exclusions).

### 2. Earliest Pipeline-Stage Attribution
When an extraction fails, the evaluator attributes the root cause to the earliest failing stage:
1. `PARSING_OCR`: Scanned digit corruption or table structure degradation.
2. `CHUNKING`: Rule clause boundary truncations or context loss across chunks.
3. `LLM_EXTRACTION`: Model omission, hallucination, wrong operator, or wrong value.
4. `NORMALIZATION`: Parser failure converting raw LLM text to canonical numbers/units.
5. `EVIDENCE_VERIFICATION`: Ungrounded evidence citations or page/block mismatches.


