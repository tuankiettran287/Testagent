async (page) => {
  const ensure = (condition, message) => { if (!condition) throw new Error(message); };
  const base = 'http://127.0.0.1:15173';
  await page.unrouteAll({ behavior: 'wait' });
  let project = { id: 'optional-context-ui', name: 'Test web không có tài liệu', base_url: base, environment: 'local', created_at: new Date().toISOString() };
  const oldProject = await page.evaluate(() => localStorage.getItem('testagent-project'));
  let submitted = null;
  // Keep browser assertions independent of the user's current account choice.
  await page.route('**/api/ai/providers?*', route => route.fulfill({ json: {
    ready: true, active_provider: 'codex', pending_provider: null,
    selection: { provider: 'codex', model: 'ui-test-model' },
    providers: [
      { id: 'codex', name: 'Codex / ChatGPT', installed: true, connected: true, blocked: false, pending: false, models: [{ id: 'ui-test-model', name: 'UI Test Model', default: true }] },
      { id: 'antigravity', name: 'Antigravity', installed: true, connected: false, blocked: true, pending: false, models: [] },
      { id: 'claude', name: 'Claude Code', installed: true, connected: false, blocked: true, pending: false, models: [] },
    ],
  } }));
  await page.route('**/api/projects', route => route.fulfill({ json: [project] }));
  await page.route('**/api/projects/optional-context-ui/**', route => route.fulfill({ json: new URL(route.request().url()).pathname.endsWith('/coverage') ? { source_count: 0, test_case_count: 0, sources_with_tests: 0, uncovered_sources: [] } : [] }));
  await page.route('**/api/agent/tasks', route => {
    submitted = route.request().postDataJSON();
    return route.fulfill({ status: 202, json: { id: 'optional-task', status: 'COMPLETED', prompt: submitted.prompt, intent: submitted.function, created_at: new Date().toISOString() } });
  });
  await page.goto(base);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const navigate = name => page.getByRole('navigation').getByRole('button', { name, exact: true }).click();
  await navigate('Tổng quan');
  const prompt = page.getByRole('textbox', { name: 'Yêu cầu của bạn', exact: true });
  const send = page.getByRole('button', { name: 'Gửi cho agent', exact: true });
  await prompt.fill('Tạo một UI smoke test cho các thành phần đang hiển thị trên website.');
  await page.waitForFunction(() => Array.from(document.querySelectorAll('button')).some(b => b.textContent.includes('Gửi cho agent') && !b.disabled));
  ensure(!await page.getByRole('region', { name: 'Thiết lập dự án', exact: true }).count(), 'Optional sources still count as missing setup');
  const registry = await (await page.request.get(base + '/api/agent/skills')).json();
  for (const skill of registry) {
    await page.locator('#agent-function').selectOption(skill.id);
    ensure((await send.isEnabled()) === (skill.requires === 'none'), `Incorrect input prerequisite for ${skill.id}`);
  }
  await page.locator('#agent-function').selectOption('ui_automation');
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    ensure(!await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), `Overflow at ${width}px`);
    await page.screenshot({ path: `output/playwright/optional-sources-after-${width}.png`, fullPage: true, animations: 'disabled' });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await send.click();
  await page.getByText('Đã giao việc cho Tạo UI automation.', { exact: true }).waitFor();
  ensure(submitted?.project_id === project.id && submitted?.function === 'ui_automation' && submitted?.provider === 'codex', 'Source-free task was not submitted with selected AI');
  await navigate('Nguồn dữ liệu');
  await page.getByText('Chưa có nguồn bổ sung', { exact: true }).waitFor();
  await navigate('Test cases');
  await page.getByRole('button', { name: 'Tạo test case', exact: true }).click();
  await prompt.waitFor();
  // A request can also draft a manual test/plan before a target URL is set.
  project = { ...project, base_url: '' };
  await page.reload();
  await prompt.fill('Đề xuất test case thủ công cho form email và password được mô tả trong yêu cầu.');
  await page.waitForFunction(() => Array.from(document.querySelectorAll('button')).some(b => b.textContent.includes('Gửi cho agent') && !b.disabled));
  await page.getByText('1 / 2 bước hoàn tất', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Nạp nguồn (tùy chọn)', exact: true }).first().waitFor();
  ensure(!await page.getByText('Nạp ít nhất một nguồn dữ liệu.', { exact: true }).count(), 'Mandatory source warning remains');
  await page.screenshot({ path: 'output/playwright/optional-sources-no-url.png', fullPage: true, animations: 'disabled' });
  await page.unrouteAll({ behavior: 'wait' });
  await page.evaluate(saved => { if (saved && saved !== 'optional-context-ui') localStorage.setItem('testagent-project', saved); else localStorage.removeItem('testagent-project'); }, oldProject);
  await page.goto(base);
  return 'Verified all general skills are usable with zero sources, code/run skills keep their prerequisites, source-free UI tasks submit, upload is optional, empty test library returns to the composer, and layouts work at 1440/1024/390px. Project/task/AI responses were mocked; skill registry used the live backend. No user account changes.';
}
