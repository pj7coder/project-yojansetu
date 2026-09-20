"""
Deterministic citizen explanation and presentation service for JanSetu.
Translates Layer 3 canonical scheme models and Day 14 deterministic eligibility results
into plain, accessible Hindi and English presentation structures without using an LLM.
"""

from datetime import date
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.citizen.schemas import (
    CitizenApplicationGuidance,
    CitizenBenefitItem,
    CitizenDocumentItem,
    CitizenSchemeCard,
    CitizenSchemeDetailResponse,
    CitizenSourceInfo,
)
from app.database.models.document import Document
from app.database.models.scheme import Scheme, SchemeVersion
from app.eligibility.result import ConditionEvaluationResult, EligibilityResult
from app.monitoring.safety import validate_url_safety
from app.questioning.field_metadata import get_field_metadata

logger = logging.getLogger("jansetu.citizen.presentation")


class CitizenExplanationService:
    """
    Deterministic presentation translator for citizen interfaces.
    Transforms raw rules, AST condition results, and canonical schemas into
    vernacular summaries without halluncination or LLM dependency.
    """

    @classmethod
    def explain_condition(cls, cond: ConditionEvaluationResult) -> Tuple[str, str]:
        """
        Translates a single satisfied eligibility condition into plain Hindi and English.
        """
        f = cond.field.lower().strip()
        op = cond.operator.upper().strip()
        val = cond.required_value

        if f == "age":
            if op in ("GTE", "GT"):
                return (
                    f"आयु {val} वर्ष या उससे अधिक की पात्रता शर्त पूर्ण है",
                    f"Age requirement satisfied ({val} years or older)",
                )
            if op in ("LTE", "LT"):
                return (
                    f"आयु {val} वर्ष या उससे कम की पात्रता शर्त पूर्ण है",
                    f"Age requirement satisfied ({val} years or younger)",
                )
            return (
                f"आयु {val} वर्ष की पात्रता शर्त पूर्ण है",
                f"Age requirement satisfied ({val} years)",
            )

        if f == "state":
            return (
                "राजस्थान का मूल निवासी होने की शर्त पूर्ण है",
                "Rajasthan state resident requirement satisfied",
            )

        if f == "district":
            d_val = str(val).capitalize() if val else ""
            return (
                f"{d_val} जिले के निवासी होने की शर्त पूर्ण है",
                f"Resident of district {d_val} requirement satisfied",
            )

        if f == "family_income":
            try:
                num_val = int(val)
                formatted = f"₹{num_val:,}"
            except (ValueError, TypeError):
                formatted = f"₹{val}"
            return (
                f"पारिवारिक वार्षिक आय सीमा ({formatted}) के भीतर है",
                f"Annual family income is within the scheme limit ({formatted})",
            )

        if f == "bpl_status":
            return (
                "बीपीएल (गरीबी रेखा से नीचे) श्रेणी की पात्रता पूर्ण है",
                "Below Poverty Line (BPL) criterion satisfied",
            )

        if f == "farmer_status":
            return (
                "कृषक होने की पात्रता शर्त पूर्ण है",
                "Farmer status criterion satisfied",
            )

        if f in ("disability_status", "disability_percentage"):
            return (
                "दिव्यांगता पात्रता मानदंड पूर्ण है",
                "Disability eligibility criterion satisfied",
            )

        if f == "gender":
            g_hi = "महिला" if str(val).upper() == "FEMALE" else ("पुरुष" if str(val).upper() == "MALE" else str(val))
            return (
                f"{g_hi} वर्ग की पात्रता शर्त पूर्ण है",
                f"Eligible for gender category {val}",
            )

        if f == "rural_urban":
            area_hi = "ग्रामीण" if str(val).upper() == "RURAL" else "शहरी"
            return (
                f"{area_hi} क्षेत्र निवासी होने की शर्त पूर्ण है",
                f"Resident of {str(val).lower()} area requirement satisfied",
            )

        # Clean fallback
        meta = get_field_metadata(f)
        return (
            f"{meta.display_name_hi} की पात्रता शर्त पूर्ण है",
            f"{meta.display_name_en} requirement satisfied",
        )

    @classmethod
    def explain_passed_conditions(
        cls, passed_conditions: List[ConditionEvaluationResult]
    ) -> Tuple[List[str], List[str]]:
        hi_list = []
        en_list = []
        for c in passed_conditions:
            hi_text, en_text = cls.explain_condition(c)
            hi_list.append(hi_text)
            en_list.append(en_text)
        return hi_list, en_list

    @classmethod
    def explain_missing_fields(
        cls, missing_fields: List[str]
    ) -> Tuple[List[str], List[str]]:
        hi_list = []
        en_list = []
        for f in missing_fields:
            meta = get_field_metadata(f)
            hi_list.append(f"{meta.display_name_hi} की जानकारी आवश्यक है")
            en_list.append(f"{meta.display_name_en} information is needed")
        return hi_list, en_list

    @classmethod
    def extract_citizen_benefits(
        cls, canonical: Dict[str, Any]
    ) -> List[CitizenBenefitItem]:
        raw_benefits = canonical.get("benefits", [])
        items: List[CitizenBenefitItem] = []

        for b in raw_benefits:
            b_type = b.get("type", b.get("benefit_type", "CASH")).upper()
            amt = b.get("amount")
            currency = b.get("currency", "INR")
            freq = b.get("frequency")
            desc_en = b.get("description") or b.get("description_en")
            desc_hi = b.get("description_hi")

            # Format human display text
            freq_hi = ""
            freq_en = ""
            if freq:
                f_upper = str(freq).upper()
                if "MONTH" in f_upper:
                    freq_hi = "प्रति माह"
                    freq_en = "per month"
                elif "YEAR" in f_upper or "ANNUAL" in f_upper:
                    freq_hi = "प्रति वर्ष"
                    freq_en = "per year"
                elif "ONE" in f_upper:
                    freq_hi = "एकमुश्त"
                    freq_en = "one-time"

            display_hi = ""
            display_en = ""
            if amt is not None:
                try:
                    amt_num = float(amt)
                    formatted_amt = f"₹{amt_num:,.0f}" if amt_num.is_integer() else f"₹{amt_num:,.2f}"
                except (ValueError, TypeError):
                    formatted_amt = f"₹{amt}"
                display_hi = f"{formatted_amt} {freq_hi}".strip()
                display_en = f"{formatted_amt} {freq_en}".strip()
            elif desc_hi or desc_en:
                display_hi = desc_hi or desc_en
                display_en = desc_en or desc_hi

            items.append(
                CitizenBenefitItem(
                    benefit_type=b_type,
                    amount=float(amt) if amt is not None and str(amt).replace(".", "", 1).isdigit() else None,
                    currency=currency,
                    frequency=freq,
                    description_en=desc_en,
                    description_hi=desc_hi,
                    display_text_en=display_en,
                    display_text_hi=display_hi,
                )
            )

        return items

    @classmethod
    def extract_citizen_documents(
        cls, canonical: Dict[str, Any]
    ) -> List[CitizenDocumentItem]:
        raw_docs = canonical.get("required_documents", [])
        items: List[CitizenDocumentItem] = []

        for d in raw_docs:
            name_en = d.get("document_name") or d.get("document_name_en") or d.get("name", "Required Document")
            name_hi = d.get("document_name_hi") or d.get("name_hi")
            is_mand = d.get("is_mandatory", True)
            desc_en = d.get("description") or d.get("description_en")
            desc_hi = d.get("description_hi")

            items.append(
                CitizenDocumentItem(
                    document_name_en=name_en,
                    document_name_hi=name_hi,
                    is_mandatory=bool(is_mand),
                    description_en=desc_en,
                    description_hi=desc_hi,
                )
            )

        return items

    @classmethod
    def extract_citizen_application(
        cls, canonical: Dict[str, Any]
    ) -> CitizenApplicationGuidance:
        raw_app = canonical.get("application", {})
        channels = raw_app.get("channels", [])
        if not channels:
            # Default known Rajasthan delivery channels
            channels = ["e-Mitra Kiosk", "Rajasthan Single Sign On (SSO)", "Department Office"]

        raw_url = raw_app.get("portal_url")
        safe_url = None
        is_safe = False

        if raw_url:
            is_safe, err = validate_url_safety(str(raw_url).strip())
            if is_safe:
                safe_url = str(raw_url).strip()
            else:
                logger.warning(f"Sanitized unsafe application portal URL: {raw_url} ({err})")

        steps_raw = raw_app.get("steps", [])
        steps_en = []
        steps_hi = []
        for s in steps_raw:
            if isinstance(s, dict):
                steps_en.append(s.get("step_en") or s.get("description", ""))
                steps_hi.append(s.get("step_hi") or s.get("description_hi", ""))
            elif isinstance(s, str):
                steps_en.append(s)
                steps_hi.append(s)

        if not steps_en:
            steps_en = [
                "Gather all required documents (Aadhaar, Jan Aadhaar, etc.).",
                "Visit your nearest e-Mitra kiosk or log in to the Rajasthan SSO portal.",
                "Fill out the scheme application and attach attested copies of documents.",
                "Submit the application and collect your receipt / tracking number.",
            ]
            steps_hi = [
                "सभी आवश्यक दस्तावेज (आधार, जन आधार आदि) एकत्र करें।",
                "अपने नजदीकी ई-मित्र केंद्र पर जाएं या राजस्थान एसएसओ पोर्टल पर लॉग इन करें।",
                "योजना का आवेदन पत्र भरें और दस्तावेजों की प्रति संलग्न करें।",
                "आवेदन जमा करें और पावती / रसीद संख्या प्राप्त करें।",
            ]

        fee = raw_app.get("fee", raw_app.get("fee_inr"))
        fee_val = float(fee) if fee is not None and str(fee).replace(".", "", 1).isdigit() else None

        return CitizenApplicationGuidance(
            channels=channels,
            portal_url=safe_url,
            is_portal_url_safe=is_safe,
            submission_mode=raw_app.get("submission_mode", "ONLINE_AND_OFFLINE"),
            steps_en=steps_en,
            steps_hi=steps_hi,
            fee_inr=fee_val,
        )

    @classmethod
    def extract_citizen_source(
        cls,
        canonical: Dict[str, Any],
        version: Optional[SchemeVersion] = None,
        doc: Optional[Document] = None,
    ) -> CitizenSourceInfo:
        ident = canonical.get("scheme_identity", {})
        dept_en = ident.get("department") or ident.get("department_en")
        dept_hi = ident.get("department_hi")
        notif_ref = ident.get("notification_number") or ident.get("order_number")
        page_ref = None

        if doc:
            if not notif_ref:
                notif_ref = doc.title or doc.original_filename

        if version and version.source_summary and not notif_ref:
            notif_ref = version.source_summary

        return CitizenSourceInfo(
            department_en=dept_en,
            department_hi=dept_hi,
            notification_reference=notif_ref,
            page_reference=page_ref,
            official_url=None,
        )

    @classmethod
    def build_scheme_card(
        cls,
        scheme_id: str,
        scheme_code: str,
        name_en: str,
        name_hi: Optional[str],
        canonical: Dict[str, Any],
        eligibility_status: str,
        passed_conditions: Optional[List[ConditionEvaluationResult]] = None,
        missing_fields: Optional[List[str]] = None,
    ) -> CitizenSchemeCard:
        ident = canonical.get("scheme_identity", {})
        dept_en = ident.get("department") or ident.get("department_en")
        dept_hi = ident.get("department_hi")
        purpose_en = ident.get("description") or ident.get("description_en")
        purpose_hi = ident.get("description_hi")

        benefits = cls.extract_citizen_benefits(canonical)
        primary_b_en = benefits[0].display_text_en if benefits else None
        primary_b_hi = benefits[0].display_text_hi if benefits else None

        why_hi, why_en = cls.explain_passed_conditions(passed_conditions or [])
        miss_hi, miss_en = cls.explain_missing_fields(missing_fields or [])

        return CitizenSchemeCard(
            scheme_id=scheme_id,
            scheme_code=scheme_code,
            name_en=name_en,
            name_hi=name_hi,
            scheme_name=name_en,
            scheme_name_hi=name_hi,
            department_en=dept_en,
            department_hi=dept_hi,
            purpose_en=purpose_en,
            purpose_hi=purpose_hi,
            primary_benefit_en=primary_b_en,
            primary_benefit_hi=primary_b_hi,
            eligibility_status=eligibility_status,
            why_eligible_summary_hi=why_hi,
            why_eligible_summary_en=why_en,
            missing_fields=missing_fields or [],
            missing_fields_display_hi=miss_hi,
            missing_fields_display_en=miss_en,
        )

    @classmethod
    def build_scheme_detail(
        cls,
        scheme: Scheme,
        version: SchemeVersion,
        doc: Optional[Document] = None,
        evaluation_result: Optional[EligibilityResult] = None,
    ) -> CitizenSchemeDetailResponse:
        canonical = version.canonical_data or {}
        ident = canonical.get("scheme_identity", {})

        dept_en = scheme.department.name_en if scheme.department else ident.get("department")
        dept_hi = scheme.department.name_hi if scheme.department else ident.get("department_hi")

        cat_en = scheme.category.name_en if scheme.category else ident.get("category")
        cat_hi = scheme.category.name_hi if scheme.category else ident.get("category_hi")

        purpose_en = scheme.short_description or ident.get("description")
        purpose_hi = ident.get("description_hi")

        passed = evaluation_result.passed_conditions if evaluation_result else []
        why_hi, why_en = cls.explain_passed_conditions(passed)

        benefits = cls.extract_citizen_benefits(canonical)
        documents = cls.extract_citizen_documents(canonical)
        application = cls.extract_citizen_application(canonical)
        source = cls.extract_citizen_source(canonical, version=version, doc=doc)

        important_dates = canonical.get("important_dates", [])

        is_active = version.status in ("ACTIVE", "HUMAN_VERIFIED")

        return CitizenSchemeDetailResponse(
            scheme_id=str(scheme.id),
            scheme_code=scheme.scheme_code,
            name_en=scheme.name_en,
            name_hi=scheme.name_hi,
            version_number=version.version_number,
            version_label=version.version_label,
            status=version.status,
            is_active=is_active,
            effective_date=version.effective_date,
            valid_from=version.valid_from,
            valid_until=version.valid_until,
            department_en=dept_en,
            department_hi=dept_hi,
            category_en=cat_en,
            category_hi=cat_hi,
            purpose_en=purpose_en,
            purpose_hi=purpose_hi,
            why_eligible_hi=why_hi,
            why_eligible_en=why_en,
            eligibility_conditions_hi=why_hi,
            eligibility_conditions_en=why_en,
            benefits=benefits,
            required_documents=documents,
            application=application,
            important_dates=important_dates,
            official_source=source,
        )
