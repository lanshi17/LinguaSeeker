module.exports = {
  testDir: '.',
  testMatch: ['task12.e2e.spec.js'],
  use: {
    browserName: 'chromium',
    headless: true,
    baseURL: 'http://127.0.0.1:4173',
  },
  reporter: 'line',
  workers: 1,
  fullyParallel: false,
};
