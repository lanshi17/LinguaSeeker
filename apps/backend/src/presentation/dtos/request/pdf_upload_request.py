from pydantic import BaseModel, Field, validator
from typing import Optional, Union
from enum import Enum
import base64


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
        None,
        description="Base64 encoded PDF file content",
        example="JVBERi0xLjQKJcfs..."
    )
    filename: Optional[str] = Field(
        None,
        description="Original filename of the uploaded PDF",
        example="research_paper.pdf"
    )
    pmid: Optional[str] = Field(
        None,
        description="PubMed ID for automatic document fetching",
        example="12345678"
    )
    doi: Optional[str] = Field(
        None,
        description="DOI for automatic document fetching",
        example="10.1038/s41586-023-06221-2"
    )
    source: UploadSource = Field(
        UploadSource.FILE,
        description="Source of the document upload"
    )
    priority: Optional[int] = Field(
        0,
        description="Processing priority (0 = normal, higher = more urgent)",
        ge=0,
        le=10
    )

    class Config:
        schema_extra = {
            "example": {
                "file_content": "JVBERi0xLjQKJcfs...",
                "filename": "acmg_evidence_study.pdf",
                "source": "file",
                "priority": 0
            }
        }

    @validator('file_content')
    def validate_file_content(cls, v, values):
        if v is None:
            return v
        # Validate that the content is valid base64
        try:
            decoded = base64.b64decode(v, validate=True)
            # Optional: Check if it looks like a PDF (starts with %PDF-)
            if len(decoded) > 4 and decoded[:4] != b'%PDF':
                raise ValueError("File content does not appear to be a valid PDF")
            return v
        except Exception as e:
            raise ValueError(f"Invalid base64 encoded file content: {str(e)}")