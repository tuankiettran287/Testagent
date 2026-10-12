# TestAgent

TestAgent giúp QA mô tả mục tiêu kiểm thử, để AI chọn agent chuyên trách, tạo hoặc bổ sung test case, khảo sát website và chạy các case đã lưu. Backend dùng Python/FastAPI; giao diện và Playwright runner dùng TypeScript.

**Tự động điều phối dùng LLM từ provider đã đăng nhập.** AI chọn agent chính và quyết định có cần sub-agent phân tích hay không. Python xác thực quyết định, chạy các phần việc độc lập rồi chuyển kết quả về agent chính.

| Tài liệu | Dùng khi |
|---|---|
| [SRS.md](./SRS.md) | Xem yêu cầu, điều kiện trước khi chạy và tiêu chí nghiệm thu |
| [TestAgent_System_Design.md](./TestAgent_System_Design.md) | Hiểu kiến trúc, luồng dữ liệu và giới hạn triển khai |
| [TEST_BRIEF.template.md](./TEST_BRIEF.template.md) | Chuẩn bị mục tiêu, quy tắc và dữ liệu cho ứng dụng cần test |
| [agent_skills](./testagent/agent_skills/) | Điều chỉnh hướng dẫn LLM cho từng vai trò |

SRS của TestAgent mô tả chính nền tảng này. SRS/OpenAPI của ứng dụng cần test là nguồn bổ sung; **không phải điều kiện bắt buộc cho mọi tác vụ**.

## Có thể làm gì

- Phân tích yêu cầu, lập kế hoạch, thiết kế dữ liệu, tạo và rà soát test case.
- Khảo sát website bằng browser thật, tạo browser DSL và xuất Playwright TypeScript.
- Bổ sung automation cho cases đã chọn, giữ nguyên mục tiêu và kết quả mong đợi.
- Chạy một case hoặc bộ 1–30 cases, tuần tự hoặc song song với 1–4 workers.
- Chạy API request độc lập và kiểm tra HTTP status.
- Đọc kết quả, tải bằng chứng, phân tích lỗi, đề xuất sửa automation và xuất báo cáo QA.

Unit test được sinh để review. Performance, security và exploratory hiện tạo kế hoạch/phân tích. Runner chưa thực thi unit code tùy ý, load test hoặc security scan. Orchestrator chưa tự nối nhiều agent thành pipeline.

## Chuẩn bị trước khi chạy

| Mục tiêu | Điều kiện cần |
|---|---|
| Mở workspace | Python, dependencies backend, Node/npm, dependencies frontend, thư mục dữ liệu ghi được |
| Dùng AI hoặc tự động điều phối | CLI của provider trên máy backend; tài khoản đã kết nối trong app; model hợp lệ; kết nối provider |
| Khảo sát hoặc chạy browser test | Node 20+, runner đã build, Chromium; HTTP(S) Base URL truy cập được từ backend |
| Test luồng cần đăng nhập | Tài khoản test được cung cấp hoặc tài khoản demo công khai; trạng thái/dữ liệu và kết quả mong đợi phù hợp |
| Chạy API case | Request cụ thể, expected status có căn cứ, dữ liệu/auth đã chuẩn bị, URL cùng origin |
| Đọc repo / sinh unit / regression | Mã nguồn đã import; regression cần mô tả thay đổi/diff để phân tích chính xác |
| Review/build cases | Cases cùng dự án; tối đa 20 cases cho builder |
| Phân tích lỗi / report / sửa automation | Lượt chạy COMPLETED hoặc FAILED có kết quả; sửa cần browser cases lỗi |
| Chạy lại cases đã lưu | Cases có readiness.ready; không cần tài khoản AI |

Python 3.10+; môi trường phát triển đã kiểm thử với Python 3.13 và Node 22. Git cần khi import repository HTTPS. SQLite được tạo tự động; không cần server database riêng.

