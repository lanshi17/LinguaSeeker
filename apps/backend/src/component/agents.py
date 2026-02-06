from typing import List, Dict, Any, Callable, Optional, TypedDict, Annotated, Sequence, Iterator
import asyncio
import websockets
import json
import base64
import json
from pathlib import Path
from loguru import logger
from component.enums import ProcessingState
from component.models import AgentRequest, AgentResponse, EvidenceOutput
from component import prompts
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_openai.embeddings import OpenAIEmbeddings
from langgraph.graph import StateGraph, END
from langchain_core.tools import tool, BaseTool
from langgraph.prebuilt import ToolNode
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph.message import add_messages
from pydantic import SecretStr, BaseModel, Field
import os
from utils.timer import Timer, timer
import utils.exceptions as exc
import utils.file_utils as file_utils
from config import settings
from rag import RAGComponent 
cfg = settings

rag=RAGComponent()




# ==================== LLM 客户端配置 ====================
logger.debug(f"LLM配置: LLM模式: {cfg.llm_mode}, 证据模型: {cfg.evidence_model}, 仲裁模型: {cfg.arbitration_model}")

def get_translation_llm():
    """获取翻译 LLM 客户端"""
    return ChatOpenAI(
        model="qwen-mt-flash",
        api_key=SecretStr(cfg.generic_api_key),
        base_url=cfg.generic_base_url,
        temperature=0.0
    )


def get_format_llm():    
    """获取排版 LLM 客户端"""
    return ChatOpenAI(
        model="qwen-plus",
        api_key=SecretStr(cfg.generic_api_key),
        base_url=cfg.generic_base_url,
        temperature=0.0,
    )
    
def get_vlm():
    """获取支持视觉的 LLM 客户端"""
    return ChatOpenAI(
        model="qwen-vl-flash",
        api_key=SecretStr(cfg.generic_api_key),
        base_url=cfg.generic_base_url,
        temperature=0.0,
    )

def get_evidence_llm():
    """获取证据提取 LLM 客户端（支持工具调用）"""
    llm = ChatOpenAI(
        model=cfg.evidence_model,
        api_key=SecretStr(cfg.evidence_api_key),
        base_url=cfg.evidence_base_url,
        temperature=0.0,
    )
    # 绑定 PS3 评估工具
    tools = [
        OddsPath_Calculator,
        determine_evidence_strength_from_oddspath,
        determine_max_evidence_from_controls,
        validate_ps3_step1,
        validate_ps3_step2,
    ]
    return llm.bind_tools(tools)

def get_arbitration_llm():
    """获取仲裁 LLM 客户端"""
    return ChatAnthropic(
        model_name=cfg.arbitration_model,
        api_key=SecretStr(cfg.arbitration_api_key),
        temperature=0.0,
        timeout=cfg.llm_timeout,
        stop=["\nHuman:", "\nAssistant:"],
    )

#========================= tools定义 ====================
@tool
def save_intermediate_md(md_content: str, file_path: str) -> str:
    """保存中间 Markdown 文件的工具函数"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        logger.info(f"中间 Markdown 文件已保存: {file_path}")
        return f"文件已保存: {file_path}"
    except Exception as e:
        logger.error(f"保存文件失败: {e}")
        return f"保存文件失败: {str(e)}"

@tool
def load_intermediate_md(file_path: str) -> str:
    """加载中间 Markdown 文件的工具函数"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logger.info(f"中间 Markdown 文件已加载: {file_path}")
        return content
    except Exception as e:
        logger.error(f"加载文件失败: {e}")
        return f"加载文件失败: {str(e)}"
    
@tool
def OddsPath_Calculator(P1: float, P2: float) -> float:
    """
    计算 OddsPath 的工具函数
    
    Args:
        P1: 野生型/正常对照的概率 (0,1)
        P2: 变异型的概率 (0,1)
    
    Returns:
        OddsPath 值，公式: OddsPath = [P2 × (1-P1)] / [(1-P2) × P1]
    """
    try:
        if not (0 < P1 < 1) or not (0 < P2 < 1):
            raise ValueError("P1 和 P2 必须在 (0,1) 范围内")
        
        odds_path = (P2 * (1 - P1)) / ((1 - P2) * P1)
        logger.info(f"计算 OddsPath: P1={P1}, P2={P2}, OddsPath={odds_path:.4f}")
        return odds_path
    except Exception as e:
        logger.error(f"计算 OddsPath 失败: {e}")
        return -1.0

