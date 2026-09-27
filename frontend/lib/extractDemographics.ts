/**
 * Deterministic Demographic Entity Extractor for Vernacular Hindi & English.
 * Extracts age, gender, category, income, occupation, residence, district, ration card,
 * land area, and special criteria from natural speech or text chat.
 */

import { CitizenParameters } from "../components/citizen/CitizenParameterPanel";

export interface ExtractedEntities {
  age?: number;
  gender?: "MALE" | "FEMALE" | "OTHER";
  category?: "GENERAL" | "OBC" | "SC" | "ST" | "EWS" | "MBC";
  income?: number;
  occupation?: string;
  residence?: "RURAL" | "URBAN";
  district?: string;
  rationCard?: "NONE" | "BPL" | "STATE_BPL" | "AAY" | "NFSA";
  isWidow?: boolean;
  isDisabled?: boolean;
  disabilityPercent?: number;
  landBigha?: number;
  hasJanAadhaar?: boolean;
  isStudent?: boolean;
  maritalStatus?: "MARRIED" | "SINGLE" | "WIDOW" | "DIVORCED";
  courseLevel?: "SCHOOL" | "COLLEGE" | "COACHING" | "OTHER";
}

const HINDI_WORD_NUMBERS: Record<string, number> = {
  "अठारह": 18, "उन्नीस": 19, "बीस": 20, "इक्कीस": 21, "बाईस": 22, "तेईस": 23, "चौबीस": 24, "पच्चीस": 25,
  "छब्बीस": 26, "सत्ताईस": 27, "अट्ठाईस": 28, "उनतीस": 29, "तीस": 30, "इकतीस": 31, "बत्तीस": 32, "तैंतीस": 33,
  "पैंतीस": 35, "छत्तीस": 36, "सैंतीस": 37, "अड़तीस": 38, "चालीस": 40, "इकतालीस": 41, "बयालीस": 42,
  "पैंतालीस": 45, "छियालीस": 46, "पचास": 50, "इक्यावन": 51, "बावन": 52, "तिरपन": 53, "चौवन": 54, "पचपन": 55,
  "छप्पन": 56, "सत्तावन": 57, "अट्ठवन": 58, "उनसठ": 59, "साठ": 60, "इकसठ": 61, "बासठ": 62, "तिरेसठ": 63,
  "चौंसठ": 64, "पैंसठ": 65, "छियासठ": 66, "सड़सठ": 67, "अड़सठ": 68, "उनहत्तर": 69, "सत्तर": 70, "इकहत्तर": 71,
  "बहत्तर": 72, "तिहत्तर": 73, "चौहत्तर": 74, "पिचहत्तर": 75, "छिहत्तर": 76, "सतहत्तर": 77, "अठहत्तर": 78,
  "उनासी": 79, "अस्सी": 80, "पिच्यासी": 85, "नब्बे": 90, "पंच्यानवे": 95,
};

