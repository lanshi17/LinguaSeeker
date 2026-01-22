"""翻译相关的领域模型"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TranslationStatus(str, Enum):
    """翻译任务状态枚举"""

    PENDING = "pending"
    PROCESSING = "processing"
    TRANSLATING = "translating"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentLanguage(str, Enum):
    """文档语言枚举"""

    ENGLISH = "en"
    CHINESE = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    FRENCH = "fr"
    GERMAN = "de"
    SPANISH = "es"
    RUSSIAN = "ru"
    ARABIC = "ar"
    PORTUGUESE = "pt"
    ITALIAN = "it"
    DUTCH = "nl"
    SWEDISH = "sv"
    OTHER = "other"


class TranslationTask(BaseModel):
    """翻译任务实体"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = Field(..., description="用户ID")
    original_filename: str = Field(..., description="原始文件名")
    original_file_size: int = Field(..., description="原始文件大小(字节)")
    original_file_hash: str = Field(..., description="原始文件哈希")
    minio_path: str = Field(..., description="MinIO存储路径")

    # 语言信息
    detected_language: Optional[DocumentLanguage] = Field(None, description="检测到的原语言")
    source_language: Optional[str] = Field(None, description="用户指定的原语言")
    target_language: DocumentLanguage = Field(
        default=DocumentLanguage.ENGLISH, description="目标语言"
    )

    # 内容信息
    original_text: Optional[str] = Field(None, description="原始文档文本内容")
    translated_text: Optional[str] = Field(None, description="翻译后的文本内容")
    character_count: Optional[int] = Field(None, description="字符数统计")

    # 状态信息
    status: TranslationStatus = Field(default=TranslationStatus.PENDING, description="任务状态")
    progress: float = Field(default=0.0, description="进度百分比(0-100)")
    error_message: Optional[str] = Field(None, description="错误信息")

    # 时间信息
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    started_at: Optional[datetime] = Field(None, description="开始处理时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    def model_dump(self, *args, **kwargs):
        """重写序列化方法，处理枚举值"""
        data = super().model_dump(*args, **kwargs)
        # 确保枚举值被序列化为字符串
        if self.detected_language:
            data["detected_language"] = self.detected_language.value
        data["target_language"] = self.target_language.value
        data["status"] = self.status.value
        return data

    def update_progress(self, progress: float, status: Optional[TranslationStatus] = None):
        """更新任务进度"""
        self.progress = progress
        if status:
            self.status = status
        self.updated_at = datetime.now()

    def mark_started(self):
        """标记任务开始"""
        self.started_at = datetime.now()
        self.status = TranslationStatus.PROCESSING
        self.updated_at = datetime.now()

    def mark_completed(self, translated_text: str = None):
        """标记任务完成"""
        if translated_text:
            self.translated_text = translated_text
        self.completed_at = datetime.now()
        self.status = TranslationStatus.COMPLETED
        self.progress = 100.0
        self.updated_at = datetime.now()

    def mark_failed(self, error_message: str):
        """标记任务失败"""
        self.error_message = error_message
        self.status = TranslationStatus.FAILED
        self.updated_at = datetime.now()

    def is_completed(self) -> bool:
        """检查任务是否完成"""
        return self.status == TranslationStatus.COMPLETED

    def is_failed(self) -> bool:
        """检查任务是否失败"""
        return self.status == TranslationStatus.FAILED


class TranslationResponse(BaseModel):
    """翻译响应模型"""

    task_id: str = Field(..., description="任务ID")
    user_id: str = Field(..., description="用户ID")
    original_filename: str = Field(..., description="原始文件名")
    detected_language: Optional[str] = Field(None, description="检测到的原语言")
    target_language: str = Field(..., description="目标语言")
    status: str = Field(..., description="任务状态")
    progress: float = Field(..., description="进度百分比")
    character_count: Optional[int] = Field(None, description="字符数统计")
    created_at: datetime = Field(..., description="创建时间")

    # 下载链接
    original_file_url: Optional[str] = Field(None, description="原始文件下载链接")
    translated_file_url: Optional[str] = Field(None, description="翻译文件下载链接")

    # 预览内容（仅提供前500字符）
    preview_original: Optional[str] = Field(None, description="原始文本预览")
    preview_translated: Optional[str] = Field(None, description="翻译文本预览")

    # 翻译统计
    translation_time_ms: Optional[int] = Field(None, description="翻译耗时(毫秒)")
    cost_estimate: Optional[float] = Field(None, description="成本估算")

    @classmethod
    def from_task(
        cls, task: TranslationTask, original_url: str = None, translated_url: str = None
    ) -> "TranslationResponse":
        """从任务实体创建响应模型"""
        preview_original = (
            task.original_text[:500] + "..."
            if task.original_text and len(task.original_text) > 500
            else task.original_text
        )
        preview_translated = (
            task.translated_text[:500] + "..."
            if task.translated_text and len(task.translated_text) > 500
            else task.translated_text
        )

        # 计算翻译耗时
        translation_time = None
        if task.started_at and task.completed_at:
            translation_time = int((task.completed_at - task.started_at).total_seconds() * 1000)

        return cls(
            task_id=task.id,
            user_id=task.user_id,
            original_filename=task.original_filename,
            detected_language=task.detected_language.value if task.detected_language else None,
            target_language=task.target_language.value,
            status=task.status.value,
            progress=task.progress,
            character_count=task.character_count,
            created_at=task.created_at,
            original_file_url=original_url,
            translated_file_url=translated_url,
            preview_original=preview_original,
            preview_translated=preview_translated,
            translation_time_ms=translation_time,
            cost_estimate=task.character_count * 0.00002
            if task.character_count
            else None,  # 估算成本
        )