@tool
def determine_evidence_strength_from_oddspath(oddspath: float) -> str:
    """
    根据 OddsPath 值确定 PS3/BS3 证据强度
    
    Args:
        oddspath: 计算得到的 OddsPath 值
    
    Returns:
        证据强度等级字符串
    
    OddsPath 映射规则:
    - <0.053: BS3
    - <0.23: BS3_moderate
    - <0.48: BS3_supporting
    - 0.48-2.1: 不明确
    - >2.1: PS3_supporting
    - >4.3: PS3_moderate
    - >18.7: PS3
    - >350: PS3_very_strong
    """
    try:
        if oddspath < 0:
            return "invalid_oddspath"
        elif oddspath < 0.053:
            return "BS3"
        elif oddspath < 0.23:
            return "BS3_moderate"
        elif oddspath < 0.48:
            return "BS3_supporting"
        elif oddspath <= 2.1:
            return "inconclusive"
        elif oddspath <= 4.3:
            return "PS3_supporting"
        elif oddspath <= 18.7:
            return "PS3_moderate"
        elif oddspath <= 350:
            return "PS3"
        else:
            return "PS3_very_strong"
    except Exception as e:
        logger.error(f"确定证据强度失败: {e}")
        return "error"

@tool
def determine_max_evidence_from_controls(control_variants_count: int) -> str:
    """
    根据对照变异数量确定最大可用的证据强度
    
    Args:
        control_variants_count: 使用的良性/致病对照变异总数
    
    Returns:
        最大证据强度等级
    
    规则:
    - ≤10个: 最高使用到 PS3_supporting / BS3_supporting
    - ≥11个: 最高使用到 PS3_moderate / BS3_moderate
    """
    try:
        if control_variants_count <= 0:
            return "no_evidence"
        elif control_variants_count <= 10:
            return "max_supporting"
        else:
            return "max_moderate"
    except Exception as e:
        logger.error(f"确定最大证据强度失败: {e}")
        return "error"

@tool
def validate_ps3_step1(disease_mechanism_clarity: str) -> dict:
    """
    验证 PS3 步骤①：明确疾病的致病机制
    
    Args:
        disease_mechanism_clarity: 致病机制清晰度 ("clear", "partial", "unclear")
    
    Returns:
        包含验证结果的字典
    """
    if disease_mechanism_clarity == "clear":
        return {
            "step1_pass": True,
            "can_proceed": True,
            "message": "致病机制清晰，可以继续评估"
        }
    elif disease_mechanism_clarity == "partial":
        return {
            "step1_pass": False,
            "can_proceed": True,
            "message": "致病机制部分清晰，建议补充信息后继续"
        }
    else:
        return {
            "step1_pass": False,
            "can_proceed": False,
            "message": "致病机制不清晰，不应使用 PS3/BS3 证据"
        }

@tool
def validate_ps3_step2(assay_suitable: str) -> dict:
    """
    验证 PS3 步骤②：评估功能实验方法的适用性
    
    Args:
        assay_suitable: 实验方法是否适用 ("yes", "no", "partial")
    
    Returns:
        包含验证结果的字典
    """
    if assay_suitable == "yes":
        return {
            "step2_pass": True,
            "can_proceed": True,
            "message": "功能实验方法符合致病机制，可以继续评估"
        }
    else:
        return {
            "step2_pass": False,
            "can_proceed": False,
            "message": "功能实验方法不符合致病机制，不应使用 PS3/BS3 证据"
        }

