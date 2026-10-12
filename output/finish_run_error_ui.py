from pathlib import Path

p = Path('web/src/api.ts')
s = p.read_text(encoding='utf-8').replace('summary: { total?: number; completed?: number;', 'summary: { error?: string; total?: number; completed?: number;')
p.write_text(s, encoding='utf-8')
p = Path('web/src/App.tsx')
s = p.read_text(encoding='utf-8')
old = '<div className="run-meta"><Status value={selectedRun.status}'
new = '{selectedRun.summary.error && <div className="alert alert-error" role="alert">{selectedRun.summary.error}</div>}<div className="run-meta"><Status value={selectedRun.status}'
assert old in s
p.write_text(s.replace(old, new, 1), encoding='utf-8')
