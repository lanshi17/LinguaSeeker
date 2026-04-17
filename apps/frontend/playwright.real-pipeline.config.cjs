module.exports = {
  testDir: '.',
  testMatch: ['task13.real-pipeline.e2e.spec.js'],
  use: {
    browserName: 'chromium',
    headless: true,
    baseURL: 'http://127.0.0.1:4193',
  },
  webServer: {
    command: 'VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1 npm run dev -- --host 127.0.0.1 --port 4193 --strictPort',
    url: 'http://127.0.0.1:4193',
    reuseExistingServer: false,
    timeout: 120000,
  },
  reporter: 'line',
  workers: 1,
  fullyParallel: false,
};
