async (page) => {
  const base = 'http://127.0.0.1:15173';
  const ensure = (condition, message) => { if (!condition) throw new Error(message); };
  await page.unrouteAll({ behavior: 'wait' });
  const saved = await page.evaluate(() => localStorage.getItem('testagent-project'));
  const ai = await (await page.request.get(base + '/api/ai/providers')).json();
  const project = { id: 'suite-ui-fixture', name: 'Automation workspace', base_url: 'https://www.saucedemo.com', environment: 'staging', created_at: new Date().toISOString() };
  const cases = ['Đăng nhập hợp lệ', 'Giỏ hàng', 'Chưa có locator'].map((title, index) => ({ id: `case-${index}`, task_id: 'preview', title, level: 'e2e', type: 'positive', priority: 'high', steps: ['Mở trang', 'Kiểm tra kết quả'], expected: ['Kết quả đúng yêu cầu'], preconditions: [], source_ids: [], created_at: new Date().toISOString(), automation: index < 2 ? { actions: [{ action: 'navigate', url: '/' }, { action: 'assert_visible', target: { role: 'heading', name: 'Home' } }] } : null, api_request: null, unit_test_code: null, readiness: { status: index < 2 ? 'ready' : 'manual', engine: index < 2 ? 'playwright' : null, reason: index < 2 ? 'Có thể chạy độc lập.' : 'Chưa có automation. Chọn case và dùng Chuyển case thành automation.' }, last_status: index === 0 ? 'PASS' : null, last_run_id: index === 0 ? 'last-run' : null }));
  const preview = { id: 'preview', prompt: 'Tạo hai kịch bản để xem trước', intent: 'ui_automation', status: 'READY', summary: JSON.stringify({ kind: 'test_cases', workflow: 'ui_automation', phase: 'READY', case_count: 2, case_ids: ['case-0', 'case-1'], executable_ids: ['case-0', 'case-1'], summary: 'Đã tạo các kịch bản có thể chạy độc lập.', execution: null }), created_at: new Date().toISOString(), error: '', ai_provider: 'codex', ai_model: ai.selection.model, ai_effort: ai.selection.effort };
  let taskItems = [preview];
  let currentRun = { id: 'suite-run', status: 'RUNNING', requested_at: new Date().toISOString(), started_at: new Date().toISOString(), finished_at: null, summary: { total: 2, completed: 1, mode: 'parallel', workers: 2, test_case_ids: ['case-0', 'case-1'], counts: { PASS: 1, FAIL: 0, ERROR: 0, TIMEOUT: 0 } }, results: [{ id: 'result-1', test_case_id: 'case-0', title: cases[0].title, status: 'PASS', duration_ms: 1100, failure_type: null, message: 'Expected outcome confirmed', artifacts: ['case-0.spec.ts', 'case-0-trace.zip', 'case-0.webm'] }] };
  let submittedTask, submittedRun, disconnected = false;
  await page.route('**/api/ai/providers*', route => route.fulfill({ json: disconnected ? { ...ai, ready: false, selection: null } : ai }));
  await page.route('**/api/projects', route => route.fulfill({ json: [project] }));
  await page.route('**/api/projects/suite-ui-fixture/**', route => {
    const path = new URL(route.request().url()).pathname;
    return route.fulfill({ json: path.endsWith('/tests') ? cases : path.endsWith('/tasks') ? taskItems : path.endsWith('/runs') ? [] : path.endsWith('/coverage') ? { source_count: 0, test_case_count: 3, sources_with_tests: 0, uncovered_sources: [] } : [] });
  });
  await page.route('**/api/agent/tasks', async route => {
    submittedTask = route.request().postDataJSON();
    taskItems = [{ ...preview, id: 'submitted', prompt: submittedTask.prompt, intent: submittedTask.function }, preview];
    await route.fulfill({ status: 202, json: taskItems[0] });
  });
  await page.route('**/api/tests/execute', async route => {
    submittedRun = route.request().postDataJSON();
    await route.fulfill({ status: 202, json: { ...currentRun, summary: JSON.stringify(currentRun.summary) } });
  });
  await page.route('**/api/runs/*', route => route.fulfill({ json: currentRun }));
  const nav = async name => {
    if (await page.getByRole('button', { name: 'Mở menu', exact: true }).isVisible()) await page.getByRole('button', { name: 'Mở menu', exact: true }).click();
    await page.getByRole('navigation').getByRole('button', { name, exact: true }).click();
  };
  const close = () => page.getByRole('dialog').getByRole('button', { name: 'Đóng', exact: true }).click();
  try {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(base);
    await page.locator('#agent-function').selectOption('ui_automation');
    ensure(await page.locator('#execution-mode').inputValue() === 'generate', 'UI must default to review before execution');
    ensure(await page.locator('#agent-function optgroup').count() === 3, 'Agent groups are missing');
    await page.locator('#task-prompt').fill('Tạo kịch bản đăng nhập để xem trước');
    await page.getByRole('button', { name: 'Gửi cho agent', exact: true }).click();
    await page.getByText('Đã tạo test · Chưa chạy xác nhận', { exact: true }).waitFor();
    ensure(submittedTask.execution_mode === 'generate', 'Generate-only choice was lost');
    ensure(submittedTask.effort === ai.selection.effort, 'Native model effort was lost');
    ensure(!submittedRun, 'Preview automatically started a run');
    await page.screenshot({ path: 'output/playwright/suite-preview.png', fullPage: true });
    await close();
    await nav('Test cases');
    ensure(await page.getByRole('button', { name: 'Chạy Chưa có locator', exact: true }).isDisabled(), 'Manual case can execute');
    await page.getByRole('checkbox', { name: 'Chọn Đăng nhập hợp lệ', exact: true }).check();
    await page.getByRole('checkbox', { name: 'Chọn Giỏ hàng', exact: true }).check();
    await page.getByRole('combobox', { name: 'Cách chạy', exact: true }).selectOption('parallel');
    await page.getByRole('combobox', { name: 'Số test đồng thời', exact: true }).selectOption('2');
    for (const width of [1440, 1024, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      ensure(!await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), `Page overflow at ${width}`);
      await page.screenshot({ path: `output/playwright/suite-after-${width}.png`, fullPage: true });
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByRole('button', { name: 'Chạy nhóm đã chọn (2)', exact: true }).click();
    await page.getByRole('heading', { name: 'Kết quả lượt chạy', exact: true }).waitFor();
    ensure(JSON.stringify(submittedRun.test_case_ids) === JSON.stringify(['case-0', 'case-1']), 'Group run included unselected cases');
    ensure(submittedRun.mode === 'parallel' && submittedRun.workers === 2, 'Parallel settings were lost');
    await page.getByText('1/2 case hoàn tất · Song song, tối đa 2 case', { exact: true }).waitFor();
    await page.screenshot({ path: 'output/playwright/suite-running.png', fullPage: true });
    await close();
    await page.getByRole('textbox', { name: 'Tìm test case', exact: true }).fill('Giỏ hàng');
    await page.getByRole('button', { name: 'Chạy tất cả đang lọc (1)', exact: true }).click();
    await page.getByRole('heading', { name: 'Kết quả lượt chạy', exact: true }).waitFor();
    ensure(JSON.stringify(submittedRun.test_case_ids) === JSON.stringify(['case-1']), 'Run-all ignored the current filter');
    await close();
    await page.getByRole('textbox', { name: 'Tìm test case', exact: true }).fill('');
    await page.getByRole('button', { name: 'Chạy Đăng nhập hợp lệ', exact: true }).click();
    await page.getByRole('heading', { name: 'Kết quả lượt chạy', exact: true }).waitFor();
    ensure(JSON.stringify(submittedRun.test_case_ids) === JSON.stringify(['case-0']), 'Single case run included other cases');
    await close();
    await page.getByRole('button', { name: 'Tạo automation cho Chưa có locator', exact: true }).click();
    ensure(await page.locator('#agent-function').inputValue() === 'automation_builder', 'Builder action did not select the builder agent');
    ensure(await page.getByRole('checkbox', { name: 'Chưa có locator', exact: true }).isChecked(), 'Builder action lost the chosen case');
    await page.screenshot({ path: 'output/playwright/suite-builder.png', fullPage: true });
    currentRun = { ...currentRun, status: 'FAILED', summary: { ...currentRun.summary, completed: 2, counts: { PASS: 1, FAIL: 1, ERROR: 0, TIMEOUT: 0 } }, results: [...currentRun.results, { ...currentRun.results[0], id: 'result-2', test_case_id: 'case-1', title: cases[1].title, status: 'FAIL', message: 'Expected product was absent' }] };
    await nav('Test cases');
    await page.getByRole('button', { name: 'PASS', exact: true }).click();
    await page.getByRole('button', { name: 'Giao agent sửa automation', exact: true }).click();
    ensure(await page.locator('#agent-function').inputValue() === 'repair_automation', 'Failed run cannot route to repair agent');
    disconnected = true;
    await page.reload();
    await page.locator('#agent-function').selectOption('run_tests');
    await page.getByRole('checkbox', { name: 'Đăng nhập hợp lệ', exact: true }).check();
    await page.locator('#task-prompt').fill('Chạy case đã chọn');
    ensure(await page.getByRole('button', { name: 'Gửi cho agent', exact: true }).isEnabled(), 'Execution agent incorrectly requires an AI connection');
    await page.getByRole('button', { name: 'Gửi cho agent', exact: true }).click();
    ensure(submittedTask.function === 'run_tests' && submittedTask.case_ids[0] === 'case-0' && !submittedTask.provider, 'Execution task sends an AI selection or loses case IDs');
    console.log('Suite UI verified: preview, single/group/filtered runs, workers, manual readiness, builder/repair routing, disconnected deterministic execution, responsive layouts.');
  } finally {
    await page.unrouteAll({ behavior: 'wait' });
    await page.evaluate(saved => saved ? localStorage.setItem('testagent-project', saved) : localStorage.removeItem('testagent-project'), saved);
    await page.goto(base);
    await page.setViewportSize({ width: 1440, height: 1000 });
  }
}
