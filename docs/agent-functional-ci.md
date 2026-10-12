# Chạy test case chức năng agent trên CI

Bộ [37 test case](../tests/agent_function_cases.json) gồm 30 case chức năng TestAgent và 7 case minh họa trạng thái report, được chia thành hai job Playwright độc lập, mỗi job có HTML report riêng. Mỗi case có ID ổn định, bước thực hiện và kỳ vọng. Không xuất hoặc nhập SQLite, project, test case, live-result hay phiên đăng nhập có sẵn trong workspace.

## Phạm vi

| Nhóm | ID | Kiểm tra |
|---|---|---|
| Chức năng | AGENT-F01–F19 | Toàn bộ 19 chức năng trong registry: điều phối, sinh case, UI automation, builder, review, execution, repair, đọc repo, report, requirements, plan, unit, API, defect, regression, performance, security, exploratory, test data |
| Điều kiện chặn/lỗi | AGENT-N01–N08 | Case thủ công, cross-origin, case sai project, assertion thất bại, giao lại run ID, model output sai schema, generate-only, thiếu source |
| Nhập dữ liệu | AGENT-I01–I03 | Sinh document, repository ZIP và OpenAPI trong bộ nhớ, upload và xác minh indexing/retrieval |
| Trạng thái report | DEMO-PASS01, DEMO-FAIL01–02, DEMO-FLAKY01–02, DEMO-SKIP01–02 | 1 PASS đối chiếu, 2 FAIL có chủ đích, 2 FLAKY được kiểm soát và 2 SKIP có lý do |

Playwright Test tạo và chạy riêng từng ID đã chọn trong catalog. `webServer` khởi động API FastAPI thật trên loopback, với database tạm mới, code và yêu cầu tự sinh. Các case dùng Playwright APIRequestContext để gọi HTTP thật tới API agent; task controller, SQLite, validator và HTTP request tới target dùng code thật. Ba case UI/builder/repair còn chạy lại DSL được tạo bằng Playwright Chromium, có assertion trên kết quả Healthy. Các case trong mỗi job dùng chung môi trường do chính job đó tạo và xóa khi kết thúc. Không đọc dữ liệu ứng dụng của người dùng.

Phản hồi tại biên AI provider là fixture cố định. Bộ test kiểm tra xử lý/routing/persistence/execution của agent, không đo chất lượng suy luận của model thật. Không gọi provider thật và không cần GitHub secret AI. Các chức năng performance/security/exploratory chỉ được kiểm tra ở mức analysis workflow; không phải load test hay penetration test. Unit-test code được kiểm tra cú pháp để review, không tự thực thi proposal.

Case repair bắt đầu từ một browser run **thất bại thật** trên locator `obsolete-status`, sau đó sửa locator và giữ nguyên assertion `Healthy`. AGENT-N04 chủ động tạo sai kỳ vọng HTTP 201 trong khi server trả 200: case chức năng PASS khi agent báo đúng run FAILED và result FAIL. Những run âm có chủ đích được lưu đầy đủ, không bị đổi thành product PASS.

## GitHub Actions

Workflow [ci.yml](../.github/workflows/ci.yml) có hai job Playwright và job build/regression:

1. `Build and regression checks`: build và chạy bộ regression hiện có.
2. `Playwright - 30 functional cases`: `AGENT_TEST_SUITE=functional`, chỉ chạy 30 case AGENT-F/N/I, yêu cầu đủ 30 PASS.
3. `Playwright - 7 status demo cases`: `AGENT_TEST_SUITE=status-demo`, chỉ chạy 7 case DEMO; dự kiến 1 PASS, 2 FAIL, 2 FLAKY, 2 SKIP.

Các job độc lập và chạy trên cùng commit. Push nhánh `aoce/**` trigger workflow. Hai job Playwright đều cài runner/Chromium, typecheck và thực thi `npm run test:agent --prefix browser_runner`; cấu hình chọn file test theo `AGENT_TEST_SUITE` và từ chối giá trị suite không hợp lệ. Mỗi job dùng runner riêng, database/HTTP target mới và thư mục report riêng.

Gate yêu cầu catalog có đủ mọi function trong registry, ID duy nhất, mọi scenario có implementation, bước và oracle không rỗng. Verifier nhận `--suite functional` hoặc `--suite status-demo`, chỉ yêu cầu các ID thuộc suite đó và từ chối ID của job còn lại. 30 case chức năng phải PASS đủ, không retry, skip hoặc expected-failure. Bảy case có `report_demo=true` được đối chiếu với trạng thái và lịch sử attempts đã khai báo, không đổi FAIL/FLAKY/SKIP thành PASS. Không có browser, thiếu case đã chọn, setup lỗi hoặc artifact thiếu đều không được coi là PASS.

