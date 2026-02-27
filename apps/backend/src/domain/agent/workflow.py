from typing import List, Dict, Any, Optional
import asyncio
import base64
import json
import re
from pathlib import Path
from loguru import logger
from src.domain.enums import ProcessingState
from src.domain.models import EvidenceOutput
from src.domain.agent import prompts
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_anthropic import ChatAnthropic
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
from src.config import settings
from .rag import RAGComponent 
cfg = settings


class EvidenceAgent:
    """医学证据处理 Agent"""

    def __init__(self, cfg=settings, rag_component: Optional[RAGComponent] = None):
        self.cfg = cfg
        self.rag = rag_component or RAGComponent()
        logger.info("EvidenceAgent initialized")

    def _normalize_anthropic_base_url(self, base_url: str) -> str:
        if not base_url:
            logger.debug("Anthropic base URL is empty")
            return base_url
        cleaned = base_url.rstrip("/")
        if cleaned.endswith("/v1"):
            cleaned = cleaned[:-3]
        logger.debug("Normalized Anthropic base URL: {}", cleaned)
        return cleaned

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

        sentences = [s for s in re.split(r"(?<=[。！？.!?])\s+", paragraph.strip()) if s]
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
            paragraph_units.extend(self._split_paragraph(paragraph, max_tokens, max_chars))

        segments: List[str] = []
        current = ""
        for unit in paragraph_units:
            candidate = unit if not current else f"{current}\n\n{unit}"
            if self._estimate_tokens(candidate) <= max_tokens and (max_chars is None or len(candidate) <= max_chars):
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
                    retrieved_docs.append({
                        "content": payload.get("content", ""),
                        "file_path": payload.get("file_path", ""),
                        "score": result.score,
                        "source": "rag",
                    })
        except Exception as e:
            logger.error(f"知识库检索失败: {e}")
            raise RuntimeError("知识库检索失败") from e

        for query in search_queries:
            try:
                tool_results = await search_knowledge_base.ainvoke({
                    "query": query,
                    "top_k": 3,
                })
            except Exception as e:
                logger.error(f"工具检索失败 '{query}': {e}")
                raise RuntimeError("工具检索失败") from e

            for result in tool_results:
                retrieved_docs.append({
                    "content": result.get("content", ""),
                    "file_path": result.get("file_path", ""),
                    "score": result.get("score", 0),
                    "source": "tool",
                })

        seen_content = set()
        unique_docs = []
        for doc in sorted(retrieved_docs, key=lambda x: x["score"], reverse=True):
            content_hash = hash(doc["content"][:200])
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_docs.append(doc)

        top_docs = unique_docs[:5]

        knowledge_context = "\n\n".join([
            f"[参考文档 {i+1}] (相似度: {doc['score']:.3f})\n{doc['content'][:1000]}..."
            for i, doc in enumerate(top_docs)
        ]) if top_docs else "未检索到相关知识库文档"

        logger.info(f"知识库检索完成，获取 {len(top_docs)} 个相关文档")
        return knowledge_context

    def _retrieve_knowledge_context_sync(self, search_queries: List[str]) -> str:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._retrieve_knowledge_context(search_queries))
        raise RuntimeError("_retrieve_knowledge_context_sync cannot run inside a running event loop")

    # ==================== LLM 客户端配置 ====================
    def get_translation_llm(self):
        """获取翻译 LLM 客户端"""
        logger.info("Initializing translation LLM")
        return ChatOpenAI(
            model=self.cfg.mt_model,
            api_key=SecretStr(self.cfg.mt_api_key),
            base_url=self.cfg.mt_base_url,
            temperature=0.0,
        )

    def get_format_llm(self):
        """获取排版 LLM 客户端"""
        logger.info("Initializing format LLM")
        return ChatOpenAI(
            model=self.cfg.format_model,
            api_key=SecretStr(self.cfg.format_api_key),
            base_url=self.cfg.format_base_url,
            temperature=0.0,
        )

    def get_vlm(self):
        """获取支持视觉的 LLM 客户端"""
        logger.info("Initializing VLM")
        return ChatOpenAI(
            model=self.cfg.vlm_model,
            api_key=SecretStr(self.cfg.vlm_api_key),
            base_url=self.cfg.vlm_base_url,
            temperature=0.0,
        )

    def get_evidence_llm(self):
        """获取证据提取 LLM 客户端（支持工具调用）"""
        logger.info("Initializing evidence LLM")
        llm = ChatAnthropic(
            model_name=self.cfg.evidence_model,
            api_key=SecretStr(self.cfg.evidence_api_key),
            base_url=self._normalize_anthropic_base_url(self.cfg.evidence_base_url),
            temperature=0.0,
            timeout=self.cfg.llm_timeout,
            streaming=True,
            stop=["\n\nHuman:"],
        )
        return llm.bind_tools(get_evidence_tools())

    def get_arbitration_llm(self):
        """获取仲裁 LLM 客户端"""
        logger.info("Initializing arbitration LLM")
        return ChatAnthropic(
            model_name=self.cfg.arbitration_model,
            api_key=SecretStr(self.cfg.arbitration_api_key),
            base_url=self._normalize_anthropic_base_url(self.cfg.arbitration_base_url),
            temperature=0.0,
            timeout=self.cfg.llm_timeout,
            stop=["\n\nHuman:"],
            streaming=True,
            thinking={"type": "enabled"},
        )

    def _invoke_with_tools(
        self,
        llm: ChatAnthropic,
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
                tool_name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
                tool_args = call.get("args") if isinstance(call, dict) else getattr(call, "args", None)
                tool_call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)

                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError:
                        tool_args = {}

                tool_impl = tool_map.get(tool_name)
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
        """Normalize LangChain/Anthropic message content into plain text."""
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
                text for item in content
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

    def _extract_json_payload(self, content: str) -> Dict[str, Any]:
        if not content:
            raise RuntimeError("LLM 响应为空，无法解析 JSON")

        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                raise RuntimeError("无法从响应中提取 JSON")
            return json.loads(match.group())

    # ==================== 处理步骤函数 ====================
    @timer("步骤1: 翻译")
    def translate_markdown(self, state: ProcessingState) -> ProcessingState:
        """翻译 Markdown 为英文"""
        logger.info("开始翻译 Markdown 为英文...")

        llm = self.get_translation_llm()
        markdown_content = state.get('markdown_content', '')
        if not markdown_content.strip():
            logger.warning("Markdown 内容为空，跳过翻译")
            state['translated_md'] = ""
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
                logger.info(f"翻译分段 {idx}/{len(segments)} 完成，字数: {len(content)}")
            except Exception as e:
                logger.error(f"翻译分段 {idx}/{len(segments)} 失败: {e}")
                raise RuntimeError(f"翻译分段 {idx} 失败") from e

        state['translated_md'] = "\n\n".join(translated_segments)
        logger.info(f"翻译完成，字数: {len(state['translated_md'])}")

        return state

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

        llm = self.get_vlm()
        descriptions = []

        for idx, img_path in enumerate(image_paths):
            try:
                with open(img_path, 'rb') as f:
                    img_data = base64.b64encode(f.read()).decode()

                ext = Path(img_path).suffix.lower()
                media_type = {
                    '.jpg': 'images/jpeg',
                    '.jpeg': 'images/jpeg',
                    '.png': 'images/png',
                    '.gif': 'images/gif',
                    '.webp': 'images/webp',
                }.get(ext, 'images/jpeg')

                prompt = prompts.get_image_description_prompt(idx + 1)

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

                response = llm.invoke([message])
                descriptions.append(self._message_content_to_text(response.content))
                logger.info(f"图片 {idx+1} 描述完成")
            except Exception as e:
                logger.error(f"处理图片 {img_path} 失败: {e}")
                raise RuntimeError(f"图片处理失败: {img_path}") from e

        state['image_descriptions'] = descriptions
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
            evidence_json = self._extract_json_payload(content)
            state['ps3_evidence'] = evidence_json

            overall = evidence_json.get('overall_assessment', {})
            state['evidence_sources'] = overall.get('key_strengths', [])

            total_score = (
                evidence_json.get('ps3_step_1', {}).get('score', 0)
                + evidence_json.get('ps3_step_2', {}).get('score', 0)
                + evidence_json.get('ps3_step_3', {}).get('score', 0)
                + evidence_json.get('ps3_step_4', {}).get('score', 0)
            )
            evidence_json['calculated_total_score'] = total_score

            logger.info(f"PS3 证据提取完成，总分: {total_score}/100")
            logger.info(
                f"最终证据强度: {evidence_json.get('ps3_step_4', {}).get('final_evidence_strength', 'inconclusive')}"
            )
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            raise RuntimeError("证据提取 JSON 解析失败") from e

        return state

    def extract_ps3_evidence_sync(self, state: ProcessingState) -> ProcessingState:
        """同步包装，便于在同步工作流中使用异步证据提取"""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.extract_ps3_evidence(state))
        raise RuntimeError("extract_ps3_evidence_sync cannot run inside a running event loop")

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
            evidence_json = self._extract_json_payload(content)
            total_score = (
                evidence_json.get("ps3_step_1", {}).get("score", 0)
                + evidence_json.get("ps3_step_2", {}).get("score", 0)
                + evidence_json.get("ps3_step_3", {}).get("score", 0)
                + evidence_json.get("ps3_step_4", {}).get("score", 0)
            )
            evidence_json["calculated_total_score"] = total_score
            state["ps3_evidence"] = evidence_json
        except json.JSONDecodeError as e:
            logger.error(f"证据反馈 JSON 解析失败: {e}")
            raise RuntimeError("证据反馈 JSON 解析失败") from e

    @timer("步骤5: 仲裁评分")
    def arbitrate_score(self, state: ProcessingState) -> ProcessingState:
        """仲裁 LLM 评分"""
        logger.info("开始仲裁评分...")

        llm = self.get_arbitration_llm()

        ps3_evidence = state['ps3_evidence']
        calculated_score = ps3_evidence.get('calculated_total_score', 0)
        overall_assessment = ps3_evidence.get('overall_assessment', {})
        final_recommendation = overall_assessment.get('final_recommendation', 'needs_refinement')

        search_queries = self._get_default_rag_queries()
        knowledge_context = self._retrieve_knowledge_context_sync(search_queries)
        state["knowledge_context"] = knowledge_context

        prompt = prompts.get_arbitration_prompt(
            state['translated_md'],
            state.get("image_descriptions", []),
            state['ps3_evidence'],
            calculated_score,
            final_recommendation,
            knowledge_context=knowledge_context,
        )

        try:
            response = llm.invoke([HumanMessage(content=prompt)])
        except Exception as e:
            logger.error(f"仲裁 LLM 调用失败: {e}")
            raise RuntimeError("仲裁 LLM 调用失败") from e

        try:
            content = self._message_content_to_text(response.content)
            arbitration_result = self._extract_json_payload(content)
            raw_confidence = arbitration_result.get('confidence', None)

            confidence = 0.0
            if isinstance(raw_confidence, (int, float)):
                confidence = float(raw_confidence)

            confidence = max(0.0, min(1.0, confidence))
            state['arbitration_confidence'] = confidence
            state['arbitration_score'] = round(confidence * 100.0, 2)
            state['arbitration_feedback'] = arbitration_result.get('feedback', '')

            logger.info(f"仲裁置信度: {state['arbitration_confidence']:.2f}")
            logger.info(
                f"初步得分: {calculated_score}, 最终决策: {arbitration_result.get('final_decision', 'unknown')}"
            )
        except json.JSONDecodeError as e:
            logger.error(f"仲裁 JSON 解析失败: {e}，使用计算得分")
            raise RuntimeError("仲裁 JSON 解析失败") from e

        self._apply_arbitration_feedback(state)

        logger.info(f"仲裁完成，最终置信度: {state['arbitration_confidence']:.2f}")
        return state

    

    @staticmethod
    def route_decision(state: ProcessingState) -> str:
        """路由决策：是否通过、继续迭代或标记人工复核"""
        raw_score = state.get('arbitration_score')
        raw_confidence = state.get('arbitration_confidence')

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

        logger.info("路由决策: score=%s, confidence=%s", score, confidence)

        if score is not None and score >= prompts.ARBITRATION_SCORE_THRESHOLD:
            logger.info("✓ 仲裁得分 >= %.1f，通过审核", prompts.ARBITRATION_SCORE_THRESHOLD)
            return "approved"

        if confidence is not None and confidence >= prompts.ARBITRATION_CONFIDENCE_THRESHOLD:
            logger.info("✓ 仲裁置信度 >= %.2f，通过审核", prompts.ARBITRATION_CONFIDENCE_THRESHOLD)
            return "approved"

        logger.warning("评分/置信度未达标，标记人工复核")
        return "manual_review"

    @staticmethod
    def finish_approved(state: ProcessingState) -> ProcessingState:
        """标记为审核通过"""
        result = dict(state)
        result['status'] = 'approved'
        return result  # type: ignore

    @staticmethod
    def finish_manual(state: ProcessingState) -> ProcessingState:
        """标记为需要人工复核"""
        result = dict(state)
        result['status'] = 'manual_review'
        return result  # type: ignore

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
        max_iterations: int = 2,
        **kwargs,
    ) -> EvidenceOutput:
        """处理医学证据的主函数"""
        logger.info(f"开始处理医学证据（图片: {len(image_paths)} 张，迭代限制: {max_iterations}）")

        initial_state: ProcessingState = {
            'markdown_content': markdown_content,
            'image_paths': image_paths,
            'translated_md': '',
            'image_descriptions': [],
            'enable_vlm': bool(self.cfg.vlm_enable),
            'vlm_results': [],
            'ps3_evidence': {},
            'evidence_sources': [],
            'knowledge_context': '',
            'arbitration_confidence': 0.0,
            'arbitration_feedback': '',
            'iteration_count': 0,
            'max_iterations': max_iterations,
            'status': 'pending',
            'output': None,
        }

        workflow = self.build_evidence_workflow()
        try:
            final_state = workflow.invoke(initial_state)
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
            )

        final_evidence_strength = None
        if 'ps3_step_4' in final_state.get('ps3_evidence', {}):
            final_evidence_strength = final_state['ps3_evidence']['ps3_step_4'].get(
                'final_evidence_strength',
                'inconclusive',
            )

        final_state['ps3_evidence'] = enrich_evidence_json(
            final_state.get('ps3_evidence', {}),
            final_state.get('translated_md', ''),
        )

        output = EvidenceOutput(
            ps3_evidence=final_state['ps3_evidence'],
            arbitration_confidence=final_state.get('arbitration_confidence'),
            image_descriptions=final_state['image_descriptions'],
            final_evidence_strength=final_evidence_strength,
            status=final_state['status'],
            origin_format_md=final_state['markdown_content'],
            en_format_md=final_state['translated_md'],
        )

        logger.info(
            f"证据处理完成: status={final_state['status']}, confidence={final_state['arbitration_confidence']:.2f}, "
            f"strength={final_evidence_strength}"
        )

        return output




logger.debug(f"LLM配置: LLM模式: {cfg.llm_mode}, 证据模型: {cfg.evidence_model}, 仲裁模型: {cfg.arbitration_model}")
