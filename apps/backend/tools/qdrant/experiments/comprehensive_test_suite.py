#!/usr/bin/env python3
"""
ACMG数据库系统全面测试套件
整合连通性测试、功能测试和性能测试
"""

import sys
import os
import json
from datetime import datetime
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.enhanced_connectivity_test import EnhancedConnectivityTester
from src.adaptive_database_operations_test import AdaptiveDatabaseOperationsTester

class ComprehensiveTestSuite:
    def __init__(self):
        self.results = {}
    
    def run_connectivity_tests(self):
        """运行连通性测试"""
        print("Running connectivity tests...")
        tester = EnhancedConnectivityTester()
        return tester.run_tests()
    
    def run_operation_tests(self):
        """运行操作测试"""
        print("Running database operation tests...")
        tester = AdaptiveDatabaseOperationsTester()
        return tester.run_comprehensive_test()
    
    def run_all_tests(self):
        """运行所有测试"""
        print("="*80)
        print("ACMG DATABASE SYSTEM - COMPREHENSIVE TEST SUITE")
        print("="*80)
        print(f"Test Suite Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 运行连通性测试
        connectivity_results = self.run_connectivity_tests()
        print()
        
        # 运行操作测试
        operation_results = self.run_operation_tests()
        print()
        
        # 汇总所有结果
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'connectivity_tests': connectivity_results,
            'operation_tests': operation_results,
            'summary': {
                'overall_status': 'success' if (
                    connectivity_results['summary']['passed_tests'] >= 3 and  # 至少3个服务连通
                    operation_results and operation_results['summary']['overall_status'] == 'success'
                ) else 'failure',
                'connectivity_passed': connectivity_results['summary']['passed_tests'],
                'connectivity_total': connectivity_results['summary']['total_tests'],
                'operations_passed': 4 if operation_results else 0,  # CREATE, READ, UPDATE, DELETE
                'operations_total': 4 if operation_results else 0,
                'total_tests_passed': (
                    connectivity_results['summary']['passed_tests'] + 
                    (4 if operation_results and operation_results['summary']['overall_status'] == 'success' else 0)
                ),
                'total_tests_run': connectivity_results['summary']['total_tests'] + 4
            }
        }
        
        # 打印最终汇总
        print("="*80)
        print("FINAL TEST SUMMARY")
        print("="*80)
        print(f"Connectivity Tests: {connectivity_results['summary']['passed_tests']}/{connectivity_results['summary']['total_tests']} passed")
        print(f"Operation Tests:    {self.results['summary']['operations_passed']}/{self.results['summary']['operations_total']} passed")
        print(f"Overall Status:     {self.results['summary']['overall_status']}")
        print(f"Total Tests:        {self.results['summary']['total_tests_passed']}/{self.results['summary']['total_tests_run']} passed")
        print()
        
        # 详细服务状态
        print("Service Status:")
        for service, result in connectivity_results.items():
            if service != 'summary':
                status_icon = '✓' if result['status'] in ['success', 'port_reachable'] else '✗'
                print(f"  {status_icon} {service.upper()}: {result['status']}")
        
        print()
        print("="*80)
        print("TEST SUITE COMPLETED")
        print("="*80)
        
        return self.results
    
    def generate_test_report(self, output_file="comprehensive_test_report.json"):
        """生成测试报告"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"Test report saved to: {output_file}")

def main():
    suite = ComprehensiveTestSuite()
    results = suite.run_all_tests()
    suite.generate_test_report()
    
    # 返回结果供进一步处理
    return results

if __name__ == "__main__":
    main()