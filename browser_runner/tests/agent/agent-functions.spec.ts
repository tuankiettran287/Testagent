import { test, expect, type APIRequestContext, type Page, type TestInfo } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { performAction } from '../../src/runtime.js';

type CaseDefinition = { id: string; title: string; function?: string; scenario?: string; steps: string[]; expected: string[]; report_demo?: boolean };
const catalog: { cases: CaseDefinition[] } = JSON.parse(readFileSync(
  path.resolve(import.meta.dirname, '../../../tests/agent_function_cases.json'), 'utf8'));

class AgentAPI {
  events: unknown[] = [];
  constructor(readonly request: APIRequestContext) {}

  async call(method: string, url: string, options: Record<string, unknown> = {}, expectedStatus = 200): Promise<any> {
    const response = await this.request.fetch(url, { method, ...options });
    const text = await response.text();
    let body: any = text;
    try { body = JSON.parse(text); } catch { /* Reports can return plain text. */ }
    this.events.push({ method, url, status: response.status(), body });
    expect(response.status(), `${method} ${url}: ${text}`).toBe(expectedStatus);
    return body;
  }

  get(url: string) { return this.call('GET', url); }
  post(url: string, data: unknown, status = 200) { return this.call('POST', url, { data }, status); }
  state() { return this.get('/__fixture/state'); }

  async task(state: any, fn: string, options: Record<string, unknown> = {}) {
    const created = await this.post('/api/agent/tasks', {
      project_id: state.project_id, function: fn, agent_mode: 'single',
      prompt: 'Verify the generated status portal using its supplied requirements.', ...options,
    }, 202);
    let task: any;
    await expect.poll(async () => {
      task = await this.get(`/api/agent/tasks/${created.id}`);
      return task.status;
    }, { timeout: 90_000, intervals: [100, 250, 500] }).toMatch(/^(COMPLETED|READY|FAILED|NEEDS_INPUT)$/);
    return task;
  }

  async run(state: any, ids: string[]) {
    const created = await this.post('/api/tests/execute', { project_id: state.project_id, test_case_ids: ids }, 202);
    let run: any;
    await expect.poll(async () => {
      run = await this.get(`/api/runs/${created.id}`);
      return run.status;
    }, { timeout: 90_000, intervals: [100, 250, 500] }).toMatch(/^(COMPLETED|FAILED)$/);
    return run;
  }

  async attachRun(run: any, info: TestInfo) {
    await info.attach(`run-${run.id}.json`, { body: JSON.stringify(run, null, 2), contentType: 'application/json' });
    for (const row of run.results) {
      for (const name of row.artifacts) {
        const response = await this.request.get(`/api/runs/${run.id}/artifacts/${encodeURIComponent(name)}`);
        expect(response.status(), `Missing artifact ${name}`).toBe(200);
        const type = name.endsWith('.zip') ? 'application/zip' : name.endsWith('.png') ? 'image/png' :
          name.endsWith('.webm') ? 'video/webm' : 'text/plain';
        await info.attach(name, { body: await response.body(), contentType: type });
      }
    }
  }
}

