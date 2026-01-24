# FastText 快速参考

## 问题解决

### ❌ 问题：`lid.176.ftz cannot be opened for loading!`

**原因**：FastText 模型文件不存在

**解决方案**：
```python
# 自动解决 - 第一次调用时自动下载
from src.infrastructure.ocr.mineru_ocr_service import MinerUOCRService
from src.infrastructure.utils.config import AppConfig

service = MinerUOCRService(AppConfig.from_env().llm)
language = service._detect_language(pdf_path)  # 自动下载模型
```

**手动下载**：
```bash
python -c "
import urllib.request
from pathlib import Path

cache_dir = Path.home() / '.fasttext_models'
cache_dir.mkdir(parents=True, exist_ok=True)

url = 'https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz'
urllib.request.urlretrieve(url, cache_dir / 'lid.176.ftz')
print('✓ 模型已下载')
"
```

## 工作流总结

```
PDF 输入
  ↓
文本提取 (PyPDF 或 OCR)
  ↓
FastText 检测 (获取或下载模型)
  ↓
语言代码映射 (zh → ch)
  ↓
MinerU API 请求 (包含语言参数)
```

## 日志示例

### ✓ 正常流程
```
INFO - Mapped FastText detected language zh -> ch for MinerU
INFO - Detected PDF language: ch
INFO - Got batch_id=56c14d36-75a9-450d-bd6b-efd610d664c7
INFO - PDF uploaded successfully
```

### ⚠️ 首次运行（需要下载）
```
INFO - Downloading FastText model to /home/user/.fasttext_models/lid.176.ftz...
INFO - FastText model downloaded successfully
INFO - FastText model loaded successfully
INFO - Mapped FastText detected language zh -> ch for MinerU
```

### ℹ️ 缓存命中
```
DEBUG - Using cached FastText model: /home/user/.fasttext_models/lid.176.ftz
DEBUG - FastText model loaded successfully
```

## 性能说明

| 操作 | 首次 | 后续 |
|------|------|------|
| 模型下载 | 30-60s | - |
| 模型加载 | 2-3s | 0ms（缓存） |
| 语言检测 | <100ms | <100ms |
| **总计** | ~35-65s | <100ms |

## 支持的语言

FastText 支持 176 种语言，主要包括：
- 中文 (zh) → MinerU 代码：ch
- 英文 (en) → MinerU 代码：en
- 日文 (ja) → MinerU 代码：ja
- 俄文 (ru) → MinerU 代码：ru
- 德文 (de) → MinerU 代码：de
- 法文 (fr) → MinerU 代码：fr

## 故障排查

### 检查模型是否存在
```bash
ls -lh ~/.fasttext_models/lid.176.ftz
```

### 检查模型是否有效
```python
import fasttext
from pathlib import Path

model_path = Path.home() / '.fasttext_models' / 'lid.176.ftz'
model = fasttext.load_model(str(model_path))
pred = model.predict("你好")  # 中文测试
print(pred)  # 应输出：(('__label__zh',), (置信度,))
```

### 查看日志级别
```python
import logging
logging.getLogger('src.infrastructure.ocr.mineru_ocr_service').setLevel(logging.DEBUG)
```

## 环境变量

无需额外配置，自动使用：
- `~/.fasttext_models/` 作为本地缓存目录
- 系统 `requests` 库进行下载

## 常见问题

**Q: 模型会重复下载吗？**
A: 不会。检测到本地文件后，直接使用本地版本。

**Q: 模型可以离线使用吗？**
A: 可以。首次下载后，所有操作都是离线的。

**Q: 支持自定义模型吗？**
A: 可以。手动替换 `~/.fasttext_models/lid.176.ftz` 即可。

**Q: 如何禁用自动下载？**
A: 检查 `_get_fasttext_model()` 方法，注释掉下载逻辑。

**Q: 多进程环境下是否安全？**
A: 是。缓存检查使用条件，不会重复下载。
