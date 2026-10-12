"""Synthetic UI fixture in a separate, disposable QA database."""
import json
import argparse
from testagent import db

parser = argparse.ArgumentParser()
parser.add_argument('--state', choices=['completed', 'running', 'failed'], default='completed')
state = parser.parse_args().state

db.init_db()
db.execute('UPDATE projects SET name=? WHERE id=?', ('QA · kiểm tra sub-agent', 'qa-project'))
db.execute('UPDATE tasks SET prompt=? WHERE id=?', ('Lập kế hoạch kiểm thử từ đánh giá bảo mật và hiệu năng — dữ liệu mô phỏng', 'qa-parent'))
route = {'function': 'test_plan', 'reason': 'Tổng hợp các phân tích độc lập thành kế hoạch kiểm thử. Đây là fixture giao diện, không phải kết quả gọi model.', 'source': 'ai'}
output = {'kind': 'analysis', 'skill_id': 'test_plan', 'skill_file': 'test-plan.md', 'summary': 'Dữ liệu mô phỏng để kiểm tra task con và phần tổng hợp. Không có test nào được thực thi.', 'recommendations': ['Xác nhận yêu cầu và dữ liệu trước khi tạo automation.']}
db.execute('UPDATE tasks SET orchestration=?, summary=? WHERE id=?', (json.dumps(route, ensure_ascii=False), json.dumps(output, ensure_ascii=False), 'qa-parent'))
db.execute('UPDATE tasks SET status=?, error=? WHERE id=?',
           ('COLLABORATING' if state == 'running' else 'FAILED' if state == 'failed' else 'COMPLETED',
            'Dữ liệu mô phỏng: cần xử lý lỗi task con trước khi tổng hợp.' if state == 'failed' else '', 'qa-parent'))
for function, status, summary, error in (
    ('security', 'COMPLETED', 'Ưu tiên xác nhận quyền truy cập và việc kết thúc phiên đăng nhập.', ''),
    ('performance', 'FAILED' if state == 'failed' else 'ANALYZING' if state == 'running' else 'COMPLETED',
     '' if state != 'completed' else 'Chuẩn bị workload 2.000 người dùng đồng thời, xác nhận ngưỡng độ trễ và tỷ lệ lỗi.',
     'Dữ liệu mô phỏng: provider chưa hoàn tất phần phân tích hiệu năng.' if state == 'failed' else ''),
):
    task_id = 'qa-' + function
    child = {'kind': 'analysis', 'summary': summary, 'recommendations': ['Xác nhận ngưỡng chấp nhận.'], 'findings': [{'title': 'Phân biệt bằng chứng với giả thuyết', 'detail': 'Chưa có lượt chạy kiểm thử; những điểm này là đề xuất để chuẩn bị test plan.', 'severity': 'info', 'evidence_ids': []}]} if summary else None
    db.execute('''INSERT OR REPLACE INTO tasks
        (id, project_id, parent_task_id, prompt, intent, skill_file, status, summary, error, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
               (task_id, 'qa-project', 'qa-parent', 'Phân tích phạm vi ' + function + ' từ dữ liệu đã cung cấp và ghi rõ thông tin còn thiếu.', function,
                function + '.md', status, json.dumps(child, ensure_ascii=False) if child else '', error, db.now()))
print('Updated isolated fixture with completed and failed sub-agents.')
