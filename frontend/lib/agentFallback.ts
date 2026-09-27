/**
 * YojanSetu Conversational Welfare Agent - Knowledge Graph Edition
 *
 * Knowledge Graph Dimensions:
 *   WHO:      age, gender, occupation/role, marital status
 *   WHAT:     income, ration card, social category (SC/ST/OBC/EWS)
 *   WHERE:    district, residence (rural/urban)
 *   SPECIAL:  disability%, widow status, land holding, student class/level
 */

import {
  AgentQueryResponse,
  AgentStructuredData,
  RecommendedScheme,
  RequiredDocument,
  SchemeCitation,
  ToolExecutionStep,
  EmitraKioskInfo,
  FollowUpQuestion,
} from "@/types/agent";
import { extractDemographicsFromText } from "./extractDemographics";

export type PrimaryIntent =
  | "OLD_AGE_PENSION"
  | "WIDOW_PENSION"
  | "GENERAL_PENSION"
  | "FARMER_SCHEME"
  | "DISABILITY_PENSION"
  | "STUDENT_SCHOLARSHIP"
  | "HEALTH_INSURANCE"
  | "SELF_EMPLOYMENT_LOAN"
  | "HOUSING_SCHEME"
  | "GAS_RATION"
  | "LABORER_SCHEME"
  | "WOMEN_SCHEME"
  | "GREETING"
  | "GENERAL_DISCOVERY";

interface DecisiveParams {
  age: number | null;
  gender: "MALE" | "FEMALE" | "OTHER" | null;
  income: number | null;
  occupation: string | null;
  residence: "RURAL" | "URBAN" | null;
  category: string | null;
  district: string;
  rationCard: string | null;
  isWidow: boolean;
  isDisabled: boolean;
  disabilityPercent: number;
  landBigha: number | null;
  isBpl: boolean;
  hasJanAadhaar: boolean;
}

export function executeFallbackAgent(
  query: string,
  context: Record<string, any> = {},
  language: string = "hi",
  history: any[] = []
): AgentQueryResponse {
  const startTime = Date.now();
  const rawQ = (query || "").trim();
  const lowerQ = rawQ.toLowerCase();
  const isHi = language === "hi" || (!language.includes("en") && /[\u0900-\u097F]/.test(rawQ));

  const extractedFromQuery = extractDemographicsFromText(rawQ);
  const facts: Record<string, any> = { ...context, ...extractedFromQuery };

  parseHistoryAnswers(rawQ, lowerQ, facts, history);

  const age = facts.age !== undefined && facts.age !== null ? Number(facts.age) : null;
  const gender = facts.gender || null;
  const income = facts.income !== undefined && facts.income !== null ? Number(facts.income)
    : facts.annual_income !== undefined && facts.annual_income !== null ? Number(facts.annual_income) : null;
  const occupation = facts.occupation || null;
  const residence = facts.residence || null;
  const category = facts.category || facts.social_category || null;
  const district = facts.district || "Jaipur";
  const rationCard = facts.rationCard || facts.ration_card || null;
  const isWidow = facts.isWidow === true || facts.is_widow === true || facts.maritalStatus === "WIDOW"
    || /widow|विधवा|एकल\s*नारी|पति\s*की\s*मृत्यु|husband\s*died/i.test(lowerQ);
  const isDisabled = facts.isDisabled === true || facts.is_disabled === true
    || /दिव्यांग|विकलांग|अपंग|अंधा|बहरा|disabled|handicap|specially.?abled/i.test(lowerQ);
  const disabilityPercent = facts.disabilityPercent || facts.disability_percent || (isDisabled ? 50 : 0);
  const landBigha = facts.landBigha !== undefined && facts.landBigha !== null ? Number(facts.landBigha)
    : facts.land_area_bigha !== undefined && facts.land_area_bigha !== null ? Number(facts.land_area_bigha) : null;
  const isBpl = rationCard === "BPL" || rationCard === "AAY" || rationCard === "STATE_BPL"
    || facts.is_bpl === true || /bpl|बीपीएल|अंत्योदय|below\s*poverty/i.test(lowerQ);
  const hasJanAadhaar = facts.hasJanAadhaar !== false;

  const primaryIntent = detectIntent(rawQ, lowerQ, facts, history, { age, gender, income, occupation, isWidow, isDisabled, landBigha, isBpl });

  const evalResult = knowledgeGraphDecide({
    intent: primaryIntent,
    p: { age, gender, income, occupation, residence, category, district, rationCard, isWidow, isDisabled, disabilityPercent, landBigha, isBpl, hasJanAadhaar },
    isHi, rawQ, lowerQ, history, facts,
  });

  const steps: ToolExecutionStep[] = [
    {
      step: 1,
      thought: isHi
        ? `Intent: '${primaryIntent}'. उम्र=${age ?? "?"}, व्यवसाय=${occupation ?? "?"}, जिला=${district}, श्रेणी=${category ?? "?"}`
        : `Intent: '${primaryIntent}'. age=${age ?? "?"}, occ=${occupation ?? "?"}, dist=${district}, cat=${category ?? "?"}`,
      tool_name: "knowledge_graph_profile",
      tool_args: { query: rawQ },
      tool_result: { intent: primaryIntent, score: evalResult.confidenceScore },
      duration_ms: 4,
    },
    {
      step: 2,
      thought: isHi
        ? `विश्वास: ${Math.round(evalResult.confidenceScore * 100)}% — ${evalResult.confidenceScore >= 0.80 ? "पात्रता सत्यापित" : "जानकारी अधूरी"}`
        : `Confidence: ${Math.round(evalResult.confidenceScore * 100)}% — ${evalResult.confidenceScore >= 0.80 ? "Verified" : "Gathering info"}`,
      tool_name: "eligibility_gate",
      tool_args: { missing: evalResult.missingFields },
      tool_result: { status: evalResult.confidenceScore >= 0.80 ? "VERIFIED" : "GATHERING" },
      duration_ms: 6,
    },
  ];

  const kioskInfo: EmitraKioskInfo = {
    district,
    tehsil: "मुख्य तहसील / Main Tehsil",
    toll_free_helpline: "181 (Rajasthan Sampark)",
    emitra_support: "emitra.rajasthan.gov.in",
    working_hours: "9:00 AM - 6:00 PM (Mon-Sat)",
    service_kiosks: [{
      kiosk_name: `${district} ई-मित्र केंद्र`,
      location: `तहसील परिसर, ${district}`,
      services: ["Jan Aadhaar", "Pension", "Scholarship", "Farmer Schemes"],
      govt_fee: "Rs. 0-25",
    }],
    citizen_tip: isHi
      ? "ई-मित्र जाते समय जन आधार, आधार कार्ड और बैंक पासबुक साथ लाएं।"
      : "Carry Jan Aadhaar, Aadhaar card, and bank passbook to e-Mitra.",
  };

  return {
    final_answer: evalResult.conversationalText,
    language: isHi ? "hi" : "en",
    steps,
    structured_data: {
      citations: evalResult.citations,
      recommended_schemes: evalResult.recommendedSchemes,
      candidate_schemes: evalResult.candidateSchemes,
      required_documents: evalResult.requiredDocs,
      emitra_kiosk_info: kioskInfo,
      profile_extracted: facts,
      confidence_score: evalResult.confidenceScore,
      confidence_level: evalResult.confidenceLevel,
      confidence_reasons: evalResult.verifiedCriteria,
      follow_up_question: evalResult.followUpQuestion,
    },
    execution_time_ms: Date.now() - startTime,
  };
}

