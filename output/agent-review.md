# Kết quả rà soát TestAgent — 06/10/2026

Đã rà soát runner, schema, skill registry, orchestration và bàn giao sub-agent. Bản gốc có 102 test đạt; các lỗi dưới đây được phát hiện bằng test bổ sung rồi sửa trực tiếp.

| Vấn đề | Thay đổi | Kiểm tra |
|---|---|---|
| Giao lại cùng run/task ID tạo thêm request, kết quả hoặc lượt model | Nhận việc bằng UPDATE SQLite có điều kiện theo trạng thái; chỉ một worker được thực thi | Giao lại sau hoàn tất và giao đồng thời khi worker đầu còn chạy |
| Project hoặc case thay đổi sau khi xếp hàng | Kiểm tra lại production, readiness, case ownership, mode và workers trước mọi request | Đổi environment, xóa payload, sửa tùy chọn sau admission |
| Summary hỏng làm run mắc kẹt hoặc handler lỗi lần nữa | Ghi trạng thái FAILED và lỗi kể cả khi summary không phải JSON object hợp lệ | JSON lỗi; danh sách case rỗng; mode/workers không hợp lệ |
| ID case/run-result/nguồn ngoài dự án được lưu nhầm thành source_ids | Chỉ nhận nguồn thuộc dự án và đã có trong ngữ cảnh | Nguồn hợp lệ, nguồn ngoài dự án và run-result ID trong cùng output |
| Lead được phép trích ID chỉ có ở phần context đã lược bỏ của helper | Chỉ mở rộng tập ID bằng các trích dẫn thực sự có trong handoff | Helper có một bằng chứng hiển thị và một bằng chứng không được bàn giao |
| Model trả trường lạ hoặc nhiều execution payload trong cùng case | Schema từ chối trường ngoài hợp đồng; automation/api_request/unit_test_code loại trừ nhau; prompt nói rõ các trường là lựa chọn thay thế | Contract tests và live generation |
| File skill rỗng hoặc thiếu được xử lý không nhất quán | Dùng chung một reader cho role, shared rules và subagent-handoff | Kiểm tra file thiếu/rỗng và phủ đủ 23 Markdown files |
| Executor helper phụ thuộc hoàn toàn vào routing để chặn plan sai | Runtime kiểm tra tối đa ba vai trò analysis khác nhau, parent cùng dự án, không đệ quy, khác lead; plan rỗng không có side effect | Runtime guards và 11 helper workflow tests |

Đã bổ sung `scripts/verify_agents.py` và 30 test workflow có tên riêng cho 19 skill/11 sub-agent. Mỗi bài dùng database tạm và ứng dụng HTTP local; browser và API chạy thật. Repair bắt đầu bằng một run Chromium lỗi do locator cũ, rồi giữ nguyên assertion khi sửa. Case API được model sinh được chạy lại trên HTTP server thật. Unit code được parse để review.

Kết quả tự động: **150/150 test đạt**. Browser runner và frontend đều build thành công. Log: [unittest-result.txt](unittest-result.txt). Ma trận với model mô phỏng: [agents-check-result.json](agents-check-result.json).

Lượt model thật dùng kết nối hiện có **Codex / gpt-6.1-sol / high** đã hoàn tất: **30/30 đạt**, gồm đủ **19 skill và 11 sub-agent**, không có lỗi. Kết quả từng mục, số lượt model và thời gian nhóm helper có trong [agents-live-result.json](agents-live-result.json). API case do model sinh đã chạy thật và đạt; unit code đã parse thành công. Lượt đầu phát hiện schema minh họa dễ khiến model trộn UI/API, cùng lỗi encoding console Windows; prompt và script đã được chỉnh và kiểm tra lại thành công. Giữ bằng chứng lượt đầu trong [agents-live-initial-20261006.json](agents-live-initial-20261006.json).

Các nhóm helper trong script dùng kế hoạch cố định để kiểm tra đủ vai trò; mục orchestrator riêng sử dụng routing của model. Bộ test orchestration kiểm tra fan-out song song, giới hạn semaphore, pin provider/model/effort, giữ đúng case/run scope, lược bớt context và không báo hoàn tất giả khi helper lỗi.

Đây là kiểm tra agent trên fixture, không phải xác nhận chất lượng mọi ứng dụng đích hoặc mọi provider. Unit generation tạo code để review; performance/security/exploratory vẫn tạo phân tích. BackgroundTasks chưa có queue bền vững/resume: việc chống giao trùng không tự tiếp tục công việc khi backend bị dừng. Schema chặt hơn sẽ báo lỗi với output thừa trường hoặc case cũ khai báo đồng thời browser/API.

Chạy lại:

```powershell
python -m unittest discover -s tests -v
python -m scripts.verify_agents
python -m scripts.verify_agents --live
python -m scripts.verify_agents --live --skills gen_testcase --skip-helpers --output output/agents-live-retry.json
```
