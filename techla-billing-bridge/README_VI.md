# Techla · Apify Billing MCP Bridge (bản mẫu đã kiểm thử không cần tài khoản thật)

## Giải quyết vấn đề gì?

Cho ChatGPT truy vấn **usage, credit và hard limit** trên đúng tài khoản Apify qua API chính thức, không cần gửi screenshot Billing. Đây là **plugin phụ trợ mới** để đi cùng Apify Tools v2; không thay thế kết nối Apify đang dùng để chạy Actor.

### API chính thức (chỉ đọc)

- `GET https://api.apify.com/v2/users/me`
- `GET https://api.apify.com/v2/users/me/limits`
- `GET https://api.apify.com/v2/users/me/usage/monthly`

Tài liệu: https://docs.apify.com/api/v2/users-me-get; https://docs.apify.com/api/v2/users-me-limits-get; https://docs.apify.com/api/v2/users-me-usage-monthly-get

## Bảo mật

- **Không gửi hoặc lưu token Apify vào chat, Google Sheet, plugin skill hoặc GitHub.**
- Kết nối một lần: thêm Apify API token vào bí mật của nơi triển khai (Render Environment Secrets). Token cần đủ quyền đọc thông tin tài khoản/usage; nếu 403 thì không chạy.
- Cần thêm `MCP_ACCESS_TOKEN` riêng (chuỗi ngẫu nhiên đủ mạnh) để ChatGPT kết nối MCP. Cũng điền token này qua giao diện kết nối bảo mật, không gửi trong chat.
- Mã không trả token, email hoặc thông tin nhạy cảm từ `/users/me`; chỉ trả `username`, usage và hạn mức.
- Chỉ mở HTTPS trên tên miền triển khai. Không bật public MCP anonymous.

## Kích hoạt

1. Triển khai source tới nơi có thể chạy Docker và HTTPS (ví dụ Render, không bắt buộc).
2. Điền `MCP_ACCESS_TOKEN`, `APIFY_TOKEN_HUNG`, `APIFY_EXPECTED_USERNAME_HUNG` bằng secret manager. `APIFY_EXPECTED_USERNAME_HUNG` là **tên tài khoản Apify thật**, có thể khác nhãn kết nối `hùng` trong ChatGPT.
3. Kết nối endpoint `https://<host>/mcp` qua plugin/MCP với API key là `MCP_ACCESS_TOKEN`. Không thêm MCP endpoint vào Apify Tools v2 hiện tại bằng một update App-backed: Plugin Creator không cho thay đổi app binding của plugin đó. Thêm như plugin bổ trợ hoặc cập nhật nguồn gốc của app server tương ứng.
4. Gọi `get_apify_account_usage({"account":"hung","planned_usd":5,"phase_remaining_usd":5,"campaign_remaining_usd":40})`.
5. Nếu `status=BLOCKED`, không chạy Actor. Nếu `PASS`, vẫn phải gắn hard cap cho từng Actor, giữ sổ chi phí giai đoạn/tổng chiến dịch và đọc lại usage sau run.

## Phân biệt các khoản tiền

- `used_this_cycle_usd`: số Apify ghi nhận đã dùng trong kỳ.
- `free_credit_remaining_estimate_usd`: ước tính credit theo gói còn lại; có thể không phải số dư thanh toán do trợ giá/chính sách khác.
- `hard_limit_remaining_usd`: trần chi tiêu còn lại theo cấu hình tài khoản; **không có nghĩa là tiền đã nạp**.
- `bridge_available_allowance_usd`: giá trị nhỏ nhất của các giới hạn đã xác minh, bao gồm ngân sách từ Sheet. Mặc định chỉ cho phép phạm vi credit miễn phí; bật khả năng dùng phí trả thêm phải có chính sách tài chính rõ ràng.

## Tài khoản khác

Thêm bộ secret `APIFY_TOKEN_<TÊN_NGẮN>`, `APIFY_EXPECTED_USERNAME_<TÊN_NGẮN>` và `APIFY_LINK_ID_<TÊN_NGẮN>`; tool nhận `account` theo tên ngắn viết thường không dấu, ví dụ `hung2`, `kin`, `huy`. Mỗi credential được xử lý tách biệt, không tự chuyển tài khoản.

## Giới hạn hiện tại

- Chưa triển khai dịch vụ lên host thực hoặc kết nối vào ChatGPT; chưa đọc tài khoản hùng thật.
- Đây là cầu đọc usage. Nó **không chạy Actor**, **không tự chuyển Apify connection** và **không tự theo dõi các phiên chạy**.
- Không thể kiểm định scope/token của hùng trước khi chủ tài khoản hoàn tất kết nối bí mật một lần.
- Bộ kiểm thử sử dụng dữ liệu mẫu, không phát sinh phí Apify.


## Cập nhật bảo mật phiên bản 0.2

- Bắt buộc gửi `link_id` chính xác khi gọi `get_apify_account_usage`, đối chiếu với `APIFY_LINK_ID_<ALIAS>` được cấu hình trong secret manager. Nhãn `hung` không đủ để xác minh một kết nối.
- Nếu chu kỳ sử dụng trả về không bao gồm thời điểm hiện tại, hệ thống từ chối cấp phép (`BILLING_CYCLE_STALE`).
- Giá trị ngân sách âm, NaN, vô hạn hoặc thiếu trường sẽ bị từ chối.
- Ví dụ với hùng: `get_apify_account_usage({"account":"hung","link_id":"link_6adad6d22e048191a1bca6794aaaed6f","planned_usd":5,"phase_remaining_usd":5,"campaign_remaining_usd":40})`.
- Không có credential Apify thật trong mã nguồn, test hay bản ZIP.


## Production status
Nguồn GitHub là code chuẩn bị triển khai, KHÔNG phải máy chủ đã triển khai. Bắt buộc điền bí mật trong dashboard host, xác minh payload Billing thật, kiểm tra `tools/list` và `tools/call` trước khi chạy Actor có phí.