Chi tiết checklist và dữ liệu tối thiểu: [SRS.md](./SRS.md). Nếu chỉ muốn phân tích mục tiêu, có thể chưa đặt Base URL.

## Cài đặt và chạy trên Windows

Dùng PowerShell, thay đường dẫn nếu workspace khác. Cài lần đầu:

```powershell
Set-Location "F:/TestAgent"
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt

Set-Location "F:/TestAgent/browser_runner"
npm ci
npm run build
npm run browser:install

Set-Location "F:/TestAgent/web"
npm ci
```

Gọi trực tiếp Python trong .venv nên không cần activate hay đổi execution policy. Browser runner được backend mở khi cần; không chạy thêm server runner riêng.

Terminal backend:

```powershell
Set-Location "F:/TestAgent"
$env:WEB_ORIGIN = "http://127.0.0.1:5173"
./.venv/Scripts/python.exe -m uvicorn testagent.api:app --reload --host 127.0.0.1 --port 8000
```

Terminal frontend:

```powershell
Set-Location "F:/TestAgent/web"
$env:VITE_API_PROXY_TARGET = "http://127.0.0.1:8000"
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Mở http://127.0.0.1:5173. Swagger ở http://127.0.0.1:8000/docs. Giữ hai terminal mở, dừng bằng Ctrl+C.

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/health"
```

status=ok xác nhận backend phản hồi. browser_runner_ready=true xác nhận Node, entrypoint và browser binary sẵn sàng; chưa chứng minh website truy cập được. model_configured=true cho biết app có kết nối AI/model được chọn; false trước khi đăng nhập là bình thường.

Nếu cổng bận, đổi backend sang 18000 và frontend sang 15173. Cập nhật WEB_ORIGIN thành http://127.0.0.1:15173 và proxy thành http://127.0.0.1:18000. WEB_ORIGIN phải trùng scheme/host/port của frontend; localhost và 127.0.0.1 là hai origin khác nhau.

## Cài đặt trên macOS / Linux

Từ thư mục gốc:

```bash
[ -f .env ] || cp .env.example .env
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd browser_runner
npm ci
npm run build
npm run browser:install
cd ../web
npm ci
cd ..
```

Terminal backend, từ thư mục gốc:

```bash
export WEB_ORIGIN=http://127.0.0.1:5173
.venv/bin/python -m uvicorn testagent.api:app --reload --host 127.0.0.1 --port 8000
```

Terminal frontend, từ thư mục gốc:

