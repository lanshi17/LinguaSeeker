"""Unit tests for InteractionAgent"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.domain.agent.interaction import InteractionAgent, TaskFormStructured


@pytest.fixture
def mock_config():
    """Mock configuration for tests"""
    config = MagicMock()
    config.evidence_model = "test-model"
    config.evidence_api_key = "test-key"
    config.evidence_base_url = "https://api.test.com"
    config.llm_timeout = 30
    return config


@pytest.fixture
def mock_llm_response():
    """Mock LLM response object"""
    response = MagicMock()
    response.content = """```json
{
  "needs_clarification": false,
  "clarification_question": null,
  "extracted_fields": {
    "goal": "functional evidence",
    "disease": "LDLR variant",
    "country": "不限",
    "language": "auto"
  }
}
```"""
    return response


@pytest.fixture
def agent(mock_config):
    """Create InteractionAgent with mocked LLM"""
    with patch("src.domain.agent.interaction.ChatOpenAI") as mock_chat:
        mock_llm_instance = MagicMock()
        mock_chat.return_value = mock_llm_instance
        agent = InteractionAgent(cfg=mock_config)
        agent.llm = mock_llm_instance
        yield agent


class TestInteractionAgent:
    """Test InteractionAgent functionality"""

    @pytest.mark.asyncio
    async def test_start_interaction_clear_input(self, agent, mock_llm_response):
        """Test starting interaction with clear input that needs no clarification"""
        agent.llm.ainvoke = AsyncMock(return_value=mock_llm_response)

        result = await agent.start_interaction("I need functional evidence for LDLR variant")

        assert result["ready"] is True
        assert result["task_form"] is not None
        assert result["task_form"]["goal"] == "functional evidence"
        assert result["task_form"]["disease"] == "LDLR variant"
        assert result["question"] is None
        assert result["round"] == 0
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_start_interaction_needs_clarification(self, agent):
        """Test starting interaction with vague input that needs clarification"""
        clarification_response = MagicMock()
        clarification_response.content = """```json
{
  "needs_clarification": true,
  "clarification_question": "What disease or gene are you researching?",
  "extracted_fields": {
    "goal": "evidence",
    "disease": null,
    "country": null,
    "language": null
  }
}
```"""
        agent.llm.ainvoke = AsyncMock(return_value=clarification_response)

        result = await agent.start_interaction("I need some evidence")

        assert result["ready"] is False
        assert result["task_form"] is None
        assert result["question"] == "What disease or gene are you researching?"
        assert result["round"] == 1
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_respond_interaction_completes_after_one_round(self, agent, mock_llm_response):
        """Test responding to clarification and completing task form"""
        # First start with vague input
        clarification_response = MagicMock()
        clarification_response.content = """```json
{
  "needs_clarification": true,
  "clarification_question": "What disease are you researching?",
  "extracted_fields": {
    "goal": "functional evidence",
    "disease": null,
    "country": null,
    "language": null
  }
}
```"""
        agent.llm.ainvoke = AsyncMock(return_value=clarification_response)
        start_result = await agent.start_interaction("I need functional evidence")
        session_id = start_result["session_id"]

        # Then respond with disease
        agent.llm.ainvoke = AsyncMock(return_value=mock_llm_response)
        result = await agent.respond_interaction(session_id, "LDLR variant")

        assert result["ready"] is True
        assert result["task_form"] is not None
        assert result["task_form"]["goal"] == "functional evidence"
        assert result["task_form"]["disease"] == "LDLR variant"
        assert result["question"] is None

    @pytest.mark.asyncio
    async def test_respond_interaction_max_rounds(self, agent):
        """Test that after 2 rounds, agent returns task form with defaults"""
        # Start with vague input
        clarification_response = MagicMock()
        clarification_response.content = """```json
{
  "needs_clarification": true,
  "clarification_question": "What is your goal?",
  "extracted_fields": {
    "goal": null,
    "disease": null,
    "country": null,
    "language": null
  }
}
```"""
        agent.llm.ainvoke = AsyncMock(return_value=clarification_response)
        start_result = await agent.start_interaction("I need some help")
        session_id = start_result["session_id"]

        # Respond vaguely again
        result = await agent.respond_interaction(session_id, "For research")

        # Even if still unclear, should continue
        assert result["round"] == 2

        # Second response should trigger max rounds limit
        result = await agent.respond_interaction(session_id, "More info")

        assert result["ready"] is True
        assert result["task_form"] is not None
        # Should have defaults applied
        assert result["task_form"]["country"] == "不限"
        assert result["task_form"]["language"] == "auto"

    @pytest.mark.asyncio
    async def test_respond_interaction_invalid_session(self, agent):
        """Test that invalid session_id raises ValueError"""
        with pytest.raises(ValueError, match="Invalid session_id"):
            await agent.respond_interaction("invalid-session-id", "Some response")

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self, agent):
        """Test that LLM failure returns safe fallback"""
        agent.llm.ainvoke = AsyncMock(side_effect=Exception("LLM timeout"))

        result = await agent.start_interaction("I need evidence")

        assert result["ready"] is False
        assert "clarify your research goal" in result["question"]
        assert result["round"] == 1

    def test_finalize_task_form_with_defaults(self, agent):
        """Test that _finalize_task_form applies defaults correctly"""
        extracted_fields = {
            "goal": "functional evidence",
            "disease": None,
            "country": None,
            "language": None,
        }

        task_form = agent._finalize_task_form(extracted_fields)

        assert task_form.goal == "functional evidence"
        assert task_form.disease == "unspecified"
        assert task_form.country == "不限"
        assert task_form.language == "auto"

    @pytest.mark.asyncio
    async def test_session_rehydrates_across_agent_instances(self, mock_config, mock_llm_response):
        class FakeRedisConnection:
            def __init__(self) -> None:
                self.data = {}

            def set(self, key, value, ex=None):
                self.data[key] = value

            def get(self, key):
                return self.data.get(key)

            def delete(self, key):
                self.data.pop(key, None)

        fake_redis = FakeRedisConnection()

        class FakeRedisClient:
            def get_connection(self):
                return fake_redis

        clarification_response = MagicMock()
        clarification_response.content = """```json
{
  "needs_clarification": true,
  "clarification_question": "What disease are you researching?",
  "extracted_fields": {
    "goal": "functional evidence",
    "disease": null,
    "country": null,
    "language": null
  }
}
```"""

        with patch("src.domain.agent.interaction.ChatOpenAI"):
            with patch("src.domain.agent.interaction.RedisClient", return_value=FakeRedisClient()):
                agent_a = InteractionAgent(cfg=mock_config)
                agent_b = InteractionAgent(cfg=mock_config)

        agent_a.llm = MagicMock()
        agent_a.llm.ainvoke = AsyncMock(return_value=clarification_response)
        start_result = await agent_a.start_interaction("I need functional evidence")

        agent_b.llm = MagicMock()
        agent_b.llm.ainvoke = AsyncMock(return_value=mock_llm_response)
        result = await agent_b.respond_interaction(start_result["session_id"], "LDLR variant")

        assert result["ready"] is True
        assert result["task_form"]["disease"] == "LDLR variant"


class TestTaskFormStructured:
    """Test TaskFormStructured model"""

    def test_task_form_defaults(self):
        """Test TaskFormStructured default values"""
        form = TaskFormStructured(goal="test goal", disease="test disease")
        assert form.goal == "test goal"
        assert form.disease == "test disease"
        assert form.country == "不限"
        assert form.language == "auto"

    def test_task_form_custom_values(self):
        """Test TaskFormStructured with custom values"""
        form = TaskFormStructured(
            goal="functional evidence",
            disease="LDLR variant",
            country="CN",
            language="Chinese",
        )
        assert form.goal == "functional evidence"
        assert form.disease == "LDLR variant"
        assert form.country == "CN"
        assert form.language == "Chinese"
