# Techla Spa — Billing Bridge 0.4 (TÙY CHỌN từ Apify Tools v2.7)

**Không phải điều kiện bắt buộc để quét lead.** Apify Tools v2.7 sử dụng trực tiếp kết nối Apify App đang có, với giới hạn phí ở từng lần chạy (`maxTotalChargeUsd` hoặc `maxItems` tùy mô hình giá). Không cần triển khai Render hay cung cấp thêm token để bắt đầu một lượt Actor đã được duyệt và giới hạn phí.

Mã nguồn Bridge trong thư mục này vẫn được giữ **chỉ để cung cấp chức năng xem hạn mức bổ sung**, nếu chủ tài khoản chủ động yêu cầu. Mã không tự chạy khi cài plugin.

## Chỉ triển khai nếu cần kiểm tra billing bổ sung

1. Tạo HTTPS Web Service cho Dockerfile trong thư mục này, tách khỏi Apify App đang kết nối.
2. Trong secret manager của host (không đưa vào chat/GitHub/Sheets) nhập `MCP_ACCESS_TOKEN`, `APIFY_TOKEN_HUNG`, `APIFY_EXPECTED_USERNAME_HUNG`, `APIFY_LINK_ID_HUNG` và biến tương tự cho tài khoản khác nếu cần. Mặc định `APIFY_ALLOW_PAID_USAGE=false`.
3. Kết nối `/mcp` bằng Bearer token qua giao diện quản trị, kiểm tra `/health`, `initialize`, `tools/list`, `tools/call` với đúng account alias và `link_id`.
4. Phân biệt mock test, host triển khai, tài khoản đã kết nối, và dữ liệu billing thực đã kiểm chứng; đừng dùng kết quả mock để tuyên bố còn tiền.

Kết quả Bridge chỉ mang tính tư vấn; không phải số dư nạp chắc chắn, phê duyệt chi tiêu, hay khóa giao dịch ngân sách. Chạy Actor có phí qua Apify App vẫn phải có trần riêng mỗi run, ledger chi phí chung và kiểm soát không chạy đồng thời. Không yêu cầu token hoặc ảnh chụp Billing để bắt đầu quy trình trực tiếp nếu API có thể áp dụng trần phí phù hợp.
