"""Tests for utils/observability.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.utils.observability import traced_node


class TestTracedNode:
    def test_basic_execution(self):
        @traced_node("test_node")
        def my_node(state: dict) -> dict:
            return {"result": state["input"] + 1}

        result = my_node({"input": 5})
        assert result == {"result": 6}

    def test_logging_on_success(self):
        @traced_node("success_node")
        def my_node(state: dict) -> dict:
            return state

        with patch("src.utils.observability.logger") as mock_logger:
            my_node({"data": "test"})
            mock_logger.info.assert_any_call("Node [{}] start", "success_node")
            mock_logger.info.assert_any_call("Node [{}] done", "success_node")

    def test_logging_on_failure(self):
        @traced_node("fail_node")
        def my_node(state: dict) -> dict:
            raise ValueError("test error")

        with patch("src.utils.observability.logger") as mock_logger:
            with pytest.raises(ValueError, match="test error"):
                my_node({})
            mock_logger.info.assert_any_call("Node [{}] start", "fail_node")
            mock_logger.error.assert_called_once()

    def test_preserves_function_name(self):
        @traced_node("named_node")
        def my_custom_node(state: dict) -> dict:
            return state

        assert my_custom_node.__name__ == "my_custom_node"

    def test_kwargs_passthrough(self):
        @traced_node("kwargs_node")
        def my_node(state: dict, multiplier: int = 1) -> dict:
            return {"result": state["value"] * multiplier}

        result = my_node({"value": 3}, multiplier=2)
        assert result == {"result": 6}

    @pytest.mark.asyncio
    async def test_traced_node_with_async_function(self):
        """traced_node should properly await async functions and log correctly."""

        @traced_node("async_test")
        async def async_fn(x: int) -> int:
            return x * 2

        with patch("src.utils.observability.logger") as mock_logger:
            result = await async_fn(5)
            assert result == 10
            mock_logger.info.assert_any_call("Node [{}] start", "async_test")
            mock_logger.info.assert_any_call("Node [{}] done", "async_test")
