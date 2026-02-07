#!/usr/bin/env node

/**
 * 后端服务检查脚本
 * 用于验证后端 API 是否正常运行
 */

const http = require('http');

const BACKEND_URL = 'localhost';
const BACKEND_PORT = 8000;
const TIMEOUT = 3000;

function checkEndpoint(path, method = 'GET') {
  return new Promise((resolve) => {
    const options = {
      hostname: BACKEND_URL,
      port: BACKEND_PORT,
      path: path,
      method: method,
      timeout: TIMEOUT,
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        resolve({
          status: res.statusCode,
          statusText: res.statusMessage,
          data: data,
          ok: res.statusCode >= 200 && res.statusCode < 300,
        });
      });
    });

    req.on('error', (err) => {
      resolve({
        status: 0,
        error: err.message,
        ok: false,
      });
    });

    req.on('timeout', () => {
      req.destroy();
      resolve({
        status: 0,
        error: '连接超时',
        ok: false,
      });
    });

    req.end();
  });
}

async function main() {
  console.log('🔍 检查后端服务状态...\n');

  // 1. 检查根路径
  console.log(`1. 检查 http://${BACKEND_URL}:${BACKEND_PORT}/`);
  const rootCheck = await checkEndpoint('/');
  if (rootCheck.ok) {
    console.log('   ✅ 后端服务运行正常');
  } else {
    console.log('   ❌ 后端服务未响应');
    console.log(`      错误: ${rootCheck.error || `HTTP ${rootCheck.status}`}`);
    console.log('\n💡 请启动后端服务:');
    console.log('   cd /path/to/backend');
    console.log('   uvicorn main:app --reload --port 8000');
    process.exit(1);
  }

  // 2. 检查 API 文档
  console.log('\n2. 检查 API 文档 (/docs)');
  const docsCheck = await checkEndpoint('/docs');
  if (docsCheck.ok) {
    console.log('   ✅ API 文档可访问');
  } else {
    console.log(`   ⚠️  API 文档返回 ${docsCheck.status}`);
  }

  // 3. 检查 API 端点
  const endpoints = [
    { path: '/api/v1/pdf/upload', method: 'POST', name: 'PDF 上传' },
    { path: '/api/v1/pdf/fetch-by-pmid?pmid=123', method: 'POST', name: 'PMID 获取' },
    { path: '/api/v1/tasks/test', method: 'GET', name: '任务状态' },
  ];

  console.log('\n3. 检查 API 端点:');
  for (const endpoint of endpoints) {
    const result = await checkEndpoint(endpoint.path, endpoint.method);
    const icon = result.ok || result.status === 405 ? '✅' : result.status === 404 ? '⚠️' : '❌';
    console.log(`   ${icon} ${endpoint.name} (${endpoint.method} ${endpoint.path})`);
    if (!result.ok && result.status !== 405) {
      console.log(`      状态: ${result.status} ${result.statusText || result.error || ''}`);
    }
  }

  console.log('\n✨ 检查完成!');
  console.log('\n如果看到 500 错误，请检查后端日志获取详细信息。');
}

main().catch(console.error);
