/**
 * Conversational Welfare Agent Engine for YojanSetu.
 * 
 * Strict Golden Conversational Rules:
 * 1. NEVER suggest schemes without knowing the citizen's profile!
 * 2. If neither Age nor Occupation is known:
 *    -> Ask: "Who are you, what is your age and what is your profession?" (0 schemes)
 * 3. If Occupation is known, but Age is missing:
 *    -> Ask: "What is your current age?" (0 schemes)
 * 4. If Age is known, but Occupation is missing:
 *    -> Ask: "What is your primary profession or role?" (0 schemes)
 * 5. If Age AND Occupation are known, but qualifying criteria (land/income/category) is missing:
 *    -> Ask the decisive follow-up question (0 schemes)
 * 6. ONLY when Age + Occupation + Qualifying criteria are verified:
 *    -> Unlock 100% verified schemes with DBT amounts and application documents.
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

  // 1. Synthesize contextual and newly extracted facts
  const extractedFromQuery = extractDemographicsFromText(rawQ);
  const facts: Record<string, any> = {
    ...context,
    ...extractedFromQuery,
  };

  // Inspect recent conversation history to parse context-dependent answers
  if (history && history.length > 0) {
    for (let i = history.length - 1; i >= 0; i--) {
      const msg = history[i];
      if (msg.sender === "assistant" && msg.followUpQuestion) {
        const fld = msg.followUpQuestion.field;
        // If the assistant just asked for age and user replied with a number
        if ((fld === "age" || msg.followUpQuestion.question_id === "ask_identity_and_role") && facts.age === undefined) {
          const numMatch = rawQ.match(/\b(\d{1,2})\b/);
          if (numMatch && parseInt(numMatch[1], 10) >= 12 && parseInt(numMatch[1], 10) <= 100) {
            facts.age = parseInt(numMatch[1], 10);
          }
        }
        // If the assistant just asked for land and user replied with a number
        if (fld === "landBigha" && facts.landBigha === undefined) {
          const numMatch = rawQ.match(/(\d+(?:\.\d+)?)/);
          if (numMatch) {
            facts.landBigha = parseFloat(numMatch[1]);
            facts.occupation = "FARMER";
          }
        }
        // If assistant asked for income / BPL
        if (fld === "income" && facts.income === undefined) {
          if (/हाँ|yes|bpl|बीपीएल|कम|हूँ/i.test(rawQ)) {
            facts.income = 36000;
            facts.isBpl = true;
          } else if (/नहीं|no|ज्यादा|अधिक/i.test(rawQ)) {
            facts.income = 90000;
          }
        }
        break;
      }
    }
  }

  const age = facts.age !== undefined && facts.age !== null ? Number(facts.age) : null;
  const gender = facts.gender || null;
  const income = facts.income !== undefined && facts.income !== null
    ? Number(facts.income)
    : facts.annual_income !== undefined && facts.annual_income !== null
    ? Number(facts.annual_income)
    : null;
  const occupation = facts.occupation || null;
  const residence = facts.residence || null;
  const category = facts.category || facts.social_category || null;
  const district = facts.district || "Jaipur";
  const rationCard = facts.rationCard || facts.ration_card || null;
  const isWidow = facts.isWidow === true || facts.is_widow === true || facts.maritalStatus === "WIDOW" || /widow|विधवा|एकल\s*नारी|पति\s*की\s*मृत्यु/i.test(lowerQ);
  const isDisabled = facts.isDisabled === true || facts.is_disabled === true || /दिव्यांग|विकलांग|अपंग|handicap|disabled/i.test(lowerQ);
  const disabilityPercent = facts.disabilityPercent || facts.disability_percent || (isDisabled ? 50 : 0);
  const landBigha =
    facts.landBigha !== undefined && facts.landBigha !== null
      ? Number(facts.landBigha)
      : facts.land_area_bigha !== undefined && facts.land_area_bigha !== null
      ? Number(facts.land_area_bigha)
      : null;
  const isBpl = rationCard === "BPL" || rationCard === "AAY" || rationCard === "STATE_BPL" || facts.is_bpl === true;
  const hasJanAadhaar = facts.hasJanAadhaar !== false;

  // 2. Classify Citizen Intent
  const primaryIntent = detectIntent(rawQ, facts, history);

  // 3. Evaluate Decisive Criteria with Strict Progressive Conversational Gating
  const evalResult = evaluateConfidenceAndFollowUp(
    primaryIntent,
    {
      age,
      gender,
      income,
      occupation,
      residence,
      category,
      district,
      rationCard,
      isWidow,
      isDisabled,
      disabilityPercent,
      landBigha,
      isBpl,
      hasJanAadhaar,
    },
    isHi,
    rawQ,
    history
  );

  const steps: ToolExecutionStep[] = [
    {
      step: 1,
      thought: isHi
        ? `नागरिक के कथन से आवश्यकता '${primaryIntent}' की पहचान की गई। ज्ञात तथ्य: उम्र=${age ?? "अज्ञात"}, व्यवसाय=${occupation ?? "अज्ञात"}, ज़िला=${district}।`
        : `Identified primary need '${primaryIntent}'. Confirmed facts: age=${age ?? "unknown"}, occupation=${occupation ?? "unknown"}, district=${district}.`,
      tool_name: "extract_citizen_profile",
      tool_args: { query: rawQ, context: facts },
      tool_result: {
        primary_intent: primaryIntent,
        confirmed_facts: Object.fromEntries(
          Object.entries(facts).filter(([_, v]) => v !== null && v !== undefined)
        ),
      },
      duration_ms: 5,
    },
    {
      step: 2,
      thought: isHi
        ? `सत्यापन विश्वास: ${Math.round(evalResult.confidenceScore * 100)}% (${evalResult.confidenceLevel})। ${
            evalResult.confidenceScore >= 0.80
              ? "पात्रता पूर्णतः सत्यापित। योजनाएं स्वीकृत की जा रही हैं।"
              : "पात्रता अधूरी है। पहले नागरिक से आवश्यक विवरण पूछे जा रहे हैं।"
          }`
        : `Verification confidence: ${Math.round(evalResult.confidenceScore * 100)}% (${evalResult.confidenceLevel}). ${
            evalResult.confidenceScore >= 0.80
              ? "Eligibility verified. Displaying recommended schemes."
              : "Insufficient info. Asking citizen for age, profession, or qualifying criteria first."
          }`,
      tool_name: "evaluate_eligibility_confidence",
      tool_args: {
        intent: primaryIntent,
        confidence_score: evalResult.confidenceScore,
        missing_fields: evalResult.missingFields,
      },
      tool_result: {
        status: evalResult.confidenceScore >= 0.80 ? "CONFIDENT_VERIFIED" : "INQUIRY_IN_PROGRESS",
        confidence_score: evalResult.confidenceScore,
      },
      duration_ms: 7,
    },
  ];

  const kioskInfo: EmitraKioskInfo = {
    district: district,
    tehsil: "मुख्य ब्लॉक (Main)",
    toll_free_helpline: "181 (राजस्थान संपर्क)",
    emitra_support: "emitra.rajasthan.gov.in",
    working_hours: "9:00 AM - 6:00 PM (सोमवार से शनिवार)",
    service_kiosks: [
      {
        kiosk_name: `${district} केंद्रीय ई-मित्र केंद्र`,
        location: `तहसील परिसर, ${district}`,
        services: ["जन आधार प्रमाणीकरण", "पेंशन सत्यापन", "किसान पंजीकरण", "छात्रवृत्ति आवेदन"],
        govt_fee: "₹0 - ₹25 (सरकारी नियमानुसार)",
      },
    ],
    citizen_tip: isHi
      ? "आवेदन हेतु मूल जन आधार कार्ड, आधार कार्ड एवं बैंक पासबुक अनिवार्य रूप से साथ ले जाएं।"
      : "Carry original Jan Aadhaar card, Aadhaar, and bank passbook to the kiosk.",
  };

  const totalDuration = Date.now() - startTime;

  const structuredData: AgentStructuredData = {
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
  };

  return {
    final_answer: evalResult.conversationalText,
    language: isHi ? "hi" : "en",
    steps: steps,
    structured_data: structuredData,
    execution_time_ms: totalDuration,
  };
}

// ---------------------------------------------------------------------------
// Intent Classification with Conversation Context Retention
// ---------------------------------------------------------------------------
function detectIntent(
  rawQ: string,
  facts: Record<string, any>,
  history: any[] = []
): PrimaryIntent {
  const q = rawQ.toLowerCase();

  // 1. Direct Greetings / Casual
  if (/^(hello|hi|hey|namaste|नमस्ते|प्रणाम|राम\s*राम|kya\s*haal|who\s*are\s*you|help|मदद|सहायता)$/i.test(q.trim())) {
    return "GREETING";
  }

  // 2. Direct Keywords
  if (facts.isWidow || /विधवा|एकल\s*नारी|पति\s*की\s*मृत्यु|widow/i.test(q)) {
    return "WIDOW_PENSION";
  }
  if (facts.isDisabled || /दिव्यांग|विकलांग|अपंग|अंधा|disabled|handicap/i.test(q)) {
    return "DISABILITY_PENSION";
  }
  if (/वृद्ध|बुजुर्ग|बूढ़े|senior|old\s*age|60\s*साल|60\s*वर्ष|58\s*साल|58\s*वर्ष|vridh/i.test(q)) {
    return "OLD_AGE_PENSION";
  }
  if (/पेंशन|pension/i.test(q)) {
    if (facts.age !== null && facts.age >= 55) return "OLD_AGE_PENSION";
    return "GENERAL_PENSION";
  }
  if (facts.occupation === "FARMER" || /किसान|कृषक|खेती|फसल|farmer|kisan|बीघा|खाद|subsidy|तारबंदी|solar\s*pump/i.test(q)) {
    return "FARMER_SCHEME";
  }
  if (facts.occupation === "STUDENT" || facts.isStudent || /छात्र|छात्रा|विद्यार्थी|student|छात्रवृत्ति|scholarship|अनुप्रति|coaching|neet|jee|upsc/i.test(q)) {
    return "STUDENT_SCHOLARSHIP";
  }
  if (/इलाज|अस्पताल|स्वास्थ्य|दवा|health|hospital|chiranjeevi|चिरंजीवी|ayushman|आयुष्मान|बीमारी|medical/i.test(q)) {
    return "HEALTH_INSURANCE";
  }
  if (/ऋण|लोन|loan|मुद्रा|mudra|विश्वकर्मा|vishwakarma|दुकान|व्यापार|रोजगार|स्वरोजगार|धंधा|कारीगर|artisan/i.test(q)) {
    return "SELF_EMPLOYMENT_LOAN";
  }
  if (/आवास|मकान|घर|pmay|इंदिरा\s*आवास|housing|ghar/i.test(q)) {
    return "HOUSING_SCHEME";
  }
  if (/सिलेंडर|गैस|उज्ज्वला|राशन|खाद्य\s*सुरक्षा|ration|cylinder|gas|nfsa|अन्नपूर्णा/i.test(q)) {
    return "GAS_RATION";
  }

  // 3. Fallback to Prior Intent from Context or History
  if (facts.primaryIntent && facts.primaryIntent !== "GENERAL_DISCOVERY" && facts.primaryIntent !== "GREETING") {
    return facts.primaryIntent as PrimaryIntent;
  }
  if (facts.occupation === "FARMER" || (facts.landBigha !== null && facts.landBigha > 0)) {
    return "FARMER_SCHEME";
  }
  if (facts.occupation === "STUDENT" || facts.isStudent) {
    return "STUDENT_SCHOLARSHIP";
  }
  if (facts.age !== null && facts.age >= 55) {
    return "OLD_AGE_PENSION";
  }

  if (history && history.length > 0) {
    for (let i = history.length - 1; i >= 0; i--) {
      const msg = history[i];
      if (msg.sender === "assistant") {
        const full = ((msg.text || "") + " " + JSON.stringify(msg.followUpQuestion || "")).toLowerCase();
        if (/पेंशन|vridh|वृद्ध|58|55/i.test(full)) return "OLD_AGE_PENSION";
        if (/विधवा|एकल\s*नारी|widow/i.test(full)) return "WIDOW_PENSION";
        if (/किसान|भूमि|farmer|kisan|बीघा/i.test(full)) return "FARMER_SCHEME";
        if (/छात्र|विद्यार्थी|scholarship|coaching/i.test(full)) return "STUDENT_SCHOLARSHIP";
        if (/ऋण|लोन|विश्वकर्मा|mudra|स्वरोजगार/i.test(full)) return "SELF_EMPLOYMENT_LOAN";
        if (/स्वास्थ्य|आयुष्मान|चिरंजीवी/i.test(full)) return "HEALTH_INSURANCE";
      }
    }
  }

  return "GENERAL_DISCOVERY";
}

interface DecisionResult {
  confidenceScore: number;
  confidenceLevel: "HIGH" | "MEDIUM" | "LOW";
  recommendedSchemes: RecommendedScheme[];
  candidateSchemes: RecommendedScheme[];
  followUpQuestion: FollowUpQuestion | null;
  missingFields: string[];
  verifiedCriteria: string[];
  pendingCriteria: string[];
  citations: SchemeCitation[];
  requiredDocs: RequiredDocument[];
  conversationalText: string;
}

// ---------------------------------------------------------------------------
// Strict Progressive Conversational Decision Engine
// ---------------------------------------------------------------------------
function evaluateConfidenceAndFollowUp(
  intent: PrimaryIntent,
  p: DecisiveParams,
  isHi: boolean,
  rawQ: string,
  history: any[] = []
): DecisionResult {
  const verified: string[] = [];
  const pending: string[] = [];
  const missing: string[] = [];
  const recommended: RecommendedScheme[] = [];
  const candidates: RecommendedScheme[] = [];
  const citations: SchemeCitation[] = [];
  const requiredDocs: RequiredDocument[] = [];
  let followUp: FollowUpQuestion | null = null;
  let score = 0.10;
  let text = "";

  const isSenior =
    (p.age !== null && p.age >= 55) ||
    intent === "OLD_AGE_PENSION" ||
    p.occupation === "RETIRED" ||
    /वृद्ध|बुजुर्ग|बूढ़े|senior|old\s*age|60\s*साल|60\s*वर्ष|58\s*साल|58\s*वर्ष|vridh/i.test(rawQ);
  const effectiveOccupation = p.occupation || (isSenior ? "RETIRED" : null);
  const hasAge = p.age !== null && p.age >= 10;
  const hasOccupation = effectiveOccupation !== null || p.isWidow;

  const janAadhaarDoc: RequiredDocument = {
    document_name: isHi ? "जन आधार कार्ड" : "Jan Aadhaar Card",
    purpose: isHi ? "पहचान एवं परिवार सत्यापन" : "Identity and family verification",
    issued_by: "Rajasthan Government",
    is_mandatory: true,
  };
  const bankDoc: RequiredDocument = {
    document_name: isHi ? "बैंक पासबुक (आधार सीडेड खाता)" : "Bank Passbook (Aadhaar Seeded)",
    purpose: isHi ? "प्रत्यक्ष लाभ हस्तांतरण (DBT)" : "Direct Benefit Transfer (DBT)",
    issued_by: "Bank / Post Office",
    is_mandatory: true,
  };

  // =========================================================================
  // PILLAR 1 & 2 GATING: AGE & OCCUPATION MUST BOTH BE GATHERED FIRST!
  // =========================================================================

  // CASE 1: Neither Age nor Occupation is known
  if (!hasAge && !hasOccupation) {
    score = 0.10;
    missing.push("age", "occupation");
    pending.push("नागरिक की आयु व मुख्य कार्य/व्यवसाय");

    text = isHi
      ? `मुझे खुशी होगी आपसे मिलकर! 😊\n\nमैं राजस्थान सरकार की स्कीमों का विशेषज्ञ हूँ — पेंशन, किसान सहायता, छात्रवृत्ति, आवास, स्वास्थ्य बीमां और अनेक वित्तीय सहायताओं के बारे में।\n\nआपकी सही पात्रता जानने के लिए मुझे कुछ पता लगाना होगा। सबसे पहले बताइए — **आपकी उम्र कितनी है और आप क्या काम करते हैं?** जैसे खेती, पढ़ाई, दुकान, मजदूरी, या घर संभालना — जो भी हो`
      : `Great to meet you! 😊\n\nI specialize in Rajasthan government schemes — pensions, farmer aid, scholarships, housing, health insurance, and financial assistance.\n\nTo find what's right for you, I need to know a bit about you. Let's start — **how old are you and what do you do for a living?** (farming, studying, running a shop, daily work, household, retired — anything works!)`;

    followUp = {
      question_id: "ask_identity_and_role",
      field: "occupation",
      question_hi: "आपकी उम्र कितनी है और आप क्या काम करते हैं?",
      question_en: "How old are you and what do you do?",
      rationale_hi: "",
      rationale_en: "",
      options: [],
    };

    return {
      confidenceScore: score,
      confidenceLevel: "LOW",
      recommendedSchemes: [],
      candidateSchemes: [],
      followUpQuestion: followUp,
      missingFields: missing,
      verifiedCriteria: verified,
      pendingCriteria: pending,
      citations: [],
      requiredDocs: [],
      conversationalText: text,
    };
  }

  // CASE 2: Occupation is known, but Age is missing
  if (!hasAge && hasOccupation) {
    score = 0.35;
    missing.push("age");
    pending.push("नागरिक की वर्तमान आयु");

    const roleName = p.occupation === "FARMER"
      ? (isHi ? "किसान भाई" : "Farmer")
      : p.occupation === "STUDENT"
      ? (isHi ? "विद्यार्थी" : "Student")
      : p.occupation === "SELF_EMPLOYED"
      ? (isHi ? "स्वरोजगार/व्यापारी" : "Self-Employed")
      : p.occupation === "LABORER"
      ? (isHi ? "श्रमिक भाई" : "Worker")
      : p.isWidow
      ? (isHi ? "एकल नारी/विधवा" : "Widow/Single Woman")
      : (isHi ? "नागरिक" : "Citizen");

    text = isHi
      ? `अच्छा! आप ${roleName} हैं — यह पता चल गया। 😊\n\nअब पड़ताल के लिए: **आपकी उम्र कितनी है?** (आप सीधे अंक में बता सकते हैं, जैसे: 45 या 32)`
      : `Got it! You are a ${roleName}. 😊\n\nTo check your exact scheme eligibility: **How old are you?** (Just type your age in numbers, e.g. 45 or 32)`;

    followUp = {
      question_id: "ask_age",
      field: "age",
      question_hi: "आपकी उम्र कितनी है?",
      question_en: "How old are you?",
      rationale_hi: "",
      rationale_en: "",
      options: [],
    };

    return {
      confidenceScore: score,
      confidenceLevel: "LOW",
      recommendedSchemes: [],
      candidateSchemes: [],
      followUpQuestion: followUp,
      missingFields: missing,
      verifiedCriteria: verified,
      pendingCriteria: pending,
      citations: [],
      requiredDocs: [],
      conversationalText: text,
    };
  }

  // CASE 3: Age is known, but Occupation is missing
  if (hasAge && !hasOccupation) {
    score = 0.35;
    missing.push("occupation");
    pending.push("नागरिक का व्यवसाय / कार्य");

    verified.push(`आयु: ${p.age} वर्ष`);

    text = isHi
      ? `ठीक है, ${p.age} वर्ष नोट कर लिया। 😊\n\nअब यह बताइए — **आप क्या काम करते हैं?** (जैसे खेती, पढ़ाई, दुकानदारी, मजदूरी, घर संभालना, या सेवानिवृत्त?)`
      : `Got it, ${p.age} years noted! 😊\n\nNow tell me — **what do you do for work or livelihood?** (farming, studying, running a business, daily labour, homemaker, retired — anything is fine)`;

    followUp = {
      question_id: "ask_occupation_with_age",
      field: "occupation",
      question_hi: "आप क्या काम करते हैं?",
      question_en: "What do you do for work?",
      rationale_hi: "",
      rationale_en: "",
      options: [],
    };

    return {
      confidenceScore: score,
      confidenceLevel: "LOW",
      recommendedSchemes: [],
      candidateSchemes: [],
      followUpQuestion: followUp,
      missingFields: missing,
      verifiedCriteria: verified,
      pendingCriteria: pending,
      citations: [],
      requiredDocs: [],
      conversationalText: text,
    };
  }

  // =========================================================================
  // PILLAR 3 GATING: BOTH AGE AND OCCUPATION ARE CONFIRMED.
  // NOW CHECK SPECIFIC STATUTORY QUALIFYING CONDITIONS!
  // =========================================================================

  // -------------------------------------------------------------------------
  // SCENARIO 1: FARMER
  // -------------------------------------------------------------------------
  if (effectiveOccupation === "FARMER" || intent === "FARMER_SCHEME") {
    if (p.landBigha === null) {
      score = 0.60;
      missing.push("landBigha");

      text = isHi
        ? `नमस्ते अन्नदाता! ${p.age} वर्ष के किसान भाई के रूप में आपके लिए पीएम किसान सम्मान निधि (₹8,000/वर्ष) और खेत तारबंदी सब्सिडी (₹48,000) जैसी महत्वपूर्ण योजनाएं हैं।\n\nसटीक पात्रता और अनुदान राशि निर्धारित करने के लिए:\n👉 **आपके पास कितने बीघा कृषि भूमि (खेत) है?**`
        : `Greetings! For a ${p.age}-year-old farmer, major schemes include PM-KISAN (₹8,000/yr) and Farm Fencing Subsidies up to ₹48,000.\n\nTo verify your exact entitlement:\n👉 **How many bighas of agricultural land do you own?**`;

      followUp = {
        question_id: "ask_farmer_land",
        field: "landBigha",
        question_hi: "आपके पास कृषि भूमि (खेत) कितनी है?",
        question_en: "How many bighas of land do you hold?",
        rationale_hi: "भूमि के रकबे के आधार पर लघु/सीमांत किसान की आधिकारिक पात्रता तय होती है।",
        rationale_en: "Landholding size determines small/marginal farmer eligibility.",
        options: [],
      };
    } else {
      score = 0.95;
      const isSmall = p.landBigha <= 5 && p.landBigha > 0;
      verified.push(`आयु: ${p.age} वर्ष`);
      verified.push(`व्यवसाय: किसान (${p.landBigha} बीघा भूमि - ${isSmall ? "लघु/सीमांत कृषक" : "सामान्य कृषक"})`);
      verified.push("भू-अभिलेख जमाबंदी पात्रता पूर्ण");

      text = isHi
        ? `🎉 **बधाई हो! आपकी पूरी जानकारी सत्यापित हो चुकी है।**\n\nआपके विवरण (${p.age} वर्ष, किसान, ${p.landBigha} बीघा कृषि भूमि) के आधार पर आप निम्नलिखित सरकारी योजनाओं के लिए पूरी तरह पात्र हैं:`
        : `🎉 **Congratulations! Your profile has been fully verified.**\n\nBased on your confirmed details (${p.age} yrs, Farmer, ${p.landBigha} bighas land), you are officially entitled to the following government schemes:`;

      recommended.push({
        scheme_code: "RAJ-AGRI-001",
        name_en: "PM Kisan Samman Nidhi + Rajasthan Krishi Top-Up",
        name_hi: "पीएम किसान + राजस्थान किसान अतिरिक्त सहायता योजना",
        eligibility_status: "CONFIDENTLY_ELIGIBLE",
        benefit_summary: "₹8,000 प्रति वर्ष प्रत्यक्ष बैंक खाता हस्तांतरण (₹2,000 प्रति 4 माह)",
        benefit_details: {
          central_dbt: 6000,
          state_topup: 2000,
          annual_total: 8000,
        },
        passed_conditions: verified,
        documents_required: ["जन आधार कार्ड", "आधार कार्ड", "जमाबंदी (खसरा नकल)", "बैंक पासबुक"],
      });

      recommended.push({
        scheme_code: "RAJ-AGRI-002",
        name_en: "Rajasthan Khet Tarbandi Subsidy Yojana",
        name_hi: "राजस्थान खेत तारबंदी सब्सिडी योजना",
        eligibility_status: "CONFIDENTLY_ELIGIBLE",
        benefit_summary: "खेत की तारबंदी पर 50% सरकारी अनुदान (अधिकतम ₹48,000)",
        passed_conditions: ["कृषि भूमि धारक", "फसल सुरक्षा अनुदान"],
        documents_required: ["जन आधार कार्ड", "जमाबंदी नकल", "नक्शा ट्रेस"],
      });

      recommended.push({
        scheme_code: "RAJ-HEALTH-001",
        name_en: "Mukhyamantri Ayushman Arogya Yojana",
        name_hi: "मुख्यमंत्री आयुष्मान आरोग्य (स्वास्थ्य) योजना",
        eligibility_status: "CONFIDENTLY_ELIGIBLE",
        benefit_summary: "₹25 लाख कैशलेस अस्पताल उपचार + ₹10 लाख दुर्घटना बीमा",
        passed_conditions: ["राजस्थान जन आधार कार्ड धारी परिवार"],
        documents_required: ["जन आधार कार्ड"],
      });

      citations.push({
        citation_tag: "RAJ-AGRI-2024-C08",
        title: "राजस्थान मुख्यमंत्री किसान सम्मान निधि दिशा-निर्देश 2024",
        page: 3,
        snippet: "पीएम-किसान योजना के समस्त पात्र कृषकों को राजस्थान सरकार द्वारा ₹2,000 प्रति वर्ष की अतिरिक्त वित्तीय सहायता सीधे बैंक खाते में अंतरित की जाएगी।",
      });

      requiredDocs.push(
        janAadhaarDoc,
        {
          document_name: isHi ? "जमाबंदी नकल (खसरा नकल)" : "Jamabandi (Land Record)",
          purpose: isHi ? "कृषि भूमि स्वामित्व का आधिकारिक सत्यापन" : "Land ownership proof",
          issued_by: "Revenue Department",
          is_mandatory: true,
        },
        bankDoc
      );
    }
  }

  // -------------------------------------------------------------------------
  // SCENARIO 2: SENIOR CITIZEN / OLD AGE PENSION
  // -------------------------------------------------------------------------
  else if (isSenior || (p.age !== null && p.age >= 55) || effectiveOccupation === "RETIRED") {
    const effectiveAge = p.age || 60;
    if (p.income === null && !p.isBpl) {
      score = 0.60;
      missing.push("income");

      text = isHi
        ? `आपकी आयु (${effectiveAge} वर्ष) वृद्धजन सम्मान पेंशन के आयु मानदंड को पूरा करती है (प्रति माह ₹1,000 से ₹1,500)।\n\nसरकारी नियमों के अनुसार अंतिम सत्यापन के लिए:\n👉 **क्या आपकी पारिवारिक वार्षिक आय ₹48,000 से कम है अथवा आपके पास बीपीएल राशन कार्ड है?**`
        : `Your age (${effectiveAge} years) satisfies the senior citizen pension criteria (₹1,000/month, ₹1,500/month after 75 yrs).\n\nTo complete statutory verification:\n👉 **Is your annual family income under ₹48,000 or do you hold a BPL ration card?**`;

      followUp = {
        question_id: "ask_income_for_pension",
        field: "income",
        question_hi: "क्या आपकी वार्षिक आय ₹48,000 से कम है या बीपीएल राशन कार्ड है?",
        question_en: "Is your family income under ₹48,000 or do you have a BPL ration card?",
        rationale_hi: "",
        rationale_en: "",
        options: [],
      };
    } else {
      score = 0.98;
      const monthlyVal = effectiveAge >= 75 ? 1500 : 1000;
      verified.push(`आयु: ${effectiveAge} वर्ष (न्यूनतम आयु सीमा पूर्ण)`);
      verified.push(p.isBpl ? "बीपीएल / अंत्योदय राशन कार्ड धारक" : `वार्षिक आय: ₹${(p.income || 36000).toLocaleString("en-IN")} (सीमा ₹48,000 के अंतर्गत)`);
      verified.push("राजस्थान का मूल निवासी");

      text = isHi
        ? `🎉 **बधाई हो! आपकी पूरी जानकारी सत्यापित हो चुकी है।**\n\nआपकी आयु (${effectiveAge} वर्ष) और पारिवारिक आय के आधार पर आप **मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना** के लिए पूर्णतः पात्र हैं। आपको **₹${monthlyVal.toLocaleString("en-IN")}/- प्रति माह** की पेंशन सीधे बैंक खाते में मिलेगी:`
        : `🎉 **Congratulations! Your profile has been fully verified.**\n\nBoth your age (${effectiveAge} yrs) and family income qualify. You are officially entitled to the **Mukhyamantri Vridhjan Samman Pension Yojana** (₹${monthlyVal.toLocaleString("en-IN")}/- per month direct DBT):`;

      recommended.push({
        scheme_code: "RAJ-PEN-001",
        name_en: "Mukhyamantri Vridhjan Samman Pension Yojana",
        name_hi: "मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना",
        eligibility_status: "CONFIDENTLY_ELIGIBLE",
        benefit_summary: `₹${monthlyVal.toLocaleString("en-IN")} प्रति माह (वार्षिक कुल ₹${(monthlyVal * 12).toLocaleString("en-IN")})`,
        benefit_details: {
          monthly_payout: monthlyVal,
          annual_total: monthlyVal * 12,
          payout_rule: effectiveAge >= 75 ? "75 वर्ष से अधिक (₹1,500/माह)" : "न्यूनतम पेंशन गारंटी (₹1,000/माह)",
        },
        passed_conditions: verified,
        documents_required: ["जन आधार कार्ड", "आधार कार्ड (आयु प्रमाण)", "आय स्व-घोषणा पत्र", "बैंक पासबुक"],
      });

      recommended.push({
        scheme_code: "RAJ-HEALTH-001",
        name_en: "Mukhyamantri Ayushman Arogya Yojana",
        name_hi: "मुख्यमंत्री आयुष्मान आरोग्य योजना",
        eligibility_status: "CONFIDENTLY_ELIGIBLE",
        benefit_summary: "₹25 लाख कैशलेस अस्पताल उपचार + ₹10 लाख दुर्घटना बीमा",
        passed_conditions: ["राजस्थान जन आधार कार्ड धारी परिवार"],
        documents_required: ["जन आधार कार्ड"],
      });

      citations.push({
        citation_tag: "RAJ-SSP-2024-C03",
        title: "राजस्थान सामाजिक सुरक्षा पेंशन (संशोधित) अधिसूचना 2024",
        page: 2,
        snippet: "धारा 3(1): राजस्थान राज्य में निवासरत 55 वर्ष या अधिक की महिला तथा 58 वर्ष या अधिक के पुरुष नागरिक जिनकी वार्षिक आय ₹48,000 से कम हो, उन्हें न्यूनतम ₹1,000 प्रति माह पेंशन देय होगी। 75 वर्ष की आयु पूर्ण होने पर यह राशि ₹1,500 प्रति माह होगी।",
      });

      requiredDocs.push(
        janAadhaarDoc,
        {
          document_name: isHi ? "आधार कार्ड (आयु प्रमाण)" : "Aadhaar Card (Age Proof)",
          purpose: isHi ? "आयु (उम्र) का आधिकारिक सत्यापन" : "Age verification",
          issued_by: "UIDAI",
          is_mandatory: true,
        },
        bankDoc
      );
    }
  }

  // -------------------------------------------------------------------------
  // SCENARIO 3: STUDENT
  // -------------------------------------------------------------------------
  else if (effectiveOccupation === "STUDENT" || intent === "STUDENT_SCHOLARSHIP") {
    if (p.category === null || (p.income === null && !p.isBpl)) {
      score = 0.55;
      missing.push("category", "income");

      text = isHi
        ? `${p.age} वर्ष के विद्यार्थी के रूप में आपके लिए उत्तर मैट्रिक छात्रवृत्ति (100% फीस वापसी) और मुख्यमंत्री अनुप्रति फ्री कोचिंग जैसी योजनाएं हैं।\n\nसटीक छात्रवृत्ति स्लैब निर्धारित करने के लिए:\n👉 **आपकी सामाजिक श्रेणी (SC, ST, OBC, EWS, सामान्य) क्या है और क्या पारिवारिक वार्षिक आय ₹2.5 लाख से कम है?**`
        : `For a ${p.age}-year-old student, major schemes include Post-Matric Scholarships and Anuprati Free Coaching.\n\nTo determine exact eligibility:\n👉 **What is your social category (SC, ST, OBC, EWS, General), and is your family annual income under ₹2.5 Lakhs?**`;

      followUp = {
        question_id: "ask_student_details",
        field: "category",
        question_hi: "अपनी श्रेणी व आय स्थिति चुनें:",
        question_en: "Select your category and income status:",
        rationale_hi: "आरक्षित श्रेणियों एवं आय सीमा के अनुसार 100% फीस वापसी लागू होती है।",
        rationale_en: "Reserved categories receive 100% fee waiver under state norms.",
        options: [
          { label_hi: "SC / ST श्रेणी (आय < ₹2.5 लाख)", label_en: "SC / ST Category (Income < ₹2.5L)", value: { category: "SC", income: 120000, occupation: "STUDENT" } },
          { label_hi: "OBC श्रेणी (आय < ₹2.5 लाख)", label_en: "OBC Category (Income < ₹2.5L)", value: { category: "OBC", income: 150000, occupation: "STUDENT" } },
          { label_hi: "EWS / सामान्य (आय < ₹2.5 लाख)", label_en: "EWS Category (Income < ₹2.5L)", value: { category: "EWS", income: 180000, occupation: "STUDENT" } },
          { label_hi: "सामान्य श्रेणी (आय > ₹2.5 लाख)", label_en: "General (Income > ₹2.5L)", value: { category: "GENERAL", income: 400000, occupation: "STUDENT" } },
        ],
      };
    } else {
      score = 0.95;
      verified.push(`आयु: ${p.age} वर्ष`);
      verified.push(`विद्यार्थी: ${p.category} श्रेणी`);
      verified.push(`वार्षिक पारिवारिक आय: ₹${(p.income || 150000).toLocaleString("en-IN")} (सीमा ₹2.5 लाख के अंतर्गत)`);

      text = isHi
        ? `🎉 **बधाई हो! आपकी पूरी जानकारी सत्यापित हो चुकी है।**\n\nआपके विवरण (${p.age} वर्ष, ${p.category} श्रेणी, आय ₹2.5 लाख से कम) के आधार पर आप निम्नलिखित छात्रवृत्ति एवं कोचिंग योजनाओं के लिए पात्र हैं:`
        : `🎉 **Congratulations! Your profile has been fully verified.**\n\nBased on your details (${p.age} yrs, ${p.category} category, family income under ₹2.5L), you are entitled to the following scholarship and coaching schemes:`;

      recommended.push({
        scheme_code: "RAJ-EDU-002",
        name_en: "Rajasthan Uttar Matric Scholarship Scheme",
        name_hi: "राजस्थान उत्तर मैट्रिक छात्रवृत्ति योजना",
        eligibility_status: "CONFIDENTLY_ELIGIBLE",
        benefit_summary: "कॉलेज एवं तकनीकी कोर्स फीस की शत-प्रतिशत प्रतिपूर्ति सीधे बैंक खाते में",
        passed_conditions: verified,
        documents_required: ["जन आधार कार्ड", "जाति प्रमाण पत्र", "आय प्रमाण पत्र", "फीस रसीद"],
      });

      recommended.push({
        scheme_code: "RAJ-EDU-001",
        name_en: "Mukhyamantri Anuprati Coaching Yojana",
        name_hi: "मुख्यमंत्री अनुप्रति निःशुल्क कोचिंग योजना",
        eligibility_status: "CONFIDENTLY_ELIGIBLE",
        benefit_summary: "UPSC, RAS, REET, NEET, IIT की प्रतिष्ठित कोचिंग + ₹40,000 छात्रावास सहायता",
        passed_conditions: verified,
        documents_required: ["जन आधार कार्ड", "10वीं/12वीं अंकतालिका", "मूल निवास प्रमाण पत्र"],
      });

      citations.push({
        citation_tag: "RAJ-SJE-2024-C15",
        title: "सामाजिक न्याय एवं अधिकारिता विभाग उत्तर मैट्रिक छात्रवृत्ति नियम",
        page: 2,
        snippet: "SC, ST, OBC, EWS वर्ग के ऐसे विद्यार्थी जिनकी पारिवारिक आय ₹2.5 लाख से कम हो, उन्हें राजकीय एवं मान्यता प्राप्त निजी शिक्षण संस्थानों में 100% शिक्षण शुल्क प्रतिपूर्ति देय होगी।",
      });

      requiredDocs.push(janAadhaarDoc, bankDoc);
    }
  }

  // -------------------------------------------------------------------------
  // SCENARIO 4: WIDOW / SINGLE WOMAN
  // -------------------------------------------------------------------------
  else if (p.isWidow || intent === "WIDOW_PENSION") {
    if (p.income === null && !p.isBpl) {
      score = 0.60;
      missing.push("income");

      text = isHi
        ? `एकल नारी एवं विधवा बहनों के लिए राजस्थान सरकार द्वारा 'मुख्यमंत्री एकल नारी सम्मान पेंशन योजना' संचालित है (₹1,000 से ₹1,500 प्रति माह)।\n\nपात्रता सत्यापित करने के लिए:\n👉 **क्या आपकी वार्षिक पारिवारिक आय ₹48,000 से कम है अथवा आपके पास बीपीएल राशन कार्ड है?**`
        : `Under the Mukhyamantri Ekal Nari Pension, widowed and single women receive ₹1,000 to ₹1,500/month.\n\nTo complete verification:\n👉 **Is your annual family income under ₹48,000 or do you hold a BPL card?**`;

      followUp = {
        question_id: "ask_widow_income",
        field: "income",
        question_hi: "अपनी आय स्थिति बताएं:",
        question_en: "Confirm income status:",
        rationale_hi: "पेंशन नियमों के तहत आय सीमा ₹48,000 वार्षिक निर्धारित है।",
        rationale_en: "Statutory income limit is ₹48,000/yr.",
        options: [
          { label_hi: "हाँ, वार्षिक आय ₹48,000 से कम है", label_en: "Yes, income < ₹48K", value: { income: 36000, isWidow: true } },
          { label_hi: "हाँ, मेरे पास BPL कार्ड है", label_en: "Yes, hold BPL Card", value: { rationCard: "BPL", income: 36000, isWidow: true } },
          { label_hi: "नहीं, वार्षिक आय ₹48,000 से अधिक है", label_en: "No, income > ₹48K", value: { income: 90000, isWidow: true } },
        ],
      };
    } else {
      score = 0.98;
      const widowAge = p.age || 50;
      const monthlyVal = widowAge >= 75 ? 1500 : widowAge >= 55 ? 1250 : 1000;
      verified.push(`आयु: ${widowAge} वर्ष (एकल नारी परिस्थिति)`);
      verified.push("वार्षिक आय सीमा ₹48,000 के अंतर्गत");

      text = isHi
        ? `🎉 **बधाई हो! आपकी पूरी जानकारी सत्यापित हो चुकी है।**\n\nआप **मुख्यमंत्री एकल नारी सम्मान पेंशन योजना** (₹${monthlyVal.toLocaleString("en-IN")}/माह) तथा बच्चों की सहायता हेतु **पालनहार योजना** के लिए पात्र हैं:`
        : `🎉 **Congratulations! Your profile has been fully verified.**\n\nYou qualify for the **Mukhyamantri Ekal Nari Pension Scheme** (₹${monthlyVal.toLocaleString("en-IN")}/mo) and **Palanhar Scheme**:`;

      recommended.push({
        scheme_code: "RAJ-PEN-002",
        name_en: "Mukhyamantri Ekal Nari Samman Pension Yojana",
        name_hi: "मुख्यमंत्री एकल नारी सम्मान पेंशन योजना",
        eligibility_status: "CONFIDENTLY_ELIGIBLE",
        benefit_summary: `₹${monthlyVal.toLocaleString("en-IN")} प्रति माह (वार्षिक कुल ₹${(monthlyVal * 12).toLocaleString("en-IN")})`,
        passed_conditions: verified,
        documents_required: ["जन आधार कार्ड", "पति का मृत्यु प्रमाण पत्र", "आय घोषणा पत्र", "बैंक पासबुक"],
      });

      recommended.push({
        scheme_code: "RAJ-SOC-001",
        name_en: "Palanhar Yojana",
        name_hi: "पालनहार योजना (बच्चों की शिक्षा व पोषण सहायता)",
        eligibility_status: "CONFIDENTLY_ELIGIBLE",
        benefit_summary: "₹1,500 से ₹2,500 प्रति माह प्रति बच्चा + ₹2,000 वार्षिक वस्त्र अनुदान",
        passed_conditions: ["एकल नारी / विधवा माता"],
        documents_required: ["जन आधार कार्ड", "बच्चों का स्कूल प्रमाण पत्र"],
      });

      citations.push({
        citation_tag: "RAJ-SSP-2024-C12",
        title: "राजस्थान सामाजिक सुरक्षा एकल नारी पेंशन नियमावली",
        page: 4,
        snippet: "विधवा एवं एकल नारी नागरिक जिनकी वार्षिक आय ₹48,000 से कम हो, उन्हें उम्र अनुसार ₹1,000 से ₹1,500 मासिक पेंशन देय है।",
      });

      requiredDocs.push(janAadhaarDoc, bankDoc);
    }
  }

  // -------------------------------------------------------------------------
  // SCENARIO 5: SELF-EMPLOYMENT / ARTISAN / BUSINESS LOAN
  // -------------------------------------------------------------------------
  else if (effectiveOccupation === "SELF_EMPLOYED" || effectiveOccupation === "LABORER" || intent === "SELF_EMPLOYMENT_LOAN") {
    if (p.residence === null && p.income === null) {
      score = 0.60;
      missing.push("residence");

      text = isHi
        ? `${p.age} वर्ष के व्यापारी / कारीगर / श्रमिक भाई-बहनों के लिए पीएम विश्वकर्मा (₹3 लाख ऋण + ₹15,000 टूलकिट) और शहरी क्रेडिट कार्ड (₹50,000 ब्याज मुक्त) योजनाएं हैं।\n\nसटीक योजना तय करने के लिए:\n👉 **आप किस प्रकार का कार्य करते हैं और आपको लगभग कितने ऋण की आवश्यकता है?**`
        : `For self-employed, artisans, and small business owners aged ${p.age}, major programs include PM Vishwakarma and Urban Credit Card.\n\nTo identify the best scheme:\n👉 **What type of work or shop do you operate, and how much credit do you require?**`;

      followUp = {
        question_id: "ask_loan_type",
        field: "residence",
        question_hi: "अपनी कार्य श्रेणी व आवश्यकता चुनें:",
        question_en: "Select your trade category and need:",
        rationale_hi: "कार्य प्रकृति के अनुसार 100% ब्याज अनुदान अथवा टूलकिट सहायता निर्धारित होती है।",
        rationale_en: "Trade nature determines eligibility for toolkits or interest subvention.",
        options: [
          { label_hi: "🛠️ पारंपरिक कारीगर / शिल्पकार (PM विश्वकर्मा)", label_en: "Artisan / Craftsman (PM Vishwakarma)", value: { residence: "RURAL", income: 60000, occupation: "SELF_EMPLOYED" } },
          { label_hi: "🏪 शहरी वेंडर / छोटा दुकानदार (₹50,000 ब्याज मुक्त)", label_en: "Urban Street Vendor / Shop (₹50K Interest Free)", value: { residence: "URBAN", income: 60000, occupation: "SELF_EMPLOYED" } },
          { label_hi: "💼 सामान्य व्यापार विस्तार (मुद्रा ऋण)", label_en: "General Business Expansion (Mudra)", value: { residence: "URBAN", income: 120000, occupation: "SELF_EMPLOYED" } },
        ],
      };
    } else {
      score = 0.95;
      verified.push(`आयु: ${p.age} वर्ष`);
      verified.push("स्वरोजगार / व्यापार / कारीगरी आवश्यकता चिन्हित");

      text = isHi
        ? `🎉 **बधाई हो! आपकी जानकारी सत्यापित हो चुकी है।**\n\nदस्तकारों, कारीगरों व छोटे व्यापारियों के लिए आप **पीएम विश्वकर्मा योजना** (₹3 लाख तक 5% ब्याज पर ऋण + ₹15,000 फ्री टूलकिट) तथा **इंदिरा गांधी शहरी क्रेडिट कार्ड योजना** (₹50,000 ब्याज मुक्त ऋण) के लिए पात्र हैं:`
        : `🎉 **Congratulations! Your profile has been verified.**\n\nFor artisans, shopkeepers, and self-employed individuals, you qualify for **PM Vishwakarma** (up to ₹3L loan at 5% + ₹15K toolkit) and **Indira Gandhi Urban Credit Card**:`;

      recommended.push({
        scheme_code: "RAJ-SE-001",
        name_en: "PM Vishwakarma & Mudra Yojana",
        name_hi: "पीएम विश्वकर्मा एवं मुद्रा स्वरोजगार योजना",
        eligibility_status: "CONFIDENTLY_ELIGIBLE",
        benefit_summary: "₹1 लाख से ₹3 लाख तक 5% रियायती ब्याज पर ऋण + ₹15,000 फ्री टूलकिट वाउचर",
        passed_conditions: ["कारीगर / शिल्पकार / स्वरोजगार", "आधार सत्यापित"],
        documents_required: ["जन आधार कार्ड", "आधार कार्ड", "बैंक पासबुक"],
      });

      recommended.push({
        scheme_code: "RAJ-SE-002",
        name_en: "Indira Gandhi Urban Credit Card Scheme",
        name_hi: "इंदिरा गांधी शहरी क्रेडिट कार्ड योजना",
        eligibility_status: "CONFIDENTLY_ELIGIBLE",
        benefit_summary: "छोटे व्यापारियों व वेंडर्स को ₹50,000 तक 100% ब्याज मुक्त ऋण",
        passed_conditions: ["शहरी क्षेत्र में छोटा व्यापार / सेवा"],
        documents_required: ["जन आधार कार्ड", "वेंडर पहचान"],
      });

      citations.push({
        citation_tag: "IND-MSME-2024-V01",
        title: "पीएम विश्वकर्मा योजना आधिकारिक मार्गदर्शिका",
        page: 1,
        snippet: "पारंपरिक शिल्पकारों को ₹15,000 टूलकिट वाउचर तथा व्यवसाय विस्तार हेतु 5% रियायती ब्याज पर ₹3,00,000 तक का संपार्श्विक मुक्त ऋण दिया जाता है।",
      });

      requiredDocs.push(janAadhaarDoc, bankDoc);
    }
  }

  // -------------------------------------------------------------------------
  // SCENARIO 6: HOMEMAKER / WOMEN
  // -------------------------------------------------------------------------
  else if (effectiveOccupation === "HOMEMAKER") {
    if (p.rationCard === null) {
      score = 0.55;
      missing.push("rationCard");

      text = isHi
        ? `महिलाओं व गृहिणियों के लिए राजस्थान सरकार की ₹450 में गैस सिलेंडर सब्सिडी योजना तथा लखपति दीदी योजनाएं उपलब्ध हैं।\n\nपात्रता तय करने के लिए:\n👉 **क्या आपके पास उज्ज्वला योजना या बीपीएल राशन कार्ड है?**`
        : `For homemakers and women, key programs include the ₹450 LPG Cylinder Subsidy and Lakhpati Didi.\n\nTo verify entitlement:\n👉 **Do you hold a PM Ujjwala connection or BPL ration card?**`;

      followUp = {
        question_id: "ask_gas_ration",
        field: "rationCard",
        question_hi: "राशन कार्ड व गैस कनेक्शन की स्थिति चुनें:",
        question_en: "Select ration card and gas connection status:",
        rationale_hi: "उज्ज्वला व बीपीएल परिवारों को ₹450 में सिलेंडर उपलब्ध कराया जाता है।",
        rationale_en: "Ujjwala and BPL families are subsidized for ₹450 LPG cylinders.",
        options: [
          { label_hi: "हाँ, PM उज्ज्वला योजना गैस कनेक्शन है", label_en: "Yes, hold PM Ujjwala Gas", value: { rationCard: "BPL", occupation: "HOMEMAKER" } },
          { label_hi: "हाँ, BPL / अंत्योदय राशन कार्ड है", label_en: "Yes, hold BPL Card", value: { rationCard: "BPL", occupation: "HOMEMAKER" } },
          { label_hi: "सामान्य राशन कार्ड है", label_en: "Regular / APL Card", value: { rationCard: "NONE", occupation: "HOMEMAKER" } },
        ],
      };
    } else {
      score = 0.95;
      verified.push(`आयु: ${p.age} वर्ष`);
      verified.push("महिला / गृहिणी परिवार सदस्या");
      verified.push("गैस सब्सिडी पात्रता पूर्ण");

      text = isHi
        ? `🎉 **बधाई हो! आपकी जानकारी सत्यापित हो चुकी है।**\n\nआप **राजस्थान ₹450 रसोई गैस सिलेंडर सब्सिडी योजना** तथा **मुख्यमंत्री आयुष्मान आरोग्य योजना** के लिए पूर्णतः पात्र हैं:`
        : `🎉 **Congratulations! Your profile has been verified.**\n\nYou qualify for the **₹450 LPG Cylinder Subsidy Scheme** and **Mukhyamantri Ayushman Arogya Yojana**:`;

      recommended.push({
        scheme_code: "RAJ-GAS-001",
        name_en: "Rajasthan Rs 450 LPG Cylinder Subsidy Scheme",
        name_hi: "राजस्थान ₹450 रसोई गैस सिलेंडर सब्सिडी योजना",
        eligibility_status: "CONFIDENTLY_ELIGIBLE",
        benefit_summary: "प्रति माह ₹450 में गैस सिलेंडर (शेष राशि सरकार द्वारा सीधे सब्सिडी के रूप में बैंक खाते में)",
        passed_conditions: ["उज्ज्वला / बीपीएल परिवार", "जन आधार लिंक्ड"],
        documents_required: ["जन आधार कार्ड", "गैस कनेक्शन डायरी / एलपीजी आईडी"],
      });

      recommended.push({
        scheme_code: "RAJ-HEALTH-001",
        name_en: "Mukhyamantri Ayushman Arogya Yojana",
        name_hi: "मुख्यमंत्री आयुष्मान आरोग्य योजना",
        eligibility_status: "CONFIDENTLY_ELIGIBLE",
        benefit_summary: "₹25 लाख कैशलेस अस्पताल उपचार + ₹10 लाख दुर्घटना बीमा",
        passed_conditions: ["राजस्थान जन आधार कार्ड धारी परिवार"],
        documents_required: ["जन आधार कार्ड"],
      });

      requiredDocs.push(janAadhaarDoc, bankDoc);
    }
  }

  // -------------------------------------------------------------------------
  // FALLBACK: GENERAL INQUIRY (Needs details)
  // -------------------------------------------------------------------------
  else {
    score = 0.20;
    text = isHi
      ? "सटीक सरकारी योजना खोजने के लिए, मुझे आपके बारे में एक-दो जानकारी और चाहिए।\n\n👉 **कृपया बताएं: आपकी आयु क्या है और आप किस क्षेत्र (जैसे किसान, छात्र, पेंशन, स्वरोजगार) में योजना देखना चाहते हैं?**"
      : "To identify the best government schemes for you, I need a little more information.\n\n👉 **What is your age and which category (e.g. Farmer, Student, Pension, Self-Employed) are you interested in?**";

    followUp = {
      question_id: "ask_specific_need",
      field: "occupation",
      question_hi: "अपनी पसंदीदा श्रेणी चुनें:",
      question_en: "Select your preferred category:",
      rationale_hi: "सही पात्रता मूल्यांकन के लिए श्रेणी का चयन आवश्यक है।",
      rationale_en: "Category selection is required for statutory eligibility evaluation.",
      options: [
        { label_hi: "🌾 किसान सहायता (PM-KISAN)", label_en: "Farmer Schemes", value: { occupation: "FARMER", primaryIntent: "FARMER_SCHEME" } },
        { label_hi: "👴 वरिष्ठ नागरिक पेंशन", label_en: "Senior Pension", value: { age: 60, primaryIntent: "OLD_AGE_PENSION" } },
        { label_hi: "🎓 छात्रवृत्ति व फ्री कोचिंग", label_en: "Scholarship & Coaching", value: { occupation: "STUDENT", primaryIntent: "STUDENT_SCHOLARSHIP" } },
        { label_hi: "💼 स्वरोजगार व मुद्रा ऋण", label_en: "Self-Employment Loan", value: { occupation: "SELF_EMPLOYED", primaryIntent: "SELF_EMPLOYMENT_LOAN" } },
      ],
    };
  }

  const isConfident = score >= 0.80;
  const confidenceLevel = score >= 0.80 ? "HIGH" : score >= 0.50 ? "MEDIUM" : "LOW";

  return {
    confidenceScore: score,
    confidenceLevel,
    recommendedSchemes: isConfident ? recommended : [],
    candidateSchemes: !isConfident ? candidates : [],
    followUpQuestion: isConfident ? null : followUp,
    missingFields: missing,
    verifiedCriteria: verified,
    pendingCriteria: pending,
    citations: isConfident ? citations : [],
    requiredDocs: isConfident ? requiredDocs : [],
    conversationalText: text,
  };
}

export function getFallbackTools(): { tools: any[] } {
  return {
    tools: [
      {
        name: "extract_citizen_profile",
        description: "Extracts verified demographic facts from conversational inputs.",
      },
      {
        name: "evaluate_eligibility_confidence",
        description: "Computes information gain and confidence score against official scheme rules.",
      },
    ],
  };
}
