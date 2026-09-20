import re

# Regex separating words, whitespace, and punctuation
WORD_SPLIT_REGEX = re.compile(r"\s+")
DEVANAGARI_CHAR_REGEX = re.compile(r"[\u0900-\u097F\uA8E0-\uA8FF]")


def estimate_tokens(text: str) -> int:
    """
    Calibrated token count estimator for Llama 3.2 tokenization.

    Llama byte-pair encoding (BPE) expands Devanagari / Hindi script into
    subword tokens (~1.5 to 1.8 tokens per word) due to UTF-8 multibyte representation,
    whereas standard English averages ~1.3 tokens per word.

    Args:
        text: Input string (English, Hindi, or mixed)

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    tokens = 0
    words = WORD_SPLIT_REGEX.split(text.strip())

    for w in words:
        if not w:
            continue

        devanagari_chars = len(DEVANAGARI_CHAR_REGEX.findall(w))
        latin_and_other = len(w) - devanagari_chars

        # Devanagari token weight: ~0.45 tokens per character (min 1 per word)
        devanagari_tokens = max(1, int(round(devanagari_chars * 0.45))) if devanagari_chars > 0 else 0

        # Latin/ASCII token weight: ~0.25 tokens per character (min 1 per word)
        latin_tokens = max(1, int(round(latin_and_other * 0.28))) if latin_and_other > 0 else 0

        tokens += (devanagari_tokens + latin_tokens)

    return max(1, tokens) if text.strip() else 0
