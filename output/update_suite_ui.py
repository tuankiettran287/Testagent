from pathlib import Path

path = Path('web/src/App.tsx')
text = path.read_text(encoding='utf-8')
start = text.index("          {view === 'tests' &&")
end = text.index("          {view === 'runs' &&", start)
text = text[:start] + '''          {view === 'tests' && <section className="panel table-panel">
            <div className="section-heading"><div><h2>Thư viện test cases</h2><p>{tests.length} case · {executable.length} sẵn sàng chạy · chọn từng case hoặc một nhóm</p></div><button className="button button-secondary" onClick={() => navigate('overview')}>Tạo test mới</button></div>
            {tests.length ? <>
              <div className="table-toolbar"><label className="search-field"><Icon name="search" size={17} /><span className="sr-only">Tìm test case</span><input value={testQuery} onChange={event => setTestQuery(event.target.value)} placeholder="Tìm test case..." /></label><label className="level-field"><span className="sr-only">Lọc cấp độ</span><select value={testLevel} onChange={event => setTestLevel(event.target.value)}><option value="all">Tất cả cấp độ</option>{[...new Set(tests.map(test => test.level))].map(level => <option key={level} value={level}>{level.toUpperCase()}</option>)}</select></label><span className="filter-count">{filteredTests.length} kết quả</span></div>
              {filteredTests.length ? <TestLibrary tests={filteredTests} total={tests.length} selected={selectedCaseIds} active={activeCaseIds} busy={!!busy} mode={runMode} workers={workers} onMode={setRunMode} onWorkers={setWorkers} onSelection={setSelectedCaseIds} onOpen={setSelectedCase} onRun={ids => void execute(ids)} onBuild={ids => assignCases('automation_builder', ids)} onReview={ids => assignCases('case_review', ids)} onOpenRun={id => void openRun(id)} /> : <Empty icon="search" title="Không tìm thấy test case" description="Thử một từ khóa hoặc cấp độ khác." />}
            </> : <Empty icon="flask" title="Chưa có test case" description="Nhập URL và mục tiêu tại Tổng quan để agent tạo kịch bản. Nguồn dữ liệu là tùy chọn." action={<button className="button button-secondary" onClick={() => navigate('overview')}>Tạo test case</button>} />}
          </section>}

''' + text[end:]
old = '''{(selectedCase.automation || selectedCase.api_request) ? <button className="button button-primary" onClick={() => execute([selectedCase.id])} disabled={!!busy}><Icon name="play" size={16} /> Chạy test này</button> : <span className="muted">Test này cần được chạy thủ công hoặc tích hợp runner.</span>}'''
new = '''{canRun(selectedCase) ? <button className="button button-primary" onClick={() => execute([selectedCase.id])} disabled={!!busy || activeCaseIds.has(selectedCase.id)}><Icon name="play" size={16} /> {activeCaseIds.has(selectedCase.id) ? 'Test đang chạy' : 'Chạy test này'}</button> : <><p className="muted">{selectedCase.readiness?.reason || 'Test này chưa có automation.'}</p><button className="button button-primary" disabled={!!busy} onClick={() => assignCases('automation_builder', [selectedCase.id])}>Giao agent tạo automation</button></>}'''
assert old in text
text = text.replace(old, new, 1)
old = '''<div className="run-summary"><div>'''
new = '''<p className="run-progress" role="status">{selectedRun.summary.completed ?? selectedRun.results?.length ?? 0}/{selectedRun.summary.total || 0} case hoàn tất · {selectedRun.summary.mode === 'parallel' ? `Song song, tối đa ${selectedRun.summary.workers || 1} case` : 'Tuần tự'}</p><div className="run-summary"><div>'''
assert old in text
text = text.replace(old, new, 1)
old = '''<a className="button button-secondary report-link" href={`/api/reports/${selectedRun.id}`}'''
new = '''{['COMPLETED', 'FAILED'].includes(selectedRun.status) && <div className="drawer-actions run-followup"><button className="button button-secondary" onClick={() => assignRun('defect_analysis', selectedRun)}>Phân tích kết quả</button>{selectedRun.results?.some(result => result.status !== 'PASS') && <><button className="button button-primary" onClick={() => assignRun('repair_automation', selectedRun)}>Giao agent sửa automation</button><button className="text-button" disabled={!!busy} onClick={() => execute(selectedRun.results!.filter(result => result.status !== 'PASS').map(result => result.test_case_id))}>Chạy lại case lỗi</button></>}</div>}<a className="button button-secondary report-link" href={`/api/reports/${selectedRun.id}`}'''
assert old in text
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
