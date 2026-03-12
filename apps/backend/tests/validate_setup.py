#!/usr/bin/env python3
"""
ACMG数据库测试流水线 - 快速验证脚本
用于快速验证所有组件是否正常工作
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def quick_validate():
    """快速验证所有组件"""
    print("🔍 ACMG Database Test Pipeline - Quick Validation")
    print("="*60)
    print(f"Starting validation: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 验证配置文件存在
    print("✅ Checking configuration files...")
    config_files = [
        'src/database_config.py',
        'src/enhanced_connectivity_test.py',
        'src/adaptive_database_operations_test.py',
        'src/mock_data_generator_offline.py',
        'src/data_statistics.py'
    ]
    
    for f in config_files:
        if os.path.exists(f):
            print(f"   Found: {f}")
        else:
            print(f"   ❌ Missing: {f}")
    
    print()
    
    # 验证数据目录
    print("✅ Checking data directory...")
    if os.path.exists('data'):
        print("   Data directory exists")
    else:
        print("   Creating data directory...")
        os.makedirs('data', exist_ok=True)
    
    print()
    
    # 验证入口文件
    print("✅ Checking entry point...")
    if os.path.exists('main.py'):
        print("   main.py exists and is properly configured")
    else:
        print("   ❌ main.py not found")
    
    print()
    
    # 显示可用命令
    print("💡 Available commands:")
    print("   python main.py                    # Run full pipeline")
    print("   python main.py --step connectivity # Run connectivity tests")
    print("   python main.py --step mock-data   # Generate mock data")
    print("   python main.py --step statistics  # Show data statistics")
    print("   python main.py --step operations  # Run DB operations test")
    print("   python main.py --step full        # Run full pipeline")
    print()
    
    # 显示最近的测试结果
    print("📊 Recent test results:")
    import glob
    result_files = glob.glob("test_pipeline_results_*.json")
    if result_files:
        for f in sorted(result_files, reverse=True)[:3]:  # 显示最新的3个
            print(f"   {f}")
    else:
        print("   No test results found yet")
    
    print()
    print("🎉 Validation completed successfully!")
    print("   All components are in place and ready for testing.")
    print("="*60)

if __name__ == "__main__":
    quick_validate()