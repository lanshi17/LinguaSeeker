#!/usr/bin/env python3
"""Simple ACMG PS3 Evidence Extraction Agent - Entry Point.

This is the main command-line interface for the ACMG PS3 pipeline.
Uses Domain-Driven Design architecture with clean separation of concerns.
"""

import argparse
import sys
from pathlib import Path

from src.domain.interfaces import run_pipeline_refactored


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="ACMG PS3 Evidence Extraction Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a PDF with default output directory
  uv run src/simple_acmgAgent.py input.pdf
  
  # Process with custom output directory
  uv run src/simple_acmgAgent.py input.pdf --out-dir ./results
  
  # Or use main.py
  uv run main.py input.pdf
        """,
    )
    
    parser.add_argument(
        "pdf_path",
        type=str,
        help="Path to the input PDF file",
    )
    
    parser.add_argument(
        "--out-dir",
        type=str,
        default="outputs",
        help="Output directory for results (default: outputs)",
    )
    
    args = parser.parse_args()
    
    # Validate input file
    pdf_file = Path(args.pdf_path)
    if not pdf_file.exists():
        print(f"Error: Input file not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)
    
    if not pdf_file.suffix.lower() == ".pdf":
        print(f"Error: Input file must be a PDF: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)
    
    # Run pipeline
    print(f"Processing PDF: {args.pdf_path}")
    print(f"Output directory: {args.out_dir}")
    print("-" * 60)
    
    try:
        result = run_pipeline_refactored(pdf_path=args.pdf_path, out_dir=args.out_dir)
        
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
