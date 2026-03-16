#!/bin/bash

# ACMG-PS3 Intelligence System Frontend Quick Start Script

echo "==========================================="
echo "ACMG-PS3 Intelligence System Frontend Setup"
echo "==========================================="

echo ""
echo "Checking prerequisites..."

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js >= 18.0.0"
    exit 1
else
    NODE_VERSION=$(node --version)
    echo "✅ Node.js version: $NODE_VERSION"
fi

# 检查 npm
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install npm"
    exit 1
else
    NPM_VERSION=$(npm --version)
    echo "✅ npm version: $NPM_VERSION"
fi

echo ""
echo "Installing dependencies..."
npm install

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
else
    echo "✅ Dependencies installed successfully"
fi

echo ""
echo "Setting up environment variables..."
if [ ! -f ".env.local" ]; then
    echo "Creating .env.local from example..."
    cp .env.local.example .env.local
    echo "✅ Created .env.local file"
    echo "⚠️  Remember to configure VITE_API_BASE_URL in .env.local if your backend is not running on http://localhost:8000/api/v1"
else
    echo "✅ Using existing .env.local file"
fi

echo ""
echo "Validating configuration files..."
if [ -f "package.json" ]; then
    echo "✅ package.json found"
else
    echo "❌ package.json not found"
    exit 1
fi

if [ -f "src/services/apiService.ts" ]; then
    echo "✅ apiService.ts found"
else
    echo "❌ apiService.ts not found"
    exit 1
fi

echo ""
echo "Running TypeScript type check..."
npx tsc --noEmit

if [ $? -eq 0 ]; then
    echo "✅ TypeScript type check passed"
else
    echo "❌ TypeScript type check failed"
    exit 1
fi

echo ""
echo "==========================================="
echo "Setup completed successfully!"
echo "==========================================="
echo ""
echo "To start the development server, run:"
echo "  npm run dev"
echo ""
echo "The application will be available at http://localhost:5173"
echo ""
echo "To build for production, run:"
echo "  npm run build"
echo ""