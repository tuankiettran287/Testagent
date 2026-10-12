# Chạy test case chức năng agent trên CI

Bộ [30 test case](../tests/agent_function_cases.json) được tạo riêng để kiểm tra TestAgent. Mỗi case có ID ổn định, bước thực hiện và kỳ vọng. Không xuất hoặc nhập SQLite, project, test case, live-result hay phiên đăng nhập có sẵn trong workspace.

## Phạm vi

| Nhóm | ID | Kiểm tra |
|---|---|---|
| Chức năng | AGENT-F01–F19 | Toàn bộ 19 chức năng trong registry: điều phối, sinh case, UI automation, builder, review, execution, repair, đọc repo, report, requirements, plan, unit, API, defect, regression, performance, security, exploratory, test data |
| Điều kiện chặn/lỗi | AGENT-N01–N08 | Case thủ công, cross-origin, case sai project, assertion thất bại, giao lại run ID, model output sai schema, generate-only, thiếu source |
| Nhập dữ liệu | AGENT-I01–I03 | Sinh document, repository ZIP và OpenAPI trong bộ nhớ, upload và xác minh indexing/retrieval |

Playwright Test tạo và chạy riêng từng ID trong catalog. `webServer` khởi động API FastAPI thật trên loopback, với database tạm mới, code và yêu cầu tự sinh. Các case dùng Playwright APIRequestContext để gọi HTTP thật tới API agent; task controller, SQLite, validator và HTTP request tới target dùng code thật. Ba case UI/builder/repair còn chạy lại DSL được tạo bằng Playwright Chromium, có assertion trên kết quả Healthy. Bộ case dùng chung môi trường do chính lượt chạy tạo và xóa môi trường đó khi kết thúc. Không đọc dữ liệu ứng dụng của người dùng.

Phản hồi tại biên AI provider là fixture cố định. Bộ test kiểm tra xử lý/routing/persistence/execution của agent, không đo chất lượng suy luận của model thật. Không gọi provider thật và không cần GitHub secret AI. Các chức năng performance/security/exploratory chỉ được kiểm tra ở mức analysis workflow; không phải load test hay penetration test. Unit-test code được kiểm tra cú pháp để review, không tự thực thi proposal.

Case repair bắt đầu từ một browser run **thất bại thật** trên locator `obsolete-status`, sau đó sửa locator và giữ nguyên assertion `Healthy`. AGENT-N04 chủ động tạo sai kỳ vọng HTTP 201 trong khi server trả 200: case chức năng PASS khi agent báo đúng run FAILED và result FAIL. Những run âm có chủ đích được lưu đầy đủ, không bị đổi thành product PASS.

## GitHub Actions

Workflow [ci.yml](../.github/workflows/ci.yml) có hai job:

1. `Build and regression checks`: build và chạy bộ regression hiện có.
2. `Playwright agent cases and HTML report`: cài runner/Chromium, typecheck và **thực thi** 30 case qua `npm run test:agent --prefix browser_runner`.

Job case không phụ thuộc kết quả job regression, nên cả hai có thể chạy trên cùng commit. Push nhánh `aoce/**` trigger workflow. Mỗi job dùng runner riêng và thư mục dữ liệu mới ở `runner.temp`.

Gate yêu cầu catalog có đủ mọi function trong registry, ID duy nhất, mọi scenario có implementation, bước và oracle không rỗng. Phải thực thi đủ 30 case, không FAIL/ERROR/SKIP/expected-failure và có đủ file evidence. Không retry tự động hoặc sinh lại case bằng AI trong CI. Không có browser, thiếu case, setup lỗi hoặc artifact thiếu đều không được coi là PASS.

Artifact `playwright-report-<run-id>-<attempt>` giữ 7 ngày và được upload bằng `always()` cả khi test FAIL:

- `html/index.html` và `html/data/`: HTML report gốc do Playwright tạo; có bộ lọc Passed/Failed/Skipped, thời gian, bước, lỗi, response và các file đính kèm.
- `results.json`, `junit.xml`: reporter JSON và JUnit gốc của Playwright.
- `catalog.json`: bộ case đã chọn trước khi chạy.
- `manifest.json`, `summary.md`: đối chiếu đúng commit/catalog, kết quả từng ID và đủ evidence; bảng kết quả cũng hiển thị trong GitHub Actions summary.
- `test-results/`: trace, screenshot và video của Playwright khi case thất bại; response và case definition được đính kèm trong HTML report.
- `browser/`: run/results của target synthetic, generated specs, screenshot, trace và video do runner xuất.

Manifest ghi rõ `workspace_data_imported=false`, `model_mode=fixture`, `actual_provider_calls=0`. Lỗi setup trước khi runner bắt đầu được ghi BLOCKED với executed=0. Cleanup/evidence validation lỗi làm run thất bại kể cả khi assertion đã pass.

Trong GitHub Actions, mở run → **Artifacts** → tải `playwright-report-...` → giải nén. Chạy:

```powershell
npx playwright show-report <thu-muc-giai-nen>/html
```

Mở URL mà lệnh in ra để lọc Passed/Failed hoặc xem chi tiết case. GitHub artifact không trực tiếp host HTML; tải và chạy `show-report` giúp xem cả attachments/trace. Nếu dependency/setup lỗi trước khi Playwright bắt đầu thì artifact ghi BLOCKED, không thể có HTML report của những case chưa chạy.

## Chạy local

Sau khi build `browser_runner` và cài Chromium, chạy trong PowerShell:

```powershell
npm run test:agent --prefix browser_runner
python -m scripts.verify_playwright_report
npm run report:agent --prefix browser_runner
```

Kết quả nằm trong `output/playwright/agent-cases/`, không commit. Playwright tự cấp thư mục DATA_DIR/IMPORT_ROOT trong hệ thống tạm cho fixture, không tái sử dụng server đã có. Runner Python cũ `scripts.ci_agent_cases` vẫn có thể chạy riêng để chẩn đoán, CI job chức năng dùng Playwright Test.

Các test gate chạy bằng `python -m unittest discover -s tests -p test_playwright_report.py -v` và `python -m unittest discover -s tests -p test_ci_agent_cases.py -v`. Gate đọc kết quả execution gốc của Playwright và từ chối thiếu case, skip, expected-failure, retry hoặc ID trùng. Không chuyển kết quả unittest cũ thành Playwright report.
