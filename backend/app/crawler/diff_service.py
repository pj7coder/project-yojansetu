from dataclasses import asdict, dataclass, field
import difflib
from typing import Any, Dict, List, Optional, Tuple, Union

from app.crawler.html_cleaner import CleanedPage
from app.crawler.relevance_terms import (
    POSITIVE_ENGLISH_TERMS,
    POSITIVE_HINDI_TERMS,
    contains_numeric_change_indicators,
)


@dataclass
class DiffChange:
    change_type: str  # LINK_ADDED, LINK_REMOVED, LINK_CHANGED, TEXT_ADDED, TEXT_REMOVED, TEXT_CHANGED, HEADING_CHANGED
    old_value: Any = None
    new_value: Any = None
    old_text: Optional[str] = None
    new_text: Optional[str] = None
    is_numeric: bool = False
    is_scheme_keyword: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_type": self.change_type,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "old_text": self.old_text,
            "new_text": self.new_text,
            "is_numeric": self.is_numeric,
            "is_scheme_keyword": self.is_scheme_keyword,
        }


@dataclass
class WebpageDiffResult:
    changes: List[DiffChange] = field(default_factory=list)
    text_changes_count: int = 0
    links_added_count: int = 0
    links_removed_count: int = 0
    links_changed_count: int = 0
    numeric_changes_count: int = 0
    has_high_priority_change: bool = False
    is_baseline_missing: bool = False
    has_changes: bool = False

    def summary(self) -> Dict[str, Any]:
        return {
            "text_changes": self.text_changes_count,
            "links_added": self.links_added_count,
            "links_removed": self.links_removed_count,
            "links_changed": self.links_changed_count,
            "numeric_changes": self.numeric_changes_count,
            "high_priority_change": self.has_high_priority_change,
            "is_baseline_diff": self.is_baseline_missing,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary(),
            "changes": [c.to_dict() for c in self.changes],
        }

    def __iter__(self):
        # Support tuple unpacking: changes_list, summary_dict
        yield [c.to_dict() for c in self.changes]
        yield self.summary()


