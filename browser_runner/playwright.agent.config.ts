import { defineConfig } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { tmpdir } from 'node:os';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const output = path.resolve(process.env.AGENT_REPORT_DIR || path.join(root, 'output/playwright/agent-cases'));
const baseURL = `http://127.0.0.1:${process.env.AGENT_CI_PORT || '8766'}`;
const data = path.join(tmpdir(), `testagent-playwright-${randomUUID()}`);

export default defineConfig({
  testDir: './tests',
  testMatch: ['**/agent/*.spec.ts', '**/status-demo/*.spec.ts'],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,
  timeout: 120_000,
  globalTimeout: 600_000,
  expect: { timeout: 10_000 },
  outputDir: path.join(output, 'test-results'),
  globalTeardown: './tests/agent/finalize.ts',
  reporter: [
    ['list'],
    ['html', { outputFolder: path.join(output, 'html'), open: 'never' }],
    ['json', { outputFile: path.join(output, 'results.json') }],
    ['junit', { outputFile: path.join(output, 'junit.xml') }],
  ],
  metadata: { dataOrigin: 'generated-fixtures-only', modelMode: 'fixture', workspaceDataImported: false,
    statusDemo: 'Includes deliberate FAIL, controlled FLAKY and declared SKIP cases' },
  use: {
    baseURL, browserName: 'chromium', headless: true,
    trace: 'retain-on-failure', screenshot: 'only-on-failure', video: 'retain-on-failure',
  },
  webServer: {
    command: `${process.env.PYTHON_BINARY || 'python'} -m scripts.playwright_agent_fixture --port ${process.env.AGENT_CI_PORT || '8766'}`,
    cwd: root,
    url: `${baseURL}/__fixture/state`,
    timeout: 90_000,
    reuseExistingServer: false,
    env: {
      PYTHONUTF8: '1', DATA_DIR: data, IMPORT_ROOT: path.join(data, 'imports'),
      TESTAGENT_EVIDENCE_DIR: path.join(output, 'browser'),
    },
  },
});
