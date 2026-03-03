import json
from typing import Dict, List, Optional
from uuid import uuid4

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, SecretStr

from src.config import settings

cfg = settings


class TaskFormStructured(BaseModel):
    goal: str
    disease: str
    country: str = "不限"
    language: str = "auto"


class SessionState(BaseModel):
    session_id: str
    round: int
    history: List[Dict[str, str]]
    extracted_fields: Dict[str, Optional[str]]


class InteractionAgent:
    def __init__(self, cfg=settings):
        self.cfg = cfg
        self._sessions: Dict[str, SessionState] = {}

        anthropic_base_url = self._normalize_anthropic_base_url(cfg.evidence_base_url)
        self.llm = ChatAnthropic(
            model_name=cfg.evidence_model,
            api_key=SecretStr(cfg.evidence_api_key),
            base_url=anthropic_base_url,
            temperature=0.3,
            timeout=cfg.llm_timeout,
            stop=["\n\nHuman:"],
        )
        logger.info("InteractionAgent initialized with model: {}", cfg.evidence_model)

    def _normalize_anthropic_base_url(self, base_url: str) -> str:
        if not base_url:
            return base_url
        cleaned = base_url.rstrip("/")
        if cleaned.endswith("/v1"):
            cleaned = cleaned[:-3]
        return cleaned

    async def start_interaction(self, user_input: str) -> Dict:
        session_id = str(uuid4())
        history = [{"role": "user", "content": user_input}]

        result = await self._analyze_input(user_input, history)

        state = SessionState(
            session_id=session_id,
            round=0 if result["ready"] else 1,
            history=history,
            extracted_fields=result["extracted_fields"],
        )
        self._sessions[session_id] = state

        if result["ready"]:
            task_form = self._finalize_task_form(result["extracted_fields"])
            return {
                "session_id": session_id,
                "ready": True,
                "task_form": task_form.model_dump(),
                "question": None,
                "round": 0,
            }

        state.history.append({"role": "assistant", "content": result["question"]})
        return {
            "session_id": session_id,
            "ready": False,
            "task_form": None,
            "question": result["question"],
            "round": 1,
        }

    async def respond_interaction(self, session_id: str, user_response: str) -> Dict:
        if session_id not in self._sessions:
            raise ValueError(f"Invalid session_id: {session_id}")

        state = self._sessions[session_id]
        if state.round >= 2:
            task_form = self._finalize_task_form(state.extracted_fields)
            return {
                "ready": True,
                "task_form": task_form.model_dump(),
                "question": None,
                "round": state.round,
            }

        state.history.append({"role": "user", "content": user_response})

        result = await self._analyze_input(user_response, state.history)

        state.extracted_fields.update(
            {k: v for k, v in result["extracted_fields"].items() if v is not None}
        )

        if result["ready"] or state.round >= 2:
            task_form = self._finalize_task_form(state.extracted_fields)
            state.round = state.round + 1
            return {
                "ready": True,
                "task_form": task_form.model_dump(),
                "question": None,
                "round": state.round,
            }

        state.round += 1
        state.history.append({"role": "assistant", "content": result["question"]})
        return {
            "ready": False,
            "task_form": None,
            "question": result["question"],
            "round": state.round,
        }

    async def _analyze_input(self, user_input: str, history: List[Dict]) -> Dict:
        system_prompt = """You are a genetics literature search assistant. Extract the following fields from user input:
- goal: Research objective or evidence type (e.g., "functional evidence", "pathogenicity", "PS3 evidence")
- disease: Disease, gene, or variant name (e.g., "LDLR gene variant", "familial hypercholesterolemia")
- country: Country or region (e.g., "China", "US", "不限" for any)
- language: Language preference (e.g., "Chinese", "English", "auto" for any)

If all required fields (goal, disease) are present, set needs_clarification=false.
If any required field is missing or ambiguous, set needs_clarification=true and ask ONE focused question.

Return ONLY valid JSON with this structure:
{
  "needs_clarification": true/false,
  "clarification_question": "your question here" or null,
  "extracted_fields": {
    "goal": "value" or null,
    "disease": "value" or null,
    "country": "value" or null,
    "language": "value" or null
  }
}"""

        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
        user_message = f"""Conversation history:
{history_text}

Current input: {user_input}

Extract the fields and determine if clarification is needed."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            content = response.content.strip()

            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            parsed = json.loads(content)

            extracted = parsed.get("extracted_fields", {})
            needs_clarification = parsed.get("needs_clarification", True)
            question = parsed.get("clarification_question")

            has_goal = extracted.get("goal") is not None
            has_disease = extracted.get("disease") is not None
            ready = has_goal and has_disease and not needs_clarification

            return {
                "ready": ready,
                "question": question if not ready else None,
                "extracted_fields": extracted,
            }
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {
                "ready": False,
                "question": "Could you please clarify your research goal and disease/gene of interest?",
                "extracted_fields": {},
            }

    def _finalize_task_form(self, extracted_fields: Dict) -> TaskFormStructured:
        return TaskFormStructured(
            goal=extracted_fields.get("goal") or "evidence synthesis",
            disease=extracted_fields.get("disease") or "unspecified",
            country=extracted_fields.get("country") or "不限",
            language=extracted_fields.get("language") or "auto",
        )
