import { canRun, type TestCase, type RunMode } from './api';

export function RunOptions({ mode, workers, onMode, onWorkers }: { mode: RunMode; workers: number; onMode: (mode: RunMode) => void; onWorkers: (workers: number) => void }) {
  return <div className="run-options">
    <label>Cách chạy<select aria-label="Cách chạy" value={mode} onChange={event => onMode(event.target.value as RunMode)}><option value="sequential">Tuần tự</option><option value="parallel">Song song</option></select></label>
    {mode === 'parallel' && <label>Số test đồng thời<select aria-label="Số test đồng thời" value={workers} onChange={event => onWorkers(Number(event.target.value))}>{[1, 2, 3, 4].map(count => <option key={count} value={count}>{count}</option>)}</select></label>}
    <small>Mỗi case mở phiên riêng.{mode === 'parallel' ? ' Chọn các case có dữ liệu độc lập.' : ''}</small>
  </div>;
}

type Props = {
  tests: TestCase[]; total: number; selected: string[]; active: Set<string>; busy: boolean;
  mode: RunMode; workers: number; onMode: (mode: RunMode) => void; onWorkers: (workers: number) => void;
  onSelection: (ids: string[]) => void; onOpen: (test: TestCase) => void; onRun: (ids: string[]) => void;
  onBuild: (ids: string[]) => void; onReview: (ids: string[]) => void; onOpenRun: (id: string) => void;
};

export default function TestLibrary(props: Props) {
  const { tests, total, selected, active, busy, onSelection } = props;
  const ready = tests.filter(test => canRun(test) && !active.has(test.id));
  const picked = tests.filter(test => selected.includes(test.id));
  const runnable = picked.filter(test => canRun(test) && !active.has(test.id));
  const toggle = (id: string) => onSelection(selected.includes(id) ? selected.filter(value => value !== id) : [...selected, id]);
  const all = tests.length > 0 && tests.every(test => selected.includes(test.id));
  return <>
    <div className="suite-controls">
      <RunOptions mode={props.mode} workers={props.workers} onMode={props.onMode} onWorkers={props.onWorkers} />
      <div className="suite-actions">
        <span>{picked.length} đã chọn · {runnable.length} sẵn sàng chạy</span>
        <button className="button button-primary" disabled={busy || !runnable.length || runnable.length > 30} onClick={() => props.onRun(runnable.map(test => test.id))}>Chạy nhóm đã chọn ({runnable.length})</button>
        <button className="button button-secondary" disabled={busy || !ready.length || ready.length > 30} onClick={() => props.onRun(ready.map(test => test.id))}>Chạy tất cả đang lọc ({ready.length})</button>
        <button className="text-button" disabled={busy || !picked.length || picked.length > 20 || picked.some(test => active.has(test.id))} onClick={() => props.onBuild(picked.map(test => test.id))}>Tạo automation</button>
        <button className="text-button" disabled={busy || !picked.length || picked.length > 30} onClick={() => props.onReview(picked.map(test => test.id))}>Rà soát case</button>
      </div>
      {picked.length > runnable.length && <p className="suite-hint">{picked.length - runnable.length} case chưa sẵn sàng hoặc đang chạy. Xem lý do ở từng dòng; dùng Tạo automation cho case thủ công.</p>}
      {ready.length > 30 && <p className="suite-hint">Mỗi lượt chạy tối đa 30 case. Chọn một nhóm hoặc lọc thêm.</p>}
      {!ready.length && !!total && <p className="suite-hint">Chưa có case sẵn sàng trong bộ lọc này. Chọn case để bổ sung automation.</p>}
    </div>
    <div className="table-wrap"><table className="suite-table"><thead><tr>
      <th><input type="checkbox" aria-label="Chọn tất cả case đang lọc" checked={all} onChange={() => onSelection(all ? selected.filter(id => !tests.some(test => test.id === id)) : [...new Set([...selected, ...tests.map(test => test.id)])])} /></th>
      <th>Test case</th><th>Sẵn sàng chạy</th><th>Lần chạy gần nhất</th><th>Thao tác</th>
    </tr></thead><tbody>{tests.map(test => {
      const running = active.has(test.id);
      const ready = canRun(test);
      return <tr key={test.id} className={selected.includes(test.id) ? 'case-selected' : undefined}>
        <td><input type="checkbox" aria-label={`Chọn ${test.title}`} checked={selected.includes(test.id)} onChange={() => toggle(test.id)} /></td>
        <td><button className="row-link" onClick={() => props.onOpen(test)}>{test.title}</button><small className="table-subtitle">{test.id.slice(0, 8)} · {test.level.toUpperCase()} · {test.type}</small></td>
        <td><span className={`status status-${running ? 'running' : ready ? 'ready' : 'needs_input'}`}>{running ? 'Đang chạy' : ready ? test.automation ? 'Playwright · Sẵn sàng' : 'API · Sẵn sàng' : test.readiness?.status === 'manual' || !test.readiness ? 'Cần automation' : 'Cần bổ sung'}</span>{!ready && <small className="readiness-reason">{test.readiness?.reason || 'Chưa có automation để chạy.'}</small>}</td>
        <td>{test.last_status ? <button className={`status status-${test.last_status.toLowerCase()}`} onClick={() => test.last_run_id && props.onOpenRun(test.last_run_id)}>{test.last_status}</button> : <span className="muted">Chưa chạy</span>}</td>
        <td><div className="case-row-actions"><button className="button button-secondary" aria-label={`Chạy ${test.title}`} disabled={busy || running || !ready} onClick={() => props.onRun([test.id])}>Chạy</button>{!ready && <button className="text-button" aria-label={`Tạo automation cho ${test.title}`} disabled={busy} onClick={() => props.onBuild([test.id])}>Tạo automation</button>}</div></td>
      </tr>;
    })}</tbody></table></div>
  </>;
}
