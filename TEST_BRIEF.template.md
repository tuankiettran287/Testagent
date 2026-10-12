# Brief kiểm thử ứng dụng

Sao chép và điền các thông tin đã biết. Đây là nguồn ngữ cảnh tùy chọn cho TestAgent, không phải cấu hình tự chạy. Không để placeholders thành dữ liệu executable; thông tin thiếu phải được ghi rõ.

## Mục tiêu

- Ứng dụng / phiên bản:
- Project / environment:
- Base URL / trang bắt đầu:
- Kết quả cần từ agent: phân tích / tạo case / tạo automation / chạy case / phân tích run.
- Tính năng và phạm vi:
- Hành vi ưu tiên, tác động khi lỗi:

## Actor và chuẩn bị

- Actor / role:
- Tài khoản test: ghi cách cung cấp phù hợp; tránh commit mật khẩu/token vào tài liệu.
- Trạng thái ban đầu:
- Dữ liệu/record cụ thể đã có:
- Bước chuẩn bị cần làm ngoài runner:
- Dữ liệu có thể thay đổi; cách phục hồi:
- Cases có dùng chung cart/account/record không:

## Quy tắc và expected results

| ID quy tắc | Điều kiện / input | Thao tác | Expected result quan sát được | Căn cứ |
|---|---|---|---|---|
| R-01 | | | | Spec / yêu cầu đã xác nhận / observation smoke |

Ghi đúng marker/URL/status đã biết. Nếu chưa biết, ghi “chưa xác định”, không đoán. Tách rule được yêu cầu khỏi hiện trạng triển khai.

## API — nếu có

- Method/path/query/body:
- Expected HTTP status và căn cứ:
- Auth/resource IDs đã chuẩn bị:
- Response fields/schema cần kiểm tra bổ sung: runner hiện chỉ assert status.
- Endpoint có side effects và cleanup ngoài runner:

## Code / thay đổi — nếu có

- Sources/repository đã import:
- File/symbol cần xem:
- Change/diff:
- Framework/test harness và fixtures đã biết:

## Case/run scope — nếu có

- Case IDs cùng project:
- Run ID cần phân tích:
- Results thực tế:
- Artifact contents đã cung cấp/xem; phân biệt với filename-only:

## Chế độ và giới hạn

- Xem automation trước (generate) hay cho phép execution (run):
- Sequential/parallel; mức workers nếu dùng parallel:
- Các hành động trong phạm vi test:
- Capability thiếu: cross-origin SSO, fixture, body/input-value/absence assertion, hoặc khác.
- Thông tin thiết yếu chưa có và người/bước cung cấp:

generate có thể vẫn fill/click khi browser agent khảo sát; chỉ bỏ qua confirmation run. Reset browser không reset dữ liệu server.

## Yêu cầu gửi agent

Viết một câu nêu mục tiêu, starting state, actor/data và dấu hiệu kết quả. Dùng ID thật khi gửi case_ids/run_id; không dán ID mẫu.

Tài liệu tham chiếu: [README](./README.md), [SRS](./SRS.md).
