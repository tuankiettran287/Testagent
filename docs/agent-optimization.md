# Agent Optimization và CI Execution

Áp dụng ngày 2026-10-12 cho TestAgent trong repo này. Nguồn: [AOCE content](../L3_AIQE_AOCE_course_content_vi.md), Units 1–7, và [AOCE exercises](../L3_AIQE_AOCE_exercises_vi.md), đặc biệt hard gates U1/U2/U5/U6. Các packets PortalLite trong tài liệu vẫn là synthetic; không lấy số liệu packet làm kết quả của TestAgent.

## Phân tích và quyết định

Baseline `dd7373d`: `python -m unittest discover -s tests -v` chạy 150 tests, OK, 118.564 giây trên Windows/Python 3.13.11. Repo đã có 19 vai trò chính, 11 analysis-helper roles, registry allowlist, production guard, cô lập browser, giữ assertion khi repair và ngăn thực thi lặp cùng run ID. Các controls đó được giữ lại.

| Finding từ code | Thay đổi và lý do |
|---|---|
| `compact_snapshot` đưa nguyên element objects vào model; nhiều null/empty và locator expression lặp với suggested_target | Bỏ thuộc tính absent và expression có thể dựng lại. Giữ toàn bộ text/ARIA, mọi element, scope, false/zero, ID và literal oracle. Không giảm bằng cách cắt chuỗi. |
| `_source_context` cắt chunk retrieval tại 2000 ký tự mặc dù chunk đã bounded 2400 | Gửi đủ chunk đã chọn để giữ oracle ở cuối. Thay đổi này có thể tăng source-context bytes; ưu tiên correctness. Chưa thay thuật toán retrieval. |
| Lỗi action được gửi lại model tối đa ba nhóm mà không có trạng thái ghi | Runner trả failed_action/mutation_outcome. Trước dispatch mà locator ambiguous: not_started. Lỗi trong/ sau mutation: unknown. Controller dừng NEEDS_INPUT để reconcile; missing metadata/transport loss cũng không cho phép retry. |
| Không có deadline toàn vòng observe/act | Admission budget UI_TIMEOUT_SECONDS, mặc định/tối đa 1200 giây; kiểm tra trước/sau model và trước browser dispatch. In-flight model/browser vẫn có timeout riêng; đây không phải cơ chế preemption. |
| Khó xác định chính xác prompt/context đã dùng | Manifest version, task/role/environment, prompt hash, source excerpt hashes, case/run refs, turn/time/observation hash. Summary thành công lưu thêm final-generation prompt/request hash. Hash giúp truy vết, không chứng minh requirement đúng. |
| Chưa có GitHub Actions workflow | Workflow push/PR/manual với Python 3.13, Node 22, npm locks, Python CI snapshot, action commit pins, build cả hai TypeScript projects và strict verification. |

Read/pre-action recovery được giới hạn một lần; lần lỗi thứ hai dừng. Không nới oracle, dùng `.first()` hoặc `force`, không retry write chỉ vì timeout. Chưa có lookup/cleanup API cho arbitrary target: reconcile dữ liệu thật cần owner xử lý trước tác vụ mới. Browser reset chỉ xóa session.

## Benchmark và quality gate

`python -m scripts.benchmark_context` replay ba snapshot synthetic cho mỗi cấu hình trên cùng input hashes. Chỉ thay structural context selector; không có model call. Mỗi mẫu kiểm tra toàn bộ giá trị meaningful, element count và text/ARIA/scope trước khi tính bytes.

| Chỉ số | Baseline | Optimized |
|---|---:|---:|
| Median serialized snapshot bytes | 5836 | 2876 |
| Structural quality gate | 3/3 | 3/3 |
| Tổng snapshot bytes giảm | — | 50.72% |

Đây là bytes của snapshot, không phải toàn prompt/request, billed tokens, chi phí hay model-quality benchmark. Manifest thêm metadata vào request; source chunks đầy đủ có thể tăng kích thước. Billed-token/monetary savings là UNKNOWN. Timing script chỉ đo preprocessing, không chứng minh end-to-end latency cải thiện. Sample nhỏ/synthetic chưa cho phép kết luận production reliability.

Regression mới bao gồm oracle sau ký tự 2000, scoped dialog, false/zero, negative controls sai department/khác run ID, zero-tests, selected-but-unexecuted, skip/expected-failure, prompt/source linkage, unknown write, missing metadata, transport timeout, recovery budget và deadline. Real browser checks xác nhận ambiguous locator chưa ghi và lỗi sau một mutation không bị coi là not_started.

## Coverage và CI contract

Không dựng thêm PortalLite hoặc tự nhận F01/F02/F03 đã chạy. Map sang các flow có thật của TestAgent:

