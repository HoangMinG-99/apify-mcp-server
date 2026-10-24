# Techla Spa · Apify Billing Bridge 0.4 — triển khai và nghiệm thu

**Đây là mã nguồn máy chủ MCP chỉ đọc, không tự chạy khi cập nhật plugin.** Nó không dùng chung token OAuth mà ChatGPT đã cấp cho Apify App.

## Triển khai độc lập

Dùng nguồn `skills/apify-actors/assets/billing-bridge/` trong plugin, hoặc đồng bộ lên nhánh riêng của `HoangMinG-99/apify-mcp-server` (không ghi đè Apify MCP chính). Trên Render, tạo Docker Web Service, đặt root directory đúng thư mục chứa Dockerfile, chọn HTTPS và triển khai. Không được đánh dấu `DEPLOYED` trước khi URL `/health` thực sự trả lời.

Qua secret manager của host (không qua chat) cấu hình:

- `MCP_ACCESS_TOKEN`: chuỗi ngẫu nhiên mạnh bảo vệ API `/mcp`.
- `APIFY_TOKEN_HUNG`: token được ủy quyền cho tài khoản Apify muốn kiểm tra.
- `APIFY_EXPECTED_USERNAME_HUNG`: username thật từ tài khoản Apify đó; không suy diễn từ tên nhãn GPT.
- `APIFY_LINK_ID_HUNG`: ID kết nối Apify trong GPT đúng với tài khoản tương ứng.
- `APIFY_ALLOW_PAID_USAGE=false`: mặc định chỉ cho phép xét phạm vi credit miễn phí. Chỉ thay đổi khi chính sách tài chính cho phép riêng, có ledger và hard cap.

Có thể thêm bộ biến môi trường tương tự cho tài khoản khác (`_KIN`, `_HUY`,...). Secrets các tài khoản được phân tách. Không sử dụng môi trường public logs để in access token; không đẩy `.env` thật lên GitHub.

Kết nối endpoint `https://<your-host>/mcp` vào công cụ MCP/Plugin qua giao diện có kiểm soát quyền, với header Bearer `MCP_ACCESS_TOKEN`. Không yêu cầu người dùng gửi token trong ChatGPT. Nếu chưa có app/host connector tương ứng, cần chủ tài khoản hoàn thành kết nối một lần trong giao diện quản trị.

## Nghiệm thu thực (không chạy Actor)

1. `GET /health` phản hồi từ host đã triển khai, không chỉ từ môi trường test.
2. `POST /mcp` không Bearer phải trả 401. Với Bearer hợp lệ, `initialize`, `tools/list` có `get_apify_account_usage` và `tools/call` chạy được.
3. `get_apify_account_usage` nhận đủ `account`, `link_id`, `planned_usd`, `phase_remaining_usd`, `campaign_remaining_usd` và lấy dữ liệu thông qua API Apify. `phase_remaining_usd` / `campaign_remaining_usd` phải trích từ ledger đang được phê duyệt, không dùng ví dụ giả định.
4. Xác minh `apify_username`, `verified_at`, `usage_cycle`, `monthly_hard_limit_usd`, `free_credit_remaining_estimate_usd`, kết quả PASS/BLOCKED và xử lý sai tài khoản.
5. **Không dùng kết quả PASS như phê duyệt thanh toán.** Ngân sách giai đoạn/tổng cần được giữ và cập nhật ngoài API này. Chạy tuần tự hoặc dùng ledger có khóa giao dịch. Hard cap từng Actor phụ thuộc mô hình giá và phải được kiểm tra riêng.
6. Chỉ khi live billing đạt mới được đề xuất kiểm thử Actor nhỏ với quyền của người dùng; phải có hậu kiểm actual cost, dataset, dedupe, CRM.

## Kiểm thử mã nguồn offline

`pip install -r requirements.txt && python -m pytest -q test_server.py`

Các bài test sử dụng giả lập thông tin Apify, không chứng minh API token hoạt động hoặc host thực. Nếu host trả 401/403, kiểm tra token qua secret manager; tuyệt đối không đăng token trong chat.

## Cảnh báo về hạn mức

`monthly_hard_limit_usd` là giới hạn sử dụng, không phải số dư đã nạp. `monthly_plan_credit_usd` là credit trong plan; `free_credit_remaining_estimate_usd` là **ước lượng**, có thể khác số dư tín dụng thực tế trong Billing Console. Khi các nguồn usage không đồng nhất, cầu kết nối chọn `BLOCKED` (fail closed). API cầu chỉ đọc và không có khóa ngân sách; các Actor chạy đồng thời vẫn có thể gây vượt tổng ngân sách nếu không có cơ chế đặt chỗ thực.

Xem `references/remediation-v2.6.md` để hiểu kết quả nghiệm thu sau 2.5.1.
