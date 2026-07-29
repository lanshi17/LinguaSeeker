"""Quick check of Neo4j indexes."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from src.core.config import get_config
from src.dao.neo4j.connection import build_neo4j_driver


async def main():
    cfg = get_config()
    driver = build_neo4j_driver(cfg)
    async with driver.session() as session:
        result = await session.run("SHOW INDEXES")
        data = await result.data()
        print(f"Total indexes: {len(data)}")
        for d in data:
            print(f"  name={d.get('name', '?')} state={d.get('state', '?')}")
    await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
