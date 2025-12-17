"""配置验证脚本 - 检查所有必要的配置和依赖"""
import os
import sys
from pathlib import Path


def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
    if version < (3, 12):
        print("❌ Python版本过低，需要 >= 3.12")
        return False
    return True


def check_env_file():
    """检查.env文件"""
    if Path(".env").exists():
        print("✓ .env file exists")
        return True
    else:
        print("⚠️  .env file not found")
        if Path(".env.example").exists():
            print("  → Run: cp .env.example .env")
        return False


def check_required_env_vars():
    """检查必需的环境变量"""
    required_vars = [
        "DEEPSEEK_API_KEY",
        "CLAUDE_API_KEY",
        "POSTGRES_PASSWORD",
        "NEO4J_PASSWORD",
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.startswith("your-"):
            missing.append(var)
            print(f"❌ {var} not configured")
        else:
            print(f"✓ {var} configured")
    
    return len(missing) == 0


def check_dependencies():
    """检查关键依赖是否安装"""
    dependencies = {
        "fastapi": "FastAPI",
        "uvicorn": "Uvicorn",
        "langgraph": "LangGraph",
        "neo4j": "Neo4j Driver",
        "pymilvus": "Milvus Client",
    }
    
    all_installed = True
    for package, name in dependencies.items():
        try:
            __import__(package)
            print(f"✓ {name} installed")
        except ImportError:
            print(f"❌ {name} not installed")
            all_installed = False
    
    return all_installed


def check_database_connections():
    """检查数据库连接（可选）"""
    print("\n📊 Database connections (skipping for now):")
    print("  - PostgreSQL: Check manually")
    print("  - Neo4j: Check manually")
    print("  - Milvus: Check manually")


def main():
    """主函数"""
    print("=" * 60)
    print("ACMG-PS3 Backend Configuration Check")
    print("=" * 60)
    print()
    
    # 加载.env文件
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✓ .env loaded\n")
    except ImportError:
        print("⚠️  python-dotenv not installed\n")
    
    checks = [
        ("Python Version", check_python_version),
        (".env File", check_env_file),
        ("Environment Variables", check_required_env_vars),
        ("Dependencies", check_dependencies),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n📋 Checking {name}...")
        print("-" * 60)
        result = check_func()
        results.append(result)
    
    check_database_connections()
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All checks passed! Ready to start the server.")
        print("\nRun: python main.py")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print("\nSetup guide:")
        print("1. cp .env.example .env")
        print("2. Edit .env with your API keys")
        print("3. pip install -e .")
        print("4. python check_config.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
