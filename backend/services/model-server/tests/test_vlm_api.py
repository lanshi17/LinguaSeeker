import base64
import io
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image


def _make_test_client():
    """Create a test client with VLM route wired up."""
    with patch("app.domain.llm.vllm.LLM"), \
         patch("app.domain.llm.MinerUClient"):
        from app.domain.llm import LLMService
        from app.api import vlm

        svc = LLMService(model_id="test-model")
        svc._ready = True  # Skip actual loading
        svc._client = MagicMock()
        svc._client.two_step_extract.return_value = (
            "# Test\n\nContent",
            [{"page_number": 1, "markdown": "# Test\n\nContent", "figures": [], "tables": []}],
        )
        vlm.bind(svc)

        app = FastAPI()
        app.include_router(vlm.router)
        return TestClient(app), svc


def _make_test_image_b64() -> str:
    """Create a valid minimal PNG as base64."""
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="white").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_vlm_extract_text_only_returns_400():
    """Text-only messages have no image — endpoint should reject."""
    client, _ = _make_test_client()
    resp = client.post("/v1/chat/completions", json={
        "model": "opendatalab/MinerU2.5-Pro-2604-1.2B",
        "messages": [{"role": "user", "content": "Extract this document."}],
    })
    assert resp.status_code == 400


def test_vlm_extract_with_image():
    client, svc = _make_test_client()
    img_b64 = _make_test_image_b64()
    resp = client.post("/v1/chat/completions", json={
        "model": "opendatalab/MinerU2.5-Pro-2604-1.2B",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "Extract."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
        ]}],
    })
    assert resp.status_code == 200
    svc._client.two_step_extract.assert_called_once()


def test_vlm_not_available():
    """Test 503 when VLM service not configured."""
    from app.api import vlm as vlm_mod
    vlm_mod._service = None

    app = FastAPI()
    app.include_router(vlm_mod.router)
    client = TestClient(app)

    resp = client.post("/v1/chat/completions", json={
        "model": "test",
        "messages": [{"role": "user", "content": "test"}],
    })
    assert resp.status_code == 503
