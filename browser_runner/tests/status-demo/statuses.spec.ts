import { test, expect } from '@playwright/test';

test('DEMO-PASS01 Agent skill registry responds successfully', async ({ request }) => {
  const response = await request.get('/api/agent/skills');
  expect(response.status()).toBe(200);
  expect(await response.json()).toHaveLength(19);
});

test('DEMO-FAIL01 Missing task returns 404 while demo expects 200', async ({ request }, info) => {
  info.annotations.push({ type: 'intentional-failure', description: 'Incorrect HTTP oracle demonstrates a failed API assertion.' });
  const response = await request.get('/api/agent/tasks/generated-task-that-does-not-exist');
  await info.attach('actual-response.json', { body: await response.body(), contentType: 'application/json' });
  expect(response.status(), 'Intentional demo failure: missing task is HTTP 404').toBe(200);
});

test('DEMO-FAIL02 Refreshed UI shows Healthy while demo expects Offline', async ({ request, page }, info) => {
  info.annotations.push({ type: 'intentional-failure', description: 'Incorrect UI oracle demonstrates screenshot and trace evidence.' });
  const state = await (await request.get('/__fixture/state')).json();
  await page.goto(state.target_url);
  await page.getByRole('button', { name: 'Refresh status', exact: true }).click();
  await expect(page.locator('#status')).toHaveText('Offline', { timeout: 1_000 });
});

test.describe('Controlled transient failures with one retry', () => {
  test.describe.configure({ retries: 1 });

  test('DEMO-FLAKY01 Temporary HTTP 503 recovers on retry', async ({ request }, info) => {
    info.annotations.push({ type: 'controlled-flaky', description: 'Fixture injects 503 on attempt 0 and 200 on retry; the expected status stays 200.' });
    const response = await request.get(`/__fixture/demo-transient-health?attempt=${info.retry}`);
    await info.attach(`attempt-${info.retry}.json`, { body: await response.body(), contentType: 'application/json' });
    expect(response.status()).toBe(200);
  });

  test('DEMO-FLAKY02 UI readiness recovers on retry', async ({ request, page }, info) => {
    info.annotations.push({ type: 'controlled-flaky', description: 'Generated status data is Starting on attempt 0 and Healthy on retry; the UI oracle stays Healthy.' });
    const state = await (await request.get('/__fixture/state')).json();
    await page.route('**/__status_demo/poll', route => route.fulfill({
      json: { status: info.retry === 0 ? 'Starting' : 'Healthy' },
    }));
    await page.goto(state.target_url);
    await page.evaluate(async () => {
      const result = await fetch('/__status_demo/poll').then(response => response.json());
      document.querySelector('#status')!.textContent = result.status;
    });
    await expect(page.locator('#status')).toHaveText('Healthy', { timeout: 1_000 });
  });
});

test('DEMO-SKIP01 Live provider credentials are unavailable in the demo', async () => {
  test.skip(true, 'Demo-only skip: live provider credentials are intentionally not configured on CI.');
});

test('DEMO-SKIP02 Production mutation is outside the demo scope', async () => {
  test.skip(true, 'Demo-only skip: production mutation is excluded; this workflow uses generated local fixtures.');
});
