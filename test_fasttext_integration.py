#!/usr/bin/env python3
"""Quick test of FastText language detection integration."""

import os
from pathlib import Path
from src.infrastructure.utils.config import AppConfig
from src.infrastructure.ocr.mineru_ocr_service import MinerUOCRService

# Set up environment
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""

def test_fasttext_language_detection():
    """Test FastText language detection with sample PDFs."""
    config = AppConfig.from_env()
    service = MinerUOCRService(config.llm)
    
    test_pdfs = [
        "simple_pdfs/sample_chinese.pdf",
    ]
    
    print("=" * 70)
    print("FastText Language Detection Integration Test")
    print("=" * 70)
    
    for pdf_path in test_pdfs:
        pdf = Path(pdf_path)
        if not pdf.exists():
            print(f"\n✗ PDF not found: {pdf_path}")
            continue
        
        print(f"\nTesting: {pdf.name}")
        print("-" * 70)
        
        try:
            detected_lang = service._detect_language(pdf)
            print(f"✓ Detected language: {detected_lang}")
            
            # Also test the MinerU API batch workflow
            print(f"\nTesting MinerU batch API workflow...")
            out_dir = Path("outputs/test_fasttext")
            out_dir.mkdir(parents=True, exist_ok=True)
            
            extraction_result = service._run_http_api(pdf, out_dir, enable_translation=True)
            print(f"✓ Extraction completed!")
            print(f"  - Batch ID: {extraction_result.get('batch_id')}")
            print(f"  - Detected Language: {extraction_result.get('detected_language')}")
            print(f"  - Extraction Path: {extraction_result.get('full_zip_path')}")
            
            # Check extracted files
            extracted_dir = Path(extraction_result.get('full_zip_path'))
            if extracted_dir.exists():
                files = list(extracted_dir.glob('*'))
                print(f"  - Files extracted: {len(files)}")
                for f in files[:5]:
                    print(f"    - {f.name}")
                if len(files) > 5:
                    print(f"    ... and {len(files) - 5} more")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("Test completed!")
    print("=" * 70)

if __name__ == "__main__":
    test_fasttext_language_detection()
