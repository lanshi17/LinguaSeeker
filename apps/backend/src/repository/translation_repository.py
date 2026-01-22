"""翻译仓储 - 处理翻译任务的数据库操作"""

import json
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from src.domain.entities.translation import (
    DocumentLanguage,
    TranslationStatus,
    TranslationTask,
)
from src.utils.exceptions import DatabaseException

logger = logging.getLogger(__name__)


class TranslationRepository:
    """翻译任务的数据库仓储类"""

    def __init__(self, db_connection: Optional[any] = None):
        """初始化翻译仓储

        Args:
            db_connection: 数据库连接对象（如postgresql连接池）
        """
        self.db_connection = db_connection
        self.table_name = "translation_tasks"
        self._init_table()

    def _init_table(self):
        """初始化数据库表（如果不存在）"""
        try:
            if self.db_connection:
                # 创建翻译任务表
                create_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    original_filename VARCHAR(500) NOT NULL,
                    original_file_size INTEGER NOT NULL,
                    original_file_hash VARCHAR(64),
                    minio_path TEXT,

                    detected_language VARCHAR(10),
                    source_language VARCHAR(10),
                    target_language VARCHAR(10) DEFAULT 'en',

                    original_text TEXT,
                    translated_text TEXT,
                    character_count INTEGER,

                    status VARCHAR(20) DEFAULT 'pending',
                    progress FLOAT DEFAULT 0.0,
                    error_message TEXT,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,

                    metadata JSONB DEFAULT '{{}}'
                );

                -- 创建索引
                CREATE INDEX IF NOT EXISTS idx_user_id ON {self.table_name}(user_id);
                CREATE INDEX IF NOT EXISTS idx_status ON {self.table_name}(status);
                CREATE INDEX IF NOT EXISTS idx_created_at ON {self.table_name}(created_at);
                CREATE INDEX IF NOT EXISTS idx_user_status ON {self.table_name}(user_id, status);
                """

                with self.db_connection.cursor() as cursor:
                    cursor.execute(create_table_sql)
                logger.info(f"翻译任务表 {self.table_name} 已初始化")
        except Exception as e:
            logger.warning(f"初始化翻译任务表失败: {e}")
            # 如果是开发环境，可以继续使用内存缓存

    async def save_translation_task(self, task: TranslationTask) -> TranslationTask:
        """保存翻译任务到数据库

        Args:
            task: 翻译任务实体

        Returns:
            TranslationTask: 保存后的任务实体
        """
        try:
            if not self.db_connection:
                logger.warning("数据库连接不可用，任务将仅在内存中保存")
                return task

            # 准备SQL和数据
            sql = f"""
            INSERT INTO {self.table_name} (
                id, user_id, original_filename, original_file_size, original_file_hash,
                minio_path, detected_language, source_language, target_language,
                original_text, translated_text, character_count, status, progress,
                error_message, created_at, updated_at, started_at, completed_at, metadata
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                original_filename = EXCLUDED.original_filename,
                original_file_size = EXCLUDED.original_file_size,
                original_file_hash = EXCLUDED.original_file_hash,
                minio_path = EXCLUDED.minio_path,
                detected_language = EXCLUDED.detected_language,
                source_language = EXCLUDED.source_language,
                target_language = EXCLUDED.target_language,
                original_text = EXCLUDED.original_text,
                translated_text = EXCLUDED.translated_text,
                character_count = EXCLUDED.character_count,
                status = EXCLUDED.status,
                progress = EXCLUDED.progress,
                error_message = EXCLUDED.error_message,
                updated_at = EXCLUDED.updated_at,
                started_at = EXCLUDED.started_at,
                completed_at = EXCLUDED.completed_at,
                metadata = EXCLUDED.metadata
            """

            # 准备数据
            data = (
                task.id,
                task.user_id,
                task.original_filename,
                task.original_file_size,
                task.original_file_hash,
                task.minio_path,
                task.detected_language.value if task.detected_language else None,
                task.source_language,
                task.target_language.value,
                task.original_text,
                task.translated_text,
                task.character_count,
                task.status.value,
                task.progress,
                task.error_message,
                task.created_at,
                task.updated_at,
                task.started_at,
                task.completed_at,
                json.dumps(task.metadata),  # 将字典转换为JSON字符串
            )

            with self.db_connection.cursor() as cursor:
                cursor.execute(sql, data)
            self.db_connection.commit()

            logger.debug(f"翻译任务已保存到数据库: {task.id}")
            return task

        except Exception as e:
            logger.error(f"保存翻译任务失败: {e}")
            raise DatabaseException(f"保存翻译任务失败: {str(e)}")

    async def get_translation_task(self, task_id: str) -> Optional[TranslationTask]:
        """根据ID获取翻译任务

        Args:
            task_id: 任务ID

        Returns:
            Optional[TranslationTask]: 翻译任务实体，如果不存在返回None
        """
        try:
            if not self.db_connection:
                return None

            sql = f"""
            SELECT
                id, user_id, original_filename, original_file_size, original_file_hash,
                minio_path, detected_language, source_language, target_language,
                original_text, translated_text, character_count, status, progress,
                error_message, created_at, updated_at, started_at, completed_at, metadata
            FROM {self.table_name}
            WHERE id = %s
            """

            with self.db_connection.cursor() as cursor:
                cursor.execute(sql, (task_id,))
                row = cursor.fetchone()

            if not row:
                return None

            # 将数据库行转换为TranslationTask实体
            return await self._row_to_task(row)

        except Exception as e:
            logger.error(f"获取翻译任务失败: {e}")
            raise DatabaseException(f"获取翻译任务失败: {str(e)}")

    async def update_translation_task(self, task: TranslationTask) -> TranslationTask:
        """更新翻译任务

        Args:
            task: 要更新的翻译任务

        Returns:
            TranslationTask: 更新后的任务实体
        """
        try:
            if not self.db_connection:
                logger.warning("数据库连接不可用，任务更新将仅在内存中生效")
                return task

            sql = f"""
            UPDATE {self.table_name}
            SET
                original_filename = %s,
                original_file_size = %s,
                original_file_hash = %s,
                minio_path = %s,
                detected_language = %s,
                source_language = %s,
                target_language = %s,
                original_text = %s,
                translated_text = %s,
                character_count = %s,
                status = %s,
                progress = %s,
                error_message = %s,
                updated_at = %s,
                started_at = %s,
                completed_at = %s,
                metadata = %s
            WHERE id = %s
            """

            # 准备数据
            data = (
                task.original_filename,
                task.original_file_size,
                task.original_file_hash,
                task.minio_path,
                task.detected_language.value if task.detected_language else None,
                task.source_language,
                task.target_language.value,
                task.original_text,
                task.translated_text,
                task.character_count,
                task.status.value,
                task.progress,
                task.error_message,
                task.updated_at,
                task.started_at,
                task.completed_at,
                json.dumps(task.metadata),  # 将字典转换为JSON字符串
                task.id,
            )

            with self.db_connection.cursor() as cursor:
                cursor.execute(sql, data)
                if cursor.rowcount == 0:
                    raise DatabaseException(f"任务不存在: {task.id}")
            self.db_connection.commit()

            logger.debug(f"翻译任务已更新: {task.id}, 状态: {task.status}")
            return task

        except Exception as e:
            logger.error(f"更新翻译任务失败: {e}")
            raise DatabaseException(f"更新翻译任务失败: {str(e)}")

    async def list_translation_tasks(
        self,
        user_id: Optional[str] = None,
        status: Optional[TranslationStatus] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[TranslationTask]:
        """列出翻译任务

        Args:
            user_id: 用户ID（可选，用于过滤特定用户）
            status: 任务状态（可选，用于过滤特定状态）
            limit: 每页数量
            offset: 偏移量

        Returns:
            List[TranslationTask]: 翻译任务列表
        """
        try:
            if not self.db_connection:
                return []

            # 构建查询条件
            conditions = []
            params = []

            if user_id:
                conditions.append("user_id = %s")
                params.append(user_id)

            if status:
                conditions.append("status = %s")
                params.append(status.value)

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            sql = f"""
            SELECT
                id, user_id, original_filename, original_file_size, original_file_hash,
                minio_path, detected_language, source_language, target_language,
                original_text, translated_text, character_count, status, progress,
                error_message, created_at, updated_at, started_at, completed_at, metadata
            FROM {self.table_name}
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """

            params.extend([limit, offset])

            tasks = []
            with self.db_connection.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                rows = cursor.fetchall()

                for row in rows:
                    task = await self._row_to_task(row)
                    if task:
                        tasks.append(task)

            logger.debug(f"查询到 {len(tasks)} 个翻译任务")
            return tasks

        except Exception as e:
            logger.error(f"列出翻译任务失败: {e}")
            raise DatabaseException(f"列出翻译任务失败: {str(e)}")

    async def _row_to_task(self, row) -> Optional[TranslationTask]:
        """将数据库行转换为TranslationTask实体

        Args:
            row: 数据库查询结果行

        Returns:
            Optional[TranslationTask]: 转换后的任务实体
        """
        try:
            # 解包数据库行
            (
                task_id,
                user_id,
                original_filename,
                original_file_size,
                original_file_hash,
                minio_path,
                detected_language,
                source_language,
                target_language,
                original_text,
                translated_text,
                character_count,
                status,
                progress,
                error_message,
                created_at,
                updated_at,
                started_at,
                completed_at,
                metadata,
            ) = row

            # 创建任务实体
            task = TranslationTask(
                id=task_id,
                user_id=user_id,
                original_filename=original_filename,
                original_file_size=original_file_size or 0,
                original_file_hash=original_file_hash,
                minio_path=minio_path,
                detected_language=DocumentLanguage(detected_language)
                if detected_language
                else None,
                source_language=source_language,
                target_language=DocumentLanguage(target_language),
                original_text=original_text,
                translated_text=translated_text,
                character_count=character_count,
                status=TranslationStatus(status),
                progress=progress or 0.0,
                error_message=error_message,
                created_at=created_at,
                updated_at=updated_at or datetime.now(),
                started_at=started_at,
                completed_at=completed_at,
                metadata=json.loads(metadata) if isinstance(metadata, str) else (metadata or {}),
            )

            return task

        except Exception as e:
            logger.error(f"转换数据库行为任务实体失败: {e}")
            return None

    async def get_task_count(
        self, user_id: Optional[str] = None, status: Optional[TranslationStatus] = None
    ) -> int:
        """获取任务数量统计

        Args:
            user_id: 用户ID（可选）
            status: 任务状态（可选）

        Returns:
            int: 任务数量
        """
        try:
            if not self.db_connection:
                return 0

            conditions = []
            params = []

            if user_id:
                conditions.append("user_id = %s")
                params.append(user_id)

            if status:
                conditions.append("status = %s")
                params.append(status.value)

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            sql = f"SELECT COUNT(*) FROM {self.table_name} {where_clause}"

            with self.db_connection.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                result = cursor.fetchone()
                return result[0] if result else 0

        except Exception as e:
            logger.error(f"获取任务数量失败: {e}")
            return 0

    async def delete_translation_task(self, task_id: str) -> bool:
        """删除翻译任务

        Args:
            task_id: 要删除的任务ID

        Returns:
            bool: 是否删除成功
        """
        try:
            if not self.db_connection:
                return False

            sql = f"DELETE FROM {self.table_name} WHERE id = %s"

            with self.db_connection.cursor() as cursor:
                cursor.execute(sql, (task_id,))
                affected_rows = cursor.rowcount
            self.db_connection.commit()

            success = affected_rows > 0
            if success:
                logger.info(f"翻译任务已删除: {task_id}")
            else:
                logger.warning(f"删除翻译任务失败，任务不存在: {task_id}")

            return success

        except Exception as e:
            logger.error(f"删除翻译任务失败: {e}")
            raise DatabaseException(f"删除翻译任务失败: {str(e)}")
