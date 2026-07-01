"""HTML parsers for document content extraction."""

from __future__ import annotations

from html.parser import HTMLParser


class TableParser(HTMLParser):
    """HTML table parser that extracts rows and detects <th> header rows."""

    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self.has_th: bool = False
        self._current_row: list[str] = []
        self._current_cell = ""
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag in ("td", "th"):
            self._in_cell = True
            self._current_cell = ""
            if tag == "th":
                self.has_th = True
        elif tag == "tr":
            self._current_row = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._in_cell = False
            self._current_row.append(self._current_cell.strip())
        elif tag == "tr" and self._current_row:
            self.rows.append(self._current_row)

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell += data
