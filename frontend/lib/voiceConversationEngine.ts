/**
 * Conversational Multi-Turn Dialogue Engine for YojanSetu Voice Assistant.
 * Maintains profile facts across dialogue turns, matches against authentic Rajasthan
 * flagship schemes, asks intelligent clarifying follow-ups, and speaks concise natural answers.
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
  occupation?: 'FARMER' | 'STUDENT' | 'DAILY_WAGE' | 'OTHER';
  land_area_bigha?: number;
  marital_status?: 'WIDOWED' | 'DIVORCED' | 'MARRIED' | 'SINGLE';
  is_widow?: boolean;
  is_student?: boolean;
  is_disabled?: boolean;
  is_bpl?: boolean;
  is_ujjwala_beneficiary?: boolean;
  has_jan_aadhaar?: boolean;
  caste_category?: 'SC' | 'ST' | 'OBC' | 'MBC' | 'EWS' | 'GEN';
  district?: string;
  intent?: 'PENSION' | 'FARMER' | 'HEALTHCARE' | 'STUDENT' | 'WIDOW' | 'CYLINDER' | 'DISABILITY' | 'GENERAL';
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
 * Extracts and accumulates demographic entities from natural speech in Hindi & English.
 */
export function extractProfileFromUtterance(
  text: string,
  existingProfile: DialogueProfile = {}
): DialogueProfile {
  const profile: DialogueProfile = { ...existingProfile };
  const lower = text.toLowerCase();

  // 1. Age extraction
  const ageMatch = text.match(/(\d{1,2})\s*(?:साल|वर्ष|saal|sal|years?|yrs?|की उम्र|आयु)/i) ||
                   text.match(/(?:उम्र|आयु|age)\D*?(\d{1,2})/i);
  if (ageMatch) {
    const parsedAge = parseInt(ageMatch[1], 10);
    if (parsedAge > 0 && parsedAge <= 110) {
      profile.age = parsedAge;
    }
  } else {
    // Check standalone numbers like "65", "60", "70" if pension/age is context
    const numMatch = text.match(/\b(5[5-9]|[6-9]\d)\b/);
    if (numMatch && !profile.age) {
      profile.age = parseInt(numMatch[1], 10);
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

  if (/महिला|औरत|female|woman|लड़की|माताजी|दादी/i.test(text)) {
    profile.gender = 'FEMALE';
  } else if (/पुरुष|आदमी|male|man|लड़का|दादाजी|भाई/i.test(text)) {
    profile.gender = 'MALE';
  }

  // 3. Occupation & Land
  const landMatch = text.match(/(\d+(?:\.\d+)?)\s*(?:बीघा|bigha|एकड़|acre|हेक्टेयर|hectare)/i);
  if (landMatch) {
    profile.land_area_bigha = parseFloat(landMatch[1]);
    profile.occupation = 'FARMER';
    profile.intent = 'FARMER';
  }

  if (/किसान|खेती|कृषक|काश्तकार|फसल|farmer|agriculture/i.test(text)) {
    profile.occupation = 'FARMER';
    profile.intent = 'FARMER';
    if (profile.land_area_bigha === undefined) {
      profile.land_area_bigha = 3.0; // Default small farmer baseline
    }
  }

  // 4. Student & Education
  if (/छात्र|छात्रा|विद्यार्थी|पढ़ाई|कॉलेज|12वीं|neet|iit|coaching|student|study|exam/i.test(text)) {
    profile.is_student = true;
    profile.occupation = 'STUDENT';
    profile.intent = 'STUDENT';
    if (!profile.age) profile.age = 19;
  }

  // 5. Disability
  if (/दिव्यांग|विकलांग|विशेष योग्यजन|handicapped|disabled|40%|अपंग/i.test(text)) {
    profile.is_disabled = true;
    profile.intent = 'DISABILITY';
  }

  // 6. LPG Cylinder / Gas
  if (/गैस|सिलेंडर|cylinder|gas|उज्ज्वला|lpg|450/i.test(text)) {
    profile.is_ujjwala_beneficiary = true;
    profile.intent = 'CYLINDER';
  }

  // 7. BPL & Income
  if (/बीपीएल|bpl|गरीब|अंत्योदय/i.test(text)) {
    profile.is_bpl = true;
    profile.annual_income = 30000;
  }

  const incomeMatch = text.match(/(?:आय|कमाई|कम|income)\D*?(\d[\d,]*)/i) ||
                      text.match(/(\d[\d,]*)\s*(?:रुपये|rs|हजार|वार्षिक|सालाना)/i);
  if (incomeMatch) {
    let inc = parseInt(incomeMatch[1].replace(/,/g, ''), 10);
    if (inc < 500) inc = inc * 1000; // e.g. "48 हजार"
    profile.annual_income = inc;
  }

  if (/48,?000|48 हजार|कम आय|गरीब परिवार|low income/i.test(text)) {
    profile.annual_income = 40000;
  }

  // 8. Jan Aadhaar
  if (/जन आधार|jan aadhaar|janadhar/i.test(text)) {
    profile.has_jan_aadhaar = true;
  } else if (profile.has_jan_aadhaar === undefined) {
    profile.has_jan_aadhaar = true; // High prevalence default in Rajasthan
  }

  // 9. Broad intent classification
  if (!profile.intent) {
    if (/पेंशन|बुजुर्ग|वृद्ध|senior|old age/i.test(text)) {
      profile.intent = 'PENSION';
    } else if (/इलाज|अस्पताल|स्वास्थ्य|दवा|health|hospital|treatment|चिरंजीवी|आरोग्य/i.test(text)) {
      profile.intent = 'HEALTHCARE';
    } else if (/पशु|पालनहार|अनाथ|बच्चे|child/i.test(text)) {
      profile.intent = 'WIDOW';
    } else {
      profile.intent = 'GENERAL';
    }
  }

  return profile;
}

/**
 * Executes multi-turn reasoning: analyzes intent, checks missing facts,
 * generates follow-up questions or final scheme recommendations.
 */
export function processDialogueTurn(
  utterance: string,
  existingProfile: DialogueProfile = {},
  lang: 'hi' | 'en' = 'hi'
): DialogueTurnResult {
  const isHi = lang === 'hi';
  const updatedProfile = extractProfileFromUtterance(utterance, existingProfile);

  // Check which schemes are matched vs need more info
  const eligibleSchemes: RajasthanSchemeItem[] = [];
  const moreInfoSchemes: RajasthanSchemeItem[] = [];

  for (const scheme of RAJASTHAN_FLAGSHIP_SCHEMES) {
    if (scheme.isEligible(updatedProfile)) {
      eligibleSchemes.push(scheme);
    } else {
      const missing = scheme.needsMoreInfo(updatedProfile);
      if (missing) {
        moreInfoSchemes.push(scheme);
      }
    }
  }

  // Handle Document Inquiry (e.g. "दस्तावेज क्या चाहिए?")
  if (/दस्तावेज़|कागज़|documents?|apply|आवेदन/i.test(utterance) && eligibleSchemes.length > 0) {
    const topScheme = eligibleSchemes[0];
    const docs = topScheme.mandatory_docs.map((d) => (isHi ? d.name_hi : d.name_en)).join(', ');

    const spokenReply = isHi
      ? `${topScheme.short_name} के लिए आवश्यक दस्तावेज हैं: ${docs}। आप जन आधार कार्ड लेकर नजदीकी ई-मित्र पर तुरंत आवेदन कर सकते हैं।`
      : `The required documents for ${topScheme.name_en} are: ${docs}. You can apply with your Jan Aadhaar Card at your nearest e-Mitra kiosk.`;

    const displayReply = isHi
      ? `📄 **${topScheme.name_hi} — आवश्यक दस्तावेज़:**\n` +
        topScheme.mandatory_docs.map((d, i) => `${i + 1}. **${d.name_hi}** (${d.name_en})`).join('\n') +
        `\n\n🏛️ **आवेदन का माध्यम:** ${topScheme.apply_channel_hi}\n📞 हेल्पलाइन: 181 (मुख्यमंत्री हेल्पलाइन)`
      : `📄 **${topScheme.name_en} — Mandatory Documents:**\n` +
        topScheme.mandatory_docs.map((d, i) => `${i + 1}. **${d.name_en}**`).join('\n') +
        `\n\n🏛️ **Where to Apply:** ${topScheme.apply_channel_en}\n📞 Helpline: 181`;

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes,
      moreInfoSchemes: [],
      suggestedChips: [
        { label_hi: '🏛️ ई-मित्र पर कैसे जाएं?', label_en: 'How to visit e-Mitra?', text: 'ई-मित्र कियोस्क पर आवेदन की क्या फीस है?' },
        { label_hi: '🔄 नई योजना खोजें', label_en: 'Explore Other Schemes', text: 'मुझे अन्य योजनाओं के बारे में भी बताइए।' },
      ],
      isComplete: true,
    };
  }

  // CASE 1: Specific Intent = PENSION, but age is missing
  if ((updatedProfile.intent === 'PENSION' || /पेंशन|वृद्धजन|सहायता/i.test(utterance)) && !updatedProfile.age && !updatedProfile.is_widow && !updatedProfile.is_disabled) {
    const spokenReply = isHi
      ? 'राजस्थान में वृद्धजन, विधवा और विशेष योग्यजन पेंशन योजनाएँ उपलब्ध हैं। क्या आप अपनी उम्र बता सकते हैं, और आप पुरुष हैं या महिला?'
      : 'Rajasthan provides Senior, Widow, and Specially-Abled pensions. Could you please share your age, and whether you are male or female?';

    const displayReply = isHi
      ? `🏛️ **पेंशन परामर्श:** राजस्थान सामाजिक सुरक्षा पेंशन हेतु कृपया अपनी जानकारी दें:\n• **आयु (उम्र):** वरिष्ठ नागरिक पेंशन हेतु महिला 55+ वर्ष, पुरुष 58+ वर्ष\n• **श्रेणी:** क्या आप वरिष्ठ नागरिक, एकल नारी (विधवा), या विशेष योग्यजन हैं?`
      : `🏛️ **Pension Guidance:** Please share your details to evaluate pension eligibility:\n• **Age:** 55+ for women, 58+ for men\n• **Category:** Senior citizen, single woman/widow, or specially-abled?`;

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[0]],
      suggestedChips: [
        { label_hi: '👴 मेरी उम्र 65 वर्ष है', label_en: 'I am 65 years old', text: 'मेरी उम्र 65 वर्ष है, मैं पुरुष हूँ।' },
        { label_hi: '👵 महिला, आयु 58 वर्ष', label_en: 'Female, 58 years old', text: 'मेरी आयु 58 वर्ष है, मैं महिला हूँ।' },
        { label_hi: '👩 मैं विधवा महिला हूँ', label_en: 'I am a widow', text: 'मैं विधवा महिला हूँ, मेरी उम्र 45 वर्ष है।' },
      ],
      isComplete: false,
      missingField: 'age',
    };
  }

  // CASE 2: Specific Intent = FARMER, but land size is unknown
  if (updatedProfile.intent === 'FARMER' && updatedProfile.land_area_bigha === undefined) {
    const spokenReply = isHi
      ? 'किसान सम्मान निधि व साथी योजना के लिए आपके पास कितनी बीघा या एकड़ कृषि भूमि है?'
      : 'For Kisan Samman Nidhi and farm subsidies, how many bighas or acres of land do you hold?';

    const displayReply = isHi
      ? `🌾 **कृषि सहायता योजनाएँ:** राजस्थान में 12.5 बीघा (5 एकड़) तक भूमि वाले लघु व सीमांत किसानों को ₹8,000 वार्षिक सम्मान निधि एवं 75% तक सोलर पंप/ड्रिप अनुदान मिलता है।\n\n👉 **कृपया अपनी कृषि भूमि (बीघा में) बताएं:**`
      : `🌾 **Farmer Support Schemes:** Rajasthan provides ₹8,000/year and up to 75% farm equipment subsidies for farmers holding up to 12.5 bighas.\n\n👉 **Please specify your land area:**`;

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[1]], // MAA health always eligible
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[2]],
      suggestedChips: [
        { label_hi: '🚜 3 बीघा कृषि भूमि', label_en: '3 Bighas land', text: 'मेरे पास 3 बीघा कृषि भूमि है।' },
        { label_hi: '🚜 5 बीघा कृषि भूमि', label_en: '5 Bighas land', text: 'मेरे पास 5 बीघा कृषि भूमि है।' },
        { label_hi: '🚜 10 बीघा कृषि भूमि', label_en: '10 Bighas land', text: 'मेरे पास 10 बीघा कृषि भूमि है।' },
      ],
      isComplete: false,
      missingField: 'land_area_bigha',
    };
  }

  // CASE 3: Age is provided (e.g. 60+), but income hasn't been confirmed
  if (updatedProfile.age && updatedProfile.age >= 55 && updatedProfile.annual_income === undefined && !updatedProfile.is_bpl) {
    const spokenReply = isHi
      ? `${updatedProfile.age} वर्ष की आयु में आप मुख्यमंत्री वृद्धजन सम्मान पेंशन के पात्र हैं। क्या आपकी पारिवारिक वार्षिक आय ₹48,000 से कम है?`
      : `At ${updatedProfile.age} years of age, you qualify for Senior Citizen Pension. Is your family annual income within ₹48,000?`;

    const displayReply = isHi
      ? `👴 **वृद्धजन सम्मान पेंशन पात्रता:**\nआपकी आयु ${updatedProfile.age} वर्ष है। राजस्थान सरकार द्वारा 75 वर्ष तक ₹1,000/माह तथा 75 से अधिक पर ₹1,500/माह पेंशन दी जाती है।\n\n📌 **आय सीमा:** क्या आपकी वार्षिक आय ₹48,000 से कम है या आप बीपीएल कार्डधारक हैं?`
      : `👴 **Senior Pension Eligibility:**\nYour age is ${updatedProfile.age}. Rajasthan grants ₹1,000 to ₹1,500 monthly pension.\n\n📌 **Income Criteria:** Is your annual income within ₹48,000 or do you hold a BPL card?`;

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[1]],
      moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[0]],
      suggestedChips: [
        { label_hi: '✅ हाँ, आय ₹48,000 से कम है', label_en: 'Yes, income is under ₹48k', text: 'हाँ, मेरी पारिवारिक आय 48,000 से कम है।' },
        { label_hi: '✅ मेरे पास बीपीएल कार्ड है', label_en: 'I hold BPL card', text: 'मैं बीपीएल परिवार से हूँ।' },
        { label_hi: '❌ आय ₹48,000 से अधिक है', label_en: 'Income is higher', text: 'मेरी आय 48,000 से अधिक है।' },
      ],
      isComplete: false,
      missingField: 'annual_income',
    };
  }

  // CASE 4: Confident Eligible Matches Found!
  if (eligibleSchemes.length > 0) {
    const schemeNames = eligibleSchemes.map((s) => (isHi ? s.short_name : s.name_en)).slice(0, 2).join(isHi ? ' और ' : ' and ');
    const topScheme = eligibleSchemes[0];

    const spokenReply = isHi
      ? `आपकी जानकारी के अनुसार आप ${schemeNames} के लिए पात्र हैं। इसमें आपको ${topScheme.payout_summary_hi} का लाभ मिलेगा। आवश्यक दस्तावेज़ स्क्रीन पर दिखाए गए हैं।`
      : `Based on your details, you are eligible for ${schemeNames}, providing ${topScheme.payout_summary_en}. The documents and details are displayed on screen.`;

    const displayReply = isHi
      ? `🎉 **पात्रता निष्कर्ष — आपके लिए ${eligibleSchemes.length} प्रमुख योजनाएँ:**\n\n` +
        eligibleSchemes.map((s, i) =>
          `**${i + 1}. ${s.name_hi}**\n` +
          `• **वित्तीय लाभ:** ${s.payout_summary_hi}\n` +
          `• **विभाग:** ${s.department_hi}\n` +
          `• **ज़रूरी दस्तावेज़:** ${s.mandatory_docs.map((d) => d.name_hi).join(', ')}\n`
        ).join('\n') +
        `\n🏛️ **कहाँ आवेदन करें:** नज़दीकी **ई-मित्र केंद्र** पर जन आधार कार्ड के साथ आवेदन करें। सहायता हेतु **181** डायल करें।`
      : `🎉 **Eligibility Results — ${eligibleSchemes.length} Schemes Found:**\n\n` +
        eligibleSchemes.map((s, i) =>
          `**${i + 1}. ${s.name_en}**\n` +
          `• **Benefits:** ${s.payout_summary_en}\n` +
          `• **Department:** ${s.department_en}\n` +
          `• **Documents:** ${s.mandatory_docs.map((d) => d.name_en).join(', ')}\n`
        ).join('\n') +
        `\n🏛️ **Application:** Visit your nearest **e-Mitra kiosk** with your Jan Aadhaar Card, or dial **181** for support.`;

    return {
      spokenReply,
      displayReply,
      updatedProfile,
      eligibleSchemes,
      moreInfoSchemes: [],
      suggestedChips: [
        { label_hi: '📄 ज़रूरी दस्तावेज़ बताइए', label_en: 'What documents are required?', text: 'इन योजनाओं के लिए आवश्यक दस्तावेज़ क्या हैं?' },
        { label_hi: '📍 नज़दीकी ई-मित्र कहाँ है?', label_en: 'Nearest e-Mitra Kiosk', text: 'नज़दीकी ई-मित्र कियोस्क और आवेदन प्रक्रिया बताएं।' },
        { label_hi: '🔄 अन्य योजनाएं देखें', label_en: 'Explore Other Benefits', text: 'क्या मेरे लिए अन्य सरकारी योजनाएं भी हैं?' },
      ],
      isComplete: true,
    };
  }

  // DEFAULT FALLBACK: General guidance
  const universalScheme = RAJASTHAN_FLAGSHIP_SCHEMES[1]; // Ayushman MAA Healthcare
  const spokenReply = isHi
    ? 'राजस्थान में जन आधार धारक सभी परिवारों को आयुष्मान आरोग्य योजना में ₹25 लाख का निःशुल्क इलाज प्राप्त है। पेंशन या कृषक सहायता के लिए अपनी आयु या पेशा बताएं।'
    : 'All Rajasthan families with Jan Aadhaar receive ₹25 Lakh free health cover under Ayushman Arogya. Share your age or occupation to check pensions and farm grants.';

  const displayReply = isHi
    ? `🏛️ **योजनसेतु कल्याणकारी परामर्श:**\nराजस्थान के प्रत्येक जन आधार धारक परिवार को **मुख्यमंत्री आयुष्मान आरोग्य योजना** अंतर्गत प्रतिवर्ष **₹25 लाख का कैशलेस उपचार** उपलब्ध है।\n\n👉 अन्य योजनाओं (पेंशन, किसान सम्मान निधि, निःशुल्क कोचिंग) की पात्रता जानने के लिए अपनी **आयु, व्यवसाय (किसान/छात्र) या श्रेणी** बोलकर बताएं।`
    : `🏛️ **YojanSetu Welfare Guidance:**\nAll Rajasthan families with Jan Aadhaar receive up to **₹25 Lakh cashless healthcare** under Mukhyamantri Ayushman Arogya Yojana.\n\n👉 Speak your **age, occupation, or category** to discover senior pensions, farmer support, and scholarships.`;

  return {
    spokenReply,
    displayReply,
    updatedProfile,
    eligibleSchemes: [universalScheme],
    moreInfoSchemes: [RAJASTHAN_FLAGSHIP_SCHEMES[0], RAJASTHAN_FLAGSHIP_SCHEMES[2]],
    suggestedChips: [
      { label_hi: '👴 60+ वरिष्ठ नागरिक पेंशन', label_en: 'Senior Citizen Pension', text: 'मेरी उम्र 60 वर्ष से अधिक है, मुझे पेंशन चाहिए।' },
      { label_hi: '🌾 3 बीघा ज़मीन, किसान सहायता', label_en: 'Farmer Support', text: 'मेरे पास 3 बीघा कृषि भूमि है, किसान योजना बताएं।' },
      { label_hi: '👩 एकल नारी (विधवा) पेंशन', label_en: 'Widow Pension', text: 'मैं विधवा महिला हूँ, पेंशन योजना की जानकारी चाहिए।' },
    ],
    isComplete: false,
  };
}

/**
 * Converts authentic RajasthanSchemeItem into frontend CitizenSchemeCard format.
 */
export function toCitizenSchemeCard(scheme: RajasthanSchemeItem, lang: 'hi' | 'en' = 'hi'): CitizenSchemeCard {
  const isHi = lang === 'hi';
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
