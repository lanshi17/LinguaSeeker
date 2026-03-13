#!/usr/bin/env python3
"""
ACMG数据库模拟数据统计报告
显示生成的模拟数据的统计信息
"""

import json
import os
from datetime import datetime
from collections import Counter

def load_json_file(filepath):
    """加载JSON文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_statistics():
    """生成数据统计报告"""
    print("="*70)
    print("ACMG数据库模拟数据统计报告")
    print("="*70)
    print(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 加载数据
    documents = load_json_file('data/documents.json')
    parsing_tasks = load_json_file('data/parsing_tasks.json')
    evidence_records = load_json_file('data/evidence_records.json')
    agent_logs = load_json_file('data/agent_logs.json')
    
    # 总体统计
    print("总体数据统计:")
    print("-" * 40)
    print(f"Documents表: {len(documents)} 条记录")
    print(f"Parsing Tasks表: {len(parsing_tasks)} 条记录")
    print(f"Evidence Records表: {len(evidence_records)} 条记录")
    print(f"Agent Logs表: {len(agent_logs)} 条记录")
    print()
    
    # Documents表详细统计
    print("Documents表详细统计:")
    print("-" * 40)
    status_counts = Counter(doc['status'] for doc in documents)
    print("状态分布:")
    for status, count in status_counts.items():
        print(f"  {status}: {count} ({count/len(documents)*100:.1f}%)")
    
    year_counts = Counter(doc['publication_year'] for doc in documents)
    print("出版年份分布:")
    for year, count in sorted(year_counts.items()):
        print(f"  {year}: {count} ({count/len(documents)*100:.1f}%)")
    
    journals = Counter(doc['journal'] for doc in documents)
    print("期刊分布 (Top 5):")
    for journal, count in journals.most_common(5):
        print(f"  {journal}: {count}")
    print()
    
    # Parsing Tasks表详细统计
    print("Parsing Tasks表详细统计:")
    print("-" * 40)
    task_type_counts = Counter(task['task_type'] for task in parsing_tasks)
    print("任务类型分布:")
    for task_type, count in task_type_counts.items():
        print(f"  {task_type}: {count} ({count/len(parsing_tasks)*100:.1f}%)")
    
    task_status_counts = Counter(task['status'] for task in parsing_tasks)
    print("任务状态分布:")
    for status, count in task_status_counts.items():
        print(f"  {status}: {count} ({count/len(parsing_tasks)*100:.1f}%)")
    
    avg_progress = sum(task['progress'] for task in parsing_tasks) / len(parsing_tasks)
    print(f"平均进度: {avg_progress:.1f}%")
    print()
    
    # Evidence Records表详细统计
    print("Evidence Records表详细统计:")
    print("-" * 40)
    evidence_type_counts = Counter(evidence['evidence_type'] for evidence in evidence_records)
    print("证据类型分布 (Top 10):")
    for ev_type, count in evidence_type_counts.most_common(10):
        print(f"  {ev_type}: {count} ({count/len(evidence_records)*100:.1f}%)")
    
    evidence_status_counts = Counter(evidence['status'] for evidence in evidence_records)
    print("证据状态分布:")
    for status, count in evidence_status_counts.items():
        print(f"  {status}: {count} ({count/len(evidence_records)*100:.1f}%)")
    
    avg_confidence = sum(evidence['confidence_score'] for evidence in evidence_records) / len(evidence_records)
    print(f"平均置信度: {avg_confidence:.2f}")
    print()
    
    # Agent Logs表详细统计
    print("Agent Logs表详细统计:")
    print("-" * 40)
    agent_type_counts = Counter(log['agent_type'] for log in agent_logs)
    print("代理类型分布:")
    for agent_type, count in agent_type_counts.items():
        print(f"  {agent_type}: {count} ({count/len(agent_logs)*100:.1f}%)")
    
    avg_duration = sum(log['duration_ms'] for log in agent_logs) / len(agent_logs)
    print(f"平均处理时间: {avg_duration:.0f} ms")
    
    avg_retry = sum(log['retry_count'] for log in agent_logs) / len(agent_logs)
    print(f"平均重试次数: {avg_retry:.1f}")
    print()
    
    # 关系统计
    print("关系统计:")
    print("-" * 40)
    docs_with_tasks = len(set(task['document_id'] for task in parsing_tasks))
    print(f"有解析任务的文档数: {docs_with_tasks}/{len(documents)} ({docs_with_tasks/len(documents)*100:.1f}%)")
    
    docs_with_evidence = len(set(ev['document_id'] for ev in evidence_records))
    print(f"有证据记录的文档数: {docs_with_evidence}/{len(documents)} ({docs_with_evidence/len(documents)*100:.1f}%)")
    
    tasks_with_logs = len(set(log['task_id'] for log in agent_logs))
    print(f"有日志记录的任务数: {tasks_with_logs}/{len(parsing_tasks)} ({tasks_with_logs/len(parsing_tasks)*100:.1f}%)")
    print()
    
    # 数据质量评估
    print("数据质量评估:")
    print("-" * 40)
    unique_pmids = len(set(doc['pmid'] for doc in documents))
    print(f"PMID唯一性: {unique_pmids}/{len(documents)} ({unique_pmids/len(documents)*100:.1f}%)")
    
    unique_dois = len(set(doc['doi'] for doc in documents))
    print(f"DOI唯一性: {unique_dois}/{len(documents)} ({unique_dois/len(documents)*100:.1f}%)")
    
    docs_with_error = len([task for task in parsing_tasks if task['error_message']])
    print(f"有错误消息的任务: {docs_with_error}/{len(parsing_tasks)} ({docs_with_error/len(parsing_tasks)*100:.1f}%)")
    
    print()
    print("="*70)
    print("统计报告生成完成！")
    print("="*70)

def main():
    generate_statistics()

if __name__ == "__main__":
    main()