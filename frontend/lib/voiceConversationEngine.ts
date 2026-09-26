/**
 * Conversational Multi-Turn Dialogue Engine for YojanSetu Voice Assistant.
 * Maintains dialogue state, tracks question context, extracts entities,
 * asks intelligent targeted follow-ups, and speaks concise natural answers.
 */

import {
  RAJASTHAN_FLAGSHIP_SCHEMES,
  RajasthanSchemeItem,
} from './rajasthanSchemesData';
import { CitizenSchemeCard } from '@/types/citizen';

export interface DialogueProfile {
  age?: number;
  gender?: 'MALE' | 'FEMALE';
  annual_income?: number;
  income_confirmed?: boolean;
  occupation?: 'FARMER' | 'STUDENT' | 'DAILY_WAGE' | 'OTHER';
  land_area_bigha?: number;
  marital_status?: 'WIDOWED' | 'DIVORCED' | 'MARRIED' | 'SINGLE';
  is_widow?: boolean;
  is_student?: boolean;
  exam_name?: string;
  has_school_child?: boolean;
  is_disabled?: boolean;
  is_bpl?: boolean;
  is_ujjwala_beneficiary?: boolean;
  has_jan_aadhaar?: boolean;
  caste_category?: 'SC' | 'ST' | 'OBC' | 'MBC' | 'EWS' | 'GEN';
  district?: string;
  intent?: 'PENSION' | 'FARMER' | 'HEALTHCARE' | 'STUDENT' | 'WIDOW' | 'CYLINDER' | 'DISABILITY' | 'DAILY_WAGE' | 'GENERAL';
  pension_type?: 'VRIDHJAN' | 'WIDOW' | 'DISABILITY';
  wants_documents?: boolean;
  lastQuestionField?: string;
  stage?: 'GREETING' | 'COLLECTING' | 'RECOMMENDING' | 'DOCUMENT_INQUIRY' | 'COMPLETED';
}

export interface DialogueTurnResult {
  spokenReply: string;       // Crisp, natural speech optimized for voice synthesis
  displayReply: string;      // Formatted text for the screen card
  updatedProfile: DialogueProfile;
  eligibleSchemes: RajasthanSchemeItem[];
  moreInfoSchemes: RajasthanSchemeItem[];
  suggestedChips: Array<{ label_hi: string; label_en: string; text: string }>;
  isComplete: boolean;       // True if schemes have been confidently determined
  missingField?: string;
}

/**
 * Checks if user affirmation ("हाँ", "yes", "जी हाँ", "कम है", "बताओ") is present.
 */
export function isAffirmative(text: string): boolean {
  const clean = text.trim();
  return /^(हाँ|हां|हाँजी|जी\s*हाँ|हाँ\s*है|हाँ\s*कम\s*है|कम\s*है|कम|बिलकुल|सही|बताओ|दिखाओ|बताएं|बताइए|दिखाइए|ज़रूर|जरूर|yes|yep|yeah|sahi|sahi\s*hai|kam\s*hai|hota\s*hai|hoga|hai|sure|tell|show)/i.test(clean) ||
         /\b(yes|yeah|haan|ha|ji\s*ha|kam|below|under|sure|batao|dikhao)\b/i.test(clean);
}

/**
 * Checks if user negative ("नहीं", "no", "nahin", "ज्यादा है") is present.
 */
export function isNegative(text: string): boolean {
  const clean = text.trim();
  return /^(नहीं|ना|नाही|नाजी|ज्यादा|अधिक|ज्यादा\s*है|नहीं\s*है|no|nahin|na|nahi|never|not|zyada)/i.test(clean) ||
         /\b(no|not|nahin|nahi|zyada|more|above|exceed)\b/i.test(clean);
}

export function parseHindiOrArabicNumber(str: string): number | null {
  // Check Arabic digits
  const digitMatch = str.match(/\b(\d+(?:\.\d+)?)\b/);
  if (digitMatch) {
    const val = parseFloat(digitMatch[1]);
    if (!isNaN(val)) return val;
  }

  // Check Devanagari digits (०-९)
  const devanagariDigits = ['०', '१', '२', '३', '४', '५', '६', '७', '८', '९'];
  let devStr = '';
  for (const char of str) {
    const idx = devanagariDigits.indexOf(char);
    if (idx !== -1) devStr += idx;
  }
  if (devStr.length > 0) {
    const val = parseInt(devStr, 10);
    if (!isNaN(val)) return val;
  }

  // Check Hindi word numbers
  const hindiWords: Array<[RegExp, number]> = [
    [/(?:पिच्यासी|85)/, 85],
    [/(?:अस्सी|80)/, 80],
    [/(?:पिचहत्तर|75)/, 75],
    [/(?:सत्तर|70)/, 70],
    [/(?:पैंसठ|पिंसठ|65)/, 65],
    [/(?:चौंसठ|64)/, 64],
    [/(?:तिरेसठ|63)/, 63],
    [/(?:बासठ|62)/, 62],
    [/(?:इकसठ|61)/, 61],
    [/(?:साठ|60)/, 60],
    [/(?:उनसठ|59)/, 59],
    [/(?:अट्ठवन|58)/, 58],
    [/(?:सत्तावन|57)/, 57],
    [/(?:छप्पन|56)/, 56],
    [/(?:पचपन|55)/, 55],
    [/(?:चौवन|54)/, 54],
    [/(?:तिरपन|53)/, 53],
    [/(?:बावन|52)/, 52],
    [/(?:इक्यावन|51)/, 51],
    [/(?:पचास|50)/, 50],
    [/(?:पैंतालीस|45)/, 45],
    [/(?:चालीस|40)/, 40],
    [/(?:पैंतीस|35)/, 35],
    [/(?:तीस|30)/, 30],
    [/(?:पच्चीस|25)/, 25],
    [/(?:बीस|20)/, 20],
    [/(?:उन्नीस|19)/, 19],
    [/(?:अट्ठारह|18)/, 18],
    [/(?:सत्रह|17)/, 17],
    [/(?:सोलह|16)/, 16],
    [/(?:पंद्रह|15)/, 15],
    [/(?:चौदह|14)/, 14],
    [/(?:तेरह|13)/, 13],
    [/(?:बारह|12)/, 12],
    [/(?:ग्यारह|11)/, 11],
    [/(?:दस|10)/, 10],
    [/(?:नौ|9)/, 9],
    [/(?:आठ|8)/, 8],
    [/(?:सात|7)/, 7],
    [/(?:छह|6)/, 6],
    [/(?:पांच|पाँच|5)/, 5],
    [/(?:चार|4)/, 4],
    [/(?:तीन|3)/, 3],
    [/(?:दो|2)/, 2],
    [/(?:एक|1)/, 1],
  ];

  for (const [re, num] of hindiWords) {
    if (re.test(str)) return num;
  }
  return null;
}

/**
 * Extracts and accumulates demographic entities from natural speech in Hindi & English,
 * resolving conversational context based on what the AI previously asked.
 */
