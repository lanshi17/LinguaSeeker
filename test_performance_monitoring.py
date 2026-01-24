#!/usr/bin/env python3
"""性能监控测试脚本 - 处理指定PDF并记录各步骤耗时"""

import sys
from pathlib import Path

from src.domain.interfaces import run_pipeline_refactored
from src.infrastructure.utils.timer import print_timer_stats, clear_timer_stats


def main():
    """运行性能监控测试"""
    # 指定的俄文PDF文件
    pdf_file = "inputs/ФЕНОТИП СЕМЕЙНОЙ ГЕТЕРОЗИГОТНОЙ ГИПЕРХОЛЕСТЕРИНЕМИИ, ОБУСЛОВЛЕННОЙ ДЕЛЕЦИЕЙ ЭКЗОНОВ 2-10 ГЕНА LDLR: КЛИНИЧЕСКИЙ СЛУЧАЙ.pdf"
    
    if not Path(pdf_file).exists():
        print(f"❌ 错误: PDF文件不存在: {pdf_file}")
        return 1
    
    print("\n" + "=" * 80)
    print("ACMG管线性能监控测试".center(80))
    print("=" * 80)
    print(f"📄 输入文件: {pdf_file}")
    print(f"📁 输出目录: outputs/performance_test")
    print("=" * 80 + "\n")
    
    try:
        # 清除之前的统计
        clear_timer_stats()
        
        # 运行重构后的管线（已集成timer）
        print("⏱ 开始处理...\n")
        result = run_pipeline_refactored(
            pdf_path=pdf_file,
            out_dir="outputs/performance_test"
        )
        
        # 显示处理结果摘要
        print("\n" + "=" * 80)
        print("处理结果摘要".center(80))
        print("=" * 80)
        print(f"✓ 检测语言: {result['detected_language']}")
        print(f"✓ 仲裁评分: {result.get('arbiter_score', 0):.1f}/100")
        print(f"✓ 输出HTML: {result.get('output_html') or result.get('html_report_path')}")
        print(f"✓ 输出JSON: {result['final_structured_path']}")
        print("=" * 80 + "\n")
        
        # 打印性能统计
        print_timer_stats()
        
        print("=" * 80)
        print("✅ 性能监控测试完成！".center(80))
        print("=" * 80 + "\n")
        
        return 0
        
    except FileNotFoundError as e:
        print(f"❌ 文件错误: {e}")
        return 1
    except Exception as e:
        print(f"❌ 处理错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
