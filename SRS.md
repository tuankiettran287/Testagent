# SRS — TestAgent

Đặc tả yêu cầu và điều kiện vận hành cho phiên bản hiện có. Cập nhật: 05/10/2026.

Tài liệu này đặc tả **TestAgent**, không phải SRS nghiệp vụ của website được kiểm thử. README hướng dẫn cài/chạy; tài liệu thiết kế giải thích cách triển khai. Các khả năng chưa có được ghi riêng, không thuộc phạm vi nghiệm thu hiện tại.

## 1. Mục tiêu và người dùng

QA/tester cần chuyển mục tiêu và bằng chứng thành cases có thể review, chạy các kiểm tra được hỗ trợ, rồi phân tích kết quả. Developer cần review unit code, phạm vi regression và lỗi automation. Người vận hành cần biết phụ thuộc nào bắt buộc trước từng loại tác vụ.

Luồng chính: mục tiêu → LLM chọn chuyên trách → kiểm tra đầu vào → tạo/phân tích/khảo sát → lưu definitions → người dùng hoặc chế độ run yêu cầu thực thi → lưu results → phân tích/báo cáo.

## 2. Phạm vi hiện tại

| Nhóm | Có trong phiên bản này |
|---|---|
| Điều phối | LLM chọn agent chính và 0–3 sub-agent phân tích độc lập; lý do được lưu; không có keyword fallback |
| AI | Native CLI Codex/Antigravity/Claude; một provider kết nối; model/effort theo capability |
| Ngữ cảnh | Documents/OpenAPI/code/UI; SQLite FTS5 và fallback; metadata routing |
| Thiết kế | Yêu cầu, plan, dữ liệu, cases, review, repo/unit/regression |
| Browser | Chromium headless; observe/act; validated DSL; export TypeScript |
| Thực thi | Browser/API cases; sequential/parallel; per-case results và artifacts |
| Chẩn đoán | Phân tích finished run; repair browser definitions; report JSON/Markdown |

Performance/security/exploratory là kế hoạch/phân tích. Unit code là artifact để review. Những vai trò này không có executor chuyên dụng.

## 3. Điều kiện trước khi khởi động

| ID | Điều kiện | Cách xác nhận |
|---|---|---|
| PRE-01 | Python 3.10+, pip/venv; dependencies requirements.txt đã cài | Chạy đúng Python của .venv và import testagent.api |
| PRE-02 | Node 20+ và npm cho web/browser runner | node --version; npm --version |
| PRE-03 | Dependencies web đã cài | npm ci trong web thành công |
| PRE-04 | DATA_DIR ghi được; SQLite hỗ trợ FTS5 | Backend init_db thành công |
| PRE-05 | Backend và frontend dùng cổng khả dụng | Hai server khởi động; Vite dùng --strictPort |
| PRE-06 | WEB_ORIGIN và VITE_API_PROXY_TARGET đúng | Origin khớp frontend; proxy gọi được /api/health |
| PRE-07 | Máy backend truy cập các dịch vụ cần thiết | Provider/website/repo tương ứng truy cập được khi dùng |
| PRE-08 | Giữ backend hoạt động khi tác vụ đang chạy | BackgroundTasks chưa có resume bền vững sau restart |

Docker không bắt buộc. Git chỉ bắt buộc với HTTPS repository import. Không cần cài database server riêng.

## 4. Điều kiện theo tác vụ

### 4.1 Dùng AI

- CLI executable của provider phải tồn tại trong môi trường backend.
- Hoàn tất kết nối tài khoản trong TestAgent; native CLI login sẵn không tự tạo kết nối app.
- Có model hợp lệ; effort nếu dùng phải nằm trong capability của model.
- Chỉ một provider kết nối hoặc đăng nhập tại một thời điểm; đổi provider sau logout/cancel.
- Có kết nối provider và hạn mức phù hợp. Không có API-key/HTTP-model fallback.
- Prompt và evidence có thể được gửi tới provider đã chọn; dữ liệu phải phù hợp với việc này.

Chạy trực tiếp saved cases bằng run_tests hoặc /api/tests/execute không cần AI. Chế độ tự động điều phối tới run_tests vẫn cần AI cho quyết định ban đầu.

### 4.2 Browser discovery và execution

