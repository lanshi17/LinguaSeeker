#!/usr/bin/env python3
"""Test if encoding fix is being applied during PDF processing"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def test_fix_method():
    """Test the static method directly"""
    from src.infrastructure.repositories.pdf_repository_impl import PDFRepositoryImpl
    
    garbled = '\x83V\x83\x93\x83|\x83W\x83E\x83\x80(II)'
    fixed = PDFRepositoryImpl._fix_ocr_encoding(garbled)
    
    print(f"Input (garbled): {repr(garbled)}")
    print(f"Output (fixed): {repr(fixed)}")
    print(f"Readable: {fixed}")
    
    # Check if fix worked
    has_hiragana = any('\u3040' <= c <= '\u309f' for c in fixed)
    has_katakana = any('\u30a0' <= c <= '\u30ff' for c in fixed)
    is_readable = has_hiragana or has_katakana
    
    print(f"Has hiragana/katakana: {is_readable}")
    
    if is_readable and '(II)' in fixed:
        print("✓ Fix method works correctly!")
        return True
    else:
        print("✗ Fix method didn't work")
        return False

if __name__ == '__main__':
    success = test_fix_method()
    sys.exit(0 if success else 1)
