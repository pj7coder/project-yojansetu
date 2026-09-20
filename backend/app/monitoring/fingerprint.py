import hashlib
from html.parser import HTMLParser
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit
import xml.etree.ElementTree as ET


class LinkExtractorParser(HTMLParser):
    """Safe streaming HTMLParser to extract href links from anchor tags."""

    def __init__(self):
        super().__init__()
        self.links: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        if tag.lower() == "a":
            for attr, val in attrs:
                if attr.lower() == "href" and val:
                    val_clean = val.strip()
                    if val_clean and not val_clean.startswith(("javascript:", "mailto:", "tel:")):
                        self.links.append(val_clean)


def normalize_html_body(html_text: str) -> str:
    """Basic deterministic HTML normalization.
    
    Removes:
    - Transport noise (CRLF to LF)
    - HTML comments (<!-- ... -->)
    - Redundant consecutive whitespace while preserving semantic tags/attributes
    """
    if not html_text:
        return ""

    # Normalize line endings
    text = html_text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Normalize whitespace per line and strip empty lines
    lines = []
    for line in text.split("\n"):
        line_clean = re.sub(r"[ \t]+", " ", line).strip()
        if line_clean:
            lines.append(line_clean)

    return "\n".join(lines)


def compute_body_fingerprint(html_text: str) -> str:
    """Compute SHA-256 hash of normalized HTML body."""
    normalized = normalize_html_body(html_text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_link_url(raw_href: str, base_url: str) -> Optional[str]:
    """Normalize link URL:
    - Converts relative URL to absolute URL against base_url
    - Strips fragment (#...)
    - Preserves query parameters
    - Normalizes scheme and host to lowercase
    - Deduplicates consecutive slashes in path
    """
    if not raw_href:
        return None

    # Resolve relative URL
    abs_url = urljoin(base_url, raw_href)

    # Strip URL fragments
    defragged, _ = urldefrag(abs_url)

    try:
        parts = urlsplit(defragged)
        scheme = parts.scheme.lower()
        if scheme not in ("http", "https"):
            return None

        netloc = parts.netloc.lower()

        # Canonicalize path duplicate slashes
        path = re.sub(r"/{2,}", "/", parts.path)
        if not path:
            path = "/"

        # Rebuild without fragment, preserving query
        normalized = urlunsplit((scheme, netloc, path, parts.query, ""))
        return normalized
    except Exception:
        return None


def extract_and_normalize_links(html_text: str, base_url: str) -> List[str]:
    """Extract all href links from HTML, normalize them against base_url, deduplicate and sort."""
    if not html_text:
        return []

    parser = LinkExtractorParser()
    try:
        parser.feed(html_text)
    except Exception:
        pass

    normalized_set: Set[str] = set()
    for raw_href in parser.links:
        norm = normalize_link_url(raw_href, base_url)
        if norm:
            normalized_set.add(norm)

    return sorted(list(normalized_set))


def compute_link_fingerprint(links: List[str]) -> str:
    """Compute deterministic SHA-256 over sorted unique normalized links."""
    content = "\n".join(links)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_sitemap_fingerprint(xml_text: str) -> Tuple[str, int]:
    """Parse sitemap XML and compute SHA-256 over sorted (loc, lastmod) entries.
    
    Returns:
        (fingerprint_hash, url_count)
    """
    if not xml_text:
        return hashlib.sha256(b"").hexdigest(), 0

    entries: List[str] = []
    try:
        root = ET.fromstring(xml_text)
        # Handle default namespace if present
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        for url_elem in root.findall(f"{ns}url"):
            loc = url_elem.findtext(f"{ns}loc") or ""
            lastmod = url_elem.findtext(f"{ns}lastmod") or ""
            entries.append(f"{loc.strip()}|{lastmod.strip()}")

        # Also support sitemapindex
        for sm_elem in root.findall(f"{ns}sitemap"):
            loc = sm_elem.findtext(f"{ns}loc") or ""
            lastmod = sm_elem.findtext(f"{ns}lastmod") or ""
            entries.append(f"{loc.strip()}|{lastmod.strip()}")
    except Exception:
        # Fallback: regex search if XML is malformed
        locs = re.findall(r"<loc>(.*?)</loc>", xml_text, re.IGNORECASE)
        for loc in locs:
            entries.append(loc.strip())

    entries = sorted(list(set(entries)))
    joined = "\n".join(entries)
    fp = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return fp, len(entries)


def compute_feed_fingerprint(xml_text: str) -> Tuple[str, int]:
    """Parse RSS or Atom XML feed and compute SHA-256 over sorted entries."""
    if not xml_text:
        return hashlib.sha256(b"").hexdigest(), 0

    entries: List[str] = []
    try:
        root = ET.fromstring(xml_text)
        # RSS items
        for item in root.findall(".//item"):
            guid = item.findtext("guid") or item.findtext("link") or item.findtext("title") or ""
            pub_date = item.findtext("pubDate") or ""
            entries.append(f"{guid.strip()}|{pub_date.strip()}")

        # Atom entries
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"
        for entry in root.findall(f".//{ns}entry"):
            eid = entry.findtext(f"{ns}id") or entry.findtext(f"{ns}title") or ""
            updated = entry.findtext(f"{ns}updated") or ""
            entries.append(f"{eid.strip()}|{updated.strip()}")
    except Exception:
        pass

    entries = sorted(list(set(entries)))
    joined = "\n".join(entries)
    fp = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return fp, len(entries)


def compute_stream_sha256(chunks_iterable) -> Tuple[str, int]:
    """Compute SHA-256 over streaming byte chunks without loading all into memory.
    
    Returns:
        (sha256_hex, total_bytes)
    """
    hasher = hashlib.sha256()
    total_bytes = 0
    for chunk in chunks_iterable:
        if chunk:
            hasher.update(chunk)
            total_bytes += len(chunk)
    return hasher.hexdigest(), total_bytes
