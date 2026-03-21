from typing import List, Dict, Any, Optional, Mapping, cast
import asyncio
import base64
import json
import re
from pathlib import Path
from loguru import logger
from src.domain.enums import ProcessingState
from src.domain.models import (
    EvidenceOutput,
    EvidenceStrengthClassification,
    ExtractedEvidenceFields,
)
from src.domain.agent import prompts
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from pydantic import SecretStr
from src.domain.evidence.tools import (
    search_knowledge_base,
    get_evidence_tools,
    get_evidence_tool_map,
)
from src.utils.timer import timer
from src.utils.evidence_annotation import enrich_evidence_json
from src.config import Settings, get_settings, resolve_llm_triplet
from .rag import RAGComponent


class EvidenceAgent:
    """医学证据处理 Agent"""

    def __init__(
        self,
        cfg: Optional[Settings] = None,
        rag_component: Optional[RAGComponent] = None,
    ):
        self.cfg = cfg or get_settings()
        self.rag = rag_component or RAGComponent()
        logger.info("EvidenceAgent initialized")

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            logger.debug("Token estimate requested for empty text")
            return 0
        ascii_chars = sum(1 for ch in text if ch.isascii())
        non_ascii_chars = len(text) - ascii_chars
        estimated = int(ascii_chars / 4 + non_ascii_chars)
        logger.debug("Estimated tokens: {}", estimated)
        return estimated

    def _split_paragraph(
        self,
        paragraph: str,
        max_tokens: int = 8192,
        max_chars: Optional[int] = None,
    ) -> List[str]:
        def fits(text: str) -> bool:
            if self._estimate_tokens(text) > max_tokens:
                return False
            if max_chars is not None and len(text) > max_chars:
                return False
            return True

        if fits(paragraph):
            logger.debug("Paragraph fits in a single chunk")
            return [paragraph]

        sentences = [
            s for s in re.split(r"(?<=[。！？.!?])\s+", paragraph.strip()) if s
        ]
        chunks: List[str] = []
        current = ""
        for sentence in sentences:
            candidate = f"{current} {sentence}".strip() if current else sentence
            if fits(candidate):
                current = candidate
                continue

            if current:
                chunks.append(current)
                current = ""

            if fits(sentence):
                current = sentence
                continue

            start = 0
            chunk_size = max_chars if max_chars is not None else max_tokens * 4
            chunk_size = max(1, chunk_size)
            while start < len(sentence):
                end = min(len(sentence), start + chunk_size)
                chunks.append(sentence[start:end].strip())
                start = end

        if current:
            chunks.append(current)
        logger.debug("Paragraph split into {} chunk(s)", len(chunks))
        return chunks

    def _segment_text_for_translation(
        self,
        text: str,
        max_tokens: int = 8192,
        max_chars: Optional[int] = None,
    ) -> List[str]:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        paragraph_units: List[str] = []
        for paragraph in paragraphs:
            paragraph_units.extend(
                self._split_paragraph(paragraph, max_tokens, max_chars)
            )

        segments: List[str] = []
        current = ""
        for unit in paragraph_units:
            candidate = unit if not current else f"{current}\n\n{unit}"
            if self._estimate_tokens(candidate) <= max_tokens and (
                max_chars is None or len(candidate) <= max_chars
            ):
                current = candidate
                continue

            if current:
                segments.append(current)
            current = unit

        if current:
            segments.append(current)
        logger.debug("Segmented text into {} segment(s)", len(segments))
        return segments

    def _get_default_rag_queries(self) -> List[str]:
        return [
            "PS3 BS3 functional evidence assessment criteria",
            "ACMG variant interpretation guidelines functional assays",
            "OddsPath calculation pathogenic benign variants",
        ]

    async def _retrieve_knowledge_context(self, search_queries: List[str]) -> str:
        retrieved_docs = []
        try:
            qdrant_manager = self.rag.get_qdrant_manager()
            embedding_client = self.rag.get_embedding_client()

            for query in search_queries:
                query_vector = embedding_client.embed_query(query)

                search_response = await qdrant_manager.search(
                    query_vector=query_vector,
                    top_k=3,
                    score_threshold=qdrant_manager.score_threshold,
                )

                for result in search_response.results:
                    payload = result.payload or {}
                    retrieved_docs.append(
                        {
                            "content": payload.get("content", ""),
                            "file_path": payload.get("file_path", ""),
                            "score": result.score,
                            "source": "rag",
                        }
                    )
        except Exception as e:
            logger.error(f"知识库检索失败: {e}")
            raise RuntimeError("知识库检索失败") from e

        for query in search_queries:
            try:
                tool_results = await search_knowledge_base.ainvoke(
                    {
                        "query": query,
                        "top_k": 3,
                    }
                )
            except Exception as e:
                logger.error(f"工具检索失败 '{query}': {e}")
                raise RuntimeError("工具检索失败") from e

            for result in tool_results:
                retrieved_docs.append(
                    {
                        "content": result.get("content", ""),
                        "file_path": result.get("file_path", ""),
                        "score": result.get("score", 0),
                        "source": "tool",
                    }
                )

        seen_content = set()
        unique_docs = []
        for doc in sorted(retrieved_docs, key=lambda x: x["score"], reverse=True):
            content_hash = hash(doc["content"][:200])
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_docs.append(doc)

        top_docs = unique_docs[:5]

        knowledge_context = (
            "\n\n".join(
                [
                    f"[参考文档 {i + 1}] (相似度: {doc['score']:.3f})\n{doc['content'][:1000]}..."
                    for i, doc in enumerate(top_docs)
                ]
            )
            if top_docs
            else "未检索到相关知识库文档"
        )

        logger.info(f"知识库检索完成，获取 {len(top_docs)} 个相关文档")
        return knowledge_context

    def _retrieve_knowledge_context_sync(self, search_queries: List[str]) -> str:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._retrieve_knowledge_context(search_queries))
        raise RuntimeError(
            "_retrieve_knowledge_context_sync cannot run inside a running event loop"
        )

    # ==================== LLM 客户端配置 ====================
    def get_translation_llm(self):
        """获取翻译 LLM 客户端"""
        logger.info("Initializing translation LLM")
        llm_config = resolve_llm_triplet(self.cfg, "mt")
        return ChatOpenAI(
            model=llm_config.model,
            api_key=SecretStr(llm_config.api_key),
            base_url=llm_config.base_url,
            temperature=0.0,
        )

    def get_format_llm(self):
        """获取排版 LLM 客户端"""
        logger.info("Initializing format LLM")
        llm_config = resolve_llm_triplet(self.cfg, "format")
        return ChatOpenAI(
            model=llm_config.model,
            api_key=SecretStr(llm_config.api_key),
            base_url=llm_config.base_url,
            temperature=0.0,
        )

    def get_vlm(self):
        """获取支持视觉的 LLM 客户端"""
        logger.info("Initializing VLM")
        llm_config = resolve_llm_triplet(self.cfg, "vlm")
        return ChatOpenAI(
            model=llm_config.model,
            api_key=SecretStr(llm_config.api_key),
            base_url=llm_config.base_url,
            temperature=0.0,
        )

    def get_evidence_llm(self):
        """获取证据提取 LLM 客户端（支持工具调用）"""
        logger.info("Initializing evidence LLM")
        llm_config = resolve_llm_triplet(self.cfg, "evidence")
        llm = ChatOpenAI(
            model=llm_config.model,
            api_key=SecretStr(llm_config.api_key),
            base_url=llm_config.base_url,
            temperature=0.0,
            timeout=self.cfg.llm_timeout,
            streaming=True,
        )
        return llm.bind_tools(get_evidence_tools())

    def get_arbitration_llm(self):
        """获取仲裁 LLM 客户端"""
        logger.info("Initializing arbitration LLM")
        llm_config = resolve_llm_triplet(self.cfg, "arbitration")
        return ChatOpenAI(
            model=llm_config.model,
            api_key=SecretStr(llm_config.api_key),
            base_url=llm_config.base_url,
            temperature=0.0,
            timeout=self.cfg.llm_timeout,
            streaming=True,
        )

    def _invoke_with_tools(
        self,
        llm: Any,
        messages: List[Any],
        max_rounds: int = 4,
    ):
        tool_map = get_evidence_tool_map()
        current_messages: List[Any] = list(messages)
        logger.debug("Invoking LLM with {} message(s)", len(current_messages))
        response = llm.invoke(current_messages)

        for _ in range(max_rounds):
            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                break

            logger.debug("Processing {} tool call(s)", len(tool_calls))

            current_messages.append(response)
            tool_messages: List[ToolMessage] = []
            for call in tool_calls:
                if isinstance(call, dict):
                    call_dict = cast(Dict[str, Any], call)
                    tool_name_candidate = call_dict.get("name")
                    tool_args = call_dict.get("args")
                    tool_call_id = call_dict.get("id")
                else:
                    tool_name_candidate = getattr(call, "name", None)
                    tool_args = getattr(call, "args", None)
                    tool_call_id = getattr(call, "id", None)

                tool_name = (
                    tool_name_candidate if isinstance(tool_name_candidate, str) else ""
                )

                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError:
                        tool_args = {}

                tool_impl = tool_map.get(tool_name) if tool_name else None
                if tool_impl is None:
                    result_payload = {"error": f"Unknown tool: {tool_name}"}
                else:
                    result_payload = tool_impl.invoke(tool_args or {})

                tool_messages.append(
                    ToolMessage(
                        content=json.dumps(result_payload, ensure_ascii=False),
                        tool_call_id=tool_call_id or "unknown",
                    )
                )

            current_messages.extend(tool_messages)
            response = llm.invoke(current_messages)

        return response

    def _message_content_to_text(self, content: Any) -> str:
        """Normalize LangChain message content into plain text."""
        if content is None:
            return ""

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, bytes):
            try:
                return content.decode("utf-8").strip()
            except Exception:
                return ""

        if isinstance(content, list):
            parts = [
                text
                for item in content
                if (text := self._message_content_to_text(item))
            ]
            return "\n".join(parts).strip()

        if isinstance(content, dict):
            if content.get("type") == "text" and "text" in content:
                return self._message_content_to_text(content["text"])

            parts = []
            for key in ("text", "content", "result", "message"):
                if key in content:
                    text = self._message_content_to_text(content[key])
                    if text:
                        parts.append(text)
            return "\n".join(parts).strip()

        for attr in ("text", "content", "result", "message"):
            value = getattr(content, attr, None)
            if value is not None:
                text = self._message_content_to_text(value)
                if text:
                    return text

        return str(content).strip()

    def _collect_json_object_candidates(self, content: str) -> List[str]:
        candidates: List[str] = []
        seen: set[str] = set()

        def push(candidate: str) -> None:
            normalized = candidate.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                candidates.append(normalized)

        text = content.strip()
        push(text)

        for match in re.finditer(
            r"```(?:json)?\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL
        ):
            push(match.group(1))

        brace_stack = 0
        start_idx: Optional[int] = None
        in_string = False
        escaped = False
        for index, char in enumerate(text):
            if in_string:
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                    continue
                if char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
                continue

            if char == "{":
                if brace_stack == 0:
                    start_idx = index
                brace_stack += 1
                continue

            if char == "}" and brace_stack > 0:
                brace_stack -= 1
                if brace_stack == 0 and start_idx is not None:
                    push(text[start_idx : index + 1])
                    start_idx = None

        greedy = re.search(r"\{.*\}", text, re.DOTALL)
        if greedy:
            push(greedy.group())

        return candidates

    def _try_parse_json_dict(self, candidate: str) -> Optional[Dict[str, Any]]:
        normalized = candidate.strip()
        variants = [normalized]

        trailing_comma_fixed = re.sub(r",\s*([}\]])", r"\1", normalized)
        if trailing_comma_fixed != normalized:
            variants.append(trailing_comma_fixed)

        decoder = json.JSONDecoder()
        for variant in variants:
            try:
                parsed = json.loads(variant)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                for index, char in enumerate(variant):
                    if char != "{":
                        continue
                    try:
                        parsed_obj, _ = decoder.raw_decode(variant[index:])
                    except json.JSONDecodeError:
                        continue
                    if isinstance(parsed_obj, dict):
                        return parsed_obj

        return None

    def _extract_json_payload(self, content: str) -> Dict[str, Any]:
        if not content:
            raise RuntimeError("LLM 响应为空，无法解析 JSON")

        parse_errors: List[str] = []
        for candidate in self._collect_json_object_candidates(content):
            parsed = self._try_parse_json_dict(candidate)
            if parsed is not None:
                return parsed

            try:
                json.loads(candidate)
            except json.JSONDecodeError as exc:
                parse_errors.append(f"line {exc.lineno}, col {exc.colno}: {exc.msg}")

        if parse_errors:
            raise RuntimeError(f"无法从响应中提取有效 JSON（{parse_errors[-1]}）")

        raise RuntimeError("无法从响应中提取 JSON")

    def get_json_repair_llm(self):
        """获取 JSON 修复 LLM 客户端（不启用工具调用）"""
        logger.info("Initializing JSON repair LLM")
        llm_config = resolve_llm_triplet(self.cfg, "evidence")
        return ChatOpenAI(
            model=llm_config.model,
            api_key=SecretStr(llm_config.api_key),
            base_url=llm_config.base_url,
            temperature=0.0,
            timeout=self.cfg.llm_timeout,
            streaming=False,
        )

    def _parse_json_payload_with_repair(
        self, content: str, stage_name: str
    ) -> Dict[str, Any]:
        try:
            return self._extract_json_payload(content)
        except RuntimeError as parse_exc:
            snippet = content[:1200]
            logger.warning(
                "{} JSON parse failed, attempting repair fallback: {} | content_len={} | snippet={}...",
                stage_name,
                parse_exc,
                len(content),
                snippet,
            )

        repair_prompt = (
            "You are a strict JSON repair engine.\n"
            "Fix the malformed JSON-like content below and return exactly one valid JSON object.\n"
            "Rules:\n"
            "1) Return JSON only, no markdown/code fences/explanations.\n"
            "2) Keep original keys and values whenever possible.\n"
            "3) Keep numeric/boolean/null types unchanged whenever possible.\n"
            "4) If malformed punctuation exists (missing commas, trailing commas, quote issues), minimally repair it.\n"
            "\n"
            "Input content:\n"
            f"{content}"
        )

        try:
            repair_llm = self.get_json_repair_llm()
            repair_response = repair_llm.invoke([HumanMessage(content=repair_prompt)])
            repaired_content = self._message_content_to_text(repair_response.content)
            repaired_payload = self._extract_json_payload(repaired_content)
            logger.info("{} JSON repair fallback succeeded", stage_name)
            return repaired_payload
        except Exception as repair_exc:
            logger.error("{} JSON repair fallback failed: {}", stage_name, repair_exc)
            raise RuntimeError(f"{stage_name} JSON 解析失败") from repair_exc

    @staticmethod
    def _coerce_optional_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    @staticmethod
    def _normalize_optional_string(value: Any) -> Optional[str]:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return None

    def _extract_output_contract_fields(
        self,
        state: Mapping[str, Any],
        final_strength: Optional[str],
    ) -> Dict[str, Any]:
        ps3_evidence = state.get("ps3_evidence", {})
        if not isinstance(ps3_evidence, dict):
            ps3_evidence = {}

        extracted_fields = state.get("extracted_fields")
        if not isinstance(extracted_fields, dict):
            extracted_fields = {}

        nested_extracted = ps3_evidence.get("extracted_fields")
        if not extracted_fields and isinstance(nested_extracted, dict):
            extracted_fields = nested_extracted

        evidence_quality = ps3_evidence.get("evidence_quality")
        quality_payload = evidence_quality if isinstance(evidence_quality, dict) else {}

        raw_quality_scores = quality_payload.get("field_confidence_scores")
        field_confidence_scores = (
            raw_quality_scores if isinstance(raw_quality_scores, dict) else {}
        )

        derived_confidence: Optional[float] = None
        if extracted_fields:
            try:
                normalized_fields = ExtractedEvidenceFields(**extracted_fields)
                derived_scores = normalized_fields.compute_field_confidence_scores()
                if not field_confidence_scores:
                    field_confidence_scores = derived_scores
                derived_confidence = normalized_fields.compute_overall_confidence()
            except Exception as exc:
                logger.warning(
                    "Failed to derive confidence from extracted_fields: {}", exc
                )

        overall_confidence = self._coerce_optional_float(
            quality_payload.get("overall_confidence")
        )
        if overall_confidence is None and derived_confidence is not None:
            overall_confidence = round(derived_confidence, 2)
        if overall_confidence is None:
            overall_confidence = 0.0

        evidence_classification = (
            self._normalize_optional_string(
                quality_payload.get("evidence_classification")
            )
            or ""
        )

        raw_acmg_levels = quality_payload.get("acmg_evidence_levels")
        acmg_evidence_levels: List[str] = []
        if isinstance(raw_acmg_levels, list):
            acmg_evidence_levels = [
                level.strip()
                for level in raw_acmg_levels
                if isinstance(level, str) and level.strip()
            ]
        if not acmg_evidence_levels:
            acmg_evidence_levels = EvidenceStrengthClassification.determine_acmg_levels(
                {"final_evidence_strength": final_strength or "inconclusive"},
                overall_confidence,
            )

        return {
            "extracted_fields": extracted_fields,
            "field_confidence_scores": field_confidence_scores,
            "overall_confidence": overall_confidence,
            "evidence_classification": evidence_classification,
            "acmg_evidence_levels": acmg_evidence_levels,
        }

    # ==================== 处理步骤函数 ====================
    @timer("步骤1: 翻译")
    def translate_markdown(self, state: ProcessingState) -> ProcessingState:
        """翻译 Markdown 为英文"""
        logger.info("开始翻译 Markdown 为英文...")

        existing_translation = state.get("translated_md", "")
        if isinstance(existing_translation, str) and existing_translation.strip():
            logger.info("检测到已有英文翻译，跳过翻译步骤")
            return state

        llm = self.get_translation_llm()
        markdown_content = state.get("markdown_content", "")
        if not markdown_content.strip():
            logger.warning("Markdown 内容为空，跳过翻译")
            state["translated_md"] = ""
            return state
        max_tokens = 8192
        prompt_overhead = len(prompts.get_translation_prompt(""))
        max_chars = max(1, max_tokens - prompt_overhead - 20)
        segments = self._segment_text_for_translation(
            markdown_content,
            max_tokens=max_tokens,
            max_chars=max_chars,
        )

        translated_segments: List[str] = []
        for idx, segment in enumerate(segments, start=1):
            prompt = prompts.get_translation_prompt(segment)
            try:
                response = llm.invoke([HumanMessage(content=prompt)])
                content = self._message_content_to_text(response.content)
                translated_segments.append(content)
                logger.info(
                    f"翻译分段 {idx}/{len(segments)} 完成，字数: {len(content)}"
                )
            except Exception as e:
                logger.error(f"翻译分段 {idx}/{len(segments)} 失败: {e}")
                raise RuntimeError(f"翻译分段 {idx} 失败") from e

        state["translated_md"] = "\n\n".join(translated_segments)
        logger.info(f"翻译完成，字数: {len(state['translated_md'])}")

        return state

    @staticmethod
    def _get_image_media_type(img_path: str) -> str:
        ext = Path(img_path).suffix.lower()
        return {
            ".jpg": "images/jpeg",
            ".jpeg": "images/jpeg",
            ".png": "images/png",
            ".gif": "images/gif",
            ".webp": "images/webp",
        }.get(ext, "images/jpeg")

    @staticmethod
    def _encode_image(img_path: str) -> tuple[str, str]:
        with open(img_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()
        media_type = EvidenceAgent._get_image_media_type(img_path)
        return img_data, media_type

    def _describe_images_batch(
        self, vlm: Any, paths: list[str], start_index: int = 0
    ) -> list[str]:
        content: list[Any] = [
            {
                "type": "text",
                "text": prompts.get_batch_image_description_prompt(len(paths)),
            }
        ]
        batch_image_inputs: list[dict[str, Any]] = []

        for img_path in paths:
            img_data, media_type = self._encode_image(img_path)
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{img_data}"},
                }
            )
            batch_image_inputs.append(
                {"path": img_path, "base64": img_data, "mime_type": media_type}
            )

        response = vlm.invoke([HumanMessage(content=content)])
        raw_text = self._message_content_to_text(response.content)

        descriptions: list[str] = []
        current_desc_lines: list[str] = []
        for line in raw_text.split("\n"):
            stripped = line.strip()
            if stripped.lower().startswith("figure ") and ":" in stripped:
                if current_desc_lines:
                    descriptions.append("\n".join(current_desc_lines).strip())
                current_desc_lines = [stripped.split(":", 1)[1].strip()]
            elif stripped:
                current_desc_lines.append(stripped)
        if current_desc_lines:
            descriptions.append("\n".join(current_desc_lines).strip())

        if len(descriptions) < len(paths):
            descriptions.extend([""] * (len(paths) - len(descriptions)))

        return descriptions[: len(paths)]

    @timer("步骤2: 图片描述")
    def describe_images(self, state: ProcessingState) -> ProcessingState:
        """使用 VLM 生成图片描述"""
        enable_vlm = bool(state.get("enable_vlm", self.cfg.vlm_enable))
        image_paths = state.get("image_paths", [])

        if not enable_vlm:
            logger.info("VLM 功能已禁用，跳过图片描述阶段")
            state["image_descriptions"] = []
            return state

        if not image_paths:
            logger.info("没有可处理的图片，跳过图片描述阶段")
            state["image_descriptions"] = []
            return state

        logger.info(f"开始处理 {len(image_paths)} 张图片...")

        vlm = self.get_vlm()
        max_batch = self.cfg.vlm_max_batch_images
        descriptions: list[str] = []
        image_inputs: list[dict[str, Any]] = []

        for batch_start in range(0, len(image_paths), max_batch):
            batch_paths = image_paths[batch_start : batch_start + max_batch]
            try:
                batch_descs = self._describe_images_batch(
                    vlm, batch_paths, start_index=batch_start
                )
                descriptions.extend(batch_descs)
                for img_path in batch_paths:
                    img_data, media_type = self._encode_image(img_path)
                    image_inputs.append(
                        {"path": img_path, "base64": img_data, "mime_type": media_type}
                    )
                logger.info(
                    f"批量描述完成: 图片 {batch_start + 1}-{batch_start + len(batch_paths)}"
                )
            except Exception:
                logger.warning(
                    f"批量描述失败，回退到逐张处理: 图片 {batch_start + 1}-{batch_start + len(batch_paths)}"
                )
                for idx, img_path in enumerate(batch_paths):
                    try:
                        img_data, media_type = self._encode_image(img_path)
                        prompt = prompts.get_image_description_prompt(
                            batch_start + idx + 1
                        )
                        message = HumanMessage(
                            content=[
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{media_type};base64,{img_data}"
                                    },
                                },
                            ]
                        )
                        response = vlm.invoke([message])
                        descriptions.append(
                            self._message_content_to_text(response.content)
                        )
                        image_inputs.append(
                            {
                                "path": img_path,
                                "base64": img_data,
                                "mime_type": media_type,
                            }
                        )
                        logger.info(f"图片 {batch_start + idx + 1} 描述完成（逐张）")
                    except Exception as e:
                        logger.error(f"处理图片 {img_path} 失败: {e}")
                        raise RuntimeError(f"图片处理失败: {img_path}") from e

        state["image_descriptions"] = descriptions
        state["image_inputs"] = image_inputs
        return state

    @timer("步骤4: 证据提取+RAG")
    async def extract_ps3_evidence(self, state: ProcessingState) -> ProcessingState:
        """使用 LLM + RAG 提取 PS3 证据"""
        logger.info("开始提取 PS3 证据...")

        translated_md = state.get("translated_md", "")
        if not translated_md:
            raise RuntimeError("翻译后的 Markdown 为空，无法提取证据")

        search_queries = self._get_default_rag_queries()
        knowledge_context = await self._retrieve_knowledge_context(search_queries)
        state["knowledge_context"] = knowledge_context

        llm = self.get_evidence_llm()
        prompt = prompts.get_ps3_evidence_extraction_prompt(
            translated_md,
            state.get("image_descriptions", []),
            knowledge_context=knowledge_context,
        )

        try:
            response = self._invoke_with_tools(llm, [HumanMessage(content=prompt)])
        except Exception as e:
            logger.error(f"证据提取 LLM 调用失败: {e}")
            raise RuntimeError("证据提取 LLM 调用失败") from e

        try:
            content = self._message_content_to_text(response.content)
            evidence_json = self._parse_json_payload_with_repair(content, "证据提取")
            state["ps3_evidence"] = evidence_json

            overall = evidence_json.get("overall_assessment", {})
            state["evidence_sources"] = overall.get("key_strengths", [])

            total_score = (
                evidence_json.get("ps3_step_1", {}).get("score", 0)
                + evidence_json.get("ps3_step_2", {}).get("score", 0)
                + evidence_json.get("ps3_step_3", {}).get("score", 0)
                + evidence_json.get("ps3_step_4", {}).get("score", 0)
            )
            evidence_json["calculated_total_score"] = total_score

            logger.info(f"PS3 证据提取完成，总分: {total_score}/100")
            logger.info(
                f"最终证据强度: {evidence_json.get('ps3_step_4', {}).get('final_evidence_strength', 'inconclusive')}"
            )
        except RuntimeError as e:
            logger.error(f"证据提取 JSON 解析失败: {e}")
            raise RuntimeError("证据提取 JSON 解析失败") from e

        return state

    def extract_ps3_evidence_sync(self, state: ProcessingState) -> ProcessingState:
        """同步包装，便于在同步工作流中使用异步证据提取"""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.extract_ps3_evidence(state))
        raise RuntimeError(
            "extract_ps3_evidence_sync cannot run inside a running event loop"
        )

    def _apply_arbitration_feedback(self, state: ProcessingState) -> None:
        arbitration_feedback = state.get("arbitration_feedback", "").strip()
        if not arbitration_feedback:
            return

        llm = self.get_evidence_llm()
        prompt = prompts.get_ps3_evidence_feedback_prompt(
            state.get("translated_md", ""),
            state.get("image_descriptions", []),
            state.get("ps3_evidence", {}),
            arbitration_feedback,
            knowledge_context=state.get("knowledge_context", ""),
        )

        try:
            response = self._invoke_with_tools(llm, [HumanMessage(content=prompt)])
        except Exception as e:
            logger.error(f"证据反馈 LLM 调用失败: {e}")
            raise RuntimeError("证据反馈 LLM 调用失败") from e

        try:
            content = self._message_content_to_text(response.content)
            evidence_json = self._parse_json_payload_with_repair(content, "证据反馈")
            total_score = (
                evidence_json.get("ps3_step_1", {}).get("score", 0)
                + evidence_json.get("ps3_step_2", {}).get("score", 0)
                + evidence_json.get("ps3_step_3", {}).get("score", 0)
                + evidence_json.get("ps3_step_4", {}).get("score", 0)
            )
            evidence_json["calculated_total_score"] = total_score
            state["ps3_evidence"] = evidence_json
        except RuntimeError as e:
            logger.error(f"证据反馈 JSON 解析失败: {e}")
            raise RuntimeError("证据反馈 JSON 解析失败") from e

    @timer("步骤5: 仲裁评分")
    def arbitrate_score(self, state: ProcessingState) -> ProcessingState:
        """仲裁 LLM 评分"""
        logger.info("开始仲裁评分...")

        llm = self.get_arbitration_llm()

        ps3_evidence = state["ps3_evidence"]
        calculated_score = ps3_evidence.get("calculated_total_score", 0)
        overall_assessment = ps3_evidence.get("overall_assessment", {})
        final_recommendation = overall_assessment.get(
            "final_recommendation", "needs_refinement"
        )

        search_queries = self._get_default_rag_queries()
        knowledge_context = self._retrieve_knowledge_context_sync(search_queries)
        state["knowledge_context"] = knowledge_context

        prompt = prompts.get_arbitration_prompt(
            state["translated_md"],
            state.get("image_descriptions", []),
            state["ps3_evidence"],
            calculated_score,
            final_recommendation,
            knowledge_context=knowledge_context,
        )

        graph_context = state.get("graph_context")
        if isinstance(graph_context, dict) and graph_context.get("reasoning_summary"):
            prompt += (
                "\n\n--- Knowledge Graph Reasoning Context ---\n"
                + graph_context["reasoning_summary"]
                + "\n--- End Knowledge Graph Context ---\n"
            )

        try:
            response = llm.invoke([HumanMessage(content=prompt)])
        except Exception as e:
            logger.error(f"仲裁 LLM 调用失败: {e}")
            raise RuntimeError("仲裁 LLM 调用失败") from e

        try:
            content = self._message_content_to_text(response.content)
            arbitration_result = self._parse_json_payload_with_repair(content, "仲裁")
            raw_confidence = arbitration_result.get("confidence", None)

            confidence = 0.0
            if isinstance(raw_confidence, (int, float)):
                confidence = float(raw_confidence)

            confidence = max(0.0, min(1.0, confidence))
            state["arbitration_confidence"] = confidence
            state["arbitration_score"] = round(confidence * 100.0, 2)
            state["arbitration_feedback"] = arbitration_result.get("feedback", "")

            logger.info(
                "仲裁完成，置信度: {:.2f}，仲裁得分: {:.1f}",
                state["arbitration_confidence"],
                state["arbitration_score"],
            )
        except RuntimeError as e:
            logger.error(f"仲裁 JSON 解析失败: {e}，使用计算得分")
            raise RuntimeError("仲裁 JSON 解析失败") from e

        self._apply_arbitration_feedback(state)

        logger.debug("仲裁反馈长度: {}", len(state.get("arbitration_feedback", "")))
        return state

    @staticmethod
    def route_decision(state: ProcessingState) -> str:
        raw_score = state.get("arbitration_score")
        raw_confidence = state.get("arbitration_confidence")

        score: Optional[float] = None
        confidence: Optional[float] = None
        try:
            if raw_score is not None:
                score = float(raw_score)
        except (TypeError, ValueError):
            score = None
        try:
            if raw_confidence is not None:
                confidence = float(raw_confidence)
        except (TypeError, ValueError):
            confidence = None

        logger.info("路由决策: score={}, confidence={}", score, confidence)

        if score is not None and score >= prompts.ARBITRATION_SCORE_THRESHOLD:
            logger.info(
                "路由结果: approved（score {:.1f} >= {:.1f}）",
                score,
                prompts.ARBITRATION_SCORE_THRESHOLD,
            )
            return "approved"

        if (
            confidence is not None
            and confidence >= prompts.ARBITRATION_CONFIDENCE_THRESHOLD
        ):
            logger.info(
                "路由结果: approved（confidence {:.2f} >= {:.2f}）",
                confidence,
                prompts.ARBITRATION_CONFIDENCE_THRESHOLD,
            )
            return "approved"

        logger.warning(
            "路由结果: manual_review（score={}, confidence={}）", score, confidence
        )
        return "manual_review"

    @staticmethod
    def finish_approved(state: ProcessingState) -> ProcessingState:
        """标记为审核通过"""
        state["status"] = "approved"
        return state

    @staticmethod
    def finish_manual(state: ProcessingState) -> ProcessingState:
        """标记为需要人工复核"""
        state["status"] = "manual_review"
        return state

    def build_evidence_workflow(self):
        """构建医学证据提取工作流"""
        workflow = StateGraph(ProcessingState)

        workflow.add_node("translate", self.translate_markdown)
        workflow.add_node("describe_images", self.describe_images)
        workflow.add_node("extract_evidence", self.extract_ps3_evidence_sync)
        workflow.add_node("arbitrate", self.arbitrate_score)
        workflow.add_node("finish_approved", self.finish_approved)
        workflow.add_node("finish_manual", self.finish_manual)

        workflow.add_edge("translate", "describe_images")
        workflow.add_edge("describe_images", "extract_evidence")
        workflow.add_edge("extract_evidence", "arbitrate")

        workflow.add_conditional_edges(
            "arbitrate",
            self.route_decision,
            {
                "approved": "finish_approved",
                "manual_review": "finish_manual",
            },
        )

        workflow.add_edge("finish_approved", END)
        workflow.add_edge("finish_manual", END)

        workflow.set_entry_point("translate")
        return workflow.compile()

    @timer("医学证据处理")
    def process_medical_evidence(
        self,
        markdown_content: str,
        image_paths: List[str],
        translated_md: str = "",
        max_iterations: int = 2,
        **kwargs,
    ) -> EvidenceOutput:
        """处理医学证据的主函数"""
        logger.info("开始处理医学证据（图片: {} 张）", len(image_paths))

        initial_state: ProcessingState = {
            "markdown_content": markdown_content,
            "image_paths": image_paths,
            "translated_md": translated_md or "",
            "image_descriptions": [],
            "enable_vlm": bool(self.cfg.vlm_enable),
            "vlm_results": [],
            "ps3_evidence": {},
            "extracted_fields": {},
            "evidence_sources": [],
            "knowledge_context": "",
            "field_confidence_scores": {},
            "overall_confidence": 0.0,
            "evidence_classification": "",
            "acmg_evidence_levels": [],
            "arbitration_confidence": 0.0,
            "arbitration_score": 0.0,
            "arbitration_feedback": "",
            "iteration_count": 0,
            "max_iterations": max_iterations,
            "needs_manual_review": False,
            "status": "pending",
            "output": None,
        }

        workflow = self.build_evidence_workflow()
        try:
            final_state = workflow.invoke(initial_state)
            if not isinstance(final_state, dict):
                raise RuntimeError("Evidence workflow returned non-dict state")
        except Exception as e:
            logger.error(f"医学证据处理失败: {e}")
            return EvidenceOutput(
                ps3_evidence={"error": str(e)},
                arbitration_confidence=0.0,
                image_descriptions=initial_state.get("image_descriptions", []),
                final_evidence_strength=None,
                status="failed",
                origin_format_md=markdown_content,
                en_format_md=initial_state.get("translated_md", ""),
                extracted_fields={},
                field_confidence_scores={},
                overall_confidence=0.0,
                evidence_classification="",
                acmg_evidence_levels=[],
            )

        final_evidence_strength = None
        if "ps3_step_4" in final_state.get("ps3_evidence", {}):
            final_evidence_strength = final_state["ps3_evidence"]["ps3_step_4"].get(
                "final_evidence_strength",
                "inconclusive",
            )

        final_state["ps3_evidence"] = enrich_evidence_json(
            final_state.get("ps3_evidence", {}),
            final_state.get("translated_md", ""),
        )
        contract_fields = self._extract_output_contract_fields(
            final_state, final_evidence_strength
        )

        output = EvidenceOutput(
            ps3_evidence=final_state["ps3_evidence"],
            arbitration_confidence=final_state.get("arbitration_confidence"),
            image_descriptions=final_state["image_descriptions"],
            final_evidence_strength=final_evidence_strength,
            status=final_state["status"],
            origin_format_md=final_state["markdown_content"],
            en_format_md=final_state["translated_md"],
            extracted_fields=contract_fields["extracted_fields"],
            field_confidence_scores=contract_fields["field_confidence_scores"],
            overall_confidence=contract_fields["overall_confidence"],
            evidence_classification=contract_fields["evidence_classification"],
            acmg_evidence_levels=contract_fields["acmg_evidence_levels"],
        )

        logger.info(
            f"证据处理完成: status={final_state['status']}, confidence={final_state['arbitration_confidence']:.2f}, "
            f"strength={final_evidence_strength}"
        )

        return output


logger.debug("EvidenceAgent workflow module loaded")
