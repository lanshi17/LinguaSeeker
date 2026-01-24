# 导入依赖检查报告

**检查日期**: 2026-01-24  
**检查状态**: ⚠️ 发现导入路径错误

## 问题概述

发现多个文件使用了错误的导入路径：使用 `from src.utils.xxx` 而实际的模块位置是 `src/infrastructure/utils/`

## 错误导入清单

| 文件 | 错误导入 | 应改为 | 状态 |
|------|--------|--------|------|
| pdf_repository_impl.py | `from src.utils.exceptions import ...` | `from src.infrastructure.utils.exceptions import ...` | ❌ |
| pdf_repository_impl.py | `from src.utils.config import ...` | `from src.infrastructure.utils.config import ...` | ❌ |
| pipeline_orchestrator.py | `from src.utils.config import ...` | `from src.infrastructure.utils.config import ...` | ❌ |
| pipeline_orchestrator.py | `from src.utils.logger import ...` | `from src.infrastructure.utils.logger import ...` | ❌ |
| rag_repository_impl.py | `from src.utils.exceptions import ...` | `from src.infrastructure.utils.exceptions import ...` | ❌ |
| rag_repository_impl.py | `from src.utils.config import ...` | `from src.infrastructure.utils.config import ...` | ❌ |
| rag_repository_impl.py | `from src.utils.logger import ...` | `from src.infrastructure.utils.logger import ...` | ❌ |

## 正确的模块位置

```
src/
├── infrastructure/
│   └── utils/                    ✅ 真实位置
│       ├── config.py             ✅
│       ├── exceptions.py         ✅
│       ├── logger.py             ✅
│       └── __init__.py
```

## 需要修复的导入

共 7 处导入错误需要修复：

**pdf_repository_impl.py** (2处)
```python
# ❌ 错误
from src.utils.exceptions import LanguageDetectionError, ParsingException
from src.utils.config import LLMConfig

# ✅ 正确
from src.infrastructure.utils.exceptions import LanguageDetectionError, ParsingException
from src.infrastructure.utils.config import LLMConfig
```

**pipeline_orchestrator.py** (2处)
```python
# ❌ 错误
from src.utils.config import AppConfig
from src.utils.logger import Logger

# ✅ 正确
from src.infrastructure.utils.config import AppConfig
from src.infrastructure.utils.logger import Logger
```

**rag_repository_impl.py** (3处)
```python
# ❌ 错误
from src.utils.exceptions import ParsingException
from src.utils.config import RerankConfig
from src.utils.logger import Logger

# ✅ 正确
from src.infrastructure.utils.exceptions import ParsingException
from src.infrastructure.utils.config import RerankConfig
from src.infrastructure.utils.logger import Logger
```

## 其他文件导入检查

✅ **arbiter_impl.py** - 正确使用 `from src.utils.xxx`（需修正）

```python
from src.utils.exceptions import ReasoningException
from src.utils.logger import Logger
```

应改为：
```python
from src.infrastructure.utils.exceptions import ReasoningException
from src.infrastructure.utils.logger import Logger
```

✅ **translator_impl.py** - 正确使用 `from src.utils.xxx`（需修正）

```python
from src.utils.exceptions import TranslationError
```

应改为：
```python
from src.infrastructure.utils.exceptions import TranslationError
```

✅ **evidence_extractor_impl.py** - 正确使用 `from src.utils.xxx`（需修正）

```python
from src.utils.logger import Logger
```

应改为：
```python
from src.infrastructure.utils.logger import Logger
```

✅ **embedding_provider.py** - 正确使用 `from src.utils.xxx`（需修正）

```python
from src.utils.config import AppConfig
```

应改为：
```python
from src.infrastructure.utils.config import AppConfig
```

✅ **ocr/qwen_ocr_service.py** - 正确使用 `from src.utils.xxx`（需修正）

```python
from src.utils.config import LLMConfig
from src.utils.exceptions import ParsingException
from src.utils.logger import Logger
```

应改为：
```python
from src.infrastructure.utils.config import LLMConfig
from src.infrastructure.utils.exceptions import ParsingException
from src.infrastructure.utils.logger import Logger
```

✅ **domain/interfaces/__init__.py** - 正确使用 `from src.utils.xxx`（需修正）

```python
from src.utils.config import AppConfig
```

应改为：
```python
from src.infrastructure.utils.config import AppConfig
```

## 总结

**总计需要修复**: 17 处导入错误

所有导入都需要从 `src.utils` 更改为 `src.infrastructure.utils`

### DDD 架构建议

建议方案选择（二选一）：

**方案A**: 使用 `from src.infrastructure.utils` ✅ 推荐
- 符合DDD架构
- utils 是infrastructure层的共享工具
- 导入路径清晰
- **成本**: 修改17处导入

**方案B**: 在 src/ 下创建 shared/ 目录（不推荐）
- 复制utils文件到 `src/shared/`
- 维护两份代码副本
- **缺点**: 代码冗余，维护困难

## 建议

✅ 采用方案A：修正所有导入为 `from src.infrastructure.utils.xxx`

这样可以：
1. 保持DDD清晰的层次结构
2. 避免代码冗余
3. 便于后续维护
