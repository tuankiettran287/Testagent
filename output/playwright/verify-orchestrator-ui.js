async (page) => {
  const ensure = (value, message) => { if (!value) throw new Error(message); };
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const now = '2026-10-05T00:00:00Z';
  const project = { id: 'orchestrator-ui', name: 'Orchestrator preview', base_url: '', environment: 'local', created_at: now };
  const ai = { ready: true, active_provider: 'codex', pending_provider: null, selection: { provider: 'codex', model: 'preview-model', effort: 'high' }, providers: [{ id: 'codex', name: 'Codex', installed: true, connected: true, blocked: false, pending: false, models: [{ id: 'preview-model', name: 'Preview model', default: true, efforts: [{ id: 'high', name: 'High' }] }], account: 'Preview account' }] };
  const skills = await (await page.request.get('http://127.0.0.1:15173/orchestrator-skills.json')).json();
  const testCase = { id: 'case-1', title: 'API health', level: 'api', type: 'positive', priority: 'high', steps: ['Request health'], expected: ['HTTP 200'], preconditions: [], source_ids: [], api_request: { method: 'GET', path: '/health', expected_status: 200, headers: {} }, automation: null, created_at: now, readiness: { status: 'ready', engine: 'api', reason: 'Ready' } };
  const run = { id: 'run-1', status: 'COMPLETED', requested_at: now, summary: '{"total":1,"counts":{"PASS":1}}' };
  let tasks = [], submitted, connected = true;
  await page.unrouteAll({ behavior: 'wait' });
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let json = [], status = 200;
    if (path === '/api/projects') json = [project];
    else if (path === '/api/agent/skills') json = skills;
    else if (path.startsWith('/api/ai/providers')) json = connected ? ai : { ...ai, ready: false, selection: null };
    else if (path === '/api/health') json = { status: 'ok', model_configured: true, browser_runner_ready: true };
    else if (path.endsWith('/coverage')) json = { source_count: 0, test_case_count: 1, sources_with_tests: 0, uncovered_sources: [] };
    else if (path.endsWith('/tests')) json = [testCase];
    else if (path.endsWith('/runs')) json = [run];
    else if (path.endsWith('/tasks') && route.request().method() === 'GET') json = tasks;
    else if (path === '/api/agent/tasks' && route.request().method() === 'POST') {
      submitted = route.request().postDataJSON();
      const task = { id: 'routed-task', prompt: submitted.prompt, intent: 'performance', skill_file: 'performance.md', status: 'COMPLETED', created_at: now, error: '', ai_provider: submitted.provider, ai_model: submitted.model, ai_effort: submitted.effort, orchestration: { function: 'performance', reason: 'Mục tiêu là đánh giá tải 2.000 người dùng đồng thời trên API đăng nhập, nên cần agent phân tích hiệu năng.', source: 'ai' }, summary: JSON.stringify({ kind: 'analysis', skill_id: 'performance', summary: 'Đề xuất workload cho API đăng nhập.', findings: [], recommendations: [] }) };
      tasks = [task]; json = task; status = 202;
    }
    return route.fulfill({ json, status });
  });
  await page.goto('http://127.0.0.1:15173');
  await page.locator('#agent-function').waitFor();
  ensure(await page.locator('#agent-function').inputValue() === 'orchestrator', 'Automatic routing is not the default');
  ensure(await page.locator('#execution-mode').inputValue() === 'generate', 'Preview choice was lost');
  ensure(await page.locator('#agent-run').inputValue() === '', 'An optional run was forced');
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    ensure(!await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), `Overflow at ${width}`);
    await page.screenshot({ path: `output/playwright/orchestrator-after-${width}.png`, fullPage: true });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.locator('#agent-run').selectOption('run-1');
  await page.getByRole('checkbox', { name: 'API health', exact: true }).check();
  await page.locator('#task-prompt').fill('Kiểm tra API login chịu được 2.000 concurrent users không.');
  await page.getByRole('button', { name: 'Gửi cho agent', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('heading', { name: 'Điều phối', exact: true }).waitFor();
  ensure(submitted.function === 'orchestrator', 'UI classified the request itself');
  ensure(submitted.provider === 'codex' && submitted.model === 'preview-model' && submitted.effort === 'high', 'Chosen AI selection was lost');
  ensure(submitted.execution_mode === 'generate', 'Automatic routing started a confirmation run');
  ensure(submitted.case_ids[0] === 'case-1' && submitted.run_id === 'run-1', 'Scope inputs were lost');
  ensure(await dialog.getByText('Đã giao cho', { exact: false }).textContent().then(text => text.includes('Phân tích hiệu năng')), 'Selected specialist is not shown');
  await dialog.getByText('Mục tiêu là đánh giá tải', { exact: false }).waitFor();
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    ensure(!await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), `Dialog overflow at ${width}`);
    await page.screenshot({ path: `output/playwright/orchestrator-decision-${width}.png`, fullPage: true });
  }
  await dialog.getByRole('button', { name: 'Đóng', exact: true }).click();
  await page.locator('#agent-function').selectOption('run_tests');
  ensure(await page.getByText('Không cần gọi AI', { exact: false }).isVisible(), 'Manual deterministic execution changed');
  await page.locator('#agent-function').selectOption('orchestrator');
  connected = false;
  await page.reload();
  await page.locator('#task-prompt').fill('Lập kế hoạch test đăng nhập.');
  ensure(await page.getByRole('button', { name: 'Gửi cho agent', exact: true }).isDisabled(), 'AI routing is enabled without a connected account');
  await page.getByText('Đăng nhập và chọn model trong', { exact: false }).waitFor();
  return { viewports: [1440, 1024, 390], automaticProvider: submitted.provider, reasonVisible: true, disconnectedBlocked: true };
}