- browser_runner/dist/cli.js đã build, Node sẵn sàng và Chromium đã cài.
- Base URL HTTP(S) của ứng dụng cần test truy cập được từ backend, gồm DNS/TLS/dependencies cần thiết.
- URL thao tác và destination nằm cùng scheme/host/port với origin dự án.
- Có start state, actor, dữ liệu và oracle đủ cho mục tiêu; credentials lấy từ input hoặc demo account công khai.
- Dữ liệu server đã chuẩn bị nếu DSL không thể tự chuẩn bị; mỗi case tự login trong phiên browser sạch.
- Môi trường production cần ALLOW_PRODUCTION_EXECUTION=true cho live browser automation và test execution; mặc định false.
- generate bỏ qua confirmation run, **không bỏ qua browser exploration**. Fill/click trong discovery có thể đổi trạng thái ứng dụng.

browser_runner_ready xác nhận executable/browser binary, chưa xác nhận website, tài khoản hoặc cả business flow chạy đúng.

### 4.3 API case

Có method/path, input/headers/body cụ thể và expected status có căn cứ. Authentication/resource IDs/fixtures phải sẵn có trước request. URL cùng origin. Không dùng token placeholders, request chaining hoặc kỳ vọng body/schema như thể runner đã kiểm tra.

### 4.4 Repository/unit/regression

Mã nguồn phải import vào project. Repo local nằm trong IMPORT_ROOT; repo remote dùng HTTPS host allowlist, không có credentials trong URL; ZIP chứa source phù hợp. Regression cần mô tả thay đổi hoặc diff để kết luận cụ thể. Unit code cần harness/import/fixture đủ để review, và phải chạy bằng harness của repo ngoài TestAgent.

### 4.5 Selected cases và finished run

| Chức năng | Input bắt buộc |
|---|---|
| case_review | 1–30 case IDs cùng dự án |
| automation_builder | 1–20 case IDs cùng dự án; Base URL cho live browser |
| run_tests | 1–30 IDs cùng dự án; mọi case readiness.ready |
| defect_analysis / report | Finished run COMPLETED/FAILED có result rows |
| repair_automation | Finished run có failed browser automation; Base URL; tối đa 20 revisions trong schema |

Run-based chức năng dùng run đã chọn; nếu không chọn, dùng finished run gần nhất của project. Repair không chọn passing/API-only cases. Không có tự chia batch repair khi run có quá nhiều browser failures; thu hẹp run scope trước khi yêu cầu sửa.

## 5. Đầu vào tối thiểu cho ứng dụng cần test

| Thông tin | Khi cần | Nếu chưa biết |
|---|---|---|
| Mục tiêu/deliverable | Mọi tác vụ AI; prompt 5–4000 ký tự | Mô tả kết quả muốn nhận; goal quá rộng có thể được route tới test_plan |
| Base URL / entry path | Live browser và executable cases | Vẫn có thể phân tích/thiết kế từ goal; chưa thể thực thi |
| Actor/account/role | Luồng được bảo vệ | Nêu access thiếu; không đoán credentials |
| Quy tắc/kết quả mong đợi | Assertion nghiệp vụ | Phân biệt smoke observation với intended rule; hỏi đúng rule thiếu |
| Dữ liệu/trạng thái ban đầu | Luồng phụ thuộc records/cart/state | Chuẩn bị ngoài runner khi cần; không giả định fixture đã chạy |
| Method/path/status contract | API execution | Definition ở dạng manual hoặc phân tích gap |
| Case/run/source IDs | Review/build/diagnostics/attribution | Chỉ dùng ID thực cùng project/context |
| SRS/OpenAPI/code/logs | Khi bổ sung rule/contract/implementation | Không yêu cầu upload chung chỉ vì sources trống |

Dùng [TEST_BRIEF.template.md](./TEST_BRIEF.template.md) để ghi scope, actor, rule, expected outcome và gaps. Không điền “thành công” chung chung thay cho dấu hiệu quan sát được.

## 6. Yêu cầu chức năng và nghiệm thu

### FR-01 — Project và environment

Tạo project có name, Base URL tùy chọn và environment local/development/staging/production. URL có giá trị phải hợp lệ HTTP(S). Case/run/source thuộc project rõ ràng.

Nghiệm thu: project tạo/list/update qua API; URL sai bị 422; IDs của project khác bị từ chối trong selected-case/run input.

Triển khai: [api.py](./testagent/api.py), [schemas.py](./testagent/schemas.py).

### FR-02 — Provider/model selection

