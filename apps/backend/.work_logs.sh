: 1765983866:0;uv init
: 1765983872:0;uv venv
: 1765983902:0;vim ~/.config/uv/uv.toml
: 1765983992:0;vim ~/.config/uv/uv-receipt.json
: 1765984026:0;rm -r .venv
: 1765984049:0;uv venve --python 3.12
: 1765984058:0;uv venv --python 3.12
: 1765984079:0;python --version
: 1765984233:0;source /home/lanshi/Documents/Graduate/02_Research/02_MultilingualDocumentEvidenceCollectionPlatform/apps/backend/.venv/bin/activate
: 1765984246:0;uv run main.py
: 1765985431:0;rm -r src/*
: 1765987733:0;uv add requests
: 1765988401:0;cat > /home/lanshi/Documents/Graduate/02_Research/02_MultilingualDocumentEvidenceCollectionPlatform/apps/backend/PRODUCTION_DEPLOYMENT.md << 'EOF'\
# çƒ´ƒ¿äº§éƒ£¨ç½²ï¼ƒºæƒ¼ƒ­åƒªƒä¸ƒ®æƒµ°æƒ­®åƒ¨ƒ¦ç¦»æƒ¾¶æƒ¾ƒ¤\
\
## æƒ€¸å¿ƒ£åƒ®ƒ¿åƒ¨ƒ¹\
\
æƒ¼¬ç³»ç»ƒ¿éƒ§ƒ§çƒ´¨ **æƒ¼ƒ­åƒªƒ-æƒµ°æƒ­®åƒ¨ƒ¦ç¦»æƒ¾¶æƒ¾ƒ¤**ï¼ƒ¬åƒ­³ï¼ƒº\
- **åºƒ´çƒ´¨æƒ¼ƒ­åƒªƒ** (FastAPI) éƒ£¨ç½²åƒ¼¨åºƒ´çƒ´¨æƒ¼ƒ­åƒªƒåƒ¹¨\
- **æƒµ°æƒ­®åºƒ³** (PostgreSQL/Neo4j/Qdrant/MinIO) éƒ£¨ç½²åƒ¼¨çƒ«¬ç«ƒ«ä¸»æƒ¼ºæƒ¨ƒ¶äºƒ±æƒ¼ƒ­åƒªƒ\
- åºƒ´çƒ´¨é€ƒºè¿ƒ§ç½ƒ±ç»ƒ¼è¿ƒ¾æƒ®¥åƒ¨°è¿ƒ¼ç¨ƒ«æƒµ°æƒ­®åºƒ³ï¼ƒ¬ä¸ƒ­åƒ¼¨æƒ¼¬åƒ¼°å­ƒ¸å‚¨æƒµ°æƒ­®\
\
## âƒºƒ¹ï¸ƒ¯ éƒ¥ƒ­ç½®è¿ƒ¼ç¨ƒ«è¿ƒ¾æƒ®¥\
\
### 1. ä½¿çƒ´¨ `.env.production` éƒ¥ƒ­ç½®æƒ¶ƒ§ä»¶\
\
å¤ƒ­åƒ¨¶å¹¶ç¼ƒ¶è¾ƒ±çƒ´ƒ¿äº§éƒ¥ƒ­ç½®æƒ¶ƒ§ä»¶ï¼ƒº\
\`\`\`bash\
cp .env.production .env\
vi .env\
\`\`\`\
\
**åƒ¥³éƒ´®åƒ¯‚æƒµ°ï¼ƒ¨æƒ´¹ä¸ºè¿ƒ¼ç¨ƒ«åƒ¼°åƒ½€ï¼ƒ©ï¼ƒº**\
\`\`\`ini\n# PostgreSQL\nPOSTGRES_HOST=\"db.postgres.example.com\"  # æƒ´¹ä¸ºè¿ƒ¼ç¨ƒ«ä¸»æƒ¼ºåƒ°ƒ­\nPOSTGRES_PORT=\"5432\"\nPOSTGRES_PASSWORD=\"your-secure-password\"  # ä½¿çƒ´¨å¼ºå¯ƒ¦çƒ€\n\n# Neo4j\nNEO4J_URI=\"bolt://neo4j.example.com:7687\"  # æƒ´¹ä¸ºè¿ƒ¼ç¨ƒ«åƒ¼°åƒ½€\nNEO4J_PASSWORD=\"your-secure-password\"\n\n# Qdrant\nQDANT_HOST=\"qdrant.example.com\"\nQDANT_PORT=\"6333\"\nQDANT_PREFER_GRPC=\"true\"\n\n# MinIO\nMINIO_ENDPOINT=\"minio.example.com:9000\"  # æƒ´¹ä¸ºè¿ƒ¼ç¨ƒ«åƒ¼°åƒ½€\nMINIO_SECURE=\"true\"  # åƒ°¯çƒ´¨ TLS\nMINIO_ACCESS_KEY=\"your-access-key\"\nMINIO_SECRET_KEY=\"your-secret-key\"\n\n# çƒ´ƒ¿äº§çƒ®¯åƒ‚ƒ£\nENVIRONMENT=\"production\"\nDEBUG=\"false\"\n\`\`\`\
\
### 2. ç½ƒ±ç»ƒ¼éƒ¥ƒ­ç½®\
\
**éƒ¸²ç«åƒ‚ƒ¹è§ƒ¤åƒ¨ƒ¹** (ç¤ºä¾ƒ«)ï¼ƒº\
\`\`\`bash\n# ä»ƒ¥åƒ¥è®¸åºƒ´çƒ´¨æƒ¼ƒ­åƒªƒåƒ¹¨ IP è®¿éƒ·®æƒµ°æƒ­®åºƒ³\nufw allow from APP_SERVER_IP to any port 5432   # PostgreSQL\nufw allow from APP_SERVER_IP to any port 7687   # Neo4j\nufw allow from APP_SERVER_IP to any port 6333   # Qdrant\nufw allow from APP_SERVER_IP to any port 9000   # MinIO\n\`\`\`\
\
### 3. åƒ°¯åƒª¨åºƒ´çƒ´¨\
\
\`\`\`bash\n# åƒªƒ€è½½çƒ®¯åƒ‚ƒ£åƒ¯ƒ¸éƒ§ƒ¯å¹¶åƒ°¯åƒª¨\nenv $(cat .env | xargs) python main.py\n\n# æƒ¨ƒ¶ä½¿çƒ´¨ systemd\nsudo systemctl start acmg-backend\n\`\`\`\
\
## ðƒ¿ƒ´ƒ² å®ƒ©åƒ¥¨å»ºè®®\
\
âƒ¼ƒ¥ **å¿ƒ¥éƒ»åƒºçƒºƒ¤ï¼ƒº**\
1. æƒ©€æƒ¼ƒ©æƒµ°æƒ­®åºƒ³è¿ƒ¾æƒ®¥ä½¿çƒ´¨ TLS/SSL åƒªƒ€å¯ƒ¦\n2. å¼ºå¯ƒ¦çƒ€ (âƒ©¥16å­ƒ·ç¬¦ï¼ƒ¬åƒ°«å¤§å°ƒ¯åƒ¦ƒ¹ã€æƒµ°å­ƒ·ã€ç¬¦åƒ¯·)\n3. åƒ§­è¯é€ƒºè¿ƒ§çƒ®¯åƒ‚ƒ£åƒ¯ƒ¸éƒ§ƒ¯æƒ¨ƒ¶å¯ƒ¦éƒ²¥ç®ƒçƒ°ƒ¦æƒ¼ƒ­åƒªƒ (Vault) ä¼ƒ€é€ƒ²\n4. éƒ¸²ç«åƒ‚ƒ¹ä¸¥æƒ€¼éƒ¹ƒ°åƒ¨¶è®¿éƒ·® (åƒ¯ªåƒ¥è®¸åºƒ´çƒ´¨æƒ¼ƒ­åƒªƒåƒ¹¨ IP)\n5. å®ƒºæƒ¼ƒ¿å¤ƒ§ä»½æƒ©€æƒ¼ƒ©æƒµ°æƒ­®åºƒ³\n\nâƒ½ƒ¬ **ç»ƒ½å¯¹ä¸ƒ­è¦ï¼ƒº**\n1. åƒ¼¨ä»£çƒ€ä¸­çƒ¬ç¼ƒ¶çƒ€ \`localhost\` æƒµ°æƒ­®åºƒ³è¿ƒ¾æƒ®¥\n2. åƒ¼¨ Git ä¸­æƒ¯ƒ°äº¤æƒµƒ¯æƒ¤ƒ¿åƒ§­è¯\n3. åƒ¼¨çƒ´ƒ¿äº§çƒ®¯åƒ‚ƒ£åƒ°¯çƒ´¨ DEBUG æ¨ƒå¼ƒ¯\n4. ä½¿çƒ´¨é»ƒ¸è®¤å¯ƒ¦çƒ€\n5. åƒ¼¨åƒ¥¬ç½ƒ±çƒ»´æƒ®¥æƒº´éƒ¼²æƒµ°æƒ­®åºƒ³ç«¯åƒ¯£\n\n## ðƒ¿ƒ³ƒª éªƒ¬è¯è¿ƒ¾æƒ®¥\n\n\`\`\`bash\n# æ£€æƒ¿¥éƒ¥ƒ­ç½®åƒªƒ€è½½\npython check_config.py\n\n# æµƒ«è¯ƒµè¿ƒ¾æƒ®¥\npython -c \"from src.config.database_config import DatabaseConfig; cfg = DatabaseConfig.from_env(); print('PostgreSQL:', cfg.postgresql.host)\"\n\`\`\`\n\n## ðƒ¿ƒ³ƒ½ å®ƒ¬æƒµ´æ£€æƒ¿¥æ¸ƒ¥åƒ­ƒµ\n\n- [ ] æƒ©€æƒ¼ƒ©æƒµ°æƒ­®åºƒ³ä¸»æƒ¼ºåƒ°ƒ­å·²ä»ƒ® \`localhost\` æƒ´¹ä¸ºè¿ƒ¼ç¨ƒ«åƒ¼°åƒ½€\n- [ ] PostgreSQL å¯ƒ¦çƒ€å·²æƒ»´æƒ´¹ä¸ºå¼ºå¯ƒ¦çƒ€\n- [ ] Neo4j å¯ƒ¦çƒ€å·²æƒ»´æƒ´¹ä¸ºå¼ºå¯ƒ¦çƒ€  \n- [ ] MinIO åƒ°¯çƒ´¨ TLS (MINIO_SECURE=true)\n- [ ] éƒ¸²ç«åƒ‚ƒ¹è§ƒ¤åƒ¨ƒ¹å·²éƒ¥ƒ­ç½®ï¼ƒ¬ä»ƒ¥åƒ¥è®¸åºƒ´çƒ´¨æƒ¼ƒ­åƒªƒåƒ¹¨è®¿éƒ·®\n- [ ] æƒ©€æƒ¼ƒ©æƒµ°æƒ­®åºƒ³è¿ƒ¾æƒ®¥ä½¿çƒ´¨ TLS/SSL\n- [ ] çƒ®¯åƒ‚ƒ£åƒ¯ƒ¸éƒ§ƒ¯å·²æ­£çƒ®åƒªƒ€è½½\n- [ ] \`DEBUG=false\` åƒ¼¨çƒ´ƒ¿äº§çƒ®¯åƒ‚ƒ£\n- [ ] æƒµƒ¯æƒ¤ƒ¿åƒ§­è¯å·²ä»ƒ®ä»£çƒ€ä¸­ç§»éƒ¹¤\n- [ ] çƒ»ƒ±æƒ®§åƒ²ƒ¬åƒ±ƒªè­¦å·²éƒ¥ƒ­ç½®\nEOF\
cat >> /home/lanshi/Documents/Graduate/02_Research/02_MultilingualDocumentEvidenceCollectionPlatform/apps/backend/src/config/app_config.py << 'EOF'\
    \
    @classmethod\
    def from_env(cls):\
        """ä»ƒ®çƒ®¯åƒ‚ƒ£åƒ¯ƒ¸éƒ§ƒ¯åƒªƒ€è½½éƒ¥ƒ­ç½®"""\
        import os\
        \
        cfg = cls()\
        \
        # åºƒ´çƒ´¨éƒ¥ƒ­ç½®\
        cfg.app_name = os.getenv("APP_NAME", cfg.app_name)\
        cfg.version = os.getenv("APP_VERSION", cfg.version)\
        env = os.getenv("ENVIRONMENT", "development")\
        cfg.environment = Environment(env) if env in (e.value for e in Environment) else Environment.DEVELOPMENT\
        cfg.debug = os.getenv("DEBUG", "false").lower() == "true"\
        \
        # API éƒ¥ƒ­ç½®\
        cfg.api_prefix = os.getenv("API_PREFIX", cfg.api_prefix)\
        cfg.api_version = os.getenv("API_VERSION", cfg.api_version)\
        cfg.host = os.getenv("API_HOST", cfg.host)\
        cfg.port = int(os.getenv("API_PORT", cfg.port))\
        \
        # LLM éƒ¥ƒ­ç½®\
        cfg.llm.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")\
        cfg.llm.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", cfg.llm.deepseek_base_url)\
        cfg.llm.deepseek_model = os.getenv("DEEPSEEK_MODEL", cfg.llm.deepseek_model)\
        cfg.llm.claude_api_key = os.getenv("CLAUDE_API_KEY")\
        cfg.llm.claude_model = os.getenv("CLAUDE_MODEL", cfg.llm.claude_model)\
        cfg.llm.temperature = float(os.getenv("LLM_TEMPERATURE", cfg.llm.temperature))\
        cfg.llm.max_tokens = int(os.getenv("LLM_MAX_TOKENS", cfg.llm.max_tokens))\
        cfg.llm.timeout = int(os.getenv("LLM_TIMEOUT", cfg.llm.timeout))\
        \
        # Embedding éƒ¥ƒ­ç½®\
        cfg.embedding.provider = os.getenv("EMBEDDING_PROVIDER", cfg.embedding.provider)\
        cfg.embedding.model_name = os.getenv("EMBEDDING_MODEL", cfg.embedding.model_name)\
        cfg.embedding.dimension = int(os.getenv("EMBEDDING_DIMENSION", cfg.embedding.dimension))\
        cfg.embedding.batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", cfg.embedding.batch_size))\
        \
        # MinerU éƒ¥ƒ­ç½®\
        cfg.mineru.mode = os.getenv("MINERU_MODE", cfg.mineru.mode)\
        cfg.mineru.api_url = os.getenv("MINERU_API_URL", cfg.mineru.api_url)\
        cfg.mineru.timeout = int(os.getenv("MINERU_TIMEOUT", cfg.mineru.timeout))\
        cfg.mineru.max_file_size_mb = int(os.getenv("MINERU_MAX_FILE_SIZE_MB", cfg.mineru.max_file_size_mb))\
        \
        # ä»»åƒªƒéƒ¥ƒ­ç½®\
        cfg.max_reasoning_iterations = int(os.getenv("MAX_REASONING_ITERATIONS", cfg.max_reasoning_iterations))\
        cfg.task_timeout_seconds = int(os.getenv("TASK_TIMEOUT_SECONDS", cfg.task_timeout_seconds))\
        \
        return cfg\
EOF
: 1765988791:0;cd /home/lanshi/Documents/Graduate/02_Research/02_MultilingualDocumentEvidenceCollectionPlatform/apps/backend && python -c "\
from src.config.database_config import DatabaseConfig\
config = DatabaseConfig.from_env()\
print('=== æƒµ°æƒ­®åºƒ³éƒ¥ƒ­ç½®éªƒ¬è¯ ===')\
print(f'PostgreSQL: {config.postgresql.host}:{config.postgresql.port}')\
print(f'Neo4j: {config.neo4j.uri}')\
print(f'Qdrant: {config.qdrant.host}:{config.qdrant.port}')\
print(f'MinIO: {config.minio.endpoint}')\
print(f'åƒ°ƒ±éƒ§ƒ¯DB: {config.vector_backend}')\
"
: 1765988885:0;ls -la /home/lanshi/Documents/Graduate/02_Research/02_MultilingualDocumentEvidenceCollectionPlatform/apps/backend/*.md
: 1765988893:0;ls -lh /home/lanshi/Documents/Graduate/02_Research/02_MultilingualDocumentEvidenceCollectionPlatform/apps/backend/{PRODUCTION_DEPLOYMENT.md,.env.production}
: 1765988959:0;uv add requests
: 1766026852:0;source /home/lanshi/Documents/Graduate/02_Research/02_MultilingualDocumentEvidenceCollectionPlatform/apps/backend/.venv/bin/activate
: 1766027924:0;python src/service/test_llm_service.py
: 1766027937:0;uv sync
: 1766027953:0;python src/service/test_llm_service.py
: 1766027962:0;uv run python src/service/test_llm_service.py
: 1766028168:0;git rm --cacehd .work_logs.sh
: 1766028178:0;git rm --cached .work_logs.sh
: 1766028257:0;ls -la | grep "\.env"
: 1769403076:0;source /home/lanshi/Documents/Graduate/02_Research/02_MultilingualDocumentEvidenceCollectionPlatform/apps/backend/.venv/bin/activate
: 1769403080:0;uv init
: 1769413205:0;uv add requests
: 1769413212:0;uv add fastapi
: 1769416681:0;tree src/service
: 1769417072:0;tree src
: 1769417259:0;cd src
: 1769417266:0;mv controller presentation
: 1769417285:0;mv service application
: 1769417345:0;cd ..
: 1769417347:0;qwen
: 1769417956:0;source /home/lanshi/Documents/Graduate/02_Research/02_MultilingualDocumentEvidenceCollectionPlatform/apps/backend/.venv/bin/activate
: 1769418593:0;cp -r /home/lanshi/Documents/Graduate/02_Research/05_Multi-ACMG-MinerU-demo/src/infrastructure/utils src
