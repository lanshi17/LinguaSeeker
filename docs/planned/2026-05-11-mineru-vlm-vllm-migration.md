# MinerU VLM + vllm 全量迁移 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 model-server 的所有推理后端（Embedding / Rerank / LLM）统一迁移到 vllm，并新增 MinerU2.5-Pro-2604-1.2B VLM 服务，提供 OpenAI 兼容的多模态 `/v1/chat/completions` 端点。

**Architecture:** 所有模型服务从 sentence-transformers / 占位符迁移到 vllm.LLM 统一引擎。Embedding 使用 `task="embed"` + `model.embed()`，Rerank 使用 `task="score"` + `model.score()`，MinerU VLM 使用 `MinerUClient(backend="vllm-engine")`。每个服务独立持有 vllm.LLM 实例，通过 `VLLM_GPU_MEMORY_UTILIZATION` 控制显存分配。API 层在 `/v1/chat/completions` 上支持多模态消息（text + base64 image），返回结构化 ParseResult JSON。

**Tech Stack:** Python 3.12+, FastAPI, vllm >= 0.10.1, mineru_vl_utils, Pydantic v2, loguru, uv

---

## Task 1: Update Dependencies

**Files:**
- Modify: `backend/pyproject.toml`

**Step 1: Add vllm and mineru_vl_utils to dependencies**

在 `backend/pyproject.toml` 的 `dependencies` 列表中追加：

```toml
"vllm>=0.10.1",
"mineru_vl_utils",
```

**Step 2: Run uv lock to resolve**

```bash
cd backend && uv lock
```

Expected: Lock file updated, no conflicts.

**Step 3: Install new dependencies**

```bash
cd backend && uv pip install -e ".[dev]"
```

Expected: vllm and mineru_vl_utils installed successfully.

**Step 4: Verify imports work**

```bash
cd backend && uv run python -c "import vllm; print(vllm.__version__)"
cd backend && uv run python -c "from mineru_vl_utils import MinerUClient, MinerULogitsProcessor; print('OK')"
```

Expected: Both print without error.

**Step 5: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "deps: add vllm>=0.10.1 and mineru_vl_utils for unified inference backend"
```

---

## Task 2: Add VLM Config

**Files:**
- Modify: `backend/services/model-server/app/config.py`

**Step 1: Write test for new config fields**

```python
# backend/services/model-server/tests/test_config.py
import os


def test_vlm_config_defaults(monkeypatch):
    monkeypatch.setenv("VLM_MODEL_ID", "opendatalab/MinerU2.5-Pro-2604-1.2B")
    # Clear lru_cache
    from app.config import Settings, get_config
    get_config.cache_clear()

    cfg = Settings()
    assert cfg.vlm_model_id == "opendatalab/MinerU2.5-Pro-2604-1.2B"
    assert cfg.vlm_image_analysis is False
    assert cfg.vllm_gpu_memory_utilization == 0.9


def test_vlm_config_empty_by_default(monkeypatch):
    monkeypatch.delenv("VLM_MODEL_ID", raising=False)
    from app.config import Settings, get_config
    get_config.cache_clear()

    cfg = Settings()
    assert cfg.vlm_model_id == ""
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest services/model-server/tests/test_config.py -v
```

Expected: FAIL — `Settings` has no `vlm_model_id` field.

**Step 3: Add config fields**

在 `backend/services/model-server/app/config.py` 的 `Settings` 类中，`llm_model_id` 字段之后追加：

```python
    # VLM model (MinerU)
    vlm_model_id: str = ""
    vlm_image_analysis: bool = False

    # vllm shared settings
    vllm_gpu_memory_utilization: float = 0.9
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest services/model-server/tests/test_config.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/services/model-server/app/config.py backend/services/model-server/tests/test_config.py
git commit -m "feat(model-server): add VLM and vllm config fields"
```

---

## Task 3: Add VLM API Schemas

**Files:**
- Modify: `backend/services/model-server/app/models/schemas.py`
- Modify: `backend/services/model-server/app/models/__init__.py`

**Step 1: Write test for VLM schemas**

```python
# backend/services/model-server/tests/test_vlm_schemas.py
from app.models import (
    VLMExtractRequest,
    VLMExtractResponse,
    VLMPageContent,
    VLMDocumentMetadata,
)


