# Selectolax Migration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace BeautifulSoup with selectolax (Rust-backed HTML parser) across the entire backend, removing the beautifulsoup4 dependency.

**Architecture:** selectolax uses the Modest engine (C/Rust). It provides `HTMLParser` for parsing, `.css()` for selectors, `.text()` for text extraction, and `.attributes` for attrs. Three files need changes: `base.py` (fallback paths), `hans_publishers.py`, and `pubscholar.py`.

**Tech Stack:** Python (selectolax), existing Rust integration stays unchanged.

---

### Task 1: Add selectolax Dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add selectolax to dependencies**

Run:
```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend
uv add selectolax
```

Expected: selectolax added to `[project.dependencies]` in `pyproject.toml`.

**Step 2: Verify installation**

Run:
```bash
uv run python -c "from selectolax.parser import HTMLParser; print('selectolax OK')"
```

Expected: `selectolax OK`

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add selectolax HTML parser"
```

---

### Task 2: Replace BeautifulSoup in base.py

**Files:**
- Modify: `src/core/ingest_and_digitize_data/literature_acquisition/web/base.py:1-79`

**Step 1: Replace import and fallback code**

Replace the BS4 import (line 12) and rewrite the two fallback functions.

Current code at line 12:
```python
from bs4 import BeautifulSoup
```

Replace with:
```python
from selectolax.parser import HTMLParser
```

Current `extract_pdf_links_from_html` fallback (lines 44-57):
```python
    # Fallback: BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if ".pdf" in href.lower():
            links.append(urljoin(base_url, href))
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").lower()
        if name == "citation_pdf_url":
            content = (meta.get("content") or "").strip()
            if content:
                links.append(urljoin(base_url, content))
    return list(dict.fromkeys(links))
```

Replace with:
```python
    # Fallback: selectolax
    tree = HTMLParser(html)
    links = []
    for node in tree.css("a[href]"):
        href = (node.attributes.get("href") or "").strip()
        if ".pdf" in href.lower():
            links.append(urljoin(base_url, href))
    for node in tree.css("meta[name='citation_pdf_url']"):
        content = (node.attributes.get("content") or "").strip()
        if content:
            links.append(urljoin(base_url, content))
    return list(dict.fromkeys(links))
```

Current `scrape_html_elements` fallback (lines 69-79):
```python
    # Fallback: BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    return [
        {
            "text": el.get_text(" ", strip=True),
            "html": str(el),
            "tag_name": el.name,
            "attrs": dict(el.attrs),
        }
        for el in soup.select(css_selector)
    ]
```

Replace with:
```python
    # Fallback: selectolax
    tree = HTMLParser(html)
    return [
        {
            "text": node.text(deep=True, separator=" ").strip(),
            "html": node.html,
            "tag_name": node.tag,
            "attrs": dict(node.attributes) if node.attributes else {},
        }
        for node in tree.css(css_selector)
    ]
```

**Step 2: Update docstrings**

Update the docstring on line 36:
```python
    """Extract PDF links from HTML. Uses Rust parser when available, falls back to selectolax."""
```

Update the docstring on line 61:
```python
    """Parse HTML with CSS selector. Uses Rust when available, falls back to selectolax."""
```

**Step 3: Run existing tests to verify no regressions**

Run: `uv run pytest tests/core/ingest_and_digitize_data/literature_acquisition/test_web_providers.py -v`
Expected: All 22 tests pass.

**Step 4: Commit**

```bash
git add src/core/ingest_and_digitize_data/literature_acquisition/web/base.py
git commit -m "refactor(web): replace BeautifulSoup with selectolax in base.py fallbacks"
```

---

### Task 3: Replace BeautifulSoup in hans_publishers.py

**Files:**
- Modify: `src/core/ingest_and_digitize_data/literature_acquisition/web/hans_publishers.py:11,36`

**Step 1: Replace import**

Line 11, replace:
```python
from bs4 import BeautifulSoup
```
with:
```python
from selectolax.parser import HTMLParser
```

**Step 2: Rewrite `_fallback_extract_items_from_html`**

Replace the function body (lines 34-61):

```python
def _fallback_extract_items_from_html(html_text: str, limit: int) -> List[Dict[str, Any]]:
    """Extract items from HTML by parsing paperinformation links."""
    tree = HTMLParser(html_text or "")
    seen_links: set[str] = set()
    items: List[Dict[str, Any]] = []
    for node in tree.css("a[href]"):
        href = str(node.attributes.get("href") or "").strip()
        if "paperinformation?paperid=" not in href:
            continue
        detail_link = urljoin(BASE_URL, href)
        if detail_link in seen_links:
            continue
        seen_links.add(detail_link)
        title = re.sub(r"\s+", " ", node.text(deep=True, separator=" ")).strip()
        if not title:
            title = f"Hans Paper {len(items) + 1}"
        items.append({
            "title": title,
            "authors": None,
            "year": None,
            "journal": None,
            "subject": None,
            "detail_link": detail_link,
            "index": len(items),
        })
        if len(items) >= max(1, limit):
            break
    return items