Kết nối một native provider, chọn model/effort phù hợp, lưu trạng thái app qua restart và snapshot lựa chọn cho mỗi task. Logout app không được giả định là logout toàn bộ CLI.

Nghiệm thu: chưa kết nối thì AI task không được tạo; provider thứ hai bị chặn; selection không hợp lệ bị từ chối; task giữ provider/model/effort đã giao.

Triển khai: [ai_providers.py](./testagent/ai_providers.py), [llm.py](./testagent/llm.py), [cli_transport.py](./testagent/cli_transport.py).

### FR-03 — LLM orchestration

Bỏ function hoặc chọn orchestrator/auto thì gọi LLM với goal, project metadata và danh sách specialists. LLM trả function/reason và sub_tasks tùy chọn; code xác thực ID, input và dispatch. Chọn agent trực tiếp bỏ qua lượt AI routing.

Nghiệm thu: quyết định function do JSON của provider cung cấp, không suy đoán bằng regex; ID không đăng ký/tự route bị lỗi; reason/selection được lưu; thiếu required context ở chế độ auto dẫn NEEDS_INPUT.

Triển khai: [orchestrator.py](./testagent/orchestrator.py), [routing_context.py](./testagent/routing_context.py), [agent_validation.py](./testagent/agent_validation.py).

### FR-04 — Evidence ingestion và retrieval

Import documents/OpenAPI/repository/UI observations; lưu sources, chunks và truy xuất theo project. Giữ attribution source IDs. Nội dung evidence không được coi là chỉ dẫn đổi schema/role.

Nghiệm thu: upload hỗ trợ đúng định dạng/giới hạn; local repo ngoài IMPORT_ROOT bị chặn; UI snapshots dùng đúng origin; prompt-only role không bắt buộc sources.

Triển khai: [ingest.py](./testagent/ingest.py), [knowledge.py](./testagent/knowledge.py).

### FR-05 — Case generation và review

AI trả GeneratedPlan hoặc AgentAnalysis theo mode. Prompt yêu cầu tối đa 12 new cases; schema cho tối đa 20 cases. Cases có steps/expected và attribution. Payload executable chỉ có capabilities được hỗ trợ.

Nghiệm thu: parse/validate schema; chỉ lưu citation IDs hợp lệ trong context; review không tuyên bố đã thực thi; manual cases giữ nguyên expected behavior và nêu gap.

Triển khai: [skills.py](./testagent/skills.py), [planner.py](./testagent/planner.py), [schemas.py](./testagent/schemas.py).

### FR-06 — Live browser loop

Nhận snapshot, để LLM quyết định actions, xác thực DSL, thực thi rồi nhận observation mới. Reset browser giữa independent scenarios. Thiếu input thiết yếu có blocked_reason.

Nghiệm thu: decision không trộn actions với done/block/reset; tối đa 8 decisions, 6 actions/decision; tổng 3 failed groups dừng; last_error chưa giải quyết không được done thành công.

Triển khai: [ui_agent.py](./testagent/ui_agent.py), [browser_bridge.py](./testagent/browser_bridge.py), [session.ts](./browser_runner/src/session.ts).

### FR-07 — Replayable browser DSL và export

Case bắt đầu navigate và có outcome assertion; mỗi target xác định đúng một element; resolver/compiler dùng cùng semantics. Export .spec.ts phản ánh DSL.

Nghiệm thu: route ngoài origin bị từ chối; ambiguity không chọn phần tử đầu; supported example payloads validate và compile; không thiếu await assertions.

Triển khai: [automation.py](./testagent/automation.py), [locators.ts](./browser_runner/src/locators.ts), [runtime.ts](./browser_runner/src/runtime.ts).

### FR-08 — Saved-suite admission/scheduling

Chạy 1–30 saved cases, deduplicate giữ selection order, kiểm tra readiness/ownership/environment trước run creation. Sequential theo selection; parallel bounded 1–4 workers.

Nghiệm thu: foreign/manual/invalid cases không tạo run; browser state mới cho mỗi case; kết quả ghi khi hoàn tất; case lỗi không làm bỏ toàn bộ phần còn lại; không tự retry.

Triển khai: [readiness.py](./testagent/readiness.py), [runner.py](./testagent/runner.py).

### FR-09 — Standalone API execution

Mỗi case gửi một request và so expected_status. Redirect không tự follow. JSON/list body gửi dưới dạng JSON, string dưới dạng content.

