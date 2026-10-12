async (page) => {
  const project = { id: 'orchestrator-ui', name: 'Orchestrator preview', base_url: '', environment: 'local', created_at: '2026-10-05T00:00:00Z' };
  const ai = { ready: true, active_provider: 'codex', pending_provider: null, selection: { provider: 'codex', model: 'preview-model', effort: 'high' }, providers: [{ id: 'codex', name: 'Codex', installed: true, connected: true, blocked: false, pending: false, models: [{ id: 'preview-model', name: 'Preview model', default: true, efforts: [{ id: 'high', name: 'High' }] }], account: 'Preview account' }] };
  const skills = await (await page.request.get('http://127.0.0.1:15173/orchestrator-skills.json')).json();
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    let json = [];
    if (path === '/api/projects') json = [project];
    else if (path === '/api/agent/skills') json = skills;
    else if (path.startsWith('/api/ai/providers')) json = ai;
    else if (path === '/api/health') json = { status: 'ok', model_configured: true, browser_runner_ready: true };
    else if (path.endsWith('/coverage')) json = { source_count: 0, test_case_count: 0, sources_with_tests: 0, uncovered_sources: [] };
    return route.fulfill({ json });
  });
  await page.goto('http://127.0.0.1:15173');
  await page.locator('#agent-function').waitFor();
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.screenshot({ path: `output/playwright/orchestrator-before-${width}.png`, fullPage: true });
  }
  return { defaultFunction: await page.locator('#agent-function').inputValue() };
}