// ============================================================================
// HISTORY ANSWER PARSER
// ============================================================================
function parseHistoryAnswers(rawQ: string, lowerQ: string, facts: Record<string, any>, history: any[]) {
  if (!history || history.length === 0) return;

  // Direct option format parsing: e.g. "45 वर्ष किसान", "2 बीघा ज़मीन है", etc.
  if (/(\d{1,2})\s*वर्ष\s*(किसान|farmer)/i.test(lowerQ)) {
    const m = lowerQ.match(/(\d{1,2})\s*वर्ष/);
    if (m) facts.age = parseInt(m[1], 10);
    facts.occupation = "FARMER";
  }
  if (/(\d{1,2})\s*वर्ष\s*(बुजुर्ग|senior|वरिष्ठ)/i.test(lowerQ)) {
    const m = lowerQ.match(/(\d{1,2})\s*वर्ष/);
    if (m) facts.age = parseInt(m[1], 10);
    facts.occupation = "RETIRED";
  }
  if (/(\d{1,2})\s*वर्ष\s*(विद्यार्थी|छात्र|student)/i.test(lowerQ)) {
    const m = lowerQ.match(/(\d{1,2})\s*वर्ष/);
    if (m) facts.age = parseInt(m[1], 10);
    facts.occupation = "STUDENT";
    facts.isStudent = true;
  }
  if (/(\d{1,2})\s*वर्ष\s*(गृहिणी|महिला|homemaker)/i.test(lowerQ)) {
    const m = lowerQ.match(/(\d{1,2})\s*वर्ष/);
    if (m) facts.age = parseInt(m[1], 10);
    facts.gender = "FEMALE";
    facts.occupation = "HOMEMAKER";
  }
  if (/(\d{1,2})\s*वर्ष\s*(श्रमिक|मजदूर|worker)/i.test(lowerQ)) {
    const m = lowerQ.match(/(\d{1,2})\s*वर्ष/);
    if (m) facts.age = parseInt(m[1], 10);
    facts.occupation = "LABORER";
  }
  if (/(\d{1,2})\s*वर्ष\s*(स्वरोजगार|दुकान|व्यापारी|business)/i.test(lowerQ)) {
    const m = lowerQ.match(/(\d{1,2})\s*वर्ष/);
    if (m) facts.age = parseInt(m[1], 10);
    facts.occupation = "SELF_EMPLOYED";
  }

  // Children detection for widows and families
  if (/बच्चे\s*हैं|बच्चा\s*है|kids|children/i.test(lowerQ)) {
    facts.hasMinorChildren = true;
  }

  for (let i = history.length - 1; i >= 0; i--) {
    const msg = history[i];
    if (msg.sender !== "assistant" || !msg.followUpQuestion) continue;
    const qId = msg.followUpQuestion.question_id || "";
    const field = msg.followUpQuestion.field || "";

    if ((field === "age" || qId.includes("age")) && !facts.age) {
      const m = rawQ.match(/\b(\d{1,2})\b/);
      if (m) { const v = parseInt(m[1], 10); if (v >= 5 && v <= 100) facts.age = v; }
    }
    if ((field === "landBigha" || qId.includes("land")) && facts.landBigha === undefined) {
      if (/भूमिहीन|landless|no\s*land|zero|शून्य|नहीं\s*है/i.test(lowerQ)) { facts.landBigha = 0; }
      else { const m = rawQ.match(/(\d+(?:\.\d+)?)/); if (m) { facts.landBigha = parseFloat(m[1]); if (!facts.occupation) facts.occupation = "FARMER"; } }
    }
    if ((field === "income" || qId.includes("income") || qId.includes("bpl")) && !facts.income) {
      if (/हाँ|yes|bpl|बीपीएल|कम\s*है|हूँ|गरीब|poor|below/i.test(lowerQ)) { facts.income = 36000; facts.isBpl = true; }
      else if (/नहीं|no|ज्यादा|अधिक|more|above/i.test(lowerQ)) { facts.income = 90000; facts.isBpl = false; }
      else { const m = rawQ.match(/(\d[\d,]*)/); if (m) { let v = parseInt(m[1].replace(/,/g, ""), 10); if (/हजार|thousand|k\b/i.test(lowerQ) && v < 1000) v *= 1000; if (v > 0 && v < 10000000) facts.income = v; } }
    }
    if ((field === "category" || qId.includes("category")) && !facts.category) {
      if (/\bsc\b|अनुसूचित\s*जाति|scheduled\s*caste/i.test(lowerQ)) facts.category = "SC";
      else if (/\bst\b|अनुसूचित\s*जनजाति|tribal|आदिवासी/i.test(lowerQ)) facts.category = "ST";
      else if (/\bobc\b|अन्य\s*पिछड़ा|other\s*backward/i.test(lowerQ)) facts.category = "OBC";
      else if (/\bews\b|economically\s*weaker/i.test(lowerQ)) facts.category = "EWS";
      else if (/general|सामान्य|open/i.test(lowerQ)) facts.category = "GENERAL";
    }
    if ((field === "gender" || qId.includes("gender")) && !facts.gender) {
      if (/महिला|woman|female|lady|औरत|girl/i.test(lowerQ)) facts.gender = "FEMALE";
      else if (/पुरुष|male|man|boy/i.test(lowerQ)) facts.gender = "MALE";
    }
    if ((field === "residence" || qId.includes("residence")) && !facts.residence) {
      if (/गाँव|ग्रामीण|rural|village/i.test(lowerQ)) facts.residence = "RURAL";
      else if (/शहर|urban|city|नगर/i.test(lowerQ)) facts.residence = "URBAN";
    }
    if ((field === "disabilityPercent" || qId.includes("disability")) && !facts.disabilityPercent) {
      const m = rawQ.match(/(\d+)\s*%/);
      if (m) facts.disabilityPercent = parseInt(m[1], 10);
      else if (/80|गंभीर/i.test(lowerQ)) facts.disabilityPercent = 80;
      else if (/50|40|मध्यम/i.test(lowerQ)) facts.disabilityPercent = 50;
      facts.isDisabled = true;
    }
    if (qId.includes("widow") && !facts.isWidow) { if (/हाँ|yes|हूँ|विधवा/i.test(lowerQ)) facts.isWidow = true; }
    break;
  }
}

