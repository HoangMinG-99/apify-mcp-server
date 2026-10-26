# Techla Spa — Apify Tools v2.7.0

Bản nguồn của plugin cá nhân Techla Spa [Apify Tools v2](https://chatgpt.com/plugins/plugins_6acd0feabbdc819191d1440ab3f5d5ae), release `pluginrel_6adeb57c19248191becd5f7e5b33d5a4`, đồng bộ từ Plugin Creator ngày 26/10/2026.

**Quy trình đang áp dụng:** Apify App đã liên kết → chọn đúng `link_id` → tra Actor/schema/giá → kiểm tra phạm vi CRM và sổ ngân sách → chạy Actor với hạn mức phí ngay tại `callOptions` → lấy dataset thật → lọc trùng → cập nhật CRM và nhật ký phí.

- **Không bắt buộc** Billing Bridge, Render hay token Apify riêng để chạy Actor có giới hạn chi phí qua Apify App được kết nối.
- Trần đã phê duyệt cho C03: tối đa **5 USD/lượt**, **40 USD/toàn chiến dịch**, chỉ khi sổ chi phí/reservation hiện hành cho phép. Bắt đầu với run nhỏ khoảng 0,50 USD; chạy tuần tự.
- Actor pay-per-event: bắt buộc `callOptions.maxTotalChargeUsd`. Actor pay-per-result: bắt buộc `callOptions.maxItems`, giới hạn input và tính trần phí phù hợp mô hình giá; không được dùng sai loại cap.
- Nếu Apify từ chối do hết hạn mức hoặc điều kiện nhà cung cấp, báo đúng lỗi; không chuyển tài khoản nhằm né lệnh chặn. Không suy diễn `maxTotalChargeUsd` là số dư tài khoản.
- Chỉ báo lead nóng khi có bằng chứng nhu cầu hoặc Sales xác nhận. Hồ sơ doanh nghiệp/cá nhân phải có nguồn, trạng thái kiểm chứng và chống trùng.

**Dọn bản cũ:** PR trước chứa một dự án Render/Billing Bridge v2.6 tách rời ở `/techla-billing-bridge/` và `/render.yaml`. Các tệp này đã được loại khỏi PR. Bộ source tùy chọn của Billing Bridge trong **package plugin 2.7** vẫn được giữ ở `skills/apify-actors/assets/billing-bridge/` làm tham khảo, **không phải thành phần bắt buộc và không tự triển khai**.

**Phân biệt nguồn:** bản GitHub này là snapshot để kiểm soát phiên bản; việc cập nhật riêng trên GitHub không tự phát hành plugin ChatGPT. Phiên bản đang cài đã được xuất bản độc lập qua Plugin Creator.

Không đưa token, thông tin lead cá nhân hay số liệu nhạy cảm lên repository công khai.
