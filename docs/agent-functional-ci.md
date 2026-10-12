# Chạy test case chức năng agent trên CI

Bộ [30 test case](../tests/agent_function_cases.json) được tạo riêng để kiểm tra TestAgent. Mỗi case có ID ổn định, bước thực hiện và kỳ vọng. Không xuất hoặc nhập SQLite, project, test case, live-result hay phiên đăng nhập có sẵn trong workspace.

## Phạm vi

| Nhóm | ID | Kiểm tra |
|---|---|---|
| Chức năng | AGENT-F01–F19 | Toàn bộ 19 chức năng trong registry: điều phối, sinh case, UI automation, builder, review, execution, repair, đọc repo, report, requirements, plan, unit, API, defect, regression, performance, security, exploratory, test data |
| Điều kiện chặn/lỗi | AGENT-N01–N08 | Case thủ công, cross-origin, case sai project, assertion thất bại, giao lại run ID, model output sai schema, generate-only, thiếu source |
| Nhập dữ liệu | AGENT-I01–I03 | Sinh document, repository ZIP và OpenAPI trong bộ nhớ, upload và xác minh indexing/retrieval |

Runner tạo một database tạm mới, mã nguồn và yêu cầu mẫu, cùng HTTP server chỉ lắng nghe loopback. Các case gọi API TestAgent qua FastAPI TestClient; task controller, SQLite, validator, HTTP request tới target và Chromium dùng code thật. Bộ case dùng chung môi trường do chính lượt chạy tạo và xóa môi trường đó khi kết thúc. Không đọc dữ liệu ứng dụng của người dùng.

Phản hồi tại biên AI provider là fixture cố định. Bộ test kiểm tra xử lý/routing/persistence/execution của agent, không đo chất lượng suy luận của model thật. Không gọi provider thật và không cần GitHub secret AI. Các chức năng performance/security/exploratory chỉ được kiểm tra ở mức analysis workflow; không phải load test hay penetration test. Unit-test code được kiểm tra cú pháp để review, không tự thực thi proposal.

Case repair bắt đầu từ một browser run **thất bại thật** trên locator `obsolete-status`, sau đó sửa locator và giữ nguyên assertion `Healthy`. AGENT-N04 chủ động tạo sai kỳ vọng HTTP 201 trong khi server trả 200: case chức năng PASS khi agent báo đúng run FAILED và result FAIL. Những run âm có chủ đích được lưu đầy đủ, không bị đổi thành product PASS.

## GitHub Actions

Workflow [ci.yml](../.github/workflows/ci.yml) có hai job:

1. `Build and regression checks`: build và chạy bộ regression hiện có.
2. `Execute generated agent test cases`: cài runner/Chromium và **thực thi** catalog qua `python -m scripts.ci_agent_cases`.

Job case không phụ thuộc kết quả job regression, nên cả hai có thể chạy trên cùng commit. Push nhánh `aoce/**` trigger workflow. Mỗi job dùng runner riêng và thư mục dữ liệu mới ở `runner.temp`.

Gate yêu cầu catalog có đủ mọi function trong registry, ID duy nhất, mọi scenario có implementation, bước và oracle không rỗng. Phải thực thi đủ 30 case, không FAIL/ERROR/SKIP/expected-failure và có đủ file evidence. Không retry tự động hoặc sinh lại case bằng AI trong CI. Không có browser, thiếu case, setup lỗi hoặc artifact thiếu đều không được coi là PASS.

Artifact `agent-functional-cases-<run-id>-<attempt>` giữ 7 ngày:

- `catalog.json`: bộ case đã chọn trước khi chạy.
- `manifest.json`: commit, catalog SHA-256, trigger/run/attempt, kết quả từng ID, thời gian, API responses và task/run references.
- `junit.xml`, `cases.log`, `summary.md`: kết quả từng case; bảng summary cũng hiển thị trong GitHub Actions.
- `browser/`: run/results của target synthetic, generated specs, screenshot, trace và video do runner xuất.

Manifest ghi rõ `workspace_data_imported=false`, `model_mode=fixture`, `actual_provider_calls=0`. Lỗi setup trước khi runner bắt đầu được ghi BLOCKED với executed=0. Cleanup/evidence validation lỗi làm run thất bại kể cả khi assertion đã pass.

## Chạy local

Sau khi build `browser_runner` và cài Chromium, chạy trong PowerShell:

```powershell
$env:DATA_DIR = Join-Path $env:TEMP 'testagent-functional-bootstrap'
$env:IMPORT_ROOT = Join-Path $env:TEMP 'testagent-functional-imports'
python -m scripts.ci_agent_cases
```

Kết quả nằm trong `output/aoce/agent-cases/`, không commit. Các test gate của catalog chạy bằng `python -m unittest discover -s tests -p test_ci_agent_cases.py -v`.