// ============================================================================
// INTENT DETECTOR
// ============================================================================
function detectIntent(rawQ: string, lowerQ: string, facts: Record<string, any>, history: any[],
  resolved: { age: number|null, gender: string|null, income: number|null, occupation: string|null, isWidow: boolean, isDisabled: boolean, landBigha: number|null, isBpl: boolean }
): PrimaryIntent {
  if (/^(hello|hi|hey|namaste|नमस्ते|प्रणाम|राम\s*राम|helo|नमस)[\s!.,]*$/i.test(rawQ.trim())) return "GREETING";
  if (resolved.isWidow || /विधवा|एकल\s*नारी|पति\s*(मर|गए|की\s*मृत्यु)|widow|husband\s*died/i.test(lowerQ)) return "WIDOW_PENSION";
  if (resolved.isDisabled || /दिव्यांग|विकलांग|अपंग|अंधा|बहरा|disabled|handicap/i.test(lowerQ)) return "DISABILITY_PENSION";
  if (/वृद्धा?\s*पेंशन|वृद्धजन|old\s*age\s*pension|senior\s*pension/i.test(lowerQ)) return "OLD_AGE_PENSION";
  if (/किसान\s*सम्मान|pm\s*kisan|tarbandi|सोलर\s*पंप/i.test(lowerQ)) return "FARMER_SCHEME";
  if (/अनुप्रति|scholarship|छात्रवृत्ति|post\s*matric|coaching/i.test(lowerQ)) return "STUDENT_SCHOLARSHIP";
  if (/आयुष्मान|chiranjeevi|चिरंजीवी|health\s*insurance|स्वास्थ्य\s*बीमा/i.test(lowerQ)) return "HEALTH_INSURANCE";
  if (/pm\s*awas|इंदिरा\s*आवास|housing\s*scheme|आवास\s*योजना/i.test(lowerQ)) return "HOUSING_SCHEME";
  if (/उज्ज्वला|गैस\s*सिलेंडर|ujjwala|ration\s*card/i.test(lowerQ)) return "GAS_RATION";
  if (/mudra|मुद्रा|विश्वकर्मा|vishwakarma|self\s*employ|स्वरोजगार/i.test(lowerQ)) return "SELF_EMPLOYMENT_LOAN";
  if (/shramik|श्रमिक|labour\s*card|मजदूर\s*योजना/i.test(lowerQ)) return "LABORER_SCHEME";
  if (/महिला\s*योजना|लाडो|ladli|beti|बेटी|mahila/i.test(lowerQ)) return "WOMEN_SCHEME";
  if (resolved.occupation === "FARMER" || resolved.landBigha !== null) return "FARMER_SCHEME";
  if (resolved.occupation === "STUDENT" || facts.isStudent) return "STUDENT_SCHOLARSHIP";
  if (resolved.occupation === "LABORER") return "LABORER_SCHEME";
  if (resolved.occupation === "SELF_EMPLOYED") return "SELF_EMPLOYMENT_LOAN";
  if (resolved.occupation === "HOMEMAKER" || (resolved.gender === "FEMALE" && !resolved.occupation)) return "WOMEN_SCHEME";
  if (resolved.occupation === "RETIRED" || (resolved.age !== null && resolved.age >= 55)) return "OLD_AGE_PENSION";
  if (/पेंशन|pension/i.test(lowerQ)) return resolved.age && resolved.age >= 55 ? "OLD_AGE_PENSION" : "GENERAL_PENSION";
  if (/किसान|कृषक|खेती|farmer|kisan|बीघा/i.test(lowerQ)) return "FARMER_SCHEME";
  if (/छात्र|विद्यार्थी|student|पढ़ाई|school|college/i.test(lowerQ)) return "STUDENT_SCHOLARSHIP";
  if (/अस्पताल|hospital|इलाज|medical|health/i.test(lowerQ)) return "HEALTH_INSURANCE";
  if (/मकान|घर|house|आवास/i.test(lowerQ)) return "HOUSING_SCHEME";
  if (/दुकान|व्यापार|loan|ऋण|रोजगार/i.test(lowerQ)) return "SELF_EMPLOYMENT_LOAN";
  if (/मजदूर|मजदूरी|labor|श्रमिक|daily\s*wage/i.test(lowerQ)) return "LABORER_SCHEME";
  if (history?.length > 0) {
    for (let i = history.length - 1; i >= 0; i--) {
      const m = history[i];
      if (m.sender === "assistant" && m.followUpQuestion) {
        const qid = (m.followUpQuestion.question_id || "").toLowerCase();
        if (qid.includes("farmer") || qid.includes("land")) return "FARMER_SCHEME";
        if (qid.includes("pension") || qid.includes("senior")) return "OLD_AGE_PENSION";
        if (qid.includes("widow")) return "WIDOW_PENSION";
        if (qid.includes("student") || qid.includes("scholar")) return "STUDENT_SCHOLARSHIP";
        if (qid.includes("disability")) return "DISABILITY_PENSION";
        if (qid.includes("laborer") || qid.includes("shramik")) return "LABORER_SCHEME";
        if (qid.includes("self_employ")) return "SELF_EMPLOYMENT_LOAN";
        break;
      }
    }
  }
  return "GENERAL_DISCOVERY";
}

// ============================================================================
// KNOWLEDGE GRAPH ENGINE - SHARED HELPERS
// ============================================================================
interface KGInput { intent: PrimaryIntent; p: DecisiveParams; isHi: boolean; rawQ: string; lowerQ: string; history: any[]; facts: Record<string, any>; }
interface DecisionResult { confidenceScore: number; confidenceLevel: "HIGH"|"MEDIUM"|"LOW"; recommendedSchemes: RecommendedScheme[]; candidateSchemes: RecommendedScheme[]; followUpQuestion: FollowUpQuestion|null; missingFields: string[]; verifiedCriteria: string[]; pendingCriteria: string[]; citations: SchemeCitation[]; requiredDocs: RequiredDocument[]; conversationalText: string; }

const makeJanAadhaarDoc = (isHi: boolean): RequiredDocument => ({ document_name: isHi ? "जन आधार कार्ड" : "Jan Aadhaar Card", purpose: isHi ? "पहचान एवं परिवार सत्यापन" : "Identity and family verification", issued_by: "Rajasthan Government", is_mandatory: true });
const makeBankDoc = (isHi: boolean): RequiredDocument => ({ document_name: isHi ? "बैंक पासबुक (आधार लिंक)" : "Bank Passbook (Aadhaar Linked)", purpose: isHi ? "DBT हेतु बैंक खाता" : "Bank account for DBT", issued_by: "Bank / Post Office", is_mandatory: true });
function makeFollowUp(id: string, field: string, hiQ: string, enQ: string): FollowUpQuestion {
  return { question_id: id, field, question_hi: hiQ, question_en: enQ, rationale_hi: "", rationale_en: "", options: [] };
}