async function checkFunction(api: AgentAPI, state: any, definition: CaseDefinition, page: Page, info: TestInfo) {
  const fn = definition.function!;
  const skills = await api.get('/api/agent/skills');
  const skill = skills.find((item: any) => item.id === fn);
  expect(skill, `Function ${fn} is registered`).toBeTruthy();
  const options: Record<string, unknown> = {};
  if (skill.requires === 'cases') options.case_ids = [fn === 'run_tests' ? state.api_case : state.manual_case];
  if (skill.requires === 'run') options.run_id = state.failed_run;
  const task = await test.step(`Submit ${fn} through the real agent API`, () => api.task(state, fn, options));
  expect(task.status, task.error).toBe('COMPLETED');
  const output = JSON.parse(task.summary);
  if (fn === 'orchestrator') {
    expect(task.intent).toBe('performance');
    expect(task.orchestration.function).toBe('performance');
    expect((await api.state()).model_calls - state.model_calls).toBe(2);
  } else {
    expect(output.skill_id).toBe(fn);
  }
  if (skill.mode === 'analysis') {
    expect(output.findings.length).toBeGreaterThan(0);
    for (const finding of output.findings) expect(finding.evidence_ids).not.toContain('fabricated');
  }
  if (skill.workflow === 'browser' || skill.mode === 'execution') {
    expect(output.execution.status).toBe('COMPLETED');
    expect(output.execution.counts.PASS).toBe(1);
    const run = await api.get(`/api/runs/${output.run_id}`);
    expect(run.results).toHaveLength(1);
    expect(run.results[0].status).toBe('PASS');
    await api.attachRun(run, info);
    if (skill.workflow === 'browser') {
      expect(run.results[0].artifacts.some((name: string) => name.endsWith('-trace.zip'))).toBe(true);
      expect(output.context_manifest.task_id).toBe(task.id);
      const generated = await api.get(`/api/tests/${output.case_ids[0]}`);
      await test.step('Execute the generated automation in Playwright Chromium', async () => {
        for (const action of generated.automation.actions) {
          await test.step(`${action.action} ${action.value || action.url || ''}`,
            () => performAction(page, state.target_url, action));
        }
        await expect(page.locator('#status')).toHaveText('Healthy');
        await info.attach('generated-browser-result.png', { body: await page.screenshot(), contentType: 'image/png' });
      });
    }
  }
  if (fn === 'run_tests') {
    const after = await api.state();
    expect(after.model_calls).toBe(state.model_calls);
    expect(after.resolution_calls).toBe(state.resolution_calls);
  }
  if (fn === 'automation_builder' || fn === 'repair_automation') {
    const original = fn === 'automation_builder' ? state.manual_case : state.failed_case;
    expect(output.case_ids).toEqual([original]);
    const updated = await api.get(`/api/tests/${original}`);
    expect(updated.expected).toEqual(['Status text contains Healthy']);
    expect(updated.automation.actions).toContainEqual(expect.objectContaining({ action: 'assert_text', value: 'Healthy' }));
  }
  if (['gen_testcase', 'api_test', 'unit_test'].includes(fn)) {
    expect(output.case_count).toBe(1);
    const generated = await api.get(`/api/tests/${output.case_ids[0]}`);
    expect(generated.source_ids).toEqual([fn === 'unit_test' ? state.code_source_id : state.source_id]);
    if (fn === 'gen_testcase') expect(generated.readiness.status).toBe('manual');
    if (fn === 'api_test') {
      const run = await api.run(state, [generated.id]);
      expect(run.status).toBe('COMPLETED');
      expect(run.results[0].status).toBe('PASS');
      await api.attachRun(run, info);
    }
    if (fn === 'unit_test') {
      expect(await api.post('/__fixture/parse-python', { code: generated.unit_test_code })).toEqual({ syntax_valid: true, executed: false });
    }
  }
  if (fn === 'report') {
    expect(await api.get(`/api/agent/tasks/${task.id}/report`)).toContain(state.failed_run);
  }
}