def test_vlm_extract_request_text_only():
    req = VLMExtractRequest(
        model="opendatalab/MinerU2.5-Pro-2604-1.2B",
        messages=[{"role": "user", "content": "Extract this document."}],
    )
    assert req.model == "opendatalab/MinerU2.5-Pro-2604-1.2B"


def test_vlm_extract_request_with_image():
    req = VLMExtractRequest(
        model="opendatalab/MinerU2.5-Pro-2604-1.2B",
        messages=[
            {"role": "user", "content": [
                {"type": "text", "text": "Extract this document."},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBOR..."}},
            ]},
        ],
    )
    content = req.messages[0]["content"]
    assert isinstance(content, list)
    assert content[1]["type"] == "image_url"


def test_vlm_page_content():
    page = VLMPageContent(
        page_number=1,
        markdown="# Title\n\nContent here.",
        figures=[],
        tables=[],
    )
    assert page.page_number == 1


def test_vlm_extract_response():
    resp = VLMExtractResponse(
        id="vlm-abc123",
        model="opendatalab/MinerU2.5-Pro-2604-1.2B",
        metadata=VLMDocumentMetadata(total_pages=1),
        pages=[VLMPageContent(page_number=1, markdown="test")],
        full_markdown="test",
        choices=[],
    )
    assert resp.object == "vlm.extraction"
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest services/model-server/tests/test_vlm_schemas.py -v
```

Expected: FAIL — cannot import VLMExtractRequest.

**Step 3: Add VLM schemas to schemas.py**

在 `backend/services/model-server/app/models/schemas.py` 末尾追加：

```python
# ── VLM / MinerU Extraction ─────────────────────────────────────────────


class VLMDocumentMetadata(BaseModel):
    """Document-level metadata from VLM extraction."""

    total_pages: int = 1
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    abstract_text: str | None = None


class VLMFigurePosition(BaseModel):
    """Position of a figure within the document."""

    page: int = Field(ge=1)
    index: int = Field(ge=1)
    caption: str | None = None


class VLMTableStructure(BaseModel):
    """Structured table data extracted by VLM."""

    page: int = Field(ge=1)
    index: int = Field(ge=1)
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class VLMPageContent(BaseModel):
    """Content of a single page extracted by VLM."""

    page_number: int = Field(ge=1)
    markdown: str
    figures: list[VLMFigurePosition] = Field(default_factory=list)
    tables: list[VLMTableStructure] = Field(default_factory=list)


class VLMExtractRequest(BaseModel):
    """OpenAI-compatible multimodal chat request for VLM extraction."""

    model: str = ""
    messages: list[dict]  # OpenAI multimodal message format
    max_tokens: int = 4096
    temperature: float = 0.0


