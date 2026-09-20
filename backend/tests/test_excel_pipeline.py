import io
from pathlib import Path
import tempfile
import uuid
import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.database.session import get_db_context
from app.ingestion.validator import DocumentValidationService
from app.ingestion.service import DocumentIngestionService
from app.parser.excel_parser import ExcelLayoutParser
from app.parser.service import DocumentParserService
from app.pipeline.auto_runner import run_full_pipeline
from app.main import app

client = TestClient(app)
settings = get_settings()


def create_test_excel_bytes(tag: str = "") -> bytes:
    """Generate a valid test Excel workbook in memory with government scheme data."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Welfare Schemes"

    suffix = f" {tag}" if tag else f" {uuid.uuid4().hex[:6]}"

    headers = [
        "Scheme ID",
        "Scheme Name (English)",
        "Scheme Name (Hindi)",
        "Department",
        "Target Beneficiaries",
        "Eligibility Criteria",
        "Benefits and Financial Assistance",
        "Required Documents",
        "Application Mode",
    ]
    ws.append(headers)

    row1 = [
        f"RJ-EDU-SCOOTY-{suffix.strip()}",
        f"Mukhyamantri Free Scooty Scheme 2026{suffix}",
        f"मुख्यमंत्री निःशुल्क स्कूटी योजना २०२६{suffix}",
        "Higher Education Department",
        "Meritorious College Girls",
        "Resident of Rajasthan, scored 75% or above in 12th Board, annual family income below Rs. 2.5 Lakh",
        "Free Motorized or Electric Scooty with helmet, insurance, and 2000 rupees fuel allowance",
        "Jan Aadhaar Card, 12th Marksheet, Domicile Certificate, Income Certificate",
        "Apply online via SSO Rajasthan portal or nearest Emitra kiosk",
    ]
    ws.append(row1)

    row2 = [
        f"RJ-AGR-TARBANDI-{suffix.strip()}",
        f"Rajasthan Tarbandi Subsidy Scheme{suffix}",
        f"राजस्थान तारबंदी अनुदान योजना{suffix}",
        "Department of Agriculture",
        "Small and Marginal Farmers",
        "Farmer possessing minimum 1.5 hectare agricultural land in Rajasthan",
        "50% financial subsidy on wire fencing cost up to maximum Rs. 48,000",
        "Jan Aadhaar Card, Jamabandi (land records), Bank passbook copy",
        "RajKisan Saathi Portal or Emitra center",
    ]
    ws.append(row2)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_excel_validation():
    """Verify that DocumentValidationService recognizes and validates an .xlsx file."""
    excel_bytes = create_test_excel_bytes()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(excel_bytes)
        tmp_path = Path(tmp.name)

    try:
        validator = DocumentValidationService()
        res = validator.validate(tmp_path, original_filename="Rajasthan_Schemes_2026.xlsx")

        assert res.valid is True
        assert res.file_extension == ".xlsx"
        assert res.mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert res.page_count == 1
        assert len(res.errors) == 0
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_excel_parser_extracts_tables_and_rows():
    """Verify ExcelLayoutParser extracts sheets, tables, and row paragraphs."""
    excel_bytes = create_test_excel_bytes()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(excel_bytes)
        tmp_path = Path(tmp.name)

    try:
        parser = ExcelLayoutParser()
        with tempfile.TemporaryDirectory() as out_dir:
            raw_result = parser.parse(tmp_path, raw_output_dir=Path(out_dir))

            assert raw_result.success is True
            assert raw_result.page_count == 1
            page = raw_result.pages[0]
            assert page.page_number == 1

            # Check that table was parsed
            table_blocks = [b for b in page.blocks if b.block_type == "TABLE"]
            assert len(table_blocks) >= 1
            tbl = table_blocks[0].table_data
            assert "Scheme Name (English)" in tbl.headers
            assert len(tbl.rows) == 2

            # Check that row paragraphs were generated
            para_blocks = [b for b in page.blocks if b.block_type == "PARAGRAPH"]
            assert len(para_blocks) >= 2
            assert "Mukhyamantri Free Scooty" in para_blocks[0].text
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_excel_upload_and_pipeline():
    """Test full upload of an Excel file via API and verify it ingests as .xlsx."""
    excel_bytes = create_test_excel_bytes()
    filename = "Welfare_Schemes_Rajasthan_2026.xlsx"

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"title": "Rajasthan Welfare Schemes Excel Upload"},
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["original_filename"] == filename
    assert data["stored_filename"] == "original.xlsx"
    assert data["file_extension"] == ".xlsx"
    assert data["mime_type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert data["processing_status"] in ["READY_FOR_DUPLICATE_CHECK", "PARSING", "READY_FOR_PARSING", "PUBLISHED", "READY_FOR_CHUNKING", "READY_FOR_OCR_CHECK"]

    # Verify the automated pipeline parsed the document into storage/parsed/<doc_id>/document.json
    doc_id = uuid.UUID(data["id"])
    parser_service = DocumentParserService()
    artifact = parser_service.get_parsed_artifact(doc_id)
    assert artifact is not None
    assert artifact["parser"]["name"] == "excel"
    assert len(artifact["pages"]) >= 1

    # Verify canonical tables and blocks in the parsed artifact
    page1 = artifact["pages"][0]
    blocks = page1.get("blocks", [])
    assert any(b.get("block_type") == "TABLE" for b in blocks)
    assert any("Mukhyamantri Free Scooty" in b.get("text", "") for b in blocks)
