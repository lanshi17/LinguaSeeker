"""OCR service using Alibaba Cloud Qwen-VL-OCR."""

import base64
from pathlib import Path
from typing import List
from io import BytesIO

from openai import OpenAI
from pdf2image import convert_from_path

from src.infrastructure.utils.config import LLMConfig
from src.infrastructure.utils.exceptions import ParsingException
from src.infrastructure.utils.logger import Logger


class QwenOCRService:
    """OCR service using Qwen-VL-OCR model with multi-image batch processing."""
    
    def __init__(self, config: LLMConfig, batch_size: int = 1):
        """Initialize OCR service.
        
        Args:
            config: LLM configuration containing OCR settings
            batch_size: Number of pages to process in one API call (default: 1, single page at a time)
        """
        self.config = config
        self.batch_size = batch_size  # Set to 1 for single-page processing
        self.logger = Logger.get_logger(__name__)
        
        # Initialize OpenAI-compatible client
        self.client = OpenAI(
            api_key=config.ocr_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
    def pdf_to_markdown(self, pdf_path: str) -> str:
        """Convert PDF to markdown using OCR with batch processing.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Markdown formatted text
            
        Raises:
            ParsingException: If OCR fails
        """
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise ParsingException(f"PDF not found: {pdf_path}")
        
        self.logger.info(f"Starting OCR for PDF: {pdf_path}")
        
        # Convert PDF to images
        try:
            images = convert_from_path(pdf_path)
            self.logger.info(f"Converted PDF to {len(images)} images")
        except Exception as e:
            raise ParsingException(f"Failed to convert PDF to images: {e}")
        
        # Process images in batches
        all_results = []
        for i in range(0, len(images), self.batch_size):
            batch = images[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(images) + self.batch_size - 1) // self.batch_size
            
            self.logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} pages)")
            
            try:
                result = self._ocr_batch(batch, start_page=i+1)
                all_results.append(result)
            except Exception as e:
                self.logger.error(f"Failed to OCR batch {batch_num}: {e}")
                # Add placeholder for failed batch
                for page_idx in range(len(batch)):
                    page_num = i + page_idx + 1
                    all_results.append(f"# Page {page_num}\n\n[OCR Failed: {str(e)}]")
        
        return "\n\n---\n\n".join(all_results)
    
    def _ocr_batch(self, images: List, start_page: int = 1) -> str:
        """OCR a batch of images using Qwen-VL-OCR API with multi-image input.
        
        Args:
            images: List of PIL Image objects
            start_page: Starting page number for this batch
            
        Returns:
            OCR result text with page markers
        """
        # Convert images to base64 data URIs
        image_contents = []
        for image in images:
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            img_data_uri = f"data:image/png;base64,{img_base64}"
            
            image_contents.append({
                "type": "image_url",
                "image_url": {"url": img_data_uri}
            })
        
        # Add text prompt asking for document parsing
        image_contents.append({
            "type": "text",
            "text": "请对这个文档图片进行OCR识别，保持原始格式和结构，使用LaTeX格式输出数学公式和表格。请完整识别所有文本内容。"
        })
        
        # Prepare request using OpenAI-compatible format
        messages = [
            {
                "role": "user",
                "content": image_contents
            }
        ]
        
        # Send request
        try:
            completion = self.client.chat.completions.create(
                model=self.config.ocr_model,
                messages=messages,
                timeout=120.0
            )
            
            # Extract text from response
            if completion.choices and len(completion.choices) > 0:
                result_text = completion.choices[0].message.content
                
                # For single-page processing, add page header
                if len(images) == 1:
                    return f"# Page {start_page}\n\n{result_text}"
                
                # For multi-page batch (if batch_size > 1), return combined content
                # Note: API combines content, so we return as-is with first page marker
                return f"# Page {start_page}\n\n{result_text}"
            
            self.logger.warning("No content in OCR response")
            return f"# Page {start_page}\n\n[No OCR result]"
                    
        except Exception as e:
            error_msg = f"OCR API error: {e}"
            self.logger.error(error_msg)
            raise ParsingException(error_msg)
    
    def _ocr_image(self, image) -> str:
        """OCR a single image (legacy method for compatibility).
        
        Args:
            image: PIL Image object
            
        Returns:
            OCR result text
        """
        result = self._ocr_batch([image], start_page=1)
        # Remove page header for single image
        if result.startswith("# Page 1\n\n"):
            return result[len("# Page 1\n\n"):]
        return result