```bash
export VITE_API_PROXY_TARGET=http://127.0.0.1:8000
cd web
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Nếu Linux thiếu thư viện Chromium, chạy npx playwright install --with-deps chromium trong browser_runner.

## Kết nối AI

| Provider | CLI mặc định | Cấu hình executable |
|---|---|---|
| Codex / tài khoản ChatGPT | codex | CODEX_BINARY |
| Antigravity | agy | ANTIGRAVITY_BINARY |
| Claude Code | claude | CLAUDE_BINARY |

Cài CLI phù hợp và bảo đảm backend tìm được executable trong PATH hoặc qua cấu hình. CLI phải có trên **máy chạy backend**, kể cả khi đăng nhập mở trong browser. Sau khi cài hoặc đổi PATH, khởi động lại backend.

1. Mở **Kết nối AI**, chọn provider và hoàn tất luồng đăng nhập app hiển thị.
2. Codex hỗ trợ browser/device login; Antigravity/Claude dùng luồng CLI tương ứng. Nếu đã đăng nhập native CLI, vẫn cần kết nối provider trong app.
3. Nhấn kiểm tra kết nối khi cần, chọn model và effort nếu model hỗ trợ.
4. Quay lại Tổng quan để giao việc.

App chỉ kết nối một provider tại một thời điểm. Đổi provider bằng cách đăng xuất hoặc hủy đăng nhập hiện tại trước. Model/effort lấy từ khả năng CLI và tài khoản, không cố định theo tên trong tài liệu.

Provider/model/effort được lưu theo tác vụ và dùng cho cả điều phối lẫn agent chuyên trách. Khi phiên hết hạn hoặc CLI lỗi, app báo lỗi; không fallback sang provider/API key/endpoint ngoài. Đăng xuất trong app ngắt kết nối app; phiên tài khoản native vẫn do CLI quản lý.

## Luồng sử dụng

### 1. Tạo dự án và mô tả kết quả cần kiểm tra

Đặt môi trường local/development/staging và Base URL của **ứng dụng cần test**. Website phải truy cập được từ máy backend. URL/goal đủ để bắt đầu các kiểm tra phù hợp; tài liệu, OpenAPI hoặc repository giúp xác định quy tắc chính xác hơn.

Một yêu cầu tốt nêu điểm bắt đầu, actor/dữ liệu, thao tác và dấu hiệu thành công. Với login, cung cấp tài khoản test và marker/URL sau đăng nhập nếu đã biết. Dùng [mẫu brief](./TEST_BRIEF.template.md) khi cần ghi rõ quy tắc và các thông tin còn thiếu.

### 2. Chọn tự động điều phối hoặc agent trực tiếp

**Tự động điều phối** là mặc định. LLM trả chức năng và lý do; phần Điều phối trong chi tiết tác vụ hiển thị quyết định. Thiếu input của agent được chọn dẫn đến NEEDS_INPUT, không tự đổi sang một chức năng khác.

Chọn trực tiếp agent bỏ qua lượt LLM điều phối. Chạy bộ test trực tiếp không gọi AI. Những bước tiếp theo trong recommendations vẫn là đề xuất, chưa tự thực thi.

**Tự động chia việc khi cần** là mặc định: một yêu cầu đơn giản dùng một specialist; yêu cầu có nhiều phần phân tích độc lập có thể dùng tối đa 3 sub-agent trước khi agent chính tổng hợp. Ví dụ: lập test plan cần đánh giá bảo mật, workload hiệu năng và dữ liệu biên. LLM chọn vai trò và viết mục tiêu từng phần; không có keyword rule để tạo đội.

Sub-agent dùng cùng provider/model/effort đã chọn, không cần thêm tài khoản hoặc framework. Mỗi task con có trạng thái, kết quả và lỗi riêng trong chi tiết task cha. Các sub-agent chỉ phân tích, không tự chạy browser/test hay tạo/sửa cases. Browser journey và execution vẫn do agent chính thực hiện theo thứ tự của luồng. Không có pipeline tự động generate → run → repair.

Chọn **Chạy một agent**, hoặc gửi agent_mode=single qua API, để bỏ fan-out. Auto mặc định agent_mode=auto. SUBAGENT_WORKERS giới hạn 1–3 sub-agent đang chạy trong mỗi backend process; đặt 1 để chạy tuần tự khi hạn mức thấp. Một sub-agent thêm một lượt model; không có lượt tổng hợp riêng ngoài lượt vốn có của agent chính. Nếu task con lỗi, task cha không báo hoàn tất và giữ các kết quả đã có.

Lượt đo ngày 05/10/2026 với Codex/gpt-6.1-sol/high và cùng một kế hoạch AI chọn 3 helpers: pha helper song song mất 65,1 giây, tuần tự 168,6 giây. Đây là một mẫu cho mỗi chế độ, chưa bao gồm lượt routing/agent chính và không so với việc chỉ dùng một agent. Chưa đo tổng token/chi phí. Script [verify_subagents.py](./scripts/verify_subagents.py) kiểm tra routing đơn giản, single mode, task con và so sánh này bằng model thật.

Tùy chọn chạy lại từ root sau khi kết nối AI: python -m scripts.verify_subagents. Script dùng database tạm và dữ liệu mô phỏng, không thao tác website; gọi model thật 9–11 lượt tùy số helpers. Kết quả được ghi vào output/subagents-live-result.json.

### 3. Tạo và xem automation

Giao việc cho UI automation để khảo sát luồng thực tế; hoặc tạo cases trước rồi dùng builder cho selection.

**Xem test trước, chọn chạy sau** là mặc định trên giao diện. Chế độ generate vẫn cho phép browser agent navigate/fill/click để tìm locator và quan sát kết quả; nó chỉ bỏ qua lượt chạy test xác nhận. Browser exploration có thể thay đổi dữ liệu của ứng dụng.

API mặc định execution_mode=run nếu bỏ qua trường này. Khi tích hợp API, gửi generate rõ ràng nếu cần xem trước. Standard roles như gen_testcase/api_test chỉ lưu definitions, không tự chạy, dù execution_mode=run.

Mỗi browser case phải tự navigate, chuẩn bị/login trong phiên sạch và có assertion. Xem kỳ vọng, dữ liệu, locator và readiness trước khi chạy.

### 4. Chạy và xử lý kết quả

Chọn một case hoặc 1–30 cases, chạy tuần tự hoặc song song với 1–4 workers. Browser state tách riêng từng case; dữ liệu server vẫn có thể dùng chung. Chọn dữ liệu độc lập trước khi chạy song song.

| Giá trị | Ý nghĩa |
|---|---|
| NEEDS_INPUT | Tác vụ cần đầu vào cụ thể để tiếp tục |
| READY | Browser cases đã tạo để xem trước; chưa chạy xác nhận |
| readiness.ready | Payload hợp lệ về cấu trúc; chưa chứng minh chạy thành công |
| Task COMPLETED | Công việc được giao đã hoàn thành; có thể chỉ là phân tích/sinh case |
| Run COMPLETED | Các kết quả được thực thi trong lượt đó đều PASS |
| PASS / FAIL / ERROR / TIMEOUT | Kết quả của một case, diễn giải cùng message/bằng chứng |

Mở run để xem screenshot/video/trace/spec khi có. Chạy lại tạo run mới. Phân tích lỗi dùng kết quả đã ghi; sửa automation tạo bản sửa cần review và xác nhận bằng lượt mới. Assertion/kỳ vọng ban đầu được giữ khi sửa.

Report JSON nằm tại /api/reports/{run_id}; agent report xuất Markdown sau khi hoàn tất.

## Agent và skill

Registry có 18 chuyên trách và 1 orchestrator:

| ID | Công việc | Input chính |
|---|---|---|
| orchestrator | LLM chọn agent chính và tối đa 3 sub-agent phân tích khi hữu ích | Mục tiêu và metadata dự án |
| requirement_under | Phân tích quy tắc/điểm chưa rõ | Mục tiêu; nguồn tùy chọn |
| test_plan | Kế hoạch theo rủi ro | Mục tiêu; nguồn tùy chọn |
| gen_testcase | Thiết kế cases mới | Quy tắc/goal/inspection |
| test_data | Dữ liệu theo quy tắc | Constraints đã biết |
| ui_automation | Live discovery và browser cases | Base URL; access/data khi cần |
| automation_builder | Bổ sung DSL cho cases đã chọn | 1–20 cases và Base URL |
| case_review | Review chất lượng cases | 1–30 cases |
| run_tests | Chạy definitions đã lưu | 1–30 cases structurally ready |
| api_test | Request có expected status | Hợp đồng method/path/status |
| repo_under | Bản đồ QA từ code | Code đã import |
| unit_test | Unit code để review | Code đã import |
| regression | Phạm vi retest theo thay đổi | Code; change/diff để kết luận chính xác |
| defect_analysis | Triage kết quả lỗi | Finished run có results |
| repair_automation | Sửa browser cases lỗi | Finished run và Base URL; tối đa 20 revisions |
| report | Báo cáo QA | Finished run có results |
| exploratory | Charter khám phá | Goal và evidence |
| performance | Kế hoạch đo tải/latency | Transaction và target/assumptions |
| security | Kế hoạch kiểm tra theo rủi ro | Roles/resources/rules đã biết |

AI roles tải automation-core.md cùng file vai trò. Browser roles thêm locator-mastery.md; final generation thêm automation-patterns.md. Execution dùng suite-execution.md để mô tả chính sách, không compose AI prompt.

Hướng dẫn skill nói rõ deliverable, quy trình, giới hạn và tiêu chí hoàn thành. Chỉnh Markdown không thêm capability vào runner; muốn thêm action/assertion phải sửa schema, validator, runtime và compiler tương ứng.

## Cấu hình và dữ liệu

| Biến | Mặc định | Tác dụng |
|---|---|---|
| DATA_DIR | ./data | SQLite, trạng thái app AI và artifacts |
| IMPORT_ROOT | . | Gốc cho phép import repo local |
| CODEX_BINARY / CLAUDE_BINARY / ANTIGRAVITY_BINARY | codex / claude / agy | CLI executable |
| AI_TIMEOUT_SECONDS | 300 | Timeout từng lượt AI, không phải cả tác vụ |
| SUBAGENT_WORKERS | 3 | Tối đa 1–3 sub-agent đồng thời trong mỗi backend process |
| ALLOWED_REPOSITORY_HOSTS | github.com,gitlab.com,bitbucket.org | Host cho Git HTTPS import |
| ALLOW_PRODUCTION_EXECUTION | false | Quyền live automation và test execution trên production |
| WEB_ORIGIN | http://localhost:5173 | Origin frontend được cấu hình |
| NODE_BINARY | node | Node mở runner |
| BROWSER_RUNNER_ENTRY | browser_runner/dist/cli.js | Entrypoint mặc định trong repo |
| VITE_API_PROXY_TARGET | http://localhost:8000 | Proxy frontend; đặt trước khi mở Vite |

Backend đọc .env khi khởi động. Đường dẫn tương đối dựa trên working directory; chạy từ root. Biến môi trường terminal ưu tiên .env. Proxy Vite lấy từ môi trường tiến trình frontend.

DATA_DIR chứa testagent.sqlite3, ai/session.json, ai/selection.json và artifacts/<run_id>/. CLI quản lý xác thực native; frontend không nhận token đăng nhập. Prompt, DSL, unit code và artifacts có thể chứa dữ liệu test hoặc credential literals đã nhập; hệ thống chưa có secret vault. Chỉ dùng dữ liệu/tài khoản phù hợp với việc lưu và gửi ngữ cảnh cho provider.

## API và cấu trúc mã

Schema đầy đủ tại /docs.

| Endpoint | Mục đích |
|---|---|
| GET /api/health | Backend/AI/browser readiness |
| GET /api/ai/providers; PUT /api/ai/selection | Provider và model/effort |
| POST /api/projects | Tạo dự án |
| GET /api/agent/skills | Registry và file hướng dẫn |
| POST /api/agent/tasks; GET /api/agent/tasks/{id} | Giao việc, đọc tiến độ |
| GET /api/projects/{id}/tests | Cases và readiness |
| POST /api/tests/execute | Replay selection |
| GET /api/tests/{id}/playwright | Xuất TypeScript |
| GET /api/runs/{id}; GET /api/reports/{id} | Results và report |
| GET /api/agent/tasks/{id}/report | Markdown từ agent report |

Ví dụ điều phối để lập kế hoạch, thay PROJECT_ID bằng ID thật:

```json
{
  "project_id": "PROJECT_ID",
  "prompt": "Lập kế hoạch kiểm thử luồng đăng nhập, ưu tiên rủi ro và các dữ liệu cần chuẩn bị.",
  "execution_mode": "generate"
}
```

Bỏ function hoặc gửi orchestrator/auto để dùng LLM điều phối. Có thể gửi case_ids/run_id làm ngữ cảnh; trường provider/model/effort phải phù hợp kết nối hiện tại.

```text
testagent/
  api.py                 API và background entrypoints
  orchestrator.py        LLM chọn chuyên trách
  routing_context.py     Metadata gửi cho orchestrator
  agent_validation.py    Kiểm tra quyết định/đầu vào
  planner.py             Context, dispatch, lưu output
  subagents.py           Worker phân tích, giới hạn đồng thời và bàn giao
  ai_providers.py         Quản lý đăng nhập và inference CLI
  cli_transport.py       Transport tiến trình native
  ui_agent.py            Browser observe/act
  runner.py              Admission và thực thi suite
  skills.py              Registry/hợp đồng prompt
  agent_skills/          23 file hướng dẫn
  ingest.py, knowledge.py, db.py
