import asyncio
import json
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, SecretStr

from src.config import settings, resolve_llm_triplet
from src.infrastructure.redis import RedisClient

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
        self._session_locks: Dict[str, asyncio.Lock] = {}
        self._session_ttl_seconds = int(
            getattr(cfg, "interaction_session_ttl_seconds", 3600)
        )
        try:
            self._redis_client: Optional[RedisClient] = RedisClient()
        except Exception as exc:
            logger.warning(
                "Interaction session store unavailable, fallback to memory: {}", exc
            )
            self._redis_client = None

        llm_config = resolve_llm_triplet(cfg, "evidence")
        self.llm = ChatOpenAI(
            model=llm_config.model,
            api_key=SecretStr(llm_config.api_key or ""),
            base_url=llm_config.base_url,
            temperature=0.3,
            timeout=cfg.llm_timeout,
        )
        logger.info("InteractionAgent initialized with model: {}", llm_config.model)

    def _session_key(self, session_id: str) -> str:
        return f"interaction:session:{session_id}"

    def _normalize_session_id(self, session_id: str) -> str:
        normalized = str(session_id or "").strip()
        try:
            UUID(normalized)
        except Exception as exc:
            raise ValueError(f"Invalid session_id: {session_id}") from exc
        return normalized

    def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        return self._session_locks.setdefault(session_id, asyncio.Lock())

    def _get_redis_connection(self):
        try:
            if self._redis_client is None:
                self._redis_client = RedisClient()
            return self._redis_client.get_connection()
        except Exception as exc:
            logger.warning(
                "Interaction session store unavailable, fallback to memory: {}", exc
            )
            return None

    def _save_session(self, state: SessionState) -> None:
        self._sessions[state.session_id] = state
        redis_conn = self._get_redis_connection()
        if redis_conn is None:
            return
        try:
            redis_conn.set(
                self._session_key(state.session_id),
                state.model_dump_json(),
                ex=self._session_ttl_seconds,
            )
        except Exception as exc:
            logger.warning(
                "Failed to persist interaction session {}: {}", state.session_id, exc
            )

    def _load_session(self, session_id: str) -> Optional[SessionState]:
        state = self._sessions.get(session_id)
        if state is not None:
            return state

        redis_conn = self._get_redis_connection()
        if redis_conn is None:
            return None

        try:
            payload = redis_conn.get(self._session_key(session_id))
            if payload is None:
                return None
            if not isinstance(payload, (str, bytes, bytearray)):
                return None
            serialized_payload: str | bytes | bytearray = payload
            if isinstance(serialized_payload, bytes):
                serialized_payload = serialized_payload.decode("utf-8")
            state = SessionState.model_validate_json(serialized_payload)
            self._sessions[session_id] = state
            return state
        except Exception as exc:
            logger.warning("Failed to load interaction session {}: {}", session_id, exc)
            return None

    def _delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._session_locks.pop(session_id, None)
        redis_conn = self._get_redis_connection()
        if redis_conn is None:
            return
        try:
            redis_conn.delete(self._session_key(session_id))
        except Exception as exc:
            logger.warning(
                "Failed to delete interaction session {}: {}", session_id, exc
            )

    async def start_interaction(self, user_input: str) -> Dict[str, Any]:
        session_id = str(uuid4())
        history = [{"role": "user", "content": user_input}]

        result = await self._analyze_input(user_input, history)

        state = SessionState(
            session_id=session_id,
            round=0 if result["ready"] else 1,
            history=history,
            extracted_fields=result["extracted_fields"],
        )
        self._get_session_lock(session_id)
        self._save_session(state)

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
        self._save_session(state)
        return {
            "session_id": session_id,
            "ready": False,
            "task_form": None,
            "question": result["question"],
            "round": 1,
        }

    async def respond_interaction(
        self, session_id: str, user_response: str
    ) -> Dict[str, Any]:
        normalized_session_id = self._normalize_session_id(session_id)
        async with self._get_session_lock(normalized_session_id):
            state = self._load_session(normalized_session_id)
            if state is None:
                raise ValueError(f"Invalid session_id: {session_id}")

            if state.round >= 2:
                task_form = self._finalize_task_form(state.extracted_fields)
                self._save_session(state)
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
                self._save_session(state)
                return {
                    "ready": True,
                    "task_form": task_form.model_dump(),
                    "question": None,
                    "round": state.round,
                }

            state.round += 1
            state.history.append({"role": "assistant", "content": result["question"]})
            self._save_session(state)
            return {
                "ready": False,
                "task_form": None,
                "question": result["question"],
                "round": state.round,
            }

    async def _analyze_input(
        self, user_input: str, history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
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

        history_text = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in history]
        )
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
            raw_content = response.content
            if isinstance(raw_content, str):
                content = raw_content.strip()
            elif isinstance(raw_content, list):
                content = " ".join(str(item) for item in raw_content).strip()
            else:
                content = str(raw_content).strip()

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

    def _finalize_task_form(
        self, extracted_fields: Dict[str, Any]
    ) -> TaskFormStructured:
        return TaskFormStructured(
            goal=extracted_fields.get("goal") or "evidence synthesis",
            disease=extracted_fields.get("disease") or "unspecified",
            country=extracted_fields.get("country") or "不限",
            language=extracted_fields.get("language") or "auto",
        )
