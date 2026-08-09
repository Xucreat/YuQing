"""Backend boundary sanitizer for content received from foreign publishers."""
from __future__ import annotations

import html
import re
import unicodedata
from urllib.parse import urlparse

from bs4 import BeautifulSoup


ALLOWED_TAGS = {"p", "br", "strong", "em", "ul", "ol", "li", "blockquote", "a"}
DROP_TAGS = {
    "script", "style", "iframe", "object", "embed", "svg", "img", "meta", "link",
    "figure", "figcaption", "picture", "source",
}
NOISE_TAGS = DROP_TAGS | {
    "aside", "footer", "form", "header", "nav", "noscript", "template",
    "menu", "dialog",
}
MAX_NORMALIZED_TEXT = 12_000
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_SPACE_RE = re.compile(r"[\t\r\n\f\v ]+")
_NOISE_CLASS_RE = re.compile(
    r"(?:advert|author|byline|breadcrumb|caption|copyright|credit|footer|header|hero|image|nav|photo|pool|recommend|related|share|social|subscribe|template|toolbar)",
    re.IGNORECASE,
)
_BRAND_TOKENS = {"voa", "nasa", "usa", "uk", "eu", "bbc", "cnn", "ap", "nyt"}
_TEMPLATE_LINE_RE = re.compile(
    r"^\s*(?:photo|pool\s+photo|image|illustration|credit|copyright|courtesy|byline|written\s+by|reported\s+by|©)\b.*$",
    re.IGNORECASE,
)
_PUBLISHER_CREDIT_MARKERS = (
    "the new york times", "getty images", "reuters", "ap photo", "associated press",
)


def _is_template_line(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    if not normalized or _TEMPLATE_LINE_RE.match(normalized):
        return True
    return (
        len(normalized.split()) <= 18
        and any(marker in normalized.casefold() for marker in _PUBLISHER_CREDIT_MARKERS)
    )


def _safe_href(value: object) -> str | None:
    href = str(value or "").strip()
    if not href:
        return None
    parsed = urlparse(href)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        return None
    return href


def sanitize_foreign_html(value: object) -> str:
    """Return a small safe HTML subset, or plain text if parsing fails."""
    raw = html.unescape(str(value or ""))
    if not raw.strip():
        return ""
    try:
        soup = BeautifulSoup(raw, "html.parser")
        for node in list(soup.find_all(NOISE_TAGS)):
            node.decompose()
        for node in list(soup.find_all(True)):
            tag = str(node.name).casefold()
            classes = " ".join(node.get("class", []) or [])
            if _NOISE_CLASS_RE.search(classes):
                node.decompose()
                continue
            if tag not in ALLOWED_TAGS:
                node.unwrap()
                continue
            if tag == "a":
                href = _safe_href(node.get("href"))
                node.attrs = {"href": href} if href else {}
            else:
                node.attrs = {}
        for node in list(soup.find_all(["p", "div", "span", "small", "a"])):
            if _is_template_line(node.get_text(" ", strip=True)):
                node.decompose()
        result = soup.decode_contents(formatter="html").strip()
        if result:
            return result
    except Exception:
        pass
    try:
        return BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    except Exception:
        return " ".join(raw.split())


def sanitize_foreign_text(value: object) -> str:
    """Expose content as text when a caller does not render trusted markup."""
    return normalize_foreign_text(value)


def normalize_foreign_text(value: object, *, max_length: int = MAX_NORMALIZED_TEXT) -> str:
    """Return bounded plain text suitable for language, risk, and similarity logic.

    This is intentionally separate from ``sanitize_foreign_html``: service code
    should never use markup, image URLs, template chrome, or repeated whitespace
    as analytical input.
    """
    limit = max(1, int(max_length))
    raw = html.unescape(str(value or ""))
    if not raw.strip():
        return ""
    try:
        soup = BeautifulSoup(raw, "html.parser")
        for node in list(soup.find_all(NOISE_TAGS)):
            node.decompose()
        for node in list(soup.find_all(True)):
            classes = " ".join(node.get("class", []) or [])
            node_id = str(node.get("id") or "")
            marker = f"{classes} {node_id}"
            if _NOISE_CLASS_RE.search(marker):
                node.decompose()
        text = soup.get_text("\n", strip=True)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(unicodedata.normalize("NFKC", text))
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        normalized_line = " ".join(line.split()).strip()
        if _is_template_line(normalized_line):
            continue
        cleaned_lines.append(normalized_line)
    text = "\n".join(cleaned_lines)
    text = _URL_RE.sub(" ", text)
    text = re.sub(r"\b(?:src|srcset|alt|style|class|onclick|onerror)\s*=\s*[^\s]+", " ", text, flags=re.IGNORECASE)
    text = _SPACE_RE.sub(" ", text).strip()
    # Keep punctuation readable while eliminating separators left by HTML.
    text = re.sub(r"\s+([,.;:!?，。；：！？])", r"\1", text)
    return text[:limit].rstrip()


def normalize_foreign_article(
    title: object,
    summary: object,
    content: object,
    *,
    max_length: int = MAX_NORMALIZED_TEXT,
) -> str:
    """Build one deduplicated analytical document from article fields."""
    limit = max(1, int(max_length))
    parts: list[str] = []
    for value in (title, summary, content):
        cleaned = normalize_foreign_text(value, max_length=limit)
        if not cleaned:
            continue
        folded = re.sub(r"\s+", " ", cleaned).casefold()
        if any(folded == re.sub(r"\s+", " ", existing).casefold() for existing in parts):
            continue
        # Some feeds repeat the title verbatim at the start of the body.
        if parts and folded.startswith(re.sub(r"\s+", " ", parts[0]).casefold() + " "):
            cleaned = cleaned[len(parts[0]):].lstrip(" \t:-|")
        if cleaned:
            parts.append(cleaned)
    return "\n".join(parts)[:limit].rstrip()


def detect_foreign_language(value: object) -> str:
    """Classify normalized foreign text as ``zh``, ``en``, ``mixed`` or ``unknown``."""
    text = normalize_foreign_text(value)
    cjk_count = sum("\u4e00" <= char <= "\u9fff" for char in text)
    latin_count = sum(char.isascii() and char.isalpha() for char in text)
    # Lowercase running prose is a stronger mixed-language signal than names,
    # acronyms, brands, and numeric references (which are common in zh feeds).
    prose_tokens = re.findall(r"\b[A-Za-z]{2,}\b", text)
    latin_signal = sum(
        len(token)
        for token in prose_tokens
        if token.islower() and token.casefold() not in _BRAND_TOKENS
    )
    if cjk_count and latin_signal >= 8:
        return "mixed"
    if cjk_count:
        return "zh"
    if latin_count:
        return "en"
    return "unknown"
