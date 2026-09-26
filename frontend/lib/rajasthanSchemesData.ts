/**
 * Official Rajasthan Flagship Welfare Schemes Catalog.
 * Curated from verified circulars, gazetted rules, and seed specifications.
 */

export interface RajasthanSchemeItem {
  code: string;
  name_en: string;
  name_hi: string;
  short_name: string;
  dept_code: string;
  department_en: string;
  department_hi: string;
  category: string;
  desc_en: string;
  desc_hi: string;
  circular_no: string;
  payout_summary_hi: string;
  payout_summary_en: string;
  annual_or_monthly_val: number;
  frequency: 'MONTHLY' | 'ANNUAL' | 'ONE_TIME' | 'PER_CYLINDER';
  mandatory_docs: Array<{ name_en: string; name_hi: string }>;
  apply_channel_hi: string;
  apply_channel_en: string;
  // Matching criteria function
  isEligible: (profile: Record<string, any>) => boolean;
  needsMoreInfo: (profile: Record<string, any>) => string | null; // returns missing field name if applicable
}

export const RAJASTHAN_FLAGSHIP_SCHEMES: RajasthanSchemeItem[] = [
  {
    code: 'RJ-PENSION-VRIDHJAN',
    name_en: 'Mukhyamantri Vridhjan Samman Pension Yojana',
    name_hi: 'मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना',
    short_name: 'वृद्धजन पेंशन',
    dept_code: 'SJE',
    department_en: 'Social Justice and Empowerment Department',
    department_hi: 'सामाजिक न्याय एवं अधिकारिता विभाग',
    category: 'पेंशन (सामाजिक सुरक्षा)',
    desc_en: 'Monthly financial pension assistance for senior citizen residents of Rajasthan with low family income.',
    desc_hi: 'राजस्थान के वरिष्ठ नागरिकों (महिला 55+ वर्ष, पुरुष 58+ वर्ष) को जीवन-यापन हेतु ₹1,000 से ₹1,500 मासिक पेंशन।',
    circular_no: 'F.1(3)/PENS/SJE/2023/1842',
    payout_summary_hi: '₹1,000 - ₹1,500 प्रति माह DBT',
    payout_summary_en: '₹1,000 - ₹1,500 per month DBT',
    annual_or_monthly_val: 1000,
    frequency: 'MONTHLY',
    mandatory_docs: [
      { name_en: 'Jan Aadhaar Card', name_hi: 'जन आधार कार्ड' },
      { name_en: 'Aadhaar Card (Age Proof)', name_hi: 'आधार कार्ड (आयु प्रमाण)' },
      { name_en: 'Income Declaration (<= ₹48,000/yr)', name_hi: 'आय स्व-घोषणा पत्र' },
      { name_en: 'Bank Passbook', name_hi: 'बैंक पासबुक' },
    ],
    apply_channel_hi: 'नज़दीकी ई-मित्र कियोस्क अथवा जन आधार पोर्टल से ऑनलाइन',
    apply_channel_en: 'Nearest e-Mitra Kiosk or Jan Aadhaar Portal',
    isEligible: (p) => {
      const age = Number(p.age || 0);
      const isFemale = p.gender === 'FEMALE';
      const income = p.annual_income !== undefined ? Number(p.annual_income) : 40000;
      const ageOk = isFemale ? age >= 55 : age >= 58;
      return ageOk && income <= 48000;
    },
    needsMoreInfo: (p) => {
      if (p.age === undefined) return 'age';
      if (p.annual_income === undefined && !p.is_bpl) return 'annual_income';
      return null;
    },
  },
  {
    code: 'RJ-HEALTH-MAA',
    name_en: 'Mukhyamantri Ayushman Arogya Yojana (MAA)',
    name_hi: 'मुख्यमंत्री आयुष्मान आरोग्य योजना (एम.ए.ए.)',
    short_name: 'आयुष्मान स्वास्थ्य बीमा',
    dept_code: 'HEALTH',
    department_en: 'Medical, Health and Family Welfare Department',
    department_hi: 'चिकित्सा एवं स्वास्थ्य विभाग',
    category: 'स्वास्थ्य उपचार (कैशलेस)',
    desc_en: 'Universal health insurance providing up to ₹25 Lakh cashless hospital treatment per family in Rajasthan.',
    desc_hi: 'राजस्थान के प्रत्येक जन आधार धारक परिवार को ₹25 लाख तक का कैशलेस अस्पताल उपचार व ₹10 लाख दुर्घटना बीमा।',
    circular_no: 'DHS/MAA/Rules/2023/5021',
    payout_summary_hi: '₹25 लाख कैशलेस उपचार + ₹10 लाख दुर्घटना बीमा',
    payout_summary_en: '₹25 Lakh cashless treatment + ₹10 Lakh insurance',
    annual_or_monthly_val: 2500000,
    frequency: 'ANNUAL',
    mandatory_docs: [
      { name_en: 'Jan Aadhaar Card', name_hi: 'जन आधार कार्ड' },
      { name_en: 'Aadhaar Card', name_hi: 'आधार कार्ड' },
    ],
    apply_channel_hi: 'सभी सम्बद्ध सरकारी एवं निजी अस्पतालों में जन आधार कार्ड द्वारा सीधा कैशलेस प्रवेश',
    apply_channel_en: 'Direct cashless admission at 1,800+ empanelled hospitals via Jan Aadhaar',
    isEligible: (p) => {
      return p.has_jan_aadhaar !== false;
    },
    needsMoreInfo: () => null,
  },
  {
    code: 'RJ-AGRI-KISAN-SAMMAN',
    name_en: 'Mukhyamantri Kisan Samman Nidhi & Saathi Yojana',
    name_hi: 'मुख्यमंत्री किसान सम्मान निधि व साथी योजना',
    short_name: 'किसान सम्मान निधि',
    dept_code: 'AGRI',
    department_en: 'Department of Agriculture, Rajasthan',
    department_hi: 'कृषि विभाग, राजस्थान',
    category: 'कृषि एवं किसान कल्याण',
    desc_en: 'Direct financial assistance of ₹8,000/year and up to 75% solar/drip equipment subsidies for small & marginal farmers.',
    desc_hi: 'लघु एवं सीमांत किसानों (भूमि <= 12.5 बीघा) को ₹8,000 वार्षिक सीधा बैंक अंतरण एवं सोलर/ड्रिप संयंत्र पर 75% तक अनुदान।',
    circular_no: 'AGRI/DIR/F.8(2)/KISAN/2024/782',
    payout_summary_hi: '₹8,000 प्रति वर्ष (3 किश्तों में DBT) + 75% कृषि यंत्र अनुदान',
    payout_summary_en: '₹8,000 per year (DBT in 3 installments) + 75% farm subsidy',
    annual_or_monthly_val: 8000,
    frequency: 'ANNUAL',
    mandatory_docs: [
      { name_en: 'Jan Aadhaar Card', name_hi: 'जन आधार कार्ड' },
      { name_en: 'Jamabandi Nakal (Land Record)', name_hi: 'जमाबंदी नकल / खतौनी' },
      { name_en: 'Jan Aadhaar Linked Bank Passbook', name_hi: 'बैंक पासबुक' },
    ],
    apply_channel_hi: 'राजकिसान साथी पोर्टल (RajKisan) अथवा नजदीकी ई-मित्र पर जमाबंदी दर्ज कराएं',
    apply_channel_en: 'RajKisan Saathi Portal or local e-Mitra kiosk',
    isEligible: (p) => {
      const isFarmer = p.occupation === 'FARMER' || (p.land_area_bigha !== undefined && p.land_area_bigha > 0);
      const land = p.land_area_bigha !== undefined ? Number(p.land_area_bigha) : 3;
      return isFarmer && land <= 12.5;
    },
    needsMoreInfo: (p) => {
      if (p.occupation === 'FARMER' && p.land_area_bigha === undefined) return 'land_area_bigha';
      return null;
    },
  },
  {
    code: 'RJ-PENSION-EKAL-NARI',
    name_en: 'Mukhyamantri Ekal Nari Samman Pension Yojana',
    name_hi: 'मुख्यमंत्री एकल नारी सम्मान पेंशन योजना',
    short_name: 'एकल नारी (विधवा) पेंशन',
    dept_code: 'SJE',
    department_en: 'Social Justice and Empowerment Department',
    department_hi: 'सामाजिक न्याय एवं अधिकारिता विभाग',
    category: 'पेंशन (महिला कल्याण)',
    desc_en: 'Monthly pension of ₹1,000 to ₹1,500 for widowed, divorced, and separated women aged 18+ in Rajasthan.',
    desc_hi: '18 वर्ष से अधिक आयु की विधवा, तलाकशुदा एवं परित्यक्ता महिलाओं को ₹1,000 से ₹1,500 प्रतिमाह सम्मान पेंशन।',
    circular_no: 'SJE/PENS/EKAL/2023/1109',
    payout_summary_hi: '₹1,000 - ₹1,500 प्रति माह आयु अनुसार',
    payout_summary_en: '₹1,000 - ₹1,500 per month graded by age',
    annual_or_monthly_val: 1000,
    frequency: 'MONTHLY',
    mandatory_docs: [
      { name_en: 'Jan Aadhaar Card', name_hi: 'जन आधार कार्ड' },
      { name_en: 'Husband Death Certificate / Divorce Order', name_hi: 'पति का मृत्यु प्रमाण पत्र / तलाक आदेश' },
      { name_en: 'Income Certificate (<= ₹48,000)', name_hi: 'आय प्रमाण पत्र' },
    ],
    apply_channel_hi: 'ई-मित्र कियोस्क अथवा सामाजिक सुरक्षा पेंशन पोर्टल',
    apply_channel_en: 'e-Mitra Kiosk or Social Security Pension Portal (SSO)',
    isEligible: (p) => {
      const isWidowOrSeparated = p.is_widow || p.marital_status === 'WIDOWED' || p.marital_status === 'DIVORCED';
      const age = Number(p.age || 25);
      const income = p.annual_income !== undefined ? Number(p.annual_income) : 36000;
      return isWidowOrSeparated && age >= 18 && income <= 48000;
    },
    needsMoreInfo: (p) => {
      if (p.is_widow && p.annual_income === undefined && !p.is_bpl) return 'annual_income';
      return null;
    },
  },
  {
    code: 'RJ-WOMEN-PALANHAR',
    name_en: 'Palanhar Yojana',
    name_hi: 'पालनहार योजना',
    short_name: 'पालनहार बाल सहायता',
    dept_code: 'SJE',
    department_en: 'Social Justice and Empowerment Department',
    department_hi: 'सामाजिक न्याय एवं अधिकारिता विभाग',
    category: 'बाल संरक्षण एवं पोषण',
    desc_en: 'Financial foster-care assistance for caretakers of orphan children, children of widowed mothers, and disabled parents.',
    desc_hi: 'अनाथ बच्चों व विधवा माता के बच्चों के भरण-पोषण हेतु ₹1,500 से ₹2,500 प्रतिमाह + ₹2,000 वार्षिक पोशाक अनुदान।',
    circular_no: 'F.14(10)PALANHAR/SJE/2023/349',
    payout_summary_hi: '₹1,500 - ₹2,500/माह + ₹2,000 वार्षिक पोशाक अनुदान',
    payout_summary_en: '₹1,500 - ₹2,500/month + ₹2,000 clothing grant',
    annual_or_monthly_val: 2000,
    frequency: 'MONTHLY',
    mandatory_docs: [
      { name_en: 'Jan Aadhaar Card', name_hi: 'जन आधार कार्ड' },
      { name_en: 'Child Study Certificate (School)', name_hi: 'बच्चे का अध्ययनरत स्कूल प्रमाण पत्र' },
      { name_en: 'Father Death Certificate', name_hi: 'पिता का मृत्यु प्रमाण पत्र' },
    ],
    apply_channel_hi: 'पालनहार पोर्टल अथवा ई-मित्र कियोस्क द्वारा',
    apply_channel_en: 'Palanhar Portal or local e-Mitra',
    isEligible: (p) => {
      return Boolean(p.is_widow || p.has_orphan_child || p.is_disabled);
    },
    needsMoreInfo: () => null,
  },
  {
    code: 'RJ-EDU-ANUPRATI',
    name_en: 'Mukhyamantri Anuprati Coaching Yojana',
    name_hi: 'मुख्यमंत्री अनुप्रति कोचिंग योजना',
    short_name: 'अनुप्रति निःशुल्क कोचिंग',
    dept_code: 'SJE',
    department_en: 'Social Justice and Empowerment Department',
    department_hi: 'सामाजिक न्याय एवं अधिकारिता विभाग',
    category: 'शिक्षा एवं निःशुल्क कोचिंग',
    desc_en: '100% free competitive exam coaching (UPSC, RAS, REET, NEET, IIT) + ₹40,000 hostel stipend for meritorious students.',
    desc_hi: 'UPSC, RAS, REET, NEET, IIT-JEE की तैयारी हेतु प्रतिष्ठित संस्थानों से 100% निःशुल्क कोचिंग एवं ₹40,000 हॉस्टल भत्ता।',
    circular_no: 'SJE/ANUPRATI/SCHEME/2024/114',
    payout_summary_hi: '100% निःशुल्क कोचिंग फीस + ₹40,000 वार्षिक हॉस्टल भत्ता',
    payout_summary_en: '100% Free Coaching + ₹40,000 Annual Hostel Grant',
    annual_or_monthly_val: 100000,
    frequency: 'ANNUAL',
    mandatory_docs: [
      { name_en: 'Jan Aadhaar Card', name_hi: 'जन आधार कार्ड' },
      { name_en: 'Class 10th & 12th Marksheets', name_hi: '10वीं व 12वीं की अंकतालिका' },
      { name_en: 'Caste / EWS Certificate', name_hi: 'जाति / ईडब्ल्यूएस प्रमाण पत्र' },
      { name_en: 'Income Certificate (<= ₹8 Lakh)', name_hi: 'आय प्रमाण पत्र (₹8 लाख तक)' },
    ],
    apply_channel_hi: 'एसएसओ पोर्टल (SSO Rajasthan) पर SJMS डीएसटी पोर्टल द्वारा ऑनलाइन',
    apply_channel_en: 'SSO Rajasthan (SJMS Coaching Portal) or e-Mitra',
    isEligible: (p) => {
      const isStudent = p.is_student || p.occupation === 'STUDENT' || (p.age && p.age >= 16 && p.age <= 30);
      const income = p.annual_income !== undefined ? Number(p.annual_income) : 200000;
      return Boolean(isStudent && income <= 800000);
    },
    needsMoreInfo: (p) => {
      if (p.is_student && p.caste_category === undefined) return 'caste_category';
      return null;
    },
  },
  {
    code: 'RJ-CIVIL-GAS-SUBSIDY',
    name_en: 'Indira Gandhi Gas Cylinder Subsidy Yojana',
    name_hi: 'इंदिरा गांधी गैस सिलेंडर सब्सिडी योजना',
    short_name: '₹450 रसोई गैस सिलेंडर',
    dept_code: 'FINANCE',
    department_en: 'Food and Civil Supplies Department',
    department_hi: 'खाद्य एवं नागरिक आपूर्ति विभाग',
    category: 'घरेलू राहत एवं सब्सिडी',
    desc_en: 'Subsidized domestic LPG gas cylinder at only ₹450 with direct cashback for PM Ujjwala and BPL cardholder families.',
    desc_hi: 'उज्ज्वला योजना एवं बीपीएल राशन कार्डधारक परिवारों को मात्र ₹450 में घरेलू एलपीजी गैस सिलेंडर (प्रतिवर्ष 12 सिलेंडर)।',
    circular_no: 'FCS/LPG/SUBSIDY/2023/1299',
    payout_summary_hi: '₹450 में गैस सिलेंडर (शेष सब्सिडी बैंक खाते में DBT)',
    payout_summary_en: 'LPG Cylinder at ₹450 (cashback subsidy via DBT)',
    annual_or_monthly_val: 500,
    frequency: 'PER_CYLINDER',
    mandatory_docs: [
      { name_en: 'Jan Aadhaar Card', name_hi: 'जन आधार कार्ड' },
      { name_en: 'LPG Gas Connection Consumer Diary', name_hi: 'गैस कनेक्शन डायरी / उपभोक्ता संख्या' },
      { name_en: 'BPL Card / Ujjwala ID', name_hi: 'बीपीएल राशन कार्ड / उज्ज्वला आईडी' },
    ],
    apply_channel_hi: 'जन आधार से गैस कनेक्शन सीड कराएं अथवा गैस एजेंसी पर दर्ज कराएं',
    apply_channel_en: 'Seed gas connection with Jan Aadhaar at e-Mitra or gas agency',
    isEligible: (p) => {
      return Boolean(p.is_bpl || p.is_ujjwala_beneficiary || p.annual_income && p.annual_income <= 60000);
    },
    needsMoreInfo: () => null,
  },
  {
    code: 'RJ-SJE-DIVYANG-PENSION',
    name_en: 'Vishesh Yogyajan Samman Pension Yojana',
    name_hi: 'विशेष योग्यजन सम्मान पेंशन योजना',
    short_name: 'दिव्यांग पेंशन',
    dept_code: 'SJE',
    department_en: 'Social Justice and Empowerment Department',
    department_hi: 'सामाजिक न्याय एवं अधिकारिता विभाग',
    category: 'पेंशन (विशेष योग्यजन)',
    desc_en: 'Monthly pension of ₹1,000 to ₹1,500 for specially-abled citizens with 40%+ certified disability in Rajasthan.',
    desc_hi: '40% या अधिक दिव्यांगता वाले नागरिकों को जीवन-यापन हेतु ₹1,000 से ₹1,500 प्रतिमाह सामाजिक सुरक्षा पेंशन।',
    circular_no: 'SJE/PENS/DIVYANG/2023/1402',
    payout_summary_hi: '₹1,000 - ₹1,500 प्रति माह DBT',
    payout_summary_en: '₹1,000 - ₹1,500 per month DBT',
    annual_or_monthly_val: 1000,
    frequency: 'MONTHLY',
    mandatory_docs: [
      { name_en: 'Jan Aadhaar Card', name_hi: 'जन आधार कार्ड' },
      { name_en: 'Disability Certificate (40%+ UDID Card)', name_hi: 'दिव्यांगता प्रमाण पत्र (UDID कार्ड)' },
      { name_en: 'Income Certificate (<= ₹60,000)', name_hi: 'आय प्रमाण पत्र (बीपीएल हेतु छूट)' },
    ],
    apply_channel_hi: 'ई-मित्र कियोस्क अथवा सामाजिक सुरक्षा पेंशन पोर्टल',
    apply_channel_en: 'Nearest e-Mitra Kiosk or Social Security Portal',
    isEligible: (p) => {
      const income = p.annual_income !== undefined ? Number(p.annual_income) : 40000;
      return Boolean(p.is_disabled && income <= 60000);
    },
    needsMoreInfo: (p) => {
      if (p.is_disabled && p.annual_income === undefined && !p.is_bpl) return 'annual_income';
      return null;
    },
  },
  {
    code: 'RJ-EDU-KALI-BAI-SCOOTY',
    name_en: 'Kali Bai Bheel Medhavi Chhatra Scooty Yojana',
    name_hi: 'काली बाई भील मेधावी छात्रा स्कूटी योजना',
    short_name: 'काली बाई स्कूटी',
    dept_code: 'EDUCATION',
    department_en: 'College Education Department',
    department_hi: 'कॉलेज शिक्षा विभाग',
    category: 'शिक्षा एवं प्रोत्साहन',
    desc_en: 'Free motorized scooty distribution for meritorious girl students in Rajasthan passing Class 12 and enrolled in college.',
    desc_hi: '12वीं कक्षा में 65%+ अंक प्राप्त करने वाली कॉलेज में अध्ययनरत नियमित छात्राओं को निःशुल्क स्कूटी एवं ₹10,000 प्रोत्साहन।',
    circular_no: 'HED/COMM/SCOOTY/2023/910',
    payout_summary_hi: 'निःशुल्क स्कूटी + 1 वर्ष बीमा + ₹10,000 प्रोत्साहन',
    payout_summary_en: 'Free Motorized Scooty + 1-Yr Insurance + ₹10,000 grant',
    annual_or_monthly_val: 85000,
    frequency: 'ONE_TIME',
    mandatory_docs: [
      { name_en: 'Jan Aadhaar Card', name_hi: 'जन आधार कार्ड' },
      { name_en: 'Class 12th Marksheet (>= 65%)', name_hi: '12वीं की अंकतालिका' },
      { name_en: 'College Admission Fee Receipt', name_hi: 'कॉलेज प्रवेश शुल्क रसीद' },
      { name_en: 'Income Certificate (<= ₹2.5 Lakh)', name_hi: 'आय प्रमाण पत्र (₹2.5 लाख तक)' },
    ],
    apply_channel_hi: 'उच्च शिक्षा विभाग छात्रवृत्ति पोर्टल (HTE Rajasthan) अथवा ई-मित्र',
    apply_channel_en: 'HTE Rajasthan Portal or e-Mitra',
    isEligible: (p) => {
      const isFemale = p.gender === 'FEMALE';
      const isStudent = p.is_student || p.occupation === 'STUDENT';
      const income = p.annual_income !== undefined ? Number(p.annual_income) : 150000;
      return isFemale && isStudent && income <= 250000;
    },
    needsMoreInfo: () => null,
  },
];
