from types import SimpleNamespace

from src.agents.chinese_fulltext_recovery.agent import run_chinese_fulltext_recovery
from src.agents.chinese_fulltext_recovery.tools import (
    extract_readable_body,
    validate_normalized_body,
)


def test_extract_readable_body_prefers_article_text_from_chinese_html() -> None:
    html = """
    <html><body>
      <nav>导航</nav>
      <article>
        <h1>DNAJB2复合杂合突变相关腓骨肌萎缩症2型家系病例1例</h1>
        <p>摘要：这里是摘要。</p>
        <p>正文第一段。</p>
        <p>正文第二段。</p>
      </article>
    </body></html>
    """

    result = extract_readable_body(html)

    assert result["success"] is True
    assert "DNAJB2复合杂合突变相关腓骨肌萎缩症2型家系病例1例" in result["body"]
    assert "正文第一段" in result["body"]
    assert result["body_selector"] == "article"


def test_validate_body_rejects_navigation_shell() -> None:
    assert validate_normalized_body("登录 注册 搜索 首页") is False


def test_recovery_agent_skips_llm_when_body_is_already_good(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.agents.chinese_fulltext_recovery.tools.fetch_detail_html",
        lambda url: {"success": True, "html": "<article><p>足够长的正文 ...</p></article>"},
    )
    monkeypatch.setattr(
        "src.agents.chinese_fulltext_recovery.tools.extract_readable_body",
        lambda html: {
            "success": True,
            "body": "足够长的正文" * 100,
            "body_selector": "article",
            "warnings": [],
        },
    )

    result = run_chinese_fulltext_recovery("https://example.cn/paper")

    assert result["success"] is True
    assert result["provider"] == "chinese_fulltext_recovery"
    assert result["normalized_markdown"]
    assert "fallback:html_body" in result["warnings"]


def test_recovery_agent_uses_hans_canonical_detail_page_when_image_url_redirects_homepage(
    monkeypatch,
) -> None:
    def fake_fetch(url: str) -> dict[str, str | bool | list[str]]:
        if url == "https://image.hanspub.org/Html/77-1577845_75032.htm":
            return {
                "success": True,
                "html": "<html><body>汉斯期刊 开放获取</body></html>",
                "final_url": "https://www.hanspub.org/",
                "warnings": [],
            }
        if url == "https://www.hanspub.org/journal/paperinformation?paperid=75032":
            return {
                "success": True,
                "html": """
                <html><body>
                  <div class='articles_main'>
                    <h1>一例ANK1基因突变型遗传性球形红细胞增多症病例报告并文献复习</h1>
                    <div id='ctl00_ContentPlaceHolder1_div_abs_zw'>
                      摘要: 目的：总结分析遗传性球形红细胞增多症的临床特点。ANK1基因c.3604delG导致p.D1202Tfs*28。术后恢复顺利。
                    </div>
                  </div>
                </body></html>
                """,
                "final_url": "https://www.hanspub.org/journal/paperinformation?paperid=75032",
                "warnings": [],
            }
        raise AssertionError(url)

    monkeypatch.setattr(
        "src.agents.chinese_fulltext_recovery.tools.fetch_detail_html",
        fake_fetch,
    )

    result = run_chinese_fulltext_recovery(
        "https://image.hanspub.org/Html/77-1577845_75032.htm"
    )

    assert result["success"] is True
    assert "ANK1" in result["normalized_markdown"]
    assert "遗传性球形红细胞增多症" in result["normalized_markdown"]
    assert "fallback:html_body" in result["warnings"]



def test_recovery_agent_uses_llm_when_extracted_body_is_poor(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.agents.chinese_fulltext_recovery.tools.fetch_detail_html",
        lambda url: {"success": True, "html": "<article><p>短正文</p></article>"},
    )
    monkeypatch.setattr(
        "src.agents.chinese_fulltext_recovery.tools.extract_readable_body",
        lambda html: {
            "success": True,
            "body": "短正文",
            "body_selector": "article",
            "warnings": [],
        },
    )
    calls: list[str] = []

    def fake_normalize(body: str) -> str:
        calls.append(body)
        return "# 标题\n\n整理后的正文"

    monkeypatch.setattr(
        "src.agents.chinese_fulltext_recovery.tools.normalize_body_with_format_llm",
        fake_normalize,
    )

    result = run_chinese_fulltext_recovery("https://example.cn/paper")



import pytest


@pytest.mark.asyncio
async def test_recovery_agent_handles_hans_detail_page_inside_running_event_loop(
    monkeypatch,
) -> None:
    image_url = "https://image.hanspub.org/Html/77-1577845_75032.htm"
    canonical_url = "https://www.hanspub.org/journal/paperinformation?paperid=75032"

    class FakeResponse:
        def __init__(self, text: str, final_url: str) -> None:
            self.text = text
            self.url = final_url

        def raise_for_status(self) -> None:
            return None

    def fake_httpx_get(url: str, **_: object) -> FakeResponse:
        if url == image_url:
            return FakeResponse("<html><body>汉斯期刊 开放获取</body></html>", "https://www.hanspub.org/")
        if url == canonical_url:
            return FakeResponse("<html><body><script>gate</script></body></html>", canonical_url)
        raise AssertionError(url)

    class FakeCrawler:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        async def __aenter__(self) -> "FakeCrawler":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def arun(self, *, url: str, config) -> SimpleNamespace:
            del config
            assert url == canonical_url
            return SimpleNamespace(
                success=True,
                cleaned_html="""
                <html><body>
                  <div id='ctl00_ContentPlaceHolder1_div_abs_zw'>
                    摘要: 目的：总结分析遗传性球形红细胞增多症的临床特点。ANK1基因c.3604delG导致p.D1202Tfs*28。术后恢复顺利。
                  </div>
                </body></html>
                """,
            )

    monkeypatch.setattr(
        "src.agents.chinese_fulltext_recovery.tools.httpx.get",
        fake_httpx_get,
    )
    monkeypatch.setattr(
        "src.agents.chinese_fulltext_recovery.tools.AsyncWebCrawler",
        FakeCrawler,
    )

    result = run_chinese_fulltext_recovery(image_url)

    assert result["success"] is True
    assert "ANK1" in result["normalized_markdown"]
