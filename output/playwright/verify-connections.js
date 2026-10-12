async (page) => {
  // Exercise native account attachment while keeping global CLI credentials.
  const ensure = (condition, message) => { if (!condition) throw new Error(message); };
  const base = 'http://127.0.0.1:15173';
  const liveState = async () => (await page.request.get(base + '/api/ai/providers?refresh=true')).json();
  const card = name => page.getByRole('article').filter({ has: page.getByRole('heading', { name, exact: true }) });
  const aiSidebar = page.locator('.sidebar-status').filter({ has: page.getByText('Model AI', { exact: true }) });
  const assertReady = async expected => {
    await aiSidebar.getByText(expected ? 'Đã kết nối' : 'Chưa kết nối', { exact: true }).waitFor();
    ensure((await (await page.request.get(base + '/api/health')).json()).model_configured === expected, 'Health and UI readiness disagree');
  };
  const navigateAi = async () => page.getByRole('navigation').getByRole('button', { name: 'Kết nối AI', exact: true }).click();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.unrouteAll({ behavior: 'wait' });
  const initial = await liveState();
  const owner = initial.active_provider || initial.pending_provider;
  if (owner) ensure((await page.request.post(`${base}/api/ai/providers/${owner}/logout`, { data: {} })).ok(), 'Could not disconnect initial app session');
  await page.goto(base);
  await navigateAi();
  const anti = card('Antigravity');
  const codex = card('Codex / ChatGPT');
  const claude = card('Claude Code');
  await anti.getByRole('button', { name: 'Mở đăng nhập CLI', exact: true }).click();
  await anti.getByText('Đã kết nối', { exact: true }).waitFor({ timeout: 60000 });
  await assertReady(true);
  let state = await liveState();
  ensure(state.active_provider === 'antigravity' && state.ready && state.selection?.provider === 'antigravity', 'Antigravity did not auto-select a model');
  ensure(state.providers.filter(p => p.connected).length === 1, 'Multiple providers connected');
  ensure(await codex.getByRole('button', { name: 'Đăng nhập ChatGPT', exact: true }).isDisabled(), 'Other provider login is enabled');
  ensure(await claude.getByRole('button', { name: 'Mở đăng nhập CLI', exact: true }).isDisabled(), 'Claude login is enabled during Antigravity session');
  ensure((await page.request.post(base + '/api/ai/providers/codex/login', { data: {} })).status() === 409, 'Backend allowed a second provider');
  await anti.getByRole('button', { name: 'Đăng xuất', exact: true }).click();
  await anti.getByText('Chưa kết nối', { exact: true }).waitFor();
  await assertReady(false);
  await page.getByRole('button', { name: 'Kiểm tra kết nối', exact: true }).click();
  await codex.getByRole('button', { name: 'Đăng nhập ChatGPT', exact: true }).waitFor();
  state = await liveState();
  ensure(!state.ready && !state.active_provider && !state.selection && !state.providers.some(p => p.connected), 'Logged-out native credentials auto-reconnected');
  await page.reload();
  await navigateAi();
  await assertReady(false);
  ensure(!((await liveState()).providers.some(p => p.connected)), 'Logout did not survive reload');
  await codex.getByRole('button', { name: 'Đăng nhập ChatGPT', exact: true }).click();
  await codex.getByText('Đã kết nối', { exact: true }).waitFor({ timeout: 60000 });
  await assertReady(true);
  state = await liveState();
  const models = state.providers.find(p => p.id === 'codex').models;
  const originalModel = models.some(m => m.id === 'gpt-6.1-sol') ? 'gpt-6.1-sol' : state.selection.model;
  const alternate = models.find(m => m.id !== originalModel)?.id;
  if (alternate) {
    await codex.getByRole('combobox', { name: 'Model Codex / ChatGPT', exact: true }).selectOption(alternate);
    await codex.getByRole('button', { name: 'Áp dụng', exact: true }).click();
    await codex.getByRole('button', { name: 'Đang sử dụng', exact: true }).waitFor();
    await page.reload();
    await navigateAi();
    await codex.getByRole('combobox', { name: 'Model Codex / ChatGPT', exact: true }).waitFor();
    ensure(await codex.getByRole('combobox', { name: 'Model Codex / ChatGPT', exact: true }).inputValue() === alternate, 'Selected model did not survive reload');
  }
  await codex.getByRole('combobox', { name: 'Model Codex / ChatGPT', exact: true }).selectOption(originalModel);
  if (await codex.getByRole('button', { name: 'Áp dụng', exact: true }).count()) {
    await codex.getByRole('button', { name: 'Áp dụng', exact: true }).click();
    await codex.getByRole('button', { name: 'Đang sử dụng', exact: true }).waitFor();
  }
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    ensure(!await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), `Connections overflow at ${width}px`);
    await page.screenshot({ path: `output/playwright/connections-${width}.png`, fullPage: true, animations: 'disabled' });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  const savedProject = await page.evaluate(() => localStorage.getItem('testagent-project'));
  await page.route('**/api/projects', route => route.fulfill({ json: [{ id: 'ui-qa', name: 'Kiểm tra giao diện AI', base_url: '', environment: 'local', created_at: new Date().toISOString() }] }));
  await page.route('**/api/projects/ui-qa/**', route => {
    const path = new URL(route.request().url()).pathname;
    const json = path.endsWith('/sources') ? [{ id: 'qa-source', kind: 'document', name: 'login.txt', origin: 'upload', created_at: new Date().toISOString() }]
      : path.endsWith('/coverage') ? { source_count: 1, test_case_count: 0, sources_with_tests: 0, uncovered_sources: [] } : [];
    return route.fulfill({ json });
  });
  await page.reload();
  await page.getByRole('combobox', { name: 'Provider AI', exact: true }).waitFor();
  await page.waitForFunction(() => document.querySelector('[aria-label="Model AI"]')?.value);
  ensure(await page.getByRole('combobox', { name: 'Provider AI', exact: true }).inputValue() === 'codex', 'Composer provider differs from app session');
  ensure(await page.getByRole('combobox', { name: 'Model AI', exact: true }).inputValue() === originalModel, 'Composer model differs from saved model');
  ensure(await page.getByRole('combobox', { name: 'Provider AI', exact: true }).locator('option[value="antigravity"]').evaluate(option => option.disabled), 'Composer allows a disconnected provider');
  await page.getByRole('textbox', { name: 'Yêu cầu của bạn' }).fill('Tạo một test case cho luồng đăng nhập.');
  await page.waitForFunction(() => Array.from(document.querySelectorAll('button')).some(b => b.textContent.includes('Gửi cho agent') && !b.disabled));
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 900 });
    ensure(!await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), `Composer overflow at ${width}px`);
    await page.screenshot({ path: `output/playwright/composer-${width}.png`, fullPage: true, animations: 'disabled' });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  const disconnected = { ready: false, selection: null, active_provider: null, pending_provider: null, providers: [
    { id: 'codex', name: 'Codex / ChatGPT', installed: true, connected: false, blocked: false, pending: false, models: [] },
    { id: 'antigravity', name: 'Antigravity', installed: true, connected: false, blocked: false, pending: false, models: [] },
    { id: 'claude', name: 'Claude Code', installed: true, connected: false, blocked: false, pending: false, models: [] },
  ] };
  let mockState = disconnected;
  await page.route('**/api/ai/providers?*', route => route.fulfill({ json: mockState }));
  await page.route('**/api/ai/providers/codex/login', route => {
    mockState = { ...disconnected, pending_provider: 'codex', providers: disconnected.providers.map(p => ({ ...p, pending: p.id === 'codex', blocked: p.id !== 'codex' })) };
    return route.fulfill({ json: { provider: 'codex', mode: 'device', url: 'https://auth.openai.com/codex/device', user_code: 'TEST-1234', message: 'Nhập mã thiết bị trong trang đăng nhập.' } });
  });
  await page.route('**/api/ai/providers/codex/login/cancel', route => {
    mockState = disconnected;
    return route.fulfill({ json: { message: 'Đã hủy đăng nhập.' } });
  });
  await page.reload();
  await navigateAi();
  await codex.getByRole('button', { name: 'Dùng mã thiết bị', exact: true }).click();
  await page.getByText('TEST-1234', { exact: true }).waitFor();
  ensure(await anti.getByRole('button', { name: 'Mở đăng nhập CLI', exact: true }).isDisabled(), 'Pending OAuth does not block another provider');
  await page.screenshot({ path: 'output/playwright/device-login.png', fullPage: true, animations: 'disabled' });
  await page.reload();
  await navigateAi();
  await codex.getByRole('button', { name: 'Hủy đăng nhập', exact: true }).click();
  await page.waitForFunction(() => Array.from(document.querySelectorAll('button')).some(b => b.textContent === 'Đăng nhập ChatGPT' && !b.disabled));
  ensure(await anti.getByRole('button', { name: 'Mở đăng nhập CLI', exact: true }).isEnabled(), 'Cancellation after reload leaves other providers blocked');
  await page.unrouteAll({ behavior: 'wait' });
  await page.evaluate(value => { if (value) localStorage.setItem('testagent-project', value); else localStorage.removeItem('testagent-project'); }, savedProject);
  await page.reload();
  await navigateAi();
  await assertReady(true);
  await page.locator('.sidebar-status').filter({ has: page.getByText('API', { exact: true }) }).getByText('Đang hoạt động', { exact: true }).waitFor();
  await page.screenshot({ path: 'output/playwright/ai-session-final.png', fullPage: true, animations: 'disabled' });
  return 'Verified live Antigravity connect/logout, one provider enforcement in UI/API, consistent sidebar/health/composer readiness, model persistence, mocked pending OAuth cancellation after reload, and responsive layouts at 1440/1024/390px. Final app session: Codex; global CLI credentials were not revoked.';
}
