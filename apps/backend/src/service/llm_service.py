"""LLM调用服务 - 封装DeepSeek和Claude的调用

支持双LLM架构:
- DeepSeek-V3.2: 主力LLM，用于实体提取、证据验证等
- Claude Opus 4.5: 仲裁LLM，用于最终评级决策和复杂推理
"""
from typing import Dict, Any, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """LLM提供商"""
    DEEPSEEK = "deepseek"  # 主力LLM
    CLAUDE = "claude"      # 仲裁LLM


class LLMRole(str, Enum):
    """LLM角色"""
    PRIMARY = "primary"    # 主力模型 - DeepSeek
    ARBITER = "arbiter"    # 仲裁模型 - Claude


class LLMService:
    """大语言模型调用服务
    
    双LLM架构:
    1. DeepSeek-V3.2 (主力): 
       - 实体提取
       - 证据初步验证
       - Cypher查询生成
       - 文本理解和分类
    
    2. Claude Opus 4.5 (仲裁):
       - 最终ACMG-PS3评级决策
       - 复杂证据推理
       - 冲突解决
       - 高风险决策验证
    """
    
    def __init__(
        self,
        deepseek_client=None,
        claude_client=None,
        llm_config: Optional[Dict[str, Any]] = None
    ):
        """支持OpenAI兼容的自定义调用与本地部署模式
        
        llm_config示例:
        {
          "mode": "api" | "local",
          "openai_api_base": "https://api.deepseek.com",
          "openai_api_key": "...",
          "deepseek_model": "deepseek-chat",
          "claude_model": "claude-opus-4.5",
          "local_endpoint": "http://localhost:11434/v1"
        }
        """
        self.deepseek_client = deepseek_client
        self.claude_client = claude_client
        self.config = llm_config or {}
    
    async def chat_completion(
        self, 
        messages: List[Dict[str, str]],
        provider: LLMProvider = LLMProvider.DEEPSEEK,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """通用聊天补全接口
        
        Args:
            messages: [{"role": "user", "content": "..."}]
            provider: DEEPSEEK | CLAUDE
            temperature: 温度参数
            max_tokens: 最大token数
        """
        try:
            if provider == LLMProvider.DEEPSEEK:
                return await self._call_deepseek(messages, temperature, max_tokens, **kwargs)
            elif provider == LLMProvider.CLAUDE:
                return await self._call_claude(messages, temperature, max_tokens, **kwargs)
            else:
                raise ValueError(f"Unknown provider: {provider}")
        except Exception as e:
            logger.error(f"LLM call failed ({provider}): {e}")
            raise
    
    async def _call_deepseek(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """调用OpenAI兼容API (DeepSeek或其他)"""
        # TODO: 实现OpenAI兼容API调用（远程API或本地endpoint）
        # response = await self.deepseek_client.chat.completions.create(
        #     model=self.config.get("deepseek_model", "deepseek-chat"),
        #     messages=messages,
        #     temperature=temperature,
        #     max_tokens=max_tokens
        # )
        # return response.choices[0].message.content
        logger.info(f"[DeepSeek] Calling with {len(messages)} messages")
        return "DeepSeek response placeholder"
    
    async def _call_claude(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """调用Claude API"""
        # TODO: 实现Claude API调用
        # response = await self.claude_client.messages.create(
        #     model=self.config.get("claude_model", "claude-opus-4.5"),
        #     messages=messages,
        #     temperature=temperature,
        #     max_tokens=max_tokens
        # )
        # return response.content[0].text
        logger.info(f"[Claude] Calling with {len(messages)} messages")
        return "Claude response placeholder"
    
    async def extract_entities(
        self, 
        text: str,
        entity_types: List[str]
    ) -> Dict[str, List[Any]]:
        """实体提取专用接口 (使用DeepSeek)
        
        Args:
            text: 待提取的文本
            entity_types: ["Gene", "Variant", "Method", "Evidence"]
        
        Returns:
            {"genes": [...], "variants": [...], ...}
        """
        prompt = f"""Extract the following entities from the biomedical text:
Entity types: {', '.join(entity_types)}

Text:
{text}

Return a JSON object with entity types as keys and lists of entities as values.
"""
        
        messages = [
            {"role": "system", "content": "You are a biomedical entity extraction expert."},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat_completion(
            messages=messages,
            provider=LLMProvider.DEEPSEEK,
            temperature=0.3  # 低温度以提高准确性
        )
        
        # TODO: 解析JSON响应
        logger.info(f"[DeepSeek] Extracted entities from {len(text)} chars")
        return {}
    
    async def verify_evidence(
        self, 
        evidence_text: str,
        variant_info: Dict[str, str]
    ) -> Dict[str, Any]:
        """证据验证专用接口 (使用DeepSeek)
        
        Returns:
            {
                "is_valid": true/false,
                "strength": "Strong/Moderate/Weak",
                "confidence_score": 0.95,
                "reason": "..."
            }
        """
        prompt = f"""Verify if the following evidence supports the functional impact of the variant:

Variant: {variant_info.get('gene_symbol')} {variant_info.get('cdna_change')}

Evidence:
{evidence_text}

Evaluate:
1. Does this evidence demonstrate functional impact?
2. What is the strength of evidence? (Strong/Moderate/Weak)
3. Confidence score (0-1)
4. Brief reasoning

Return as JSON.
"""
        
        messages = [
            {"role": "system", "content": "You are an ACMG variant interpretation expert."},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat_completion(
            messages=messages,
            provider=LLMProvider.DEEPSEEK,
            temperature=0.5
        )
        
        # TODO: 解析JSON响应
        logger.info(f"[DeepSeek] Verified evidence for {variant_info}")
        return {}
    
    async def generate_final_rating(
        self, 
        evidence_summary: List[Dict[str, Any]],
        gene_symbol: str,
        variant_id: str
    ) -> Dict[str, Any]:
        """生成最终ACMG-PS3评级 (使用Claude仲裁)
        
        这是高风险决策，使用Claude Opus 4.5进行最终仲裁
        
        Returns:
            {
                "rating": "PS3_Strong | PS3_Moderate | PS3_Supporting | Insufficient",
                "confidence": 0.92,
                "reasoning": "...",
                "model_used": "claude-opus-4.5"
            }
        """
        prompt = f"""As an ACMG variant classification arbiter, provide the final PS3 (functional evidence) rating.

Gene: {gene_symbol}
Variant: {variant_id}

Evidence Summary:
{self._format_evidence_summary(evidence_summary)}

Based on ACMG guidelines, determine:
1. PS3 Rating: PS3_Strong | PS3_Moderate | PS3_Supporting | Insufficient
2. Confidence score (0-1)
3. Detailed reasoning
4. Any conflicting evidence concerns

Return as structured JSON.
"""
        
        messages = [
            {"role": "system", "content": "You are a senior clinical geneticist making ACMG PS3 classification decisions."},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat_completion(
            messages=messages,
            provider=LLMProvider.CLAUDE,  # 使用Claude仲裁
            temperature=0.3,
            max_tokens=3000
        )
        
        # TODO: 解析JSON响应
        logger.info(f"[Claude Arbiter] Generated final rating for {gene_symbol} {variant_id}")
        return {
            "model_used": "claude-opus-4.5",
            "role": "arbiter"
        }
    
    async def text_to_cypher(
        self, 
        natural_query: str,
        schema_info: Dict[str, Any]
    ) -> str:
        """自然语言转Cypher查询 (使用DeepSeek)
        
        Args:
            natural_query: "Find all evidence for ASS1 c.1168G>A"
            schema_info: Neo4j图谱的schema信息
        
        Returns:
            Cypher查询语句
        """
        prompt = f"""Convert the natural language query to a Neo4j Cypher query.

Graph Schema:
{self._format_schema(schema_info)}

Query: {natural_query}

Return only the Cypher query, no explanation.
"""
        
        messages = [
            {"role": "system", "content": "You are a Neo4j Cypher query expert."},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat_completion(
            messages=messages,
            provider=LLMProvider.DEEPSEEK,
            temperature=0.2
        )
        
        logger.info(f"[DeepSeek] Generated Cypher for: {natural_query}")
        return response
    
    async def dual_llm_consensus(
        self,
        task: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """双LLM共识机制
        
        对于复杂或有争议的决策，使用两个LLM并比较结果:
        1. DeepSeek给出初步评估
        2. Claude进行独立评估
        3. 如果一致，采用共识结果
        4. 如果不一致，Claude作为仲裁者做最终决策
        """
        # 1. DeepSeek初步评估
        deepseek_result = await self._evaluate_task(task, context, LLMProvider.DEEPSEEK)
        
        # 2. Claude独立评估
        claude_result = await self._evaluate_task(task, context, LLMProvider.CLAUDE)
        
        # 3. 比较结果
        if self._results_agree(deepseek_result, claude_result):
            logger.info("[Consensus] Both models agree")
            return {
                "consensus": True,
                "result": deepseek_result,
                "deepseek": deepseek_result,
                "claude": claude_result
            }
        else:
            logger.warning("[Disagreement] Models disagree, Claude arbitrating")
            return {
                "consensus": False,
                "final_decision": claude_result,  # Claude仲裁
                "deepseek": deepseek_result,
                "claude": claude_result,
                "arbiter": "claude"
            }
    
    async def _evaluate_task(
        self, 
        task: str, 
        context: Dict[str, Any], 
        provider: LLMProvider
    ) -> Dict[str, Any]:
        """评估任务"""
        # TODO: 实现具体的评估逻辑
        pass
    
    def _results_agree(self, result1: Dict, result2: Dict) -> bool:
        """判断两个结果是否一致"""
        # TODO: 实现结果比较逻辑
        return False
    
    def _format_evidence_summary(self, evidence: List[Dict[str, Any]]) -> str:
        """格式化证据摘要"""
        # TODO: 格式化证据列表
        return str(evidence)
    
    def _format_schema(self, schema: Dict[str, Any]) -> str:
        """格式化图谱schema"""
        # TODO: 格式化schema信息
        return str(schema)
