from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
import re
from typing import Any, Dict, List, Optional, Tuple
import unicodedata
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit


@dataclass
class CleanedLink:
    text: str
    url: str
    normalized_url: str
    block_index: int = 0


@dataclass
class CleanedPage:
    title: str = ""
    headings: List[Dict[str, Any]] = field(default_factory=list)
    text_blocks: List[Dict[str, Any]] = field(default_factory=list)
    links: List[CleanedLink] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    cleaned_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "headings": self.headings,
            "text_blocks": self.text_blocks,
            "links": [asdict(l) for l in self.links],
            "tables": self.tables,
            "cleaned_text": self.cleaned_text,
        }


class StructuredHtmlParser(HTMLParser):
    """Streaming HTML parser producing clean structured blocks, headings, links, and text."""

    def __init__(self, base_url: str = ""):
        super().__init__()
        self.base_url = base_url
        self.title: str = ""
        self.headings: List[Dict[str, Any]] = []
        self.text_blocks: List[Dict[str, Any]] = []
        self.links: List[Dict[str, Any]] = []
        self.tables: List[Dict[str, Any]] = []

        self._current_tag: Optional[str] = None
        self._current_text: List[str] = []
        self._current_link_href: Optional[str] = None
        self._current_link_text: List[str] = []
        self._in_title: bool = False
        self._in_heading: Optional[int] = None
        self._ignore_stack: int = 0
        self._block_counter: int = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        t = tag.lower()

        # Tags to completely skip
        if t in ("script", "style", "noscript", "svg", "iframe"):
            self._ignore_stack += 1
            return

        if self._ignore_stack > 0:
            return

        if t == "title":
            self._in_title = True
            self._current_text = []

        elif t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush_text_block()
            self._in_heading = int(t[1])
            self._current_text = []

        elif t in ("p", "div", "li", "td", "th", "article", "section"):
            self._flush_text_block()
            self._current_tag = t

        elif t == "a":
            href_val = None
            for k, v in attrs:
                if k.lower() == "href" and v:
                    href_val = v.strip()
                    break
            if href_val and not href_val.startswith(("javascript:", "mailto:", "tel:")):
                self._current_link_href = href_val
                self._current_link_text = []

    def handle_endtag(self, tag: str):
        t = tag.lower()

        if t in ("script", "style", "noscript", "svg", "iframe"):
            self._ignore_stack = max(0, self._ignore_stack - 1)
            return

        if self._ignore_stack > 0:
            return

        if t == "title":
            self.title = "".join(self._current_text).strip()
            self._in_title = False
            self._current_text = []

        elif t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            head_text = "".join(self._current_text).strip()
            if head_text and self._in_heading is not None:
                self.headings.append({
                    "level": self._in_heading,
                    "text": head_text,
                    "index": self._block_counter,
                })
                self.text_blocks.append({
                    "index": self._block_counter,
                    "tag": f"h{self._in_heading}",
                    "text": head_text,
                })
                self._block_counter += 1
            self._in_heading = None
            self._current_text = []

        elif t == "a":
            if self._current_link_href:
                anchor = "".join(self._current_link_text).strip()
                norm_url = self._normalize_url(self._current_link_href)
                if norm_url:
                    self.links.append({
                        "text": anchor,
                        "raw_url": self._current_link_href,
                        "normalized_url": norm_url,
                        "block_index": self._block_counter,
                    })
            self._current_link_href = None
            self._current_link_text = []

        elif t in ("p", "li", "td", "th", "article", "section"):
            self._flush_text_block()

    def handle_data(self, data: str):
        if self._ignore_stack > 0:
            return

        text = data.strip()
        if not text:
            return

        if self._in_title:
            self._current_text.append(data)
        elif self._in_heading:
            self._current_text.append(data)
        else:
            self._current_text.append(data)
            if self._current_link_href is not None:
                self._current_link_text.append(data)

    def _flush_text_block(self):
        if self._current_text:
            raw_joined = " ".join(self._current_text)
            clean_text = re.sub(r"\s+", " ", raw_joined).strip()
            if clean_text:
                self.text_blocks.append({
                    "index": self._block_counter,
                    "tag": self._current_tag or "p",
                    "text": clean_text,
                })
                self._block_counter += 1
            self._current_text = []

    def _normalize_url(self, href: str) -> Optional[str]:
        if not href:
            return None
        abs_url = urljoin(self.base_url, href) if self.base_url else href
        defragged, _ = urldefrag(abs_url)
        try:
            parts = urlsplit(defragged)
            scheme = parts.scheme.lower()
            if scheme not in ("http", "https"):
                return None
            netloc = parts.netloc.lower()
            path = re.sub(r"/{2,}", "/", parts.path) or "/"
            return urlunsplit((scheme, netloc, path, parts.query, ""))
        except Exception:
            return None


class HtmlContentCleaner:
    """Parses, cleans, and structures raw HTML into a deterministic model and linear text."""

    def clean(self, raw_html: str, source_url: str = "") -> CleanedPage:
        """Clean raw HTML and return CleanedPage object."""
        structured_data, linear_text = self.clean_html(raw_html, base_url=source_url)
        cleaned_links = [
            CleanedLink(
                text=l.get("text", ""),
                url=l.get("raw_url", l.get("normalized_url", "")),
                normalized_url=l.get("normalized_url", ""),
                block_index=l.get("block_index", 0),
            )
            for l in structured_data.get("links", [])
        ]
        return CleanedPage(
            title=structured_data.get("title", ""),
            headings=structured_data.get("headings", []),
            text_blocks=structured_data.get("text_blocks", []),
            links=cleaned_links,
            tables=structured_data.get("tables", []),
            cleaned_text=linear_text,
        )

    def clean_html(self, raw_html: str, base_url: str = "") -> Tuple[Dict[str, Any], str]:
        """Clean raw HTML.
        
        Returns:
            (structured_page_dict, normalized_linear_text)
        """
        if not raw_html:
            return {"title": "", "headings": [], "text_blocks": [], "links": [], "tables": []}, ""

        # Remove comments and normalize Unicode
        text = unicodedata.normalize("NFKC", raw_html)
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

        parser = StructuredHtmlParser(base_url=base_url)
        try:
            parser.feed(text)
            parser._flush_text_block()
        except Exception:
            pass

        structured_data = {
            "title": parser.title,
            "headings": parser.headings,
            "text_blocks": parser.text_blocks,
            "links": parser.links,
            "tables": parser.tables,
        }

        # Build clean linear text
        lines: List[str] = []
        if parser.title:
            lines.append(f"# {parser.title}")

        for block in parser.text_blocks:
            tag = block.get("tag", "p")
            b_text = block.get("text", "").strip()
            if not b_text:
                continue
            if tag.startswith("h"):
                level = tag[1:] if len(tag) > 1 and tag[1:].isdigit() else "2"
                lines.append(f"{'#' * int(level)} {b_text}")
            elif tag == "li":
                lines.append(f"- {b_text}")
            else:
                lines.append(b_text)

        linear_text = "\n\n".join(lines)
        return structured_data, linear_text