function knowledgeGraphDecide(inp: KGInput): DecisionResult {
  const { intent, p, isHi, rawQ, lowerQ } = inp;
  const base: DecisionResult = { confidenceScore: 0.05, confidenceLevel: "LOW", recommendedSchemes: [], candidateSchemes: [], followUpQuestion: null, missingFields: [], verifiedCriteria: [], pendingCriteria: [], citations: [], requiredDocs: [], conversationalText: "" };

  const isSenior = (p.age !== null && p.age >= 55) || intent === "OLD_AGE_PENSION" || p.occupation === "RETIRED"
    || /वृद्ध|बुजुर्ग|senior|old\s*age|60\s*(साल|वर्ष)|58\s*(साल|वर्ष)/i.test(lowerQ);
  const effectiveOccupation = p.occupation || (isSenior ? "RETIRED" : null) || (p.isWidow ? "HOMEMAKER" : null);
  const hasAge = p.age !== null && p.age >= 5;
  const hasOccupation = effectiveOccupation !== null || p.isDisabled;

  // GATE: No WHO info at all
  if (!hasAge && !hasOccupation) {
    return {
      ...base,
      confidenceScore: 0.05,
      conversationalText: isHi
        ? "नमस्ते! मैं आपका योजनसेतु सहायक हूँ। आपके लिए सही सरकारी योजनाएं खोजने के लिए — आपकी उम्र क्या है और आप क्या काम करते हैं?"
        : "Hello! I'm your YojanSetu assistant. To find the right government schemes for you — how old are you and what do you do?",
      followUpQuestion: makeFollowUp(
        "ask_who_age_occupation",
        "occupation",
        "आपकी उम्र क्या है और आप क्या काम करते हैं?",
        "How old are you and what do you do?"
      ),
      missingFields: ["age", "occupation"],
    };
  }

  // GATE: Occupation known but no age
  if (hasOccupation && !hasAge) {
    const occLabel: Record<string, string> = {
      FARMER: isHi ? "किसान" : "farmer",
      STUDENT: isHi ? "विद्यार्थी" : "student",
      RETIRED: isHi ? "वरिष्ठ नागरिक" : "senior citizen",
      LABORER: isHi ? "श्रमिक" : "worker",
      SELF_EMPLOYED: isHi ? "व्यापारी" : "self-employed",
      HOMEMAKER: isHi ? "गृहिणी" : "homemaker",
    };
    const lbl = (effectiveOccupation && occLabel[effectiveOccupation]) || (isHi ? "नागरिक" : "citizen");
    return {
      ...base,
      confidenceScore: 0.25,
      verifiedCriteria: [`व्यवसाय: ${lbl}`],
      missingFields: ["age"],
      conversationalText: isHi
        ? `अच्छा, तो आप ${lbl} हैं! आपकी उम्र कितनी है?`
        : `Got it, you're a ${lbl}! How old are you?`,
      followUpQuestion: makeFollowUp(
        "ask_age_after_occupation",
        "age",
        "आपकी उम्र कितनी है?",
        "How old are you?"
      ),
    };
  }

  // GATE: Age known but no occupation
  if (hasAge && !hasOccupation) {
    const ag = p.age!;
    return {
      ...base,
      confidenceScore: 0.25,
      verifiedCriteria: [`उम्र: ${ag} वर्ष`],
      missingFields: ["occupation"],
      conversationalText: isHi
        ? `${ag} वर्ष, ठीक है। आप क्या काम करते हैं?`
        : `Noted, ${ag} years. What do you do for work?`,
      followUpQuestion: makeFollowUp(
        "ask_occupation_after_age",
        "occupation",
        "आप क्या काम करते हैं?",
        "What do you do for work?"
      ),
    };
  }

  // Route to scheme logic
  if (effectiveOccupation === "FARMER" || intent === "FARMER_SCHEME") return farmSchemeDecide(p, isHi, base);
  if (isSenior || effectiveOccupation === "RETIRED") return seniorPensionDecide(p, isHi, base);
  if (p.isWidow || intent === "WIDOW_PENSION") return widowPensionDecide(p, isHi, base);
  if (p.isDisabled || intent === "DISABILITY_PENSION") return disabilityDecide(p, isHi, base);
  if (effectiveOccupation === "STUDENT" || intent === "STUDENT_SCHOLARSHIP") return studentDecide(p, isHi, base);
  if (effectiveOccupation === "LABORER" || intent === "LABORER_SCHEME") return laborerDecide(p, isHi, base);
  if (effectiveOccupation === "SELF_EMPLOYED" || intent === "SELF_EMPLOYMENT_LOAN") return selfEmployedDecide(p, isHi, base);
  if (effectiveOccupation === "HOMEMAKER" || intent === "WOMEN_SCHEME") return womenDecide(p, isHi, base);
  if (intent === "HEALTH_INSURANCE") return healthDecide(p, isHi, base);
  if (intent === "HOUSING_SCHEME") return housingDecide(p, isHi, base);
  return generalDiscovery(p, isHi, base, effectiveOccupation);
}

// ============================================================================
// FARMER
// ============================================================================
function farmSchemeDecide(p: DecisiveParams, isHi: boolean, base: DecisionResult): DecisionResult {
  if (p.landBigha === null) {
    return {
      ...base,
      confidenceScore: 0.45,
      verifiedCriteria: [`उम्र: ${p.age} वर्ष`, "व्यवसाय: किसान"],
      missingFields: ["landBigha"],
      conversationalText: isHi
        ? `${p.age} साल के किसान भाई, आपके पास कुल कितनी ज़मीन (बीघा) है?`
        : `As a ${p.age}-year-old farmer, how many bighas of land do you own?`,
      followUpQuestion: makeFollowUp(
        "ask_farmer_land_bigha",
        "landBigha",
        "आपके पास कितनी कृषि भूमि है (बीघे में)?",
        "How much land do you own (in bighas)?"
      ),
    };
  }
  const isLandless = p.landBigha === 0;
  const isMarginal = p.landBigha > 0 && p.landBigha <= 2.5;
  const schemes: RecommendedScheme[] = [];
  const docs: RequiredDocument[] = [makeJanAadhaarDoc(isHi), makeBankDoc(isHi)];
  if (!isLandless) {
    schemes.push({ scheme_code: "PM-KISAN", name_hi: "पीएम किसान सम्मान निधि + राजस्थान टॉप-अप", name_en: "PM Kisan Samman Nidhi + Rajasthan Top-Up", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? "₹8,000/वर्ष DBT — ₹6,000 केंद्र + ₹2,000 राजस्थान" : "Rs.8,000/yr DBT — Rs.6,000 central + Rs.2,000 state", passed_conditions: [`उम्र ${p.age}`, `भूमि: ${p.landBigha} बीघा`], documents_required: ["जन आधार", "जमाबंदी नकल", "बैंक पासबुक"] });
    schemes.push({ scheme_code: "TARBANDI", name_hi: "खेत तारबंदी सब्सिडी योजना", name_en: "Khet Tarbandi Subsidy", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? `50% सब्सिडी, अधिकतम ₹${isMarginal ? "48,000" : "40,000"}` : `50% subsidy up to Rs.${isMarginal ? "48,000" : "40,000"}`, passed_conditions: ["कृषि भूमि धारक"], documents_required: ["जन आधार", "जमाबंदी नकल"] });
  } else {
    schemes.push({ scheme_code: "MGNREGA", name_hi: "भूमिहीन श्रमिक / MGNREGA", name_en: "Landless / MGNREGA", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? "100 दिन गारंटीशुदा काम — ₹255/दिन" : "100 days guaranteed work @ Rs.255/day", passed_conditions: ["भूमिहीन श्रमिक"], documents_required: ["जन आधार", "आधार"] });
  }
  schemes.push({ scheme_code: "CHIRANJEEVI", name_hi: "मुख्यमंत्री आयुष्मान आरोग्य योजना", name_en: "Ayushman Arogya Yojana", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? "₹25 लाख कैशलेस अस्पताल इलाज" : "Rs.25L cashless hospital treatment", passed_conditions: ["जन आधार धारी"], documents_required: ["जन आधार"] });
  docs.push({ document_name: isHi ? "जमाबंदी नकल" : "Jamabandi (Land Record)", purpose: isHi ? "भूमि स्वामित्व प्रमाण" : "Land ownership proof", issued_by: "Revenue Dept.", is_mandatory: !isLandless });
  const ctx = isLandless ? (isHi ? "भूमिहीन" : undefined) : (isHi ? `${p.landBigha} बीघा` : `${p.landBigha} bighas`);
  return {
    ...base,
    confidenceScore: 0.96,
    confidenceLevel: "HIGH",
    verifiedCriteria: [`उम्र: ${p.age} वर्ष ✓`, `किसान${ctx ? " (" + ctx + ")" : ""} ✓`],
    recommendedSchemes: schemes,
    requiredDocs: docs,
    citations: [{ citation_tag: "RAJ-AGRI-2024", title: "Rajasthan PM-KISAN + State Top-Up Guidelines 2024", page: 4, snippet: "Rajasthan farmers receive Rs.2,000 additional state top-up via DBT in addition to central Rs.6,000." }],
    conversationalText: isHi
      ? `बधाई हो! ${p.age} वर्षीय किसान${ctx ? " (" + ctx + ")" : ""} के रूप में आप पीएम किसान (₹8,000/वर्ष) और तारबंदी सब्सिडी के पात्र हैं। आप जन आधार लेकर नज़दीकी ई-मित्र पर आवेदन कर सकते हैं।`
      : `Great news! As a ${p.age}-yr-old farmer${ctx ? " (" + ctx + ")" : ""}, you qualify for PM-Kisan (Rs.8,000/yr) and fencing subsidy. You can apply at e-Mitra with your Jan Aadhaar.`,
  };
}

