"""
JanSetu - Day 26 Tests: Speech Text Normalization.

Verifies deterministic expansion of currency, numbers, ages, percentages,
dates, boundary operators, acronyms, and Rajasthan districts, while
strictly preserving canonical display text, inclusive bounds, and negation.
"""

import pytest
from app.tts.speech_normalizer import (
    SpeechTextNormalizer,
    int_to_hindi_words,
)


class TestSpeechTextNormalizer:
    """Test suite for SpeechTextNormalizer."""

    def test_int_to_hindi_words(self):
        assert int_to_hindi_words(0) == "शून्य"
        assert int_to_hindi_words(1) == "एक"
        assert int_to_hindi_words(10) == "दस"
        assert int_to_hindi_words(60) == "साठ"
        assert int_to_hindi_words(62) == "बासठ"
        assert int_to_hindi_words(65) == "पैंसठ"
        assert int_to_hindi_words(100) == "सौ"
        assert int_to_hindi_words(500) == "पांच सौ"
        assert int_to_hindi_words(1000) == "एक हजार"
        assert int_to_hindi_words(15000) == "पंद्रह हजार"
        assert int_to_hindi_words(150000) == "एक लाख पचास हजार"
        assert int_to_hindi_words(200000) == "दो लाख"
        assert int_to_hindi_words(250000) == "दो लाख पचास हजार"
        assert int_to_hindi_words(1000000) == "दस लाख"

    def test_currency_rupees_normalization(self):
        # 1,50,000
        text = "आपने वार्षिक पारिवारिक आय ₹1,50,000 बताई है।"
        norm = SpeechTextNormalizer.normalize_for_speech(text)
        assert "एक लाख पचास हजार रुपये" in norm
        assert "बताई है" in norm

        # ₹500
        text2 = "पंजीकरण शुल्क ₹500 है।"
        assert "पांच सौ रुपये" in SpeechTextNormalizer.normalize_for_speech(text2)

        # ₹10,00,000
        text3 = "बीमा कवर ₹10,00,000 है।"
        assert "दस लाख रुपये" in SpeechTextNormalizer.normalize_for_speech(text3)

    def test_currency_with_periodicity(self):
        # Monthly
        text = "पात्र नागरिकों को ₹1,000 प्रति माह दिए जाते हैं।"
        norm = SpeechTextNormalizer.normalize_for_speech(text)
        assert "एक हजार रुपये प्रति माह" in norm

        # Annual
        text2 = "आय सीमा ₹2,00,000 प्रति वर्ष है।"
        norm2 = SpeechTextNormalizer.normalize_for_speech(text2)
        assert "दो लाख रुपये प्रति वर्ष" in norm2

    def test_decimal_scale(self):
        text = "वार्षिक आय 1.5 लाख रुपये से कम होनी चाहिए।"
        norm = SpeechTextNormalizer.normalize_for_speech(text)
        assert "एक लाख पचास हजार रुपये" in norm

    def test_age_and_number_cardinals(self):
        text = "आपने अपनी आयु 62 वर्ष बताई है। क्या यह सही है?"
        norm = SpeechTextNormalizer.normalize_for_speech(text)
        assert "बासठ वर्ष" in norm
        assert "क्या यह सही है?" in norm

        text2 = "पात्रता 60 वर्ष से अधिक होनी चाहिए।"
        assert "साठ वर्ष से अधिक" in SpeechTextNormalizer.normalize_for_speech(text2)

        text3 = "वरिष्ठ नागरिक 65 वर्ष के बाद आवेदन कर सकते हैं।"
        assert "पैंसठ वर्ष" in SpeechTextNormalizer.normalize_for_speech(text3)

    def test_percentage_normalization(self):
        text = "दिव्यांगता 40% या अधिक होनी चाहिए।"
        norm = SpeechTextNormalizer.normalize_for_speech(text)
        assert "चालीस प्रतिशत या अधिक" in norm

        text2 = "कम से कम 45% अंक आवश्यक हैं।"
        assert "पैंतालीस प्रतिशत" in SpeechTextNormalizer.normalize_for_speech(text2)

        text3 = "उपस्थिति 75% होनी चाहिए।"
        assert "पचहत्तर प्रतिशत" in SpeechTextNormalizer.normalize_for_speech(text3)

    def test_date_normalization(self):
        text1 = "सत्र 1 अक्टूबर 2026 से शुरू होगा।"
        norm1 = SpeechTextNormalizer.normalize_for_speech(text1)
        assert "एक अक्टूबर दो हजार छब्बीस" in norm1

        text2 = "अंतिम तिथि 31 मार्च 2027 है।"
        norm2 = SpeechTextNormalizer.normalize_for_speech(text2)
        assert "इकतीस मार्च दो हजार सत्ताईस" in norm2

        text3 = "कार्यक्रम 15 अगस्त 2026 को है।"
        norm3 = SpeechTextNormalizer.normalize_for_speech(text3)
        assert "पंद्रह अगस्त दो हजार छब्बीस" in norm3

    def test_boundary_operators(self):
        text = "पारिवारिक आय <= ₹2,00,000 होनी चाहिए।"
        norm = SpeechTextNormalizer.normalize_for_speech(text)
        assert "दो लाख रुपये या उससे कम" in norm

        text2 = "आयु >= 60 वर्ष होनी चाहिए।"
        norm2 = SpeechTextNormalizer.normalize_for_speech(text2)
        assert "साठ वर्ष या उससे अधिक" in norm2

    def test_acronym_expansions(self):
        text = "आप ई-मित्र या SSO पोर्टल से BPL कार्ड के लिए आवेदन करें।"
        norm = SpeechTextNormalizer.normalize_for_speech(text)
        assert "ई-मित्र" in norm
        assert "एस एस ओ" in norm
        assert "बी पी एल" in norm

        # Variants
        assert "ई-मित्र" in SpeechTextNormalizer.normalize_for_speech("e-Mitra केंद्र")
        assert "ई-मित्र" in SpeechTextNormalizer.normalize_for_speech("eMitra पर जाएं")

    def test_rajasthan_districts(self):
        districts = [
            "उदयपुर", "डूंगरपुर", "बांसवाड़ा", "चित्तौड़गढ़",
            "झालावाड़", "प्रतापगढ़", "जैसलमेर", "श्रीगंगानगर", "सवाई माधोपुर"
        ]
        for d in districts:
            text = f"नागरिक {d} जिले के निवासी हैं।"
            norm = SpeechTextNormalizer.normalize_for_speech(text)
            assert d in norm

    def test_critical_negation_preserved(self):
        text = "यदि आपको पहले से यह लाभ मिल रहा है, तो आप पात्र नहीं हैं।"
        norm = SpeechTextNormalizer.normalize_for_speech(text)
        assert "पात्र नहीं हैं।" in norm
        assert "नहीं" in norm

    def test_url_sanitization(self):
        text = "कृपया अधिक जानकारी के लिए https://sso.rajasthan.gov.in/portal पर जाएं।"
        norm = SpeechTextNormalizer.normalize_for_speech(text)
        assert "https://" not in norm
        assert "sso.rajasthan.gov.in" not in norm
        assert "आधिकारिक वेबसाइट का लिंक स्क्रीन पर दिया गया है।" in norm

    def test_markdown_and_emoji_cleaning(self):
        text = "**महत्वपूर्ण:** योजना के तहत *निशुल्क* लाभ मिलेगा! 👍✨"
        norm = SpeechTextNormalizer.normalize_for_speech(text)
        assert "**" not in norm
        assert "*" not in norm
        assert "👍" not in norm
        assert "महत्वपूर्ण: योजना के तहत निशुल्क लाभ मिलेगा!" in norm

    def test_ordinary_hindi_unmodified(self):
        text = "आपकी आयु क्या है?"
        assert SpeechTextNormalizer.normalize_for_speech(text) == "आपकी आयु क्या है?"

        text2 = "कृपया दोबारा बताइए।"
        assert SpeechTextNormalizer.normalize_for_speech(text2) == "कृपया दोबारा बताइए।"