const DISTRICTS_MAP: Record<string, string> = {
  "जयपुर": "Jaipur", "jaipur": "Jaipur",
  "जोधपुर": "Jodhpur", "jodhpur": "Jodhpur",
  "कोटा": "Kota", "kota": "Kota",
  "उदयपुर": "Udaipur", "udaipur": "Udaipur",
  "बीकानेर": "Bikaner", "bikaner": "Bikaner",
  "अजमेर": "Ajmer", "ajmer": "Ajmer",
  "अलवर": "Alwar", "alwar": "Alwar",
  "सीकर": "Sikar", "sikar": "Sikar",
  "नागौर": "Nagaur", "nagaur": "Nagaur",
  "पाली": "Pali", "pali": "Pali",
  "भरतपुर": "Bharatpur", "bharatpur": "Bharatpur",
  "भीलवाड़ा": "Bhilwara", "bhilwara": "Bhilwara",
  "बाड़मेर": "Barmer", "barmer": "Barmer",
  "गंगानगर": "Ganganagar", "ganganagar": "Ganganagar",
  "चूरू": "Churu", "churu": "Churu",
  "झुंझुनू": "Jhunjhunu", "jhunjhunu": "Jhunjhunu",
  "दौसा": "Dausa", "dausa": "Dausa",
  "टोंक": "Tonk", "tonk": "Tonk",
  "चित्तौड़गढ़": "Chittorgarh", "chittorgarh": "Chittorgarh",
  "झालावाड़": "Jhalawar", "jhalawar": "Jhalawar",
  "बांसवाड़ा": "Banswara", "banswara": "Banswara",
  "डूंगरपुर": "Dungarpur", "dungarpur": "Dungarpur",
  "प्रतापगढ़": "Pratapgarh", "pratapgarh": "Pratapgarh",
  "राजसमंद": "Rajsamand", "rajsamand": "Rajsamand",
  "सिरोही": "Sirohi", "sirohi": "Sirohi",
  "सवाई माधोपुर": "Sawai Madhopur", "sawai madhopur": "Sawai Madhopur",
  "करौली": "Karauli", "karauli": "Karauli",
  "धौलपुर": "Dholpur", "dholpur": "Dholpur",
  "बूंदी": "Bundi", "bundi": "Bundi",
  "बारां": "Baran", "baran": "Baran",
  "जैसलमेर": "Jaisalmer", "jaisalmer": "Jaisalmer",
  "जालोर": "Jalore", "jalore": "Jalore",
  "हनुमानगढ़": "Hanumangarh", "hanumangarh": "Hanumangarh",
  "अनूपगढ़": "Anupgarh", "anupgarh": "Anupgarh",
  "बालोतरा": "Balotra", "balotra": "Balotra",
  "ब्यावर": "Beawar", "beawar": "Beawar",
  "डीग": "Deeg", "deeg": "Deeg",
  "डीडवाना": "Didwana Kuchaman", "didwana": "Didwana Kuchaman",
  "दूदू": "Dudu", "dudu": "Dudu",
  "गंगापुर": "Gangapur City", "gangapur": "Gangapur City",
  "केकड़ी": "Kekri", "kekri": "Kekri",
  "कोटपूतली": "Kotputli Behror", "kotputli": "Kotputli Behror",
  "खैरथल": "Khairthal Tijara", "khairthal": "Khairthal Tijara",
  "नीम का थाना": "Neem Ka Thana", "neem ka thana": "Neem Ka Thana",
  "फलौदी": "Phalodi", "phalodi": "Phalodi",
  "सलूंबर": "Salumbar", "salumbar": "Salumbar",
  "सांचौर": "Sanchore", "sanchore": "Sanchore",
  "शाहपुरा": "Shahpura", "shahpura": "Shahpura",
};

