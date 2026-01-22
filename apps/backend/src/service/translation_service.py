"""翻译服务 - 处理PDF文档的翻译功能

主要功能：
1. PDF文档解析和文本提取
2. 语言检测和识别
3. LLM翻译调用
4. 翻译任务管理
"""

import asyncio
import hashlib
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.domain.entities.translation import (
    DocumentLanguage,
    TranslationStatus,
    TranslationTask,
)
from src.utils.logger import Logger

from ..utils.exceptions import TranslationError

logger = logging.getLogger(__name__)


class TranslationService:
    """翻译服务类"""

    def __init__(
        self,
        mineru_service=None,
        llm_service=None,
        minio_service=None,
        database_repository=None,
    ):
        """初始化翻译服务

        Args:
            mineru_service: PDF解析服务（MinerU）
            llm_service: LLM翻译服务
            minio_service: 文件存储服务
            database_repository: 数据库仓储
        """
        self.mineru_service = mineru_service
        self.llm_service = llm_service
        self.minio_service = minio_service
        self.database_repository = database_repository
        self.logger = Logger.get_logger("TranslationService")

    async def create_translation_task(
        self,
        user_id: str,
        file_content: bytes,
        filename: str,
        target_language: DocumentLanguage = DocumentLanguage.ENGLISH,
        source_language: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TranslationTask:
        """创建翻译任务

        Args:
            user_id: 用户ID
            file_content: 文件内容（字节）
            filename: 文件名
            target_language: 目标语言
            source_language: 指定原语言（可选，自动检测）
            metadata: 扩展元数据

        Returns:
            TranslationTask: 翻译任务实体
        """
        try:
            # 计算文件哈希
            file_hash = hashlib.sha256(file_content).hexdigest()
            file_size = len(file_content)

            # 保存文件到MinIO
            minio_path = await self._save_to_minio(file_content, filename, user_id)

            # 创建任务实体
            task = TranslationTask(
                user_id=user_id,
                original_filename=filename,
                original_file_size=file_size,
                original_file_hash=file_hash,
                minio_path=minio_path,
                target_language=target_language,
                source_language=source_language,
                metadata=metadata or {},
            )

            # 保存到数据库
            if self.database_repository:
                await self.database_repository.save_translation_task(task)

            self.logger.info(f"创建翻译任务: {task.id}, 用户: {user_id}, 文件: {filename}")
            return task

        except Exception as e:
            self.logger.error(f"创建翻译任务失败: {e}")
            raise TranslationError(f"创建翻译任务失败: {str(e)}")

    async def _save_to_minio(self, file_content: bytes, filename: str, user_id: str) -> str:
        """保存文件到MinIO

        Args:
            file_content: 文件内容
            filename: 文件名
            user_id: 用户ID

        Returns:
            str: MinIO存储路径
        """
        if not self.minio_service:
            # 如果没有MinIO服务，使用临时文件路径
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
                tmp.write(file_content)
                return tmp.name

        try:
            # 构造存储路径: translations/{user_id}/{timestamp}_{filename}
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            minio_path = f"translations/{user_id}/{timestamp}_{filename}"

            # 上传到MinIO
            await self.minio_service.upload_file(
                bucket_name="documents",
                object_path=minio_path,
                file_content=file_content,
                content_type="application/pdf",
            )

            self.logger.debug(f"文件已保存到MinIO: {minio_path}")
            return minio_path

        except Exception as e:
            self.logger.error(f"保存到MinIO失败: {e}")
            # 如果MinIO失败，使用临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
                tmp.write(file_content)
                return tmp.name

    async def process_translation_task(self, task_id: str) -> TranslationTask:
        """处理翻译任务

        Args:
            task_id: 任务ID

        Returns:
            TranslationTask: 更新后的任务
        """
        # 从数据库获取任务
        if not self.database_repository:
            raise TranslationError("数据库仓储未初始化，无法处理翻译任务")
            
        task = await self.database_repository.get_translation_task(task_id)
        if not task:
            raise TranslationError(f"任务不存在: {task_id}")

        try:
            task.mark_started()
            task.update_progress(10, TranslationStatus.PROCESSING)
            await self.database_repository.update_translation_task(task)

            # 步骤1: 解析PDF文档
            self.logger.info(f"开始解析PDF: {task.original_filename}")
            extracted_text = await self._extract_pdf_text(task)
            task.original_text = extracted_text
            task.character_count = len(extracted_text)
            task.update_progress(30, TranslationStatus.PROCESSING)
            await self.database_repository.update_translation_task(task)

            # 步骤2: 检测语言
            self.logger.info(f"检测文档语言")
            detected_lang = await self._detect_language(extracted_text)
            task.detected_language = detected_lang
            task.update_progress(40)
            await self.database_repository.update_translation_task(task)

            # 步骤3: 判断是否需要翻译
            if detected_lang == task.target_language:
                # 如果文档已经是目标语言，直接返回原文本
                self.logger.info(f"文档已是目标语言({detected_lang.value})，无需翻译")
                task.translated_text = extracted_text
                task.mark_completed()
                await self.database_repository.update_translation_task(task)
                return task

            # 步骤4: 开始翻译
            task.update_progress(50, TranslationStatus.TRANSLATING)
            await self.database_repository.update_translation_task(task)

            self.logger.info(f"开始翻译: {detected_lang.value} -> {task.target_language.value}")
            translated_text = await self._translate_text(
                extracted_text, detected_lang, task.target_language
            )
            task.translated_text = translated_text
            task.update_progress(90)
            await self.database_repository.update_translation_task(task)

            # 步骤5: 保存翻译结果
            if self.minio_service:
                await self._save_translated_text(task, translated_text)

            # 步骤6: 标记完成
            task.mark_completed()
            await self.database_repository.update_translation_task(task)

            self.logger.info(f"翻译任务完成: {task.id}")
            return task

        except Exception as e:
            self.logger.error(f"处理翻译任务失败: {e}", exc_info=True)
            task.mark_failed(str(e))
            await self.database_repository.update_translation_task(task)
            raise TranslationError(f"翻译任务处理失败: {str(e)}")

    async def _extract_pdf_text(self, task: TranslationTask) -> str:
        """从PDF提取文本

        Args:
            task: 翻译任务

        Returns:
            str: 提取的文本内容
        """
        if self.mineru_service and self.minio_service:
            # 使用MinerU解析PDF
            try:
                # 从MinIO获取文件
                file_content = await self.minio_service.download_file(
                    bucket_name="documents", object_path=task.minio_path
                )
                # 调用MinerU解析
                result = await self.mineru_service.parse_pdf(file_content)
                return result.get("text", "") or result.get("content", "")
            except Exception as e:
                self.logger.warning(f"MinerU解析失败，尝试备用方案: {e}")

        # 备用方案: 使用PyPDF2或pdfplumber
        try:
            # 导入备用PDF解析库
            import pdfplumber

            # 从临时文件或MinIO下载
            if task.minio_path.startswith("/tmp") or task.minio_path.startswith("temp"):
                pdf_path = task.minio_path
            else:
                # 下载到临时文件
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    if self.minio_service:
                        file_content = await self.minio_service.download_file(
                            bucket_name="documents", object_path=task.minio_path
                        )
                    else:
                        # MinIO不可用，直接使用保存的路径
                        with open(task.minio_path, 'rb') as f:
                            file_content = f.read()
                    tmp.write(file_content)
                    pdf_path = tmp.name

            # 使用pdfplumber提取文本
            text_parts = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

            return "\n\n".join(text_parts)

        except ImportError:
            self.logger.warning("pdfplumber未安装，无法解析PDF")
            raise TranslationError("PDF解析服务不可用")

    async def _detect_language(self, text: str) -> DocumentLanguage:
        """检测文本语言

        Args:
            text: 文本内容

        Returns:
            DocumentLanguage: 检测到的语言
        """
        # 使用langdetect库进行语言检测
        try:
            from langdetect import DetectorFactory, LangDetectException, detect

            # 设置种子以确保一致性
            DetectorFactory.seed = 0

            if not text or len(text.strip()) < 10:
                return DocumentLanguage.OTHER

            try:
                lang_code = detect(text)
            except LangDetectException:
                return DocumentLanguage.OTHER

            # 映射到我们的语言枚举
            lang_map = {
                "en": DocumentLanguage.ENGLISH,
                "zh-cn": DocumentLanguage.CHINESE,
                "zh-tw": DocumentLanguage.CHINESE,
                "ja": DocumentLanguage.JAPANESE,
                "ko": DocumentLanguage.KOREAN,
                "fr": DocumentLanguage.FRENCH,
                "de": DocumentLanguage.GERMAN,
                "es": DocumentLanguage.SPANISH,
                "ru": DocumentLanguage.RUSSIAN,
                "ar": DocumentLanguage.ARABIC,
                "pt": DocumentLanguage.PORTUGUESE,
                "it": DocumentLanguage.ITALIAN,
                "nl": DocumentLanguage.DUTCH,
                "sv": DocumentLanguage.SWEDISH,
            }

            return lang_map.get(lang_code, DocumentLanguage.OTHER)

        except ImportError:
            self.logger.warning("langdetect未安装，使用简单检测")

            # 简单检测：基于字符范围
            # 检测英文
            if all(ord(c) < 128 for c in text[:100]):
                return DocumentLanguage.ENGLISH

            # 检测中文（包含中文标点）
            chinese_chars = sum(1 for c in text[:100] if "\u4e00" <= c <= "\u9fff")
            if chinese_chars > 10:
                return DocumentLanguage.CHINESE

            # 检测日语
            japanese_chars = sum(
                1
                for c in text[:100]
                if (
                    "\u3040" <= c <= "\u309f"  # 平假名
                    or "\u30a0" <= c <= "\u30ff"  # 片假名
                    or "\u4e00" <= c <= "\u9fff"  # 汉字
                )
            )
            if japanese_chars > 10:
                return DocumentLanguage.JAPANESE

            return DocumentLanguage.OTHER

    async def _translate_text(
        self,
        text: str,
        source_lang: DocumentLanguage,
        target_lang: DocumentLanguage,
    ) -> str:
        """使用LLM翻译文本

        Args:
            text: 要翻译的文本
            source_lang: 原语言
            target_lang: 目标语言

        Returns:
            str: 翻译后的文本
        """
        if not self.llm_service:
            raise TranslationError("LLM服务不可用")

        # 准备翻译提示词
        source_lang_name = source_lang.value.upper()
        target_lang_name = target_lang.value.upper()

        system_prompt = f"""你是一个专业的文档翻译助手。请将{source_lang_name}文档翻译成{target_lang_name}。

翻译要求：
1. 保持原文的专业术语和语义准确性
2. 保持文档的格式和结构
3. 确保翻译自然流畅，符合{target_lang_name}的表达习惯
4. 保留数字、专有名词、技术术语
5. 不要添加任何解释或额外内容

请只返回翻译后的文本，不要添加任何说明。"""

        user_message = f"请翻译以下{source_lang_name}文档：\n\n{text[:30000]}"  # 限制长度

        try:
            # 调用LLM服务
            response = await self.llm_service.generate_translation(
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=len(text) * 2,  # 预留足够空间
                temperature=0.1,  # 低温度确保准确性
            )

            self.logger.info(f"翻译完成，源文本长度: {len(text)}，翻译长度: {len(response)}")
            return response

        except Exception as e:
            self.logger.error(f"LLM翻译失败: {e}")
            raise TranslationError(f"翻译失败: {str(e)}")

    async def _save_translated_text(self, task: TranslationTask, translated_text: str):
        """保存翻译结果到MinIO

        Args:
            task: 翻译任务
            translated_text: 翻译后的文本
        """
        if not self.minio_service:
            self.logger.warning("MinIO服务不可用，无法保存翻译结果")
            return
            
        try:
            # 生成翻译文件名
            filename_stem = Path(task.original_filename).stem
            translated_filename = f"{filename_stem}_translated.txt"

            # 生成MinIO路径
            user_part = task.minio_path.split("/")[1] if "/" in task.minio_path else "translations"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            minio_path = f"{user_part}/translated/{timestamp}_{translated_filename}"

            # 上传到MinIO
            await self.minio_service.upload_file(
                bucket_name="documents",
                object_path=minio_path,
                file_content=translated_text.encode("utf-8"),
                content_type="text/plain; charset=utf-8",
            )

            # 更新任务的元数据
            if "translated_files" not in task.metadata:
                task.metadata["translated_files"] = []
            task.metadata["translated_files"].append(
                {
                    "filename": translated_filename,
                    "minio_path": minio_path,
                    "size": len(translated_text.encode("utf-8")),
                }
            )

            self.logger.debug(f"翻译结果已保存到MinIO: {minio_path}")

        except Exception as e:
            self.logger.error(f"保存翻译结果失败: {e}")

    async def get_task_status(self, task_id: str) -> TranslationTask:
        """获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            TranslationTask: 任务实体
        """
        if not self.database_repository:
            raise TranslationError("数据库服务不可用")

        task = await self.database_repository.get_translation_task(task_id)
        if not task:
            raise TranslationError(f"任务不存在: {task_id}")

        return task

    async def list_user_tasks(
        self, user_id: str, limit: int = 10, offset: int = 0
    ) -> List[TranslationTask]:
        """获取用户的翻译任务列表

        Args:
            user_id: 用户ID
            limit: 每页数量
            offset: 偏移量

        Returns:
            List[TranslationTask]: 任务列表
        """
        if not self.database_repository:
            return []

        return await self.database_repository.list_translation_tasks(
            user_id=user_id, limit=limit, offset=offset
        )

    async def cancel_task(self, task_id: str) -> bool:
        """取消翻译任务

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功取消
        """
        if not self.database_repository:
            return False

        task = await self.database_repository.get_translation_task(task_id)
        if not task:
            return False

        # 只能取消待处理或处理中的任务
        if task.status in (TranslationStatus.PENDING, TranslationStatus.PROCESSING):
            task.status = TranslationStatus.FAILED
            task.error_message = "用户取消"
            task.updated_at = datetime.now()
            await self.database_repository.update_translation_task(task)
            return True

        return False
