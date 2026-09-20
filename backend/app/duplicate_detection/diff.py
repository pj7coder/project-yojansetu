import difflib
import re
from dataclasses import dataclass, field
from typing import List, Set


# Controlled version and amendment indicator keywords
VERSION_KEYWORDS_EN: Set[str] = {
    "amendment",
    "revised",
    "revision",
    "updated",
    "notification",
    "corrigendum",
    "addendum",
    "modified",
    "supersession",
    "amended",
    "extension",
}

VERSION_KEYWORDS_HI: Set[str] = {
    "संशोधन",
    "संशोधित",
    "अधिसूचना",
    "शुद्धिपत्र",
    "परिशिष्ट",
    "आदेश",
    "नवीन",
    "परिवर्तन",
}


@dataclass
class DiffAnalysis:
    """Structured text difference and version indicator analysis."""

    has_meaningful_diff: bool
    added_lines_count: int
    removed_lines_count: int
    diff_summary: str
    version_keywords_found: List[str] = field(default_factory=list)
    date_transition_detected: bool = False
    is_probable_version: bool = False


def detect_version_keywords(text: str) -> List[str]:
    """Search for English and Hindi version/amendment keywords in text or titles."""
    found = set()
    text_lower = text.lower()

    for kw in VERSION_KEYWORDS_EN:
        # Match whole words for English
        if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
            found.add(kw)

    for kw in VERSION_KEYWORDS_HI:
        # Substring match for Hindi words
        if kw in text:
            found.add(kw)

    return sorted(found)


def detect_year_transition(title1: str, title2: str) -> bool:
    """Detect if title1 and title2 mention different years (e.g. 2025 vs 2026)."""
    years1 = set(re.findall(r"\b20\d{2}\b", title1))
    years2 = set(re.findall(r"\b20\d{2}\b", title2))
    return bool(years1 and years2 and years1 != years2)


def analyze_document_diff(
    text_old: str,
    text_new: str,
    title_old: str = "",
    title_new: str = "",
    max_summary_lines: int = 8,
) -> DiffAnalysis:
    """
    Perform a unified line diff between two documents and evaluate version indicators.

    :param text_old: Normalized text of reference document.
    :param text_new: Normalized text of candidate document.
    :param title_old: Title/filename of reference document.
    :param title_new: Title/filename of candidate document.
    :param max_summary_lines: Maximum diff lines to include in the human-readable summary.
    :return: DiffAnalysis with structured metrics and summary.
    """
    lines_old = text_old.splitlines()
    lines_new = text_new.splitlines()

    diff_lines = list(difflib.unified_diff(
        lines_old,
        lines_new,
        fromfile="canonical",
        tofile="candidate",
        lineterm="",
    ))

    added_lines = []
    removed_lines = []
    summary_snippets = []

    for line in diff_lines:
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            added_lines.append(line[1:].strip())
            if len(summary_snippets) < max_summary_lines:
                summary_snippets.append(f"+ {line[1:].strip()}")
        elif line.startswith("-"):
            removed_lines.append(line[1:].strip())
            if len(summary_snippets) < max_summary_lines:
                summary_snippets.append(f"- {line[1:].strip()}")

    # Check version keywords in changed content as well as titles
    changed_text = " ".join(added_lines + removed_lines)
    full_context_text = f"{title_new} {title_old} {changed_text}"
    keywords = detect_version_keywords(full_context_text)

    # Check date transitions in titles
    year_transition = detect_year_transition(title_old, title_new)

    has_diff = len(added_lines) > 0 or len(removed_lines) > 0

    # Probable version if there is a meaningful text diff AND (version keywords found OR year transition)
    is_probable_version = has_diff and (len(keywords) > 0 or year_transition)

    diff_summary_str = "\n".join(summary_snippets)
    if not diff_summary_str and has_diff:
        diff_summary_str = f"{len(added_lines)} line(s) added, {len(removed_lines)} line(s) removed."
    elif not has_diff:
        diff_summary_str = "No line differences detected."

    return DiffAnalysis(
        has_meaningful_diff=has_diff,
        added_lines_count=len(added_lines),
        removed_lines_count=len(removed_lines),
        diff_summary=diff_summary_str,
        version_keywords_found=keywords,
        date_transition_detected=year_transition,
        is_probable_version=is_probable_version,
    )
