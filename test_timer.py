#!/usr/bin/env python3
"""计时器功能测试脚本"""

import time
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from infrastructure.utils.timer import (
    Timer,
    measure_time,
    get_timer_stats,
    print_timer_stats,
    timer,
    configure_timer,
    TimerConfig,
    ConsoleOutput,
)


def test_basic_timer():
    """测试基础计时器"""
    print("\n✅ 测试1: 基础计时器")
    print("-" * 60)

    t = Timer('基础计时', silent=False)
    t.start()
    time.sleep(0.1)
    duration = t.stop()
    
    assert 0.09 < duration < 0.15, f"Duration {duration} not in range"
    print(f"✓ 基础计时通过: {duration:.4f}s")


def test_context_manager():
    """测试上下文管理器"""
    print("\n✅ 测试2: 上下文管理器")
    print("-" * 60)

    with Timer('上下文计时', silent=False) as t:
        time.sleep(0.05)

    assert 0.04 < t.duration < 0.1, f"Duration {t.duration} not in range"
    print(f"✓ 上下文管理器通过: {t.duration:.4f}s")


def test_decorator():
    """测试装饰器"""
    print("\n✅ 测试3: 装饰器")
    print("-" * 60)

    @timer('装饰器函数')
    def slow_function():
        time.sleep(0.05)
        return "result"

    result = slow_function()
    assert result == "result"
    print("✓ 装饰器通过")


def test_measure_time_context():
    """测试便捷上下文函数"""
    print("\n✅ 测试4: 便捷上下文函数")
    print("-" * 60)

    with measure_time('便捷函数计时', silent=False):
        time.sleep(0.05)

    print("✓ 便捷上下文函数通过")


def test_nested_timing():
    """测试嵌套计时"""
    print("\n✅ 测试5: 嵌套计时")
    print("-" * 60)

    with Timer('外层任务', silent=False):
        time.sleep(0.05)
        with Timer('内层任务1', silent=False):
            time.sleep(0.03)
        with Timer('内层任务2', silent=False):
            time.sleep(0.02)

    print("✓ 嵌套计时通过")


def test_stats_collection():
    """测试统计数据收集"""
    print("\n✅ 测试6: 统计数据收集")
    print("-" * 60)

    for i in range(3):
        with Timer('重复任务', silent=True):
            time.sleep(0.01)

    stats = get_timer_stats('重复任务')
    assert stats is not None
    assert stats['count'] == 3, f"Expected count=3, got {stats['count']}"
    assert stats['total'] > 0.025, f"Expected total > 0.025, got {stats['total']}"

    print(f"✓ 统计数据通过: {stats['count']} 次, 总耗时 {stats['total']:.4f}s")


def test_pipeline_simulation():
    """模拟管线计时（类似ACMG处理流程）"""
    print("\n✅ 测试7: 管线模拟")
    print("-" * 60)

    with Timer('完整管线', silent=False):
        with Timer('PDF处理', silent=False):
            time.sleep(0.05)
        
        with Timer('文本翻译', silent=False):
            time.sleep(0.08)
        
        with Timer('证据提取', silent=False):
            time.sleep(0.06)
        
        with Timer('结果生成', silent=False):
            time.sleep(0.03)

    print("✓ 管线模拟通过")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("计时器功能测试套件".center(60))
    print("=" * 60)

    try:
        test_basic_timer()
        test_context_manager()
        test_decorator()
        test_measure_time_context()
        test_nested_timing()
        test_stats_collection()
        test_pipeline_simulation()

        # 打印统计汇总
        print_timer_stats()

        print("=" * 60)
        print("✅ 所有测试通过！".center(60))
        print("=" * 60 + "\n")
        return 0

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
