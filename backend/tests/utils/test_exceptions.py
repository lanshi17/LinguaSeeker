"""Tests for the centralized exception hierarchy."""
from __future__ import annotations

import pytest

from src.utils.exceptions import (
    ACMGException,
    DatabaseException,
    LLMException,
    NotFoundException,
    ParsingException,
    ServiceException,
    TranslationException,
    ValidationException,
    error_code_from_exception,
)


class TestACMGException:
    def test_base_exception_stores_message_and_code(self):
        exc = ACMGException("something broke", code="GENERIC_ERROR")
        assert exc.message == "something broke"
        assert exc.code == "GENERIC_ERROR"
        assert str(exc) == "something broke"

    def test_default_code_is_internal_error(self):
        exc = ACMGException("oops")
        assert exc.code == "INTERNAL_ERROR"


class TestSubclasses:
    def test_not_found_has_code(self):
        exc = NotFoundException("item", "123")
        assert exc.code == "NOT_FOUND"
        assert "item" in exc.message
        assert "123" in exc.message

    def test_validation_has_code(self):
        exc = ValidationException("bad input")
        assert exc.code == "VALIDATION_ERROR"

    def test_database_has_code(self):
        exc = DatabaseException("connection refused")
        assert exc.code == "DATABASE_ERROR"

    def test_llm_has_code(self):
        exc = LLMException("timeout")
        assert exc.code == "LLM_ERROR"

    def test_translation_has_code(self):
        exc = TranslationException("failed")
        assert exc.code == "TRANSLATION_ERROR"

    def test_parsing_has_code(self):
        exc = ParsingException("corrupt pdf")
        assert exc.code == "PARSING_ERROR"

    def test_service_has_code(self):
        exc = ServiceException("unavailable")
        assert exc.code == "SERVICE_ERROR"


class TestErrorCodeFromException:
    def test_acmg_exception_returns_its_code(self):
        exc = LLMException("boom")
        assert error_code_from_exception(exc) == "LLM_ERROR"

    def test_generic_exception_returns_internal_error(self):
        exc = ValueError("unexpected")
        assert error_code_from_exception(exc) == "INTERNAL_ERROR"

    def test_http_status_mapping(self):
        assert error_code_from_exception(Exception(), status_code=404) == "NOT_FOUND"
        assert error_code_from_exception(Exception(), status_code=422) == "VALIDATION_ERROR"
        assert error_code_from_exception(Exception(), status_code=500) == "INTERNAL_ERROR"
