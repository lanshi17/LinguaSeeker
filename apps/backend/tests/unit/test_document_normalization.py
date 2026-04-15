from src.domain.document_normalization import normalize_document_body


def test_normalize_document_body_strips_html_scaffold_and_keeps_article_text() -> None:
    html = """
    <html>
      <body>
        <header>site nav</header>
        <main>
          <article>
            <h1>Example Title</h1>
            <p>这是正文第一段。</p>
            <p>Body paragraph two.</p>
          </article>
        </main>
        <footer>copyright</footer>
      </body>
    </html>
    """

    normalized = normalize_document_body(html)

    assert normalized.text == "# Example Title\n\n这是正文第一段。\n\nBody paragraph two."
    assert "site nav" not in normalized.text
    assert "copyright" not in normalized.text
    assert normalized.source_type == "html"
    assert normalized.body_selector in {"article", "main", "body"}


def test_normalize_document_body_removes_embedded_html_blocks_from_markdown() -> None:
    markdown = "# Title\n\n正文保留。\n\n<div>debug html</div>\n\n## Results\n\nEnglish body."

    normalized = normalize_document_body(markdown)

    assert normalized.text == "# Title\n\n正文保留。\n\n## Results\n\nEnglish body."
    assert "<div>" not in normalized.text
    assert normalized.source_type == "markdown"
