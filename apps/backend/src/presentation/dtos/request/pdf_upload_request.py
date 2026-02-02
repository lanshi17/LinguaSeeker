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

    @validator("file_content")
    def validate_file_content(cls, v, values):
        if v is None:
            return v
        # Validate that the content is valid base64
        try:
            decoded = base64.b64decode(v, validate=True)
            # Optional: Check if it looks like a PDF (starts with %PDF-)
            if len(decoded) > 4 and decoded[:4] != b"%PDF":
                raise ValueError("File content does not appear to be a valid PDF")
            return v
        except ValueError as e:
            # Ensure we don't include bytes objects in the error message
            error_msg = str(e)
            if isinstance(error_msg, bytes):
                error_msg = error_msg.decode("utf-8", errors="replace")
            raise ValueError(f"Invalid base64 encoded file content: {error_msg}")
