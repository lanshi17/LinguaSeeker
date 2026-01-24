"""
DDD架构重构 - 端到端测试
测试所有重构后的组件和层次依赖关系
"""
import pytest
from pathlib import Path


class TestDomainLayer:
    """Domain层测试 - 值对象、实体、仓储接口"""
    
    def test_odds_path_immutability(self):
        """测试OddsPath值对象不可变性"""
        from src.domain.value_objects.odds_path import OddsPath
        
        odds = OddsPath(p1=0.1, p2=0.8)
        
        # 验证计算正确
        assert odds.value > 0
        assert odds.p1 == 0.1
        assert odds.p2 == 0.8
        
        # 验证不可变性
        with pytest.raises(Exception):  # FrozenInstanceError
            odds.p1 = 0.2
    
    def test_odds_path_strength_classification(self):
        """测试OddsPath强度分类"""
        from src.domain.value_objects.odds_path import OddsPath, EvidenceStrength
        
        # Supporting (>= 2)
        odds1 = OddsPath(p1=0.3, p2=0.5)
        assert odds1.strength == EvidenceStrength.SUPPORTING
        
        # Strong (>= 18)
        odds2 = OddsPath(p1=0.05, p2=0.5)
        assert odds2.strength == EvidenceStrength.STRONG
    
    def test_arbiter_feedback_immutability(self):
        """测试ArbiterFeedback值对象不可变性"""
        from src.domain.value_objects.arbiter_feedback import (
            ArbiterFeedback, DimensionScore
        )
        
        dim = DimensionScore(
            name="test",
            score=90.0,
            max_score=100.0,
            status="pass",
            reason="OK",
            suggestions=("s1", "s2")
        )
        
        # 验证tuple类型
        assert isinstance(dim.suggestions, tuple)
        
        # 验证不可变性
        with pytest.raises(Exception):
            dim.score = 95.0
        
        feedback = ArbiterFeedback(
            overall_score=85.0,
            dimensions=(dim,),
            key_issues=("issue1",),
            recommendations=("rec1",)
        )
        
        assert isinstance(feedback.dimensions, tuple)
        assert isinstance(feedback.key_issues, tuple)
        assert feedback.overall_score == 85.0
    
    def test_document_entity_encapsulation(self):
        """测试Document实体封装性"""
        from src.domain.entities.document import Document
        from src.domain.value_objects.language import Language
        
        doc = Document(
            original_path="test.pdf",
            detected_language=Language.CHINESE,
            english_content="Test content"
        )
        
        # 验证属性访问
        assert doc.original_path == "test.pdf"
        assert doc.detected_language == Language.CHINESE
        assert doc.english_content == "Test content"
        
        # 验证业务规则方法
        assert not doc.is_highlighted()
        
        # 验证highlight功能
        doc.highlight_evidence(["Test"])
        assert doc.is_highlighted()
        assert doc.highlighted_content is not None
        assert "==Test==" in doc.highlighted_content
    
    def test_document_bbox_fragments(self):
        """测试Document的bbox fragments功能"""
        from src.domain.entities.document import Document
        from src.domain.value_objects.language import Language
        
        bbox_data = [
            {"page": 0, "text": "test", "fragment_id": 1},
            {"page": 0, "text": "content", "fragment_id": 2}
        ]
        
        doc = Document(
            original_path="test.pdf",
            detected_language=Language.ENGLISH,
            english_content="test content",
            bbox_fragments=bbox_data
        )
        
        # 验证bbox_fragments返回副本（不可修改原数据）
        fragments = doc.bbox_fragments
        assert len(fragments) == 2
        fragments.append({"new": "data"})  # 修改副本不影响原数据
        assert len(doc.bbox_fragments) == 2  # 原数据未变
    
    def test_repository_interfaces_are_abstract(self):
        """测试Repository接口为抽象类"""
        import inspect
        from src.domain.repositories.pdf_repository import PDFRepository
        from src.domain.repositories.rag_repository import RAGRepository
        
        assert inspect.isabstract(PDFRepository)
        assert inspect.isabstract(RAGRepository)
        
        # 验证不能直接实例化
        with pytest.raises(TypeError):
            PDFRepository()
        
        with pytest.raises(TypeError):
            RAGRepository()
    
    def test_language_value_object(self):
        """测试Language值对象"""
        from src.domain.value_objects.language import Language
        
        assert Language.is_supported("zh")
        assert Language.is_supported("en")
        assert not Language.is_supported("xx")
        
        # 测试转换
        lang = Language.from_detected_code("zh-cn")
        assert lang == Language.CHINESE