browser_runner/src/      Protocol, snapshot, locator, runtime, compiler
web/src/                 React workspace
tests/                   Kiểm tra hợp đồng và workflows
```

## Kiểm tra khi phát triển

Từ root với dependencies và browser runner đã build:

```powershell
./.venv/Scripts/python.exe -m unittest discover -s tests -v
Set-Location browser_runner
npm run build
Set-Location ../web
npm run build
```

Tests gồm prompt composition, ví dụ DSL compile, provider adapters, context, orchestration, browser flow và suite execution. Phần lớn AI workflow dùng mock; chúng không chứng minh mọi provider/model đang online. Live provider kiểm tra riêng phụ thuộc tài khoản/hạn mức.

Mỗi skill trong registry và mỗi vai trò analysis hỗ trợ sub-agent có một workflow test riêng trong `tests/test_skill_workflows.py`. Các test dùng database tạm và ứng dụng HTTP local; Chromium và request HTTP chạy thật, phản hồi model được mô phỏng. Chạy ma trận đầy đủ và xuất JSON:

```powershell
python -m scripts.verify_agents
python -m scripts.verify_agents --live
```

Chế độ `--live` dùng provider/model/effort đang kết nối trong app cho mọi lượt AI. Nó kiểm tra 19 skill và 11 vai trò sub-agent trên cùng ứng dụng mẫu cô lập, gồm tạo/chạy UI, builder, repair từ một browser run lỗi thật và API execution. Các nhóm helper dùng kế hoạch cố định để bao phủ đủ vai trò; kiểm tra orchestrator riêng dùng routing của model thật. Unit code chỉ được kiểm tra cú pháp để review; performance/security/exploratory vẫn là phân tích. Script ghi kết quả từng mục ngay khi xong vào `output/agents-check-result.json` hoặc `output/agents-live-result.json` và trả exit code khác 0 khi có lỗi. Chạy lại riêng một mục:

```powershell
python -m scripts.verify_agents --live --skills gen_testcase --skip-helpers --output output/agents-live-retry.json
```

Run và task cha được nhận bằng cập nhật SQLite có điều kiện trước khi thực thi: giao lại cùng ID khi đang chạy hoặc đã kết thúc không tạo thêm lượt AI, request hay kết quả. Replay có chủ đích vẫn tạo run/task ID mới. Runner kiểm tra lại quyền production, readiness và tùy chọn thực thi lúc nhận run đang xếp hàng. Cơ chế này không cung cấp resume sau khi backend bị dừng.

Khi sửa browser_runner/src cần build lại runner. Build frontend không build runner và không khởi động server.

## Agent Optimization và GitHub Actions

Thay đổi theo hai tài liệu AOCE được mô tả trong [docs/agent-optimization.md](./docs/agent-optimization.md). Context browser bỏ thuộc tính rỗng và locator expression có thể dựng lại, giữ nguyên text/ARIA, scope và oracle. Prompt/context có version/hash; unknown write dừng để reconcile, chỉ một recovery cho lỗi read/pre-action.

GitHub Actions chạy khi push `master`/`aoce/**`, pull request hoặc workflow dispatch. CI cài dependency đã khóa, build runner/frontend và chạy toàn bộ unittest với Chromium/HTTP thật trên app fixture cục bộ. Model responses là fixture; CI không cần phiên đăng nhập AI. Không có test, thiếu browser, test fail hoặc skip đều làm CI thất bại. Evidence artifact giữ 7 ngày, gồm manifest/revision, JUnit, log, benchmark và trace/video của status portal synthetic.

Chạy cùng verification ở máy local sau khi build runner/cài Chromium:

```powershell
python -m scripts.ci_verify
python -m scripts.benchmark_context
```

Job **Playwright agent cases and HTML report** chạy chung [37 case](./tests/agent_function_cases.json): 30 case chức năng trước đó và 7 case minh họa trạng thái report. Kết quả demo dự kiến là **31 PASS, 2 FAIL, 2 FLAKY, 2 SKIP**; workflow sẽ đỏ vì 2 FAIL có chủ đích. Chỉ hai demo flaky được retry một lần; 30 case chức năng giữ gate nghiêm ngặt. Job tự tạo database/HTTP target/dữ liệu mẫu, không lấy data workspace. Artifact `playwright-report-<run>-<attempt>` vẫn upload khi fail, có HTML report gốc, JUnit/JSON, API evidence và browser traces. Tải, giải nén rồi chạy `npx playwright show-report <thu-muc>/html`. Xem [chi tiết](./docs/agent-functional-ci.md).

Kết quả nằm trong `output/aoce/` (không commit). Benchmark đo bytes trên ba snapshot synthetic mỗi cấu hình; không suy billed tokens/chi phí hoặc chất lượng model thật. Chưa bật scheduled/live-model CI; phiên đăng nhập AI local không tự có trên GitHub runner.

## Docker

Docker/Compose là lựa chọn thêm, không bắt buộc. docker compose up --build mở API 8000 và web dev server 5173 theo cấu hình hiện có. Playwright image/runner và SQLite volume đã được cấu hình.

**Image API hiện không cài các CLI AI hoặc chia sẻ phiên đăng nhập native từ host.** Docker chạy workspace/runner không đồng nghĩa AI sẵn sàng. Cần bổ sung CLI và phiên tài khoản trong container trước khi dùng AI. localhost trong container chỉ chính container; Base URL phải truy cập được từ container.

## Xử lý lỗi và giới hạn

| Hiện tượng | Việc cần kiểm tra |
|---|---|
| Frontend API lỗi | Backend/health, cổng proxy và WEB_ORIGIN |
| AI connection 403 Origin | Scheme/host/port frontend trùng cấu hình |
| CLI chưa tìm thấy | PATH của backend hoặc executable trong .env; restart |
| CLI đã login nhưng app chưa ready | Kết nối trong app và chọn model |
| Provider thứ hai bị chặn | Đăng xuất/hủy provider hiện tại |
| browser_runner_ready=false | Node, build dist/cli.js, Chromium |
| NEEDS_INPUT | Đọc đúng input thiếu; bổ sung rồi gửi tác vụ mới |
| Locator zero/multiple matches | Route/auth/state, attribute/name và scope; giữ oracle |
| API chỉ kiểm tra được status | Body/schema/chaining cần harness/capability bổ sung |
| Production bị chặn | Dùng môi trường test hoặc cấu hình quyền rõ ràng |
| Backend restart khi có tác vụ | BackgroundTasks chưa có queue bền vững/resume tự động |

App là workspace local, chưa có user authentication/RBAC hay distributed queue. CORS/origin checks không thay thế đăng nhập người dùng. Các action phải cùng origin; iframe, upload, cross-origin SSO, assertion input-value/absence/body và fixtures chưa được hỗ trợ. Danh sách đầy đủ và tiêu chí hiện tại ở [SRS.md](./SRS.md).