```

**Step 3: Run tests**

Run: `uv run pytest tests/core/ingest_and_digitize_data/literature_acquisition/test_web_providers.py -v`
Expected: All 22 tests pass.

**Step 4: Commit**

```bash
git add src/core/ingest_and_digitize_data/literature_acquisition/web/hans_publishers.py
git commit -m "refactor(web): replace BeautifulSoup with selectolax in hans_publishers.py"
```

---

### Task 4: Replace BeautifulSoup in pubscholar.py

**Files:**
- Modify: `src/core/ingest_and_digitize_data/literature_acquisition/web/pubscholar.py:12,65`

**Step 1: Replace import**

Line 12, replace:
```python
from bs4 import BeautifulSoup
```
with:
```python
from selectolax.parser import HTMLParser
```

**Step 2: Rewrite `_duckduckgo_search` parsing**

Replace lines 65-77 (the BS4 parsing block inside `_duckduckgo_search`):

```python
    tree = HTMLParser(resp.text)
    results: List[Dict[str, str]] = []
    seen: set[str] = set()
    for node in tree.css("a.result__a"):
        href = _decode_duckduckgo_link(node.attributes.get("href") or "")
        if not href or href in seen:
            continue
        seen.add(href)
        title = node.text(deep=True, separator=" ").strip() or href
        results.append({"title": title, "url": href})
        if len(results) >= limit:
            break
    return results
```

**Step 3: Run tests**

Run: `uv run pytest tests/core/ingest_and_digitize_data/literature_acquisition/test_web_providers.py -v`
Expected: All 22 tests pass.

**Step 4: Commit**

```bash
git add src/core/ingest_and_digitize_data/literature_acquisition/web/pubscholar.py
git commit -m "refactor(web): replace BeautifulSoup with selectolax in pubscholar.py"
```

---

### Task 5: Remove beautifulsoup4 Dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Remove beautifulsoup4**

Run:
```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend
uv remove beautifulsoup4
```

If `beautifulsoup4` is not listed directly (transitive dep), remove `bs4` import references. Verify no remaining BS4 imports:

Run:
```bash
grep -rn "from bs4\|import bs4\|BeautifulSoup" src/ tests/
```

Expected: No output (all references removed).

**Step 2: Run full test suite**

Run: `uv run pytest tests/core/ingest_and_digitize_data/literature_acquisition/ -v`
Expected: All tests pass.

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): remove beautifulsoup4, replaced by selectolax"
```

---

### Task 6: End-to-End Verification

**Step 1: Verify import chain**

Run:
```bash
uv run python -c "
from src.core.ingest_and_digitize_data.literature_acquisition.web.base import extract_pdf_links_from_html, scrape_html_elements
from src.core.ingest_and_digitize_data.literature_acquisition.web.hans_publishers import hanspub_search
from src.core.ingest_and_digitize_data.literature_acquisition.web.pubscholar import pubscholar_search
print('All imports OK')
"
```

Expected: `All imports OK`

**Step 2: Verify selectolax fallback works when Rust unavailable**

Run:
```bash
uv run python -c "
import sys
# Temporarily block rust_io
sys.modules['rust_io'] = None
sys.modules['rust_io.literature'] = None

from src.core.ingest_and_digitize_data.literature_acquisition.web.base import extract_pdf_links_from_html, scrape_html_elements

# Test extract_pdf_links fallback
html = '<a href=\"paper.pdf\">Download</a><a href=\"other.html\">Link</a>'
links = extract_pdf_links_from_html(html, 'https://example.com')
assert len(links) == 1, f'Expected 1 link, got {len(links)}'
assert 'paper.pdf' in links[0]

# Test scrape_html_elements fallback
result = scrape_html_elements('<div class=\"item\">Hello</div><div class=\"item\">World</div>', 'div.item')
assert len(result) == 2, f'Expected 2 items, got {len(result)}'
assert result[0]['text'] == 'Hello'

print('selectolax fallback OK')
"
```

Expected: `selectolax fallback OK`

**Step 3: Run full test suite**

Run: `uv run pytest tests/core/ingest_and_digitize_data/literature_acquisition/ -v`
Expected: All tests pass.

**Step 4: Final commit (if any remaining changes)**

```bash
git add -A
git commit -m "chore: verify selectolax migration end-to-end"
```
