# Automated Web Crawlers

Web crawlers for academic literature sources using crawl4ai and LLM-powered extraction.

## Sources

- **CyberLeninka** (`cyberleninka/`): Russian academic papers
- **Hans Publishers** (`hans_publishers/`): Chinese academic journals
- **PubScholar** (`pubscholar/`): Multi-source academic search

## Configuration

These crawlers now integrate with the global `AppConfig` from `src/config/app_config.py`.

### Default LLM Configuration

By default, all crawlers use **DeepSeek** configuration from AppConfig:

```python
from src.domain.literature.automated_web.cyberleninka.models import (
    CyberleninkaPayload,
    SearchParams,
)

# Uses DeepSeek config from AppConfig automatically
payload = CyberleninkaPayload(
    action="search",
    search_params=SearchParams(keyword="machine learning", limit=10)
)
```

### Custom LLM Configuration

Override the default by providing explicit values:

```python
payload = CyberleninkaPayload(
    action="search",
    search_params=SearchParams(keyword="machine learning", limit=10),
    llm_provider="ollama",  # Custom provider
    llm_api_token="your-token"  # Custom token
)
```

### Using Different LLMs from Config

Access other LLM configurations via `AutomatedWebConfig`:

```python
from src.domain.literature.automated_web.config import AutomatedWebConfig

# Get Claude config
claude_cfg = AutomatedWebConfig.get_claude_config()

payload = CyberleninkaPayload(
    action="search",
    search_params=SearchParams(keyword="machine learning", limit=10),
    llm_provider=claude_cfg["provider"],
    llm_api_token=claude_cfg["api_key"]
)
```

## Available Config Methods

```python
from src.domain.literature.automated_web.config import AutomatedWebConfig

# Get full AppConfig
cfg = AutomatedWebConfig.get_app_config()

# Get LLM configs
deepseek_cfg = AutomatedWebConfig.get_deepseek_config()
ocr_cfg = AutomatedWebConfig.get_ocr_config()
claude_cfg = AutomatedWebConfig.get_claude_config()

# Get individual values
provider = AutomatedWebConfig.get_default_llm_provider()
api_key = AutomatedWebConfig.get_default_llm_api_key()
base_url = AutomatedWebConfig.get_default_llm_base_url()
model = AutomatedWebConfig.get_default_llm_model()
```

## Environment Variables

Configure LLMs via environment variables in `.env`:

```bash
# DeepSeek (default)
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# OCR LLM
OCR_API_KEY=your-ocr-api-key
OCR_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OCR_MODEL=qwen-vl-ocr-latest

# Claude
CLAUDE_API_KEY=your-claude-api-key
ANTHROPIC_BASE_URL=https://api.anthropic.com
CLAUDE_MODEL=claude-3-5-sonnet-20241022
```

## Testing

Run the integration test:

```bash
cd /path/to/backend
PYTHONPATH=/path/to/backend python3 \
    src/domain/literature/automated_web/test_config_integration.py
```

## Documentation

- `CONFIG_INTEGRATION.md`: Detailed integration guide
- `INTEGRATION_SUMMARY.md`: Quick summary of changes

## Architecture

```
automated_web/
├── config.py                    # AppConfig integration bridge
├── cyberleninka/               # CyberLeninka crawler
│   ├── models.py               # Payload models with AppConfig support
│   └── service.py              # Service using effective_* properties
├── hans_publishers/            # Hans Publishers crawler
│   ├── models.py
│   └── service.py
└── pubscholar/                 # PubScholar crawler
    ├── models.py
    └── service.py
```

## Key Features

✅ **Centralized Configuration**: All LLM settings in AppConfig  
✅ **Environment-Aware**: Different configs per environment  
✅ **Flexible Overrides**: Per-request customization  
✅ **Secure**: API keys from environment variables  
✅ **Consistent**: Same config across all crawlers
