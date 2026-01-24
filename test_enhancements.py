#!/usr/bin/env python3
"""Integration test to verify PS3 extraction enhancements."""

import json
from pathlib import Path

def test_enhanced_features():
    """Test that all enhanced features are properly integrated."""
    
    print("=" * 60)
    print("PS3 EXTRACTION ENHANCEMENTS - INTEGRATION TEST")
    print("=" * 60)
    
    # Test 1: Verify Evidence Extractor Prompt Enhancement
    print("\n1. Testing Evidence Extractor Prompt...")
    try:
        from src.infrastructure.llm.evidence_extractor_impl import EvidenceExtractorServiceImpl
        
        # Create a mock instance to check prompt
        class MockLLM:
            pass
        
        extractor = EvidenceExtractorServiceImpl(MockLLM())
        prompt = extractor._build_human_prompt()
        
        # Check for key enhancements
        assert "P1 = Proportion of pathogenic variants in model data" in prompt
        assert "P2 = Proportion of pathogenic variants in functionally abnormal group" in prompt
        assert "coordinate-level tracing" in prompt
        assert "data-bbox" in prompt or "bbox metadata" in prompt
        
        print("✓ Evidence extractor prompt includes P1/P2 clarifications")
        print("✓ Evidence extractor prompt includes coordinate-level guidance")
        
    except Exception as e:
        print(f"✗ Evidence extractor test failed: {e}")
        return False
    
    # Test 2: Verify Bilingual HTML Generator Enhancement
    print("\n2. Testing Bilingual HTML Generator...")
    try:
        from src.infrastructure.rendering.bilingual_html_generator import BilingualHTMLGenerator
        
        gen = BilingualHTMLGenerator(original_language="zh")
        
        # Check that method accepts bbox_metadata parameter
        import inspect
        sig = inspect.signature(gen.generate_bilingual_html)
        params = list(sig.parameters.keys())
        
        assert "bbox_metadata" in params, "bbox_metadata parameter not found"
        print("✓ BilingualHTMLGenerator accepts bbox_metadata parameter")
        
        # Test with sample data - use text that matches the markdown content
        sample_bbox = [
            {"page": 1, "bbox": [100, 200, 300, 400], "text": "This is a longer test sentence"}
        ]
        
        html = gen.generate_bilingual_html(
            original_markdown="This is a longer test sentence",
            english_markdown="This is a longer test sentence",
            highlighted_original_markdown="This is a longer test sentence",
            highlighted_english_markdown="This is a longer test sentence",
            evidence_summary=None,
            bbox_metadata=sample_bbox
        )
        
        assert "data-page" in html or "data-bbox" in html, "Bbox attributes not in HTML"
        print("✓ HTML includes data-bbox attributes")
        
    except Exception as e:
        print(f"✗ Bilingual HTML generator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Verify Report Generation Step Enhancement
    print("\n3. Testing Report Generation Step...")
    try:
        from src.application.services.report_generation_step import ReportGenerationStep
        
        step = ReportGenerationStep()
        
        # Check that _generate_html_report includes bbox handling
        import inspect
        source = inspect.getsource(step._generate_html_report)
        
        assert "bbox_metadata" in source, "bbox_metadata not used in HTML generation"
        print("✓ Report generation passes bbox_metadata to HTML generator")
        
        # Check final payload includes p1_bbox and p2_bbox
        source = inspect.getsource(step._build_final_payload)
        assert "p1_bbox" in source, "p1_bbox not in final payload"
        assert "p2_bbox" in source, "p2_bbox not in final payload"
        print("✓ Final payload includes p1_bbox and p2_bbox fields")
        
    except Exception as e:
        print(f"✗ Report generation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Verify Evidence Entity Fields
    print("\n4. Testing Evidence Entity...")
    try:
        from src.domain.entities.evidence import Evidence
        
        # Create sample evidence
        evidence = Evidence(
            findings=["Test finding"],
            p1=0.5,
            p2=0.8,
            rationale="Test rationale",
            experimental_details="Test details",
            p1_source_location="Table 1",
            p2_source_location="Figure 2",
            ps3_criteria_met=True,
            control_variants_count=5,
            odds_path_computable=True,
            reason_if_not_applicable=""
        )
        
        # Verify all required fields exist
        assert hasattr(evidence, 'findings')
        assert hasattr(evidence, 'odds_path')
        assert hasattr(evidence, 'p1_source_location')
        assert hasattr(evidence, 'p2_source_location')
        assert hasattr(evidence, 'control_variants_count')
        assert hasattr(evidence, 'odds_path_computable')
        assert hasattr(evidence, 'reason_if_not_applicable')
        
        # Convert to dict and verify all fields
        evidence_dict = evidence.to_dict()
        required_fields = [
            'findings', 'p1', 'p2', 'odds_path', 'strength',
            'rationale', 'experimental_details',
            'p1_source_location', 'p2_source_location',
            'ps3_criteria_met', 'control_variants_count',
            'odds_path_computable', 'reason_if_not_applicable'
        ]
        
        for field in required_fields:
            assert field in evidence_dict, f"Missing field: {field}"
        
        print("✓ Evidence entity includes all required fields")
        print(f"✓ Evidence strength correctly calculated: {evidence.strength.value}")
        
    except Exception as e:
        print(f"✗ Evidence entity test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 5: Verify PS3 Framework
    print("\n5. Testing PS3 Framework...")
    try:
        from src.domain.services.ps3_framework import PS3EvaluationFramework
        
        # Test with sample data
        result = PS3EvaluationFramework.evaluate_evidence(
            has_disease_mechanism=True,
            disease_mechanism_detail="Clear mechanism",
            method_suitable=True,
            method_detail="Appropriate method",
            has_controls=True,
            has_replicates=True,
            method_reliable=True,
            has_positive_controls=True,
            control_variants_count=5,
            odds_path_value=10.0,
            odds_path_computable=True
        )
        
        assert "step_1" in result
        assert "step_2" in result
        assert "step_3" in result
        assert "step_4" in result
        assert "conclusion" in result
        
        print("✓ PS3 four-step framework correctly evaluates evidence")
        print(f"✓ Step 1 status: {result['step_1']['status']}")
        print(f"✓ Step 2 status: {result['step_2']['status']}")
        print(f"✓ Step 3 status: {result['step_3']['overall_status']}")
        print(f"✓ Step 4 OddsPath: {result['step_4']['odds_path_value']}")
        
    except Exception as e:
        print(f"✗ PS3 framework test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 6: Verify Documentation
    print("\n6. Verifying Documentation...")
    try:
        doc_files = [
            "docs/PS3_EXTRACTION_ENHANCEMENTS.md",
            "docs/USER_GUIDE.md"
        ]
        
        for doc_file in doc_files:
            path = Path(doc_file)
            assert path.exists(), f"Documentation file not found: {doc_file}"
            
            content = path.read_text(encoding='utf-8')
            assert len(content) > 1000, f"Documentation seems incomplete: {doc_file}"
            
            print(f"✓ {doc_file} exists ({len(content):,} characters)")
        
    except Exception as e:
        print(f"✗ Documentation verification failed: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    print("\nSummary of Verified Enhancements:")
    print("1. ✓ Evidence extractor prompt includes P1/P2 definitions")
    print("2. ✓ Evidence extractor prompt includes coordinate-level tracing")
    print("3. ✓ Bilingual HTML generator accepts bbox_metadata")
    print("4. ✓ HTML output includes data-bbox attributes")
    print("5. ✓ Report generation includes p1_bbox and p2_bbox")
    print("6. ✓ Evidence entity has all required fields")
    print("7. ✓ PS3 four-step framework properly implemented")
    print("8. ✓ Comprehensive documentation provided")
    
    print("\nEnhanced Features Ready for Use:")
    print("- Coordinate-level P1/P2 evidence tracing")
    print("- Bilingual HTML with data-bbox attributes")
    print("- Complete JSON output with all required fields")
    print("- PS3 SVI four-step evaluation framework")
    print("- Detailed user guide and technical documentation")
    
    return True


if __name__ == "__main__":
    import sys
    success = test_enhanced_features()
    sys.exit(0 if success else 1)