@tool
async def search_knowledge_base(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    从 Qdrant 知识库中检索相关文档
    
    Args:
        query: 检索查询字符串
        top_k: 返回的最相关文档数量（默认 5）
    
    Returns:
        包含相关文档的列表，每个文档包含 content 和 score
    """
    try:
        qdrant_manager = rag.get_qdrant_manager()
        embedding_client = rag.get_embedding_client()
        
        # 生成查询向量
        query_vector = embedding_client.embed_query(query)
        
        # 检索相关文档
        search_results = await qdrant_manager.client.search(
            collection_name=qdrant_manager.collection_name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=qdrant_manager.score_threshold,
        )
        
        # 格式化结果
        results = []
        for result in search_results:
            results.append({
                "content": result.payload.get("content", ""),
                "file_path": result.payload.get("file_path", ""),
                "score": result.score,
            })
        
        logger.info(f"知识库检索完成: query='{query[:50]}...', results={len(results)}")
        return results
    except Exception as e:
        logger.error(f"知识库检索失败: {e}")
        return []

# ==================== 处理步骤函数 ====================

@timer("步骤1: 翻译")
def translate_markdown(state: ProcessingState) -> ProcessingState:
    """翻译 Markdown 为英文"""
    logger.info("开始翻译 Markdown 为英文...")
    
    llm = get_translation_llm()
    prompt = prompts.get_translation_prompt(state['markdown_content'])
    
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content if isinstance(response.content, str) else str(response.content)
    state['translated_md'] = content
    logger.info(f"翻译完成，字数: {len(state['translated_md'])}")
    
    return state

@timer("步骤2: 图片描述")
def describe_images(state: ProcessingState) -> ProcessingState:
    """使用 VLM 生成图片描述"""
    logger.info(f"开始处理 {len(state['image_paths'])} 张图片...")
    
    llm = get_vlm()  # 使用支持 vision 的模型
    descriptions = []
    
    for idx, img_path in enumerate(state['image_paths']):
        try:
            # 读取图片并转换为 base64
            with open(img_path, 'rb') as f:
                img_data = base64.b64encode(f.read()).decode()
            
            # 确定图片类型
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
                        }
                    }
                ]
            )
            
            response = llm.invoke([message])
            descriptions.append(response.content)
            logger.info(f"图片 {idx+1} 描述完成")
        except Exception as e:
            logger.error(f"处理图片 {img_path} 失败: {e}")
            descriptions.append(f"[图片处理失败] {str(e)}")
    
    state['image_descriptions'] = descriptions
    return state

@timer("步骤3: 排版融合")
def fuse_layout(state: ProcessingState) -> ProcessingState:
    """将翻译 MD 和图片描述融合为排版 MD"""
    logger.info("开始融合翻译内容和图片描述...")
    
    llm = get_format_llm()
    prompt = prompts.get_layout_fusion_prompt(
        state['translated_md'],
        state['image_descriptions']
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content if isinstance(response.content, str) else str(response.content)
    state['middleware_md'] = content
    logger.info(f"融合完成，字数: {len(state['middleware_md'])}")
    
    return state

@timer("步骤4: 证据提取+RAG")
async def extract_ps3_evidence(state: ProcessingState) -> ProcessingState:
    """使用 LLM + RAG 提取 PS3 证据"""
    logger.info("开始提取 PS3 证据...")
    
    # 步骤 1: 从知识库检索相关文档
    middleware_content = state['middleware_md']
    search_queries = [
        "PS3 BS3 functional evidence assessment criteria",
        "ACMG variant interpretation guidelines functional assays",
        "OddsPath calculation pathogenic benign variants",
    ]
    
    retrieved_docs = []
    try:
        qdrant_manager = rag.get_qdrant_manager()
        embedding_client = rag.get_embedding_client()
        
        for query in search_queries:
            try:
                # 生成查询向量
                query_vector = embedding_client.embed_query(query)
                
                # 检索相关文档
                search_results = await qdrant_manager.client.search(  # type: ignore
                    collection_name=qdrant_manager.collection_name,
                    query_vector=query_vector,
                    limit=3,
                    score_threshold=qdrant_manager.score_threshold,
                )
                
                # 格式化结果
                for result in search_results:
                    retrieved_docs.append({
                        "content": result.payload.get("content", ""),
                        "file_path": result.payload.get("file_path", ""),
                        "score": result.score,
                    })
            except Exception as e:
                logger.warning(f"检索查询 '{query}' 失败: {e}")
                continue
    except Exception as e:
        logger.warning(f"知识库检索失败: {e}，将不使用 RAG 上下文")
    
    # 去重并按相似度排序
    seen_content = set()
    unique_docs = []
    for doc in sorted(retrieved_docs, key=lambda x: x['score'], reverse=True):
        content_hash = hash(doc['content'][:200])  # 使用前200字符判断重复
        if content_hash not in seen_content:
            seen_content.add(content_hash)
            unique_docs.append(doc)
    
    # 限制最多使用前 5 个最相关文档
    top_docs = unique_docs[:5]
    
    # 构建知识库上下文
    knowledge_context = "\n\n".join([
        f"[参考文档 {i+1}] (相似度: {doc['score']:.3f})\n{doc['content'][:1000]}..."
        for i, doc in enumerate(top_docs)
    ]) if top_docs else "未检索到相关知识库文档"
    
    logger.info(f"知识库检索完成，获取 {len(top_docs)} 个相关文档")
    
    # 步骤 2: 使用 LLM + RAG 上下文提取证据
    llm = get_evidence_llm()
    prompt = prompts.get_ps3_evidence_extraction_prompt(
        state['middleware_md'],
        knowledge_context=knowledge_context
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        # 提取 JSON 部分
        import re
        content = response.content if isinstance(response.content, str) else str(response.content)
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            evidence_json = json.loads(json_match.group())
            state['ps3_evidence'] = evidence_json
            
            # 提取总分用于后续仲裁
            overall = evidence_json.get('overall_assessment', {})
            state['evidence_sources'] = overall.get('key_strengths', [])
            
            # 计算总分（各步骤得分之和）
            total_score = (
                evidence_json.get('ps3_step_1', {}).get('score', 0) +
                evidence_json.get('ps3_step_2', {}).get('score', 0) +
                evidence_json.get('ps3_step_3', {}).get('score', 0) +
                evidence_json.get('ps3_step_4', {}).get('score', 0)
            )
            evidence_json['calculated_total_score'] = total_score
            
            logger.info(f"PS3 证据提取完成，总分: {total_score}/100")
            logger.info(f"最终证据强度: {evidence_json.get('ps3_step_4', {}).get('final_evidence_strength', 'none')}")
        else:
            logger.warning("无法从响应中提取 JSON")
            state['ps3_evidence'] = {"error": "提取失败"}
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}")
        state['ps3_evidence'] = {"error": f"JSON 解析失败: {e}"}
    
    return state

@timer("步骤5: 仲裁评分")
def arbitrate_score(state: ProcessingState) -> ProcessingState:
    """仲裁 LLM 评分"""
    logger.info("开始仲裁评分...")
    
    llm = get_arbitration_llm()
    
    # 提取 PS3 评估的关键信息
    ps3_evidence = state['ps3_evidence']
    calculated_score = ps3_evidence.get('calculated_total_score', 0)
    overall_assessment = ps3_evidence.get('overall_assessment', {})
    final_recommendation = overall_assessment.get('final_recommendation', 'needs_refinement')
    
    prompt = prompts.get_arbitration_prompt(
        state['middleware_md'],
        state['ps3_evidence'],
        calculated_score,
        final_recommendation
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        import re
        content = response.content if isinstance(response.content, str) else str(response.content)
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            arbitration_result = json.loads(json_match.group())
            state['arbitration_score'] = arbitration_result.get('arbitration_score', calculated_score)
            state['arbitration_feedback'] = arbitration_result.get('feedback', '')
            
            # 记录详细的仲裁结果
            logger.info(f"仲裁得分: {state['arbitration_score']}/100")
            logger.info(f"初步得分: {calculated_score}, 调整: {arbitration_result.get('score_adjustment', 0)}")
            logger.info(f"最终决策: {arbitration_result.get('final_decision', 'unknown')}")
        else:
            logger.warning("无法从仲裁结果中提取 JSON，使用计算得分")
            state['arbitration_score'] = calculated_score
            state['arbitration_feedback'] = "仲裁结果解析失败，使用自动计算得分"
    except json.JSONDecodeError as e:
        logger.error(f"仲裁 JSON 解析失败: {e}，使用计算得分")
        state['arbitration_score'] = calculated_score
        state['arbitration_feedback'] = f"JSON解析失败: {str(e)}"
    
    logger.info(f"仲裁完成，最终得分: {state['arbitration_score']}")
    return state

@timer("步骤6: 反馈微调")
def feedback_refinement(state: ProcessingState) -> ProcessingState:
    """根据仲裁反馈微调 middleware.md"""
    logger.info(f"开始反馈微调（第 {state['iteration_count']+1} 次）...")
    
    llm = get_format_llm()
    
    # 提取关键改进点
    ps3_evidence = state['ps3_evidence']
    overall_assessment = ps3_evidence.get('overall_assessment', {})
    improvements = overall_assessment.get('improvement_suggestions', [])
    weaknesses = overall_assessment.get('key_weaknesses', [])
    
    prompt = prompts.get_feedback_refinement_prompt(
        state['middleware_md'],
        state['arbitration_feedback'],
        state['arbitration_score'],
        weaknesses,
        improvements
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content if isinstance(response.content, str) else str(response.content)
    state['middleware_md'] = content
    state['iteration_count'] += 1
    
    logger.info(f"微调完成，迭代次数: {state['iteration_count']}")
    return state

def route_decision(state: ProcessingState) -> str:
    """路由决策：是否通过、继续迭代或标记人工复核"""
    score = state['arbitration_score']
    iterations = state['iteration_count']
    max_iter = state.get('max_iterations', 2)
    
    logger.info(f"路由决策: score={score}, iterations={iterations}, max={max_iter}")
    
    if score >= prompts.ARBITRATION_SCORE_THRESHOLD:
        logger.info("✓ 评分 >= 85，通过审核")
        return "approved"
    elif iterations < max_iter:
        logger.info(f"评分 < 85，继续迭代 ({iterations+1}/{max_iter})")
        return "refine"
    else:
        logger.warning(f"达到最大迭代次数，标记人工复核")
        return "manual_review"

def finish_approved(state: ProcessingState) -> ProcessingState:
    """标记为审核通过"""
    result = dict(state)
    result['status'] = 'approved'
    return result  # type: ignore

def finish_manual(state: ProcessingState) -> ProcessingState:
    """标记为需要人工复核"""
    result = dict(state)
    result['status'] = 'manual_review'
    return result  # type: ignore

# ==================== 工作流构建 ====================

def build_evidence_workflow():
    """构建医学证据提取工作流"""
    
    workflow = StateGraph(ProcessingState)
    
    # 添加节点
    workflow.add_node("translate", translate_markdown)
    workflow.add_node("describe_images", describe_images)
    workflow.add_node("fuse_layout", fuse_layout)
    workflow.add_node("extract_evidence", extract_ps3_evidence)
    workflow.add_node("arbitrate", arbitrate_score)
    workflow.add_node("refine", feedback_refinement)
    workflow.add_node("finish_approved", finish_approved)
    workflow.add_node("finish_manual", finish_manual)
    
    # 添加边
    workflow.add_edge("translate", "describe_images")
    workflow.add_edge("describe_images", "fuse_layout")
    workflow.add_edge("fuse_layout", "extract_evidence")
    workflow.add_edge("extract_evidence", "arbitrate")
    
    # 条件分支
    workflow.add_conditional_edges(
        "arbitrate",
        route_decision,
        {
            "approved": "finish_approved",
            "refine": "refine",
            "manual_review": "finish_manual",
        }
    )
    
    # 迭代回环
    workflow.add_edge("refine", "extract_evidence")
    
    # 结束节点
    workflow.add_edge("finish_approved", END)
    workflow.add_edge("finish_manual", END)
    
    # 设置入口
    workflow.set_entry_point("translate")
    
    return workflow.compile()

# ==================== 主处理函数 ====================

@timer("医学证据处理")
def process_medical_evidence(
    markdown_content: str,
    image_paths: List[str],
    max_iterations: int = 2,
    **kwargs,
) -> EvidenceOutput:
    """处理医学证据的主函数"""
    
    logger.info(f"开始处理医学证据（图片: {len(image_paths)} 张，迭代限制: {max_iterations}）")
    
    # 初始化状态
    initial_state: ProcessingState = {
        'markdown_content': markdown_content,
        'image_paths': image_paths,
        'translated_md': '',
        'image_descriptions': [],
        'middleware_md': '',
        'ps3_evidence': {},
        'evidence_sources': [],
        'arbitration_score': 0,
        'arbitration_feedback': '',
        'iteration_count': 0,
        'max_iterations': max_iterations,
        'status': 'pending',
        'output': None,
    }
    
    # 构建并执行工作流
    workflow = build_evidence_workflow()
    final_state = workflow.invoke(initial_state)
    
    # 提取最终证据强度
    final_evidence_strength = None
    if 'ps3_step_4' in final_state.get('ps3_evidence', {}):
        final_evidence_strength = final_state['ps3_evidence']['ps3_step_4'].get('final_evidence_strength', 'none')
    
    # 生成输出
    output = EvidenceOutput(
        ps3_evidence=final_state['ps3_evidence'],
        arbitration_score=final_state['arbitration_score'],
        middleware_md=final_state['middleware_md'],
        image_descriptions=final_state['image_descriptions'],
        final_evidence_strength=final_evidence_strength,
        status=final_state['status'],
    )
    
    logger.info(f"证据处理完成: status={final_state['status']}, score={final_state['arbitration_score']}, strength={final_evidence_strength}")
    
    return output

