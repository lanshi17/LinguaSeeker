"""图数据库实体 - 对应Neo4j节点"""
from typing import Optional, List


class Paper:
    """文献节点"""
    
    def __init__(
        self,
        pmid: str,
        title: str,
        year: int,
        doi: Optional[str] = None,
        file_path: Optional[str] = None
    ):
        self.pmid = pmid
        self.title = title
        self.year = year
        self.doi = doi
        self.file_path = file_path


class Gene:
    """基因节点"""
    
    def __init__(
        self,
        symbol: str,
        hgnc_id: Optional[str] = None
    ):
        self.symbol = symbol
        self.hgnc_id = hgnc_id


class Variant:
    """变异节点"""
    
    def __init__(
        self,
        cdna_change: str,
        protein_change: Optional[str] = None,
        genomic_coord: Optional[str] = None
    ):
        self.cdna_change = cdna_change
        self.protein_change = protein_change
        self.genomic_coord = genomic_coord


class Disease:
    """疾病节点"""
    
    def __init__(
        self,
        name: str,
        phenotype_ontology_id: Optional[str] = None
    ):
        self.name = name
        self.phenotype_ontology_id = phenotype_ontology_id


class Method:
    """实验方法节点"""
    
    def __init__(
        self,
        name: str,
        category: Optional[str] = None
    ):
        self.name = name
        self.category = category  # 例如: "Kinase assay", "Western Blot"


class Evidence:
    """证据节点"""
    
    def __init__(
        self,
        snippet_text: str,
        confidence: float,
        source_page: Optional[int] = None,
        support_level: Optional[str] = None
    ):
        self.snippet_text = snippet_text
        self.confidence = confidence
        self.source_page = source_page
        self.support_level = support_level  # 例如: "PS3_Strong"