class TestInfrastructureLayer:
    """Infrastructure层测试 - 仓储实现、导入更新"""
    
    def test_task_store_uses_presentation_schemas(self):
        """测试TaskStore使用presentation层的schemas"""
        from src.infrastructure.repositories.task_store import (
            InMemoryTaskStore, TaskRecord
        )
        from src.presentation.schemas import InputType, TaskStatus
        
        store = InMemoryTaskStore()
        record = store.create(
            input_type=InputType.PMID,
            value="12345678",
            project_tag="test"
        )
        
        assert record.task_id.startswith("task_")
        assert record.input_type == InputType.PMID
        assert record.status == TaskStatus.ACCEPTED
        assert record.value == "12345678"
    
    def test_task_store_operations(self):
        """测试TaskStore的CRUD操作"""
        from src.infrastructure.repositories.task_store import InMemoryTaskStore
        from src.presentation.schemas import InputType, TaskStatus
        
        store = InMemoryTaskStore()
        
        # Create
        record = store.create(InputType.DOI, "10.1234/test", None)
        task_id = record.task_id
        
        # Read
        retrieved = store.get(task_id)
        assert retrieved is not None
        assert retrieved.value == "10.1234/test"
        
        # Update
        updated = store.update(task_id, status=TaskStatus.SUCCESS)
        assert updated is not None
        assert updated.status == TaskStatus.SUCCESS
        
        # List
        all_tasks = store.list_all()
        assert task_id in all_tasks
    
    def test_pdf_repository_implementation(self):
        """测试PDFRepository实现正确继承接口"""
        from src.infrastructure.repositories.pdf_repository_impl import PDFRepositoryImpl
        from src.domain.repositories.pdf_repository import PDFRepository
        
        assert issubclass(PDFRepositoryImpl, PDFRepository)
        
        # 可以实例化实现类
        impl = PDFRepositoryImpl()
        assert impl is not None
    
    def test_rag_repository_implementation(self):
        """测试RAGRepository实现正确继承接口"""
        from src.infrastructure.repositories.rag_repository_impl import RAGRepositoryImpl
        from src.domain.repositories.rag_repository import RAGRepository
        
        assert issubclass(RAGRepositoryImpl, RAGRepository)


class TestPresentationLayer:
    """Presentation层测试 - schemas和api_services迁移"""
    
    def test_schemas_in_presentation_layer(self):
        """测试schemas在presentation层"""
        from src.presentation.schemas import (
            InputType, TaskStatus, EvidenceLevel,
            TaskSubmissionRequest, TaskStatusResponse
        )
        
        # 验证枚举可用
        assert InputType.PDF.value == "pdf"
        assert TaskStatus.SUCCESS.value == "success"
        assert EvidenceLevel.PS3.value == "PS3"
        
        # 验证模型可实例化
        request = TaskSubmissionRequest(
            input_type=InputType.PMID,
            value="12345678",
            project_tag="test"
        )
        assert request.input_type == InputType.PMID
    
    def test_old_schemas_location_removed(self):
        """测试旧的schemas位置已删除"""
        with pytest.raises(ImportError):
            from src.infrastructure.utils.schemas import InputType
    
    def test_old_api_services_location_removed(self):
        """测试旧的api_services位置已删除"""
        with pytest.raises(ImportError):
            from src.application.services.api_services import TaskService
    
    def test_api_services_in_presentation_layer(self):
        """测试api_services在presentation层（需要fastapi，可能跳过）"""
        try:
            from src.presentation.api_services import (
                TaskService, EvidenceQueryService, MetadataService
            )
            
            # 验证类可用
            assert TaskService is not None
            assert EvidenceQueryService is not None
            assert MetadataService is not None
            
            # 测试MetadataService（不需要依赖）
            languages = MetadataService.get_supported_languages()
            assert "zh" in languages
            assert "en" in languages
            
            evidence_levels = MetadataService.get_evidence_levels()
            assert "PS3" in evidence_levels
            
        except ImportError as e:
            pytest.skip(f"Skipped due to missing dependencies: {e}")


class TestApplicationLayer:
    """Application层测试 - 应用服务和依赖检查"""
    
    def test_application_services_importable(self):
        """测试应用层服务可导入"""
        from src.application.services import (
            PipelineContext,
            ResultAccumulator,
        )
        
        # 验证类可用
        assert PipelineContext is not None
        assert ResultAccumulator is not None
        
        # 测试PipelineContext
        context = PipelineContext()
        context.update({"test_key": "test_value"})
        assert context.get("test_key") == "test_value"
    
    def test_application_not_depends_on_infrastructure_repos(self):
        """测试Application层不直接依赖Infrastructure仓储"""
        import os
        import ast
        
        app_services_dir = Path("src/application/services")
        
        for py_file in app_services_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            
            content = py_file.read_text(encoding="utf-8")
            
            # 检查是否有直接导入infrastructure.repositories
            assert "from src.infrastructure.repositories" not in content, \
                f"{py_file.name} 不应直接依赖 infrastructure.repositories"


