"""
Deterministic Profile Extractor for YojanSetu.
Provides < 2ms fast path for direct expected-field answers and rule-based multi-fact parsing
without relying on an LLM for simple statements.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.profile_extraction.boolean_parser import BooleanAndStatusParser
from app.profile_extraction.location_parser import LocationAndDistrictParser
from app.profile_extraction.number_parser import HindiNumberParser
from app.profile_extraction.schemas import (
    CandidateProfileUpdate,
    CandidateStatus,
    ExtractionMethod,
    InputSource,
)

OCCUPATION_MAP: Dict[str, str] = {
    "किसान": "FARMER", "खेती": "FARMER", "काश्तकार": "FARMER", "farmer": "FARMER",
    "मजदूर": "LABOURER", "मजदूरी": "LABOURER", "श्रमिक": "LABOURER", "labourer": "LABOURER", "daily wage": "LABOURER",
    "छात्र": "STUDENT", "विद्यार्थी": "STUDENT", "student": "STUDENT",
    "स्वरोजगार": "SELF_EMPLOYED", "दुकान": "SELF_EMPLOYED", "छोटा व्यवसाय": "SELF_EMPLOYED", "self employed": "SELF_EMPLOYED",
    "दस्तकार": "ARTISAN", "कारीगर": "ARTISAN", "artisan": "ARTISAN",
    "बेरोजगार": "UNEMPLOYED", "unemployed": "UNEMPLOYED",
}

SOCIAL_CATEGORY_MAP: Dict[str, str] = {
    "सामान्य": "GENERAL", "जनरल": "GENERAL", "general": "GENERAL",
    "ओबीसी": "OBC", "obc": "OBC", "अन्य पिछड़ा वर्ग": "OBC",
    "एससी": "SC", "sc": "SC", "अनुसूचित जाति": "SC",
    "एसटी": "ST", "st": "ST", "अनुसूचित जनजाति": "ST",
    "एमबीसी": "MBC", "mbc": "MBC", "अति पिछड़ा वर्ग": "MBC",
    "ईडब्ल्यूएस": "EWS", "ews": "EWS", "आर्थिक रूप से कमजोर": "EWS",
}


class DeterministicProfileExtractor:
    """
    Extracts candidate profile facts deterministically from citizen text.
    """

    def extract_expected_field(
        self,
        text: str,
        expected_field: str,
        input_source: InputSource = InputSource.TEXT_INPUT,
    ) -> List[CandidateProfileUpdate]:
        """
        Fast-path extraction when the system already knows the expected question field.
        """
        clean = text.strip()
        candidates: List[CandidateProfileUpdate] = []

        # Check if user is redirecting/answering another field instead
        if expected_field != "age" and re.search(r'(उम्र|आयु|साल\s*का|वर्ष\s*का)', clean):
            age_val = HindiNumberParser.parse_compound_indian_number(clean)
            if age_val is not None and 0 <= age_val <= 125:
                candidates.append(
                    CandidateProfileUpdate(
                        field="age",
                        value=age_val,
                        raw_value=clean,
                        source_text=clean,
                        input_source=input_source,
                        extraction_method=ExtractionMethod.EXPECTED_FIELD_PARSER,
                        status=CandidateStatus.EXTRACTED,
                        normalization_steps=["HINDI_NUMBER_TO_INTEGER", "FIELD_REDIRECT"],
                    )
                )
                return candidates

        # Field: AGE
        if expected_field == "age":
            num = HindiNumberParser.parse_compound_indian_number(clean)
            if num is not None and 0 <= num <= 125:
                candidates.append(
                    CandidateProfileUpdate(
                        field="age",
                        value=num,
                        raw_value=clean,
                        source_text=clean,
                        input_source=input_source,
                        extraction_method=ExtractionMethod.EXPECTED_FIELD_PARSER,
                        status=CandidateStatus.EXTRACTED,
                        normalization_steps=["HINDI_NUMBER_TO_INTEGER"],
                    )
                )
            return candidates

        # Field: FAMILY_INCOME / ANNUAL_INCOME
        if expected_field in ("family_income", "annual_income"):
            is_approx = HindiNumberParser.is_approximate(clean)
            # Check range
            rng = HindiNumberParser.parse_range(clean)
            if rng is not None:
                candidates.append(
                    CandidateProfileUpdate(
                        field=expected_field,
                        value=rng[0],  # store min as nominal with range bounds
                        range_min=rng[0],
                        range_max=rng[1],
                        raw_value=clean,
                        source_text=clean,
                        input_source=input_source,
                        extraction_method=ExtractionMethod.EXPECTED_FIELD_PARSER,
                        status=CandidateStatus.AMBIGUOUS,
                        requires_confirmation=True,
                        confirmation_reason="RANGE_EXPRESSION_REQUIRES_CLARIFICATION",
                        unit="INR",
                        frequency="ANNUAL",
                    )
                )
                return candidates

            amt = HindiNumberParser.parse_compound_indian_number(clean)
            if amt is not None and amt >= 0:
                period = HindiNumberParser.detect_periodicity(clean, default="ANNUAL")
                candidates.append(
                    CandidateProfileUpdate(
                        field=expected_field,
                        value=amt,
                        raw_value=clean,
                        source_text=clean,
                        input_source=input_source,
                        extraction_method=ExtractionMethod.EXPECTED_FIELD_PARSER,
                        status=CandidateStatus.AMBIGUOUS if is_approx else CandidateStatus.EXTRACTED,
                        requires_confirmation=is_approx,
                        confirmation_reason="APPROXIMATE_VALUE" if is_approx else None,
                        is_approximate=is_approx,
                        unit="INR",
                        frequency=period,
                        normalization_steps=["INDIAN_SCALE_TO_INR"],
                    )
                )
            return candidates

        # Field: BPL_STATUS / DISABILITY_STATUS / STUDENT_STATUS / WIDOW_STATUS
        if expected_field in ("bpl_status", "disability_status", "student_status", "widow_status", "farmer_status"):
            # Check negation
            if BooleanAndStatusParser.detect_negation(clean):
                candidates.append(
                    CandidateProfileUpdate(
                        field=expected_field,
                        value=False,
                        raw_value=clean,
                        source_text=clean,
                        input_source=input_source,
                        extraction_method=ExtractionMethod.EXPECTED_FIELD_PARSER,
                        status=CandidateStatus.EXTRACTED,
                        normalization_steps=["NEGATION_TO_FALSE"],
                    )
                )
                return candidates

            b_val = BooleanAndStatusParser.parse_direct_boolean(clean)
            if b_val is not None:
                candidates.append(
                    CandidateProfileUpdate(
                        field=expected_field,
                        value=b_val,
                        raw_value=clean,
                        source_text=clean,
                        input_source=input_source,
                        extraction_method=ExtractionMethod.EXPECTED_FIELD_PARSER,
                        status=CandidateStatus.EXTRACTED,
                        normalization_steps=["BOOLEAN_TOKEN_MAPPING"],
                    )
                )
            return candidates

        # Field: DISTRICT
        if expected_field == "district":
            dist = LocationAndDistrictParser.parse_district(clean)
            if dist is not None:
                candidates.append(
                    CandidateProfileUpdate(
                        field="district",
                        value=dist,
                        raw_value=clean,
                        source_text=clean,
                        input_source=input_source,
                        extraction_method=ExtractionMethod.EXPECTED_FIELD_PARSER,
                        status=CandidateStatus.EXTRACTED,
                        normalization_steps=["DISTRICT_REGISTRY_LOOKUP"],
                    )
                )
            return candidates

        # Field: OCCUPATION
        if expected_field == "occupation":
            for kw, occ in OCCUPATION_MAP.items():
                if kw in clean.lower():
                    candidates.append(
                        CandidateProfileUpdate(
                            field="occupation",
                            value=occ,
                            raw_value=clean,
                            source_text=clean,
                            input_source=input_source,
                            extraction_method=ExtractionMethod.EXPECTED_FIELD_PARSER,
                            status=CandidateStatus.EXTRACTED,
                            normalization_steps=["OCCUPATION_SYNONYM_MAP"],
                        )
                    )
                    break
            return candidates

        # Field: SOCIAL_CATEGORY
        if expected_field == "social_category":
            for kw, cat in SOCIAL_CATEGORY_MAP.items():
                if kw in clean.lower():
                    candidates.append(
                        CandidateProfileUpdate(
                            field="social_category",
                            value=cat,
                            raw_value=clean,
                            source_text=clean,
                            input_source=input_source,
                            extraction_method=ExtractionMethod.EXPECTED_FIELD_PARSER,
                            status=CandidateStatus.EXTRACTED,
                            normalization_steps=["SOCIAL_CATEGORY_MAP"],
                        )
                    )
                    break
            return candidates

        return candidates

    def extract_open_utterance(
        self,
        text: str,
        input_source: InputSource = InputSource.TEXT_INPUT,
    ) -> Tuple[List[CandidateProfileUpdate], Optional[str]]:
        """
        Deterministic multi-fact rule extraction from open citizen utterances.
        Returns: (candidates, need_text)
        """
        clean = text.strip()
        candidates: List[CandidateProfileUpdate] = []
        need_text: Optional[str] = None

        # Check for adversarial manipulation / non-factual hypothetical statements
        for manip in [
            r'(मान\s*लो|मान\s*लीजिए|दिखाने\s*के\s*लिए|दिखा\s*दो|लिख\s*दो|पात्र\s*बना\s*दो|पात्र\s*दिखाने)',
            r'(suppose|assume|pretend|make\s*me\s*eligible|mark\s*me\s*eligible|ignore\s*all)',
        ]:
            if re.search(manip, clean, re.IGNORECASE):
                # Non-factual assertion or prompt injection; do not extract simulated facts
                return (candidates, need_text)

        # 1. District detection
        district = LocationAndDistrictParser.parse_district(clean)
        if district:
            candidates.append(
                CandidateProfileUpdate(
                    field="district",
                    value=district,
                    source_text=clean,
                    input_source=input_source,
                    extraction_method=ExtractionMethod.DETERMINISTIC,
                    status=CandidateStatus.EXTRACTED,
                    normalization_steps=["DISTRICT_REGISTRY_LOOKUP"],
                )
            )

        # 2. State & Domicile detection (strictly separated!)
        state, domicile = LocationAndDistrictParser.parse_residence_vs_domicile(clean)
        if domicile:
            candidates.append(
                CandidateProfileUpdate(
                    field="domicile_status",
                    value=domicile,
                    source_text=clean,
                    input_source=input_source,
                    extraction_method=ExtractionMethod.DETERMINISTIC,
                    status=CandidateStatus.EXTRACTED,
                    normalization_steps=["DOMICILE_EXPLICIT_VERIFICATION"],
                )
            )
        elif state:
            candidates.append(
                CandidateProfileUpdate(
                    field="state",
                    value=state,
                    source_text=clean,
                    input_source=input_source,
                    extraction_method=ExtractionMethod.DETERMINISTIC,
                    status=CandidateStatus.EXTRACTED,
                    normalization_steps=["STATE_RESIDENCE_MAPPING"],
                )
            )

        # 3. Rural / Urban
        ru = LocationAndDistrictParser.parse_rural_urban(clean)
        if ru:
            candidates.append(
                CandidateProfileUpdate(
                    field="rural_urban",
                    value=ru,
                    source_text=clean,
                    input_source=input_source,
                    extraction_method=ExtractionMethod.DETERMINISTIC,
                    status=CandidateStatus.EXTRACTED,
                    normalization_steps=["RURAL_URBAN_CLASSIFICATION"],
                )
            )

        # 4. Occupation (explicit only; does not infer from land!)
        for kw, occ in OCCUPATION_MAP.items():
            if re.search(r'\b' + re.escape(kw) + r'\b', clean, re.IGNORECASE) or kw in clean:
                candidates.append(
                    CandidateProfileUpdate(
                        field="occupation",
                        value=occ,
                        raw_value=kw,
                        source_text=clean,
                        input_source=input_source,
                        extraction_method=ExtractionMethod.DETERMINISTIC,
                        status=CandidateStatus.EXTRACTED,
                        normalization_steps=["OCCUPATION_EXPLICIT_MATCH"],
                    )
                )
                break

        # 5. Social Category (explicit only)
        for kw, cat in SOCIAL_CATEGORY_MAP.items():
            if re.search(r'\b' + re.escape(kw) + r'\b', clean, re.IGNORECASE) or kw in clean:
                candidates.append(
                    CandidateProfileUpdate(
                        field="social_category",
                        value=cat,
                        raw_value=kw,
                        source_text=clean,
                        input_source=input_source,
                        extraction_method=ExtractionMethod.DETERMINISTIC,
                        status=CandidateStatus.EXTRACTED,
                        normalization_steps=["SOCIAL_CATEGORY_EXPLICIT_MATCH"],
                    )
                )
                break

        # 6. Age pattern: (मेरी उम्र|आयु|उमर|age|umar) [number] (साल|वर्ष|saal)?
        age_match = re.search(
            r'(?:मेरी|मेरा|meri|mera)?\s*(?:उम्र|आयु|उमर|age|umar)\s*(?:करीब|लगभग|around|approx)?\s*([^\s,।]+)\s*(?:साल|वर्ष|saal|year|years)?',
            clean,
            re.IGNORECASE,
        )
        if not age_match:
            age_match = re.search(r'([^\s,।]+)\s*(?:साल\s*का|वर्ष\s*का|साल\s*की|वर्ष\s*की|saal\s*ka)', clean, re.IGNORECASE)

        if age_match:
            raw_age = age_match.group(1)
            age_val = HindiNumberParser.parse_single_number(raw_age)
            if age_val is not None and 0 <= age_val <= 125:
                candidates.append(
                    CandidateProfileUpdate(
                        field="age",
                        value=age_val,
                        raw_value=raw_age,
                        source_text=age_match.group(0),
                        input_source=input_source,
                        extraction_method=ExtractionMethod.DETERMINISTIC,
                        status=CandidateStatus.EXTRACTED,
                        normalization_steps=["HINDI_CARDINAL_AGE"],
                    )
                )

        # 7. Income pattern (Family vs Personal)
        # Matches phrases like "घर की सालाना आमदनी डेढ़ लाख", "कमाई दो लाख", "आय करीब डेढ़ लाख"
        income_match = re.search(
            r'((?:परिवार|घर|मेरी|सालाना|वार्षिक|कुल)?\s*(?:की\s*)?(?:सालाना|वार्षिक)?\s*(?:आमदनी|आय|कमाई)\s*(?:करीब|लगभग)?\s*([^\s,।]+(?:\s+[^\s,।]+)?(?:\s+[^\s,।]+)?))',
            clean,
            re.IGNORECASE,
        )
        if income_match:
            income_clause = income_match.group(1)
            has_family = bool(re.search(r'(परिवार|पारिवारिक|घर|घरां|household|family)', clean, re.IGNORECASE))
            income_field = "family_income" if has_family else HindiNumberParser.detect_income_scope(income_clause)
            is_approx = HindiNumberParser.is_approximate(income_clause) or HindiNumberParser.is_approximate(clean)
            period = HindiNumberParser.detect_periodicity(income_clause, default=HindiNumberParser.detect_periodicity(clean, default="ANNUAL"))
            amt = HindiNumberParser.parse_compound_indian_number(income_clause)
            if amt is not None and amt >= 0:
                candidates.append(
                    CandidateProfileUpdate(
                        field=income_field,
                        value=amt,
                        raw_value=income_match.group(2),
                        source_text=income_clause,
                        input_source=input_source,
                        extraction_method=ExtractionMethod.DETERMINISTIC,
                        status=CandidateStatus.EXTRACTED,
                        is_approximate=is_approx,
                        unit="INR",
                        frequency=period,
                        normalization_steps=["INDIAN_SCALE_INCOME"],
                    )
                )

        # 8. Disability status & percentage
        if re.search(r'(दिव्यांग|विकलांग|handicapped|disabled)', clean):
            candidates.append(
                CandidateProfileUpdate(
                    field="disability_status",
                    value=True,
                    source_text=clean,
                    input_source=input_source,
                    extraction_method=ExtractionMethod.DETERMINISTIC,
                    status=CandidateStatus.EXTRACTED,
                    normalization_steps=["DISABILITY_INDICATOR"],
                )
            )
            # Check percentage
            pct_m = re.search(r'([^\s,।]+)\s*(?:प्रतिशत|%|percent)', clean)
            if pct_m:
                pct_val = HindiNumberParser.parse_single_number(pct_m.group(1))
                if pct_val is not None and 0 <= pct_val <= 100:
                    candidates.append(
                        CandidateProfileUpdate(
                            field="disability_percentage",
                            value=pct_val,
                            raw_value=pct_m.group(1),
                            source_text=pct_m.group(0),
                            input_source=input_source,
                            extraction_method=ExtractionMethod.DETERMINISTIC,
                            status=CandidateStatus.EXTRACTED,
                            unit="PERCENT",
                            normalization_steps=["DISABILITY_PERCENTAGE"],
                        )
                    )

        # 9. Land holding: "दो बीघा", "5 एकड़", "2 hectare"
        land_m = re.search(r'([^\s,।]+)\s*(बीघा|bigha|हेक्टेयर|hectare|एकड़|acre)\s*(?:जमीन|भूमि)?', clean, re.IGNORECASE)
        if land_m:
            land_num = HindiNumberParser.parse_single_number(land_m.group(1))
            unit_str = land_m.group(2).upper()
            if unit_str in ("बीघा", "BIGHA"):
                unit_str = "BIGHA"
            if land_num is not None:
                candidates.append(
                    CandidateProfileUpdate(
                        field="land_holding",
                        value=land_num,
                        raw_value=land_m.group(0),
                        source_text=land_m.group(0),
                        input_source=input_source,
                        extraction_method=ExtractionMethod.DETERMINISTIC,
                        status=CandidateStatus.EXTRACTED,
                        unit=unit_str,
                        normalization_steps=["LAND_BIGHA_PRESERVED_NO_CONVERSION"],
                    )
                )

        # 10. Family size: "घर में पांच लोग हैं", "परिवार में 4 सदस्य"
        fsize_m = re.search(r'(?:घर|परिवार)\s*में\s*([^\s,।]+)\s*(?:लोग|सदस्य|जन)', clean)
        if fsize_m:
            size_num = HindiNumberParser.parse_single_number(fsize_m.group(1))
            if size_num is not None and 1 <= size_num <= 50:
                candidates.append(
                    CandidateProfileUpdate(
                        field="family_size",
                        value=size_num,
                        raw_value=fsize_m.group(1),
                        source_text=fsize_m.group(0),
                        input_source=input_source,
                        extraction_method=ExtractionMethod.DETERMINISTIC,
                        status=CandidateStatus.EXTRACTED,
                        normalization_steps=["FAMILY_SIZE_PARSED"],
                    )
                )

        # 11. BPL negation or positive assertion
        if re.search(r'(बीपीएल|bpl)', clean, re.IGNORECASE):
            is_neg = BooleanAndStatusParser.detect_negation(clean, concept="बीपीएल") or BooleanAndStatusParser.detect_negation(clean, concept="bpl")
            candidates.append(
                CandidateProfileUpdate(
                    field="bpl_status",
                    value=not is_neg,
                    source_text=clean,
                    input_source=input_source,
                    extraction_method=ExtractionMethod.DETERMINISTIC,
                    status=CandidateStatus.EXTRACTED,
                    normalization_steps=["BPL_STATEMENT_NEGATION_AWARE"],
                )
            )

        # 12. Need text extraction
        need_m = re.search(r'(मुझे\s*[^।!?]+(?:चाहिए|सहायता|मदद|योजना))', clean)
        if need_m:
            need_text = need_m.group(1).strip()

        return (candidates, need_text)