const scenarios: Record<string, (api: AgentAPI, state: any, info: TestInfo) => Promise<void>> = {
  async manual_rejected(api, state) {
    const created = await api.post('/__fixture/cases', { title: 'Generated manual-only case', level: 'ui' });
    await api.post('/api/tests/execute', { project_id: state.project_id, test_case_ids: [created.id] }, 422);
    expect((await api.state()).runs).toBe(state.runs);
  },
  async cross_origin_rejected(api, state) {
    const created = await api.post('/__fixture/cases', { title: 'Generated cross-origin case', level: 'api',
      api_request: { method: 'GET', path: 'https://outside.invalid/health', expected_status: 200 } });
    await api.post('/api/tests/execute', { project_id: state.project_id, test_case_ids: [created.id] }, 422);
    expect((await api.state()).runs).toBe(state.runs);
  },
  async foreign_case_rejected(api, state) {
    const other = await api.post('/api/projects', { name: 'Generated other project' }, 201);
    await api.post('/api/agent/tasks', { project_id: other.id, function: 'case_review',
      prompt: 'Review the selected test case.', case_ids: [state.api_case] }, 422);
    const after = await api.state();
    expect(after.tasks).toBe(state.tasks);
    expect(after.model_calls).toBe(state.model_calls);
  },
  async assertion_failure_reported(api, state, info) {
    const created = await api.post('/__fixture/cases', { title: 'Generated wrong HTTP oracle', level: 'api',
      api_request: { method: 'GET', path: '/health', expected_status: 201 } });
    const run = await api.run(state, [created.id]);
    expect(run.status).toBe('FAILED');
    expect(run.results[0].status).toBe('FAIL');
    expect(run.summary.counts).toMatchObject({ PASS: 0, FAIL: 1 });
    await api.attachRun(run, info);
  },
  async duplicate_delivery(api, state) {
    const run = await api.run(state, [state.api_case]);
    expect(run.status).toBe('COMPLETED');
    expect(await api.post(`/__fixture/replay/${run.id}`, {})).toEqual({ execution_calls: 0, unchanged: true });
  },
  async invalid_model_rejected(api, state) {
    await api.post('/__fixture/model-response', { project_name: 'Isolated status portal', function: 'gen_testcase',
      response: { intent: 'test_generation', summary: 'Invalid scripted response.', cases: [], shell_command: 'unsupported-command' } });
    const task = await api.task(state, 'gen_testcase');
    expect(task.status).toBe('FAILED');
    expect(task.error).toBeTruthy();
    expect((await api.state()).cases).toBe(state.cases);
  },
  async generate_without_execution(api, state) {
    const task = await api.task(state, 'ui_automation', { execution_mode: 'generate' });
    expect(task.status, task.error).toBe('READY');
    const output = JSON.parse(task.summary);
    expect(output.execution).toBeNull();
    expect(output.executable_ids).toHaveLength(1);
    expect((await api.state()).runs).toBe(state.runs);
  },
  async missing_context(api, state) {
    const other = await api.post('/api/projects', { name: 'Generated empty Playwright project' }, 201);
    await api.post('/__fixture/model-response', { project_name: other.name, function: 'orchestrator',
      response: { function: 'repo_under', reason: 'Repository analysis requires source code.' } });
    const task = await api.task(state, 'orchestrator', { project_id: other.id });
    expect(task.status).toBe('NEEDS_INPUT');
    expect(JSON.parse(task.summary).blocked_reason).toBeTruthy();
    expect((await api.state()).model_calls - state.model_calls).toBe(1);
  },
  async document_ingestion(api, state) {
    const uploaded = await api.call('POST', `/api/projects/${state.project_id}/documents`, { multipart: {
      file: { name: 'generated-requirement.txt', mimeType: 'text/plain',
        buffer: Buffer.from('Generated acceptance requirement: invoice limit is exactly 37 items.') },
    } }, 201);
    const hits = await api.get(`/api/projects/${state.project_id}/knowledge?q=invoice`);
    expect(hits.some((hit: any) => hit.source_id === uploaded.source_id && hit.content.includes('37 items'))).toBe(true);
  },
  async repository_ingestion(api, state) {
    const archive = await api.request.get('/__fixture/repository.zip');
    expect(archive.status()).toBe(200);
    const uploaded = await api.call('POST', `/api/projects/${state.project_id}/repositories/zip`, { multipart: {
      file: { name: 'generated-repository.zip', mimeType: 'application/zip', buffer: await archive.body() },
    } }, 201);
    expect(uploaded.imported).toBe(1);
    const hits = await api.get(`/api/projects/${state.project_id}/knowledge?q=generated_limit`);
    expect(hits.some((hit: any) => uploaded.source_ids.includes(hit.source_id) && hit.kind === 'code' && hit.content.includes('generated_limit'))).toBe(true);
  },
  async openapi_ingestion(api, state) {
    const contract = { openapi: '3.0.3', info: { title: 'Generated API', version: '1.0' },
      paths: { '/health': { get: { responses: { '200': { description: 'Healthy' } } } } } };
    const uploaded = await api.call('POST', `/api/projects/${state.project_id}/openapi`, { multipart: {
      file: { name: 'generated-openapi.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(contract)) },
    } }, 201);
    const hits = await api.get(`/api/projects/${state.project_id}/knowledge?q=health`);
    expect(hits.some((hit: any) => hit.source_id === uploaded.source_id && hit.kind === 'openapi' && hit.content.includes('/health') && hit.content.includes('200'))).toBe(true);
  },
};

for (const definition of catalog.cases.filter(item => !item.report_demo)) {
  test(`${definition.id} ${definition.title}`, async ({ request, page }, info) => {
    const api = new AgentAPI(request);
    info.annotations.push({ type: 'case-id', description: definition.id });
    await info.attach('reviewed-case.json', { body: JSON.stringify(definition, null, 2), contentType: 'application/json' });
    try {
      await api.call('DELETE', '/__fixture/model-response');
      const state = await api.state();
      expect(state.workspace_data_imported).toBe(false);
      expect(state.catalog_ids).toEqual(catalog.cases.map(item => item.id));
      if (definition.function) await checkFunction(api, state, definition, page, info);
      else await test.step(definition.title, () => scenarios[definition.scenario!](api, state, info));
    } finally {
      await info.attach('api-evidence.json', { body: JSON.stringify(api.events, null, 2), contentType: 'application/json' });
    }
  });
}
