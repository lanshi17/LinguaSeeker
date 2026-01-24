"""HTML annotator for side-by-side MinerU outputs with bbox-driven highlights."""

from __future__ import annotations

from typing import List, Dict, Any
from pathlib import Path
from bs4 import BeautifulSoup  # type: ignore


def _annotate_html_by_bbox(html_text: str, targets: List[Dict[str, Any]]) -> str:
    """Annotate HTML by wrapping matching data-bbox nodes with <mark> tags.

    Args:
        html_text: Input HTML string
        targets: List of dicts with keys: page, bbox ([x0,y0,x1,y1])

    Returns:
        Annotated HTML string
    """
    soup = BeautifulSoup(html_text, "html.parser")

    def bbox_str(b):
        return f"[{','.join(str(int(x)) for x in b)}]"

    target_map = {(t.get("page"), bbox_str(t.get("bbox", []))): True for t in targets if t.get("bbox")}

    # Find elements carrying data-bbox and optionally data-page
    for el in soup.find_all(attrs={"data-bbox": True}):
        bbox = el.get("data-bbox")
        page = int(el.get("data-page")) if el.get("data-page") else None
        key = (page, bbox) if page is not None else (None, bbox)
        if key in target_map:
          # assign a deterministic id by bbox for linking
          if page is not None and bbox:
            el["id"] = f"bbox-{page}-{bbox.replace('[','').replace(']','').replace(',','-')}"
          # wrap inner content with <mark>
          el.string = el.get_text()  # ensure NavigableString
          el.insert(0, soup.new_tag("mark"))
          # move text inside mark
          mark = el.find("mark")
          mark.string = el.get_text()
          # clear original text nodes except mark
          for child in list(el.children):
            if child != mark:
              child.extract()

    return str(soup)


def generate_side_by_side_annotated(
    original_html_path: str,
    translated_html_path: str,
    targets: List[Dict[str, Any]],
  title: str,
  figures: List[Dict[str, Any]] | None = None,
  tables: List[Dict[str, Any]] | None = None,
) -> str:
    """Create a side-by-side HTML page with synchronized highlights.

    Args:
        original_html_path: Path to original-language HTML
        translated_html_path: Path to English translation HTML
        targets: List of bbox targets to highlight
        title: Page title

    Returns:
        Final HTML document string with two columns
    """
    orig_html = Path(original_html_path).read_text(encoding="utf-8")
    en_html = Path(translated_html_path).read_text(encoding="utf-8")

    annotated_orig = _annotate_html_by_bbox(orig_html, targets)
    annotated_en = _annotate_html_by_bbox(en_html, targets)

    # Build sidebar items for figures/tables
    def _item_block(items, heading: str) -> str:
        if not items:
            return ""
        blocks = [f"<h2>{heading}</h2>"]
        for it in items:
            title = it.get("title", "")
            caption = it.get("caption", "")
            img = it.get("image_path")
            bbox = it.get("bbox") or []
            page = it.get("page")
            bbox_str = f"[{','.join(str(int(x)) for x in bbox)]}" if bbox else "[]"
            target_id = f"bbox-{page}-{bbox_str.replace('[','').replace(']','').replace(',','-')}" if bbox else ""
            thumb = f"<img src=\"{img}\" style=\"max-width:100%;border:1px solid #eee;border-radius:4px\"/>" if img else ""
            blocks.append(
                f"<div class=\"item\" onclick=\"scrollToBBox('{target_id}')\" style=\"cursor:pointer;margin-bottom:12px\">"
                f"<div class=\"thumb\">{thumb}</div>"
                f"<div class=\"meta\"><div class=\"title\"><strong>{title}</strong></div><div class=\"cap\">{caption}</div></div>"
                f"</div>"
            )
        return "".join(blocks)

    sidebar_items = _item_block(figures, "Figures") + _item_block(tables, "Tables")

    # Simple container with two columns and sidebar
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; background: #f5f5f5; }}
    .container {{ display: flex; gap: 16px; padding: 16px; }}
    .pane {{ flex: 1; background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 12px; overflow-y: auto; max-height: 90vh; }}
    .sidebar {{ width: 340px; background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 12px; overflow-y: auto; max-height: 90vh; }}
    .pane h1 {{ font-size: 18px; border-bottom: 1px solid #eee; padding-bottom: 8px; }}
    mark {{ background-color: #fff3cd; padding: 2px 4px; border-radius: 3px; }}
  </style>
  <script>
    function scrollToBBox(id) {{
      if (!id) return;
      const leftEl = document.querySelector('.left-pane #' + CSS.escape(id));
      const rightEl = document.querySelector('.right-pane #' + CSS.escape(id));
      if (leftEl) {{ leftEl.scrollIntoView({{behavior:'smooth', block:'center'}}); }}
      if (rightEl) {{ rightEl.scrollIntoView({{behavior:'smooth', block:'center'}}); }}
      [leftEl, rightEl].forEach(el => {{ if (el) {{ el.style.outline='2px solid #ff9800'; setTimeout(()=>{{el.style.outline='';}}, 1500); }} }});
    }}
  </script>
</head>
<body>
  <div class=\"container\">
    <div class=\"pane left-pane\">
      <h1>Original</h1>
      {annotated_orig}
    </div>
    <div class=\"pane right-pane\">
      <h1>English</h1>
      {annotated_en}
    </div>
    <div class=\"sidebar\">
      <h1>Assets</h1>
      {sidebar_items}
    </div>
  </div>
</body>
</html>"""
