# Global fixture configuration (e.g., pytest-asyncio, database sessions)
import sys
from pathlib import Path

import dotenv
import pytest

# Load environment variables from .env.test file
dotenv.load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env.test")

# Add src directory to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def any_global_fixture():
    # Setup code here
    
    yield
    # Teardown code here
    pass
# Add more fixtures as needed for tests

# This file is used to define global fixtures and configurations for tests.
# It can include setup and teardown logic for test sessions.
# For example, you can define database fixtures, mock services, etc.