export function extractDemographicsFromText(text: string): ExtractedEntities {
  const result: ExtractedEntities = {};
  if (!text || typeof text !== "string") return result;

  const lower = text.toLowerCase().trim();

  // 1. Age Extraction
  // Robust matching for: "20 साल", "20 saal", "20 sal", "20 saa", "20 वर्ष", "20 years", "20 yrs", "20 yr", "20 ki umar", "umar 20", "age 20", "me 20 ka hu", "i am 20", etc.
  const ageRegexes = [
    /(\d{1,2})\s*(?:साल|वर्ष|saal|sal|saa\b|years?|yrs?|yr|ki\s*umar|ki\s*aayu|की\s*उम्र|की\s*आयु)/i,
    /(?:उम्र|आयु|age|umar|aayu)\s*(?:is|hai|है|=|:)?\s*(\d{1,2})/i,
    /(?:i am|मैं|me|mai|iam)\s*(\d{1,2})\s*(?:ka|ki|का|की|years?|saal|sal|saa\b|साल|वर्ष)?\s*(?:hu|hoon|हूँ|है)?/i,
    /(\d{1,2})\s*(?:ka|ki|का|की)\s*(?:student|kisan|ladka|ladki|chhatra|vidyarthi|farmer|boy|girl)/i,
  ];

  for (const re of ageRegexes) {
    const match = text.match(re);
    if (match && match[1]) {
      const val = parseInt(match[1], 10);
      if (val >= 10 && val <= 105) {
        result.age = val;
        break;
      }
    }
  }

  // Standalone or bounded 2-digit number for age reply: e.g. "45", "62", "20", "me 20"
  if (result.age === undefined) {
    const rawNumberMatch = text.match(/\b(\d{1,2})\b/);
    if (rawNumberMatch && rawNumberMatch[1]) {
      const n = parseInt(rawNumberMatch[1], 10);
      // Ensure it's not a money / land / percentage term
      const isNotOtherUnit = !/(?:₹|rs|रु|लाख|lakh|हजार|k\b|%|बीघा|bigha|acre|एकड़)/i.test(text);
      if (n >= 14 && n <= 100 && isNotOtherUnit) {
        result.age = n;
      }
    }
  }

  // Hindi Word Numbers for Age
  if (result.age === undefined) {
    for (const [word, num] of Object.entries(HINDI_WORD_NUMBERS)) {
      if (text.includes(word)) {
        if (/उम्र|आयु|साल|वर्ष|बुजुर्ग|पेंशन/i.test(text) || text.length < 30) {
          result.age = num;
          break;
        }
      }
    }
  }

  // 2. Gender Extraction (Including Hindi verb markers like पढ़ती हूँ / पढ़ता हूँ)
  if (
    /(?:महिला|औरत|स्त्री|लड़की|माता|बहन|फीमेल|female|woman|girl|widow|विधवा)/i.test(text) ||
    /(?:पढ़ती|करती|रहती|जाती|आती|चाहती|दिखती)\s*(?:हूँ|हूं|hu|hoon|है|hai)?/i.test(text) ||
    /\b(?:padhti|karti|rahti|chahti|ladki)\b/i.test(text)
  ) {
    result.gender = "FEMALE";
  } else if (
    /(?:पुरुष|मर्द|आदमी|लड़का|मेल|male|man|boy)/i.test(text) ||
    /(?:पढ़ता|करता|रहता|जाता|आता|चाहता)\s*(?:हूँ|हूं|hu|hoon|है|hai)?/i.test(text) ||
    /\b(?:padhta|karta|rahta|chahta|ladka)\b/i.test(text)
  ) {
    result.gender = "MALE";
  } else if (/(?:अन्य|transgender|किन्नर|other)/i.test(text)) {
    result.gender = "OTHER";
  }

  // 3. Category Extraction
  if (/\b(?:obc|ओबीसी|अन्य\s*पिछड़ा|पिछड़ी\s*जाति)\b/i.test(text)) {
    result.category = "OBC";
  } else if (/\b(?:sc|एससी|अनुसूचित\s*जाति|दलित)\b/i.test(text)) {
    result.category = "SC";
  } else if (/\b(?:st|एसटी|अनुसूचित\s*जनजाति|आदिवासी)\b/i.test(text)) {
    result.category = "ST";
  } else if (/\b(?:ews|ईडब्ल्यूएस|आर्थिक\s*कमजोर)\b/i.test(text)) {
    result.category = "EWS";
  } else if (/\b(?:mbc|एमबीसी|अति\s*पिछड़ा)\b/i.test(text)) {
    result.category = "MBC";
  } else if (/\b(?:general|सामान्य|जनरल|open)\b/i.test(text)) {
    result.category = "GENERAL";
  }

  // 4. Income Extraction
  // Examples: "1.5 लाख", "1 लाख", "2.5 lakh", "आय 50000", "income 80000", "शून्य आय"
  const lakhMatch = text.match(/(\d+(?:\.\d+)?)\s*(?:लाख|lakh|lac)/i);
  if (lakhMatch && lakhMatch[1]) {
    const val = parseFloat(lakhMatch[1]) * 100000;
    if (val >= 0 && val <= 1000000) {
      result.income = Math.round(val);
    }
  } else {
    const incomeMatch = text.match(/(?:आय|income|कमाई)\s*(?:is|है|=|:)?\s*₹?\s*(\d{4,7})/i) ||
                        text.match(/₹\s*(\d{4,7})/i);
    if (incomeMatch && incomeMatch[1]) {
      const val = parseInt(incomeMatch[1], 10);
      if (val >= 0 && val <= 1000000) {
        result.income = val;
      }
    } else if (/शून्य\s*आय|कोई\s*आय\s*नहीं|zero\s*income|0\s*आय/i.test(text)) {
      result.income = 0;
    }
  }

  // 5. Occupation Extraction
  // Student, College, School, Coaching, Economics / Higher Education
  if (
    /विद्यार्थी|छात्र|छात्रा|student|study|studying|padhai|padh\s*raha|padh\s*rahi|padhti|padhta|कॉलेज|कालेज|college|स्कूल|विद्यालय|school|coaching|कोचिंग|10th|12th|10वीं|12वीं|b\.?tech|b\.?sc|b\.?a\b|b\.?com|diploma|iti\b|neet|jee|upsc|ras|ssc|bed|b\.?ed|scholarship|छात्रवृत्ति|पढ़ती|पढ़ता|पढ़ते|पढ़ाई|पढ़\s*रहा|पढ़\s*रही|अध्ययन|अर्थशास्त्र|economics|arts|commerce|science|ग्रेजुएशन|पोस्ट\s*ग्रेजुएशन|डिग्री/i.test(text)
  ) {
    result.occupation = "STUDENT";
    result.isStudent = true;
    if (/कॉलेज|कालेज|college|महाविद्यालय|विश्वविद्यालय|ग्रेजुएशन|degree|डिग्री|b\.?tech|b\.?sc|b\.?a|b\.?com|अर्थशास्त्र|economics/i.test(text)) {
      result.courseLevel = "COLLEGE";
    } else if (/कोचिंग|coaching|प्रतियोगी|competition|neet|jee|upsc|ras|ssc/i.test(text)) {
      result.courseLevel = "COACHING";
    } else if (/स्कूल|विद्यालय|school|10th|12th|10वीं|12वीं/i.test(text)) {
      result.courseLevel = "SCHOOL";
    }
  }
  // Farmer & Agriculture
  else if (
    /किसान|खेती|कृषक|farmer|agriculture|काश्तकार|खेतीहर|kisan|kheti|fasal|jamabandi|khet\b|bigha|बीघा|फसल|agro|खाद|बीज|पटवारी|गिरदावरी/i.test(text)
  ) {
    result.occupation = "FARMER";
  }
  // Self-Employed, MSME, Entrepreneur, Shopkeeper, Artisan
  else if (
    /स्वरोजगार|दुकान|व्यापार|बिजनेस|business|self\s*employed|दुकानदार|छोटा\s*व्यापारी|dukan|shop|vyapar|thela|vendor|artisan|vishwakarma|karigar|tailor|darji|lohar|kumhar|suthar|entrepreneur|mudra|pmegp|startup|udyam|कारोबार|सिलाई|टेलरिंग|ब्यूटी/i.test(text)
  ) {
    result.occupation = "SELF_EMPLOYED";
  }
  // Laborer, Construction Worker, Daily Wage
  else if (
    /मजदूर|श्रमिक|दिहाड़ी|labor|labour|daily\s*wage|मजदूरी|कारीगर|majdoor|mazdoor|shramik|dihadi|mistri|driver|beldar|safai\s*karmi|shramik\s*card|श्रम/i.test(text)
  ) {
    result.occupation = "LABORER";
  }
  // Homemaker
  else if (/गृहणी|गृहिणी|हाउसवाइफ|homemaker|housewife|grihini|महिला|औरत/i.test(text)) {
    result.occupation = "HOMEMAKER";
    result.gender = "FEMALE";
  }
  // Unemployed
  else if (/बेरोजगार|unemployed|नौकरी\s*नहीं|jobless|no\s*job/i.test(text)) {
    result.occupation = "UNEMPLOYED";
  }
  // Retired / Senior Citizen
  else if (/रिटायर्ड|सेवानिवृत्त|retired|वरिष्ठ\s*नागरिक|senior|old\s*age|बुजुर्ग|बूढ़े|वृद्ध|पेंशनर|vridh/i.test(text)) {
    result.occupation = "RETIRED";
  }

  // 6. Residence (Rural / Urban)
  if (/ग्रामीण|गांव|गाँव|देहात|rural|village/i.test(text)) {
    result.residence = "RURAL";
  } else if (/शहरी|शहर|कस्बा|urban|city|town/i.test(text)) {
    result.residence = "URBAN";
  }

  // 7. District Extraction
  for (const [key, distName] of Object.entries(DISTRICTS_MAP)) {
    const regex = new RegExp(`\\b${key}\\b`, "i");
    if (regex.test(text)) {
      result.district = distName;
      break;
    }
  }

  // 8. Ration Card / Tier
  if (/अंत्योदय|aay|गुलाबी\s*कार्ड/i.test(text)) {
    result.rationCard = "AAY";
  } else if (/बीपीएल|bpl|पीला\s*कार्ड/i.test(text)) {
    result.rationCard = "BPL";
  } else if (/स्टेट\s*बीपीएल|state\s*bpl/i.test(text)) {
    result.rationCard = "STATE_BPL";
  } else if (/खाद्य\s*सुरक्षा|nfsa|राशन/i.test(text)) {
    result.rationCard = "NFSA";
  } else if (/सामान्य\s*राशन|non\s*bpl|apl|एपीएल/i.test(text)) {
    result.rationCard = "NONE";
  }

  // 9. Special Criteria (Widow, Disability, Land)
  if (/विधवा|पति\s*नहीं|widow|एकल\s*नारी|परित्यक्ता/i.test(text)) {
    result.isWidow = true;
    result.maritalStatus = "WIDOW";
    result.gender = "FEMALE";
  }

  if (/दिव्यांग|विकलांग|अपंग|अंधा|handicap|disabled|special\s*need/i.test(text)) {
    result.isDisabled = true;
    const pctMatch = text.match(/(\d{2,3})\s*%/);
    if (pctMatch) {
      result.disabilityPercent = Math.min(100, Math.max(40, parseInt(pctMatch[1], 10)));
    }
  }

  // Landholding Bigha
  const landMatch = text.match(/(\d+(?:\.\d+)?)\s*(?:बीघा|bigha|bighas|bighe|एकड़|acre|हेक्टेयर|hectare)/i);
  if (landMatch && landMatch[1]) {
    result.landBigha = parseFloat(landMatch[1]);
    result.occupation = "FARMER";
  } else if (/भूमिहीन|जमीन\s*नहीं|ज़मीन\s*नहीं|landless/i.test(text)) {
    result.landBigha = 0;
  }

  // Jan Aadhaar
  if (/जन\s*आधार|जनआधार|jan\s*aadhaar/i.test(text)) {
    result.hasJanAadhaar = true;
  }

  return result;
}