class VLMUsage(BaseModel):
    """Token usage for VLM extraction."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class VLMExtractResponse(BaseModel):
    """Structured extraction response from VLM."""

    id: str = ""
    object: str = "vlm.extraction"
    model: str
    metadata: VLMDocumentMetadata = Field(default_factory=VLMDocumentMetadata)
    pages: list[VLMPageContent] = Field(default_factory=list)
    full_markdown: str = ""
    choices: list[dict] = Field(default_factory=list)
    usage: VLMUsage = Field(default_factory=VLMUsage)
```

**Step 4: Update models/__init__.py**

在 `backend/services/model-server/app/models/__init__.py` 中追加 VLM 相关导入和 `__all__` 条目：

```python
from .schemas import (
    # ... existing imports ...
    VLMExtractRequest,
    VLMExtractResponse,
    VLMPageContent,
    VLMDocumentMetadata,
    VLMFigurePosition,
    VLMTableStructure,
    VLMUsage,
)
```

并在 `__all__` 列表中追加对应条目。

**Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest services/model-server/tests/test_vlm_schemas.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/services/model-server/app/models/ backend/services/model-server/tests/test_vlm_schemas.py
git commit -m "feat(model-server): add VLM extraction request/response schemas"
```

---

## Task 4: Add VLM ModelType Enum

**Files:**
- Modify: `backend/services/model-server/app/enums/model_type.py`

**Step 1: Add VLM enum value**

```python
class ModelType(StrEnum):
    EMBEDDING = "embedding"
    RERANK = "rerank"
    LLM = "llm"
    VLM = "vlm"
```

**Step 2: Verify import**

```bash
cd backend && uv run python -c "from app.enums.model_type import ModelType; print(ModelType.VLM)"
```

Expected: `vlm`

**Step 3: Commit**

```bash
git add backend/services/model-server/app/enums/model_type.py
git commit -m "feat(model-server): add VLM to ModelType enum"
```

---

## Task 5: Refactor EmbeddingService to vllm

**Files:**
- Modify: `backend/services/model-server/app/domain/embedding.py`
- Modify: `backend/services/model-server/app/domain/base.py`

**Step 1: Write test for vllm-based embedding**

```python
# backend/services/model-server/tests/test_embedding_vllm.py
from unittest.mock import MagicMock, patch


def test_embedding_service_load_vllm():
    """Verify EmbeddingService._load() creates vllm.LLM with correct params."""
    with patch("app.domain.embedding._require_cuda", return_value="cuda"):
        from app.domain.embedding import EmbeddingService
        svc = EmbeddingService(
            model_id="Qwen/Qwen3-Embedding-0.6B",
            gpu_memory_utilization=0.5,
        )
        assert svc.model_id == "Qwen/Qwen3-Embedding-0.6B"
        assert svc.ready is False


def test_embedding_service_infer():
    """Verify infer() calls vllm embed and returns tensors."""
    import numpy as np

    mock_output = MagicMock()
    mock_output.outputs.embedding = [0.1, 0.2, 0.3]

    with patch("app.domain.embedding._require_cuda", return_value="cuda"):
        with patch("app.domain.embedding.vllm.LLM") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.embed.return_value = [mock_output]
            mock_llm_cls.return_value = mock_llm

            from app.domain.embedding import EmbeddingService
            svc = EmbeddingService(model_id="Qwen/Qwen3-Embedding-0.6B")
            result = svc.infer(["hello world"])

            mock_llm.embed.assert_called_once_with(["hello world"])
            assert result.shape == (1, 3)
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest services/model-server/tests/test_embedding_vllm.py -v
```

Expected: FAIL — EmbeddingService doesn't accept `gpu_memory_utilization` or use vllm.

**Step 3: Remove `_require_cuda` from base.py**

在 `backend/services/model-server/app/domain/base.py` 中：
- 删除 `_require_cuda()` 函数
- 删除 `__init__` 中的 `self._device = _require_cuda()` 行
- 添加 `gpu_memory_utilization` 参数到 `__init__`：

```python
class BaseModelService(ABC):
    def __init__(self, model_id: str, gpu_memory_utilization: float = 0.9) -> None:
        self._model_id = model_id
        self._model = None
        self._ready = False
        self._gpu_memory_utilization = gpu_memory_utilization
```

同时移除 `import torch`（不再需要）。

**Step 4: Rewrite EmbeddingService**

将 `backend/services/model-server/app/domain/embedding.py` 整体重写：

```python
"""Embedding inference service via vllm."""

from __future__ import annotations

import numpy as np
import vllm

from app.domain.base import BaseModelService
from app.utils.logger import get_logger

logger = get_logger()


class EmbeddingService(BaseModelService):
    """Qwen3-Embedding-0.6B via vllm engine."""

    def __init__(
        self,
        model_id: str = "Qwen/Qwen3-Embedding-0.6B",
        gpu_memory_utilization: float = 0.9,
    ) -> None:
        super().__init__(model_id, gpu_memory_utilization)

    def _load(self) -> None:
        logger.info("Loading embedding model via vllm: {id}", id=self._model_id)
        self._model = vllm.LLM(
            model=self._model_id,
            task="embed",
            gpu_memory_utilization=self._gpu_memory_utilization,
            trust_remote_code=True,
        )

    def infer(self, texts: list[str], normalize: bool = True) -> np.ndarray:
        self.ensure_loaded()
        outputs = self._model.embed(texts)
        embeddings = np.array([o.outputs.embedding for o in outputs])
        if normalize:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / norms
        return embeddings
```

**Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest services/model-server/tests/test_embedding_vllm.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/services/model-server/app/domain/base.py backend/services/model-server/app/domain/embedding.py backend/services/model-server/tests/test_embedding_vllm.py
git commit -m "refactor(model-server): migrate EmbeddingService from sentence-transformers to vllm"
```

---

## Task 6: Refactor RerankService to vllm

**Files:**
- Modify: `backend/services/model-server/app/domain/rerank.py`

**Step 1: Write test for vllm-based rerank**

```python
# backend/services/model-server/tests/test_rerank_vllm.py
from unittest.mock import MagicMock, patch


def test_rerank_service_infer():
    """Verify infer() calls vllm score and returns scores."""
    mock_output = MagicMock()
    mock_output.outputs.score = 0.85

    with patch("app.domain.rerank._require_cuda", return_value="cuda"):
        with patch("app.domain.rerank.vllm.LLM") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.score.return_value = [mock_output]
            mock_llm_cls.return_value = mock_llm

            from app.domain.rerank import RerankService
            svc = RerankService(model_id="BAAI/bge-reranker-v2-m3")
            scores = svc.infer("query", ["doc1"])

            mock_llm.score.assert_called_once()
            assert len(scores) == 1
            assert scores[0] == 0.85
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest services/model-server/tests/test_rerank_vllm.py -v
```

Expected: FAIL — RerankService doesn't use vllm.

**Step 3: Rewrite RerankService**

将 `backend/services/model-server/app/domain/rerank.py` 整体重写：

```python
"""Rerank inference service via vllm."""

from __future__ import annotations

import numpy as np
import vllm

from app.domain.base import BaseModelService
from app.utils.logger import get_logger

logger = get_logger()


class RerankService(BaseModelService):
    """BAAI/bge-reranker-v2-m3 via vllm engine."""

    def __init__(
        self,
        model_id: str = "BAAI/bge-reranker-v2-m3",
        gpu_memory_utilization: float = 0.9,
    ) -> None:
        super().__init__(model_id, gpu_memory_utilization)

    def _load(self) -> None:
        logger.info("Loading rerank model via vllm: {id}", id=self._model_id)
        self._model = vllm.LLM(
            model=self._model_id,
            task="score",
            gpu_memory_utilization=self._gpu_memory_utilization,
            trust_remote_code=True,
        )

    def infer(self, query: str, documents: list[str]) -> np.ndarray:
        self.ensure_loaded()
        pairs = [[query, doc] for doc in documents]
        outputs = self._model.score(pairs)
        return np.array([o.outputs.score for o in outputs])
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest services/model-server/tests/test_rerank_vllm.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/services/model-server/app/domain/rerank.py backend/services/model-server/tests/test_rerank_vllm.py
git commit -m "refactor(model-server): migrate RerankService from sentence-transformers to vllm"
```

---

## Task 7: Implement MinerU VLM Service

**Files:**
- Modify: `backend/services/model-server/app/domain/llm.py`

**Step 1: Write test for VLM service**

```python
# backend/services/model-server/tests/test_vlm_service.py
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from PIL import Image


def _make_mock_vlm_service():
    """Helper to create a VLMService with mocked vllm."""
    with patch("app.domain.llm._require_cuda", return_value="cuda"):
        with patch("app.domain.llm.vllm.LLM") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm_cls.return_value = mock_llm

            with patch("app.domain.llm.MinerUClient") as mock_client_cls:
                mock_client = MagicMock()
                mock_client_cls.return_value = mock_client

                from app.domain.llm import LLMService
                svc = LLMService(
                    model_id="opendatalab/MinerU2.5-Pro-2604-1.2B",
                    gpu_memory_utilization=0.5,
                    image_analysis=False,
                )
                return svc, mock_llm, mock_client


def test_vlm_service_init():
    svc, _, _ = _make_mock_vlm_service()
    assert svc.model_id == "opendatalab/MinerU2.5-Pro-2604-1.2B"
    assert svc.ready is False


def test_vlm_service_load():
    svc, mock_llm, mock_client = _make_mock_vlm_service()
    svc.ensure_loaded()

    assert svc.ready is True
    # Verify vllm.LLM created with correct params
    from app.domain.llm import vllm as vllm_mod
    # Verify MinerUClient created
    mock_client.__class__.assert_called_once


def test_vlm_service_infer_returns_pages():
    """Verify infer() returns structured page data."""
    svc, _, mock_client = _make_mock_vlm_service()

    mock_client.two_step_extract.return_value = (
        "# Title\n\nContent",
        [{"page_number": 1, "markdown": "# Title\n\nContent", "figures": [], "tables": []}],
    )

    svc.ensure_loaded()
    img = Image.new("RGB", (100, 100))
    result = svc.infer(image=img)

    mock_client.two_step_extract.assert_called_once()
    assert "full_markdown" in result
    assert "pages" in result
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest services/model-server/tests/test_vlm_service.py -v
```

Expected: FAIL — LLMService doesn't support vllm or MinerUClient.

**Step 3: Rewrite LLMService as VLM-capable service**

将 `backend/services/model-server/app/domain/llm.py` 整体重写：

```python
"""MinerU VLM inference service via vllm + MinerUClient."""

from __future__ import annotations

import uuid
from typing import Any

import vllm
from mineru_vl_utils import MinerUClient, MinerULogitsProcessor
from PIL import Image

from app.domain.base import BaseModelService
from app.utils.logger import get_logger

logger = get_logger()


class LLMService(BaseModelService):
    """MinerU2.5-Pro VLM via vllm engine + MinerUClient.

    Provides document extraction from images using MinerU's two-step process:
    1. Structure detection (layout, tables, figures)
    2. Content extraction (markdown, structured data)
    """

    def __init__(
        self,
        model_id: str = "opendatalab/MinerU2.5-Pro-2604-1.2B",
        gpu_memory_utilization: float = 0.9,
        image_analysis: bool = False,
    ) -> None:
        super().__init__(model_id, gpu_memory_utilization)
        self._image_analysis = image_analysis
        self._client: MinerUClient | None = None

    def _load(self) -> None:
        logger.info("Loading VLM model via vllm: {id}", id=self._model_id)
        self._model = vllm.LLM(
            model=self._model_id,
            gpu_memory_utilization=self._gpu_memory_utilization,
            logits_processors=[MinerULogitsProcessor],
            trust_remote_code=True,
        )
        self._client = MinerUClient(
            backend="vllm-engine",
            vllm_llm=self._model,
            image_analysis=self._image_analysis,
        )
        logger.info("MinerUClient initialized (image_analysis={flag})", flag=self._image_analysis)

    def infer(self, image: Image.Image, **kwargs: Any) -> dict[str, Any]:
        """Extract structured content from an image.

        Args:
            image: PIL Image to extract from.

        Returns:
            Dict with 'full_markdown', 'pages', and 'metadata' keys.
        """
        self.ensure_loaded()
        assert self._client is not None

        logger.info("Running MinerU two_step_extract")
        result = self._client.two_step_extract(image)

        # MinerU returns (full_markdown, pages_data)
        if isinstance(result, tuple) and len(result) == 2:
            full_markdown, pages_data = result
        else:
            # Handle case where result is a single object
            full_markdown = str(result)
            pages_data = []

        return {
            "id": f"vlm-{uuid.uuid4().hex[:12]}",
            "full_markdown": full_markdown,
            "pages": pages_data,
            "metadata": {"total_pages": len(pages_data) if pages_data else 1},
        }
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest services/model-server/tests/test_vlm_service.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/services/model-server/app/domain/llm.py backend/services/model-server/tests/test_vlm_service.py
git commit -m "feat(model-server): implement MinerU VLM service with vllm + MinerUClient"
```

---

## Task 8: Add VLM API Route

**Files:**
- Create: `backend/services/model-server/app/api/vlm.py`
- Modify: `backend/services/model-server/app/api/__init__.py` (if exists)

**Step 1: Write test for VLM API endpoint**

```python
# backend/services/model-server/tests/test_vlm_api.py
import base64
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_test_client():
    """Create a test client with VLM route wired up."""
    with patch("app.domain.llm._require_cuda", return_value="cuda"):
        with patch("app.domain.llm.vllm.LLM"):
            with patch("app.domain.llm.MinerUClient"):
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


def test_vlm_extract_text_only():
    client, _ = _make_test_client()
    resp = client.post("/v1/chat/completions", json={
        "model": "opendatalab/MinerU2.5-Pro-2604-1.2B",
        "messages": [{"role": "user", "content": "Extract this document."}],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "pages" in data
    assert "full_markdown" in data


def test_vlm_extract_with_image():
    client, svc = _make_test_client()
    img_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100).decode()
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
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest services/model-server/tests/test_vlm_api.py -v
```

Expected: FAIL — `app.api.vlm` module doesn't exist.

**Step 3: Create VLM API route**

创建 `backend/services/model-server/app/api/vlm.py`：

```python
"""VLM / MinerU extraction API route — OpenAI-compatible multimodal endpoint."""

from __future__ import annotations

import base64
import io
import re
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from PIL import Image

from app.models import (
    VLMExtractRequest,
    VLMExtractResponse,
    VLMPageContent,
    VLMDocumentMetadata,
    VLMUsage,
)
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.domain.llm import LLMService

logger = get_logger()
router = APIRouter(tags=["vlm"])

_service: LLMService | None = None


def bind(service: LLMService) -> None:
    global _service
    _service = service


def _extract_images_from_messages(messages: list[dict]) -> list[Image.Image]:
    """Extract PIL Images from OpenAI multimodal message format."""
    images = []
    for msg in messages:
        content = msg.get("content", "")
        if not isinstance(content, list):
            continue
        for part in content:
            if part.get("type") != "image_url":
                continue
            url = part["image_url"]["url"]
            if url.startswith("data:"):
                # data:image/png;base64,<data>
                match = re.match(r"data:image/\w+;base64,(.+)", url)
                if match:
                    img_bytes = base64.b64decode(match.group(1))
                    images.append(Image.open(io.BytesIO(img_bytes)))
            else:
                raise HTTPException(status_code=400, detail="Only base64 data URIs are supported for image input.")
    return images


def _build_pages(pages_data: list[dict]) -> list[VLMPageContent]:
    """Convert raw page dicts to VLMPageContent list."""
    pages = []
    for i, page in enumerate(pages_data, start=1):
        page_number = page.get("page_number", i)
        pages.append(VLMPageContent(
            page_number=page_number,
            markdown=page.get("markdown", ""),
            figures=page.get("figures", []),
            tables=page.get("tables", []),
        ))
    return pages


@router.post("/v1/chat/completions", response_model=VLMExtractResponse)
def chat_completions(req: VLMExtractRequest):
    """OpenAI-compatible multimodal extraction endpoint.

    Accepts text and/or image inputs in OpenAI chat format.
    Returns structured extraction results as ParseResult-style JSON.
    """
    if _service is None or not _service.ready:
        raise HTTPException(status_code=503, detail="VLM service not available. Configure VLM_MODEL_ID to enable.")

    images = _extract_images_from_messages(req.messages)
    if not images:
        raise HTTPException(status_code=400, detail="No image found in messages. Provide an image via image_url content part.")

    # Use first image for extraction
    result = _service.infer(image=images[0])

    metadata = result.get("metadata", {})
    pages_data = result.get("pages", [])

    return VLMExtractResponse(
        id=result.get("id", ""),
        model=req.model or _service.model_id,
        metadata=VLMDocumentMetadata(
            total_pages=metadata.get("total_pages", len(pages_data)),
            title=metadata.get("title"),
            authors=metadata.get("authors", []),
            abstract_text=metadata.get("abstract_text"),
        ),
        pages=_build_pages(pages_data),
        full_markdown=result.get("full_markdown", ""),
        usage=VLMUsage(),
    )
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest services/model-server/tests/test_vlm_api.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/services/model-server/app/api/vlm.py backend/services/model-server/tests/test_vlm_api.py
git commit -m "feat(model-server): add VLM extraction API route at /v1/chat/completions"
```

---

## Task 9: Wire VLM into main.py

**Files:**
- Modify: `backend/services/model-server/main.py`

**Step 1: Write test for main.py wiring**

```python
# backend/services/model-server/tests/test_main_wiring.py
from unittest.mock import patch, MagicMock


def test_main_imports():
    """Verify main.py can be imported without errors (mocking heavy deps)."""
    with patch("app.domain.embedding.vllm.LLM"):
        with patch("app.domain.rerank.vllm.LLM"):
            with patch("app.domain.llm.vllm.LLM"):
                with patch("app.domain.llm.MinerUClient"):
                    with patch("app.domain.base._require_cuda", return_value="cuda"):
                        # Just verify import doesn't crash
                        import importlib
                        import app.api.vlm as vlm_mod
                        assert hasattr(vlm_mod, "router")
```

**Step 2: Run test to verify it passes (current state)**

```bash
cd backend && uv run pytest services/model-server/tests/test_main_wiring.py -v
```

Expected: PASS (vlm module exists from Task 8).

**Step 3: Update main.py**

在 `backend/services/model-server/main.py` 中：

添加 import：
```python
from app.api import chat, embedding, health, rerank, vlm
```

修改服务构建部分：
```python
cfg = get_config()

_embedding_svc = EmbeddingService(
    model_id=cfg.embedding_model_id,
    gpu_memory_utilization=cfg.vllm_gpu_memory_utilization,
)
_rerank_svc = RerankService(
    model_id=cfg.rerank_model_id,
    gpu_memory_utilization=cfg.vllm_gpu_memory_utilization,
)
_llm_svc = LLMService(
    model_id=cfg.vlm_model_id,
    gpu_memory_utilization=cfg.vllm_gpu_memory_utilization,
    image_analysis=cfg.vlm_image_analysis,
) if cfg.vlm_model_id else None
```

添加 VLM bind 和 router：
```python
embedding.bind(_embedding_svc)
rerank.bind(_rerank_svc)
if _llm_svc:
    chat.bind(_llm_svc)
    vlm.bind(_llm_svc)
```

更新 health 注册：
```python
health.register_services({
    "embedding": _embedding_svc,
    "rerank": _rerank_svc,
    **({"vlm": _llm_svc} if _llm_svc else {}),
})
```

添加 router：
```python
app.include_router(embedding.router)
app.include_router(rerank.router)
app.include_router(chat.router)
app.include_router(vlm.router)
app.include_router(health.router)
```

更新启动日志：
```python
logger.info("  VLM       : {id}", id=cfg.vlm_model_id or "(not configured)")
```

**Step 4: Verify no import errors**

```bash
cd backend && uv run python -c "
import sys
sys.path.insert(0, 'services/model-server')
# Quick import check
from app.api import vlm
print('VLM router imported OK')
"
```

Expected: `VLM router imported OK`

**Step 5: Commit**

```bash
git add backend/services/model-server/main.py
git commit -m "feat(model-server): wire VLM service into main.py with vllm config"
```

---

## Task 10: Update README

**Files:**
- Modify: `backend/services/model-server/README.md`

**Step 1: Update README**

更新 `backend/services/model-server/README.md`：

1. 更新依赖安装命令（移除 sentence-transformers，添加 vllm + mineru_vl_utils）
2. 添加 VLM API 端点文档
3. 添加 VLM 配置变量文档
4. 更新项目结构（vlm.py 在 api/ 和 domain/ 中）
5. 更新示例 curl 命令

关键变更：

```markdown
## 快速启动

```bash
cd services/model-server

# 安装依赖（复用 backend venv，vllm 由 pyproject.toml 管理）
uv pip install -e "../../.[dev]"

# 启动（默认 8001）
uv run python main.py
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查，返回各模型就绪状态 |
| `POST` | `/v1/embeddings` | 向量嵌入（vllm） |
| `POST` | `/v1/rerank` | 重排序（vllm） |
| `POST` | `/v1/chat/completions` | VLM 文档提取（MinerU + vllm，多模态） |

### VLM 文档提取

```bash
curl http://localhost:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "opendatalab/MinerU2.5-Pro-2604-1.2B",
    "messages": [
      {"role": "user", "content": [
        {"type": "text", "text": "Extract this document."},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,<BASE64_IMAGE>"}}
      ]}
    ]
  }'
```

响应格式：
```json
{
  "id": "vlm-abc123",
  "object": "vlm.extraction",
  "model": "opendatalab/MinerU2.5-Pro-2604-1.2B",
  "metadata": {"total_pages": 1, "title": null},
  "pages": [{"page_number": 1, "markdown": "...", "figures": [], "tables": []}],
  "full_markdown": "...",
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
}
```

## 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VLM_MODEL_ID` | _(空)_ | MinerU VLM 模型，配置后启用 VLM 端点 |
| `VLM_IMAGE_ANALYSIS` | `false` | 是否启用图像/图表分析 |
| `VLLM_GPU_MEMORY_UTILIZATION` | `0.9` | vllm GPU 显存分配比例 |
```

**Step 2: Commit**

```bash
git add backend/services/model-server/README.md
git commit -m "docs(model-server): update README for vllm migration and VLM endpoint"
```

---

## Task 11: Verify Full Integration

**Step 1: Run all model-server tests**

```bash
cd backend && uv run pytest services/model-server/tests/ -v
```

Expected: All tests PASS.

**Step 2: Run ruff lint**

```bash
cd backend && uv run ruff check services/model-server/
```

Expected: No errors.

**Step 3: Verify imports**

```bash
cd backend && uv run python -c "
import sys
sys.path.insert(0, 'services/model-server')
from app.models import VLMExtractRequest, VLMExtractResponse
from app.api.vlm import router
from app.enums.model_type import ModelType
print('All imports OK')
print(f'ModelType.VLM = {ModelType.VLM}')
"
```

Expected: `All imports OK` and `ModelType.VLM = vlm`

**Step 4: Commit any fixes**

If lint or tests found issues, fix and commit.

---

## Task 12: Archive Plan Document

**Step 1: Move plan to archive**

```bash
mv docs/planned/2026-05-11-mineru-vlm-vllm-migration.md docs/archive/
```

**Step 2: Update progress.txt**

```bash
echo "[2026-05-11] MinerU VLM + vllm migration [DONE]" >> progress.txt
```

---

## Summary of Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/pyproject.toml` | Modify | Add vllm, mineru_vl_utils deps |
| `app/config.py` | Modify | Add vlm_model_id, vlm_image_analysis, vllm_gpu_memory_utilization |
| `app/models/schemas.py` | Modify | Add VLM request/response schemas |
| `app/models/__init__.py` | Modify | Export VLM schemas |
| `app/enums/model_type.py` | Modify | Add VLM enum |
| `app/domain/base.py` | Modify | Remove torch CUDA check, add gpu_memory_utilization |
| `app/domain/embedding.py` | Rewrite | vllm.LLM with task="embed" |
| `app/domain/rerank.py` | Rewrite | vllm.LLM with task="score" |
| `app/domain/llm.py` | Rewrite | vllm.LLM + MinerUClient |
| `app/api/vlm.py` | Create | /v1/chat/completions multimodal endpoint |
| `main.py` | Modify | Wire VLM, update config params |
| `README.md` | Modify | Update docs for vllm + VLM |
| `tests/` | Create | 6 new test files |

## Key Design Decisions

1. **vllm as unified backend** — All three model types (embedding, rerank, VLM) use vllm.LLM with different `task` parameters
2. **MinerUClient wraps vllm** — VLM uses MinerUClient(backend="vllm-engine") for two-step extraction
3. **OpenAI-compatible API** — `/v1/chat/completions` accepts multimodal messages, returns structured ParseResult JSON
4. **GPU memory control** — Single `VLLM_GPU_MEMORY_UTILIZATION` config applied to all services
5. **Shared LLM instance** — chat.py and vlm.py share the same LLMService (MinerU VLM is the LLM)