Nghiệm thu: request/status ghi result; transport error/timeout có kết quả tương ứng; body/schema không bị báo đã kiểm tra.

Triển khai: [runner.py](./testagent/runner.py).

### FR-10 — Build/repair identity và expectations

Builder/repair trả đúng một revision mỗi supplied origin_case_id. Giữ original identity/purpose/expectations; sửa browser retains mọi assertion action/value/URL, kể cả lặp.

Nghiệm thu: extra/duplicate/foreign origin IDs bị lỗi; builder update case cũ thay vì nhân bản; repair xóa/đổi original oracle bị từ chối.

Triển khai: [planner.py](./testagent/planner.py).

### FR-11 — Results/artifacts và diagnosis

Persist run summary, per-case status/duration/message/failure type và available artifacts. AI diagnosis/report chỉ dùng evidence thực; báo cáo JSON và Markdown truy cập được.

Nghiệm thu: PASS không bị suy ra từ generated definition; mismatched counts/unknown root cause được chỉ rõ; filename-only artifacts không bị mô tả như đã xem; replay là run mới.

Triển khai: [runner.py](./testagent/runner.py), [api.py](./testagent/api.py).

### FR-12 — Tiến độ và kết quả trên UI

Workspace hiển thị task/run status, AI selection, routing reason, generated cases, readiness, results và gaps. Mặc định UI chọn orchestrator và generate.

Nghiệm thu: user thấy chuyên trách/lý do được chọn, phân biệt preview với recorded execution và biết input thiếu. UI polling kết thúc với terminal statuses.

Triển khai: [App.tsx](./web/src/App.tsx), [TaskWorkflow.tsx](./web/src/TaskWorkflow.tsx), [TestLibrary.tsx](./web/src/TestLibrary.tsx).

### FR-13 — Sub-agent phân tích độc lập

Orchestrator tự quyết định có cần phân tích bổ trợ hay không. Có tối đa 3 sub-agent từ các role mode=analysis, mỗi role khác agent chính và khác nhau. Các worker dùng provider/model/effort đã pin; không sinh/sửa cases, không browser interaction/test execution, không delegate tiếp. Agent chính nhận bàn giao có giới hạn và tổng hợp ngay trong lượt tạo deliverable vốn có.

Nghiệm thu: tác vụ đơn giản giữ nguyên số lượt AI; agent_mode=single không tạo worker; ID/role/budget sai bị lỗi trước dispatch; required context được xác thực trước fan-out. SUBAGENT_WORKERS giới hạn đồng thời 1–3 trong mỗi backend process. Parent/child linkage, outputs, errors và wall_ms/worker_ms được lưu; task con lỗi ngăn task cha COMPLETED. UI hiển thị children dưới task cha và không nhân bản feed tác vụ.

Triển khai: [subagents.py](./testagent/subagents.py), [orchestrator.py](./testagent/orchestrator.py), [planner.py](./testagent/planner.py), [test_orchestrator.py](./tests/test_orchestrator.py).

## 7. Hợp đồng và giới hạn

| Nội dung | Giá trị hiện tại |
|---|---|
| Specialists / prompt files | 18 specialists + 1 orchestrator; 23 Markdown files |
| LLM route | Một agent chính; AgentRoute gồm function/reason và sub_tasks tùy chọn |
| Sub-agent | 0–3 analysis roles độc lập; giới hạn đồng thời 1–3/process; không recursion |
| Browser DSL | navigate/fill/click/check/select/assert_visible/assert_text/assert_url |
| Locator | testid, role/name, label, placeholder, id, text, css; một scope level |
| Assertion text / URL | Substring containment / đầy đủ resolved URL |
| Case generation | Hướng dẫn 1–12 new cases; schema 1–20 cases |
| Selected builder / suite | Tối đa 20 / 1–30 IDs |
| Action count | DSL 1–50/case; BrowserDecision tối đa 6 |
| Browser exploration | Tối đa 8 decisions; 3 failed action groups tổng cộng |
| Parallel workers | 1–4; default request 3 |
| Analysis | summary tối thiểu 10 ký tự; tối đa 20 findings và 20 recommendations |
| Upload document/OpenAPI | 8 MiB |
| ZIP/repo intake | Tối đa 50 MiB source; 800 imported files; 8 MiB/file |
| AI timeout | Mặc định 300 giây mỗi inference; tổng task có thể dài hơn |
| Runtime persistence | SQLite, WAL, foreign keys; schema migration khi startup |

