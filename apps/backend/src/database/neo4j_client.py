"""
Neo4j 图数据库客户端
实体关系图 Schema：
  - Gene       ← HAS_VARIANT →    Variant
  - Variant    ← HAS_PHENOTYPE →  Phenotype
  - Disease    ← ASSOCIATED_GENE → Gene
  - Document   ← MENTIONS →       Gene / Variant / Phenotype / Disease
  - Variant    ← HAS_EVIDENCE →   Evidence
  - Gene       ← HAS_TRANSCRIPT → Transcript
  - Evidence   ← FROM_DOCUMENT → Document
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Tuple

from loguru import logger
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from src.config import settings as cfg
from src.utils.timer import Timer


# ==================== Schema 初始化 Cypher ====================

_SCHEMA_CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (g:Gene) REQUIRE g.symbol IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (v:Variant) REQUIRE v.hgvs_c IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Disease) REQUIRE d.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Phenotype) REQUIRE p.description IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (doc:Document) REQUIRE doc.document_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Transcript) REQUIRE t.transcript_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Evidence) REQUIRE e.evidence_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Species) REQUIRE s.name IS UNIQUE",
]

_SCHEMA_INDEXES = [
	"CREATE INDEX IF NOT EXISTS FOR (g:Gene) ON (g.symbol)",
	"CREATE INDEX IF NOT EXISTS FOR (v:Variant) ON (v.hgvs_p)",
	"CREATE INDEX IF NOT EXISTS FOR (v:Variant) ON (v.rs_id)",
	"CREATE INDEX IF NOT EXISTS FOR (v:Variant) ON (v.variation_id)",
	"CREATE INDEX IF NOT EXISTS FOR (v:Variant) ON (v.transcript_id, v.exon_range)",
	"CREATE INDEX IF NOT EXISTS FOR (d:Disease) ON (d.icd10_code)",
    "CREATE INDEX IF NOT EXISTS FOR (d:Disease) ON (d.omim_id)",
    "CREATE INDEX IF NOT EXISTS FOR (p:Phenotype) ON (p.hpo_id)",
    "CREATE INDEX IF NOT EXISTS FOR (doc:Document) ON (doc.file_hash)",
    "CREATE INDEX IF NOT EXISTS FOR (e:Evidence) ON (e.evidence_strength)",
]


class Neo4jClient:
    """Neo4j 图数据库客户端，支持实体关系图建模"""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        self._uri = uri or cfg.neo4j_uri
        self._user = user or cfg.neo4j_user
        self._password = password or cfg.neo4j_password
        self._database = database or cfg.neo4j_database
        self.driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))

    def close(self) -> None:
        self.driver.close()

    @contextmanager
    def _session(self) -> Iterator:
        session = self.driver.session(database=self._database)
        try:
            yield session
        finally:
            session.close()

    def run_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with self._session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    # ==================== Schema 初始化 ====================

    def initialize_schema(self) -> None:
        """创建约束和索引"""
        with self._session() as session:
            for stmt in _SCHEMA_CONSTRAINTS + _SCHEMA_INDEXES:
                try:
                    session.run(stmt)
                except Neo4jError as e:
                    logger.warning("Schema 语句执行警告: {} - {}", stmt[:60], e)
        logger.info("Neo4j schema 初始化完成")

    # ==================== 节点 CRUD ====================

    def upsert_gene(self, symbol: str, **props: Any) -> Dict[str, Any]:
        query = """
        MERGE (g:Gene {symbol: $symbol})
        SET g += $props
        RETURN g
        """
        return self._single(query, {"symbol": symbol, "props": props})

	def upsert_variant(
		self,
		hgvs_c: Optional[str],
		variation_id: Optional[int] = None,
		structural_key: Optional[str] = None,
		transcript_id: Optional[str] = None,
		exon_range: Optional[str] = None,
		**props: Any,
	) -> Dict[str, Any]:
		merge_clause, locator_params = self._build_variant_merge_clause(
			hgvs_c,
			structural_key,
			transcript_id,
			exon_range,
		)
		payload_props = {k: v for k, v in props.items() if v is not None}
		if transcript_id is not None:
			payload_props.setdefault("transcript_id", transcript_id)
		if exon_range is not None:
			payload_props.setdefault("exon_range", exon_range)
		if structural_key is not None:
			payload_props.setdefault("structural_key", structural_key)
		set_variation_clause = ""
		if variation_id is not None:
			set_variation_clause = (
				"SET v.variation_id = CASE WHEN v.variation_id IS NULL THEN $variation_id ELSE v.variation_id END"
			)
		query = f"""
		{merge_clause}
		{set_variation_clause}
		SET v += $props
		RETURN v
		"""
		params: Dict[str, Any] = {**locator_params, "props": payload_props}
		if variation_id is not None:
			params["variation_id"] = variation_id
		return self._single(query, params)

    def upsert_disease(self, name: str, **props: Any) -> Dict[str, Any]:
        query = """
        MERGE (d:Disease {name: $name})
        SET d += $props
        RETURN d
        """
        return self._single(query, {"name": name, "props": props})

    def upsert_phenotype(self, description: str, **props: Any) -> Dict[str, Any]:
        query = """
        MERGE (p:Phenotype {description: $description})
        SET p += $props
        RETURN p
        """
        return self._single(query, {"description": description, "props": props})

    def upsert_document(self, document_id: str, **props: Any) -> Dict[str, Any]:
        query = """
        MERGE (doc:Document {document_id: $document_id})
        SET doc += $props
        RETURN doc
        """
        return self._single(query, {"document_id": document_id, "props": props})

    def upsert_transcript(self, transcript_id: str, **props: Any) -> Dict[str, Any]:
        query = """
        MERGE (t:Transcript {transcript_id: $transcript_id})
        SET t += $props
        RETURN t
        """
        return self._single(query, {"transcript_id": transcript_id, "props": props})

    def upsert_evidence(self, evidence_id: str, **props: Any) -> Dict[str, Any]:
        query = """
        MERGE (e:Evidence {evidence_id: $evidence_id})
        SET e += $props
        RETURN e
        """
        return self._single(query, {"evidence_id": evidence_id, "props": props})

    def upsert_species(self, name: str, **props: Any) -> Dict[str, Any]:
        query = """
        MERGE (s:Species {name: $name})
        SET s += $props
        RETURN s
        """
        return self._single(query, {"name": name, "props": props})

    # ==================== 关系 CRUD ====================

	def link_gene_variant(
		self,
		gene_symbol: str,
		variant_hgvs_c: Optional[str],
		variation_id: Optional[int] = None,
		structural_key: Optional[str] = None,
		transcript_id: Optional[str] = None,
		exon_range: Optional[str] = None,
		**props: Any,
	) -> None:
		match_clause, params = self._build_variant_match_clause(
			variation_id,
			variant_hgvs_c,
			structural_key,
			transcript_id,
			exon_range,
		)
		query = f"""
		MATCH (g:Gene {{symbol: $gene_symbol}})
		{match_clause}
		MERGE (g)-[r:HAS_VARIANT]->(v)
		SET r += $props
		"""
		self.run_query(
			query,
			{
				**params,
				"gene_symbol": gene_symbol,
				"props": props,
			},
		)

    def link_gene_transcript(self, gene_symbol: str, transcript_id: str) -> None:
        query = """
        MATCH (g:Gene {symbol: $gene_symbol})
        MATCH (t:Transcript {transcript_id: $transcript_id})
        MERGE (g)-[:HAS_TRANSCRIPT]->(t)
        """
        self.run_query(query, {"gene_symbol": gene_symbol, "transcript_id": transcript_id})

	def link_variant_phenotype(
		self,
		variant_hgvs_c: Optional[str],
		phenotype_desc: str,
		variation_id: Optional[int] = None,
		structural_key: Optional[str] = None,
		transcript_id: Optional[str] = None,
		exon_range: Optional[str] = None,
		**props: Any,
	) -> None:
		match_clause, params = self._build_variant_match_clause(
			variation_id,
			variant_hgvs_c,
			structural_key,
			transcript_id,
			exon_range,
		)
		query = f"""
		{match_clause}
		MATCH (p:Phenotype {{description: $phenotype}})
		MERGE (v)-[r:HAS_PHENOTYPE]->(p)
		SET r += $props
		"""
		self.run_query(
			query,
			{
				**params,
				"phenotype": phenotype_desc,
				"props": props,
			},
		)

    def link_disease_gene(self, disease_name: str, gene_symbol: str, **props: Any) -> None:
        query = """
        MATCH (d:Disease {name: $disease})
        MATCH (g:Gene {symbol: $gene})
        MERGE (d)-[r:ASSOCIATED_GENE]->(g)
        SET r += $props
        """
        self.run_query(query, {"disease": disease_name, "gene": gene_symbol, "props": props})

    def link_document_entity(self, document_id: str, entity_label: str, entity_key: str, entity_value: str, **props: Any) -> None:
        """通用: Document -[:MENTIONS]-> 任意实体"""
        query = f"""
        MATCH (doc:Document {{document_id: $doc_id}})
        MATCH (e:{entity_label} {{{entity_key}: $entity_value}})
        MERGE (doc)-[r:MENTIONS]->(e)
        SET r += $props
        """
        self.run_query(query, {"doc_id": document_id, "entity_value": entity_value, "props": props})

	def link_variant_evidence(
		self,
		variant_hgvs_c: Optional[str],
		evidence_id: str,
		variation_id: Optional[int] = None,
		structural_key: Optional[str] = None,
		transcript_id: Optional[str] = None,
		exon_range: Optional[str] = None,
	) -> None:
		match_clause, params = self._build_variant_match_clause(
			variation_id,
			variant_hgvs_c,
			structural_key,
			transcript_id,
			exon_range,
		)
		query = f"""
		{match_clause}
		MATCH (e:Evidence {{evidence_id: $evidence_id}})
		MERGE (v)-[:HAS_EVIDENCE]->(e)
		"""
		self.run_query(query, {**params, "evidence_id": evidence_id})

	def _build_variant_merge_clause(
		self,
		hgvs_c: Optional[str],
		structural_key: Optional[str],
		transcript_id: Optional[str],
		exon_range: Optional[str],
	) -> Tuple[str, Dict[str, Any]]:
		if hgvs_c:
			return "MERGE (v:Variant {hgvs_c: $variant_hgvs_c})", {"variant_hgvs_c": hgvs_c}
		if structural_key:
			return "MERGE (v:Variant {structural_key: $structural_key})", {"structural_key": structural_key}
		if transcript_id and exon_range:
			return (
				"MERGE (v:Variant {transcript_id: $variant_transcript, exon_range: $variant_exon_range})",
				{"variant_transcript": transcript_id, "variant_exon_range": exon_range},
			)
		raise ValueError("variant locator is required for upsert")

	def _build_variant_match_clause(
		self,
		variation_id: Optional[int],
		variant_hgvs_c: Optional[str],
		structural_key: Optional[str],
		transcript_id: Optional[str],
		exon_range: Optional[str],
	) -> Tuple[str, Dict[str, Any]]:
		if variation_id is not None:
			return "MATCH (v:Variant {variation_id: $variation_id})", {"variation_id": variation_id}
		if variant_hgvs_c:
			return "MATCH (v:Variant {hgvs_c: $variant_hgvs_c})", {
				"variant_hgvs_c": variant_hgvs_c,
			}
		if structural_key:
			return "MATCH (v:Variant {structural_key: $structural_key})", {"structural_key": structural_key}
		if transcript_id and exon_range:
			return (
				"MATCH (v:Variant {transcript_id: $variant_transcript, exon_range: $variant_exon_range})",
				{"variant_transcript": transcript_id, "variant_exon_range": exon_range},
			)
		raise ValueError("variant locator is required")

    def link_evidence_document(self, evidence_id: str, document_id: str) -> None:
        query = """
        MATCH (e:Evidence {evidence_id: $evidence_id})
        MATCH (doc:Document {document_id: $doc_id})
        MERGE (e)-[:FROM_DOCUMENT]->(doc)
        """
        self.run_query(query, {"evidence_id": evidence_id, "doc_id": document_id})

    # ==================== 检索 ====================

    def find_variant_evidence_graph(
        self,
        variant_hgvs_c: Optional[str] = None,
        variation_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """检索变异相关的完整证据子图"""
        if variation_id is not None:
            match_variant = "MATCH (v:Variant {variation_id: $variation_id})"
        elif variant_hgvs_c:
            match_variant = "MATCH (v:Variant {hgvs_c: $variant})"
        else:
            return []
        query = """
        {match_clause}
        OPTIONAL MATCH (g:Gene)-[:HAS_VARIANT]->(v)
        OPTIONAL MATCH (v)-[:HAS_PHENOTYPE]->(p:Phenotype)
        OPTIONAL MATCH (v)-[:HAS_EVIDENCE]->(e:Evidence)
        OPTIONAL MATCH (e)-[:FROM_DOCUMENT]->(doc:Document)
        RETURN v, g, p, e, doc
        """
        params = {"variant": variant_hgvs_c, "variation_id": variation_id}
        return self.run_query(query.format(match_clause=match_variant), params)

    def find_gene_related_variants(self, gene_symbol: str) -> List[Dict[str, Any]]:
        """查找基因相关的所有变异及其证据"""
        query = """
        MATCH (g:Gene {symbol: $gene})-[:HAS_VARIANT]->(v:Variant)
        OPTIONAL MATCH (v)-[:HAS_EVIDENCE]->(e:Evidence)
        OPTIONAL MATCH (e)-[:FROM_DOCUMENT]->(doc:Document)
        RETURN g.symbol AS gene, v.hgvs_c AS variant, v.hgvs_p AS protein_change,
               e.evidence_strength AS strength, doc.document_id AS document_id, doc.title AS doc_title
        ORDER BY e.evidence_strength
        """
        return self.run_query(query, {"gene": gene_symbol})

    def find_documents_for_variant(self, variant_hgvs_c: str) -> List[Dict[str, Any]]:
        """查找引用某变异的所有文献"""
        query = """
        MATCH (doc:Document)-[:MENTIONS]->(v:Variant {hgvs_c: $variant})
        RETURN doc.document_id AS document_id, doc.title AS title, doc.file_hash AS file_hash
        """
        return self.run_query(query, {"variant": variant_hgvs_c})

    def find_multi_document_evidence(
        self,
        gene_symbol: Optional[str] = None,
        variant_hgvs_c: Optional[str] = None,
        protein_change: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """多文献图谱检索：基于变异/基因/蛋白变化查找关联证据"""
        conditions = []
        params: Dict[str, Any] = {}

        if gene_symbol:
            conditions.append("g.symbol = $gene")
            params["gene"] = gene_symbol
        if variant_hgvs_c:
            conditions.append("v.hgvs_c = $variant")
            params["variant"] = variant_hgvs_c
        if protein_change:
            conditions.append("v.hgvs_p = $protein_change")
            params["protein_change"] = protein_change

        if not conditions:
            return []

        where_clause = " AND ".join(conditions)
        query = f"""
        MATCH (g:Gene)-[:HAS_VARIANT]->(v:Variant)
        WHERE {where_clause}
        OPTIONAL MATCH (v)-[:HAS_EVIDENCE]->(e:Evidence)
        OPTIONAL MATCH (e)-[:FROM_DOCUMENT]->(doc:Document)
        OPTIONAL MATCH (v)-[:HAS_PHENOTYPE]->(p:Phenotype)
        OPTIONAL MATCH (d:Disease)-[:ASSOCIATED_GENE]->(g)
        RETURN g.symbol AS gene, v.hgvs_c AS variant, v.hgvs_p AS protein_change,
               e.evidence_id AS evidence_id, e.evidence_strength AS strength, e.classification AS classification,
               doc.document_id AS document_id, doc.title AS doc_title,
               p.description AS phenotype, d.name AS disease
        ORDER BY doc.document_id
        """
        return self.run_query(query, params)

    def get_graph_statistics(self) -> Dict[str, int]:
        """获取图数据库统计信息"""
        query = """
        MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count
        UNION ALL
        MATCH ()-[r]->() RETURN type(r) AS label, count(r) AS count
        """
        rows = self.run_query(query)
        return {r["label"]: r["count"] for r in rows if r.get("label")}

    # ==================== 辅助 ====================

    def _single(self, query: str, params: Dict[str, Any]) -> Dict[str, Any]:
        results = self.run_query(query, params)
        return results[0] if results else {}

    def health_check(self) -> bool:
        try:
            self.run_query("RETURN 1 AS ok")
            return True
        except Exception:
            return False


# ==================== 全局单例 ====================

_neo4j_client: Optional[Neo4jClient] = None


def get_neo4j_client() -> Neo4jClient:
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient()
    return _neo4j_client