// ============================================================================
// SENIOR PENSION
// ============================================================================
function seniorPensionDecide(p: DecisiveParams, isHi: boolean, base: DecisionResult): DecisionResult {
  const effectiveAge = p.age || 60;
  const isWoman = p.gender === "FEMALE";
  const minAge = isWoman ? 55 : 58;
  if (effectiveAge < minAge) {
    return {
      ...base,
      confidenceScore: 0.30,
      missingFields: ["residence"],
      conversationalText: isHi
        ? `आपकी उम्र ${effectiveAge} वर्ष है। वरिष्ठ नागरिक पेंशन के लिए उम्र कम से कम ${isWoman ? "55" : "58"} वर्ष होनी चाहिए। क्या आप किसी अन्य योजना के बारे में जानना चाहते हैं?`
        : `You are ${effectiveAge} years old. Senior pension requires at least ${isWoman ? "55" : "58"} years. Is there any other scheme you would like to explore?`,
      followUpQuestion: makeFollowUp(
        "ask_residence_bpl",
        "residence",
        "क्या आप किसी अन्य योजना के बारे में जानना चाहते हैं?",
        "Would you like to explore other schemes?"
      ),
    };
  }
  if (p.income === null && !p.isBpl) {
    return {
      ...base,
      confidenceScore: 0.60,
      confidenceLevel: "MEDIUM",
      verifiedCriteria: [`उम्र: ${effectiveAge} वर्ष ✓`, `आयु मानदंड: ${minAge}+ ✓`],
      missingFields: ["income"],
      conversationalText: isHi
        ? `${effectiveAge} वर्ष — आप वृद्धजन सम्मान पेंशन के पात्र हो सकते हैं! क्या आपके परिवार का BPL राशन कार्ड है या सालाना आय ₹48,000 से कम है?`
        : `${effectiveAge} years — you may qualify for Senior Pension! Does your family have a BPL card or annual income under Rs.48,000?`,
      followUpQuestion: makeFollowUp(
        "ask_income_bpl_pension",
        "income",
        "परिवार की वार्षिक आय ₹48,000 से कम है या BPL कार्ड है?",
        "Is family income below Rs.48,000 or BPL card?"
      ),
    };
  }
  const amt = effectiveAge >= 75 ? 1500 : 1000;
  return {
    ...base,
    confidenceScore: 0.98,
    confidenceLevel: "HIGH",
    verifiedCriteria: [`उम्र: ${effectiveAge} वर्ष ✓`, p.isBpl ? "BPL ✓" : `आय ₹${p.income?.toLocaleString("en-IN")} ✓`, "राजस्थान निवासी ✓"],
    recommendedSchemes: [
      { scheme_code: "VRIDHJAN-PENSION", name_hi: "मुख्यमंत्री वृद्धजन सम्मान पेंशन", name_en: "Vridhjan Samman Pension Yojana", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? `₹${amt.toLocaleString("en-IN")}/माह (₹${(amt * 12).toLocaleString("en-IN")}/वर्ष) DBT` : `Rs.${amt.toLocaleString("en-IN")}/month via DBT`, benefit_details: { monthly_payout: amt, annual_total: amt * 12 }, passed_conditions: [`उम्र ${effectiveAge}`, `आय/BPL ✓`], documents_required: ["जन आधार", "आधार", "आय घोषणा", "बैंक पासबुक"] },
      { scheme_code: "CHIRANJEEVI", name_hi: "मुख्यमंत्री आयुष्मान आरोग्य योजना", name_en: "Ayushman Arogya Yojana", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? "₹25 लाख मुफ्त अस्पताल इलाज" : "Rs.25L free hospital", passed_conditions: ["जन आधार धारी"], documents_required: ["जन आधार"] },
    ],
    requiredDocs: [makeJanAadhaarDoc(isHi), { document_name: isHi ? "आधार (आयु प्रमाण)" : "Aadhaar (age proof)", purpose: isHi ? "आयु सत्यापन" : "Age proof", issued_by: "UIDAI", is_mandatory: true }, makeBankDoc(isHi)],
    citations: [{ citation_tag: "RAJ-SSP-2024", title: "Rajasthan Social Security Pension 2024", page: 2, snippet: "Male≥58, Female≥55 with income≤Rs.48,000 get Rs.1,000/month; Rs.1,500 at age 75." }],
    conversationalText: isHi
      ? `बधाई हो! आप मुख्यमंत्री वृद्धजन सम्मान पेंशन (₹${amt.toLocaleString("en-IN")}/माह) और ₹25 लाख के स्वास्थ्य बीमे के पात्र हैं। नज़दीकी ई-मित्र पर जन आधार से आवेदन करें।`
      : `Congratulations! You qualify for Vridhjan Samman Pension (Rs.${amt.toLocaleString("en-IN")}/mo) and Rs.25L health insurance. Apply at e-Mitra with Jan Aadhaar.`,
  };
}

// ============================================================================
// WIDOW PENSION
// ============================================================================
function widowPensionDecide(p: DecisiveParams, isHi: boolean, base: DecisionResult): DecisionResult {
  if (!p.age) {
    return {
      ...base,
      confidenceScore: 0.30,
      verifiedCriteria: ["विधवा/एकल नारी ✓"],
      missingFields: ["age"],
      conversationalText: isHi ? "एकल नारी सम्मान पेंशन के लिए — आपकी उम्र कितनी है?" : "For Single Woman / Widow Pension — how old are you?",
      followUpQuestion: makeFollowUp(
        "ask_widow_age",
        "age",
        "आपकी उम्र कितनी है?",
        "How old are you?"
      ),
    };
  }
  if (p.income === null && !p.isBpl) {
    return {
      ...base,
      confidenceScore: 0.65,
      confidenceLevel: "MEDIUM",
      verifiedCriteria: [`उम्र: ${p.age} वर्ष ✓`, "विधवा ✓"],
      missingFields: ["income"],
      conversationalText: isHi
        ? `${p.age} वर्ष नोट कर लिया। क्या परिवार की सालाना आय ₹48,000 से कम है और क्या आपके स्कूल जाने वाले बच्चे हैं?`
        : `Noted ${p.age} years. Is your family annual income under Rs.48,000, and do you have school-going children?`,
      followUpQuestion: makeFollowUp(
        "ask_widow_income",
        "income",
        "परिवार की वार्षिक आय ₹48,000 से कम है?",
        "Family income below Rs.48,000?"
      ),
    };
  }
  const amt = (p.age || 40) >= 75 ? 1500 : 1000;
  const schemes: RecommendedScheme[] = [
    { scheme_code: "EKALNARI", name_hi: "एकल नारी सम्मान पेंशन", name_en: "Ekl Nari Samman Pension", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? `₹${amt.toLocaleString("en-IN")}/माह DBT` : `Rs.${amt.toLocaleString("en-IN")}/month DBT`, passed_conditions: [`उम्र ${p.age}`, "विधवा/एकल नारी", "आय ✓"], documents_required: ["जन आधार", "आधार", "पति का मृत्यु प्रमाण", "बैंक पासबुक"] },
    { scheme_code: "CHIRANJEEVI", name_hi: "आयुष्मान आरोग्य योजना", name_en: "Ayushman Arogya", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? "₹25 लाख मुफ्त इलाज" : "Rs.25L free hospital", passed_conditions: ["जन आधार धारी"], documents_required: ["जन आधार"] },
    {
      scheme_code: "PALANHAR",
      name_hi: "राजस्थान पालनहार योजना (बच्चों की सहायता)",
      name_en: "Rajasthan Palanhar Yojana",
      eligibility_status: "CONFIDENTLY_ELIGIBLE",
      benefit_summary: isHi ? "₹1,500–₹2,500/माह प्रति बच्चा + ₹2,000/वर्ष किताब/ड्रेस" : "Rs.1,500–Rs.2,500/mo per child + Rs.2,000/yr grant",
      passed_conditions: ["एकल नारी/विधवा माता", "18 वर्ष से कम के बच्चे"],
      documents_required: ["जन आधार", "बच्चों का आधार", "स्कूल अध्ययन प्रमाण"],
    },
  ];

  return {
    ...base,
    confidenceScore: 0.98,
    confidenceLevel: "HIGH",
    verifiedCriteria: [`उम्र: ${p.age} वर्ष ✓`, "विधवा/एकल नारी ✓", "आय पात्र ✓"],
    recommendedSchemes: schemes,
    requiredDocs: [makeJanAadhaarDoc(isHi), { document_name: isHi ? "पति का मृत्यु प्रमाण पत्र" : "Husband's Death Certificate", purpose: isHi ? "विधवा स्थिति सत्यापन" : "Widowhood verification", issued_by: isHi ? "नगरपालिका/पंचायत" : "Municipality/Panchayat", is_mandatory: true }, makeBankDoc(isHi)],
    citations: [],
    conversationalText: isHi
      ? `बधाई हो! आप एकल नारी सम्मान पेंशन (₹${amt.toLocaleString("en-IN")}/माह) और पालनहार योजना की पात्र हैं। नज़दीकी ई-मित्र पर आवेदन कर सकती हैं।`
      : `Congratulations! You qualify for Ekl Nari Pension (Rs.${amt.toLocaleString("en-IN")}/mo) and Palanhar scheme. Apply at your nearest e-Mitra.`,
  };
}