PDF intake trích xuất text, không có OCR. ZIP/repo chỉ import extensions allowlist và có skipped counts; không coi intake là quét toàn bộ codebase.

## 8. Yêu cầu chất lượng và ranh giới

| ID | Tiêu chí hiện tại | Giới hạn cần hiểu |
|---|---|---|
| NFR-01 — Tính kiểm chứng | Result dựa trên checks thực; intended rule không bị sửa để che fail | AI có thể sai; cần review |
| NFR-02 — Truy vết | Task lưu selection/routing; cases/results có IDs; output lưu instruction filenames | Chưa lưu hash/version toàn bộ prompt |
| NFR-03 — Tách dữ liệu | Ownership theo project; browser sessions riêng | Không có multi-user authentication/RBAC |
| NFR-04 — Quyền thực thi | Same-origin validators; production opt-in; AI account mutations kiểm tra origin khi header có | CORS/origin không phải user authentication |
| NFR-05 — Lỗi minh bạch | AI/validation errors hiển thị; run setup error có terminal FAILED | Chưa có durable queue/recovery sau process death |
| NFR-06 — Giới hạn tài nguyên | Bound actions/cases/workers/import/context; timeout mỗi call | Chưa có distributed scheduling/resource quotas |
| NFR-07 — Dữ liệu nhạy cảm | Native tokens do CLI quản lý; skills yêu cầu không lặp secrets trong prose | Không có vault/encryption/redaction toàn diện cho DSL/artifacts |

Không đặt SLA latency/throughput hoặc coverage target giả định cho nền tảng. Các benchmark nếu cần phải được đo riêng.

## 9. Checklist trước một lượt test

- [ ] Backend/health phản hồi; chọn đúng project/environment.
- [ ] Base URL/entry path là ứng dụng cần test và truy cập được từ backend.
- [ ] Có CLI/account/model hợp lệ nếu tác vụ dùng AI.
- [ ] Browser runner/Chromium sẵn sàng nếu có browser thao tác.
- [ ] Actor, account, dữ liệu ban đầu và expected result đủ cho journey.
- [ ] Cases thuộc project, đủ preparation, có assertion và không dùng unresolved placeholders.
- [ ] Chọn generate hoặc run đúng mục đích; hiểu exploration vẫn có thao tác.
- [ ] Parallel cases có server data độc lập; nếu chưa bảo đảm thì thu hẹp selection/dùng dữ liệu riêng.
- [ ] Biết run/case IDs cần phân tích, artifact nào thực sự đã xem và giới hạn checks.

## 10. Kiểm chứng và truy vết requirements

| Nhóm yêu cầu | Bộ kiểm tra |
|---|---|
| FR-02 | tests/test_ai_providers.py |
| FR-03, FR-13 | tests/test_orchestrator.py |
| FR-04, prompt-only behavior | tests/test_optional_context.py |
| FR-05 và prompt/examples | tests/test_agent_skills.py |
| FR-06, FR-07, FR-10 | tests/test_ui_agent.py |
| FR-08, FR-09 và run failures | tests/test_suite_execution.py |
| FR-12 | Frontend build và browser review luồng liên quan |

Chạy unittest từ root; browser-related checks cần Node/runner build/Chromium. Provider mocks xác nhận contract, không chứng minh account/model online; live LLM kiểm tra riêng. Các checkpoint trên phục vụ acceptance, không khẳng định mọi edge case đã được test.

## 11. Ngoài phạm vi và hướng phát triển

Chưa có: pipeline nhiều bước có dependency giữa các agent, planner replanning xuyên nhiều tasks, durable queue/cancel/resume, automatic repair-and-retry, unit-code executor, k6/JMeter/security-scan runner, body/schema/input-value/absence assertions, fixture engine/token capture, iframe/upload/cross-origin SSO, vector database/call graph/code coverage, RBAC/secret vault và production hosting hoàn chỉnh. Fan-out phân tích độc lập đã có; không đại diện cho pipeline thực thi mọi tác vụ QA.

Khi thêm capability phải cập nhật schema/validators/runtime/compiler, registry/skills, tests, SRS và thiết kế. Viết hướng dẫn Markdown không tự cung cấp công cụ hoặc quyền chạy mới.
