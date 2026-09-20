import re
from typing import List, Optional

from app.normalization.schemas import CanonicalDocument, DocumentTypeEnum


def normalize_document_requirement(
    name_raw: str,
    mandatory_stated: Optional[bool],
    notes: Optional[str],
    evidence_refs: List[str],
    doc_id: str,
) -> CanonicalDocument:
    """
    Map raw document names to controlled DocumentTypeEnum while preserving raw naming.
    Does not assume mandatory=True unless source explicitly indicates.
    """
    lower = name_raw.lower()

    dtype = DocumentTypeEnum.OTHER
    if re.search(r'(जन\s*आधार|jan\s*aadhaar|janaadhaar)', lower):
        dtype = DocumentTypeEnum.JAN_AADHAAR
    elif re.search(r'(आधार|aadhaar|aadhar|uid)', lower):
        dtype = DocumentTypeEnum.AADHAAR
    elif re.search(r'(आय\s*प्रमाण\s*पत्र|income\s*certificate)', lower):
        dtype = DocumentTypeEnum.INCOME_CERTIFICATE
    elif re.search(r'(मूल\s*निवास|निवास\s*प्रमाण\s*पत्र|domicile|residence\s*certificate)', lower):
        dtype = DocumentTypeEnum.DOMICILE_CERTIFICATE
    elif re.search(r'(जाति\s*प्रमाण\s*पत्र|caste\s*certificate)', lower):
        dtype = DocumentTypeEnum.CASTE_CERTIFICATE
    elif re.search(r'(दिव्यांग|विकलांग\s*प्रमाण\s*पत्र|disability\s*certificate)', lower):
        dtype = DocumentTypeEnum.DISABILITY_CERTIFICATE
    elif re.search(r'(बैंक\s*पासबुक|bank\s*passbook|खाता|account)', lower):
        dtype = DocumentTypeEnum.BANK_PASSBOOK
    elif re.search(r'(फोटो|photo|photograph)', lower):
        dtype = DocumentTypeEnum.PHOTO
    elif re.search(r'(राशन\s*कार्ड|ration\s*card)', lower):
        dtype = DocumentTypeEnum.RATION_CARD
    elif re.search(r'(जमाबंदी|खतौनी|land\s*record|पटवारी)', lower):
        dtype = DocumentTypeEnum.LAND_RECORD
    elif re.search(r'(अंकतालिका|marksheet|certificate)', lower):
        dtype = DocumentTypeEnum.MARKSHEET

    return CanonicalDocument(
        document_id=doc_id,
        document_type=dtype,
        name_raw=name_raw,
        mandatory=mandatory_stated,
        notes=notes,
        evidence_refs=evidence_refs,
    )
