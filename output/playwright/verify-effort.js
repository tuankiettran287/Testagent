async (page) => {
  const base = 'http://127.0.0.1:15173';
  const ensure = (condition, message) => { if (!condition) throw new Error(message); };
  const navigate = name => page.getByRole('navigation').getByRole('button', { name, exact: true }).click();
  const card = name => page.getByRole('article').filter({ has: page.getByRole('heading', { name, exact: true }) });
  await page.unrouteAll({ behavior: 'wait' });
  const originalProject = await page.evaluate(() => localStorage.getItem('testagent-project'));
  const live = await (await page.request.get(base + '/api/ai/providers?refresh=true')).json();
  ensure(live.ready && live.selection?.provider === 'codex', 'Expected connected Codex account for native capability QA');
  const codexModels = live.providers.find(p => p.id === 'codex').models;
  const nativeModel = codexModels.find(m => m.id === live.selection.model);
  ensure(nativeModel.efforts?.length, 'Backend has not exposed native Codex efforts');
  let state = structuredClone(live);
  let submitted;
  const project = { id: 'effort-ui', name: 'Website chỉ có URL', base_url: base, environment: 'local', created_at: new Date().toISOString() };
  try {
    await page.route('**/api/ai/providers?*', route => route.fulfill({ json: state }));
    await page.route('**/api/ai/selection', route => {
      const selected = route.request().postDataJSON();
      const model = state.providers.find(p => p.id === selected.provider)?.models.find(m => m.id === selected.model);
      if (!model || (selected.effort && !model.efforts?.some(e => e.id === selected.effort))) {
        return route.fulfill({ status: 422, json: { detail: 'Unsupported effort' } });
      }
      state.selection = { provider: selected.provider, model: selected.model };
      const effort = selected.effort || model.default_effort;
      if (effort) state.selection.effort = effort;
      return route.fulfill({ json: state.selection });
    });
    await page.route('**/api/projects', route => route.fulfill({ json: [project] }));
    await page.route('**/api/projects/effort-ui/**', route => route.fulfill({ json: route.request().url().endsWith('/coverage') ? { source_count: 0, test_case_count: 0, sources_with_tests: 0, uncovered_sources: [] } : [] }));
    await page.route('**/api/agent/tasks', route => {
      submitted = route.request().postDataJSON();
      return route.fulfill({ status: 202, json: { id: 'effort-task', status: 'COMPLETED', prompt: submitted.prompt, intent: submitted.function, ai_effort: submitted.effort, created_at: new Date().toISOString() } });
    });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(base);
    await navigate('Kết nối AI');
    const codex = card('Codex / ChatGPT');
    const effort = codex.getByRole('combobox', { name: 'Effort Codex / ChatGPT', exact: true });
    await effort.waitFor();
    ensure(JSON.stringify(await effort.locator('option').evaluateAll(options => options.map(o => o.value).filter(Boolean))) === JSON.stringify(nativeModel.efforts.map(e => e.id)), 'Picker differs from native capabilities');
    const alternative = nativeModel.efforts.find(e => e.id !== state.selection.effort).id;
    await effort.selectOption(alternative);
    await codex.getByRole('button', { name: 'Áp dụng', exact: true }).click();
    await codex.getByRole('button', { name: 'Đang sử dụng', exact: true }).waitFor();
    ensure(state.selection.effort === alternative, 'Connection effort not saved');
    await page.reload();
    await navigate('Kết nối AI');
    await effort.waitFor();
    ensure(await effort.inputValue() === alternative, 'Effort did not survive reload');
    for (const width of [1440, 1024, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      ensure(!await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), `Connections overflow at ${width}px`);
      await page.screenshot({ path: `output/playwright/effort-connections-${width}.png`, fullPage: true, animations: 'disabled' });
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await navigate('Tổng quan');
    const composerEffort = page.getByRole('combobox', { name: 'Effort AI', exact: true });
    await composerEffort.waitFor();
    ensure(await composerEffort.inputValue() === alternative, 'Composer effort differs from saved selection');
    await composerEffort.selectOption(nativeModel.default_effort);
    await page.waitForFunction(value => document.querySelector('[aria-label="Effort AI"]')?.value === value && !document.querySelector('[aria-label="Effort AI"]')?.disabled, nativeModel.default_effort);
    await page.locator('#agent-function').selectOption('gen_testcase');
    await page.getByRole('textbox', { name: 'Yêu cầu của bạn', exact: true }).fill('Tạo UI smoke test từ website, không có tài liệu.');
    for (const width of [1440, 1024, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      ensure(!await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), `Composer overflow at ${width}px`);
      await page.screenshot({ path: `output/playwright/effort-composer-${width}.png`, fullPage: true, animations: 'disabled' });
    }
    await page.getByRole('button', { name: 'Gửi cho agent', exact: true }).click();
    await page.getByText('Đã giao việc cho Tạo test case.', { exact: true }).waitFor();
    ensure(submitted.effort === nativeModel.default_effort && submitted.provider === 'codex' && submitted.model === nativeModel.id, 'Task did not include selected effort');
    await page.setViewportSize({ width: 1440, height: 1000 });

    // Check model changes against intentionally different native capabilities.
    const sample = { id: 'narrow-model', name: 'Narrow model', default_effort: 'medium', efforts: [{ id: 'medium', name: 'medium' }] };
    state.providers.find(p => p.id === 'codex').models.push(sample);
    state.selection = { provider: 'codex', model: nativeModel.id, effort: nativeModel.efforts.at(-1).id };
    await page.reload();
    await page.getByRole('combobox', { name: 'Model AI', exact: true }).selectOption(sample.id);
    await page.waitForFunction(() => document.querySelector('[aria-label="Effort AI"]')?.value === 'medium' && !document.querySelector('[aria-label="Effort AI"]')?.disabled);
    ensure(state.selection.effort === 'medium', 'Changing model retained unsupported effort');
    state = {
      ready: true, active_provider: 'claude', pending_provider: null, selection: { provider: 'claude', model: 'opus', effort: 'max' },
      providers: live.providers.map(p => ({ ...p, connected: p.id === 'claude', blocked: p.id !== 'claude', models: p.id === 'claude' ? [
        { id: 'opus', name: 'Opus', efforts: [{ id: 'low', name: 'low' }, { id: 'max', name: 'max' }] },
        { id: 'haiku', name: 'Haiku', efforts: [] },
      ] : [] })),
    };
    await page.reload();
    await composerEffort.waitFor();
    ensure(await composerEffort.inputValue() === 'max', 'Claude effort not shown');
    await navigate('Kết nối AI');
    await card('Claude Code').getByRole('combobox', { name: 'Effort Claude Code', exact: true }).waitFor();
    await card('Claude Code').getByRole('combobox', { name: 'Model Claude Code', exact: true }).selectOption('haiku');
    ensure(!await page.getByRole('combobox', { name: 'Effort Claude Code', exact: true }).count(), 'Unsupported Claude model shows effort');
    await navigate('Tổng quan');
    await page.getByRole('combobox', { name: 'Model AI', exact: true }).selectOption('haiku');
    await page.waitForFunction(() => !document.querySelector('[aria-label="Effort AI"]'));
    state = { ...state, active_provider: 'antigravity', selection: { provider: 'antigravity', model: 'agy-model' }, providers: state.providers.map(p => ({ ...p, connected: p.id === 'antigravity', blocked: p.id !== 'antigravity', models: p.id === 'antigravity' ? [{ id: 'agy-model', name: 'Native High variant' }] : [] })) };
    await page.reload();
    await page.getByRole('combobox', { name: 'Model AI', exact: true }).waitFor();
    ensure(!await composerEffort.count(), 'Antigravity with no effort capabilities shows selector');
    await navigate('Kết nối AI');
    await card('Antigravity').getByRole('combobox', { name: 'Model Antigravity', exact: true }).waitFor();
    ensure(!await page.getByRole('combobox', { name: 'Effort Antigravity', exact: true }).count(), 'Antigravity card shows unsupported effort');
  } finally {
    await page.unrouteAll({ behavior: 'wait' });
    await page.evaluate(saved => { if (saved) localStorage.setItem('testagent-project', saved); else localStorage.removeItem('testagent-project'); }, originalProject);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(base);
    await navigate('Kết nối AI');
  }
  return 'Verified native effort catalog in picker, selection persistence after reload, composer synchronization, task payload, reset when changing model, hidden controls for unsupported Claude/Antigravity models, and 1440/1024/390px layouts. UI writes used mocks; user account and selection were preserved.';
}