**Job 30 case dự kiến xanh; job 7 demo dự kiến đỏ do 2 case FAIL cố ý.** Workflow tổng vẫn đỏ khi job demo thất bại. Không dùng `continue-on-error`, `test.fail()` hoặc sửa exit code. Report chức năng có **30 PASS**; report demo có **1 PASS, 2 FAIL, 2 FLAKY, 2 SKIP** (5 case thực thi assertion và 2 case bị skip). Step đối chiếu report demo có thể thành công trong khi step chạy Playwright và job demo vẫn thất bại.

DEMO-FAIL01 cố ý mong HTTP 200 cho task không tồn tại, thực tế trả 404. DEMO-FAIL02 cố ý mong Offline sau refresh, thực tế là Healthy. Hai case flaky được phép đúng một retry: fixture lần đầu trả 503/Starting, lần retry trả 200/Healthy; assertion giữ nguyên ở cả hai attempts. Đây là mô phỏng có kiểm soát để xem report, không phải bằng chứng agent có lỗi flaky ngoài thực tế. Hai case skip ghi rõ thiếu credential live-provider và production mutation nằm ngoài phạm vi; không gọi provider hoặc ghi production.

Mỗi job upload artifact riêng bằng `always()` cả khi test FAIL, giữ 7 ngày:

| Job | Artifact | Thư mục report |
|---|---|---|
| 30 case chức năng | `playwright-functional-report-<run-id>-<attempt>` | `output/playwright/agent-cases/` |
| 7 case demo | `playwright-status-demo-report-<run-id>-<attempt>` | `output/playwright/status-demo/` |

Mỗi artifact chứa:

- `html/index.html` và `html/data/`: HTML report gốc do Playwright tạo; có bộ lọc Passed/Failed/Skipped, thời gian, bước, lỗi, response và các file đính kèm.
- `results.json`, `junit.xml`: reporter JSON và JUnit gốc của Playwright.
- `catalog.json`: bộ case đã chọn trước khi chạy.
- `manifest.json`, `summary.md`: đối chiếu đúng commit/catalog, kết quả từng ID và đủ evidence; bảng kết quả cũng hiển thị trong GitHub Actions summary.
- `test-results/`: trace, screenshot và video của Playwright khi case thất bại; response và case definition được đính kèm trong HTML report.
- `browser/`: run/results của target synthetic, generated specs, screenshot, trace và video do runner xuất.

Manifest ghi rõ suite, các ID đã chọn, commit/run/attempt, `workspace_data_imported=false`, `model_mode=fixture`, `actual_provider_calls=0`, số flaky và trạng thái từng attempt của demo. `functional_outcome` đánh giá job chức năng; `demo_outcomes_match` đối chiếu job demo. Lỗi setup trước khi runner bắt đầu được ghi BLOCKED với executed=0. Cleanup/evidence validation lỗi làm run thất bại kể cả khi assertion đã pass.

Trong GitHub Actions, mở run → **Artifacts** → chọn artifact chức năng hoặc demo → tải và giải nén. Chạy:

```powershell
npx playwright show-report <thu-muc-giai-nen>/html
```

Mở URL mà lệnh in ra để lọc Passed/Failed hoặc xem chi tiết case. GitHub artifact không trực tiếp host HTML; tải và chạy `show-report` giúp xem cả attachments/trace. Nếu dependency/setup lỗi trước khi Playwright bắt đầu thì artifact ghi BLOCKED, không thể có HTML report của những case chưa chạy.

## Chạy local

Sau khi build `browser_runner` và cài Chromium, chạy trong PowerShell:

```powershell
npm run test:agent --prefix browser_runner
python -m scripts.verify_playwright_report --suite functional
npm run report:agent --prefix browser_runner
```

Suite mặc định là `functional`; kết quả nằm trong `output/playwright/agent-cases/`, không commit. Để chẩn đoán riêng demo, đặt `$env:AGENT_TEST_SUITE = 'status-demo'` khi chạy Playwright, dùng verifier `--suite status-demo` và mở report trong `output/playwright/status-demo/html`. Playwright tự cấp thư mục DATA_DIR/IMPORT_ROOT trong hệ thống tạm cho fixture, không tái sử dụng server đã có. Runner Python cũ `scripts.ci_agent_cases` vẫn có thể chạy riêng để chẩn đoán, CI job chức năng dùng Playwright Test.

Các test gate chạy bằng `python -m unittest discover -s tests -p test_playwright_report.py -v` và `python -m unittest discover -s tests -p test_ci_agent_cases.py -v`. Gate đọc execution gốc của Playwright, từ chối thiếu case/ID trùng; chỉ cho phép retry/skip ở các demo đã khai báo. Không chuyển kết quả unittest cũ thành Playwright report. Runner Python chẩn đoán chỉ chạy 30 case chức năng, không chạy các case demo.