class TestLayerDependencies:
    """跨层依赖测试"""
    
    def test_domain_has_no_infrastructure_imports(self):
        """测试Domain层不依赖Infrastructure层"""
        import os
        
        domain_dir = Path("src/domain")
        
        for py_file in domain_dir.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue
            
            content = py_file.read_text(encoding="utf-8")
            
            # Domain层不应导入infrastructure或application
            assert "from src.infrastructure" not in content, \
                f"{py_file} 不应依赖 infrastructure"
            assert "from src.application" not in content, \
                f"{py_file} 不应依赖 application"
            assert "from src.presentation" not in content, \
                f"{py_file} 不应依赖 presentation"
    
    def test_presentation_can_import_all_layers(self):
        """测试Presentation层可以导入所有层"""
        # Presentation层位于最外层，可以导入其他层
        from src.presentation.schemas import InputType
        from src.domain.value_objects.language import Language
        
        assert InputType is not None
        assert Language is not None


class TestIntegration:
    """集成测试"""
    
    def test_complete_document_workflow(self):
        """测试完整的Document工作流"""
        from src.domain.entities.document import Document
        from src.domain.value_objects.language import Language
        
        # 1. 创建文档
        doc = Document(
            original_path="test.pdf",
            detected_language=Language.JAPANESE,
            english_content="This is a test document with evidence."
        )
        
        # 2. 验证初始状态
        assert not doc.is_highlighted()
        
        # 3. 提取证据并高亮
        evidence_spans = ["test document", "evidence"]
        doc.highlight_evidence(evidence_spans)
        
        # 4. 验证高亮结果
        assert doc.is_highlighted()
        assert "==test document==" in doc.highlighted_content
        assert "==evidence==" in doc.highlighted_content
    
    def test_complete_odds_path_workflow(self):
        """测试完整的OddsPath工作流"""
        from src.domain.value_objects.odds_path import OddsPath, EvidenceStrength
        
        # 不同概率的证据强度分类
        test_cases = [
            # SUPPORTING: OddsPath >= 2
            (0.1, 0.3, EvidenceStrength.SUPPORTING),
            # MODERATE: OddsPath >= 4.3
            (0.1, 0.5, EvidenceStrength.MODERATE),
            # STRONG: OddsPath >= 18
            (0.05, 0.5, EvidenceStrength.STRONG),
        ]
        
        for p1, p2, expected_strength in test_cases:
            odds = OddsPath(p1=p1, p2=p2)
            assert odds.strength == expected_strength
    
    def test_task_lifecycle(self):
        """测试任务生命周期"""
        from src.infrastructure.repositories.task_store import InMemoryTaskStore
        from src.presentation.schemas import InputType, TaskStatus, ProcessingStage
        
        store = InMemoryTaskStore()
        
        # 1. 创建任务
        record = store.create(InputType.PMID, "12345678", "project1")
        task_id = record.task_id
        
        assert record.status == TaskStatus.ACCEPTED
        assert record.stage == ProcessingStage.ACCEPTED
        
        # 2. 更新处理阶段
        store.update(
            task_id,
            status=TaskStatus.PROCESSING,
            stage=ProcessingStage.TRANSLATION
        )
        
        updated = store.get(task_id)
        assert updated.status == TaskStatus.PROCESSING
        assert updated.stage == ProcessingStage.TRANSLATION
        
        # 3. 完成任务
        results = {"ps3_evidence_level": "PS3_supporting", "arbiter_score": 85}
        store.update(
            task_id,
            status=TaskStatus.SUCCESS,
            stage=ProcessingStage.COMPLETE,
            results=results
        )
        
        completed = store.get(task_id)
        assert completed.status == TaskStatus.SUCCESS
        assert completed.results["arbiter_score"] == 85


class TestErrorCases:
    """错误情况测试"""
    
    def test_odds_path_invalid_probabilities(self):
        """测试OddsPath无效概率"""
        from src.domain.value_objects.odds_path import OddsPath
        
        # P1超出范围
        with pytest.raises(ValueError):
            OddsPath(p1=1.5, p2=0.5)
        
        with pytest.raises(ValueError):
            OddsPath(p1=-0.1, p2=0.5)
        
        # P2超出范围
        with pytest.raises(ValueError):
            OddsPath(p1=0.1, p2=1.5)
    
    def test_task_store_nonexistent_task(self):
        """测试TaskStore访问不存在的任务"""
        from src.infrastructure.repositories.task_store import InMemoryTaskStore
        
        store = InMemoryTaskStore()
        result = store.get("nonexistent_task_id")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
