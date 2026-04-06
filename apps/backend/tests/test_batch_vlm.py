from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

from src.domain.agent.workflow import EvidenceAgent


@pytest.fixture()
def tmp_images(tmp_path: Path) -> list[str]:
    paths: list[str] = []
    for i in range(3):
        p = tmp_path / f"img_{i}.png"
        p.write_bytes(b"\x89PNG_fake_image_data_" + str(i).encode())
        paths.append(str(p))
    return paths


@pytest.fixture()
def vlm_mock() -> MagicMock:
    mock = MagicMock()
    mock.invoke.return_value = AIMessage(
        content="Figure 1: Western blot showing protein expression\n"
        "Figure 2: Bar chart of fold change values\n"
        "Figure 3: Microscopy image of cells"
    )
    return mock


@pytest.fixture()
def agent() -> EvidenceAgent:
    a = EvidenceAgent.__new__(EvidenceAgent)
    cfg = MagicMock()
    cfg.vlm_enable = True
    cfg.vlm_max_batch_images = 10
    a.cfg = cfg
    return a


class TestDescribeImagesBatch:
    def test_single_image(self, agent: EvidenceAgent, tmp_images: list[str]) -> None:
        vlm = MagicMock()
        vlm.invoke.return_value = AIMessage(content="Figure 1: A single blot image")
        result = agent._describe_images_batch(vlm, tmp_images[:1])
        assert len(result) == 1
        assert "single blot image" in result[0]
        vlm.invoke.assert_called_once()

    def test_multiple_images(
        self, agent: EvidenceAgent, tmp_images: list[str], vlm_mock: MagicMock
    ) -> None:
        result = agent._describe_images_batch(vlm_mock, tmp_images)
        assert len(result) == 3
        vlm_mock.invoke.assert_called_once()
        call_args = vlm_mock.invoke.call_args[0][0]
        msg = call_args[0]
        image_blocks = [
            c for c in msg.content if isinstance(c, dict) and c.get("type") == "image_url"
        ]
        assert len(image_blocks) == 3

    def test_fewer_descriptions_than_images(
        self, agent: EvidenceAgent, tmp_images: list[str]
    ) -> None:
        vlm = MagicMock()
        vlm.invoke.return_value = AIMessage(content="Figure 1: Only one described")
        result = agent._describe_images_batch(vlm, tmp_images)
        assert len(result) == 3
        assert result[0] == "Only one described"
        assert result[1] == ""
        assert result[2] == ""


class TestDescribeImages:
    def test_vlm_disabled(self, agent: EvidenceAgent) -> None:
        state: dict[str, Any] = {
            "enable_vlm": False,
            "image_paths": ["/fake/img.png"],
        }
        result = agent.describe_images(cast(Any, state))
        assert result["image_descriptions"] == []

    def test_empty_image_paths(self, agent: EvidenceAgent) -> None:
        state: dict[str, Any] = {"enable_vlm": True, "image_paths": []}
        result = agent.describe_images(cast(Any, state))
        assert result["image_descriptions"] == []

    def test_batch_processing(
        self, agent: EvidenceAgent, tmp_images: list[str], vlm_mock: MagicMock
    ) -> None:
        agent.get_vlm = MagicMock(return_value=vlm_mock)  # type: ignore[method-assign]
        state: dict[str, Any] = {"enable_vlm": True, "image_paths": tmp_images}
        result = agent.describe_images(cast(Any, state))
        assert len(result["image_descriptions"]) == 3
        assert "image_inputs" in result
        assert len(result["image_inputs"]) == 3
        for entry in result["image_inputs"]:
            assert "path" in entry
            assert "base64" in entry
            assert "mime_type" in entry

    def test_exceed_max_batch_creates_multiple_batches(
        self, agent: EvidenceAgent, tmp_path: Path
    ) -> None:
        paths: list[str] = []
        for i in range(5):
            p = tmp_path / f"img_{i}.png"
            p.write_bytes(b"\x89PNG_fake_" + str(i).encode())
            paths.append(str(p))

        agent.cfg.vlm_max_batch_images = 2
        vlm = MagicMock()
        vlm.invoke.return_value = AIMessage(content="Figure 1: desc A\nFigure 2: desc B")
        agent.get_vlm = MagicMock(return_value=vlm)  # type: ignore[method-assign]
        state: dict[str, Any] = {"enable_vlm": True, "image_paths": paths}
        result = agent.describe_images(cast(Any, state))
        assert len(result["image_descriptions"]) == 5
        assert vlm.invoke.call_count == 3  # ceil(5/2) = 3 batches

    def test_file_error_raises(self, agent: EvidenceAgent) -> None:
        agent.get_vlm = MagicMock()  # type: ignore[method-assign]
        state: dict[str, Any] = {
            "enable_vlm": True,
            "image_paths": ["/nonexistent/img.png"],
        }
        with pytest.raises(Exception):
            agent.describe_images(cast(Any, state))

    def test_fallback_on_batch_failure(self, agent: EvidenceAgent, tmp_images: list[str]) -> None:
        vlm = MagicMock()
        call_count = 0

        def side_effect(messages: list[Any]) -> AIMessage:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Batch VLM failed")
            return AIMessage(content=f"Individual description {call_count - 1}")

        vlm.invoke.side_effect = side_effect
        agent.get_vlm = MagicMock(return_value=vlm)  # type: ignore[method-assign]
        state: dict[str, Any] = {"enable_vlm": True, "image_paths": tmp_images}
        result = agent.describe_images(cast(Any, state))
        assert len(result["image_descriptions"]) == 3
        # 1 batch attempt (failed) + 3 individual
        assert vlm.invoke.call_count == 4

    def test_image_inputs_populated(
        self, agent: EvidenceAgent, tmp_images: list[str], vlm_mock: MagicMock
    ) -> None:
        agent.get_vlm = MagicMock(return_value=vlm_mock)  # type: ignore[method-assign]
        state: dict[str, Any] = {"enable_vlm": True, "image_paths": tmp_images}
        result = agent.describe_images(cast(Any, state))
        assert len(result["image_inputs"]) == 3
        for entry in result["image_inputs"]:
            decoded = base64.b64decode(entry["base64"])
            assert decoded.startswith(b"\x89PNG")
