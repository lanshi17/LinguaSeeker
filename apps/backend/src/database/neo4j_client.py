from typing import List, Dict, Any
from neo4j import GraphDatabase, basic_auth
from neo4j.exceptions import Neo4jError
from contextlib import contextmanager
from loguru import logger
from src.config import settings as cfg
from src.utils.timer import Timer

class Neo4jClient:
    def __init__(self, uri, user, password):
        from neo4j import GraphDatabase
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def run_query(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]