// ============================================================================
// DISABILITY PENSION
// ============================================================================
function disabilityDecide(p: DecisiveParams, isHi: boolean, base: DecisionResult): DecisionResult {
  if (p.disabilityPercent < 40) {
    return {
      ...base,
      confidenceScore: 0.40,
      verifiedCriteria: ["दिव्यांग ✓"],
      missingFields: ["disabilityPercent"],
      conversationalText: isHi
        ? "दिव्यांग पेंशन के लिए न्यूनतम 40% दिव्यांगता ज़रूरी है। आपका दिव्यांगता प्रतिशत कितना है?"
        : "Disability pension requires minimum 40% disability. What is your disability percentage?",
      followUpQuestion: makeFollowUp(
        "ask_disability_pct",
        "disabilityPercent",
        "विकलांगता प्रतिशत क्या है?",
        "Disability percentage?"
      ),
    };
  }
  if (!p.age) {
    return {
      ...base,
      confidenceScore: 0.45,
      verifiedCriteria: [`दिव्यांगता: ${p.disabilityPercent}% ✓`],
      missingFields: ["age"],
      conversationalText: isHi
        ? `${p.disabilityPercent}% दिव्यांगता नोट कर ली। आपकी उम्र कितनी है?`
        : `Noted ${p.disabilityPercent}% disability. How old are you?`,
      followUpQuestion: makeFollowUp(
        "ask_disability_age",
        "age",
        "आपकी उम्र?",
        "Your age?"
      ),
    };
  }
  const amt = p.disabilityPercent >= 80 ? 1500 : 750;
  return {
    ...base,
    confidenceScore: 0.97,
    confidenceLevel: "HIGH",
    verifiedCriteria: [`उम्र: ${p.age} वर्ष ✓`, `दिव्यांगता: ${p.disabilityPercent}% ✓`],
    recommendedSchemes: [{ scheme_code: "VISHESH-YOGYAJAN", name_hi: "मुख्यमंत्री विशेष योग्यजन सम्मान पेंशन", name_en: "Vishesh Yogyajan Samman Pension", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? `₹${amt.toLocaleString("en-IN")}/माह (${p.disabilityPercent}% विकलांगता पर)` : `Rs.${amt.toLocaleString("en-IN")}/month for ${p.disabilityPercent}% disability`, passed_conditions: [`उम्र ${p.age}`, `${p.disabilityPercent}% विकलांगता`], documents_required: ["जन आधार", "सरकारी दिव्यांग प्रमाण पत्र", "बैंक पासबुक"] }],
    requiredDocs: [makeJanAadhaarDoc(isHi), { document_name: isHi ? "सरकारी दिव्यांग प्रमाण पत्र" : "Govt Disability Certificate", purpose: isHi ? "विकलांगता का प्रमाण" : "Disability proof", issued_by: isHi ? "सरकारी अस्पताल/CMO" : "Govt Hospital/CMO", is_mandatory: true }, makeBankDoc(isHi)],
    citations: [],
    conversationalText: isHi
      ? `बधाई हो! आप विशेष योग्यजन पेंशन (₹${amt.toLocaleString("en-IN")}/माह) के पात्र हैं। दिव्यांग प्रमाण पत्र के साथ ई-मित्र पर आवेदन करें।`
      : `Congratulations! You qualify for Vishesh Yogyajan Pension (Rs.${amt.toLocaleString("en-IN")}/mo). Apply at e-Mitra with disability certificate.`,
  };
}

// ============================================================================
// STUDENT SCHOLARSHIP
// ============================================================================
function studentDecide(p: DecisiveParams, isHi: boolean, base: DecisionResult): DecisionResult {
  if (!p.category) {
    return {
      ...base,
      confidenceScore: 0.45,
      verifiedCriteria: [`उम्र: ${p.age} वर्ष ✓`, "विद्यार्थी ✓"],
      missingFields: ["category"],
      conversationalText: isHi
        ? `${p.age} साल के विद्यार्थी के लिए कई योजनाएं हैं। आपकी सामाजिक श्रेणी क्या है?`
        : `For a ${p.age}-year-old student, there are several schemes! What is your social category?`,
      followUpQuestion: makeFollowUp(
        "ask_student_category",
        "category",
        "आपकी सामाजिक श्रेणी क्या है?",
        "What is your social category?"
      ),
    };
  }
  if (p.income === null && !p.isBpl && p.category !== "SC" && p.category !== "ST") {
    return {
      ...base,
      confidenceScore: 0.65,
      confidenceLevel: "MEDIUM",
      verifiedCriteria: [`उम्र: ${p.age} वर्ष ✓`, `श्रेणी: ${p.category} ✓`],
      missingFields: ["income"],
      conversationalText: isHi
        ? `${p.category} श्रेणी नोट कर ली। क्या आपके परिवार की वार्षिक आय ₹2.5 लाख से कम है?`
        : `Noted ${p.category} category. Is your family annual income under Rs.2.5 lakh?`,
      followUpQuestion: makeFollowUp(
        "ask_student_income",
        "income",
        "परिवार की वार्षिक आय क्या है?",
        "What is your family annual income?"
      ),
    };
  }
  const amtRange = (p.category === "SC" || p.category === "ST") ? "₹15,000–₹1,15,000/वर्ष" : "₹5,000–₹50,000/वर्ष";
  return {
    ...base,
    confidenceScore: 0.96,
    confidenceLevel: "HIGH",
    verifiedCriteria: [`उम्र: ${p.age} वर्ष ✓`, `श्रेणी: ${p.category} ✓`, "विद्यार्थी ✓"],
    recommendedSchemes: [
      { scheme_code: "POST-MATRIC", name_hi: "उत्तर मैट्रिक छात्रवृत्ति", name_en: "Post-Matric Scholarship", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? `${amtRange} — 100% ट्यूशन फीस + रहन-सहन भत्ता` : `${amtRange} — 100% tuition + maintenance`, passed_conditions: [`${p.category}`, `उम्र ${p.age}`], documents_required: ["जन आधार", "जाति प्रमाण", "आय प्रमाण", "मार्कशीट"] },
      { scheme_code: "ANUPRATI", name_hi: "मुख्यमंत्री अनुप्रति फ्री कोचिंग", name_en: "CM Anuprati Free Coaching", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? "NEET/JEE/UPSC/RAS फ्री कोचिंग + ₹40,000/वर्ष स्टाइपेंड" : "Free coaching for NEET/JEE/UPSC + Rs.40,000/yr stipend", passed_conditions: [`${p.category}`, "10वीं/12वीं पास"], documents_required: ["जन आधार", "जाति प्रमाण", "मार्कशीट"] },
    ],
    requiredDocs: [makeJanAadhaarDoc(isHi), { document_name: isHi ? "जाति प्रमाण पत्र" : "Caste Certificate", purpose: isHi ? "सामाजिक वर्ग सत्यापन" : "Category verification", issued_by: "तहसीलदार/SDM", is_mandatory: true }, makeBankDoc(isHi)],
    citations: [],
    conversationalText: isHi
      ? "बधाई हो! आप उत्तर मैट्रिक छात्रवृत्ति और अनुप्रति फ्री कोचिंग के पात्र हैं। आप SSO पोर्टल या ई-मित्र पर आवेदन कर सकते हैं।"
      : "Congratulations! You qualify for Post-Matric Scholarship and Anuprati Free Coaching. Apply on the SSO portal or e-Mitra.",
  };
}