| Luồng | Oracle chính | Evidence |
|---|---|---|
| Route và analysis | Role allowlist, pinned provider/model, source IDs hợp lệ, finished run đúng project | Orchestrator/model-contract/optional-context tests |
| Generate/build/repair browser | Một case cho mỗi selected ID; giữ expected/original assertions; final execution có assert | UI/skill-workflow tests, real Chromium + synthetic status portal |
| Deterministic suite/API | Case readiness, same-origin, production guard, chạy cùng ID một lần, counts/results khớp | Suite-execution tests, HTTP thật trên loopback |
| Recovery | Không replan sau unknown write; một safe recovery; deadline chặn dispatch | Controller regression và runner browser tests |
| Context provenance | Giữ oracle/scope; sai department/run làm hash khác; matching task/prompt | Context và UI manifest tests |

Workflow `.github/workflows/ci.yml` chạy khi push `master`/`aoce/**`, PR và dispatch. `contents: read`, timeout 20 phút, concurrency theo ref, không cancel run đang chạy. Các run chỉ dùng app/SQLite/ports tạm riêng nên không cần lock shared environment. Không có live credentials, external target hay actual model call trong CI; fixture responses được ghi nhãn rõ.

`scripts.ci_verify` preflight Chromium, discover và execute toàn bộ tests. Gate yêu cầu selected > 0, executed = selected, không failure/error/skip/expected-failure. Discovery không được tính là execution. JUnit/log/manifest luôn được ghi khi harness chạy; setup failure trước harness có BLOCKED manifest do workflow tạo. Job không suppress exit code. Upload dùng always(), retention 7 ngày, missing artifact là lỗi.

Evidence artifact `aoce-ci-<run>-<attempt>` gồm code revision, trigger, timestamps, versions/instruction hashes, per-test results/durations, benchmark, và status-portal runs/results nối tới generated spec, screenshot, trace/video trước khi temporary fixture được xóa. Đây là dữ liệu synthetic không có live auth. Cleanup status theo fixture teardown; lỗi teardown cần review. Force cancellation/runner loss vẫn có thể mất evidence; always() không bảo đảm trong mọi sự cố.

Chưa bật schedule. Theo [GitHub workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), dispatch/schedule cần workflow trên default branch; push feature branch dùng để kiểm chứng CI ngay. Manual/push run không chứng minh scheduled trigger đã chạy. [GitHub artifacts](https://docs.github.com/en/actions/tutorials/store-and-share-data) là nguồn đối chiếu upload/retention. [Playwright retries](https://playwright.dev/docs/test-retries) là nguồn phân biệt first-pass/flaky; workflow không có automatic retry để che failure.

## Review, rủi ro và rollback

| Quyết định | Căn cứ |
|---|---|
| Accept structural compaction | Giữ đầy đủ semantic values và có negative controls; tránh cắt text/ARIA. |
| Reject quảng cáo giảm token/cost 50.72% | Chỉ đo snapshot bytes, không có usage metadata hoặc rate thực tế. |
| Accept conservative unknown-write stop | Tool transport/timeout không chứng minh write chưa xảy ra. |
| Reject model generation mỗi lần CI | Reviewed deterministic tests đủ cho regression và không yêu cầu AI credentials trên hosted runner. |
| Giữ schedule chưa bật | Chưa có live environment/accounts/ownership/reconciliation contract để chạy định kỳ. |

Owner dưới đây là đề xuất cho maintainer/QA, không khẳng định người nào đã nhận việc.

| Risk | Control/detection | Proposed owner và next evidence | Residual risk |
|---|---|---|---|
| False savings claim từ synthetic bytes | Benchmark có mode/unknown fields; review report | QA: thu ≥3 actual usage/output samples/config nếu cần đo model cost | Chưa đo live model quality/cost |
| Snapshot runner đã cắt 100 elements/text 8000/ARIA 12000 | Giữ nguyên mọi dữ liệu đã nhận; ghi giới hạn | Maintainer: thiết kế scoped retrieval nếu target phức tạp | Oracle ngoài snapshot vẫn có thể thiếu |
| Retrieval không chọn đúng requirement chunk | Không cắt thêm excerpt; source hashes | QA: cung cấp requirement/flow catalog cụ thể | Hash không phát hiện thiếu nguồn chưa retrieve |
| Unknown write tạo record cần xử lý | Freeze/reconciliation notice, không blind retry | Target owner: owned lookup/cleanup helper theo contract | Chưa có generic reconciler, dữ liệu thật cần xử lý riêng |
| Runner cancellation làm mất cleanup/evidence | Temp fixture ownership; artifact upload always | Maintainer: kiểm tra run kết thúc bất thường | Không có reconciler ngoài job cho external app |
| Hosted CI thiếu live model evidence | Ghi fixture mode, actual_provider_calls=0 | QA: chạy `verify_agents --live` riêng nếu cần và giữ usage UNKNOWN khi provider không export | Passing fixtures không chứng minh model behavior |
| Schedule không chạy từ feature branch | Không bật schedule, giữ push run URL/revision | Maintainer: merge sau review; thêm schedule khi có owner/environment | Chưa có scheduled execution evidence |

Rollback: revert commit thay đổi agent và workflow trên branch đang triển khai, build lại browser_runner, chạy regression. Đảo code không đảo side effect; trước khi rerun target thật phải reconcile owned records của tác vụ bị dừng. Tài liệu bài học và `output/agents-live-result.json` cũ được giữ làm lịch sử, không dùng chúng làm evidence cho revision mới.
