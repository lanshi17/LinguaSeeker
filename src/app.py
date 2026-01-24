#!/usr/bin/env python3
"""ACMG PS3 Evidence Extraction Platform - Unified Entry Point.

Supports both CLI and FastAPI server modes.
Uses Domain-Driven Design architecture with clean separation of concerns.
"""

import argparse
import sys
from pathlib import Path

from src.application.pipeline_runner import run_pipeline_refactored
from src.presentation.api_app import app as fastapi_app


def main():
    """Main entry point with mode selection (CLI or API)."""
    parser = argparse.ArgumentParser(
        description="ACMG PS3 Evidence Extraction Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # CLI mode: Process a PDF with default output directory
  uv run main.py input.pdf
  
  # CLI mode: Process with custom output directory
  uv run main.py input.pdf --out-dir ./results
  
  # API mode: Start FastAPI server
  uv run main.py --api --port 8000
        """,
    )
    
    # Mode argument
    parser.add_argument(
        "--api",
        action="store_true",
        help="Run FastAPI server instead of CLI mode",
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for FastAPI server (default: 8000)",
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host for FastAPI server (default: 127.0.0.1)",
    )
    
    # CLI mode arguments
    parser.add_argument(
        "pdf_path",
        nargs="?",
        type=str,
        help="Path to the input PDF file (CLI mode)",
    )
    
    parser.add_argument(
        "--out-dir",
        type=str,
        default="outputs",
        help="Output directory for results (default: outputs, CLI mode)",
    )
    
    args = parser.parse_args()
    
    # API mode
    if args.api:
        return _run_api_server(args.host, args.port)
    
    # CLI mode
    return _run_cli_mode(args.pdf_path, args.out_dir)


def _run_api_server(host: str, port: int) -> int:
    """Run FastAPI server.
    
    Args:
        host: Server host
        port: Server port
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        import uvicorn
        
        print(f"Starting FastAPI server on {host}:{port}...")
        print(f"API documentation: http://{host}:{port}/api/v1/docs")
        
        uvicorn.run(
            fastapi_app,
            host=host,
            port=port,
            log_level="info",
        )
        return 0
    except ImportError:
        print("Error: uvicorn is required for API mode. Install it with: pip install uvicorn", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"API server error: {e}", file=sys.stderr)
        return 1


def _run_cli_mode(pdf_path: str, out_dir: str) -> int:
    """Run CLI mode for PDF processing.
    
    Args:
        pdf_path: Path to PDF file
        out_dir: Output directory
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    
    # Validate input file
    if not pdf_path:
        print("Error: pdf_path is required in CLI mode", file=sys.stderr)
        print("Use --api to run API server mode", file=sys.stderr)
        return 1
    
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"Error: Input file not found: {pdf_path}", file=sys.stderr)
        return 1
    
    if not pdf_file.suffix.lower() == ".pdf":
        print(f"Error: Input file must be a PDF: {pdf_path}", file=sys.stderr)
        return 1
    
    # Run pipeline
    print(f"Processing PDF: {pdf_path}")
    print(f"Output directory: {out_dir}")
    print("-" * 60)
    
    try:
        result = run_pipeline_refactored(pdf_path=pdf_path, out_dir=out_dir)
        
        # Display summary
        print("\n" + "=" * 60)
        print("PROCESSING COMPLETE")
        print("=" * 60)
        print(f"Detected Language: {result['detected_language']}")
        arb_score = result.get('arbiter_score') or 0.0
        print(f"Arbiter Score: {arb_score:.1f}/100")
        evidence_obj = result.get('evidence') or {}
        evidence_count = len(evidence_obj.get('findings', [])) if isinstance(evidence_obj, dict) else len(evidence_obj)
        print(f"Evidence Count: {evidence_count}")
        print(f"\nOutput Files:")
        if result.get('output_html'):
            print(f"  - 📄 HTML Report: {result['output_html']}")
        elif result.get('html_report_path'):
            print(f"  - 📊 HTML Report: {result['html_report_path']}")
        if result.get('evidence_json_path'):
            print(f"  - Evidence JSON: {result['evidence_json_path']}")
        if result.get('final_structured_path'):
            print(f"  - Final Structured JSON: {result['final_structured_path']}")
        if result.get('bbox_metadata_path'):
            print(f"  - BBox metadata: {result['bbox_metadata_path']}")
        if result.get('html_report_path'):
            print(f"  - 📊 HTML Report: {result['html_report_path']}")
        
        if arb_score >= 75:
            print("\n✓ Quality threshold met (≥75)")
        else:
            print(f"\n⚠ Quality below threshold ({arb_score:.1f} < 75)")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
