import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { api, canRun, type AgentSkill, type AiLogin, type AiProviderId, type AiSelection, type AiState, type Coverage, type Project, type Run, type RunMode, type Source, type Task, type TaskOutput, type TestCase } from './api';
import AiConnections, { AiPicker } from './AiConnections';
import TaskWorkflow, { SubAgentTasks, TaskCaption, taskStatusLabel } from './TaskWorkflow';
import TestLibrary, { RunOptions } from './TestLibrary';

type View = 'overview' | 'sources' | 'tests' | 'runs' | 'ai';
type IconName = 'grid' | 'layers' | 'flask' | 'activity' | 'plus' | 'arrow' | 'upload' | 'spark' | 'check' | 'close' | 'menu' | 'external' | 'play' | 'code' | 'settings' | 'server' | 'folder' | 'bolt' | 'info' | 'search' | 'file' | 'chevron';

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>,
    flask: <><path d="M9 3h6M10 3v7l-6 8a2 2 0 0 0 1.6 3h12.8a2 2 0 0 0 1.6-3l-6-8V3"/><path d="M7 16h10"/></>,
    activity: <><path d="M3 12h4l3-7 4 14 3-7h4"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    arrow: <><path d="M5 12h14m-6-6 6 6-6 6"/></>,
    upload: <><path d="M12 16V3m-5 5 5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></>,
    spark: <><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3ZM19 17l.7 1.3L21 19l-1.3.7L19 21l-.7-1.3L17 19l1.3-.7L19 17Z"/></>,
    check: <><path d="m5 12 4 4L19 6"/></>,
    close: <><path d="M6 6l12 12M18 6 6 18"/></>,
    menu: <><path d="M4 7h16M4 12h16M4 17h16"/></>,
    external: <><path d="M14 4h6v6M20 4l-9 9"/><path d="M20 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h5"/></>,
    play: <><path d="m8 5 11 7-11 7V5Z"/></>,
    code: <><path d="m8 8-4 4 4 4m8-8 4 4-4 4m-3-11-2 14"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.8 1.8 0 0 0 .36 2l-1.76 1.76a1.8 1.8 0 0 0-2-.36 1.8 1.8 0 0 0-1.1 1.66V22h-2.5v-1.94A1.8 1.8 0 0 0 11.3 18.4a1.8 1.8 0 0 0-2 .36l-1.76-1.76a1.8 1.8 0 0 0 .36-2A1.8 1.8 0 0 0 6.24 13.9H4.3v-2.5h1.94A1.8 1.8 0 0 0 7.9 10.3a1.8 1.8 0 0 0-.36-2L9.3 6.54a1.8 1.8 0 0 0 2 .36 1.8 1.8 0 0 0 1.1-1.66V3.3h2.5v1.94A1.8 1.8 0 0 0 16 6.9a1.8 1.8 0 0 0 2-.36l1.76 1.76a1.8 1.8 0 0 0-.36 2 1.8 1.8 0 0 0 1.66 1.1H23v2.5h-1.94A1.8 1.8 0 0 0 19.4 15Z" transform="translate(-1.65 -1.65) scale(1.1)"/></>,
    server: <><rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6.5h.01M7 17.5h.01M11 6.5h6M11 17.5h6"/></>,
    folder: <><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10H3V7Z"/></>,
    bolt: <><path d="m13 2-9 11h7l-1 9 10-12h-7l1-8Z"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
    file: <><path d="M5 3h9l5 5v13H5V3Z"/><path d="M14 3v5h5M8 13h8M8 17h6"/></>,
    chevron: <><path d="m9 6 6 6-6 6"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function TerminalMark({ className }: { className: string }) {
  return <img className={className} src="/favicon.svg?v=5" alt="" aria-hidden="true" />;
}

function SidebarStatus({ label, detail, state }: { label: string; detail: string; state: 'ready' | 'idle' | 'checking' }) {
  return <div className={`sidebar-status sidebar-status-${state}`}>
    <span className="status-led" aria-hidden="true" />
    <span className="sidebar-status-copy"><strong>{label}</strong><small>{detail}</small></span>
  </div>;
}

const NAV: { id: View; label: string; icon: IconName }[] = [
  { id: 'overview', label: 'Tổng quan', icon: 'grid' },
  { id: 'sources', label: 'Nguồn dữ liệu', icon: 'layers' },
  { id: 'tests', label: 'Test cases', icon: 'flask' },
  { id: 'runs', label: 'Lịch sử chạy', icon: 'activity' },
  { id: 'ai', label: 'Kết nối AI', icon: 'spark' },
];

function date(value?: string | null) {
  return value ? new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : '—';
}

function parseTaskOutput(value?: string): TaskOutput | null {
  if (!value) return null;
  try { return JSON.parse(value) as TaskOutput; }
  catch { return null; }
}

function Status({ value }: { value: string }) {
  return <span className={`status status-${value.toLowerCase()}`}>{taskStatusLabel(value)}</span>;
}

function Empty({ icon, title, description, action }: { icon: IconName; title: string; description: string; action?: ReactNode }) {
  return <div className="empty"><div className="empty-icon"><Icon name={icon} size={23} /></div><h3>{title}</h3><p>{description}</p>{action}</div>;
}