export function extractProfileFromUtterance(
  text: string,
  existingProfile: DialogueProfile = {}
): DialogueProfile {
  const profile: DialogueProfile = { ...existingProfile };
  const lower = text.toLowerCase();
  const lastField = profile.lastQuestionField;

  // -------------------------------------------------------------
  // STEP A: Context-aware Affirmation / Negation based on prior question
  // -------------------------------------------------------------
  if (lastField) {
    // 1. Follow-up to "क्या आप ज़रूरी दस्तावेज़ देखना चाहते हैं?"
    if (lastField === 'wants_documents') {
      if (isAffirmative(text) || /दस्तावेज़|कागज़|बताओ|दिखाओ|बताएं|yes|sure/i.test(text)) {
        profile.wants_documents = true;
      } else if (isNegative(text)) {
        profile.wants_documents = false;
      }
    }

    // 2. Follow-up to Annual Income question ("क्या आपकी आय ₹48,000 से कम है?")
    if (lastField === 'annual_income') {
      if (isAffirmative(text)) {
        profile.annual_income = 40000;
        profile.income_confirmed = true;
      } else if (isNegative(text)) {
        profile.annual_income = 100000;
        profile.income_confirmed = false;
      }
    }

    // 3. Follow-up to Land Area question
    if (lastField === 'land_area_bigha') {
      if (isNegative(text) || /ज़मीन\s*नहीं|जमीन\s*नहीं|भूमिहीन|लैंड\s*नहीं|zero|शून्य/i.test(text)) {
        profile.land_area_bigha = 0;
      } else if (isAffirmative(text) && profile.land_area_bigha === undefined) {
        profile.land_area_bigha = 3.0;
        profile.occupation = 'FARMER';
        profile.intent = 'FARMER';
      }
      const num = parseHindiOrArabicNumber(text);
      if (num !== null && num >= 0 && num <= 500) {
        profile.land_area_bigha = num;
        profile.occupation = 'FARMER';
        profile.intent = 'FARMER';
      }
    }

    // 4. Follow-up to Age questions
    if (lastField === 'age' || lastField === 'age_or_pension_type' || lastField === 'age_or_occupation') {
      const num = parseHindiOrArabicNumber(text);
      if (num !== null && num >= 10 && num <= 110) {
        profile.age = num;
      } else if (isAffirmative(text) && lastField === 'age') {
        // e.g. "क्या आपकी आयु 58 वर्ष या उससे अधिक है?" -> "हाँ"
        profile.age = 60;
      } else if (isNegative(text) && lastField === 'age') {
        // e.g. "क्या आपकी आयु 58 वर्ष या उससे अधिक है?" -> "नहीं"
        profile.age = 45;
      }
    }

    // 5. Follow-up to Pension selection question
    if (lastField === 'age_or_pension_type') {
      if (/वृद्ध|बुजुर्ग|old|senior|vridhjan/i.test(text)) {
        profile.intent = 'PENSION';
        profile.pension_type = 'VRIDHJAN';
      } else if (/विधवा|एकल नारी|पति|widow/i.test(text)) {
        profile.is_widow = true;
        profile.marital_status = 'WIDOWED';
        profile.gender = 'FEMALE';
        profile.intent = 'WIDOW';
      } else if (/दिव्यांग|विकलांग|disabled|special/i.test(text)) {
        profile.is_disabled = true;
        profile.intent = 'DISABILITY';
      }
    }

    // 6. Follow-up to Palanhar Child question
    if (lastField === 'has_school_child') {
      if (isAffirmative(text) || /बच्चे|child|school|पढ़ते/i.test(text)) {
        profile.has_school_child = true;
      } else if (isNegative(text)) {
        profile.has_school_child = false;
      }
    }

    // 7. Follow-up to Gas Cylinder BPL / Ujjwala question
    if (lastField === 'is_bpl_or_ujjwala') {
      if (isAffirmative(text) || /उज्ज्वला|बीपीएल|गैस|कनेक्शन/i.test(text)) {
        profile.is_ujjwala_beneficiary = true;
        profile.is_bpl = true;
      } else if (isNegative(text)) {
        profile.is_ujjwala_beneficiary = false;
        profile.is_bpl = false;
      }
    }

    // 8. Follow-up to Disability Certificate question
    if (lastField === 'is_disabled') {
      if (isAffirmative(text) || /40%|udid|सर्टिफिकेट|प्रमाण\s*पत्र|है/i.test(text)) {
        profile.is_disabled = true;
      } else if (isNegative(text)) {
        profile.is_disabled = false;
      }
    }

    // 8b. Follow-up to Caste Category question
    if (lastField === 'caste_category') {
      if (/obc|ओबीसी|अन्य\s*पिछड़ा|पिछड़ा/i.test(text)) profile.caste_category = 'OBC';
      else if (/sc|एससी|अनुसूचित\s*जाति/i.test(text)) profile.caste_category = 'SC';
      else if (/st|एसटी|अनुसूचित\s*जनजाति/i.test(text)) profile.caste_category = 'ST';
      else if (/mbc|एमबीसी|अति\s*पिछड़ा/i.test(text)) profile.caste_category = 'MBC';
      else if (/ews|ईडब्ल्यूएस|आर्थिक\s*कमजोर/i.test(text)) profile.caste_category = 'EWS';
      else if (/general|सामान्य|जनरल/i.test(text)) profile.caste_category = 'GEN';
    }

    // 9. Follow-up to Target Exam question
    if (lastField === 'exam_name') {
      if (/reet|रीट|शिक्षक|teacher/i.test(text)) profile.exam_name = 'REET';
      else if (/upsc|ras|ias|आरएएस|आईएएस|सिविल/i.test(text)) profile.exam_name = 'RAS/UPSC';
      else if (/neet|नीट|mbbs|medical|डॉक्टर/i.test(text)) profile.exam_name = 'NEET';
      else if (/iit|jee|engineering|इंजीनियर/i.test(text)) profile.exam_name = 'IIT-JEE';
      else if (/कॉलेज|college|degree|स्नातक/i.test(text)) profile.exam_name = 'COLLEGE';
    }

    // 10. Follow-up to Woman Scheme Choice question
    if (lastField === 'woman_scheme_choice') {
      if (/विधवा|एकल नारी|पति\s*नहीं|widow/i.test(text)) {
        profile.is_widow = true;
        profile.marital_status = 'WIDOWED';
        profile.gender = 'FEMALE';
        profile.intent = 'WIDOW';
      } else if (/सिलेंडर|गैस|उज्ज्वला|lpg/i.test(text)) {
        profile.is_ujjwala_beneficiary = true;
        profile.intent = 'CYLINDER';
      } else if (/बच्चे|पालनहार/i.test(text)) {
        profile.has_school_child = true;
        profile.intent = 'WIDOW';
      }
    }

    // 11. Follow-up to Occupation or General Demographic question
    if (lastField === 'occupation' || lastField === 'age_or_occupation') {
      if (/किसान|खेती|कृषक|farmer/i.test(text)) {
        profile.occupation = 'FARMER';
        profile.intent = 'FARMER';
      } else if (/विद्यार्थी|छात्र|छात्रा|student|पढ़ाई/i.test(text)) {
        profile.is_student = true;
        profile.occupation = 'STUDENT';
        profile.intent = 'STUDENT';
      } else if (/महिला|गृहिणी|औरत|woman|housewife/i.test(text)) {
        profile.gender = 'FEMALE';
      } else if (/मजदूर|श्रमिक|दैनिक\s*मजदूरी|कारीगर|छोटा\s*व्यापारी|labor|worker/i.test(text)) {
        profile.occupation = 'DAILY_WAGE';
        profile.intent = 'DAILY_WAGE';
      }
    }
  }

  // -------------------------------------------------------------
  // STEP B: Global Entity Extraction from Utterance
  // -------------------------------------------------------------

  // 1. Age extraction
  const ageMatch = text.match(/(\d{1,2})\s*(?:साल|वर्ष|saal|sal|years?|yrs?|की उम्र|आयु)/i) ||
                   text.match(/(?:उम्र|आयु|age)\D*?(\d{1,2})/i);
  if (ageMatch) {
    const parsedAge = parseInt(ageMatch[1], 10);
    if (parsedAge > 0 && parsedAge <= 110) {
      profile.age = parsedAge;
    }
  } else {
    // Check standalone numbers or Hindi word numbers
    const parsed = parseHindiOrArabicNumber(text);
    if (parsed !== null && parsed >= 16 && parsed <= 110 && !profile.age) {
      profile.age = parsed;
    }
  }

  // 2. Gender & Marital Status
  if (/विधवा|पति नहीं|पति की मृत्यु|एकल नारी|widow/i.test(text)) {
    profile.is_widow = true;
    profile.marital_status = 'WIDOWED';
    profile.gender = 'FEMALE';
    profile.intent = 'WIDOW';
  } else if (/तलाकशुदा|परित्यक्ता|divorce|divorced/i.test(text)) {
    profile.marital_status = 'DIVORCED';
    profile.gender = 'FEMALE';
    profile.intent = 'WIDOW';
  }

  if (/महिला|औरत|female|woman|लड़की|माताजी|दादी|गृहिणी/i.test(text)) {
    profile.gender = 'FEMALE';
  } else if (/पुरुष|आदमी|male|man|लड़का|दादाजी|भाई/i.test(text)) {
    profile.gender = 'MALE';
  }

  // 3. Children (for Palanhar)
  if (/बच्चे|बच्चा|बालक|child|children|school|स्कूल/i.test(text)) {
    profile.has_school_child = true;
  }

  // 4. Occupation & Land
  const landMatch = text.match(/(\d+(?:\.\d+)?)\s*(?:बीघा|bigha|एकड़|acre|हेक्टेयर|hectare)/i);
  if (landMatch) {
    profile.land_area_bigha = parseFloat(landMatch[1]);
    profile.occupation = 'FARMER';
    profile.intent = 'FARMER';
  }

  if (/किसान|खेती|कृषक|काश्तकार|फसल|farmer|agriculture/i.test(text)) {
    profile.occupation = 'FARMER';
    profile.intent = 'FARMER';
  }

  if (/मजदूर|श्रमिक|दैनिक\s*मजदूरी|कारीगर|छोटा\s*व्यापारी|labor|worker/i.test(text)) {
    profile.occupation = 'DAILY_WAGE';
    profile.intent = 'DAILY_WAGE';
  }

  // 5. Student & Education
  if (/छात्र|छात्रा|विद्यार्थी|पढ़ाई|कॉलेज|12वीं|neet|iit|coaching|student|study|exam/i.test(text)) {
    profile.is_student = true;
    profile.occupation = 'STUDENT';
    profile.intent = 'STUDENT';
  }

  // 6. Caste Category
  if (/obc|ओबीसी|अन्य\s*पिछड़ा|पिछड़ा/i.test(text)) profile.caste_category = 'OBC';
  else if (/sc|एससी|अनुसूचित\s*जाति/i.test(text)) profile.caste_category = 'SC';
  else if (/st|एसटी|अनुसूचित\s*जनजाति/i.test(text)) profile.caste_category = 'ST';
  else if (/mbc|एमबीसी|अति\s*पिछड़ा/i.test(text)) profile.caste_category = 'MBC';
  else if (/ews|ईडब्ल्यूएस|आर्थिक\s*कमजोर/i.test(text)) profile.caste_category = 'EWS';
  else if (/general|सामान्य|जनरल/i.test(text)) profile.caste_category = 'GEN';

  // 7. Disability
  if (/दिव्यांग|विकलांग|विशेष योग्यजन|handicapped|disabled|40%|अपंग/i.test(text)) {
    profile.is_disabled = true;
    profile.intent = 'DISABILITY';
  }

  // 8. LPG Cylinder / Gas
  if (/गैस|सिलेंडर|cylinder|gas|उज्ज्वला|lpg|450/i.test(text)) {
    profile.is_ujjwala_beneficiary = true;
    profile.intent = 'CYLINDER';
  }

  // 9. BPL & Income
  if (/बीपीएल|bpl|गरीब|अंत्योदय/i.test(text)) {
    profile.is_bpl = true;
    profile.annual_income = 30000;
    profile.income_confirmed = true;
  }

  const incomeMatch = text.match(/(?:आय|कमाई|income)\D*?(\d[\d,]*)/i) ||
                      text.match(/(\d[\d,]*)\s*(?:रुपये|rs|हजार|वार्षिक|सालाना)/i);
  if (incomeMatch) {
    let inc = parseInt(incomeMatch[1].replace(/,/g, ''), 10);
    if (inc < 500) inc = inc * 1000;
    profile.annual_income = inc;
    profile.income_confirmed = inc <= 48000;
  }

  if (/48,?000|48 हजार|कम आय|गरीब परिवार|low income/i.test(text)) {
    profile.annual_income = 40000;
    profile.income_confirmed = true;
  }

  // 10. Jan Aadhaar (default true for Rajasthan citizens)
  if (profile.has_jan_aadhaar === undefined) {
    profile.has_jan_aadhaar = true;
  }

  // 11. Intent classification
  if (!profile.intent) {
    if (/वृद्ध|बुजुर्ग|old age/i.test(text)) {
      profile.intent = 'PENSION';
      profile.pension_type = 'VRIDHJAN';
    } else if (/पेंशन/i.test(text)) {
      profile.intent = 'PENSION';
    } else if (/इलाज|अस्पताल|स्वास्थ्य|दवा|health|hospital|treatment|चिरंजीवी|आरोग्य/i.test(text)) {
      profile.intent = 'HEALTHCARE';
    } else if (/बच्चे|अनाथ|पालनहार|child/i.test(text)) {
      profile.intent = 'WIDOW';
    } else {
      profile.intent = 'GENERAL';
    }
  }

  return profile;
}

