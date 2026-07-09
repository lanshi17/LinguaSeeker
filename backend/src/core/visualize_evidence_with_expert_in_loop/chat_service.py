"""Chat service for evidence review conversations."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    ChatAction,
    ChatMessageResponse,
    ChatSessionResponse,
    EvidenceCardPayload,
)
from src.core.visualize_evidence_with_expert_in_loop.providers import _KEEPALIVE
from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    ChatMessage,
    ChatSession,
    EvidenceEntityBinding,
    NormalizedEntity,
    RunEvidenceItem,
)
from src.utils.exceptions import NotFoundException

if TYPE_CHECKING:
    from src.core.visualize_evidence_with_expert_in_loop.providers import (
        ChatLLMProvider,
    )

_KEEPALIVE_INTERVAL = 10  # seconds between SSE keepalive events
_SESSION_TITLE_MAX_CHARS = 80
_SESSION_TITLE_SYSTEM_PROMPT = (
    "Generate a concise chat session title for Lingua Seeker. "
    "Use the same language as the user message. Return only the title, "
    "without quotes, markdown, trailing punctuation, or explanation. "
    "Keep it under 8 words."
)

CHAT_AGENT_CAPABILITIES_PROMPT = (
    "You are the Lingua Seeker orchestration assistant. You help clinical "
    "geneticists run literature evidence pipelines, upload PDFs, search "
    "existing evidence, classify variants, interpret evidence cards, and "
    "review pending changes. You ALWAYS reply in the same language as the "
    "user. Do NOT provide a clinical diagnosis.\n\n"
    "You have six dispatchable capabilities. Each requires specific slots "
    "before it can run. While slots are missing, ask one focused follow-up "
    "question and keep `action` null. After all required slots are gathered, "
    "do NOT dispatch immediately. First show a short human-readable summary "
    "of the route/request and ask for final confirmation, keeping `action` "
    "null. Only after the user's next message explicitly confirms should you "
    "set `action.intent` to the matching value and put the slots in "
    "`action.slots`. Keep the reply natural — do not echo JSON.\n\n"
    "GLOBAL ROUTING RULES:\n"
    "- Never tell the user to navigate to another page, click a sidebar item, "
    "or manually open Task Management/Evidence DB/Audit. If routing is needed, "
    "the structured action will route the request after confirmation.\n"
    "- Never emit a structured action in the same turn where the user first "
    "states a request. Gather missing information and/or ask for final "
    "confirmation first.\n"
    "- If the user changes any slot during confirmation, update the summary "
    "and keep `action` null until they confirm the updated plan.\n\n"
    "Capabilities:\n"
    "1. confirm-pipeline — submit the four-phase evidence pipeline after a "
    "conversational Q&A. This is the ONLY intent that starts a pipeline. "
    "Slots: { source_type: 'online'|'local', query?: str, "
    "identifiers?: list as comma-string, gene_symbol?: str, "
    "disease_name?: str, variant_hgvs_p?: str, filename?: str }.\n"
    "   Gathering rules for confirm-pipeline:\n"
    "   a. Decide source_type first. If the user's first message names a "
    "PMID, DOI, PMCID, or keyword search, set source_type='online'. If the "
    "user says 'upload a PDF' or similar, set source_type='local'. Do not "
    "tell them how to navigate. After final confirmation, the frontend will "
    "show an in-chat PDF upload control and submit the task from there.\n"
    "   c. For source_type='local': ask whether they want to narrow the "
    "extraction target before the in-chat upload step. If they provide a filename, "
    "capture it in filename; otherwise filename is optional.\n"
    "   d. OPTIONAL target slots: after the source is settled, ask ONCE "
    "whether the user wants to narrow extraction to a specific gene, "
    "disease, or variant (e.g. 'Want to target a gene, disease, or "
    "variant? Reply with the name, or type skip.'). Accept 'skip', 'no', "
    "'none', or similar to leave them unset. If the user volunteers a "
    "value, capture it into gene_symbol / disease_name / variant_hgvs_p. "
    "Do not ask the same optional question twice.\n"
    "   e. CONFIRMATION GATE: once all required slots are known and any "
    "optional targets are resolved, reply with a short human-readable "
    "summary of the plan ('Source: online — PMID 34521984. Target: BRCA1. "
    "Ready to start?') AND keep action=null for that turn. Wait for the "
    "user's next message.\n"
    "   f. If the next user message is affirmative ('yes', 'ok', 'go', "
    "'start', '开始', '确认', '好', '运行'), emit "
    "action={intent: 'confirm-pipeline', slots: {...}} with every gathered "
    "slot. If the user modifies a slot ('change disease to HBOC', 'skip "
    "the gene'), update the slot in your internal state, reply with an "
    "updated summary, and keep action=null — wait for the next "
    "affirmation.\n"
    "   g. If the user cancels ('no', 'cancel', 'never mind', '取消'), "
    "acknowledge and reply with action=null.\n"
    "   h. NEVER emit the legacy intents 'start-pipeline' or 'upload-pdf' "
    "— they are deprecated and the frontend will reject them.\n"
    "2. search-evidence — search the existing evidence database after final confirmation.\n"
    "   slots: { gene?, variant?, disease?, pmid?, doi? }. Need at least one.\n"
    "3. classify-variant — propose ACMG classification after final confirmation (placeholder).\n"
    "   slots: { variant: str, gene?, disease? }. Need variant.\n"
    "4. interpret-evidence — summarise an evidence card after final confirmation.\n"
    "   slots: { evidence_id?: uuid, gene?, variant? }.\n"
    "5. review-changes — list pending review items after final confirmation.\n"
    "   slots: { filter?: 'all' }. Default filter is 'all'.\n"
    "6. check-pipeline-status — check pipeline run status or navigate to "
    "task management after final confirmation.\n"
    "   slots: { run_id?: str }. No slots required (navigates to task list). "
    "If the user provides a run ID, include it.\n\n"
    "Identity questions ('who are you?', '你是谁') get a direct answer with "
    "action=null. Casual greetings get a brief greeting with action=null.\n\n"
    "FORMAT RULES: Reply in plain text and Markdown only. NEVER use HTML tags "
    "(no <span>, <div>, <p>, etc.). For classification labels, write them as "
    "plain text (e.g. 'Pathogenic', 'VUS') — the frontend renders badges "
    "automatically."
)

_QUESTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p)
    for p in [
        r"\?",
        r"^\s*(hi|hello|hey)\s*[!.。！]?\s*$",
        r"^\s*(你好|您好)\s*[!.。！]?\s*$",
        r"\bwhat\b",
        r"\bwhy\b",
        r"\bhow\b",
        r"\bwhich\b",
        r"\bhelp\b",
        r"\bi\s+(want|need|would like)\b.*\b(extract|extraction|search|query|analyze|analyse|upload)\b",
        r"\b(start|run)\b.*\bpipeline\b",
        r"\b(search|query|lookup)\b.*\b(database|db|evidence)\b",
        r"\b什么\b",
        r"\b为什么\b",
        r"\b如何\b",
        r"我想",
        r"我要",
        r"请帮",
        r"帮我",
        r"文献.*(提取|抽取|分析)",
        r"(证据|信息).*(提取|抽取)",
        r"(查询|检索|搜索|查找).*(数据库|证据库|已有证据|现有证据)",
    ]
]
_CORRECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p)
    for p in [
        r"\bchange\b.*\bto\b",
        r"\bupdate\b.*\bto\b",
        r"\bcorrect\b.*\bto\b",
        r"\b修改\b.*\b为\b",
        r"\b改为\b",
    ]
]


class ChatService:
    """Manage chat sessions and messages for evidence review."""

    def __init__(
        self,
        session: AsyncSession,
        chat_provider: ChatLLMProvider | None = None,
    ):
        self._session = session
        self._chat_provider = chat_provider

    async def create_session(
        self,
        *,
        processing_run_id: UUID | None,
        user_id: UUID | None = None,
    ) -> ChatSessionResponse:
        """Create a new chat session, optionally bound to a processing run."""
        session = ChatSession(
            processing_run_id=processing_run_id,
            user_id=user_id,
        )
        self._session.add(session)
        await self._session.flush()

        return ChatSessionResponse(
            chat_session_id=session.chat_session_id,
            processing_run_id=session.processing_run_id,
            user_id=session.user_id,
            title=session.title,
            created_at=session.created_at,
            message_count=0,
        )

    async def _require_session(
        self,
        *,
        session_id: UUID,
        owner_user_id: UUID | None = None,
    ) -> ChatSession:
        """Fetch a chat session or raise NotFoundException if it doesn't exist."""
        owner_filter = ChatSession.user_id.is_(None) if owner_user_id is None else ChatSession.user_id == owner_user_id
        result = await self._session.execute(
            select(ChatSession).where(
                ChatSession.chat_session_id == session_id,
                owner_filter,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise NotFoundException("ChatSession", str(session_id))
        return session

    async def get_session(
        self,
        *,
        session_id: UUID,
        owner_user_id: UUID | None = None,
    ) -> ChatSessionResponse:
        """Fetch one chat session with its message count."""
        session = await self._require_session(session_id=session_id, owner_user_id=owner_user_id)
        count_stmt = (
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.chat_session_id == session_id)
        )
        count_result = await self._session.execute(count_stmt)
        message_count = int(count_result.scalar_one())
        return ChatSessionResponse(
            chat_session_id=session.chat_session_id,
            processing_run_id=session.processing_run_id,
            user_id=session.user_id,
            title=session.title,
            created_at=session.created_at,
            message_count=message_count,
        )

    async def append_message(
        self,
        *,
        session_id: UUID,
        role: str,
        content: str,
        evidence_id: UUID | None = None,
        entity_id: UUID | None = None,
        action: ChatAction | None = None,
        owner_user_id: UUID | None = None,
    ) -> ChatMessageResponse:
        """Append a message to a chat session."""
        await self._require_session(session_id=session_id, owner_user_id=owner_user_id)
        message = ChatMessage(
            chat_session_id=session_id,
            role=role,
            content=content,
            evidence_id=evidence_id,
            entity_id=entity_id,
            action=action.model_dump(mode="json") if action else None,
        )
        self._session.add(message)
        await self._session.flush()

        return self._to_message_response(message)

    async def generate_session_title(
        self,
        *,
        session_id: UUID,
        user_message: str,
    ) -> None:
        """Generate a title for a session that does not already have one."""
        chat_session = await self._require_session(session_id=session_id)
        if chat_session.title:
            return

        await self._maybe_generate_session_title(
            session=chat_session,
            user_message=user_message,
        )

    async def list_messages(
        self,
        *,
        session_id: UUID,
        limit: int = 100,
        owner_user_id: UUID | None = None,
    ) -> list[ChatMessageResponse]:
        """List messages in a session, ordered chronologically."""
        await self._require_session(session_id=session_id, owner_user_id=owner_user_id)
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        messages = result.scalars().all()

        return [self._to_message_response(msg) for msg in messages]

    async def list_sessions(
        self,
        *,
        processing_run_id: UUID,
        owner_user_id: UUID | None = None,
    ) -> list[ChatSessionResponse]:
        """List all chat sessions for a processing run."""
        owner_filter = ChatSession.user_id.is_(None) if owner_user_id is None else ChatSession.user_id == owner_user_id
        count_subq = (
            select(
                ChatMessage.chat_session_id,
                func.count().label("msg_count"),
            )
            .group_by(ChatMessage.chat_session_id)
            .subquery()
        )

        stmt = (
            select(ChatSession, func.coalesce(count_subq.c.msg_count, 0))
            .outerjoin(
                count_subq,
                ChatSession.chat_session_id == count_subq.c.chat_session_id,
            )
            .where(ChatSession.processing_run_id == processing_run_id)
            .where(owner_filter)
            .order_by(ChatSession.created_at.desc())
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        return [
            ChatSessionResponse(
                chat_session_id=session.chat_session_id,
                processing_run_id=session.processing_run_id,
                user_id=session.user_id,
                title=session.title,
                created_at=session.created_at,
                message_count=msg_count,
            )
            for session, msg_count in rows
        ]

    async def _maybe_generate_session_title(
        self,
        *,
        session: ChatSession,
        user_message: str,
    ) -> None:
        """Generate and persist an LLM title without blocking chat on failure."""
        provider = self._chat_provider
        if provider is None:
            logger.warning(
                "ChatService session title generation skipped without injected provider. "
                "Fix: inject via Phase4ServiceFactory.create_chat_service()"
            )
            return

        try:
            raw_title = await provider.generate(
                system_prompt=_SESSION_TITLE_SYSTEM_PROMPT,
                user_message=user_message[:1000],
            )
        except Exception as exc:
            logger.warning("Chat session title generation failed: {}", exc)
            return

        title = self._clean_session_title(raw_title)
        if not title:
            return

        session.title = title
        await self._session.flush()

    @staticmethod
    def _clean_session_title(raw_title: str) -> str:
        """Normalize an LLM-generated session title for sidebar display."""
        title = raw_title.strip()
        title = re.sub(r"^#+\s*", "", title)
        title = re.sub(r"^(title|标题)\s*[:：]\s*", "", title, flags=re.IGNORECASE)
        title = title.strip(" \t\r\n\"'`“”‘’。.!！")
        title = re.sub(r"\s+", " ", title)
        if len(title) > _SESSION_TITLE_MAX_CHARS:
            title = title[:_SESSION_TITLE_MAX_CHARS].rstrip()
        return title

    @staticmethod
    def _to_message_response(message: ChatMessage) -> ChatMessageResponse:
        """Convert a ChatMessage ORM row to a validated API response."""
        action: ChatAction | None = None
        if message.action:
            try:
                action = ChatAction.model_validate(message.action)
            except Exception as exc:
                logger.warning("Stored chat action failed validation: {}", exc)
                action = None

        return ChatMessageResponse(
            message_id=message.message_id,
            chat_session_id=message.chat_session_id,
            role=message.role,
            content=message.content,
            evidence_id=message.evidence_id,
            entity_id=message.entity_id,
            action=action,
            created_at=message.created_at,
        )

    async def _build_evidence_context(
        self,
        *,
        canonical_evidence_id: UUID,
        owner_user_id: UUID | None = None,
    ) -> str:
        """Build evidence context block for LLM (~4000 tokens).

        Includes:
        - Current evidence card (active_payload)
        - Associated entities (via bindings)
        - Source span snippet
        """
        owner_filter = (
            CanonicalEvidenceItem.owner_user_id.is_(None)
            if owner_user_id is None
            else CanonicalEvidenceItem.owner_user_id == owner_user_id
        )
        stmt = select(CanonicalEvidenceItem).where(
            CanonicalEvidenceItem.canonical_evidence_id == canonical_evidence_id,
            owner_filter,
        )
        result = await self._session.execute(stmt)
        evidence = result.scalar_one_or_none()

        if evidence is None:
            logger.warning(
                "Chat evidence context requested for missing canonical evidence: {}",
                canonical_evidence_id,
            )
            return ""

        payload = evidence.active_payload or {}
        best_run_id = evidence.current_best_run_evidence_id

        card = EvidenceCardPayload.from_field_payload(
            field_id=evidence.field_id,
            payload=payload,
        )
        context_parts = [
            "**Evidence Card**",
            f"Gene: {card.gene or 'N/A'}",
            f"Variant: {card.variant or 'N/A'}",
            f"Phenotype: {card.phenotype or 'N/A'}",
            f"Disease: {card.disease or 'N/A'}",
            f"Classification: {card.classification or 'N/A'}",
            f"Evidence Strength: {card.evidence_strength or 'N/A'}",
            f"Summary: {card.summary or 'N/A'}",
        ]

        if best_run_id:
            # Entity bindings via current_best_run_evidence_id
            stmt = (
                select(NormalizedEntity)
                .join(
                    EvidenceEntityBinding,
                    EvidenceEntityBinding.entity_id == NormalizedEntity.entity_id,
                )
                .where(
                    EvidenceEntityBinding.run_evidence_item_id == best_run_id,
                )
            )
            result = await self._session.execute(stmt)
            entities = result.scalars().all()

            if entities:
                context_parts.append("\n**Associated Entities**")
                for entity in entities[:5]:
                    context_parts.append(f"- {entity.entity_type}: {entity.display_name} ({entity.external_id})")

            # Source snippet from the best run item
            stmt = select(RunEvidenceItem).where(
                RunEvidenceItem.run_evidence_item_id == best_run_id,
                RunEvidenceItem.owner_user_id.is_(None)
                if owner_user_id is None
                else RunEvidenceItem.owner_user_id == owner_user_id,
            )
            result = await self._session.execute(stmt)
            run_item = result.scalar_one_or_none()

            if run_item and run_item.source_span:
                snippet = run_item.source_span.get("text_snippet", "")[:300]
                if snippet:
                    context_parts.append(f"\n**Source Text**\n{snippet}")

        return "\n".join(context_parts)

    _CORRECTION_FIELD_ALIASES: dict[str, str] = {
        "gene": "gene",
        "基因": "gene",
        "variant": "variant",
        "变异": "variant",
        "突变": "variant",
        "disease": "disease",
        "疾病": "disease",
        "classification": "classification",
        "分类": "classification",
        "phenotype": "phenotype",
        "表型": "phenotype",
        "evidence_strength": "evidence_strength",
        "evidence_type": "evidence_type",
        "functional_impact": "functional_impact",
        "inheritance_pattern": "inheritance_pattern",
        "zygosity": "zygosity",
        "summary": "summary",
        "摘要": "summary",
        "references": "references",
    }

    _CORRECTION_PATTERNS_PARSE: list[re.Pattern[str]] = [
        re.compile(
            r"(?:change|update|correct|set|modify)\s+"
            r"(?P<field>[a-z_\u4e00-\u9fff]+)\s+"
            r"(?:to|as|=)\s+"
            r"(?P<value>.+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:把|将)?\s*"
            r"(?P<field>[a-z_\u4e00-\u9fff]+)\s*"
            r"(?:改为|修改为|改成|设为|更新为)\s*"
            r"(?P<value>.+)",
        ),
    ]

    @classmethod
    def _parse_correction_message(cls, message: str) -> dict[str, str]:
        """Parse a correction message into {card_field: new_value}.

        Returns empty dict if no field/value pair could be extracted.
        """
        for pattern in cls._CORRECTION_PATTERNS_PARSE:
            match = pattern.search(message)
            if match:
                raw_field = match.group("field").strip().lower()
                value = match.group("value").strip().rstrip(".,;。；")
                card_field = cls._CORRECTION_FIELD_ALIASES.get(raw_field)
                if card_field and value:
                    return {card_field: value}
        return {}

    async def _apply_correction(
        self,
        *,
        evidence_id: UUID,
        user_message: str,
        reviewer_id: UUID | None = None,
        owner_user_id: UUID | None = None,
    ) -> str:
        """Parse the user message and apply correction via FeedbackService."""
        from src.core.visualize_evidence_with_expert_in_loop.feedback_service import (
            FeedbackService,
        )
        from src.core.visualize_evidence_with_expert_in_loop.contracts import (
            EvidencePatchRequest,
        )

        fields = self._parse_correction_message(user_message)
        if not fields:
            return (
                "I couldn't parse a field correction from your message. "
                'Try: "change gene to BRCA2" or "把分类改为 pathogenic". '
                "You can also use the Edit button on the evidence detail page."
            )

        patch = EvidencePatchRequest(
            fields=fields,
            change_reason=f"Chat correction: {user_message[:200]}",
        )

        try:
            service = FeedbackService(self._session)
            result = await service.patch_evidence(
                canonical_evidence_id=evidence_id,
                patch=patch,
                reviewer_id=reviewer_id,
                owner_user_id=owner_user_id,
            )
            await self._session.commit()
        except Exception as exc:
            logger.warning("Chat correction failed: {}", exc)
            return f"Correction failed: {exc}"

        delta_parts = [f"**{d.field}**: ~~{d.old_value}~~ → {d.new_value}" for d in result.field_deltas]
        summary = "\n".join(delta_parts) if delta_parts else "Status updated."
        return (
            f"Correction applied to evidence `{str(evidence_id)[:8]}…`.\n\n"
            f"{summary}\n\n"
            f"Status: {result.old_status.value} → {result.new_status.value}"
        )

    def _detect_intent(self, message: str) -> str:
        """Detect user intent: question, correction, or note.

        Priority: question > correction > note.
        Ambiguous messages (e.g. "change X to Y?") default to question
        as the less destructive intent.

        Returns:
            "question" | "correction" | "note"
        """
        msg_lower = message.lower()

        # Check question patterns first to avoid false positives on
        # messages like "What should I change?" which contain "change"
        if any(p.search(msg_lower) for p in _QUESTION_PATTERNS):
            return "question"

        if any(p.search(msg_lower) for p in _CORRECTION_PATTERNS):
            return "correction"

        return "question"

    def _system_prompt(self, *, has_evidence_context: bool) -> str:
        """Build the chat system prompt for evidence-bound or standalone chat."""
        if has_evidence_context:
            return (
                "You are a clinical genetics assistant inside Lingua Seeker. Answer "
                "questions about evidence cards using the provided context. Be "
                "precise and cite specific fields from the evidence card. "
                "Reply in plain text and Markdown only — NEVER use HTML tags. "
                "For classification labels, write them as plain text (e.g. "
                "'Pathogenic', 'VUS')."
            )

        return CHAT_AGENT_CAPABILITIES_PROMPT

    async def generate_reply(
        self,
        *,
        session_id: UUID,
        user_message: str,
        evidence_id: UUID | None = None,
        owner_user_id: UUID | None = None,
        reviewer_id: UUID | None = None,
    ) -> str | None:
        """Generate AI reply based on intent and evidence context.

        Returns:
            Reply text for questions/corrections, None for notes.
        """
        await self._require_session(session_id=session_id, owner_user_id=owner_user_id)
        intent = self._detect_intent(user_message)

        if intent == "note":
            return None

        if intent == "correction" and evidence_id:
            result = await self._apply_correction(
                evidence_id=evidence_id,
                user_message=user_message,
                reviewer_id=reviewer_id,
                owner_user_id=owner_user_id,
            )
            return result

        context = ""
        if evidence_id:
            context = await self._build_evidence_context(
                canonical_evidence_id=evidence_id,
                owner_user_id=owner_user_id,
            )

        system_prompt = self._system_prompt(has_evidence_context=bool(context))

        provider = self._chat_provider
        if provider is None:
            logger.warning(
                "ChatService.generate_reply called without injected provider — "
                "creating fallback (leaked httpx client). "
                "Fix: inject via Phase4ServiceFactory.create_chat_service()"
            )
            from src.core.visualize_evidence_with_expert_in_loop.providers import (
                ChatLLMProvider,
            )

            provider = ChatLLMProvider()

        reply = await provider.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            context=context,
        )

        return reply

    async def stream_reply(
        self,
        *,
        session_id: UUID,
        user_message: str,
        evidence_id: UUID | None = None,
        owner_user_id: UUID | None = None,
        reviewer_id: UUID | None = None,
    ):
        """Stream AI reply as SSE events.

        Yields:
            {"type": "text", "content": "..."} for each chunk
            {"type": "action", "intent": ..., "slots": {...}} when the agent dispatches
            {"type": "done"} on completion
            {"type": "error", "message": "..."} on failure
        """
        await self._require_session(session_id=session_id, owner_user_id=owner_user_id)
        intent = self._detect_intent(user_message)

        if intent == "correction" and evidence_id:
            result = await self._apply_correction(
                evidence_id=evidence_id,
                user_message=user_message,
                reviewer_id=reviewer_id,
                owner_user_id=owner_user_id,
            )
            yield {"type": "text", "content": result}
            yield {"type": "done"}
            return

        context = ""
        if evidence_id:
            context = await self._build_evidence_context(
                canonical_evidence_id=evidence_id,
                owner_user_id=owner_user_id,
            )

        system_prompt = self._system_prompt(has_evidence_context=bool(context))

        provider = self._chat_provider
        if provider is None:
            logger.warning(
                "ChatService.stream_reply called without injected provider — "
                "creating fallback (leaked httpx client). "
                "Fix: inject via Phase4ServiceFactory.create_chat_service()"
            )
            from src.core.visualize_evidence_with_expert_in_loop.providers import (
                ChatLLMProvider,
            )

            provider = ChatLLMProvider()

        if not context:
            async for event in self._stream_router_envelope(
                provider=provider,
                session_id=session_id,
                system_prompt=system_prompt,
                user_message=user_message,
                owner_user_id=owner_user_id,
            ):
                yield event
            return

        buffered: list[str] = []
        try:
            async for event in self._stream_with_keepalive(
                provider.stream(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    context=context,
                ),
            ):
                if event is _KEEPALIVE:
                    yield {"type": "keepalive"}
                else:
                    buffered.append(event)
                    yield {"type": "text", "content": event}
            yield {"type": "done"}
        except Exception as e:
            yield {"type": "error", "message": str(e)}
            return

        complete_reply = "".join(buffered)
        if complete_reply:
            await self.append_message(
                session_id=session_id,
                role="assistant",
                content=complete_reply,
                evidence_id=evidence_id,
                owner_user_id=owner_user_id,
            )

    async def _stream_router_envelope(
        self,
        *,
        provider: ChatLLMProvider,
        session_id: UUID,
        system_prompt: str,
        user_message: str,
        owner_user_id: UUID | None = None,
    ):
        history = await self._load_router_history(
            session_id=session_id,
            exclude_latest_user_message=user_message,
        )

        reply: str = ""
        action: ChatAction | None = None
        try:
            async for item in provider.route_intent_stream(
                system_prompt=system_prompt,
                user_message=user_message,
                history=history,
            ):
                if item is _KEEPALIVE:
                    yield {"type": "keepalive"}
                elif isinstance(item, tuple):
                    # Final (reply_tail, action) tuple from the provider.
                    # reply_tail is text after the delimiter (usually empty).
                    tail, action = item
                    if tail:
                        reply += tail
                        yield {"type": "text", "content": tail}
                elif isinstance(item, str) and item:
                    # Incremental text chunk — forward immediately.
                    reply += item
                    yield {"type": "text", "content": item}
        except Exception as e:
            yield {"type": "error", "message": str(e)}
            return

        if action is not None:
            yield {
                "type": "action",
                "intent": action.intent,
                "slots": action.slots,
            }

        yield {"type": "done"}

        if reply or action is not None:
            await self.append_message(
                session_id=session_id,
                role="assistant",
                content=reply or "",
                action=action,
                owner_user_id=owner_user_id,
            )

    @staticmethod
    async def _stream_with_keepalive(source):
        """Wrap an async iterator, yielding keepalive sentinels on stalls.

        If no item arrives from *source* within ``_KEEPALIVE_INTERVAL``
        seconds, yields ``_KEEPALIVE`` so the caller can emit an SSE
        heartbeat and keep the client connection open.
        """
        import asyncio

        ait = source.__aiter__()
        try:
            while True:
                try:
                    item = await asyncio.wait_for(ait.__anext__(), _KEEPALIVE_INTERVAL)
                    yield item
                except StopAsyncIteration:
                    break
                except TimeoutError:
                    yield _KEEPALIVE
        finally:
            await ait.aclose()

    async def _load_router_history(
        self,
        *,
        session_id: UUID,
        limit: int = 10,
        exclude_latest_user_message: str | None = None,
    ) -> list[dict[str, str]]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()
        history = [{"role": m.role, "content": m.content} for m in rows if m.content]
        if (
            exclude_latest_user_message
            and history
            and history[-1]["role"] == "user"
            and history[-1]["content"].strip() == exclude_latest_user_message.strip()
        ):
            history.pop()
        return history