// ============================================================================
// LABORER, SELF-EMPLOYED, WOMEN, HEALTH, HOUSING, GENERAL
// ============================================================================
function laborerDecide(p: DecisiveParams, isHi: boolean, base: DecisionResult): DecisionResult {
  if (p.income === null) {
    return {
      ...base,
      confidenceScore: 0.50,
      verifiedCriteria: [`उम्र: ${p.age} वर्ष ✓`, "श्रमिक ✓"],
      missingFields: ["income"],
      conversationalText: isHi
        ? `${p.age} वर्ष — आप गाँव में काम करते हैं या शहर में? और क्या आपके पास श्रमिक कार्ड है?`
        : `Got it, ${p.age} years. Do you work in a village or city, and do you have a Shramik Card?`,
      followUpQuestion: makeFollowUp(
        "ask_laborer_residence",
        "residence",
        "गाँव में या शहर में?",
        "Village or city?"
      ),
    };
  }
  return {
    ...base,
    confidenceScore: 0.95,
    confidenceLevel: "HIGH",
    verifiedCriteria: [`उम्र: ${p.age} वर्ष ✓`, "श्रमिक ✓"],
    recommendedSchemes: [
      { scheme_code: "SHRAMIK", name_hi: "राजस्थान निर्माण श्रमिक कल्याण", name_en: "Construction Worker Welfare", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? "बच्चों की छात्रवृत्ति + प्रसूति सहायता + औज़ार अनुदान + बीमा" : "Children's scholarship + maternity + tool grant + insurance", passed_conditions: ["श्रमिक कार्ड", `उम्र ${p.age}`], documents_required: ["श्रमिक कार्ड", "जन आधार", "बैंक पासबुक"] },
      { scheme_code: "MGNREGA", name_hi: "MGNREGA — 100 दिन गारंटीशुदा काम", name_en: "MGNREGA — 100 Days Guaranteed", eligibility_status: p.residence === "RURAL" ? "CONFIDENTLY_ELIGIBLE" : "CANDIDATE", benefit_summary: isHi ? "₹255/दिन — 100 दिन गारंटी" : "Rs.255/day — 100 days/year guaranteed", passed_conditions: ["ग्रामीण", "जॉब कार्ड"], documents_required: ["जन आधार", "MGNREGA जॉब कार्ड"] },
    ],
    requiredDocs: [makeJanAadhaarDoc(isHi), makeBankDoc(isHi)],
    citations: [],
    conversationalText: isHi
      ? "बधाई हो! आप निर्माण श्रमिक कल्याण योजनाओं और MGNREGA के पात्र हैं। ई-मित्र पर जाकर श्रमिक कार्ड बनवा सकते हैं।"
      : "Congratulations! You qualify for Shramik Welfare and MGNREGA. Apply at e-Mitra to get your Shramik Card.",
  };
}

function selfEmployedDecide(p: DecisiveParams, isHi: boolean, base: DecisionResult): DecisionResult {
  if (!p.category) {
    return {
      ...base,
      confidenceScore: 0.45,
      verifiedCriteria: [`उम्र: ${p.age} वर्ष ✓`, "स्वरोजगार ✓"],
      missingFields: ["category"],
      conversationalText: isHi
        ? `${p.age} वर्ष — आप किस तरह का काम या व्यवसाय करते हैं?`
        : `Got it, ${p.age} years. What kind of work or business do you do?`,
      followUpQuestion: makeFollowUp(
        "ask_trade_category",
        "category",
        "आप क्या काम या व्यापार करते हैं?",
        "What work or business do you do?"
      ),
    };
  }
  return {
    ...base,
    confidenceScore: 0.95,
    confidenceLevel: "HIGH",
    verifiedCriteria: [`उम्र: ${p.age} वर्ष ✓`, `श्रेणी: ${p.category} ✓`, "स्वरोजगार ✓"],
    recommendedSchemes: [
      { scheme_code: "PM-VISHWAKARMA", name_hi: "पीएम विश्वकर्मा योजना", name_en: "PM Vishwakarma Yojana", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? "₹3 लाख लोन (5% ब्याज) + फ्री ट्रेनिंग + टूलकिट" : "Rs.3L loan @5% + free training + toolkit", passed_conditions: [`उम्र ${p.age}`, "कारीगर/शिल्पकार"], documents_required: ["आधार", "जन आधार", "बैंक पासबुक"] },
      { scheme_code: "MUDRA", name_hi: "PM मुद्रा लोन", name_en: "PM Mudra Loan", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? "₹50,000–₹10 लाख — बिना गारंटी" : "Rs.50K–Rs.10L collateral-free", passed_conditions: ["स्वरोजगार", `उम्र ${p.age}`], documents_required: ["आधार", "बैंक पासबुक", "व्यापार प्रमाण"] },
    ],
    requiredDocs: [makeJanAadhaarDoc(isHi), makeBankDoc(isHi)],
    citations: [],
    conversationalText: isHi
      ? "बधाई हो! आप पीएम विश्वकर्मा योजना और मुद्रा लोन के पात्र हैं। नज़दीकी बैंक या ई-मित्र पर आवेदन करें।"
      : "Congratulations! You qualify for PM Vishwakarma and Mudra loans. Apply at a bank or e-Mitra.",
  };
}

