"""
ReAct Multi-Step Welfare Agent Orchestrator for YojanSetu.
Performs explicit, verifiable multi-step reasoning:
Thought -> Tool Call -> Observation -> Thought -> Synthesis.
Sequences retrieval, deterministic eligibility, benefit calculations,
and grounded Gazette citations for multi-step citizen queries.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agent.tools import (
    calculate_scheme_benefits,
    evaluate_citizen_eligibility,
    execute_tool,
    find_nearby_emitra_kiosk,
    get_required_documents_checklist,
    get_tools_schema,
    query_circular_documents_rag,
    search_welfare_schemes,
)

logger = logging.getLogger("yojansetu.agent.orchestrator")


@dataclass
class ReasoningStep:
    """Represents an atomic ReAct thought and tool execution cycle."""
    step_number: int
    thought: str
    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: Dict[str, Any]
    duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "thought": self.thought,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_output": self.tool_output,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class AgentResult:
    """Complete output produced by the Welfare Agent Orchestrator."""
    query: str
    language: str
    answer: str
    reasoning_steps: List[ReasoningStep]
    citations: List[Dict[str, Any]]
    recommended_schemes: List[Dict[str, Any]]
    required_documents: List[Dict[str, Any]]
    emitra_kiosk_info: Optional[Dict[str, Any]]
    profile_extracted: Dict[str, Any]
    total_execution_time_ms: float
    candidate_schemes: List[Dict[str, Any]] = field(default_factory=list)
    confidence_score: float = 1.0
    confidence_level: str = "HIGH"
    follow_up_question: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "language": self.language,
            "answer": self.answer,
            "reasoning_steps": [s.to_dict() for s in self.reasoning_steps],
            "citations": self.citations,
            "recommended_schemes": self.recommended_schemes,
            "candidate_schemes": self.candidate_schemes,
            "required_documents": self.required_documents,
            "emitra_kiosk_info": self.emitra_kiosk_info,
            "profile_extracted": self.profile_extracted,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level,
            "follow_up_question": self.follow_up_question,
            "total_execution_time_ms": round(self.total_execution_time_ms, 2),
        }


class WelfareAgentOrchestrator:
    """
    Intelligent agent orchestrator sequencing tool calling and grounded RAG
    to answer complex, multi-part citizen welfare queries in Rajasthan.
    """

    @classmethod
    def _extract_profile_from_text(cls, text: str, initial_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extracts demographic and economic facts from natural vernacular Hindi or English text.
        Understands colloquial expressions like '68 saal', '3 bigha', '50 hazar', 'kisan', 'widow'.
        """
        profile: Dict[str, Any] = dict(initial_profile or {})
        t = text.lower()

        # Age detection: e.g. "68 saal", "68 years", "68-year-old", "age 68", "68 वर्ष", "68 साल", "72y"
        age_match = re.search(r"(\d{1,2})\s*[-–—]?\s*(?:years?|yrs?|saal|sal|वर्ष|साल|की उम्र|आयु)", t)
        if not age_match:
            age_match = re.search(r"(\d{1,2})\s*(?:-year-old|-yr-old|y/o|yo)", t)
        if not age_match:
            age_match = re.search(r"(?:age|उम्र|आयु)\s*(?:is|of|:)?\s*(\d{1,2})", t)
        if age_match:
            val = int(age_match.group(1))
            if 1 <= val <= 110:
                profile["age"] = val

        # Land Area in Bighas: e.g. "3 bigha", "2.5 बीघा", "5 acre"
        bigha_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:bigha|bighas|बीघा|बीघे)", t)
        if bigha_match:
            profile["land_area_bigha"] = float(bigha_match.group(1))
            profile["occupation"] = "FARMER"

        acre_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:acre|acres|एकड़)", t)
        if acre_match:
            # 1 acre ≈ 2.5 bighas in Rajasthan
            profile["land_area_bigha"] = float(acre_match.group(1)) * 2.5
            profile["occupation"] = "FARMER"

        # Annual Income detection: remove internal commas e.g. "40,000" -> "40000"
        t_nocomma = re.sub(r"(\d+),(\d+)", r"\1\2", t)

        income_lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|लाख)", t_nocomma)
        if income_lakh_match:
            profile["annual_income"] = float(income_lakh_match.group(1)) * 100000

        income_hazar_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hazar|thousand|हजार|हज़ार)", t_nocomma)
        if income_hazar_match:
            profile["annual_income"] = float(income_hazar_match.group(1)) * 1000

        if "annual_income" not in profile:
            direct_income = re.search(r"(?:₹|rs\.?|income|earning|कमाई|आय)\s*[:=]?\s*(\d{4,7})", t_nocomma)
            if not direct_income:
                direct_income = re.search(r"(\d{4,7})\s*(?:per year|/year|वार्षिक|प्रति वर्ष|आय)", t_nocomma)
            if direct_income:
                profile["annual_income"] = float(direct_income.group(1))

        # Gender & Marital Status detection
        if any(w in t for w in ["widow", "विधवा", "एकल नारी", "परित्यक्ता", "divorced", "तलाकशुदा"]):
            profile["gender"] = "FEMALE"
            profile["marital_status"] = "WIDOWED"
        elif any(w in t for w in ["महिला", "female", "woman", "girl", "daughter", "बेटी", "छात्रा", "लड़की", "माताजी", "दादी"]):
            profile["gender"] = "FEMALE"
        elif any(w in t for w in ["पुरुष", "male", "man", "boy", "son", "बेटा", "दादाजी", "किसान भाई"]):
            profile["gender"] = "MALE"

        # Occupation
        if any(w in t for w in ["kisan", "farmer", "खेती", "कृषक", "काश्तकार"]):
            profile["occupation"] = "FARMER"

        # Student status & 12th marks
        if any(w in t for w in ["student", "छात्रा", "छात्र", "पढ़ाई", "कॉलेज", "coaching", "कोचिंग", "12वीं", "scooty", "स्कूटी"]):
            profile["is_student"] = True

        marks_match = re.search(r"(\d{2}(?:\.\d+)?)\s*%", t)
        if marks_match:
            profile["marks_percentage_12"] = float(marks_match.group(1))

        # Disability detection
        if any(w in t for w in ["divyang", "दिव्यांग", "विकलांग", "disability", "disabled", "विशेष योग्यजन"]):
            profile["disability_percentage"] = 40  # statutory benchmark default

        # BPL / Ration / Ujjwala
        if any(w in t for w in ["bpl", "बीपीएल", "ration card", "राशन कार्ड"]):
            profile["is_bpl"] = True
        if any(w in t for w in ["ujjwala", "उज्ज्वला", "gas cylinder", "गैस सिलेंडर"]):
            profile["is_ujjwala_beneficiary"] = True

        # Bilingual Rajasthan District detection
        districts_map = {
            "ajmer": "Ajmer", "अजमेर": "Ajmer",
            "alwar": "Alwar", "अलवर": "Alwar",
            "banswara": "Banswara", "बांसवाड़ा": "Banswara",
            "baran": "Baran", "बारां": "Baran",
            "barmer": "Barmer", "बाड़मेर": "Barmer",
            "bharatpur": "Bharatpur", "भरतपुर": "Bharatpur",
            "bhilwara": "Bhilwara", "भीलवाड़ा": "Bhilwara",
            "bikaner": "Bikaner", "बीकानेर": "Bikaner",
            "bundi": "Bundi", "बूंदी": "Bundi",
            "chittorgarh": "Chittorgarh", "चित्तौड़गढ़": "Chittorgarh",
            "churu": "Churu", "चूरू": "Churu",
            "dausa": "Dausa", "दौसा": "Dausa",
            "dholpur": "Dholpur", "धौलपुर": "Dholpur",
            "dungarpur": "Dungarpur", "डूंगरपुर": "Dungarpur",
            "hanumangarh": "Hanumangarh", "हनुमानगढ़": "Hanumangarh",
            "jaipur": "Jaipur", "जयपुर": "Jaipur",
            "jaisalmer": "Jaisalmer", "जैसलमेर": "Jaisalmer",
            "jalore": "Jalore", "जालौर": "Jalore",
            "jhalawar": "Jhalawar", "झालावाड़": "Jhalawar",
            "jhunjhunu": "Jhunjhunu", "झुंझुनू": "Jhunjhunu",
            "jodhpur": "Jodhpur", "जोधपुर": "Jodhpur",
            "karauli": "Karauli", "करौली": "Karauli",
            "kota": "Kota", "कोटा": "Kota",
            "nagaur": "Nagaur", "नागौर": "Nagaur",
            "pali": "Pali", "पाली": "Pali",
            "pratapgarh": "Pratapgarh", "प्रतापगढ़": "Pratapgarh",
            "rajsamand": "Rajsamand", "राजसमंद": "Rajsamand",
            "sawai madhopur": "Sawai Madhopur", "सवाई माधोपुर": "Sawai Madhopur",
            "sikar": "Sikar", "सीकर": "Sikar",
            "sirohi": "Sirohi", "सिरोही": "Sirohi",
            "sri ganganagar": "Sri Ganganagar", "श्रीगंगानगर": "Sri Ganganagar",
            "tonk": "Tonk", "टोंक": "Tonk",
            "udaipur": "Udaipur", "उदयपुर": "Udaipur",
        }
        for d_key, d_canon in districts_map.items():
            if d_key in t:
                profile["district"] = d_canon
                break

        return profile

    @classmethod
    def _detect_language(cls, text: str, preferred: Optional[str] = None) -> str:
        """Determines if query or user preference is Hindi or English."""
        if preferred in ("hi", "en"):
            return preferred

        # Check for Devanagari Unicode characters (\u0900 - \u097F)
        devanagari_count = sum(1 for c in text if "\u0900" <= c <= "\u097F")
        if devanagari_count > 3:
            return "hi"
        return "en"

    @classmethod
    def process_query(
        cls,
        query: str,
        initial_profile: Optional[Dict[str, Any]] = None,
        language_preference: Optional[str] = None,
    ) -> AgentResult:
        """
        Executes multi-step ReAct orchestration:
        Sequences tool calls based on extracted entities, synthesizes grounded answers,
        and constructs verifiable citations with page numbers.
        """
        start_time = time.perf_counter()
        steps: List[ReasoningStep] = []
        citations: List[Dict[str, Any]] = []
        recommended_schemes: List[Dict[str, Any]] = []
        all_required_docs: List[Dict[str, Any]] = []
        emitra_info: Optional[Dict[str, Any]] = None

        lang = cls._detect_language(query, language_preference)
        is_hi = (lang == "hi")

        # 1. Profile Fact Extraction
        profile = cls._extract_profile_from_text(query, initial_profile)
        logger.info("Agent extracted facts from query: %s", profile)

        step_counter = 1

        # STEP 1: Multi-Step Evaluation of Citizen Eligibility
        thought_1 = (
            f"नागरिक द्वारा उपलब्ध कराए गए जनसांख्यिकीय विवरण (आयु: {profile.get('age', 'अज्ञात')}, आय: ₹{profile.get('annual_income', 'अज्ञात')}) "
            f"के आधार पर राजस्थान सरकारी योजनाओं की पात्रता जांच हेतु 'evaluate_citizen_eligibility' टूल निष्पादित किया जा रहा है।"
            if is_hi else
            f"Evaluating citizen demographic facts (Age: {profile.get('age', 'N/A')}, Income: ₹{profile.get('annual_income', 'N/A')}) "
            f"against Rajasthan scheme rules using 'evaluate_citizen_eligibility'."
        )

        t1_start = time.perf_counter()
        elig_res = evaluate_citizen_eligibility(
            age=profile.get("age"),
            annual_income=profile.get("annual_income"),
            gender=profile.get("gender"),
            caste_category=profile.get("caste_category"),
            land_area_bigha=profile.get("land_area_bigha"),
            marital_status=profile.get("marital_status"),
            is_student=profile.get("is_student"),
            is_bpl=profile.get("is_bpl"),
            disability_percentage=profile.get("disability_percentage"),
            district=profile.get("district"),
        )
        t1_duration = (time.perf_counter() - t1_start) * 1000.0

        steps.append(
            ReasoningStep(
                step_number=step_counter,
                thought=thought_1,
                tool_name="evaluate_citizen_eligibility",
                tool_input={k: v for k, v in profile.items() if v is not None},
                tool_output={
                    "eligible_count": elig_res.get("eligible_count", 0),
                    "matched_schemes": [s.get("name_en") for s in elig_res.get("matched_schemes", [])],
                },
                duration_ms=t1_duration,
            )
        )
        step_counter += 1

        matched = elig_res.get("matched_schemes", [])

        # If no deterministic match found by profile, fallback to search_welfare_schemes tool
        if not matched:
            thought_fallback = (
                f"विशिष्ट जनसांख्यिकीय मैच न मिलने पर 'search_welfare_schemes' टूल द्वारा कीवर्ड खोज की जा रही है।"
                if is_hi else
                f"No strict demographic match found. Executing keyword search over schemes with 'search_welfare_schemes'."
            )
            tf_start = time.perf_counter()
            search_res = search_welfare_schemes(search_query=query, limit=3)
            tf_duration = (time.perf_counter() - tf_start) * 1000.0

            steps.append(
                ReasoningStep(
                    step_number=step_counter,
                    thought=thought_fallback,
                    tool_name="search_welfare_schemes",
                    tool_input={"search_query": query},
                    tool_output=search_res,
                    duration_ms=tf_duration,
                )
            )
            step_counter += 1

            for s in search_res.get("schemes", []):
                matched.append({
                    "scheme_id": s["scheme_id"],
                    "scheme_code": s["name_en"][:20],
                    "name_en": s["name_en"],
                    "name_hi": s.get("name_hi", s["name_en"]),
                    "eligibility_status": "POTENTIAL_MATCH",
                    "passed_conditions": [],
                })

        # STEP 2: Benefit Calculation for Top Matched Scheme
        primary_scheme = matched[0] if matched else None
        primary_code = primary_scheme.get("scheme_code", "RJ-PENSION-VRIDHJAN") if primary_scheme else "RJ-PENSION-VRIDHJAN"

        thought_2 = (
            f"योजना '{primary_scheme.get('name_hi', primary_code) if primary_scheme else primary_code}' के तहत मिलने वाली सटीक मासिक व वार्षिक वित्तीय सहायता "
            f"की गणना 'calculate_scheme_benefits' टूल द्वारा की जा रही है।"
            if is_hi else
            f"Calculating exact financial payouts, pensions, or subsidies for '{primary_code}' using 'calculate_scheme_benefits'."
        )

        t2_start = time.perf_counter()
        benefit_res = calculate_scheme_benefits(
            scheme_code=primary_code,
            age=profile.get("age"),
            annual_income=profile.get("annual_income"),
            land_area_bigha=profile.get("land_area_bigha"),
        )
        t2_duration = (time.perf_counter() - t2_start) * 1000.0

        steps.append(
            ReasoningStep(
                step_number=step_counter,
                thought=thought_2,
                tool_name="calculate_scheme_benefits",
                tool_input={"scheme_code": primary_code, "age": profile.get("age")},
                tool_output=benefit_res,
                duration_ms=t2_duration,
            )
        )
        step_counter += 1

        def _format_benefit_str(b_dict: Dict[str, Any]) -> str:
            if not isinstance(b_dict, dict):
                return str(b_dict) if b_dict else ("डीबीटी वित्तीय सहायता" if is_hi else "Direct DBT Financial Benefit")
            monthly = b_dict.get("monthly_payout_inr")
            annual = b_dict.get("annual_total_inr")
            slab = b_dict.get("slab_applied")
            if monthly:
                return f"₹{monthly:,}/माह ({slab or 'डीबीटी'})" if is_hi else f"₹{monthly:,}/month ({slab or 'Direct DBT'})"
            if annual:
                return f"₹{annual:,}/वर्ष ({slab or 'वार्षिक डीबीटी'})" if is_hi else f"₹{annual:,}/year ({slab or 'Annual DBT'})"
            return str(slab or b_dict.get("benefit_type") or ("डीबीटी वित्तीय सहायता" if is_hi else "Direct DBT Financial Benefit"))

        # Enrich scheme card with benefit details
        if primary_scheme:
            primary_scheme["benefit_summary"] = _format_benefit_str(benefit_res)
            primary_scheme["benefit_details"] = benefit_res
            recommended_schemes.append(primary_scheme)

        for m in matched[1:3]:
            # Calculate benefits for secondary schemes
            sec_code = m.get("scheme_code", "")
            sec_benefit = calculate_scheme_benefits(scheme_code=sec_code, age=profile.get("age"))
            m["benefit_summary"] = _format_benefit_str(sec_benefit)
            m["benefit_details"] = sec_benefit
            recommended_schemes.append(m)

        # STEP 3: Verifiable Grounded RAG Query over Official Gazette Circulars
        rag_query = f"{primary_scheme.get('name_en', '')} eligibility benefits rules circular" if primary_scheme else query
        thought_3 = (
            f"सरकारी अधिसूचना व कानूनी प्रावधानों की आधिकारिक पुष्टि हेतु 'query_circular_documents_rag' द्वारा गजटेड सर्कुलर अंश एवं पृष्ठ संख्या खोजे जा रहे हैं।"
            if is_hi else
            f"Retrieving official Gazetted notifications and page numbers for '{primary_code}' using 'query_circular_documents_rag'."
        )

        t3_start = time.perf_counter()
        rag_res = query_circular_documents_rag(query=rag_query, top_k=2)
        t3_duration = (time.perf_counter() - t3_start) * 1000.0

        citations = rag_res.get("citations", [])

        steps.append(
            ReasoningStep(
                step_number=step_counter,
                thought=thought_3,
                tool_name="query_circular_documents_rag",
                tool_input={"query": rag_query, "top_k": 2},
                tool_output={
                    "total_found": rag_res.get("total_found", 0),
                    "citations": [c.get("citation_tag") for c in citations],
                },
                duration_ms=t3_duration,
            )
        )
        step_counter += 1

        # STEP 4: Mandatory Document Checklist Retrieval
        thought_4 = (
            f"आवेदन हेतु आवश्यक अनिवार्य दस्तावेजों (जैसे जन आधार, आय प्रमाण पत्र) की सूची 'get_required_documents_checklist' टूल से प्राप्त की जा रही है।"
            if is_hi else
            f"Fetching mandatory document checklist and issuance guidelines using 'get_required_documents_checklist'."
        )

        t4_start = time.perf_counter()
        doc_res = get_required_documents_checklist(scheme_code=primary_code)
        t4_duration = (time.perf_counter() - t4_start) * 1000.0

        all_required_docs = doc_res.get("documents", [])

        steps.append(
            ReasoningStep(
                step_number=step_counter,
                thought=thought_4,
                tool_name="get_required_documents_checklist",
                tool_input={"scheme_code": primary_code},
                tool_output={"mandatory_count": doc_res.get("mandatory_count", 0)},
                duration_ms=t4_duration,
            )
        )
        step_counter += 1

        # STEP 5 (Optional): Locate Nearby e-Mitra Kiosk
        district_name = profile.get("district") or "Jaipur"
        thought_5 = (
            f"निकटतम ई-मित्र सेवा केंद्र की जानकारी 'find_nearby_emitra_kiosk' टूल द्वारा प्राप्त की जा रही है।"
            if is_hi else
            f"Locating nearest frontline e-Mitra service kiosk for district '{district_name}' using 'find_nearby_emitra_kiosk'."
        )

        t5_start = time.perf_counter()
        emitra_info = find_nearby_emitra_kiosk(district=district_name)
        t5_duration = (time.perf_counter() - t5_start) * 1000.0

        steps.append(
            ReasoningStep(
                step_number=step_counter,
                thought=thought_5,
                tool_name="find_nearby_emitra_kiosk",
                tool_input={"district": district_name},
                tool_output={"helpline": emitra_info.get("toll_free_helpline")},
                duration_ms=t5_duration,
            )
        )

        # Confidence & Decisive Criteria Calculation
        has_age = profile.get("age") is not None
        has_income = profile.get("annual_income") is not None or profile.get("is_bpl")
        has_land = profile.get("land_area_bigha") is not None
        is_widow = bool(profile.get("is_widow") or profile.get("marital_status") == "WIDOWED")
        is_farmer = bool(profile.get("occupation") == "FARMER" or has_land)
        is_pension = "pension" in query.lower() or "पेंशन" in query or is_widow
        has_occupation = profile.get("occupation") is not None or is_widow or (has_age and profile.get("age", 0) >= 60)

        confidence_score = 0.95
        follow_up_question = None
        candidate_schemes: List[Dict[str, Any]] = []

        # RULE 1: If neither age nor profession is known, DO NOT suggest schemes!
        # First ask who the citizen is, what their age and profession is!
        if not has_age and not has_occupation:
            confidence_score = 0.15
            follow_up_question = {
                "question_id": "ask_identity_and_role",
                "field": "occupation",
                "question_hi": "नमस्ते! मैं आपका योजनसेतु AI सहायक हूँ। आपके लिए 100% सही और सबसे अधिक लाभदायक सरकारी योजनाएं खोजने के लिए, मुझे पहले आपके बारे में कुछ बुनियादी बातें जाननी होंगी। कृपया बताएं: आपकी उम्र (आयु) क्या है और आप क्या काम करते हैं? (जैसे: किसान, छात्र, वरिष्ठ नागरिक, छोटा व्यापारी, दैनिक श्रमिक, या गृहिणी?)",
                "question_en": "Hello! I am your YojanSetu AI Assistant. To find the exact welfare schemes tailored for you, I need to know a little about you first. Please tell me: What is your current age and what is your primary profession or role? (e.g. Farmer, Student, Senior Citizen, Small Business, Laborer, or Homemaker?)",
                "rationale_hi": "सरकारी योजनाएं नागरिक की उम्र और व्यवसाय के आधार पर निर्धारित होती हैं।",
                "rationale_en": "Government schemes are strictly based on citizen age and occupation.",
                "options": [
                    {"label_hi": "🌾 किसान / कृषक", "label_en": "Farmer", "value": {"occupation": "FARMER"}},
                    {"label_hi": "🎓 विद्यार्थी / छात्र", "label_en": "Student", "value": {"occupation": "STUDENT"}},
                    {"label_hi": "👴 वरिष्ठ नागरिक (60+ वर्ष)", "label_en": "Senior Citizen (60+)", "value": {"age": 60}},
                    {"label_hi": "💼 छोटा व्यापारी / स्वरोजगार", "label_en": "Self-Employed / Shop", "value": {"occupation": "SELF_EMPLOYED"}},
                    {"label_hi": "👩 गृहिणी / महिला", "label_en": "Homemaker / Women", "value": {"gender": "FEMALE", "occupation": "HOMEMAKER"}},
                    {"label_hi": "🔨 दैनिक श्रमिक / मजदूर", "label_en": "Daily Wage Worker", "value": {"occupation": "LABORER"}},
                ],
            }
        elif has_occupation and not has_age:
            confidence_score = 0.35
            follow_up_question = {
                "question_id": "ask_age",
                "field": "age",
                "question_hi": f"{profile.get('occupation', 'नागरिक')} के रूप में आपकी सटीक पात्रता और आयु-सीमा जांचने के लिए: कृपया अपनी वर्तमान आयु (उम्र) बताएं:",
                "question_en": f"To determine your statutory eligibility as {profile.get('occupation', 'citizen')}: please state your current age:",
                "rationale_hi": "प्रत्येक कल्याणकारी योजना में न्यूनतम व अधिकतम आयु सीमा अनिवार्य होती है।",
                "rationale_en": "Statutory age limits are required for all government benefits.",
                "options": [
                    {"label_hi": "18 से 35 वर्ष", "label_en": "18 - 35 Years", "value": {"age": 25}},
                    {"label_hi": "36 से 55 वर्ष", "label_en": "36 - 55 Years", "value": {"age": 45}},
                    {"label_hi": "56 से 70 वर्ष", "label_en": "56 - 70 Years", "value": {"age": 62}},
                    {"label_hi": "70 वर्ष से अधिक", "label_en": "70+ Years", "value": {"age": 75}},
                ],
            }
        elif has_age and not has_occupation:
            confidence_score = 0.35
            follow_up_question = {
                "question_id": "ask_occupation",
                "field": "occupation",
                "question_hi": "कृपया बताएं: आपका मुख्य कार्य या पेशा क्या है? (जैसे: किसान, छात्र, वरिष्ठ नागरिक, छोटा व्यापारी, दैनिक श्रमिक, या गृहिणी?)",
                "question_en": "Please tell me your primary profession or role: (e.g. Farmer, Student, Senior Citizen, Small Business, Laborer, or Homemaker)",
                "rationale_hi": "व्यवसाय अनुसार राजस्थान सरकार की विशिष्ट योजनाएं लागू होती हैं।",
                "rationale_en": "Schemes are tailored to specific occupational sectors.",
                "options": [
                    {"label_hi": "🌾 किसान / कृषक", "label_en": "Farmer", "value": {"occupation": "FARMER"}},
                    {"label_hi": "🎓 विद्यार्थी / छात्र", "label_en": "Student", "value": {"occupation": "STUDENT"}},
                    {"label_hi": "👴 वरिष्ठ नागरिक पेंशन", "label_en": "Senior Citizen", "value": {"occupation": "RETIRED"}},
                    {"label_hi": "💼 छोटा व्यापारी / स्वरोजगार", "label_en": "Self-Employed", "value": {"occupation": "SELF_EMPLOYED"}},
                    {"label_hi": "👩 गृहिणी / महिला", "label_en": "Homemaker", "value": {"gender": "FEMALE", "occupation": "HOMEMAKER"}},
                    {"label_hi": "🔨 दैनिक श्रमिक / मजदूर", "label_en": "Daily Wage Worker", "value": {"occupation": "LABORER"}},
                ],
            }
        elif is_pension and not has_income:
            confidence_score = 0.65
            follow_up_question = {
                "question_id": "ask_income_for_pension",
                "field": "income",
                "question_hi": "आपकी आयु पेंशन के अनुकूल है। पेंशन नियम 2024 के अनुसार पारिवारिक आय ₹48,000 वार्षिक से कम या बीपीएल कार्ड होना आवश्यक है। क्या आपकी आय इस सीमा में है?",
                "question_en": "Your age qualifies for pension. According to rules, annual family income must be below ₹48,000 or you must hold a BPL card. Does your income meet this?",
                "rationale_hi": "पेंशन नियमों के तहत अधिकतम आय सीमा ₹48,000 वार्षिक निर्धारित है।",
                "rationale_en": "Income ceiling of ₹48,000/yr is legally required for non-BPL applicants.",
                "options": [
                    {"label_hi": "हाँ, आय ₹48,000 से कम है", "label_en": "Yes, income < ₹48,000", "value": {"income": 40000}},
                    {"label_hi": "हाँ, मेरे पास BPL / अंत्योदय कार्ड है", "label_en": "Yes, I hold BPL/AAY Card", "value": {"rationCard": "BPL", "income": 36000}},
                    {"label_hi": "नहीं, आय ₹48,000 से अधिक है", "label_en": "No, income > ₹48,000", "value": {"income": 100000}},
                ],
            }
        elif is_farmer and not has_land:
            confidence_score = 0.55
            follow_up_question = {
                "question_id": "ask_farmer_land",
                "field": "landBigha",
                "question_hi": "राजस्थान किसान अतिरिक्त सहायता (₹2,000 टॉप-अप) व अनुदान हेतु: आपके पास कितने बीघा कृषि भूमि है?",
                "question_en": "For Rajasthan Farmer Subsidy and Top-Up: How many bighas of agricultural land do you own?",
                "rationale_hi": "भूमि के रकबे के आधार पर लघु/सीमांत किसान की आधिकारिक पात्रता तय होती है।",
                "rationale_en": "Landholding size determines small/marginal farmer eligibility status.",
                "options": [
                    {"label_hi": "सीमांत किसान (2.5 बीघा से कम)", "label_en": "Marginal (< 2.5 Bigha)", "value": {"landBigha": 2, "occupation": "FARMER"}},
                    {"label_hi": "लघु किसान (2.5 से 5 बीघा)", "label_en": "Small (2.5 - 5 Bigha)", "value": {"landBigha": 4, "occupation": "FARMER"}},
                    {"label_hi": "मध्यम / बड़ा किसान (> 5 बीघा)", "label_en": "Large (> 5 Bigha)", "value": {"landBigha": 8, "occupation": "FARMER"}},
                ],
            }

        if confidence_score < 0.85:
            candidate_schemes = []
            recommended_schemes = []

        confidence_level = "HIGH" if confidence_score >= 0.80 else "MEDIUM" if confidence_score >= 0.50 else "LOW"

        # FINAL SYNTHESIS: Construct Traceable Vernacular Response
        answer_text = cls._synthesize_answer(
            is_hi=is_hi,
            profile=profile,
            recommended_schemes=recommended_schemes,
            primary_benefit=benefit_res,
            citations=citations,
            documents=all_required_docs,
            emitra_info=emitra_info,
            follow_up_question=follow_up_question,
            confidence_score=confidence_score,
        )

        total_time_ms = (time.perf_counter() - start_time) * 1000.0

        return AgentResult(
            query=query,
            language="hi" if is_hi else "en",
            answer=answer_text,
            reasoning_steps=steps,
            citations=citations,
            recommended_schemes=recommended_schemes,
            candidate_schemes=candidate_schemes,
            required_documents=all_required_docs,
            emitra_kiosk_info=emitra_info,
            profile_extracted=profile,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            follow_up_question=follow_up_question,
            total_execution_time_ms=total_time_ms,
        )

    @classmethod
    def _synthesize_answer(
        cls,
        is_hi: bool,
        profile: Dict[str, Any],
        recommended_schemes: List[Dict[str, Any]],
        primary_benefit: Dict[str, Any],
        citations: List[Dict[str, Any]],
        documents: List[Dict[str, Any]],
        emitra_info: Optional[Dict[str, Any]],
        follow_up_question: Optional[Dict[str, Any]] = None,
        confidence_score: float = 1.0,
    ) -> str:
        """Constructs an authoritative, respectful, traceable bilingual response."""
        conf_pct = int(confidence_score * 100)

        if is_hi:
            lines = []

            if follow_up_question and confidence_score < 0.80:
                q_text = follow_up_question.get("question_hi", "")
                return q_text or f"⏳ पात्रता सत्यापन जारी है ({conf_pct}% विश्वास)। सटीक योजना बताने के लिए एक जानकारी और चाहिए।"

            lines.append("नमस्ते! आपके विवरण के आधार पर पात्रता विश्लेषण:")

            if recommended_schemes:
                primary = recommended_schemes[0]
                lines.append(f"\n🎯 **सत्यापित पात्र योजना ({conf_pct}% पूर्ण विश्वास)**: **{primary.get('name_hi', primary.get('name_en'))}**")

                monthly = primary_benefit.get("monthly_payout_inr", 0)
                annual = primary_benefit.get("annual_total_inr", 0)
                slab = primary_benefit.get("slab_applied", "")

                if monthly > 0:
                    lines.append(f"💰 **मासिक वित्तीय लाभ**: ₹{monthly:,} प्रति माह (वार्षिक कुल: ₹{annual:,}) — *{slab}*")
                else:
                    lines.append(f"💰 **स्वीकृत सहायता**: ₹{annual:,} — *{slab}*")

                lines.append(f"💳 **भुगतान माध्यम**: {primary_benefit.get('payment_channel', 'जन आधार बैंक खाता')}")

                # Citations
                if citations:
                    c = citations[0]
                    lines.append(f"\n📜 **सरकारी कानूनी आधार**: {c.get('citation_tag')}")
                    lines.append(f"> \"{c.get('text', '')[:200]}...\"")

                # Required Documents
                lines.append("\n📋 **आवश्यक दस्तावेज**:")
                for d in documents[:4]:
                    lines.append(f"• **{d.get('document_name_hi', d.get('document_name'))}** ({'अनिवार्य' if d.get('is_mandatory') else 'वैकल्पिक'}) — {d.get('how_to_obtain')}")

                # Next Steps & e-Mitra
                if emitra_info:
                    lines.append(f"\n🏛️ **आवेदन प्रक्रिया**: आप निकटतम ई-मित्र केंद्र ({emitra_info.get('district')} ज़िला) पर जन आधार कार्ड के साथ उपस्थित होकर आवेदन कर सकते हैं।")
                    lines.append(f"📞 सहायता हेतु राजस्थान संपर्क हेल्पलाइन: **{emitra_info.get('toll_free_helpline', '181')}**")
            else:
                lines.append("\nआपके द्वारा दिए गए विवरण के आधार पर वर्तमान में कोई सीधी योजना मेल नहीं खाती। कृपया अपनी आयु अथवा वार्षिक आय स्पष्ट करें ताकि हम सटीक योजना बता सकें।")

            return "\n".join(lines)
        else:
            lines = []

            if follow_up_question and confidence_score < 0.80:
                q_text = follow_up_question.get("question_en", "")
                return q_text or f"⏳ Eligibility verification in progress ({conf_pct}% confidence). One more detail needed to find your best scheme."

            lines.append("Based on your profile, here is your verified eligibility analysis:")

            if recommended_schemes:
                primary = recommended_schemes[0]
                lines.append(f"\n🎯 **Statutory Verified Scheme ({conf_pct}% Confidence)**: **{primary.get('name_en')}**")

                monthly = primary_benefit.get("monthly_payout_inr", 0)
                annual = primary_benefit.get("annual_total_inr", 0)
                slab = primary_benefit.get("slab_applied", "")

                if monthly > 0:
                    lines.append(f"💰 **Monthly Assistance**: ₹{monthly:,}/month (Annual Total: ₹{annual:,}) — *{slab}*")
                else:
                    lines.append(f"💰 **Benefit Cover**: ₹{annual:,} — *{slab}*")

                lines.append(f"💳 **Disbursement Channel**: {primary_benefit.get('payment_channel', 'Direct Bank Transfer via Jan Aadhaar')}")

                # Citations
                if citations:
                    c = citations[0]
                    lines.append(f"\n📜 **Official Legal Grounding**: {c.get('citation_tag')}")
                    lines.append(f"> \"{c.get('text', '')[:220]}...\"")

                # Required Documents
                lines.append("\n📋 **Required Documents**:")
                for d in documents[:4]:
                    lines.append(f"• **{d.get('document_name')}** ({'Mandatory' if d.get('is_mandatory') else 'Optional'}) — *{d.get('how_to_obtain')}*")

                # e-Mitra
                if emitra_info:
                    lines.append(f"\n🏛️ **How to Apply**: Visit your nearest e-Mitra Kiosk in {emitra_info.get('district')} or apply online via sso.rajasthan.gov.in.")
                    lines.append(f"📞 Rajasthan Citizen CM Helpline: **{emitra_info.get('toll_free_helpline', '181')}**")
            else:
                lines.append("\nNo exact scheme match found for the inputs. Please provide your age, annual income, or land holding to verify eligibility.")

            return "\n".join(lines)

