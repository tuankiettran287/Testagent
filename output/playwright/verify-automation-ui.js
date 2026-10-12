async (page) => {
  const base = 'http://127.0.0.1:15173';
  const ensure = (condition, message) => { if (!condition) throw new Error(message); };
  const navigate = name => page.getByRole('navigation').getByRole('button', { name, exact: true }).click();
  const close = () => page.getByRole('dialog').getByRole('button', { name: 'Đóng', exact: true }).click();
  await page.unrouteAll({ behavior: 'wait' });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(base);
  const initialProject = await page.evaluate(() => localStorage.getItem('testagent-project'));
  await navigate('Tổng quan');
  ensure(await page.locator('#agent-function').inputValue() === 'ui_automation', 'Web automation is not the default skill');
  await page.getByRole('button', { name: /Đăng nhập trang web bằng tài khoản demo được công bố/ }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('region', { name: 'Tiến trình test automation' }).waitFor();
  await dialog.getByText('1 PASS', { exact: true }).waitFor();
  await dialog.getByRole('heading', { name: 'Kịch bản test', exact: true }).waitFor();
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    ensure(!await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), `Task drawer overflow at ${width}px`);
    await page.screenshot({ path: `output/playwright/automation-after-${width}.png`, fullPage: true, animations: 'disabled' });
  }
  await dialog.getByRole('button', { name: 'Xem kết quả, video và trace', exact: true }).click();
  await page.getByRole('heading', { name: 'Kết quả lượt chạy', exact: true }).waitFor();
  ensure(await dialog.getByRole('link', { name: /\.spec\.ts/ }).count() === 1, 'TypeScript test artifact is missing');
  ensure(await dialog.getByRole('link', { name: /trace\.zip/ }).count() === 1, 'Trace is missing');
  ensure(await dialog.getByRole('link', { name: /\.webm/ }).count() === 1, 'Video is missing');
  const artifact = await dialog.getByRole('link', { name: /\.spec\.ts/ }).getAttribute('href');
  const source = await (await page.request.get(base + artifact)).text();
  ensure(source.includes('.fill(') && source.includes('.click(') && source.includes('inventory.html') && source.includes('data-test'), 'Recorded test did not automate the login journey');
  await page.screenshot({ path: 'output/playwright/automation-run-mobile.png', fullPage: true });
  await close();
  await page.setViewportSize({ width: 1440, height: 1000 });

  // Error and pending states are isolated mocks; keep the user's project unchanged.
  const project = { id: 'workflow-qa', name: 'Test automation', base_url: base, environment: 'local', created_at: new Date().toISOString() };
  const output = { kind: 'test_cases', workflow: 'ui_automation', phase: 'EXPLORING', summary: 'Đang quan sát trang sau đăng nhập.', scenarios: ['Đăng nhập và xác nhận màn hình tài khoản'], activity: [{ message: 'Đã nhập thông tin và gửi form.', url: base }] };
  const task = { id: 'workflow-task', prompt: 'Kiểm tra luồng đăng nhập', intent: 'ui_automation', status: 'EXPLORING', summary: JSON.stringify(output), error: '', created_at: new Date().toISOString(), ai_provider: 'codex', ai_model: 'native', ai_effort: 'high' };
  await page.route('**/api/projects', route => route.fulfill({ json: [project] }));
  await page.route('**/api/projects/workflow-qa/**', route => route.fulfill({ json: route.request().url().endsWith('/tasks') ? [task] : route.request().url().endsWith('/coverage') ? { source_count: 0, test_case_count: 0, uncovered_sources: [] } : [] }));
  try {
    await page.goto(base);
    await page.getByRole('button', { name: /Kiểm tra luồng đăng nhập/ }).click();
    await dialog.getByText('Quan sát website', { exact: true }).waitFor();
    ensure(!await dialog.getByRole('button', { name: /Xem 0 test cases/ }).count(), 'Pending task offers fake zero-case completion');
    ensure(!await dialog.getByText('Kết quả Playwright', { exact: true }).count(), 'Exploration is displayed as a final run');
    await page.screenshot({ path: 'output/playwright/automation-exploring.png', fullPage: true });
    await close();
    task.status = 'NEEDS_INPUT';
    task.summary = JSON.stringify({ ...output, phase: 'NEEDS_INPUT', blocked_reason: 'Hãy cung cấp tài khoản và mật khẩu test cho trang này.' });
    await page.reload();
    await page.getByRole('button', { name: /Kiểm tra luồng đăng nhập/ }).click();
    await dialog.getByText('Cần bổ sung thông tin', { exact: true }).waitFor();
    await dialog.getByText('Hãy cung cấp tài khoản và mật khẩu test cho trang này.', { exact: true }).waitFor();
    await page.screenshot({ path: 'output/playwright/automation-needs-input.png', fullPage: true });
    await close();
    task.status = 'FAILED';
    task.error = 'Playwright ghi nhận test không đạt.';
    task.summary = JSON.stringify({ ...output, phase: 'FAILED', case_count: 1, execution: { status: 'FAILED', total: 1, counts: { PASS: 0, FAIL: 1, ERROR: 0, TIMEOUT: 0 } } });
    await page.reload();
    await page.getByRole('button', { name: /Kiểm tra luồng đăng nhập/ }).click();
    await dialog.getByText('1 FAIL', { exact: true }).waitFor();
    await page.screenshot({ path: 'output/playwright/automation-failed.png', fullPage: true });
    await close();
  } finally {
    await page.unrouteAll({ behavior: 'wait' });
    await page.evaluate(saved => { if (saved) localStorage.setItem('testagent-project', saved); else localStorage.removeItem('testagent-project'); }, initialProject);
    await page.goto(base);
    await navigate('Tổng quan');
  }
  return 'Verified real Sauce Demo login PASS with TypeScript/video/trace artifacts, automatic workflow default, result drawer at 1440/1024/390px, plus isolated exploration, needs-input and failure states. User account and selection preserved.';
}
