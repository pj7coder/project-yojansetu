import re
from typing import List, Set


# Ignored noise tokens in filenames / titles during candidate matching
NOISE_TITLE_TOKENS = {
    "final",
    "copy",
    "download",
    "new",
    "latest",
    "doc",
    "pdf",
    "file",
    "draft",
    "scan",
    "circular",
    "notification",
}


def tokenize_words(text: str) -> List[str]:
    """
    Tokenize text into alphanumeric words and vernacular Hindi tokens.
    Preserves Hindi unicode characters (\w includes Devanagari in Python regex).
    """
    return [w for w in re.findall(r"\w+", text.lower()) if len(w) > 1]


def generate_word_shingles(text: str, shingle_size: int = 3) -> Set[str]:
    """
    Generate n-gram word shingles from normalized text.
    If text has fewer words than shingle_size, generates 1-grams or 2-grams.
    """
    words = tokenize_words(text)
    if not words:
        return set()

    if len(words) < shingle_size:
        return {" ".join(words)}

    shingles = set()
    for i in range(len(words) - shingle_size + 1):
        shingles.add(" ".join(words[i : i + shingle_size]))
    return shingles


def calculate_jaccard_similarity(text1: str, text2: str, shingle_size: int = 3) -> float:
    """
    Calculate the Jaccard similarity between two texts using word n-gram shingles.
    Returns a score between 0.0 (completely disjoint) and 1.0 (identical shingles).
    """
    if not text1 or not text2:
        return 0.0

    if text1 == text2:
        return 1.0

    shingles1 = generate_word_shingles(text1, shingle_size=shingle_size)
    shingles2 = generate_word_shingles(text2, shingle_size=shingle_size)

    if not shingles1 or not shingles2:
        return 0.0

    intersection = len(shingles1.intersection(shingles2))
    union = len(shingles1.union(shingles2))

    if union == 0:
        return 0.0

    return round(intersection / union, 4)


def clean_title_tokens(title_or_filename: str) -> Set[str]:
    """Extract meaningful title tokens ignoring formatting and version noise."""
    tokens = tokenize_words(title_or_filename)
    return {
        t for t in tokens
        if t not in NOISE_TITLE_TOKENS and not t.isdigit() and len(t) > 2
    }


def calculate_title_similarity(title1: str, title2: str) -> float:
    """Calculate token overlap between two document titles or filenames."""
    if not title1 or not title2:
        return 0.0

    t1 = clean_title_tokens(title1)
    t2 = clean_title_tokens(title2)

    if not t1 or not t2:
        return 0.0

    intersection = len(t1.intersection(t2))
    union = len(t1.union(t2))

    return round(intersection / union, 4) if union > 0 else 0.0