/**
 * Executes true multi-turn conversational reasoning:
 * Evaluates demographic facts, identifies missing information, asks targeted follow-ups,
 * and confirms authentic Rajasthan schemes once criteria are met.
 */
export function processDialogueTurn(
  utterance: string,
  existingProfile: DialogueProfile = {},
  lang: 'hi' | 'en' = 'hi'
): DialogueTurnResult {
  const isHi = lang === 'hi';
  const updatedProfile = extractProfileFromUtterance(utterance, existingProfile);

  // Check which TARGETED schemes qualify (excluding universal healthcare MAA for follow-up determination)
  const targetedSchemes = RAJASTHAN_FLAGSHIP_SCHEMES.filter((s) => s.code !== 'RJ-HEALTH-MAA');
  const eligibleTargeted = targetedSchemes.filter((s) => s.isEligible(updatedProfile));

  // Universal MAA healthcare (available to all Rajasthan Jan Aadhaar families)
  const universalMAA = RAJASTHAN_FLAGSHIP_SCHEMES.find((s) => s.code === 'RJ-HEALTH-MAA')!;

  // -------------------------------------------------------------
  // BRANCH 1: User explicitly asks about documents / apply, OR affirmed "हाँ" / "बताओ" to document question
  // -------------------------------------------------------------
  if (
    updatedProfile.wants_documents === true ||
    (updatedProfile.lastQuestionField === 'wants_documents' && (isAffirmative(utterance) || /बताओ|दिखाओ|बताएं|दस्तावेज़|कागज़|yes|sure/i.test(utterance))) ||
    /दस्तावेज़|कागज़|documents?|apply|आवेदन|ई-मित्र|kiosk|फॉर्म/i.test(utterance)
  ) {
    const activeScheme = eligibleTargeted[0] || RAJASTHAN_FLAGSHIP_SCHEMES[0];
    const docsList = activeScheme.mandatory_docs.map((d) => (isHi ? d.name_hi : d.name_en)).join(', ');

    const spokenReply = isHi
      ? `${activeScheme.short_name} के लिए मुख्य आवश्यक दस्तावेज़ हैं: ${docsList}। आप अपना जन आधार कार्ड और बैंक पासबुक लेकर नज़दीकी ई-मित्र कियोस्क पर तुरंत आवेदन कर सकते हैं। अधिक सहायता हेतु हेल्पलाइन 181 पर संपर्क करें।`
      : `Mandatory documents for ${activeScheme.name_en} are: ${docsList}. You can apply at your nearest e-Mitra kiosk with your Jan Aadhaar Card and bank passbook, or call helpline 181.`;

    const displayReply = isHi
      ? `📄 **${activeScheme.name_hi} — आवश्यक दस्तावेज़ व आवेदन:**\n` +
        activeScheme.mandatory_docs.map((d, i) => `${i + 1}. **${d.name_hi}** (${d.name_en})`).join('\n') +
        `\n\n🏛️ **कहाँ आवेदन करें:** ${activeScheme.apply_channel_hi}\n📞 **मुख्यमंत्री हेल्पलाइन:** 181 (टोल-फ्री)\n🌐 **आधिकारिक पोर्टल:** जन आधार पोर्टल / SSO Rajasthan`
      : `📄 **${activeScheme.name_en} — Mandatory Documents & Application:**\n` +
        activeScheme.mandatory_docs.map((d, i) => `${i + 1}. **${d.name_en}**`).join('\n') +
        `\n\n🏛️ **Where to Apply:** ${activeScheme.apply_channel_en}\n📞 **Helpline:** 181 (Toll-Free)\n🌐 **Official Portal:** Jan Aadhaar Portal / SSO Rajasthan`;

    updatedProfile.stage = 'DOCUMENT_INQUIRY';
    updatedProfile.lastQuestionField = undefined;
    updatedProfile.wants_documents = undefined;

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: eligibleTargeted.length > 0 ? [...eligibleTargeted, universalMAA] : [activeScheme, universalMAA],
      moreInfoSchemes: [],
      suggestedChips: [
        { label_hi: '📍 नज़दीकी ई-मित्र केंद्र', label_en: 'Nearest e-Mitra Center', text: 'नज़दीकी ई-मित्र केंद्र पर आवेदन का क्या शुल्क है?' },
        { label_hi: '🔄 परिवार के अन्य सदस्य हेतु', label_en: 'For other family member', text: 'मेरे परिवार के अन्य सदस्यों के लिए क्या योजनाएं हैं?' },
        { label_hi: '📞 हेल्पलाइन 181 की जानकारी', label_en: 'Helpline 181 info', text: 'हेल्पलाइन 181 पर शिकायत या स्टेटस कैसे चेक करें?' },
      ],
      isComplete: true,
    };
  }

  // -------------------------------------------------------------
  // BRANCH 1b: User declined documents ("नहीं", "no") after recommendation
  // -------------------------------------------------------------
  if (
    updatedProfile.wants_documents === false ||
    (updatedProfile.lastQuestionField === 'wants_documents' && isNegative(utterance))
  ) {
    const spokenReply = isHi
      ? 'कोई बात नहीं! आप जब चाहें दस्तावेज़ देख सकते हैं। राजस्थान सरकार की मुख्यमंत्री आयुष्मान आरोग्य योजना में आपके परिवार को ₹25 लाख का निःशुल्क अस्पताल उपचार भी उपलब्ध है। क्या आप परिवार के किसी अन्य सदस्य के लिए योजनाएं देखना चाहते हैं?'
      : 'No problem! You can check documents anytime. Your family also gets ₹25 Lakh cashless healthcare under Mukhyamantri Ayushman Arogya Yojana. Would you like to explore schemes for another family member?';

    const displayReply = isHi
      ? `🏛️ **योजनसेतु कल्याणकारी परामर्श:**\nआप जब चाहें इन योजनाओं के दस्तावेज़ और आवेदन प्रक्रिया जान सकते हैं।\n\n• **योजना:** ${eligibleTargeted[0]?.name_hi || 'सत्यापित योजना'}\n• **कैशलेस स्वास्थ्य कवर:** ₹25 लाख (मुख्यमंत्री आयुष्मान आरोग्य योजना)\n\n❓ **अगला कदम:** क्या आप अपने परिवार के किसी अन्य सदस्य (माता-पिता, पत्नी, बच्चे) के लिए योजनाएं देखना चाहते हैं?`
      : `🏛️ **YojanSetu Welfare Guidance:**\nYou can review documentation and application steps at any time.\n\n• **Benefit:** ₹25 Lakh universal health cover under MAA\n\n❓ **Next Step:** Would you like to check eligible schemes for another family member?`;

    updatedProfile.stage = 'COMPLETED';
    updatedProfile.lastQuestionField = undefined;
    updatedProfile.wants_documents = undefined;

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: eligibleTargeted.length > 0 ? [...eligibleTargeted, universalMAA] : [universalMAA],
      moreInfoSchemes: [],
      suggestedChips: [
        { label_hi: '👴 माता-पिता हेतु वरिष्ठ पेंशन', label_en: 'Senior Pension for parents', text: 'मेरे माता-पिता की उम्र 62 वर्ष है, पेंशन योजना बताइए।' },
        { label_hi: '🌾 परिवार के लिए किसान सहायता', label_en: 'Farmer Support', text: 'हमारे परिवार के पास 4 बीघा कृषि भूमि है।' },
        { label_hi: '🎓 बच्चों हेतु फ्री कोचिंग', label_en: 'Free Coaching for children', text: 'मेरे बच्चे के लिए अनुप्रति कोचिंग योजना की जानकारी चाहिए।' },
        { label_hi: '🔄 नई शुरुआत करें', label_en: 'Start Over', text: 'नमस्ते, नई शुरुआत करें।' },
      ],
      isComplete: true,
    };
  }

  // -------------------------------------------------------------
  // BRANCH 2: Pension Intent without age specified
  // -------------------------------------------------------------
  if (
    (updatedProfile.intent === 'PENSION' || updatedProfile.lastQuestionField === 'age_or_pension_type') &&
    updatedProfile.age === undefined &&
    !updatedProfile.is_widow &&
    !updatedProfile.is_disabled
  ) {
    const isVridhjanSpecific = updatedProfile.pension_type === 'VRIDHJAN' || /वृद्ध|बुजुर्ग|old|senior|vridhjan/i.test(utterance);

    const spokenReply = isHi
      ? (isVridhjanSpecific
          ? 'मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना (₹1,000 से ₹1,500 प्रतिमाह सीधा बैंक खाता अंतरण) के लिए आपकी आयु (उम्र) कितने वर्ष है? (पात्रता: महिला 55+ वर्ष, पुरुष 58+ वर्ष)'
          : 'राजस्थान में वृद्धजन सम्मान पेंशन, एकल नारी विधवा पेंशन और विशेष योग्यजन पेंशन योजनाएं हैं। आप किस पेंशन के बारे में जानना चाहते हैं, और आपकी आयु कितनी है?')
      : (isVridhjanSpecific
          ? 'For Mukhyamantri Vridhjan Samman Pension (₹1,000 - ₹1,500/mo DBT), what is your age in years? (Eligibility: 55+ for women, 58+ for men)'
          : 'Rajasthan offers Senior Citizen Pension, Single Woman Widow Pension, and Disability Pension. Which pension are you inquiring about, and what is your age?');

    const displayReply = isHi
      ? `👴 **राजस्थान सामाजिक सुरक्षा पेंशन परामर्श:**\n${isVridhjanSpecific ? 'आपने **मुख्यमंत्री वृद्धजन सम्मान पेंशन** का चयन किया है।' : 'राजस्थान की मुख्य सामाजिक सुरक्षा पेंशन योजनाएं:'}\n\n• **वृद्धजन सम्मान पेंशन:** महिला 55+ वर्ष, पुरुष 58+ वर्ष (₹1,000 - ₹1,500/माह)\n• **एकल नारी (विधवा) पेंशन:** 18+ वर्ष की महिलाएं (₹1,000 - ₹1,500/माह)\n• **विशेष योग्यजन पेंशन:** 40%+ दिव्यांग नागरिक (₹1,000 - ₹1,500/माह)\n\n❓ **पात्रता प्रश्न:** कृपया अपनी **आयु (उम्र)** बोलकर बताइए:`
      : `👴 **Rajasthan Social Security Pension Guidance:**\n${isVridhjanSpecific ? 'You selected **Mukhyamantri Vridhjan Samman Pension**.' : 'Key Social Security Pension Schemes in Rajasthan:'}\n\n• **Senior Pension:** 55+ female, 58+ male (₹1,000 - ₹1,500/mo)\n• **Widow/Single Woman Pension:** Women aged 18+ (₹1,000 - ₹1,500/mo)\n• **Disability Pension:** 40%+ disability (₹1,000 - ₹1,500/mo)\n\n❓ **Eligibility Question:** Please speak your **age in years**:`;

    updatedProfile.lastQuestionField = isVridhjanSpecific ? 'age' : 'age_or_pension_type';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[0], RAJASTHAN_FLAGSHIP_SCHEMES[3]],
      suggestedChips: [
        { label_hi: '👴 मेरी उम्र 65 वर्ष है', label_en: 'I am 65 years old', text: 'मेरी उम्र 65 वर्ष है, मैं वृद्धजन पेंशन चाहता हूँ।' },
        { label_hi: '👴 मेरी उम्र 60 वर्ष है', label_en: 'I am 60 years old', text: 'मेरी उम्र 60 वर्ष है, पेंशन की पात्रता बताएं।' },
        { label_hi: '👩 मैं विधवा महिला हूँ', label_en: 'I am a widow', text: 'मैं विधवा महिला हूँ, एकल नारी पेंशन की जानकारी चाहिए।' },
        { label_hi: '♿ विशेष योग्यजन (दिव्यांग)', label_en: 'Specially abled', text: 'विशेष योग्यजन दिव्यांग पेंशन की पात्रता क्या है?' },
      ],
      isComplete: false,
      missingField: 'age',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 3: Senior Citizen with Age Known (>= 55), Income Unknown
  // -------------------------------------------------------------
  if (
    updatedProfile.age &&
    updatedProfile.age >= 55 &&
    updatedProfile.annual_income === undefined &&
    !updatedProfile.is_bpl &&
    !updatedProfile.income_confirmed
  ) {
    const spokenReply = isHi
      ? `आपकी आयु ${updatedProfile.age} वर्ष दर्ज कर ली गई है। मुख्यमंत्री वृद्धजन सम्मान पेंशन (₹1,000 प्रति माह DBT) के लिए क्या आपकी पारिवारिक वार्षिक आय ₹48,000 से कम है या आपके पास बीपीएल राशन कार्ड है?`
      : `Your age is recorded as ${updatedProfile.age}. For Senior Citizen Pension (₹1,000/month DBT), is your family annual income within ₹48,000 or do you hold a BPL card?`;

    const displayReply = isHi
      ? `👴 **मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना पात्रता:**\nआपकी आयु **${updatedProfile.age} वर्ष** दर्ज की गई है।\n• **मासिक पेंशन:** 75 वर्ष तक ₹1,000/माह; 75+ वर्ष पर ₹1,500/माह सीधा बैंक खाता DBT\n\n❓ **पात्रता प्रश्न:** क्या आपकी पारिवारिक वार्षिक आय **₹48,000 से कम** है या आपके पास **बीपीएल राशन कार्ड** है?`
      : `👴 **Mukhyamantri Vridhjan Samman Pension:**\nYour age is recorded as **${updatedProfile.age}**.\n• **Benefit:** ₹1,000 to ₹1,500 monthly direct bank transfer\n\n❓ **Eligibility Question:** Is your family annual income **within ₹48,000** or do you hold a **BPL card**?`;

    updatedProfile.lastQuestionField = 'annual_income';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[0]],
      suggestedChips: [
        { label_hi: '✅ हाँ, आय ₹48,000 से कम है', label_en: 'Yes, income is under ₹48k', text: 'हाँ, मेरी पारिवारिक आय 48,000 से कम है।' },
        { label_hi: '✅ मेरे पास बीपीएल कार्ड है', label_en: 'I hold BPL card', text: 'हाँ, मेरे पास बीपीएल राशन कार्ड है।' },
        { label_hi: '🌾 आय कम है, 3 बीघा ज़मीन भी है', label_en: 'Farmer, 3 bighas', text: 'हाँ, आय कम है और मैं किसान भी हूँ, 3 बीघा ज़मीन है।' },
        { label_hi: '❌ नहीं, आय ₹48,000 से अधिक है', label_en: 'No, income exceeds ₹48k', text: 'नहीं, मेरी वार्षिक आय 48,000 से अधिक है।' },
      ],
      isComplete: false,
      missingField: 'annual_income',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 3b: Senior Citizen with Age Known, but Income Exceeds ₹48,000
  // -------------------------------------------------------------
  if (
    updatedProfile.age &&
    updatedProfile.age >= 55 &&
    (updatedProfile.income_confirmed === false || (updatedProfile.annual_income !== undefined && updatedProfile.annual_income > 48000))
  ) {
    const spokenReply = isHi
      ? 'पारिवारिक वार्षिक आय ₹48,000 से अधिक होने के कारण आप सामाजिक सुरक्षा वृद्धजन पेंशन के दायरे में नहीं आते। परंतु राजस्थान सरकार की मुख्यमंत्री आयुष्मान आरोग्य योजना में आपके परिवार को ₹25 लाख का निःशुल्क अस्पताल उपचार मिलेगा। क्या आपके पास कृषि भूमि है, अथवा परिवार के किसी अन्य सदस्य के लिए योजना जानना चाहते हैं?'
      : 'Since your family income exceeds ₹48,000, you do not meet the means-test for Senior Citizen Pension. However, your family is fully covered for ₹25 Lakh cashless healthcare under Mukhyamantri Ayushman Arogya Yojana. Do you hold agricultural land, or wish to check schemes for another family member?';

    const displayReply = isHi
      ? `👴 **पेंशन पात्रता समीक्षा एवं वैकल्पिक योजनाएं:**\nआपकी आयु **${updatedProfile.age} वर्ष** दर्ज है, लेकिन पारिवारिक वार्षिक आय **₹48,000 से अधिक** होने के कारण आप **वृद्धजन सम्मान पेंशन** हेतु अपात्र हैं।\n\n✅ **आपके लिए सक्रिय योजनाएं:**\n1. **मुख्यमंत्री आयुष्मान आरोग्य योजना (MAA):** ₹25 लाख तक कैशलेस अस्पताल उपचार + ₹10 लाख दुर्घटना बीमा\n\n❓ **वैकल्पिक विकल्प:** क्या आपके पास **कृषि भूमि** है (किसान योजनाएं), अथवा परिवार के किसी अन्य सदस्य के लिए योजना जानना चाहते हैं?`
      : `👴 **Pension Evaluation & Alternative Benefits:**\nYour age is **${updatedProfile.age}**, but family income exceeds the ₹48,000 threshold for Senior Citizen Pension.\n\n✅ **Active Schemes for You:**\n1. **Mukhyamantri Ayushman Arogya Yojana:** ₹25 Lakh cashless hospital coverage\n\n❓ **Options:** Do you hold agricultural land, or wish to explore benefits for other family members?`;

    updatedProfile.lastQuestionField = 'after_ineligible_options';
    updatedProfile.stage = 'RECOMMENDING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[2]],
      suggestedChips: [
        { label_hi: '🌾 मेरे पास कृषि भूमि है (किसान)', label_en: 'I hold agricultural land', text: 'मेरे पास कृषि भूमि है, किसान सहायता योजनाएं बताइए।' },
        { label_hi: '🔥 ₹450 में गैस सिलेंडर योजना', label_en: '₹450 Gas Cylinder', text: '₹450 में रसोई गैस सिलेंडर योजना की पात्रता क्या है?' },
        { label_hi: '🏥 आयुष्मान योजना में इलाज कैसे मिलेगा?', label_en: 'How to use MAA health cover?', text: 'आयुष्मान आरोग्य योजना में ₹25 लाख का इलाज कैसे मिलेगा?' },
        { label_hi: '🔄 परिवार के अन्य सदस्य के लिए', label_en: 'For other family member', text: 'मेरे परिवार के अन्य सदस्यों के लिए क्या योजनाएं हैं?' },
      ],
      isComplete: true,
    };
  }

  // -------------------------------------------------------------
  // BRANCH 4: Farmer Intent, Land area is unknown
  // -------------------------------------------------------------
  if (
    (updatedProfile.occupation === 'FARMER' || updatedProfile.intent === 'FARMER') &&
    updatedProfile.land_area_bigha === undefined
  ) {
    const spokenReply = isHi
      ? 'मुख्यमंत्री किसान सम्मान निधि (₹8,000 वार्षिक DBT) और 75% कृषि यंत्र अनुदान के लिए आपकी जमाबंदी में कुल कितनी बीघा कृषि भूमि दर्ज है?'
      : 'For Kisan Samman Nidhi (₹8,000 annual DBT) and 75% farm equipment subsidy, how many bighas of agricultural land do you hold in your Jamabandi?';

    const displayReply = isHi
      ? `🌾 **मुख्यमंत्री किसान सम्मान निधि व साथी योजना:**\nराजस्थान में 12.5 बीघा (5 एकड़) तक भूमि वाले लघु-सीमांत किसानों को ₹8,000 प्रति वर्ष सीधा बैंक DBT व 75% तक सोलर/ड्रिप अनुदान मिलता है।\n\n❓ **पात्रता प्रश्न:** आपकी जमाबंदी नकल में कुल **कितनी बीघा कृषि भूमि** दर्ज है?`
      : `🌾 **Mukhyamantri Kisan Samman Nidhi:**\nSmall & marginal farmers holding up to 12.5 bighas receive ₹8,000/year DBT and up to 75% solar/drip equipment subsidies.\n\n❓ **Eligibility Question:** How many **bighas of agricultural land** do you hold?`;

    updatedProfile.lastQuestionField = 'land_area_bigha';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[2]],
      suggestedChips: [
        { label_hi: '🚜 मेरे पास 3 बीघा कृषि भूमि है', label_en: '3 Bighas land', text: 'मेरे पास 3 बीघा कृषि भूमि है।' },
        { label_hi: '🚜 मेरे पास 5 बीघा कृषि भूमि है', label_en: '5 Bighas land', text: 'मेरे पास 5 बीघा कृषि भूमि है।' },
        { label_hi: '🚜 मेरे पास 10 बीघा कृषि भूमि है', label_en: '10 Bighas land', text: 'मेरे पास 10 बीघा कृषि भूमि है।' },
        { label_hi: '❌ मेरे पास स्वयं की ज़मीन नहीं है', label_en: 'No agricultural land', text: 'मेरे पास स्वयं की कृषि भूमि नहीं है।' },
      ],
      isComplete: false,
      missingField: 'land_area_bigha',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 4b: Farmer has NO land (land_area_bigha === 0)
  // -------------------------------------------------------------
  if (
    (updatedProfile.occupation === 'FARMER' || updatedProfile.intent === 'FARMER') &&
    updatedProfile.land_area_bigha === 0
  ) {
    const spokenReply = isHi
      ? 'चूंकि आपके पास स्वयं की कृषि भूमि नहीं है, आप किसान सम्मान निधि के दायरे में नहीं आते। भूमिहीन ग्रामीण परिवारों के लिए मनरेगा, ई-श्रम और मुख्यमंत्री आयुष्मान आरोग्य योजना में ₹25 लाख का निःशुल्क इलाज उपलब्ध है। क्या आप दैनिक श्रमिक हैं, अथवा आपकी आयु 58 वर्ष से अधिक है?'
      : 'Without land ownership, you do not meet the criteria for Kisan Samman Nidhi. However, landless rural families are eligible for MGNREGA, e-Shram, and ₹25 Lakh cashless healthcare under MAA. Are you a daily-wage worker or aged 58+?';

    const displayReply = isHi
      ? `🌾 **भूमिहीन किसान / ग्रामीण परामर्श:**\nआपके पास कृषि भूमि दर्ज नहीं होने के कारण आप **किसान सम्मान निधि** के पात्र नहीं हैं।\n\n✅ **उपलब्ध योजनाएं:**\n1. **मुख्यमंत्री आयुष्मान आरोग्य योजना:** ₹25 लाख तक कैशलेस अस्पताल उपचार\n2. **ई-श्रम व मनरेगा जॉब कार्ड:** 100 दिन का सुनिश्चित ग्रामीण रोजगार\n\n❓ **पात्रता प्रश्न:** क्या आप **दैनिक श्रमिक / कामगार** हैं, अथवा आपकी **आयु 58 वर्ष से अधिक** है?`
      : `🌾 **Landless Rural Guidance:**\nWithout landholding, Kisan Samman Nidhi is not applicable.\n\n✅ **Available Schemes:**\n1. **MAA Health Cover:** ₹25 Lakh cashless hospitalization\n2. **MGNREGA & e-Shram:** 100 days guaranteed employment\n\n❓ **Question:** Are you a **daily-wage worker**, or is your **age 58+**?`;

    updatedProfile.lastQuestionField = 'age_or_occupation';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[0]],
      suggestedChips: [
        { label_hi: '👴 मेरी उम्र 60 वर्ष है', label_en: 'I am 60 years old', text: 'मेरी उम्र 60 वर्ष है, वरिष्ठ पेंशन योजना बताएं।' },
        { label_hi: '💼 दैनिक मजदूरी / श्रमिक', label_en: 'Daily-wage worker', text: 'मैं दैनिक मजदूरी करता हूँ।' },
        { label_hi: '🔥 ₹450 में गैस सिलेंडर योजना', label_en: '₹450 Gas Cylinder', text: '₹450 रसोई गैस सिलेंडर योजना की पात्रता क्या है?' },
      ],
      isComplete: false,
      missingField: 'age_or_occupation',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 5: Farmer with Land known (<= 12.5 bighas), but Age unknown
  // -------------------------------------------------------------
  if (
    (updatedProfile.occupation === 'FARMER' || updatedProfile.intent === 'FARMER') &&
    updatedProfile.land_area_bigha !== undefined &&
    updatedProfile.land_area_bigha > 0 &&
    updatedProfile.land_area_bigha <= 12.5 &&
    updatedProfile.age === undefined
  ) {
    const spokenReply = isHi
      ? `आपकी ${updatedProfile.land_area_bigha} बीघा कृषि भूमि दर्ज हो गई है। आप ₹8,000 वार्षिक किसान सम्मान निधि के पात्र हैं। क्या आपकी आयु 58 वर्ष या उससे अधिक है, ताकि आपको साथ में वृद्धजन सम्मान पेंशन (₹1,000/माह) भी मिल सके?`
      : `Your ${updatedProfile.land_area_bigha} bighas land qualifies for ₹8,000 annual Kisan Samman Nidhi. Is your age 58 or older to qualify for Senior Farmer Pension (₹1,000/mo) as well?`;

    const displayReply = isHi
      ? `🌾 **किसान सम्मान निधि एवं अतिरिक्त पेंशन पात्रता:**\nआपकी कृषि भूमि **${updatedProfile.land_area_bigha} बीघा** दर्ज हो गई है (पात्र: ₹8,000 वार्षिक सीधा बैंक अंतरण DBT)।\n\n❓ **अतिरिक्त पेंशन प्रश्न:** क्या आपकी **आयु 58 वर्ष या उससे अधिक** है, ताकि आपको साथ में **वृद्धजन सम्मान पेंशन (₹1,000/माह)** भी मिल सके?`
      : `🌾 **Kisan Samman Nidhi & Senior Pension Evaluation:**\nYour land holding of **${updatedProfile.land_area_bigha} bighas** qualifies for ₹8,000/yr DBT.\n\n❓ **Additional Pension Question:** Is your **age 58 or older** to receive **Senior Citizen Pension (₹1,000/mo)** as well?`;

    updatedProfile.lastQuestionField = 'age';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[2], universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[0]],
      suggestedChips: [
        { label_hi: '👴 हाँ, मेरी उम्र 60 वर्ष है', label_en: 'Yes, age 60', text: 'हाँ, मेरी उम्र 60 वर्ष है।' },
        { label_hi: '👨 नहीं, मेरी उम्र 45 वर्ष है', label_en: 'No, age 45', text: 'नहीं, मेरी उम्र 45 वर्ष है।' },
        { label_hi: '📄 किसान निधि के दस्तावेज़ बताइए', label_en: 'Required Documents', text: 'किसान सम्मान निधि के लिए आवश्यक दस्तावेज़ क्या हैं?' },
      ],
      isComplete: false,
      missingField: 'age',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 5b: Farmer with Land > 12.5 bighas
  // -------------------------------------------------------------
  if (
    (updatedProfile.occupation === 'FARMER' || updatedProfile.intent === 'FARMER') &&
    updatedProfile.land_area_bigha !== undefined &&
    updatedProfile.land_area_bigha > 12.5 &&
    updatedProfile.age === undefined
  ) {
    const spokenReply = isHi
      ? `आपकी ${updatedProfile.land_area_bigha} बीघा कृषि भूमि दर्ज है। राजस्थान में लघु-सीमांत किसान सम्मान निधि 12.5 बीघा तक के लिए है, परंतु आपको 75% तक सोलर पंप/ड्रिप सिंचाई अनुदान और ₹25 लाख मुफ्त अस्पताल इलाज मिलेगा। क्या आपकी आयु 58 वर्ष या उससे अधिक है?`
      : `Your ${updatedProfile.land_area_bigha} bighas land exceeds the 12.5 bighas limit for small farmer DBT, but you qualify for up to 75% solar/drip equipment subsidy and ₹25 Lakh healthcare. Is your age 58 or older?`;

    const displayReply = isHi
      ? `🌾 **कृषि अनुदान एवं कल्याण परामर्श:**\nआपकी भूमि **${updatedProfile.land_area_bigha} बीघा** दर्ज है (12.5 बीघा से अधिक होने के कारण सम्मान निधि DBT देय नहीं है, लेकिन 75% कृषि यंत्र अनुदान उपलब्ध है)।\n\n❓ **पेंशन प्रश्न:** क्या आपकी **आयु 58 वर्ष या उससे अधिक** है?`
      : `🌾 **Farm Equipment Subsidy & Pension Review:**\nLand: **${updatedProfile.land_area_bigha} bighas**. 75% solar/drip subsidies available.\n\n❓ **Pension Question:** Is your **age 58 or older**?`;

    updatedProfile.lastQuestionField = 'age';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[0]],
      suggestedChips: [
        { label_hi: '👴 हाँ, मेरी उम्र 62 वर्ष है', label_en: 'Yes, age 62', text: 'हाँ, मेरी उम्र 62 वर्ष है।' },
        { label_hi: '👨 नहीं, मेरी उम्र 48 वर्ष है', label_en: 'No, age 48', text: 'नहीं, मेरी उम्र 48 वर्ष है।' },
        { label_hi: '📄 कृषि यंत्र अनुदान के दस्तावेज़', label_en: 'Equipment Subsidy Docs', text: 'कृषि यंत्र अनुदान के लिए आवश्यक दस्तावेज़ क्या हैं?' },
      ],
      isComplete: false,
      missingField: 'age',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 6: Citizen is a Widow / Single Woman, checking income
  // -------------------------------------------------------------
  if (
    updatedProfile.is_widow &&
    updatedProfile.annual_income === undefined &&
    !updatedProfile.is_bpl &&
    !updatedProfile.income_confirmed
  ) {
    const spokenReply = isHi
      ? 'मुख्यमंत्री एकल नारी सम्मान पेंशन (₹1,000 से ₹1,500 प्रतिमाह) के लिए क्या आपकी पारिवारिक वार्षिक आय ₹48,000 से कम है या आपके पास बीपीएल कार्ड है?'
      : 'For Single Woman Pension (₹1,000 to ₹1,500/month), is your family annual income within ₹48,000 or do you hold a BPL card?';

    const displayReply = isHi
      ? `👩 **मुख्यमंत्री एकल नारी (विधवा) पेंशन योजना:**\nराजस्थान सरकार द्वारा विधवा, तलाकशुदा एवं परित्यक्ता महिलाओं को ₹1,000 से ₹1,500 प्रतिमाह पेंशन देय है।\n\n❓ **पात्रता प्रश्न:** क्या आपकी पारिवारिक वार्षिक आय **₹48,000 से कम** है या आपके पास **बीपीएल कार्ड** है?`
      : `👩 **Mukhyamantri Ekal Nari (Widow) Pension:**\nEligible women receive ₹1,000 to ₹1,500 monthly assistance.\n\n❓ **Eligibility Question:** Is your family annual income **within ₹48,000** or do you hold a **BPL card**?`;

    updatedProfile.lastQuestionField = 'annual_income';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[3]],
      suggestedChips: [
        { label_hi: '✅ हाँ, आय ₹48,000 से कम है', label_en: 'Yes, income is under ₹48k', text: 'हाँ, मेरी पारिवारिक आय 48,000 से कम है।' },
        { label_hi: '✅ मेरे पास बीपीएल कार्ड है', label_en: 'I hold BPL card', text: 'हाँ, मेरे पास बीपीएल राशन कार्ड है।' },
        { label_hi: '👶 मेरे 18 वर्ष से कम के बच्चे हैं', label_en: 'Have children under 18', text: 'हाँ, आय कम है और मेरे दो बच्चे भी हैं।' },
      ],
      isComplete: false,
      missingField: 'annual_income',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 7: Citizen is a Widow / Single Woman with income confirmed, checking child/palanhar
  // -------------------------------------------------------------
  if (
    updatedProfile.is_widow &&
    (updatedProfile.income_confirmed === true || (updatedProfile.annual_income !== undefined && updatedProfile.annual_income <= 48000) || updatedProfile.is_bpl) &&
    updatedProfile.has_school_child === undefined
  ) {
    const spokenReply = isHi
      ? 'एकल नारी पेंशन में आपको ₹1,000 से ₹1,500 मासिक पेंशन मिलेगी। क्या आपके 18 वर्ष से कम उम्र के बच्चे हैं, ताकि पालनहार योजना (₹1,500 से ₹2,500 प्रतिमाह प्रति बच्चा) का अतिरिक्त लाभ भी मिल सके?'
      : 'Under Ekal Nari Pension you receive ₹1,000 to ₹1,500 monthly. Do you have children under 18 for Palanhar Foster Support (₹1,500 to ₹2,500/month per child)?';

    const displayReply = isHi
      ? `👩 **एकल नारी (विधवा) कल्याणकारी परामर्श:**\nआप **मुख्यमंत्री एकल नारी सम्मान पेंशन योजना** (₹1,000 से ₹1,500/माह) के लिए पात्र हैं।\n\n❓ **अतिरिक्त बाल सहायता प्रश्न:** क्या आपके **18 वर्ष से कम आयु के बच्चे** हैं, ताकि आपको **पालनहार योजना** (₹1,500 से ₹2,500/माह प्रति बच्चा + ₹2,000 वार्षिक पोशाक अनुदान) का लाभ भी मिल सके?`
      : `👩 **Widow / Single Woman Welfare Guidance:**\nYou qualify for **Mukhyamantri Ekal Nari Pension** (₹1,000 - ₹1,500/month).\n\n❓ **Additional Child Benefit:** Do you have **children under 18** to receive **Palanhar Foster Support** (₹1,500 - ₹2,500/month per child + ₹2,000 clothing grant)?`;

    updatedProfile.lastQuestionField = 'has_school_child';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[3], universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[4]],
      suggestedChips: [
        { label_hi: '👶 हाँ, 18 वर्ष से कम बच्चे हैं', label_en: 'Yes, have children under 18', text: 'हाँ, मेरे दो बच्चे स्कूल में पढ़ते हैं।' },
        { label_hi: '❌ नहीं, छोटे बच्चे नहीं हैं', label_en: 'No school children', text: 'नहीं, 18 वर्ष से कम आयु के बच्चे नहीं हैं।' },
        { label_hi: '📄 आवश्यक दस्तावेज़ बताइए', label_en: 'Required Documents', text: 'एकल नारी पेंशन के लिए आवश्यक दस्तावेज़ क्या हैं?' },
      ],
      isComplete: false,
      missingField: 'has_school_child',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 8: Female Citizen not yet categorized
  // -------------------------------------------------------------
  if (
    updatedProfile.gender === 'FEMALE' &&
    !updatedProfile.is_widow &&
    !updatedProfile.is_ujjwala_beneficiary &&
    !updatedProfile.occupation &&
    !updatedProfile.is_student &&
    (!updatedProfile.age || updatedProfile.age < 55)
  ) {
    const spokenReply = isHi
      ? 'राजस्थान में महिलाओं के लिए कई विशेष योजनाएं हैं। क्या आप एकल नारी (विधवा/तलाकशुदा) हैं, अथवा आपके पास घरेलू एलपीजी गैस कनेक्शन (उज्ज्वला/बीपीएल) है?'
      : 'Rajasthan offers special schemes for women. Are you a single woman (widow/divorced), or do you hold an LPG gas connection under Ujjwala or BPL?';

    const displayReply = isHi
      ? `👩 **राजस्थान महिला कल्याण परामर्श:**\nमहिलाओं के लिए प्रमुख सरकारी योजनाएं निम्न हैं:\n\n• **एकल नारी (विधवा) पेंशन:** ₹1,000 से ₹1,500 प्रतिमाह\n• **₹450 रसोई गैस सिलेंडर सब्सिडी:** उज्ज्वला एवं बीपीएल परिवारों हेतु\n• **पालनहार योजना:** बच्चों के पालन-पोषण हेतु वित्तीय सहायता\n\n❓ **पात्रता प्रश्न:** कृपया अपनी स्थिति बोलकर बताइए:`
      : `👩 **Rajasthan Women Welfare Guidance:**\nKey schemes for women in Rajasthan:\n\n• **Single Woman / Widow Pension:** ₹1,000 to ₹1,500 monthly\n• **₹450 LPG Cylinder Subsidy:** For BPL & Ujjwala beneficiaries\n• **Palanhar Foster Support:** Financial aid for children\n\n❓ **Eligibility Question:** Please speak your situation:`;

    updatedProfile.lastQuestionField = 'woman_scheme_choice';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[3], RAJASTHAN_FLAGSHIP_SCHEMES[6]],
      suggestedChips: [
        { label_hi: '👩 मैं एकल नारी / विधवा हूँ', label_en: 'I am a widow', text: 'मैं विधवा महिला हूँ, पेंशन योजना की जानकारी चाहिए।' },
        { label_hi: '🔥 ₹450 में गैस सिलेंडर योजना', label_en: '₹450 Gas Cylinder', text: 'मेरे पास गैस कनेक्शन है, ₹450 सिलेंडर योजना बताइए।' },
        { label_hi: '👶 मेरे 18 वर्ष से कम के बच्चे हैं', label_en: 'Children under 18', text: 'मेरे दो बच्चे हैं, बाल कल्याण योजनाएं बताइए।' },
      ],
      isComplete: false,
      missingField: 'woman_scheme_choice',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 9: Student Intent, checking Category
  // -------------------------------------------------------------
  if ((updatedProfile.is_student || updatedProfile.intent === 'STUDENT') && !updatedProfile.caste_category) {
    const spokenReply = isHi
      ? 'मुख्यमंत्री अनुप्रति निःशुल्क कोचिंग योजना और स्कूटी योजना के लिए आपकी सामाजिक श्रेणी क्या है, जैसे SC, ST, OBC, EWS या सामान्य?'
      : 'For Anuprati Free Coaching Scheme, what is your social category (SC, ST, OBC, EWS, or General)?';

    const displayReply = isHi
      ? `🎓 **मुख्यमंत्री अनुप्रति कोचिंग योजना:**\nप्रतिष्ठित संस्थानों से UPSC, RAS, REET, NEET, IIT-JEE की तैयारी हेतु 100% निःशुल्क कोचिंग एवं बाहर रहने वाले छात्रों को ₹40,000 वार्षिक हॉस्टल भत्ता मिलता है।\n\n❓ **पात्रता प्रश्न:** आपकी **जाति/सामाजिक श्रेणी (Category)** क्या है?`
      : `🎓 **Mukhyamantri Anuprati Coaching:**\n100% free coaching for UPSC, RAS, REET, NEET, IIT-JEE + ₹40,000 annual hostel stipend.\n\n❓ **Eligibility Question:** What is your **social/caste category**?`;

    updatedProfile.lastQuestionField = 'caste_category';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[5]],
      suggestedChips: [
        { label_hi: 'OBC श्रेणी (आय < 8 लाख)', label_en: 'OBC Category', text: 'मेरी श्रेणी ओबीसी (OBC) है और आय 8 लाख से कम है।' },
        { label_hi: 'SC / ST श्रेणी', label_en: 'SC / ST Category', text: 'मेरी श्रेणी अनुसूचित जाति (SC/ST) है।' },
        { label_hi: 'EWS (आर्थिक कमजोर)', label_en: 'EWS Category', text: 'मेरी श्रेणी ईडब्ल्यूएस (EWS) है।' },
        { label_hi: 'सामान्य (General)', label_en: 'General Category', text: 'मेरी श्रेणी सामान्य (General) है।' },
      ],
      isComplete: false,
      missingField: 'caste_category',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 10: Student Intent with Category Known, checking Target Exam
  // -------------------------------------------------------------
  if ((updatedProfile.is_student || updatedProfile.intent === 'STUDENT') && updatedProfile.caste_category && !updatedProfile.exam_name) {
    const spokenReply = isHi
      ? 'आप किस प्रतियोगी परीक्षा की तैयारी कर रहे हैं, जैसे UPSC, RAS, REET, NEET या IIT-JEE?'
      : 'Which competitive exam are you preparing for, such as UPSC, RAS, REET, NEET, or IIT-JEE?';

    const displayReply = isHi
      ? `🎓 **अनुप्रति निःशुल्क कोचिंग परीक्षा चयन:**\nआपकी श्रेणी **${updatedProfile.caste_category}** दर्ज हो गई है।\n\n❓ **परीक्षा चयन:** आप किस परीक्षा की निःशुल्क कोचिंग चाहते हैं?\n• **UPSC / RAS:** सिविल सेवा\n• **REET / शिक्षक भर्ती:** अध्यापक पात्रता\n• **NEET / IIT-JEE:** मेडिकल व इंजीनियरिंग`
      : `🎓 **Anuprati Free Coaching Exam Selection:**\nYour category **${updatedProfile.caste_category}** is recorded.\n\n❓ **Target Exam:** Which exam are you preparing for?\n• **UPSC / RAS:** Civil Services\n• **REET / Teacher:** Teaching Eligibility\n• **NEET / IIT-JEE:** Medical & Engineering`;

    updatedProfile.lastQuestionField = 'exam_name';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[5], universalMAA],
      moreInfoSchemes: [],
      suggestedChips: [
        { label_hi: '📚 REET / शिक्षक भर्ती', label_en: 'REET Exam', text: 'मैं रीट (REET) शिक्षक भर्ती परीक्षा की तैयारी कर रहा हूँ।' },
        { label_hi: '🏛️ UPSC / RAS सिविल सेवा', label_en: 'UPSC / RAS', text: 'मैं आरएएस (RAS) सिविल सेवा की तैयारी कर रहा हूँ।' },
        { label_hi: '🩺 NEET मेडिकल प्रवेश परीक्षा', label_en: 'NEET Exam', text: 'मैं नीट (NEET) मेडिकल प्रवेश परीक्षा की तैयारी कर रहा हूँ।' },
        { label_hi: '📄 आवश्यक दस्तावेज़ बताइए', label_en: 'Required Documents', text: 'अनुप्रति कोचिंग के लिए आवश्यक दस्तावेज़ क्या हैं?' },
      ],
      isComplete: false,
      missingField: 'exam_name',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 11: LPG Cylinder / Gas Subsidy intent
  // -------------------------------------------------------------
  if (updatedProfile.intent === 'CYLINDER' && !updatedProfile.is_bpl && !updatedProfile.is_ujjwala_beneficiary) {
    const spokenReply = isHi
      ? 'मात्र ₹450 में घरेलू एलपीजी गैस सिलेंडर सब्सिडी के लिए क्या आपके पास बीपीएल राशन कार्ड या उज्ज्वला गैस कनेक्शन है?'
      : 'For subsidized LPG cylinder at ₹450, do you hold a BPL card or PM Ujjwala gas connection?';

    const displayReply = isHi
      ? `🔥 **इंदिरा गांधी गैस सिलेंडर सब्सिडी योजना:**\nराजस्थान सरकार द्वारा बीपीएल एवं उज्ज्वला परिवारों को ₹450 में घरेलू गैस सिलेंडर उपलब्ध कराया जाता है।\n\n❓ **पात्रता प्रश्न:** क्या आपके पास **बीपीएल राशन कार्ड** अथवा **प्रधानमंत्री उज्ज्वला गैस कनेक्शन** है?`
      : `🔥 **Indira Gandhi Gas Cylinder Subsidy:**\nBPL and Ujjwala families receive LPG cylinder at ₹450.\n\n❓ **Eligibility Question:** Do you hold a **BPL Ration Card** or **PM Ujjwala Connection**?`;

    updatedProfile.lastQuestionField = 'is_bpl_or_ujjwala';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[6]],
      suggestedChips: [
        { label_hi: '🔥 हाँ, उज्ज्वला गैस कनेक्शन है', label_en: 'Yes, Ujjwala connection', text: 'हाँ, मेरे पास उज्ज्वला योजना का गैस कनेक्शन है।' },
        { label_hi: '💳 हाँ, बीपीएल राशन कार्ड है', label_en: 'Yes, BPL card', text: 'हाँ, मेरे पास बीपीएल राशन कार्ड है।' },
        { label_hi: '📄 आवश्यक दस्तावेज़ बताइए', label_en: 'Required Documents', text: 'गैस सिलेंडर सब्सिडी के लिए आवश्यक दस्तावेज़ क्या हैं?' },
      ],
      isComplete: false,
      missingField: 'is_bpl_or_ujjwala',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 12: Disability intent
  // -------------------------------------------------------------
  if (updatedProfile.intent === 'DISABILITY' && updatedProfile.is_disabled === undefined) {
    const spokenReply = isHi
      ? 'विशेष योग्यजन सम्मान पेंशन के लिए क्या आपके पास 40% या अधिक दिव्यांगता का प्रमाण पत्र (UDID कार्ड) है?'
      : 'For Specially Abled Pension, do you hold a 40%+ certified disability certificate (UDID Card)?';

    const displayReply = isHi
      ? `♿ **विशेष योग्यजन सम्मान पेंशन योजना:**\n40% या अधिक दिव्यांगता वाले नागरिकों को ₹1,000 से ₹1,500 प्रतिमाह पेंशन देय है।\n\n❓ **पात्रता प्रश्न:** क्या आपके पास **40% या अधिक दिव्यांगता का प्रमाण पत्र (UDID कार्ड)** है?`
      : `♿ **Vishesh Yogyajan Samman Pension:**\nSpecially abled citizens with 40%+ disability receive ₹1,000 - ₹1,500 monthly.\n\n❓ **Eligibility Question:** Do you hold a **40%+ Disability Certificate (UDID)**?`;

    updatedProfile.lastQuestionField = 'is_disabled';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[7]],
      suggestedChips: [
        { label_hi: '♿ हाँ, 40%+ प्रमाण पत्र है', label_en: 'Yes, 40%+ UDID', text: 'हाँ, मेरे पास 40% दिव्यांगता का यूडीआईडी कार्ड है।' },
        { label_hi: '❌ नहीं, प्रमाण पत्र नहीं है', label_en: 'No certificate', text: 'नहीं, मेरे पास दिव्यांगता प्रमाण पत्र नहीं है।' },
        { label_hi: '📄 आवश्यक दस्तावेज़ बताइए', label_en: 'Required Documents', text: 'दिव्यांग पेंशन के लिए आवश्यक दस्तावेज़ क्या हैं?' },
      ],
      isComplete: false,
      missingField: 'is_disabled',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 13: Daily Wage Worker, Age Unknown
  // -------------------------------------------------------------
  if (updatedProfile.occupation === 'DAILY_WAGE' && updatedProfile.age === undefined) {
    const spokenReply = isHi
      ? 'दैनिक श्रमिकों एवं कामगारों के लिए राजस्थान में मुख्यमंत्री आयुष्मान आरोग्य योजना (₹25 लाख कैशलेस इलाज) और निर्माण श्रमिक सहायता उपलब्ध है। आपकी आयु कितने वर्ष है?'
      : 'For daily-wage workers, Rajasthan offers ₹25 Lakh cashless hospital treatment and construction worker benefits. What is your age in years?';

    const displayReply = isHi
      ? `💼 **श्रमिक एवं कामगार कल्याण परामर्श:**\nदैनिक कामगारों हेतु राजस्थान सरकार द्वारा निर्माण श्रमिक कल्याण कार्ड तथा मुख्यमंत्री आयुष्मान आरोग्य योजना में ₹25 लाख का निःशुल्क अस्पताल उपचार उपलब्ध है।\n\n❓ **पात्रता प्रश्न:** आपकी **आयु (उम्र)** कितने वर्ष है?`
      : `💼 **Daily-Wage Worker Support:**\nWorkers are eligible for Construction Labor Board benefits and ₹25 Lakh health cover under MAA.\n\n❓ **Eligibility Question:** What is your **age in years**?`;

    updatedProfile.lastQuestionField = 'age';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[0]],
      suggestedChips: [
        { label_hi: '👴 मेरी उम्र 60 वर्ष है', label_en: 'I am 60 years old', text: 'मेरी उम्र 60 वर्ष है, क्या मुझे पेंशन भी मिलेगी?' },
        { label_hi: '👨 मेरी उम्र 40 वर्ष है', label_en: 'I am 40 years old', text: 'मेरी उम्र 40 वर्ष है।' },
        { label_hi: '🔥 ₹450 में गैस सिलेंडर योजना', label_en: '₹450 Gas Cylinder', text: '₹450 रसोई गैस सिलेंडर सब्सिडी कैसे मिलेगी?' },
      ],
      isComplete: false,
      missingField: 'age',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 14: Age known (< 55), but Occupation/Profile unknown
  // -------------------------------------------------------------
  if (
    updatedProfile.age &&
    updatedProfile.age < 55 &&
    !updatedProfile.occupation &&
    !updatedProfile.is_widow &&
    !updatedProfile.is_disabled &&
    !updatedProfile.is_student &&
    updatedProfile.gender !== 'FEMALE'
  ) {
    const spokenReply = isHi
      ? `आपकी आयु ${updatedProfile.age} वर्ष दर्ज कर ली गई है। सरकारी योजनाओं की पात्रता हेतु क्या आप किसान, विद्यार्थी, या किसी अन्य व्यवसाय से जुड़े हैं?`
      : `Your age is recorded as ${updatedProfile.age}. To identify eligible schemes, are you a farmer, student, or in another occupation?`;

    const displayReply = isHi
      ? `🏛️ **योजनसेतु योजना पात्रता परामर्श:**\nआपकी आयु **${updatedProfile.age} वर्ष** दर्ज कर ली गई है।\n\n❓ **पात्रता प्रश्न:** कृपया अपना पेशा बोलकर बताएं:\n• क्या आप **किसान** हैं (कृषि भूमि धारक)?\n• क्या आप **कॉलेज छात्र / विद्यार्थी** हैं?\n• क्या आप **दैनिक श्रमिक / छोटा व्यापारी** हैं?`
      : `🏛️ **YojanSetu Scheme Guidance:**\nYour age is recorded as **${updatedProfile.age} years**.\n\n❓ **Eligibility Question:** Please speak your occupation:\n• Are you a **farmer** (holding land)?\n• Are you a **student / candidate**?\n• Are you a **daily-wage worker / artisan**?`;

    updatedProfile.lastQuestionField = 'occupation';
    updatedProfile.stage = 'COLLECTING';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [universalMAA],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[2], RAJASTHAN_FLAGSHIP_SCHEMES[5]],
      suggestedChips: [
        { label_hi: '🌾 मैं किसान हूँ, खेती करता हूँ', label_en: 'I am a farmer', text: 'मैं किसान हूँ, मेरे पास कृषि भूमि है।' },
        { label_hi: '🎓 मैं विद्यार्थी (छात्र) हूँ', label_en: 'I am a student', text: 'मैं विद्यार्थी हूँ, कोचिंग या छात्रवृत्ति योजना चाहिए।' },
        { label_hi: '💼 स्वरोजगार / दैनिक मजदूरी', label_en: 'Self Employed / Worker', text: 'मैं दैनिक मजदूरी करता हूँ।' },
      ],
      isComplete: false,
      missingField: 'occupation',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 15: Confident Eligible Targeted Matches Found!
  // -------------------------------------------------------------
  if (eligibleTargeted.length > 0) {
    const allMatches = [...eligibleTargeted, universalMAA];
    const topScheme = eligibleTargeted[0];
    const schemeNames = eligibleTargeted.map((s) => (isHi ? s.short_name : s.name_en)).slice(0, 2).join(isHi ? ' और ' : ' and ');

    const spokenReply = isHi
      ? `बधाई हो! आपकी जानकारी के अनुसार आप ${schemeNames} के लिए पात्र हैं। इसमें आपको ${topScheme.payout_summary_hi} का लाभ मिलेगा। क्या आप इसके ज़रूरी दस्तावेज़ या ई-मित्र आवेदन प्रक्रिया देखना चाहते हैं?`
      : `Congratulations! Based on your details, you qualify for ${schemeNames}, offering ${topScheme.payout_summary_en}. Would you like to view the required documents or application steps?`;

    const displayReply = isHi
      ? `🎉 **पात्रता निष्कर्ष — आपके लिए ${allMatches.length} सरकारी योजनाएं पाई गईं:**\n\n` +
        allMatches.map((s, i) =>
          `**${i + 1}. ${s.name_hi}**\n` +
          `• **वित्तीय लाभ:** ${s.payout_summary_hi}\n` +
          `• **सम्बद्ध विभाग:** ${s.department_hi}\n` +
          `• **आवश्यक दस्तावेज़:** ${s.mandatory_docs.map((d) => d.name_hi).join(', ')}\n`
        ).join('\n') +
        `\n❓ **अगला कदम:** क्या आप इनके **ज़रूरी दस्तावेज़** या **ई-मित्र आवेदन प्रक्रिया** देखना चाहते हैं?`
      : `🎉 **Eligibility Results — ${allMatches.length} Schemes Found:**\n\n` +
        allMatches.map((s, i) =>
          `**${i + 1}. ${s.name_en}**\n` +
          `• **Benefit:** ${s.payout_summary_en}\n` +
          `• **Department:** ${s.department_en}\n` +
          `• **Documents:** ${s.mandatory_docs.map((d) => d.name_en).join(', ')}\n`
        ).join('\n') +
        `\n❓ **Next Step:** Would you like to view the **mandatory documents** or **e-Mitra application guidance**?`;

    updatedProfile.stage = 'RECOMMENDING';
    updatedProfile.lastQuestionField = 'wants_documents';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: allMatches,
      moreInfoSchemes: [],
      suggestedChips: [
        { label_hi: '📄 आवश्यक दस्तावेज़ बताइए', label_en: 'Tell me documents', text: 'इन योजनाओं के लिए आवश्यक दस्तावेज़ क्या हैं?' },
        { label_hi: '🏛️ ई-मित्र पर आवेदन कैसे करें?', label_en: 'How to apply at e-Mitra?', text: 'ई-मित्र कियोस्क पर आवेदन की क्या प्रक्रिया है?' },
        { label_hi: '🔄 अन्य योजनाएं देखें', label_en: 'Explore more schemes', text: 'क्या मेरे लिए अन्य सरकारी योजनाएं भी उपलब्ध हैं?' },
      ],
      isComplete: true,
    };
  }

  // -------------------------------------------------------------
  // BRANCH 16: Greetings or Open Intent without any facts
  // -------------------------------------------------------------
  if (
    (!updatedProfile.age && !updatedProfile.occupation && !updatedProfile.is_widow && !updatedProfile.is_disabled && !updatedProfile.is_student && !updatedProfile.is_ujjwala_beneficiary) ||
    /^(नमस्ते|प्रणाम|हेलो|hello|hi|namaste|योजना\s*बताओ|सहायता|help|help\s*me)/i.test(utterance.trim())
  ) {
    const spokenReply = isHi
      ? 'नमस्ते! राजस्थान में वरिष्ठ नागरिक पेंशन, किसान सहायता, महिला पेंशन और छात्र कोचिंग जैसी कई योजनाएं हैं। आप किस बारे में जानना चाहते हैं? अपनी आयु या पेशा बोलकर बताइए।'
      : 'Hello! Rajasthan provides Senior Citizen Pensions, Farmer Grants, Single Woman Pensions, and Scholarships. Which are you looking for? Speak your age or occupation.';

    const displayReply = isHi
      ? `🏛️ **योजनसेतु सरकारी योजना परामर्श:**\nनमस्ते! राजस्थान सरकार की प्रमुख कल्याणकारी योजनाओं में पात्रता जानने के लिए कृपया अपनी जानकारी साझा करें:\n\n• **वरिष्ठ नागरिक पेंशन:** महिला 55+ वर्ष, पुरुष 58+ वर्ष\n• **किसान सम्मान निधि:** 12.5 बीघा तक कृषि भूमि\n• **एकल नारी/विधवा पेंशन:** 18+ वर्ष की महिलाएं\n• **छात्र कोचिंग/स्कूटी:** कॉलेज एवं प्रतियोगी परीक्षा छात्र\n\n👉 **कृपया अपनी आयु (उम्र) या पेशा बोलकर बताइए:**`
      : `🏛️ **YojanSetu Welfare Consultation:**\nHello! To find your eligible Rajasthan welfare schemes, please share your details:\n\n• **Senior Pension:** 55+ for women, 58+ for men\n• **Farmer Support:** Agricultural land up to 12.5 bighas\n• **Single Woman/Widow Pension:** Women aged 18+\n• **Student Coaching/Scooty:** Higher education and competitive exams\n\n👉 **Please speak your age or occupation:**`;

    updatedProfile.stage = 'GREETING';
    updatedProfile.lastQuestionField = 'age_or_occupation';

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[0], RAJASTHAN_FLAGSHIP_SCHEMES[2]],
      suggestedChips: [
        { label_hi: '👴 मेरी उम्र 65 वर्ष है', label_en: 'I am 65 years old', text: 'मेरी उम्र 65 वर्ष है, मैं वृद्धजन पेंशन चाहता हूँ।' },
        { label_hi: '🌾 मैं किसान हूँ, 3 बीघा ज़मीन', label_en: 'Farmer, 3 bighas', text: 'मैं किसान हूँ, मेरे पास 3 बीघा कृषि भूमि है।' },
        { label_hi: '👩 मैं एकल नारी / विधवा हूँ', label_en: 'Widow / Single Woman', text: 'मैं विधवा महिला हूँ, पेंशन योजना की जानकारी चाहिए।' },
        { label_hi: '🎓 कॉलेज छात्र, कोचिंग योजना', label_en: 'Student Coaching', text: 'मैं कॉलेज का छात्र हूँ, निःशुल्क कोचिंग की पात्रता क्या है?' },
      ],
      isComplete: false,
      missingField: 'age_or_occupation',
    };
  }

  // -------------------------------------------------------------
  // BRANCH 17: Fallback Clarification
  // -------------------------------------------------------------
  const spokenReply = isHi
    ? 'सटीक योजनाएं खोजने के लिए कृपया अपनी उम्र, पेशा, या कृषि भूमि का विवरण बोलकर बताएं।'
    : 'To find matching schemes, please speak your age, occupation, or land details.';

  const displayReply = isHi
    ? `🏛️ **योजनसेतु सरकारी योजना परामर्श:**\nराजस्थान के प्रत्येक परिवार को **मुख्यमंत्री आयुष्मान आरोग्य योजना** में **₹25 लाख का कैशलेस अस्पताल उपचार** उपलब्ध है।\n\n❓ **सटीक पात्रता हेतु कृपया अपनी जानकारी दें:**\n• आपकी **आयु (उम्र)** कितनी है?\n• क्या आप **किसान**, **वरिष्ठ नागरिक**, **एकल नारी**, या **छात्र** हैं?`
    : `🏛️ **YojanSetu Welfare Guidance:**\nAll Rajasthan families with Jan Aadhaar receive **₹25 Lakh cashless healthcare** under Mukhyamantri Ayushman Arogya Yojana.\n\n❓ **To discover targeted schemes, please share:**\n• What is your **age**?\n• Are you a **farmer**, **senior citizen**, **single woman**, or **student**?`;

  updatedProfile.lastQuestionField = 'age_or_occupation';

  return {
    spokenReply,
    displayReply,
    updatedProfile,
    eligibleSchemes: [universalMAA],
    moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[0], RAJASTHAN_FLAGSHIP_SCHEMES[2]],
    suggestedChips: [
      { label_hi: '👴 मेरी उम्र 65 वर्ष है', label_en: 'I am 65 years old', text: 'मेरी उम्र 65 वर्ष है, मैं वृद्धजन पेंशन चाहता हूँ।' },
      { label_hi: '🌾 3 बीघा ज़मीन, किसान हूँ', label_en: 'Farmer, 3 bighas', text: 'मैं किसान हूँ, मेरे पास 3 बीघा कृषि भूमि है।' },
      { label_hi: '👩 एकल नारी (विधवा) पेंशन', label_en: 'Widow Pension', text: 'मैं विधवा महिला हूँ, पेंशन की जानकारी चाहिए।' },
    ],
    isComplete: false,
    missingField: 'age_or_occupation',
  };
}

