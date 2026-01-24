"""
主入口脚本：5阶段结构化PDF处理

使用说明：
    python -m src.application.five_stages_main_entry \
        --pdf-path /path/to/input.pdf \
        --output-dir /path/to/output
"""

import argparse
import sys
from pathlib import Path
import json

from src.application.dto import ProcessPDFRequest, ProcessPDFResponse
from src.application.services.complete_five_stages_pipeline import CompleteFiveStagesPipelineOrchestrator
from src.infrastructure.utils.logger import Logger


def main():
    """Main entry point for 5-stage pipeline."""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="5-stage structured PDF processing pipeline"
    )
    parser.add_argument(
        "--pdf-path",
        required=True,
        help="Path to input PDF file"
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory for results"
    )
    parser.add_argument(
        "--language",
        default="auto",
        help="Source language (auto/Chinese/English/Japanese/Russian/German/French)"
    )
    
    args = parser.parse_args()
    
    # Initialize logger
    logger = Logger.get_logger(__name__)
    
    # Validate inputs
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        return 1
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 80)
    logger.info("5-STAGE STRUCTURED PDF PROCESSING PIPELINE")
    logger.info("=" * 80)
    logger.info(f"Input PDF: {pdf_path}")
    logger.info(f"Output directory: {output_dir}")
    
    try:
        # Initialize pipeline (with mock repositories for demonstration)
        from src.infrastructure.repositories.pdf_repository import PDFRepository
        from src.infrastructure.repositories.rag_repository import RAGRepository
        
        pdf_repo = PDFRepository()
        rag_repo = RAGRepository()
        
        orchestrator = CompleteFiveStagesPipelineOrchestrator(
            pdf_repository=pdf_repo,
            rag_repository=rag_repo,
            mt_llm_client=None,  # Will use default from .env
            arbiter_llm_client=None  # Will use default from .env
        )
        
        # Create processing request
        request = ProcessPDFRequest(
            pdf_path=str(pdf_path),
            out_dir=str(output_dir),
            language=args.language
        )
        
        # Execute pipeline
        response = orchestrator.process_pdf(request)
        
        if response.success:
            logger.info("\n" + "=" * 80)
            logger.info("PIPELINE EXECUTION SUCCESSFUL")
            logger.info("=" * 80)
            logger.info("\nOutput variables (with {{...}} placeholders):")
            
            for key, value in response.results.items():
                if isinstance(value, dict) and len(str(value)) > 100:
                    logger.info(f"  {key}: {type(value).__name__} ({len(value)} entries)")
                else:
                    logger.info(f"  {key}: {value}")
            
            # Save results manifest
            manifest_path = output_dir / "results_manifest.json"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(response.results, f, indent=2, ensure_ascii=False)
            logger.info(f"\nResults manifest saved to: {manifest_path}")
            
            return 0
        else:
            logger.error(f"Pipeline failed: {response.error_message}")
            return 1
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