class WebpageDiffService:
    """Calculates structured, block-aware diffs between previous and current cleaned webpage states."""

    def compute_diff(
        self,
        previous: Optional[Union[CleanedPage, Dict[str, Any]]],
        current: Union[CleanedPage, Dict[str, Any]],
    ) -> WebpageDiffResult:
        """Compute structured diff between previous and current representations."""
        # Normalize to dict
        prev_dict = previous.to_dict() if isinstance(previous, CleanedPage) else previous
        curr_dict = current.to_dict() if isinstance(current, CleanedPage) else current

        diff_changes: List[DiffChange] = []

        if not prev_dict:
            # Baseline or previous missing: all links in current are treated as baseline
            cur_links = curr_dict.get("links", [])
            for link in cur_links:
                is_num = contains_numeric_change_indicators(link.get("text", ""))
                is_kw = self._has_scheme_keywords(link.get("text", ""))
                diff_changes.append(
                    DiffChange(
                        change_type="LINK_ADDED",
                        old_value=None,
                        new_value=link,
                        is_numeric=is_num,
                        is_scheme_keyword=is_kw,
                    )
                )

            return WebpageDiffResult(
                changes=diff_changes,
                text_changes_count=0,
                links_added_count=len(cur_links),
                links_removed_count=0,
                links_changed_count=0,
                numeric_changes_count=0,
                has_high_priority_change=len(cur_links) > 0,
                is_baseline_missing=True,
                has_changes=len(cur_links) > 0,
            )

        # 1. Compare Links
        prev_links = prev_dict.get("links", [])
        curr_links = curr_dict.get("links", [])

        prev_url_map = {l["normalized_url"]: l for l in prev_links if "normalized_url" in l}
        curr_url_map = {l["normalized_url"]: l for l in curr_links if "normalized_url" in l}

        links_added = 0
        links_removed = 0
        links_changed = 0

        for url, curr_link in curr_url_map.items():
            if url not in prev_url_map:
                has_num = contains_numeric_change_indicators(curr_link.get("text", ""))
                has_kw = self._has_scheme_keywords(curr_link.get("text", ""))
                diff_changes.append(
                    DiffChange(
                        change_type="LINK_ADDED",
                        old_value=None,
                        new_value=curr_link,
                        is_numeric=has_num,
                        is_scheme_keyword=has_kw,
                    )
                )
                links_added += 1
            else:
                prev_link = prev_url_map[url]
                if prev_link.get("text") != curr_link.get("text"):
                    has_num = contains_numeric_change_indicators(curr_link.get("text", ""))
                    has_kw = self._has_scheme_keywords(curr_link.get("text", ""))
                    diff_changes.append(
                        DiffChange(
                            change_type="LINK_CHANGED",
                            old_value=prev_link,
                            new_value=curr_link,
                            is_numeric=has_num,
                            is_scheme_keyword=has_kw,
                        )
                    )
                    links_changed += 1

        for url, prev_link in prev_url_map.items():
            if url not in curr_url_map:
                diff_changes.append(
                    DiffChange(
                        change_type="LINK_REMOVED",
                        old_value=prev_link,
                        new_value=None,
                        is_numeric=False,
                        is_scheme_keyword=False,
                    )
                )
                links_removed += 1

        # 2. Compare Text Blocks
        prev_blocks = [b.get("text", "") for b in prev_dict.get("text_blocks", [])]
        curr_blocks = [b.get("text", "") for b in curr_dict.get("text_blocks", [])]

        matcher = difflib.SequenceMatcher(None, prev_blocks, curr_blocks)
        text_changes = 0
        numeric_changes = 0
        has_high_priority = False

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "replace":
                for old_txt, new_txt in zip(prev_blocks[i1:i2], curr_blocks[j1:j2]):
                    is_num = (
                        contains_numeric_change_indicators(old_txt)
                        or contains_numeric_change_indicators(new_txt)
                    )
                    is_kw = self._has_scheme_keywords(new_txt)
                    if is_num:
                        numeric_changes += 1
                    if is_num or is_kw:
                        has_high_priority = True

                    diff_changes.append(
                        DiffChange(
                            change_type="TEXT_CHANGED",
                            old_text=old_txt,
                            new_text=new_txt,
                            is_numeric=is_num,
                            is_scheme_keyword=is_kw,
                        )
                    )
                    text_changes += 1

            elif tag == "insert":
                for new_txt in curr_blocks[j1:j2]:
                    is_num = contains_numeric_change_indicators(new_txt)
                    is_kw = self._has_scheme_keywords(new_txt)
                    if is_num:
                        numeric_changes += 1
                    if is_num or is_kw:
                        has_high_priority = True

                    diff_changes.append(
                        DiffChange(
                            change_type="TEXT_ADDED",
                            old_text=None,
                            new_text=new_txt,
                            is_numeric=is_num,
                            is_scheme_keyword=is_kw,
                        )
                    )
                    text_changes += 1

            elif tag == "delete":
                for old_txt in prev_blocks[i1:i2]:
                    diff_changes.append(
                        DiffChange(
                            change_type="TEXT_REMOVED",
                            old_text=old_txt,
                            new_text=None,
                            is_numeric=False,
                            is_scheme_keyword=False,
                        )
                    )
                    text_changes += 1

        # High priority check for PDF and scheme keyword links
        for ch in diff_changes:
            if ch.change_type == "LINK_ADDED":
                val = ch.new_value or {}
                norm_u = val.get("normalized_url", "").lower()
                if norm_u.endswith(".pdf") or ch.is_scheme_keyword:
                    has_high_priority = True

        total_changes = text_changes + links_added + links_removed + links_changed
        return WebpageDiffResult(
            changes=diff_changes,
            text_changes_count=text_changes,
            links_added_count=links_added,
            links_removed_count=links_removed,
            links_changed_count=links_changed,
            numeric_changes_count=numeric_changes,
            has_high_priority_change=has_high_priority,
            is_baseline_missing=False,
            has_changes=total_changes > 0,
        )

    def _has_scheme_keywords(self, text: str) -> bool:
        if not text:
            return False
        text_lower = text.lower()
        for kw in POSITIVE_HINDI_TERMS:
            if kw in text:
                return True
        for kw in POSITIVE_ENGLISH_TERMS:
            if kw in text_lower:
                return True
        return False
