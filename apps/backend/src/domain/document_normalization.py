from __future__ import annotations

from dataclasses import dataclass
import re

from bs4 import BeautifulSoup


_REMOVED_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "form"}
_BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre"}
_HTML_BLOCK_RE = re.compile(r"<([a-z][a-z0-9]*)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class NormalizedDocument:
    text: str
    source_type: str
    body_selector: str | None = None



def normalize_document_body(content: str) -> NormalizedDocument:
    raw = str(content or "").strip()
    if not raw:
        return NormalizedDocument(text="", source_type="markdown", body_selector=None)
    if _looks_like_html(raw):
        return _normalize_html(raw)
    return _normalize_markdown(raw)



def _looks_like_html(text: str) -> bool:
    sample = text[:2000].lower().lstrip()
    if sample.startswith("<"):
        return bool(re.search(r"<\s*(html|body|article|main|div|p|section)\b", sample))
    return False



def _normalize_html(html: str) -> NormalizedDocument:
    soup = BeautifulSoup(html, "html.parser")
    for tag in list(soup.find_all(list(_REMOVED_TAGS))):
        tag.decompose()

    body = soup.select_one("article") or soup.select_one("main") or soup.body or soup
    if getattr(body, "name", None) == "article":
        selector = "article"
    elif getattr(body, "name", None) == "main":
        selector = "main"
    else:
        selector = "body"

    blocks: list[str] = []
    for node in body.find_all(list(_BLOCK_TAGS)):
        text = node.get_text(" ", strip=True)
        if not text:
            continue
        if node.name and node.name.startswith("h"):
            level = int(node.name[1]) if node.name[1:].isdigit() else 1
            blocks.append(f"{'#' * max(1, min(level, 6))} {text}")
        elif node.name == "li":
            blocks.append(f"- {text}")
        else:
            blocks.append(text)

    normalized = "\n\n".join(blocks).strip()
    return NormalizedDocument(text=normalized, source_type="html", body_selector=selector)



def _normalize_markdown(markdown: str) -> NormalizedDocument:
    cleaned = _HTML_BLOCK_RE.sub("", markdown)
    cleaned = _HTML_TAG_RE.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return NormalizedDocument(text=cleaned, source_type="markdown", body_selector=None)