function womenDecide(p: DecisiveParams, isHi: boolean, base: DecisionResult): DecisionResult {
  if (!p.income && !p.isBpl) {
    return {
      ...base,
      confidenceScore: 0.45,
      verifiedCriteria: ["महिला ✓"],
      missingFields: ["income"],
      conversationalText: isHi
        ? "महिलाओं के लिए कई कल्याणकारी योजनाएं हैं। क्या आपके पास BPL कार्ड है या परिवार की सालाना आय कितनी है?"
        : "There are several welfare schemes for women. Do you have a BPL card or what is your family annual income?",
      followUpQuestion: makeFollowUp(
        "ask_women_income",
        "income",
        "BPL कार्ड है या सालाना आय?",
        "BPL card or annual income?"
      ),
    };
  }
  return {
    ...base,
    confidenceScore: 0.93,
    confidenceLevel: "HIGH",
    verifiedCriteria: ["महिला ✓", p.isBpl ? "BPL ✓" : "आय पात्र ✓"],
    recommendedSchemes: [
      { scheme_code: "LADO", name_hi: "लाडो प्रोत्साहन योजना", name_en: "Lado Protsahan Yojana", eligibility_status: "CANDIDATE", benefit_summary: isHi ? "बेटी जन्म पर ₹2 लाख बचत बॉन्ड" : "Rs.2L savings bond at girl's birth", passed_conditions: ["राजस्थान निवासी", "बेटी जन्म"], documents_required: ["जन आधार", "जन्म प्रमाण"] },
      { scheme_code: "CHIRANJEEVI", name_hi: "मुख्यमंत्री आयुष्मान आरोग्य योजना", name_en: "Ayushman Arogya Yojana", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? "₹25 लाख मुफ्त इलाज + प्रसव" : "Rs.25L free + maternity", passed_conditions: ["जन आधार धारी"], documents_required: ["जन आधार"] },
      { scheme_code: "INDIRA-MATRITY", name_hi: "इंदिरा गांधी मातृत्व सहायता", name_en: "Indira Gandhi Maternity Aid", eligibility_status: "CANDIDATE", benefit_summary: isHi ? "₹6,000 प्रसव पर (BPL परिवार)" : "Rs.6,000 maternity (BPL)", passed_conditions: [p.isBpl ? "BPL" : "आय पात्र", "गर्भावस्था"], documents_required: ["जन आधार", "BPL राशन कार्ड"] },
    ],
    requiredDocs: [makeJanAadhaarDoc(isHi), makeBankDoc(isHi)],
    citations: [],
    conversationalText: isHi
      ? "बधाई हो! आप लाडो प्रोत्साहन, इंदिरा मातृत्व और आयुष्मान स्वास्थ्य योजना की पात्र हैं। ई-मित्र पर आवेदन कर सकती हैं।"
      : "Congratulations! You qualify for Lado Protsahan, Indira Maternity, and Ayushman health benefits. Apply at e-Mitra.",
  };
}

function healthDecide(p: DecisiveParams, isHi: boolean, base: DecisionResult): DecisionResult {
  return {
    ...base,
    confidenceScore: 0.92,
    confidenceLevel: "HIGH",
    verifiedCriteria: ["जन आधार धारी ✓"],
    recommendedSchemes: [{ scheme_code: "CHIRANJEEVI", name_hi: "मुख्यमंत्री आयुष्मान आरोग्य योजना", name_en: "Mukhyamantri Ayushman Arogya Yojana", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? "₹25 लाख/वर्ष कैशलेस + ₹10 लाख दुर्घटना बीमा — 1,736+ अस्पताल" : "Rs.25L/yr cashless + Rs.10L accident at 1,736+ hospitals", passed_conditions: ["राजस्थान निवासी", "जन आधार धारी"], documents_required: ["जन आधार"] }],
    requiredDocs: [makeJanAadhaarDoc(isHi)],
    citations: [],
    conversationalText: isHi
      ? "मुख्यमंत्री आयुष्मान आरोग्य योजना के तहत राजस्थान के हर जन आधार परिवार को ₹25 लाख तक का कैशलेस इलाज मिलता है। अस्पताल में जन आधार कार्ड दिखाएं।"
      : "Under Mukhyamantri Ayushman Arogya Yojana, every Jan Aadhaar family gets up to Rs.25L cashless treatment. Just show Jan Aadhaar at the hospital.",
  };
}

function housingDecide(p: DecisiveParams, isHi: boolean, base: DecisionResult): DecisionResult {
  if (!p.isBpl && p.income === null) {
    return {
      ...base,
      confidenceScore: 0.45,
      missingFields: ["income"],
      conversationalText: isHi
        ? "PM आवास योजना के लिए — क्या आपके पास BPL कार्ड है और क्या अभी कच्चा मकान है?"
        : "For PM Awas Yojana — do you have a BPL card and do you currently live in a kutcha house?",
      followUpQuestion: makeFollowUp(
        "ask_housing_bpl",
        "income",
        "BPL कार्ड है और कच्चा मकान है?",
        "BPL card and kutcha house?"
      ),
    };
  }
  return {
    ...base,
    confidenceScore: 0.90,
    confidenceLevel: "HIGH",
    verifiedCriteria: [p.isBpl ? "BPL ✓" : "आय पात्र ✓"],
    recommendedSchemes: [{ scheme_code: "PM-AWAS", name_hi: "प्रधानमंत्री आवास योजना (ग्रामीण)", name_en: "PM Awas Yojana Gramin", eligibility_status: "CONFIDENTLY_ELIGIBLE", benefit_summary: isHi ? "₹1,20,000–₹1,80,000 पक्का मकान — DBT" : "Rs.1,20,000–1,80,000 pucca house DBT", passed_conditions: ["BPL/EWS", "पक्का मकान नहीं"], documents_required: ["जन आधार", "BPL राशन कार्ड", "आधार", "बैंक पासबुक"] }],
    requiredDocs: [makeJanAadhaarDoc(isHi), makeBankDoc(isHi)],
    citations: [],
    conversationalText: isHi
      ? "बधाई हो! आप PM आवास योजना के तहत पक्का मकान बनाने के लिए ₹1.20 लाख से ₹1.80 लाख सहायता के पात्र हैं। पंचायत या ई-मित्र पर आवेदन करें।"
      : "Congratulations! You qualify for PM Awas Yojana (Rs.1.20L–1.80L for pucca house). Apply at Panchayat or e-Mitra.",
  };
}

function generalDiscovery(p: DecisiveParams, isHi: boolean, base: DecisionResult, occ: string | null): DecisionResult {
  return {
    ...base,
    confidenceScore: 0.55,
    confidenceLevel: "MEDIUM",
    verifiedCriteria: [`उम्र: ${p.age} वर्ष ✓`, occ ? `व्यवसाय: ${occ} ✓` : ""].filter(Boolean),
    missingFields: ["intent"],
    conversationalText: isHi
      ? `${p.age} वर्ष, ठीक है। आपको मुख्य रूप से किस तरह की योजना में मदद चाहिए?`
      : `Noted, ${p.age} years. What kind of scheme assistance are you looking for?`,
    followUpQuestion: makeFollowUp(
      "ask_specific_need",
      "intent",
      "आपको किस चीज़ में सहायता चाहिए?",
      "What kind of assistance do you need?"
    ),
  };
}

export function getFallbackTools(): { tools: any[] } {
  return {
    tools: [
      { name: "knowledge_graph_profile", description: "Extract citizen profile from conversation using knowledge graph", parameters: { query: "string", context: "object" } },
      { name: "eligibility_gate", description: "Determine which eligibility questions to ask next based on known facts", parameters: { intent: "string", known_facts: "object" } },
      { name: "scheme_eligibility_gate", description: "Gate scheme recommendations until minimum eligibility criteria met", parameters: { intent: "string", missing_fields: "array" } },
    ]
  };
}