/**
 * Converts authentic RajasthanSchemeItem into frontend CitizenSchemeCard format.
 */
export function toCitizenSchemeCard(scheme: RajasthanSchemeItem, lang: 'hi' | 'en' = 'hi'): CitizenSchemeCard {
  return {
    scheme_id: scheme.code,
    scheme_code: scheme.code,
    name_en: scheme.name_en,
    name_hi: scheme.name_hi,
    department_en: scheme.department_en,
    department_hi: scheme.department_hi,
    purpose_en: scheme.desc_en,
    purpose_hi: scheme.desc_hi,
    primary_benefit_en: scheme.payout_summary_en,
    primary_benefit_hi: scheme.payout_summary_hi,
    eligibility_status: 'ELIGIBLE',
    why_eligible_summary_hi: [
      `पात्रता नियम: ${scheme.category}`,
      `आधिकारिक परिपत्र: ${scheme.circular_no}`,
      `वित्तीय लाभ: ${scheme.payout_summary_hi}`,
    ],
    why_eligible_summary_en: [
      `Eligibility matched for ${scheme.category}`,
      `Official Circular: ${scheme.circular_no}`,
      `Benefit: ${scheme.payout_summary_en}`,
    ],
    missing_fields: [],
    missing_fields_display_hi: [],
    missing_fields_display_en: [],
  };
}
