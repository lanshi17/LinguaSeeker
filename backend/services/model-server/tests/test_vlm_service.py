from unittest.mock import MagicMock, patch

from PIL import Image


def test_vlm_service_init():
    with patch("app.domain.llm.vllm.LLM"), \
         patch("app.domain.llm.MinerUClient"):
        from app.domain.llm import LLMService
        svc = LLMService(
            model_id="opendatalab/MinerU2.5-Pro-2604-1.2B",
            gpu_memory_utilization=0.5,
            image_analysis=False,
        )
        assert svc.model_id == "opendatalab/MinerU2.5-Pro-2604-1.2B"
        assert svc.ready is False


def test_vlm_service_load():
    with patch("app.domain.llm.vllm.LLM") as mock_llm_cls, \
         patch("app.domain.llm.MinerUClient") as mock_client_cls:
        mock_llm_cls.return_value = MagicMock()
        mock_client_cls.return_value = MagicMock()

        from app.domain.llm import LLMService
        svc = LLMService(model_id="opendatalab/MinerU2.5-Pro-2604-1.2B")
        svc.ensure_loaded()

        assert svc.ready is True
        mock_llm_cls.assert_called_once()
        mock_client_cls.assert_called_once()


def test_vlm_service_infer_returns_pages():
    """Verify infer() returns structured page data."""
    mock_client = MagicMock()
    mock_client.two_step_extract.return_value = (
        "# Title\n\nContent",
        [{"page_number": 1, "markdown": "# Title\n\nContent", "figures": [], "tables": []}],
    )

    with patch("app.domain.llm.vllm.LLM") as mock_llm_cls, \
         patch("app.domain.llm.MinerUClient", return_value=mock_client):
        mock_llm_cls.return_value = MagicMock()

        from app.domain.llm import LLMService
        svc = LLMService(model_id="opendatalab/MinerU2.5-Pro-2604-1.2B")
        svc.ensure_loaded()

        img = Image.new("RGB", (100, 100))
        result = svc.infer(image=img)

        mock_client.two_step_extract.assert_called_once()
        assert "full_markdown" in result
        assert "pages" in result
