import type { AgentSkill, Task, TaskOutput } from './api';

export function taskStatusLabel(value: string) {
  const names: Record<string, string> = { ROUTING: 'Đang chọn agent', COLLABORATING: 'Đang chia việc', ANALYZING: 'Đang phân tích', QUEUED: 'Đang đợi', PLANNING: 'Lên kịch bản', EXPLORING: 'Quan sát website', NEEDS_INPUT: 'Cần thông tin', READY: 'Sẵn sàng chạy' };
  return names[value] || value.replaceAll('_', ' ');
}

export function SubAgentTasks({ tasks, skills }: { tasks: Task[]; skills: AgentSkill[] }) {
  if (!tasks.length) return null;
  const complete = tasks.filter(task => task.status === 'COMPLETED').length;
  return <section className="detail-section sub-agent-section" aria-label="Các phần việc của sub-agent">
    <h3>Phân tích từ sub-agent <small aria-live="polite">{complete}/{tasks.length} hoàn tất</small></h3>
    <p>Các phần việc độc lập được chuyển về agent chính để tổng hợp.</p>
    {tasks.map(task => {
      let output: TaskOutput | null = null;
      try { output = JSON.parse(task.summary) as TaskOutput; } catch { /* Output may still be pending. */ }
      return <details key={task.id} className="sub-agent-card">
        <summary><span><strong>{skills.find(skill => skill.id === task.intent)?.label || task.intent}</strong><small>{task.prompt}</small></span><span className={`status status-${task.status.toLowerCase()}`}>{taskStatusLabel(task.status)}</span></summary>
        <div className="sub-agent-detail"><p>{task.prompt}</p>
          {task.error && <p className="error-text" role="status">{task.error}</p>}
          {output ? <><p>{output.summary}</p>{!!output.findings?.length && <ul>{output.findings.map((finding, index) => <li key={index}><strong>{finding.title}</strong><p>{finding.detail}</p></li>)}</ul>}{!!output.recommendations?.length && <ul>{output.recommendations.map((item, index) => <li key={index}>{item}</li>)}</ul>}</> : !task.error && <p role="status">Kết quả sẽ cập nhật khi phần việc hoàn tất.</p>}
        </div>
      </details>;
    })}
  </section>;
}

const phases = [
  { id: 'PLANNING', label: 'Lên kịch bản' },
  { id: 'EXPLORING', label: 'Quan sát và thao tác' },
  { id: 'GENERATING', label: 'Hoàn thiện test' },
  { id: 'RUNNING', label: 'Chạy Playwright' },
];

export function TaskCaption({ summary }: { summary: string }) {
  let output: TaskOutput;
  try { output = JSON.parse(summary) as TaskOutput; } catch { return null; }
  if (output.execution?.counts) return <small className={output.execution.status === 'FAILED' ? 'error-text' : 'task-result-caption'}>{output.execution.counts.PASS || 0} PASS · {(output.execution.counts.FAIL || 0) + (output.execution.counts.ERROR || 0) + (output.execution.counts.TIMEOUT || 0)} không đạt{output.manual_count ? ` · ${output.manual_count} chưa tự động hóa` : ''}</small>;
  if (output.workflow) return <small>{output.blocked_reason || output.summary}</small>;
  return null;
}

export default function TaskWorkflow({ output, onOpenRun, onRun, busy }: { output: TaskOutput; onOpenRun: (id: string) => void; onRun: (ids: string[]) => void; busy: boolean }) {
  if (!output.workflow) return null;
  const index = phases.findIndex(phase => phase.id === output.phase);
  const finished = Boolean(output.execution?.counts);
  const ready = output.phase === 'READY';
  return <section className="task-workflow" aria-label="Tiến trình test automation">
    {output.workflow === 'ui_automation' && <ol className="workflow-phases">{phases.map((phase, position) => <li key={phase.id} className={finished || position < index || (ready && position < 3) ? 'phase-done' : position === index ? 'phase-current' : ''} aria-current={position === index ? 'step' : undefined}><span>{finished || position < index || (ready && position < 3) ? '✓' : position + 1}</span>{phase.label}</li>)}</ol>}
    {ready && <div className="task-execution task-execution-completed"><strong>Đã tạo test · Chưa chạy xác nhận</strong><p>{output.executable_ids?.length || 0} case có automation. Xem các bước và kết quả mong đợi trước khi chạy.</p>{!!output.executable_ids?.length && <button className="button button-primary" disabled={busy} onClick={() => onRun(output.executable_ids!)}>Chạy {output.executable_ids.length} test vừa tạo</button>}{!!output.manual_count && <p>{output.manual_count} case còn thiếu automation hoặc thông tin.</p>}</div>}
    {output.execution && <div className={`task-execution task-execution-${output.execution.status.toLowerCase()}`}>
      <strong>{finished ? 'Kết quả Playwright' : 'Playwright đang chạy kịch bản'}</strong>
      {finished && <div className="execution-counts"><span>{output.execution.counts?.PASS || 0} PASS</span><span>{output.execution.counts?.FAIL || 0} FAIL</span><span>{(output.execution.counts?.ERROR || 0) + (output.execution.counts?.TIMEOUT || 0)} ERROR</span></div>}
      {!!output.manual_count && <p>{output.manual_count} kịch bản chưa tự động hóa; cần bổ sung thông tin.</p>}
      {output.run_id && <button className="button button-primary" onClick={() => onOpenRun(output.run_id!)}>Xem kết quả, video và trace</button>}
    </div>}
    {output.blocked_reason && <div className="alert task-blocked" role="status"><strong>Cần bổ sung thông tin</strong><p>{output.blocked_reason}</p></div>}
    {!!output.scenarios?.length && <div className="detail-section"><h3>Kịch bản test</h3><ol>{output.scenarios.map((scenario, i) => <li key={i}>{scenario}</li>)}</ol></div>}
    {!!output.activity?.length && <details className="workflow-activity"><summary>Các bước agent đã thực hiện ({output.activity.length})</summary><ol>{output.activity.map((entry, i) => <li key={i}><p>{entry.message}</p>{entry.url && <small>{entry.url}</small>}</li>)}</ol></details>}
  </section>;
}
