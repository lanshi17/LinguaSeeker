from pydantic import BaseModel, Field
from typing import Optional, Union
from enum import Enum


class UploadSource(str, Enum):
    FILE = "file"
    PMID = "pmid"
    DOI = "doi"


class PDFUploadRequest(BaseModel):
    """
    Request DTO for uploading PDF documents or fetching by PMID/DOI.

    Either file_content OR (pmid OR doi) must be provided.
    """

    file_content: Optional[str] = Field(
        default=None,
        description="Base64 encoded PDF file content",
        json_schema_extra={"example": "JVBERi0xLjQKJcfs..."},
    )
    filename: Optional[str] = Field(
        default=None,
        description="Original filename of the uploaded PDF",
        json_schema_extra={"example": "research_paper.pdf"},
    )
    pmid: Optional[str] = Field(
        default=None,
        description="PubMed ID for automatic document fetching",
        json_schema_extra={"example": "12345678"},
    )
    doi: Optional[str] = Field(
        default=None,
        description="DOI for automatic document fetching",
        json_schema_extra={"example": "10.1038/s41586-023-06221-2"},
    )
    source: UploadSource = Field(
        UploadSource.FILE, description="Source of the document upload"
    )
    priority: Optional[int] = Field(
        0,
        description="Processing priority (0 = normal, higher = more urgent)",
        ge=0,
        le=10,
    )
    client_hash: Optional[str] = Field(
        default=None,
        description="Client-calculated hash for debugging mismatches",
        json_schema_extra={"example": "ccbdf673..."},
    )
    content_hash: Optional[str] = Field(
        default=None,
        description="(internal) SHA256 hash of the uploaded PDF for duplicate detection",
        exclude=True,
        repr=False,
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "file_content": "JVBERi0xLjQKJcfs...",
                "filename": "acmg_evidence_study.pdf",
                "source": "file",
                "priority": 0,
            }
        }
    }
