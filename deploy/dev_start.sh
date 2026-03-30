#!/bin/bash

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print info messages
info() {
    echo -e "[INFO] $1"
}

# Function to print success messages
success() {
    echo -e "[SUCCESS] ${GREEN}$1${NC}"
}

# Function to print warning messages
warn() {
    echo -e "[WARNING] ${YELLOW}$1${NC}"
}

# Function to print error messages
error() {
    echo -e "[ERROR] ${RED}$1${NC}"
}

# Function for graceful shutdown
cleanup() {
    info "正在关闭所有后台进程..."
    if [ ! -z "$FRONTEND_PID" ]; then
        info "关闭前端服务 (PID: $FRONTEND_PID)"
        kill $FRONTEND_PID >/dev/null 2>&1
    fi
    if [ ! -z "$BACKEND_PID" ]; then
        info "关闭后端服务 (PID: $BACKEND_PID)"
        kill $BACKEND_PID >/dev/null 2>&1
    fi
    success "清理完成"
    exit 0
}

# Trap Ctrl+C and call cleanup function
trap cleanup SIGINT

# Main script execution starts here
info "正在启动多语种文档翻译平台开发环境..."

# --- 1. System Dependency Checks ---
info "检查系统依赖..."
# Example: Check if docker and docker-compose are installed
# if ! command -v docker &> /dev/null || ! command -v docker-compose &> /dev/null; then
#     error "Docker and Docker-Compose are required. Please install them."
#     exit 1
# fi

# --- 2. Project Structure Checks ---
info "检查项目目录结构..."
if [ ! -d "apps/frontend" ] || [ ! -d "apps/backend" ]; then
    error "项目结构不完整，缺少 'apps/frontend' 或 'apps/backend' 目录"
    exit 1
fi

# --- 3. Port Availability Checks ---
info "检查端口占用..."
FRONTEND_PORT=3000
BACKEND_PORT=8000
if lsof -i:$FRONTEND_PORT -sTCP:LISTEN -t >/dev/null ; then
    warn "端口 $FRONTEND_PORT 已被占用，前端服务可能已经在运行"
    info "如果这是意外情况，请先关闭占用端口的进程"
fi
if lsof -i:$BACKEND_PORT -sTCP:LISTEN -t >/dev/null ; then
    warn "端口 $BACKEND_PORT 已被占用，后端服务可能已经在运行"
    info "如果这是意外情况，请先关闭占用端口的进程"
fi

# --- 4. Display Welcome Message ---
echo ""
echo "======================= 多语种文档翻译平台 ======================="
echo ""
echo "项目技术栈:"
echo "  • 前端: React + TypeScript + Ant Design"
echo "  • 后端: FastAPI + Python + LLM (DeepSeek/Claude)"
echo "  • 数据库: PostgreSQL + Neo4j + Qdrant/Milvus"
echo "  • 文件存储: MinIO"
echo ""
echo "服务启动信息:"
echo "  • 前端应用: http://localhost:$FRONTEND_PORT"
echo "  • 后端API: http://localhost:$BACKEND_PORT"
echo "  • API文档: http://localhost:$BACKEND_PORT/docs"
echo "  • 健康检查: http://localhost:$BACKEND_PORT/health"
echo ""
echo "开发功能:"
echo "  • PDF文档上传和翻译"
echo "  • 实时文本翻译"
echo "  • 翻译任务状态监控"
echo "  • 智能语言检测"
echo "  • LLM驱动的精准翻译"
echo ""
echo "=================================================================="
echo ""

# --- 5. Start Backend Service ---
info "启动后端API服务..."
cd apps/backend

info "设置Python环境..."
# Check for virtual environment
if [ -d ".venv" ]; then
    info "使用现有虚拟环境"
    source .venv/bin/activate
else
    warn "未找到虚拟环境，请先运行 'make setup' 或 'python -m venv .venv'"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    warn "未找到后端配置文件 .env"
    info "建议从 .env.example 复制创建: cp .env.example .env"
    info "请确保配置了必要的环境变量（如LLM API密钥）"
fi

info "启动后端服务 (端口: $BACKEND_PORT)..."
uvicorn main:app --host 0.0.0.0 --port $BACKEND_PORT --reload > ../../backend.log 2>&1 &
BACKEND_PID=$!
success "后端服务启动 (PID: $BACKEND_PID)"

# Wait for backend to be ready
info "等待后端服务初始化..."
sleep 5 # Wait a few seconds for the server to start
if ! curl --silent --fail http://localhost:$BACKEND_PORT/health > /dev/null; then
    warn "后端服务可能启动失败，请检查 backend.log 文件"
fi
success "后端服务启动成功"

cd ../../

# --- 6. Start Frontend Service ---
info "启动前端开发服务器..."
cd apps/frontend

info "启动前端服务 (端口: $FRONTEND_PORT)..."
npm start > ../../frontend.log 2>&1 &
FRONTEND_PID=$!
success "前端服务启动 (PID: $FRONTEND_PID)"
info "前端日志已重定向到: $(pwd)/../../frontend.log"

cd ../../

# --- 7. Final Instructions ---
echo ""
echo "================================================================"
echo "              🚀 开发环境启动完成！"
echo ""
echo "访问以下地址开始使用:"
echo ""
echo "  ● 前端界面: ${GREEN}http://localhost:$FRONTEND_PORT${NC}"
echo "  ● 页面自动刷新已启用 (热重载)"
echo "  ● 后端API: ${GREEN}http://localhost:$BACKEND_PORT${NC}"
echo "  ● API文档: ${GREEN}http://localhost:$BACKEND_PORT/docs${NC}"
echo ""
echo "开发功能:"
echo "  ● PDF上传翻译: 上传PDF文件进行自动翻译"
echo "  ● 文本翻译: 直接输入文本进行即时翻译"
echo "  ● 任务监控: 实时查看翻译进度"
echo "  ● 语言选择: 支持10+种语言互译"
echo ""
echo "调试信息:"
echo "  ● 前后端日志分别输出"
echo "  ● 按 Ctrl+C 可优雅关闭所有服务"
echo "================================================================"
echo ""
info "按 Ctrl+C 关闭所有服务..."

# Wait for background processes to finish
wait $BACKEND_PID
wait $FRONTEND_PID