export default function App() {
  const [view, setView] = useState<View>('overview');
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState('');
  const [sources, setSources] = useState<Source[]>([]);
  const [tests, setTests] = useState<TestCase[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [skills, setSkills] = useState<AgentSkill[]>([]);
  const [selectedFunction, setSelectedFunction] = useState('orchestrator');
  const [selectedRunId, setSelectedRunId] = useState('');
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);
  const [agentCaseIds, setAgentCaseIds] = useState<string[]>([]);
  const [executionMode, setExecutionMode] = useState<'generate' | 'run'>('generate');
  const [agentMode, setAgentMode] = useState<'auto' | 'single'>('auto');
  const [runMode, setRunMode] = useState<RunMode>('sequential');
  const [workers, setWorkers] = useState(3);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [selectedCase, setSelectedCase] = useState<TestCase | null>(null);
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [apiReady, setApiReady] = useState<boolean | null>(null);
  const [aiState, setAiState] = useState<AiState | null>(null);
  const [aiLoaded, setAiLoaded] = useState(false);
  const aiRequestId = useRef(0);
  const modelReady = aiState?.ready ?? (aiLoaded ? false : null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiLogin, setAiLogin] = useState<AiLogin | null>(null);
  const [browserRunnerReady, setBrowserRunnerReady] = useState<boolean | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [name, setName] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [environment, setEnvironment] = useState('staging');
  const [prompt, setPrompt] = useState('');
  const [testQuery, setTestQuery] = useState('');
  const [testLevel, setTestLevel] = useState('all');
  const [repoLocation, setRepoLocation] = useState('');
  const [inspectPath, setInspectPath] = useState('/');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploadKind, setUploadKind] = useState<'documents' | 'openapi' | 'repositories/zip'>('documents');
  const activeProject = useRef(projectId);
  activeProject.current = projectId;
  const project = projects.find(item => item.id === projectId);
  const executable = tests.filter(canRun);
  const activeCaseIds = new Set(runs.filter(run => ['QUEUED', 'RUNNING'].includes(run.status)).flatMap(run => run.summary.test_case_ids || []));
  const filteredTests = tests.filter(test =>
    (testLevel === 'all' || test.level === testLevel) &&
    `${test.title} ${test.type} ${test.id}`.toLowerCase().includes(testQuery.trim().toLowerCase()),
  );
  const latestRun = runs[0];
  const finishedRuns = runs.filter(run => ['COMPLETED', 'FAILED'].includes(run.status));
  const selectedSkill = skills.find(skill => skill.id === selectedFunction);
  const autoRouting = selectedSkill?.mode === 'orchestration';
  const usesAi = selectedSkill?.uses_ai !== false && selectedSkill?.mode !== 'execution';
  const browserWorkflow = autoRouting || selectedSkill?.workflow === 'browser' || selectedSkill?.id === 'ui_automation';
  const selectedTask = tasks.find(task => task.id === selectedTaskId);
  const selectedTaskOutput = parseTaskOutput(selectedTask?.summary);
  const skillInputReady = autoRouting ? agentCaseIds.length <= 30
    : selectedSkill?.requires === 'run' ? finishedRuns.length > 0
    : selectedSkill?.requires === 'cases' ? agentCaseIds.length > 0 && agentCaseIds.length <= (selectedSkill.max_cases || 30)
    : selectedSkill?.requires === 'code' ? sources.some(source => source.kind === 'code')
      : true;
  const setupDone = Number(modelReady === true) + Number(Boolean(project?.base_url));
  const hasProjectData = sources.length > 0 || tests.length > 0 || runs.length > 0;

  const loadProjects = useCallback(async () => {
    const items = await api.projects();
    setProjects(items);
    setProjectId(current => {
      if (items.some(p => p.id === current)) return current;
      const saved = localStorage.getItem('testagent-project');
      return items.find(p => p.id === saved)?.id || items[0]?.id || '';
    });
  }, []);

  const loadAi = useCallback(async (refresh = false) => {
    const requestId = ++aiRequestId.current;
    try {
      const data = await api.aiProviders(refresh);
      if (requestId !== aiRequestId.current) return;
      setAiState(data);
      setAiLogin(current => current && data.pending_provider === current.provider ? current : null);
    } finally {
      if (requestId === aiRequestId.current) setAiLoaded(true);
    }
  }, []);

  const loadWorkspace = useCallback(async () => {
    if (!projectId) return;
    const [sourceItems, caseItems, taskItems, runItems, coverageData] = await Promise.all([
      api.sources(projectId), api.tests(projectId), api.tasks(projectId), api.runs(projectId), api.coverage(projectId),
    ]);
    if (activeProject.current !== projectId) return;
    setSources(sourceItems); setTests(caseItems); setTasks(taskItems); setRuns(runItems); setCoverage(coverageData);
  }, [projectId]);

  useEffect(() => {
    api.health().then(data => { setApiReady(true); setBrowserRunnerReady(data.browser_runner_ready); }).catch(() => { setApiReady(false); setBrowserRunnerReady(false); });
    api.skills().then(setSkills).catch(exc => setError(exc.message));
    loadAi().catch(exc => setError(exc.message));
    loadProjects().catch(exc => setError(exc.message));
  }, [loadProjects, loadAi]);

  useEffect(() => {
    if (!aiLogin) return;
    let stopped = false;
    let timer: number;
    const poll = async () => {
      try { await loadAi(true); }
      catch (exc) { if (!stopped) setError(exc instanceof Error ? exc.message : String(exc)); }
      if (!stopped) timer = window.setTimeout(poll, 5000);
    };
    timer = window.setTimeout(poll, 5000);
    return () => { stopped = true; window.clearTimeout(timer); };
  }, [aiLogin, loadAi]);

  async function aiAction(action: () => Promise<unknown>) {
    ++aiRequestId.current;
    setAiBusy(true); setError('');
    try { await action(); }
    catch (exc) { setError(exc instanceof Error ? exc.message : String(exc)); }
    finally { setAiBusy(false); }
  }

  async function selectAi(selection: AiSelection) {
    await aiAction(async () => {
      const selected = await api.selectAi(selection);
      setAiState(current => current ? { ...current, selection: selected, ready: true } : current);
    });
  }

  function loginAi(provider: AiProviderId, device?: boolean) {
    void aiAction(async () => {
      const result = await api.loginAi(provider, device);
      setAiLogin(result.mode === 'connected' ? null : result);
      if (result.mode === 'connected') setNotice(result.message);
      await loadAi();
    });
  }

  function cancelAiLogin(requestedProvider?: AiProviderId) {
    const provider = requestedProvider || aiLogin?.provider || aiState?.pending_provider;
    if (!provider) return;
    setAiLogin(null);
    void aiAction(async () => { await api.cancelAiLogin(provider); await loadAi(); });
  }

  function logoutAi(provider: AiProviderId) {
    setAiLogin(null);
    void aiAction(async () => {
      const result = await api.logoutAi(provider);
      setNotice(result.message);
      await loadAi();
    });
  }

  useEffect(() => {
    if (!projectId) return;
    localStorage.setItem('testagent-project', projectId);
    setSources([]); setTests([]); setTasks([]); setRuns([]); setCoverage(null);
    setSelectedTaskId(null); setSelectedRunId('');
    setSelectedCaseIds([]); setAgentCaseIds([]);
    loadWorkspace().catch(exc => setError(exc.message));
  }, [projectId, loadWorkspace]);

  useEffect(() => {
    if (!tasks.some(t => !['COMPLETED', 'FAILED', 'NEEDS_INPUT', 'READY'].includes(t.status)) && !runs.some(r => ['QUEUED', 'RUNNING'].includes(r.status))) return;
    const timer = window.setInterval(() => loadWorkspace().catch(exc => setError(exc.message)), 2500);
    return () => window.clearInterval(timer);
  }, [tasks, runs, loadWorkspace]);

  useEffect(() => {
    if (!selectedRun || !['QUEUED', 'RUNNING'].includes(selectedRun.status)) return;
    const timer = window.setInterval(() => {
      api.run(selectedRun.id).then(updated => setSelectedRun(current => current?.id === updated.id ? updated : current)).catch(exc => setError(exc.message));
    }, 2500);
    return () => window.clearInterval(timer);
  }, [selectedRun]);

  const metrics = useMemo(() => ({
    sourceCount: sources.length,
    testCount: tests.length,
    coverage: coverage && coverage.source_count ? Math.round(coverage.sources_with_tests / coverage.source_count * 100) : 0,
    passRate: latestRun?.summary?.total ? Math.round((latestRun.summary.counts?.PASS || 0) / latestRun.summary.total * 100) : null,
  }), [sources, tests, coverage, latestRun]);

  async function perform(label: string, action: () => Promise<unknown>, success: string) {
    setBusy(label); setError(''); setNotice('');
    try { await action(); setNotice(success); await loadWorkspace(); }
    catch (exc) { setError(exc instanceof Error ? exc.message : String(exc)); }
    finally { setBusy(''); }
  }

  async function createProject(event: FormEvent) {
    event.preventDefault(); setBusy('project'); setError('');
    try {
      const created = await api.createProject({ name, base_url: baseUrl, environment });
      await loadProjects(); setProjectId(created.id); setCreateOpen(false); setName(''); setBaseUrl('');
      setNotice('Đã tạo dự án mới. Kết nối AI và mô tả mục tiêu test; nạp tài liệu là tùy chọn.');
    } catch (exc) { setError(exc instanceof Error ? exc.message : String(exc)); }
    finally { setBusy(''); }
  }

  function openSettings() {
    if (!project) return;
    setBaseUrl(project.base_url); setEnvironment(project.environment); setSettingsOpen(true);
  }

  async function saveSettings(event: FormEvent) {
    event.preventDefault();
    if (!projectId) return;
    setBusy('settings'); setError('');
    try {
      await api.updateProject(projectId, { base_url: baseUrl, environment });
      await loadProjects(); setSettingsOpen(false); setNotice('Đã cập nhật cấu hình dự án.');
    } catch (exc) { setError(exc instanceof Error ? exc.message : String(exc)); }
    finally { setBusy(''); }
  }

  async function upload(file: File, kind: typeof uploadKind) {
    if (!projectId) return;
    await perform('upload', () => api.upload(projectId, kind, file), `Đã nạp ${file.name}.`);
  }

  async function submitPrompt(event: FormEvent) {
    event.preventDefault();
    if (!projectId || !prompt.trim() || !selectedSkill || !skillInputReady || (usesAi && (!modelReady || aiBusy))) return;
    const runId = autoRouting ? (selectedRunId || undefined) : selectedSkill.requires === 'run' ? (selectedRunId || finishedRuns[0]?.id) : undefined;
    await perform('task', async () => {
      const created = await api.createTask(projectId, prompt.trim(), selectedSkill.id, runId, usesAi ? aiState?.selection : null, {
        agent_mode: autoRouting ? agentMode : 'single',
        case_ids: autoRouting || selectedSkill.requires === 'cases' ? agentCaseIds : [], execution_mode: executionMode, run_mode: runMode, workers,
      });
      setSelectedTaskId(created.id);
    }, `Đã giao việc cho ${selectedSkill.label}.`);
    setPrompt('');
  }

  async function execute(ids: string[]) {
    if (!projectId || !ids.length) return;
    await perform('run', async () => {
      const created = await api.execute(projectId, ids, runMode, workers);
      setSelectedCase(null); setSelectedTaskId(null); setSelectedRun(await api.run(created.id));
      setSelectedCaseIds([]);
    }, 'Đã tạo lượt chạy. Kết quả sẽ cập nhật tự động.');
  }

  function assignCases(skillId: string, ids: string[]) {
    setSelectedFunction(skillId); setAgentCaseIds(ids); setSelectedCase(null); setSelectedTaskId(null);
    setPrompt(skillId === 'case_review' ? 'Rà soát các case đã chọn: coverage, điều kiện, assertion và khả năng chạy độc lập. Nêu rõ các điểm cần bổ sung.' : 'Chuyển các case đã chọn thành Playwright automation chạy độc lập. Giữ nguyên mục tiêu và kết quả mong đợi, dùng locator từ giao diện thực tế.');
    setExecutionMode('generate'); setView('overview');
  }

  function assignRun(skillId: string, run: Run) {
    setSelectedFunction(skillId); setSelectedRunId(run.id); setSelectedRun(null); setView('overview');
    setExecutionMode('generate');
    setPrompt(skillId === 'repair_automation' ? 'Phân tích các case automation bị lỗi trong lượt chạy này. Quan sát website và sửa locator hoặc bước thao tác theo bằng chứng; giữ nguyên các assertion và kết quả mong đợi.' : 'Phân tích lỗi trong lượt chạy này, phân biệt lỗi sản phẩm, dữ liệu và automation; trích dẫn bằng chứng và đề xuất xử lý.');
  }

  async function openRun(runId: string) {
    setBusy('run-detail'); setError('');
    try { setSelectedRun(await api.run(runId)); }
    catch (exc) { setError(exc instanceof Error ? exc.message : String(exc)); }
    finally { setBusy(''); }
  }

  async function openCode(test: TestCase) {
    setBusy('code'); setError('');
    try { setCode(await api.playwright(test.id)); }
    catch (exc) { setError(exc instanceof Error ? exc.message : String(exc)); }
    finally { setBusy(''); }
  }

  function navigate(next: View) { setView(next); setMenuOpen(false); setSelectedCase(null); setSelectedRun(null); }

  return <div className="app-shell">
    <div className="window-chrome" aria-label="TestAgent local terminal"><div className="traffic-lights" aria-hidden="true"><span className="traffic-light traffic-light-close" /><span className="traffic-light traffic-light-minimize" /><span className="traffic-light traffic-light-expand" /></div><div className="window-title"><Icon name="code" size={14} /> testagent — local workspace</div><div className="window-session"><span className="session-dot" /> LOCAL SESSION</div></div>
    {menuOpen && <button className="mobile-scrim" aria-label="Đóng menu" onClick={() => setMenuOpen(false)} />}
    <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
      <div className="brand"><TerminalMark className="brand-mark" /><div className="brand-copy"><strong>TestAgent</strong><span>QUALITY ENGINEERING CLI</span></div></div>
      <div className="side-caption"><span aria-hidden="true">~/</span> WORKSPACE</div>
      <nav aria-label="Điều hướng chính" className="side-nav">
        {NAV.map(item => <button key={item.id} className={`nav-item ${view === item.id ? 'active' : ''}`} aria-current={view === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><span className="nav-icon"><Icon name={item.icon} /></span><span>{item.label}</span></button>)}
      </nav>
      <div className="sidebar-bottom">
        <div className="system-label">SYSTEM <span>/</span> STATUS</div>
        <div className="status-list">
          <SidebarStatus label="API" detail={apiReady === null ? 'Đang kiểm tra' : apiReady ? 'Đang hoạt động' : 'Không khả dụng'} state={apiReady === null ? 'checking' : apiReady ? 'ready' : 'idle'} />
          <SidebarStatus label="Model AI" detail={modelReady === null ? 'Đang kiểm tra' : modelReady ? 'Đã kết nối' : aiState?.pending_provider ? 'Đang đăng nhập' : aiState?.active_provider ? 'Cần kết nối lại' : 'Chưa kết nối'} state={modelReady === null ? 'checking' : modelReady ? 'ready' : 'idle'} />
          <SidebarStatus label="Browser runner" detail={browserRunnerReady === null ? 'Đang kiểm tra' : browserRunnerReady ? 'Sẵn sàng' : 'Chưa sẵn sàng'} state={browserRunnerReady === null ? 'checking' : browserRunnerReady ? 'ready' : 'idle'} />
        </div>
        <div className="sidebar-version"><span>v0.1.0</span><span>LOCAL BUILD</span></div>
      </div>
    </aside>

    <div className="main-shell">
      <header className="topbar">
        <button className="icon-button mobile-menu" aria-label="Mở menu" onClick={() => setMenuOpen(!menuOpen)}><Icon name="menu" /></button>
        <div className="breadcrumb"><span className="shell-prompt">❯</span><span>~/testagent</span><span className="breadcrumb-slash">/</span><strong>{NAV.find(item => item.id === view)?.label}</strong></div>
        <div className="top-actions"><label className="sr-only" htmlFor="project-picker">Chọn dự án</label><div className="project-picker"><Icon name="folder" size={17} /><select id="project-picker" className="project-select" value={projectId} onChange={e => setProjectId(e.target.value)}><option value="" disabled>Chọn dự án</option>{projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select><Icon name="chevron" size={15} /></div><button className="button button-primary new-project" aria-label="Tạo dự án mới" onClick={() => setCreateOpen(true)}><Icon name="plus" size={17} /><span>Dự án mới</span></button></div>
      </header>

      <main className="content">
        {error && <div className="alert alert-error" role="alert"><span>{error}</span><button aria-label="Đóng lỗi" onClick={() => setError('')}><Icon name="close" size={17} /></button></div>}
        {notice && <div className="alert alert-success" role="status"><span>{notice}</span><button aria-label="Đóng thông báo" onClick={() => setNotice('')}><Icon name="close" size={17} /></button></div>}
        {view === 'ai' ? <AiConnections state={aiState} busy={aiBusy} login={aiLogin} onRefresh={() => void aiAction(() => loadAi(true))} onSelect={selectAi} onLogin={loginAi} onCancel={cancelAiLogin} onLogout={logoutAi} /> : !project ? <div className="welcome">
          <div className="welcome-copy">
            <div className="terminal-command"><span className="command-path">~/testagent</span><span className="command-symbol">❯</span><code>testagent init</code><span className="cursor" aria-hidden="true" /></div>
            <div className="welcome-kicker"><TerminalMark className="welcome-mark" /><span className="eyebrow">AUTONOMOUS QA WORKSPACE<br /><span>READY TO START</span></span></div>
            <h1>Từ ngữ cảnh đến kết quả kiểm thử.</h1>
            <p>Nhập URL website và mô tả điều bạn muốn kiểm tra. TestAgent đọc giao diện để tạo test; tài liệu, repository và API là ngữ cảnh bổ sung nếu có.</p>
            <button className="button button-primary welcome-action" onClick={() => setCreateOpen(true)}>Tạo dự án đầu tiên <Icon name="arrow" size={18} /></button>
          </div>
          <div className="welcome-steps"><span className="steps-label">BẮT ĐẦU <span>/</span> 03 BƯỚC</span><ol className="welcome-flow" aria-label="Các bước bắt đầu">
            <li><span className="flow-number">01</span><span className="flow-icon"><Icon name="folder" /></span><span className="flow-copy"><strong>Tạo dự án</strong><small>Đặt môi trường và đích kiểm thử</small></span></li>
            <li><span className="flow-number">02</span><span className="flow-icon"><Icon name="bolt" /></span><span className="flow-copy"><strong>Kết nối tài khoản AI</strong><small>Chọn provider và model muốn dùng</small></span></li>
            <li><span className="flow-number">03</span><span className="flow-icon"><Icon name="spark" /></span><span className="flow-copy"><strong>Giao việc cho agent</strong><small>Tạo test, phân tích và báo cáo</small></span></li>
          </ol></div>
        </div> : <>
          <div className="page-header"><div><div className="eyebrow">PROJECT <span className="eyebrow-separator">/</span> {project.environment.toUpperCase()} <span className="eyebrow-separator">/</span> {view.toUpperCase()}</div><h1>{view === 'overview' ? project.name : NAV.find(item => item.id === view)?.label}</h1><p>{view === 'overview' ? 'Trung tâm điều phối kiểm thử và theo dõi chất lượng.' : view === 'sources' ? 'Ngữ cảnh bổ sung để AI hiểu hệ thống hơn. Nạp nguồn là tùy chọn khi test website.' : view === 'tests' ? 'Xem, lọc và chạy những trường hợp kiểm thử đã tạo.' : 'Theo dõi lượt chạy, kết quả và bằng chứng.'}</p></div><div className="project-tools">{project.base_url && <a className="project-link" href={project.base_url} target="_blank" rel="noreferrer"><Icon name="server" size={15} />{new URL(project.base_url).host}<Icon name="external" size={14} /></a>}{view === 'overview' && <button className="button button-secondary" onClick={() => navigate('sources')}><Icon name="plus" size={16} /> Nạp nguồn (tùy chọn)</button>}<button className="button button-secondary settings-button" onClick={openSettings}><Icon name="settings" size={16} /><span>Cấu hình</span></button></div></div>

          {view === 'overview' && <>
            {setupDone < 2 && <section className="readiness-panel" aria-label="Thiết lập dự án">
              <div className="readiness-intro">
                <span className="eyebrow">PROJECT READINESS</span>
                <h2>Chuẩn bị kiểm thử website.</h2>
                <p>Kết nối AI và đặt URL website. Bạn có thể tạo test từ yêu cầu; tài liệu và repository là ngữ cảnh bổ sung tùy chọn.</p>
                <div className="readiness-progress" aria-label={`${setupDone} trên 2 bước hoàn tất`}><span style={{ width: `${setupDone / 2 * 100}%` }} /></div>
                <small>{setupDone} / 2 bước hoàn tất</small>
              </div>
              <div className="readiness-steps">
                <button className={`readiness-step ${modelReady ? 'done' : ''}`} onClick={() => navigate('ai')}><span className="step-indicator">{modelReady ? <Icon name="check" size={16} /> : '01'}</span><span><strong>Kết nối mô hình AI</strong><small>{modelReady ? aiState?.selection?.model : 'Đăng nhập provider và chọn model'}</small></span><Icon name="chevron" size={17} /></button>
                <button className={`readiness-step ${project.base_url ? 'done' : ''}`} onClick={openSettings}><span className="step-indicator">{project.base_url ? <Icon name="check" size={16} /> : '02'}</span><span><strong>Đặt URL website</strong><small>{project.base_url ? new URL(project.base_url).host : 'Để AI đọc trang và chạy browser/API test'}</small></span><Icon name="chevron" size={17} /></button>
                <button className={`readiness-step ${sources.length ? 'done' : ''}`} onClick={() => navigate('sources')}><span className="step-indicator"><Icon name="plus" size={16} /></span><span><strong>Nạp nguồn (tùy chọn)</strong><small>{sources.length ? `${sources.length} nguồn bổ sung` : 'Thêm tài liệu hoặc repository nếu có'}</small></span><Icon name="chevron" size={17} /></button>
              </div>
            </section>}
            {hasProjectData && <section className="metric-grid" aria-label="Chỉ số dự án">
              <div className="metric"><span>Nguồn dữ liệu</span><strong>{metrics.sourceCount}</strong><small>Tài liệu · mã nguồn · API</small></div>
              <div className="metric"><span>Test cases</span><strong>{metrics.testCount}</strong><small>{executable.length} có thể chạy</small></div>
              <div className="metric"><span>Truy vết nguồn</span><strong>{metrics.coverage}%</strong><small>{coverage?.sources_with_tests || 0}/{coverage?.source_count || 0} nguồn được gắn test</small></div>
              <div className="metric"><span>Pass rate gần nhất</span><strong>{metrics.passRate === null ? '—' : `${metrics.passRate}%`}</strong><small>{latestRun ? date(latestRun.requested_at) : 'Chưa có lượt chạy'}</small></div>
            </section>}

            <section className="workspace-grid">
              <div className="panel ask-panel">
                <div className="panel-title"><div className="panel-icon accent"><Icon name="spark" /></div><div><span className="eyebrow">AGENT WORKBENCH</span><h2>Giao việc cho TestAgent</h2><p>Mô tả mục tiêu để AI chọn agent phù hợp, hoặc chọn kỹ năng trực tiếp.</p></div></div>
                <form onSubmit={submitPrompt}>
                  {usesAi ? <AiPicker state={aiState} busy={aiBusy} onSelect={selectAi} onConnect={() => navigate('ai')} /> : <p className="execution-note">Thực thi automation đã lưu bằng Playwright/API runner. Không cần gọi AI cho lượt chạy này.</p>}
                  <div className="agent-selector">
                    <label htmlFor="agent-function">Kỹ năng agent</label>
                    <select id="agent-function" value={selectedFunction} onChange={event => { setSelectedFunction(event.target.value); setAgentCaseIds([]); setSelectedRunId(''); }}>
                      {skills.filter(skill => skill.mode === 'orchestration').map(skill => <option key={skill.id} value={skill.id}>{skill.label}</option>)}
                      {(['automation', 'diagnostics', 'context'] as const).map(category => <optgroup key={category} label={{ automation: 'Automation test', diagnostics: 'Phân tích lỗi & báo cáo', context: 'Ngữ cảnh & mở rộng' }[category]}>{skills.filter(skill => skill.mode !== 'orchestration' && (skill.category || (skill.mode === 'test_cases' ? 'automation' : 'context')) === category).map(skill => <option key={skill.id} value={skill.id}>{skill.label}</option>)}</optgroup>)}
                    </select>
                    <p>{selectedSkill?.description || 'Đang tải danh sách agent...'}</p>
                    {selectedSkill && <small className="skill-path"><Icon name="file" size={13} /> Skill: <code>{selectedSkill.file}</code></small>}
                  </div>
                  {autoRouting && <div className="agent-selector"><label htmlFor="agent-mode">Cách điều phối</label><select id="agent-mode" value={agentMode} onChange={event => setAgentMode(event.target.value as 'auto' | 'single')}><option value="auto">Tự động chia việc khi cần</option><option value="single">Chạy một agent</option></select><p>AI có thể giao tối đa 3 phần phân tích độc lập cho sub-agent. Mỗi phần thêm một lượt gọi model.</p></div>}
                  {selectedSkill?.requires === 'run' && <div className="agent-selector run-picker"><label htmlFor="agent-run">Lượt chạy</label><select id="agent-run" value={selectedRunId || finishedRuns[0]?.id || ''} onChange={event => setSelectedRunId(event.target.value)}><option value="" disabled>Chọn lượt chạy</option>{finishedRuns.map(run => <option key={run.id} value={run.id}>#{run.id.slice(0, 8)} · {date(run.requested_at)}</option>)}</select></div>}
                  {autoRouting && finishedRuns.length > 0 && <div className="agent-selector run-picker"><label htmlFor="agent-run">Lượt chạy tham chiếu (tùy chọn)</label><select id="agent-run" value={selectedRunId} onChange={event => setSelectedRunId(event.target.value)}><option value="">Dùng lượt gần nhất khi cần phân tích</option>{finishedRuns.map(run => <option key={run.id} value={run.id}>#{run.id.slice(0, 8)} · {date(run.requested_at)}</option>)}</select></div>}
                  {(selectedSkill?.requires === 'cases' || (autoRouting && tests.length > 0)) && <fieldset className="agent-case-picker"><legend>{autoRouting ? 'Test cases tham chiếu (tùy chọn)' : 'Test cases cho agent'} ({agentCaseIds.length}/{selectedSkill?.max_cases || 30})</legend><div>{tests.filter(test => usesAi || canRun(test)).map(test => <label key={test.id}><input type="checkbox" checked={agentCaseIds.includes(test.id)} disabled={!usesAi && activeCaseIds.has(test.id)} onChange={() => setAgentCaseIds(current => current.includes(test.id) ? current.filter(id => id !== test.id) : [...current, test.id])} /><span>{test.title}</span></label>)}</div>{!tests.length && <p>Chưa có test case. Tạo kịch bản trước.</p>}</fieldset>}
                  {browserWorkflow && <div className="agent-selector"><label htmlFor="execution-mode">{autoRouting ? 'Thực thi test' : 'Sau khi tạo automation'}</label><select id="execution-mode" value={executionMode} onChange={event => setExecutionMode(event.target.value as 'generate' | 'run')}><option value="generate">Xem test trước, chọn chạy sau</option><option value="run">{autoRouting ? 'Cho phép chạy test theo yêu cầu' : 'Tạo và chạy ngay'}</option></select><p>{autoRouting ? 'AI chọn agent theo mục tiêu và ngữ cảnh dự án. Nếu cần tạo automation, agent sẽ quan sát website; test chỉ chạy theo chế độ bạn chọn.' : 'Agent quan sát và thao tác trên website để xác định locator và kết quả. Lượt chạy xác nhận test được ghi riêng.'}</p></div>}
                  {(!usesAi || (browserWorkflow && executionMode === 'run')) && <RunOptions mode={runMode} workers={workers} onMode={setRunMode} onWorkers={setWorkers} />}
                  <label className="prompt-label" htmlFor="task-prompt">Yêu cầu của bạn</label>
                  <textarea id="task-prompt" value={prompt} onChange={e => setPrompt(e.target.value)} placeholder={selectedSkill?.id === 'report' ? 'Ví dụ: Viết báo cáo QA, nêu các lỗi chính và hành động tiếp theo...' : selectedSkill?.id === 'repo_under' ? 'Ví dụ: Phân tích kiến trúc repository và xác định các điểm cần test...' : !usesAi ? 'Ví dụ: Chạy các case đã chọn và lưu kết quả từng case.' : 'Ví dụ: Test luồng đăng nhập, thêm sản phẩm vào giỏ; dùng tài khoản test demo / mật khẩu...'} rows={4} />
                  <div className="composer-footer"><span>{autoRouting ? 'Mô tả mục tiêu; agent phù hợp được chọn tự động.' : browserWorkflow && project.base_url ? 'Lên kịch bản → quan sát → tạo test → chọn chạy. Nguồn bổ sung là tùy chọn.' : project.base_url ? 'Website và nguồn bổ sung nếu có.' : 'Nguồn dữ liệu là tùy chọn.'}</span><button className="button button-primary" disabled={!!busy || (usesAi && (aiBusy || !modelReady)) || !prompt.trim() || !skillInputReady || !selectedSkill} type="submit">{busy === 'task' ? 'Đang gửi...' : 'Gửi cho agent'}<Icon name="arrow" size={17} /></button></div>
                </form>
                {(!skillInputReady || (usesAi && modelReady === false)) && <div className="inline-hint"><strong>Để gửi yêu cầu:</strong>{!skillInputReady && <span> {selectedSkill?.requires === 'cases' ? 'Chọn số case phù hợp trong danh sách trên.' : selectedSkill?.requires === 'code' ? 'Kỹ năng này cần mã nguồn để phân tích: nhập repository hoặc ZIP.' : 'Chạy test và đợi lượt chạy hoàn tất.'}</span>}{usesAi && modelReady === false && <span> Đăng nhập và chọn model trong <button className="text-button" onClick={() => navigate('ai')}>Kết nối AI</button>.</span>}</div>}
              </div>
              <div className="panel activity-panel"><div className="section-heading"><div><h2>Hoạt động gần đây</h2><p>Nhấn vào tác vụ để xem kết quả agent</p></div></div>{tasks.length ? <div className="activity-list">{tasks.slice(0, 7).map(task => <button key={task.id} className="activity-item activity-button" onClick={() => setSelectedTaskId(task.id)}><span className="activity-symbol"><Icon name="spark" size={16} /></span><div><strong>{task.prompt}</strong><small>{skills.find(skill => skill.id === task.intent)?.label || task.intent} · {date(task.created_at)}</small><TaskCaption summary={task.summary} />{task.error && <small className="error-text">{task.error}</small>}</div><Status value={task.status} /></button>)}</div> : <Empty icon="activity" title="Chưa có hoạt động" description="Tác vụ của bạn sẽ xuất hiện tại đây." />}</div>
            </section>
            {tests.length > 0 && <section className="panel recent-panel"><div className="section-heading"><div><h2>Test cases mới</h2><p>Kiểm tra các trường hợp vừa được tạo</p></div><button className="text-button" onClick={() => navigate('tests')}>Xem tất cả <Icon name="arrow" size={15} /></button></div><TestTable tests={tests.slice(0, 5)} onSelect={setSelectedCase} /></section>}
          </>}

          {view === 'sources' && <div className="source-layout">
            <section className="panel">
              <div className="section-heading"><div><h2>Nạp nguồn dữ liệu</h2><p>Hỗ trợ tài liệu, OpenAPI, mã nguồn và UI.</p></div></div>
              <div className="upload-options">
                <button className="upload-card" onClick={() => { setUploadKind('documents'); fileInput.current?.click(); }} disabled={!!busy}><span className="upload-icon"><Icon name="upload" /></span><strong>Tài liệu</strong><small>PDF, DOCX, TXT, MD, CSV, XLSX</small></button>
                <button className="upload-card" onClick={() => { setUploadKind('openapi'); fileInput.current?.click(); }} disabled={!!busy}><span className="upload-icon"><Icon name="code" /></span><strong>OpenAPI</strong><small>JSON hoặc YAML specification</small></button>
                <button className="upload-card" onClick={() => { setUploadKind('repositories/zip'); fileInput.current?.click(); }} disabled={!!busy}><span className="upload-icon"><Icon name="layers" /></span><strong>Source ZIP</strong><small>Repository dạng .zip</small></button>
              </div>
              <input ref={fileInput} type="file" className="sr-only" accept={uploadKind === 'repositories/zip' ? '.zip' : uploadKind === 'openapi' ? '.json,.yaml,.yml' : '.pdf,.docx,.txt,.md,.csv,.xlsx,.json,.yaml,.yml'} onChange={e => { const file = e.target.files?.[0]; if (file) void upload(file, uploadKind); e.target.value = ''; }} />
              <div className="divider"><span>hoặc nhập repository</span></div>
              <form className="repo-form" onSubmit={e => { e.preventDefault(); void perform('repo', () => api.importRepo(projectId, repoLocation), 'Đã nạp repository.'); setRepoLocation(''); }}><label htmlFor="repo-location">Git HTTPS URL hoặc đường dẫn trong IMPORT_ROOT</label><div><input id="repo-location" value={repoLocation} onChange={e => setRepoLocation(e.target.value)} placeholder="https://github.com/org/repo.git" required /><button className="button button-secondary" disabled={!!busy} type="submit">Nhập</button></div></form>
              <div className="divider"><span>hoặc quét giao diện</span></div>
              <form className="repo-form" onSubmit={e => { e.preventDefault(); void perform('inspect', () => api.inspectUi(projectId, inspectPath), 'Đã lưu thông tin phần tử UI.'); }}><label htmlFor="inspect-path">Đường dẫn trang trên Base URL</label><div><input id="inspect-path" value={inspectPath} onChange={e => setInspectPath(e.target.value)} placeholder="/login" required /><button className="button button-secondary" disabled={!!busy || !project.base_url} type="submit">Quét UI</button></div></form>
            </section>
            <section className="panel"><div className="section-heading"><div><h2>Nguồn đã nạp</h2><p>{sources.length} nguồn trong kho tri thức</p></div></div>{sources.length ? <div className="source-list">{sources.map(source => <div key={source.id} className="source-item"><span className={`source-type type-${source.kind}`}>{source.kind === 'code' ? 'CODE' : source.kind === 'openapi' ? 'API' : source.kind === 'ui' ? 'UI' : 'DOC'}</span><div><strong title={source.name}>{source.name}</strong><small>{date(source.created_at)}</small></div></div>)}</div> : <Empty icon="layers" title="Chưa có nguồn bổ sung" description="Bạn vẫn có thể test website từ URL và yêu cầu. Thêm tài liệu hoặc mã nguồn khi muốn AI hiểu hệ thống hơn." />}</section>
          </div>}

          {view === 'tests' && <section className="panel table-panel">
            <div className="section-heading"><div><h2>Thư viện test cases</h2><p>{tests.length} case · {executable.length} sẵn sàng chạy · chọn từng case hoặc một nhóm</p></div><button className="button button-secondary" onClick={() => navigate('overview')}>Tạo test mới</button></div>
            {tests.length ? <>
              <div className="table-toolbar"><label className="search-field"><Icon name="search" size={17} /><span className="sr-only">Tìm test case</span><input value={testQuery} onChange={event => setTestQuery(event.target.value)} placeholder="Tìm test case..." /></label><label className="level-field"><span className="sr-only">Lọc cấp độ</span><select value={testLevel} onChange={event => setTestLevel(event.target.value)}><option value="all">Tất cả cấp độ</option>{[...new Set(tests.map(test => test.level))].map(level => <option key={level} value={level}>{level.toUpperCase()}</option>)}</select></label><span className="filter-count">{filteredTests.length} kết quả</span></div>
              {filteredTests.length ? <TestLibrary tests={filteredTests} total={tests.length} selected={selectedCaseIds} active={activeCaseIds} busy={!!busy} mode={runMode} workers={workers} onMode={setRunMode} onWorkers={setWorkers} onSelection={setSelectedCaseIds} onOpen={setSelectedCase} onRun={ids => void execute(ids)} onBuild={ids => assignCases('automation_builder', ids)} onReview={ids => assignCases('case_review', ids)} onOpenRun={id => void openRun(id)} /> : <Empty icon="search" title="Không tìm thấy test case" description="Thử một từ khóa hoặc cấp độ khác." />}
            </> : <Empty icon="flask" title="Chưa có test case" description="Nhập URL và mục tiêu tại Tổng quan để agent tạo kịch bản. Nguồn dữ liệu là tùy chọn." action={<button className="button button-secondary" onClick={() => navigate('overview')}>Tạo test case</button>} />}
          </section>}

          {view === 'runs' && <section className="panel table-panel"><div className="section-heading"><div><h2>Lượt chạy</h2><p>Kết quả và bằng chứng theo từng lượt thực thi</p></div></div>{runs.length ? <div className="table-wrap"><table><thead><tr><th>Lượt chạy</th><th>Thời gian</th><th>Kết quả</th><th>Trạng thái</th><th></th></tr></thead><tbody>{runs.map(run => { const summary = typeof run.summary === 'string' ? JSON.parse(run.summary) : run.summary; return <tr key={run.id}><td><button className="row-link" onClick={() => openRun(run.id)}>#{run.id.slice(0, 8)}</button></td><td>{date(run.requested_at)}</td><td>{summary.counts ? `${summary.counts.PASS || 0} pass · ${(summary.counts.FAIL || 0) + (summary.counts.ERROR || 0) + (summary.counts.TIMEOUT || 0)} failed` : 'Đang xử lý'}</td><td><Status value={run.status} /></td><td><button className="icon-button" aria-label={`Xem lượt chạy ${run.id}`} onClick={() => openRun(run.id)}><Icon name="arrow" size={16} /></button></td></tr>; })}</tbody></table></div> : <Empty icon="activity" title="Chưa có lượt chạy" description="Chạy test cases từ thư viện để xem kết quả ở đây." action={tests.length > 0 ? <button className="button button-secondary" onClick={() => navigate('tests')}>Xem test cases</button> : undefined} />}</section>}
        </>}
      </main>
    </div>

    {createOpen && <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) setCreateOpen(false); }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="create-title"><div className="modal-head"><div><span className="eyebrow">THIẾT LẬP</span><h2 id="create-title">Dự án mới</h2></div><button className="icon-button" aria-label="Đóng" onClick={() => setCreateOpen(false)}><Icon name="close" /></button></div><p className="modal-intro">Mỗi dự án giữ riêng nguồn dữ liệu, test cases và lịch sử chạy.</p><form onSubmit={createProject} className="stack-form"><label>Tên dự án<input value={name} onChange={e => setName(e.target.value)} minLength={2} maxLength={120} placeholder="Ví dụ: Shop App" required autoFocus /></label><label>Base URL <span className="optional">(cần khi chạy test)</span><input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} type="url" placeholder="https://staging.example.com" /></label><label>Môi trường<select value={environment} onChange={e => setEnvironment(e.target.value)}><option value="local">Local</option><option value="development">Development</option><option value="staging">Staging</option><option value="production">Production</option></select></label><div className="modal-actions"><button type="button" className="button button-secondary" onClick={() => setCreateOpen(false)}>Hủy</button><button type="submit" className="button button-primary" disabled={!!busy}>Tạo dự án</button></div></form></section></div>}

    {settingsOpen && <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) setSettingsOpen(false); }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="settings-title"><div className="modal-head"><div><span className="eyebrow">THIẾT LẬP</span><h2 id="settings-title">Cấu hình dự án</h2></div><button className="icon-button" aria-label="Đóng" onClick={() => setSettingsOpen(false)}><Icon name="close" /></button></div><p className="modal-intro">Base URL là địa chỉ đích cho browser và API test.</p><form onSubmit={saveSettings} className="stack-form"><label>Base URL<input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} type="url" placeholder="https://staging.example.com" /></label><label>Môi trường<select value={environment} onChange={e => setEnvironment(e.target.value)}><option value="local">Local</option><option value="development">Development</option><option value="staging">Staging</option><option value="production">Production</option></select></label><div className="modal-actions"><button type="button" className="button button-secondary" onClick={() => setSettingsOpen(false)}>Hủy</button><button type="submit" className="button button-primary" disabled={!!busy}>Lưu thay đổi</button></div></form></section></div>}

    {selectedTask && <div className="drawer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setSelectedTaskId(null); }}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="task-title">
        <div className="drawer-head"><span className="eyebrow">AGENT TASK · {selectedTask.id.slice(0, 8)}</span><button className="icon-button" aria-label="Đóng" onClick={() => setSelectedTaskId(null)}><Icon name="close" /></button></div>
        <h2 id="task-title">{skills.find(skill => skill.id === selectedTask.intent)?.label || selectedTask.intent}</h2>
        <div className="task-meta"><Status value={selectedTask.status} /><span>{date(selectedTask.created_at)}</span></div>
        {selectedTask.ai_provider && <div className="skill-reference"><span>AI đã sử dụng</span><code>{selectedTask.ai_provider} / {selectedTask.ai_model}{selectedTask.ai_effort ? ` · effort ${selectedTask.ai_effort}` : ''}</code></div>}
        <div className="skill-reference"><span>Skill được sử dụng</span><code>{selectedTask.skill_file || selectedTaskOutput?.skill_file || 'Tác vụ cũ'}</code></div>
        <section className="detail-section"><h3>Yêu cầu</h3><p>{selectedTask.prompt}</p></section>
        {selectedTask.orchestration?.function && <section className="detail-section"><h3>Điều phối</h3><p>Đã giao cho <strong>{skills.find(skill => skill.id === selectedTask.orchestration?.function)?.label || selectedTask.orchestration.function}</strong>.</p><p>{selectedTask.orchestration.reason}</p></section>}
        <SubAgentTasks tasks={selectedTask.sub_tasks || []} skills={skills} />
        {selectedTask.error && <div className="alert alert-error" role="alert">{selectedTask.error}</div>}
        {selectedTaskOutput && <>
          <TaskWorkflow output={selectedTaskOutput} busy={!!busy} onRun={ids => void execute(ids)} onOpenRun={id => { setSelectedTaskId(null); void openRun(id); }} />
          <section className="detail-section"><h3>Tóm tắt</h3><p>{selectedTaskOutput.summary}</p></section>
          {!!selectedTaskOutput.risks?.length && <DetailList title="Rủi ro" items={selectedTaskOutput.risks} />}
          {!!selectedTaskOutput.findings?.length && <section className="detail-section"><h3>Phát hiện</h3>{selectedTaskOutput.findings.map((finding, index) => <div className="finding-card" key={index}><div><strong>{finding.title}</strong><span className={`priority priority-${finding.severity}`}>{finding.severity}</span></div><p>{finding.detail}</p>{finding.evidence_ids.length > 0 && <small>Bằng chứng: {finding.evidence_ids.map(id => id.slice(0, 8)).join(', ')}</small>}</div>)}</section>}
          {!!selectedTaskOutput.recommendations?.length && <DetailList title="Đề xuất" items={selectedTaskOutput.recommendations} ordered />}
          {selectedTaskOutput.kind === 'test_cases' && !!selectedTaskOutput.case_count && <div className="drawer-actions"><button className="button button-primary" onClick={() => { setSelectedTaskId(null); setTestQuery(''); setTestLevel('all'); setSelectedCaseIds(selectedTaskOutput.case_ids || []); navigate('tests'); }}>Xem {selectedTaskOutput.case_count} test cases <Icon name="arrow" size={16} /></button></div>}
          {selectedTask.intent === 'report' && <div className="drawer-actions"><a className="button button-secondary" href={`/api/agent/tasks/${selectedTask.id}/report`}>Tải report Markdown <Icon name="external" size={15} /></a></div>}
          {selectedTaskOutput.run_id && <p className="muted">Lượt chạy tham chiếu: #{selectedTaskOutput.run_id.slice(0, 8)}</p>}
        </>}
        {!selectedTaskOutput && !selectedTask.error && <p className="muted task-pending">Agent đang xử lý. Kết quả sẽ tự cập nhật.</p>}
      </aside>
    </div>}

    {selectedCase && <div className="drawer-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) setSelectedCase(null); }}><aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="case-title"><div className="drawer-head"><span className="eyebrow">TEST CASE · {selectedCase.id.slice(0, 8)}</span><button className="icon-button" aria-label="Đóng" onClick={() => setSelectedCase(null)}><Icon name="close" /></button></div><h2 id="case-title">{selectedCase.title}</h2><div className="tag-row"><span className="tag">{selectedCase.level.toUpperCase()}</span><span className={`priority priority-${selectedCase.priority}`}>{selectedCase.priority}</span><span className="tag">{selectedCase.type}</span></div><DetailList title="Điều kiện" items={selectedCase.preconditions} /><DetailList title="Các bước" items={selectedCase.steps} ordered /><DetailList title="Kết quả mong đợi" items={selectedCase.expected} /><section className="detail-section"><h3>Nguồn tham chiếu</h3>{selectedCase.source_ids.length ? selectedCase.source_ids.map(id => <div key={id} className="reference">{sources.find(item => item.id === id)?.name || id}</div>) : <p className="muted">Chưa có nguồn tham chiếu.</p>}</section>{selectedCase.api_request && <section className="detail-section"><h3>API request</h3><pre>{JSON.stringify(selectedCase.api_request, null, 2)}</pre></section>}{selectedCase.automation && <section className="detail-section"><h3>Automation DSL</h3><pre>{JSON.stringify(selectedCase.automation, null, 2)}</pre><button className="button button-secondary" onClick={() => openCode(selectedCase)} disabled={!!busy}><Icon name="code" size={16} /> Xem Playwright code</button></section>}{selectedCase.unit_test_code && <section className="detail-section"><h3>Unit test code</h3><pre>{selectedCase.unit_test_code}</pre></section>}<div className="drawer-actions">{canRun(selectedCase) ? <button className="button button-primary" onClick={() => execute([selectedCase.id])} disabled={!!busy || activeCaseIds.has(selectedCase.id)}><Icon name="play" size={16} /> {activeCaseIds.has(selectedCase.id) ? 'Test đang chạy' : 'Chạy test này'}</button> : <><p className="muted">{selectedCase.readiness?.reason || 'Test này chưa có automation.'}</p><button className="button button-primary" disabled={!!busy} onClick={() => assignCases('automation_builder', [selectedCase.id])}>Giao agent tạo automation</button></>}</div></aside></div>}

    {selectedRun && <div className="drawer-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) setSelectedRun(null); }}><aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="run-title"><div className="drawer-head"><span className="eyebrow">TEST RUN · {selectedRun.id.slice(0, 8)}</span><button className="icon-button" aria-label="Đóng" onClick={() => setSelectedRun(null)}><Icon name="close" /></button></div><h2 id="run-title">Kết quả lượt chạy</h2>{selectedRun.summary.error && <div className="alert alert-error" role="alert">{selectedRun.summary.error}</div>}<div className="run-meta"><Status value={selectedRun.status} /><span>{date(selectedRun.started_at)}</span></div><p className="run-progress" role="status">{selectedRun.summary.completed ?? selectedRun.results?.length ?? 0}/{selectedRun.summary.total || 0} case hoàn tất · {selectedRun.summary.mode === 'parallel' ? `Song song, tối đa ${selectedRun.summary.workers || 1} case` : 'Tuần tự'}</p><div className="run-summary"><div><strong>{selectedRun.summary.counts?.PASS || 0}</strong><span>PASS</span></div><div><strong>{selectedRun.summary.counts?.FAIL || 0}</strong><span>FAIL</span></div><div><strong>{(selectedRun.summary.counts?.ERROR || 0) + (selectedRun.summary.counts?.TIMEOUT || 0)}</strong><span>ERROR</span></div></div><div className="detail-section"><h3>Chi tiết</h3>{selectedRun.results?.map(result => <div className="result-card" key={result.id}><div><strong>{result.title}</strong><Status value={result.status} /></div><small>{result.duration_ms} ms · {result.failure_type || 'Không có lỗi'}</small><p>{result.message}</p>{result.artifacts.map(filename => <a key={filename} href={`/api/runs/${selectedRun.id}/artifacts/${encodeURIComponent(filename)}`} target="_blank" rel="noreferrer">{filename} <Icon name="external" size={13} /></a>)}</div>)}{!selectedRun.results?.length && <p className="muted">Lượt chạy chưa có kết quả.</p>}</div>{['COMPLETED', 'FAILED'].includes(selectedRun.status) && <div className="drawer-actions run-followup"><button className="button button-secondary" onClick={() => assignRun('defect_analysis', selectedRun)}>Phân tích kết quả</button>{selectedRun.results?.some(result => result.status !== 'PASS') && <><button className="button button-primary" onClick={() => assignRun('repair_automation', selectedRun)}>Giao agent sửa automation</button><button className="text-button" disabled={!!busy} onClick={() => execute(selectedRun.results!.filter(result => result.status !== 'PASS').map(result => result.test_case_id))}>Chạy lại case lỗi</button></>}</div>}<a className="button button-secondary report-link" href={`/api/reports/${selectedRun.id}`} target="_blank" rel="noreferrer">Mở báo cáo JSON <Icon name="external" size={15} /></a></aside></div>}

    {code && <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) setCode(null); }}><section className="modal code-modal" role="dialog" aria-modal="true" aria-labelledby="code-title"><div className="modal-head"><h2 id="code-title">Playwright test</h2><button className="icon-button" aria-label="Đóng" onClick={() => setCode(null)}><Icon name="close" /></button></div><pre>{code}</pre><div className="modal-actions"><button className="button button-secondary" onClick={() => navigator.clipboard.writeText(code).then(() => setNotice('Đã sao chép code.')).catch(() => setError('Không thể sao chép code.'))}>Sao chép</button></div></section></div>}
  </div>;
}

function TestTable({ tests, onSelect }: { tests: TestCase[]; onSelect: (test: TestCase) => void }) {
  return <div className="table-wrap"><table><thead><tr><th>Test case</th><th>Loại</th><th>Ưu tiên</th><th>Thực thi</th><th></th></tr></thead><tbody>{tests.map(test => <tr key={test.id}><td><button className="row-link" onClick={() => onSelect(test)}>{test.title}</button><small className="table-subtitle">{test.id.slice(0, 8)} · {test.level.toUpperCase()}</small></td><td>{test.type}</td><td><span className={`priority priority-${test.priority}`}>{test.priority}</span></td><td>{test.automation ? 'Browser' : test.api_request ? 'API' : test.unit_test_code ? 'Code artifact' : 'Thủ công'}</td><td><button className="icon-button" aria-label={`Xem ${test.title}`} onClick={() => onSelect(test)}><Icon name="arrow" size={16} /></button></td></tr>)}</tbody></table></div>;
}

function DetailList({ title, items, ordered = false }: { title: string; items: string[]; ordered?: boolean }) {
  if (!items.length) return null;
  const List = ordered ? 'ol' : 'ul';
  return <section className="detail-section"><h3>{title}</h3><List>{items.map((item, i) => <li key={i}>{item}</li>)}</List></section>;
}
