"""Tests verifying VLM model stays loaded after inference."""
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_client_with_mock_vlm():
    """Create test client with a mock VLM service."""
    with patch("app.domain.vlm.vllm.LLM"), \
         patch("app.domain.vlm.MinerUClient"):
        from app.domain.vlm import VLMService
        from app.api import vlm

        svc = VLMService(model_id="test-model")
        svc._ready = True
        svc._client = MagicMock()
        svc._client.two_step_extract.return_value = (
            "# Test\n\nContent",
            [{"page_number": 1, "markdown": "# Test", "figures": [], "tables": []}],
        )
        vlm.bind(svc)
        app = FastAPI()
        app.include_router(vlm.router)
        return TestClient(app), svc


def _make_test_image_b64() -> str:
    import base64
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="white").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_vlm_model_stays_loaded_after_inference():
    """VLM model should NOT be unloaded after each inference request.

    Unloading forces a full model reload on the next request, adding
    minutes of latency per page for multi-page documents.
    """
    client, svc = _make_client_with_mock_vlm()
    img_b64 = _make_test_image_b64()

    resp = client.post("/v1/chat/completions", json={
        "model": "test-model",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "Extract."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
        ]}],
    })

    assert resp.status_code == 200
    # Model should still be loaded (ready=True, client not None)
    assert svc.ready is True
    assert svc._client is not None
