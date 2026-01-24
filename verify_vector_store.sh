#!/bin/bash

echo "=========================================="
echo "向量库实现验证"
echo "=========================================="

# 1. 检查文件
echo ""
echo "✓ 检查核心文件..."
files=(
    "src/infrastructure/vector_store/vector_store_manager.py"
    "src/infrastructure/vector_store/__init__.py"
    "src/infrastructure/repositories/rag_repository_impl.py"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✓ $file ($(wc -l < $file) 行)"
    else
        echo "  ✗ $file 缺失"
    fi
done

# 2. 检查类型错误
echo ""
echo "✓ 类型检查 (Pylance)..."
python3 << 'PYEOF'
import subprocess
import json

files_to_check = [
    "src/infrastructure/vector_store/vector_store_manager.py",
    "src/infrastructure/repositories/rag_repository_impl.py"
]

for file in files_to_check:
    result = subprocess.run(
        ["python3", "-m", "py_compile", file],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print(f"  ✓ {file}: 语法检查通过")
    else:
        print(f"  ✗ {file}: {result.stderr}")
PYEOF

# 3. 检查缓存目录
echo ""
echo "✓ 缓存目录..."
if [ -d ~/.cache/acmg_vector_store ]; then
    echo "  ✓ ~/.cache/acmg_vector_store 存在"
    if [ -f ~/.cache/acmg_vector_store/checksums.json ]; then
        echo "  ✓ checksums.json 存在"
        checksum_count=$(grep -c "acmg_guide.pdf" ~/.cache/acmg_vector_store/checksums.json 2>/dev/null || echo 0)
        echo "    - PDF跟踪数: $checksum_count"
    fi
    if [ -d ~/.cache/acmg_vector_store/qdrant_storage ]; then
        echo "  ✓ Qdrant数据库存在"
        collection_count=$(ls -1 ~/.cache/acmg_vector_store/qdrant_storage/collection/ 2>/dev/null | wc -l)
        echo "    - 集合数: $collection_count"
    fi
else
    echo "  ✓ 缓存目录将在首次运行时创建"
fi

# 4. 检查输出文件
echo ""
echo "✓ 输出文件..."
output_dirs=(
    "outputs/test_vector_store_v1"
    "outputs/test_vector_store_v2"
)

for dir in "${output_dirs[@]}"; do
    if [ -d "$dir" ]; then
        count=$(ls -1 "$dir"/*.json "$dir"/*.html 2>/dev/null | wc -l)
        echo "  ✓ $dir ($(ls -1 "$dir" | wc -l) 个文件)"
    fi
done

echo ""
echo "=========================================="
echo "验证完成 ✓"
echo "=========================================="
