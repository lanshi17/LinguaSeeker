#!/usr/bin/env python3
"""
ACMG数据库系统测试流水线
执行完整的数据库连接、功能和性能测试
"""

import argparse
import sys
import os
from datetime import datetime
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.enhanced_connectivity_test import EnhancedConnectivityTester
from src.adaptive_database_operations_test import AdaptiveDatabaseOperationsTester
from src.mock_data_generator_offline import MockDataGenerator
from src.data_statistics import generate_statistics


def run_connectivity_tests():
    """运行连通性测试"""
    print("="*60)
    print("RUNNING CONNECTIVITY TESTS")
    print("="*60)

    tester = EnhancedConnectivityTester()
    results = tester.run_tests()

    return results


def run_operation_tests():
    """运行操作测试"""
    print("="*60)
    print("RUNNING DATABASE OPERATION TESTS")
    print("="*60)

    tester = AdaptiveDatabaseOperationsTester()
    results = tester.run_comprehensive_test()

    return results


def generate_mock_data(count=50):
    """生成模拟数据"""
    print("="*60)
    print(f"GENERATING {count} MOCK RECORDS PER TABLE")
    print("="*60)

    generator = MockDataGenerator()
    generator.generate_documents(count)
    generator.generate_parsing_tasks(1)
    generator.generate_evidence_records(5)
    generator.generate_agent_logs(2)

    # 保存数据到文件
    generator.save_data_to_files()
    generator.generate_insert_sql()

    print(f"✓ Generated {len(generator.documents)} documents, {len(generator.parsing_tasks)} parsing tasks,")
    print(f"  {len(generator.evidence_records)} evidence records, and {len(generator.agent_logs)} agent logs")

    return {
        'documents_count': len(generator.documents),
        'parsing_tasks_count': len(generator.parsing_tasks),
        'evidence_records_count': len(generator.evidence_records),
        'agent_logs_count': len(generator.agent_logs)
    }


def run_data_statistics():
    """运行数据统计"""
    print("="*60)
    print("RUNNING DATA STATISTICS")
    print("="*60)

    # 直接调用统计函数
    try:
        from src.data_statistics import load_json_file, Counter

        # 加载数据
        documents = load_json_file('data/documents.json')
        parsing_tasks = load_json_file('data/parsing_tasks.json')
        evidence_records = load_json_file('data/evidence_records.json')
        agent_logs = load_json_file('data/agent_logs.json')

        # 生成统计信息
        stats = {
            'total_documents': len(documents),
            'total_tasks': len(parsing_tasks),
            'total_evidence': len(evidence_records),
            'total_logs': len(agent_logs),
            'timestamp': datetime.now().isoformat()
        }

        print(f"Documents: {stats['total_documents']}")
        print(f"Parsing Tasks: {stats['total_tasks']}")
        print(f"Evidence Records: {stats['total_evidence']}")
        print(f"Agent Logs: {stats['total_logs']}")

        return stats
    except Exception as e:
        print(f"Error generating statistics: {str(e)}")
        return None


def run_full_pipeline():
    """运行完整测试流水线"""
    print("ACMG DATABASE TESTING PIPELINE")
    print("="*80)
    print(f"Pipeline started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    pipeline_results = {
        'timestamp': datetime.now().isoformat(),
        'steps': {},
        'summary': {
            'total_steps': 0,
            'successful_steps': 0,
            'failed_steps': 0
        }
    }

    # 步骤1: 连通性测试
    print("Step 1/4: Running connectivity tests...")
    try:
        conn_results = run_connectivity_tests()
        pipeline_results['steps']['connectivity'] = conn_results
        pipeline_results['summary']['successful_steps'] += 1
        print("✓ Connectivity tests completed\n")
    except Exception as e:
        pipeline_results['steps']['connectivity'] = {'error': str(e)}
        pipeline_results['summary']['failed_steps'] += 1
        print(f"✗ Connectivity tests failed: {str(e)}\n")

    pipeline_results['summary']['total_steps'] += 1

    # 步骤2: 生成模拟数据
    print("Step 2/4: Generating mock data...")
    try:
        mock_results = generate_mock_data(20)  # 生成20条记录用于测试
        pipeline_results['steps']['mock_data'] = mock_results
        pipeline_results['summary']['successful_steps'] += 1
        print("✓ Mock data generation completed\n")
    except Exception as e:
        pipeline_results['steps']['mock_data'] = {'error': str(e)}
        pipeline_results['summary']['failed_steps'] += 1
        print(f"✗ Mock data generation failed: {str(e)}\n")

    pipeline_results['summary']['total_steps'] += 1

    # 步骤3: 数据统计
    print("Step 3/4: Running data statistics...")
    try:
        stats_results = run_data_statistics()
        pipeline_results['steps']['statistics'] = stats_results
        pipeline_results['summary']['successful_steps'] += 1
        print("✓ Data statistics completed\n")
    except Exception as e:
        pipeline_results['steps']['statistics'] = {'error': str(e)}
        pipeline_results['summary']['failed_steps'] += 1
        print(f"✗ Data statistics failed: {str(e)}\n")

    pipeline_results['summary']['total_steps'] += 1

    # 步骤4: 数据库操作测试
    print("Step 4/4: Running database operation tests...")
    try:
        op_results = run_operation_tests()
        pipeline_results['steps']['operations'] = op_results
        pipeline_results['summary']['successful_steps'] += 1
        print("✓ Database operation tests completed\n")
    except Exception as e:
        pipeline_results['steps']['operations'] = {'error': str(e)}
        pipeline_results['summary']['failed_steps'] += 1
        print(f"✗ Database operation tests failed: {str(e)}\n")

    pipeline_results['summary']['total_steps'] += 1

    # 生成最终摘要
    pipeline_results['summary']['pipeline_status'] = 'success' if pipeline_results['summary']['failed_steps'] == 0 else 'partial_success'

    # 打印流水线摘要
    print("="*80)
    print("PIPELINE EXECUTION SUMMARY")
    print("="*80)
    print(f"Total Steps: {pipeline_results['summary']['total_steps']}")
    print(f"Successful:  {pipeline_results['summary']['successful_steps']}")
    print(f"Failed:      {pipeline_results['summary']['failed_steps']}")
    print(f"Status:      {pipeline_results['summary']['pipeline_status']}")
    print(f"Completed:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # 保存结果到文件
    output_file = f"test_pipeline_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(pipeline_results, f, indent=2, ensure_ascii=False)

    print(f"Pipeline results saved to: {output_file}")

    return pipeline_results


def main():
    parser = argparse.ArgumentParser(description='ACMG Database Testing Pipeline')
    parser.add_argument('--step', choices=['connectivity', 'mock-data', 'statistics', 'operations', 'full'],
                       default='full', help='Which test step to run (default: full pipeline)')
    parser.add_argument('--count', type=int, default=20, help='Number of mock records to generate (default: 20)')

    args = parser.parse_args()

    if args.step == 'connectivity':
        run_connectivity_tests()
    elif args.step == 'mock-data':
        generate_mock_data(args.count)
    elif args.step == 'statistics':
        run_data_statistics()
    elif args.step == 'operations':
        run_operation_tests()
    elif args.step == 'full':
        run_full_pipeline()
    else:
        print("Invalid step specified. Use --help for options.")


if __name__ == "__main__":
    main()
