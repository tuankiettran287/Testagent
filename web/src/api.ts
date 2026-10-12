const BASE = '/api';

export type Project = { id: string; name: string; base_url: string; environment: string; created_at: string };
export type Source = { id: string; kind: string; name: string; origin: string; created_at: string };
export type AgentSkill = { id: string; label: string; description: string; file: string; mode: 'test_cases' | 'analysis' | 'execution' | 'orchestration'; requires: 'none' | 'code' | 'run' | 'cases'; category?: 'automation' | 'diagnostics' | 'context'; workflow?: string; uses_ai?: boolean; max_cases?: number };
export type TaskFinding = { title: string; detail: string; severity: string; evidence_ids: string[] };
export type TaskOutput = { kind?: 'test_cases' | 'analysis'; skill_id?: string; skill_file?: string; summary: string; risks?: string[]; case_count?: number; case_ids?: string[]; executable_ids?: string[]; findings?: TaskFinding[]; recommendations?: string[]; run_id?: string | null; workflow?: 'ui_automation' | 'execution'; phase?: string; scenarios?: string[]; activity?: { message: string; url?: string }[]; blocked_reason?: string; manual_count?: number; execution?: { status: string; total?: number; completed?: number; counts?: Record<string, number> } };
export type Task = { id: string; prompt: string; intent: string; skill_file: string | null; status: string; summary: string; error: string; created_at: string; ai_provider: string | null; ai_model: string | null; ai_effort: string | null; parent_task_id?: string | null; sub_tasks?: Task[]; orchestration?: { function?: string; reason?: string; source?: string; run_id?: string | null; case_ids?: string[]; sub_tasks?: { function: string; prompt: string; task_id?: string }[]; metrics?: { sub_agent_count: number; completed: number; wall_ms: number; worker_ms: number } } };
export type AiProviderId = 'codex' | 'antigravity' | 'claude';
export type AiEffort = { id: string; name: string; description?: string };
export type AiModel = { id: string; name: string; default: boolean; efforts?: AiEffort[]; default_effort?: string | null };
export type AiProvider = { id: AiProviderId; name: string; installed: boolean; connected: boolean; blocked: boolean; pending: boolean; models: AiModel[]; account: string | null; plan: string | null; message: string | null };
export type AiSelection = { provider: AiProviderId; model: string; effort?: string | null };
export type AiState = { providers: AiProvider[]; selection: AiSelection | null; ready: boolean; active_provider: AiProviderId | null; pending_provider: AiProviderId | null };
export type AiLogin = { provider: AiProviderId; mode: 'connected' | 'browser' | 'device' | 'native' | 'manual'; url?: string; user_code?: string; message: string };
export type Action = { action: string; url?: string; target?: Record<string, string>; value?: string };
export type TestCase = {
  id: string; task_id: string; title: string; level: string; type: string; priority: string;
  preconditions: string[]; steps: string[]; expected: string[]; source_ids: string[];
  automation: { actions: Action[] } | null;
  api_request: { method: string; path: string; expected_status: number; headers: Record<string, string>; body?: unknown } | null;
  unit_test_code: string | null; created_at: string;
  readiness?: { status: 'ready' | 'manual' | 'needs_input' | 'invalid'; engine: 'playwright' | 'api' | null; reason: string };
  last_status?: string | null; last_run_id?: string | null;
};
export type RunResult = { id: string; test_case_id: string; title: string; status: string; duration_ms: number; failure_type: string | null; message: string; artifacts: string[] };
export type RunMode = 'sequential' | 'parallel';
export type Run = { id: string; status: string; requested_at: string; started_at: string | null; finished_at: string | null; summary: { error?: string; total?: number; completed?: number; test_case_ids?: string[]; mode?: RunMode; workers?: number; counts?: Record<string, number> }; results?: RunResult[] };
export type TaskOptions = { case_ids?: string[]; execution_mode?: 'generate' | 'run'; run_mode?: RunMode; workers?: number; agent_mode?: 'auto' | 'single' };
export const canRun = (test: TestCase) => test.readiness ? test.readiness.status === 'ready' : Boolean(test.automation || test.api_request);
export type Coverage = { source_count: number; test_case_count: number; sources_with_tests: number; uncovered_sources: Source[] };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(BASE + path, init);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
    } catch { /* Keep HTTP status */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function json(method: string, data: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) };
}

export const api = {
  aiProviders: (refresh = false) => request<AiState>(`/ai/providers?refresh=${refresh}`),
  selectAi: (selection: AiSelection) => request<AiSelection>('/ai/selection', json('PUT', selection)),
  loginAi: (provider: AiProviderId, device_code = false) => request<AiLogin>(`/ai/providers/${provider}/login`, json('POST', { device_code })),
  cancelAiLogin: (provider: AiProviderId) => request<{ message: string }>(`/ai/providers/${provider}/login/cancel`, json('POST', {})),
  logoutAi: (provider: AiProviderId) => request<{ message: string }>(`/ai/providers/${provider}/logout`, json('POST', {})),
  health: () => request<{ status: string; model_configured: boolean; browser_runner_ready: boolean }>('/health'),
  projects: () => request<Project[]>('/projects'),
  createProject: (data: { name: string; base_url: string; environment: string }) => request<Project>('/projects', json('POST', data)),
  updateProject: (id: string, data: { base_url: string; environment: string }) => request<Project>(`/projects/${id}`, json('PATCH', data)),
  sources: (id: string) => request<Source[]>(`/projects/${id}/sources`),
  coverage: (id: string) => request<Coverage>(`/projects/${id}/coverage`),
  tasks: (id: string) => request<Task[]>(`/projects/${id}/tasks`),
  skills: () => request<AgentSkill[]>('/agent/skills'),
  tests: (id: string) => request<TestCase[]>(`/projects/${id}/tests`),
  runs: (id: string) => request<(Omit<Run, 'summary'> & { summary: string })[]>(`/projects/${id}/runs`).then(rows => rows.map(row => ({ ...row, summary: JSON.parse(row.summary) as Run['summary'] }))),
  run: (id: string) => request<Run>(`/runs/${id}`),
  createTask: (project_id: string, prompt: string, agentFunction: string, run_id?: string, selection?: AiSelection | null, options: TaskOptions = {}) => request<Task>('/agent/tasks', json('POST', { project_id, prompt, function: agentFunction, run_id, provider: selection?.provider, model: selection?.model, effort: selection?.effort, ...options })),
  execute: (project_id: string, test_case_ids: string[], mode: RunMode = 'sequential', workers = 3) => request<Run>('/tests/execute', json('POST', { project_id, test_case_ids, mode, workers })),
  importRepo: (id: string, location: string) => request<{ imported: number; skipped: number }>(`/projects/${id}/repositories`, json('POST', { location })),
  inspectUi: (id: string, path: string) => request<{ source_id: string; elements: number }>(`/projects/${id}/inspect-ui`, json('POST', { path })),
  upload: async (id: string, kind: 'documents' | 'openapi' | 'repositories/zip', file: File) => {
    const form = new FormData(); form.append('file', file);
    return request<{ source_id?: string; imported?: number }>(`/projects/${id}/${kind}`, { method: 'POST', body: form });
  },
  playwright: async (id: string) => {
    const response = await fetch(`${BASE}/tests/${id}/playwright`);
    if (!response.ok) throw new Error(await response.text());
    return response.text();
  },
  updateAutomation: (id: string, automation: { actions: Action[] }) => request<TestCase>(`/tests/${id}/automation`, json('PUT', automation)),
};

