"""Convert markdown to HTML while preserving structure."""

from pathlib import Path
from typing import Optional


def markdown_to_html(markdown_text: str, title: str = "Document") -> str:
    """Convert markdown to structured HTML.
    
    Args:
        markdown_text: Markdown formatted text
        title: Document title
        
    Returns:
        HTML string
    """
    try:
        import markdown
        md = markdown.Markdown(extensions=["extra", "toc", "codehilite"])
        html_body = md.convert(markdown_text)
    except ImportError:
        # Fallback: simple conversion without markdown library
        html_body = _simple_markdown_to_html(markdown_text)
    
    # Wrap in proper HTML document
    html = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{title}</title>
<style>
html {{
    color: #1a1a1a;
    background-color: #fdfdfd;
}}
body {{
    margin: 0 auto;
    max-width: 36em;
    padding-left: 50px;
    padding-right: 50px;
    padding-top: 50px;
    padding-bottom: 50px;
    hyphens: auto;
    overflow-wrap: break-word;
    text-rendering: optimizeLegibility;
    font-kerning: normal;
}}
h1, h2, h3, h4, h5, h6 {{
    margin-top: 1.4em;
}}
p {{
    margin: 1em 0;
}}
table {{
    margin: 1em 0;
    border-collapse: collapse;
    width: 100%;
}}
table th, table td {{
    border: 1px solid #dfe2e5;
    padding: 6px 13px;
}}
code {{
    font-family: Menlo, Monaco, Consolas, 'Lucida Console', monospace;
    font-size: 85%;
    background-color: #f5f5f5;
    padding: 0.2em 0.4em;
}}
pre {{
    background-color: #f5f5f5;
    padding: 1em;
    overflow-x: auto;
}}
pre code {{
    background-color: transparent;
    padding: 0;
}}
blockquote {{
    margin: 1em 0 1em 1.7em;
    padding-left: 1em;
    border-left: 2px solid #e6e6e6;
    color: #606060;
}}
a {{
    color: #0066cc;
    text-decoration: none;
}}
a:hover {{
    text-decoration: underline;
}}
</style>
</head>
<body>
{html_body}
</body>
</html>"""
    
    return html


def _simple_markdown_to_html(text: str) -> str:
    """Simple markdown to HTML conversion without external library.
    
    Handles basic markdown:
    - Headers (# ## ###)
    - Paragraphs
    - Bold (*text*)
    - Lists (- items)
    - Code blocks (```...```)
    """
    import re
    
    lines = text.split('\n')
    html_lines = []
    in_code_block = False
    in_list = False
    
    for line in lines:
        # Code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                html_lines.append('</code></pre>')
                in_code_block = False
            else:
                lang = line.strip()[3:]
                html_lines.append(f'<pre><code class="language-{lang}">')
                in_code_block = True
            continue
        
        if in_code_block:
            # Escape HTML in code
            html_lines.append(line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
            continue
        
        # Headers
        if line.startswith('# '):
            html_lines.append(f'<h1>{_escape_html(line[2:])}</h1>')
            continue
        if line.startswith('## '):
            html_lines.append(f'<h2>{_escape_html(line[3:])}</h2>')
            continue
        if line.startswith('### '):
            html_lines.append(f'<h3>{_escape_html(line[4:])}</h3>')
            continue
        if line.startswith('#### '):
            html_lines.append(f'<h4>{_escape_html(line[5:])}</h4>')
            continue
        
        # Lists
        if line.strip().startswith('- '):
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            item_text = _escape_html(line.strip()[2:])
            html_lines.append(f'<li>{item_text}</li>')
            continue
        elif in_list:
            html_lines.append('</ul>')
            in_list = False
        
        # Blockquotes
        if line.startswith('> '):
            html_lines.append(f'<blockquote>{_escape_html(line[2:])}</blockquote>')
            continue
        
        # Paragraphs
        if line.strip():
            para_text = _escape_html(line.strip())
            # Apply inline formatting
            para_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', para_text)
            para_text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', para_text)
            para_text = re.sub(r'`(.+?)`', r'<code>\1</code>', para_text)
            html_lines.append(f'<p>{para_text}</p>')
        else:
            # Empty line
            html_lines.append('')
    
    # Close remaining tags
    if in_list:
        html_lines.append('</ul>')
    if in_code_block:
        html_lines.append('</code></pre>')
    
    return '\n'.join(html_lines)


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#39;'))
