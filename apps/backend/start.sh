#!/bin/bash

# ACMG-PS3 后端服务启动脚本

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting ACMG-PS3 Intelligence System${NC}"

# 检查Python版本
echo -e "\n${YELLOW}📋 Checking Python version...${NC}"
python --version

# 检查.env文件
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found, creating from .env.example${NC}"
    cp .env.example .env
    echo -e "${RED}❗ Please update .env with your actual configuration${NC}"
    exit 1
fi

# 创建虚拟环境 (如果不存在)
if [ ! -d "venv" ]; then
    echo -e "\n${YELLOW}📦 Creating virtual environment...${NC}"
    python -m venv venv
fi

# 激活虚拟环境
echo -e "\n${YELLOW}🔧 Activating virtual environment...${NC}"
source venv/bin/activate

# 安装依赖
echo -e "\n${YELLOW}📥 Installing dependencies...${NC}"
pip install -e .

# 检查数据库连接
echo -e "\n${YELLOW}🔍 Checking database connections...${NC}"
# TODO: 添加数据库连接检查脚本

# 启动服务
echo -e "\n${GREEN}✅ Starting FastAPI server...${NC}"
python main.py
