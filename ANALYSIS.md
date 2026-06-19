# Phân tích kết quả Benchmark Hệ thống Bộ nhớ AI Agent

Tài liệu này phân tích chi tiết kết quả thử nghiệm hiệu năng giữa **Baseline Agent** (chỉ có bộ nhớ ngắn hạn trong cùng phiên) và **Advanced Agent** (kết hợp bộ nhớ ngắn hạn, hồ sơ bền vững `User.md` và nén bộ nhớ `Compact Memory`).

---

## 1. Vì sao Advanced Agent có Recall tốt hơn Baseline Agent?

* **Hồ sơ bền vững (`User.md`)**: Advanced Agent có cơ chế trích xuất các thông tin ổn định (Facts) từ người dùng (như tên, nghề nghiệp, nơi ở, phong cách...) và ghi trực tiếp xuống file vật lý `User.md` ở ổ đĩa. Khi bắt đầu một thread hoàn toàn mới (cross-session), Advanced Agent luôn đọc file này và nạp vào ngữ cảnh hệ thống (System Prompt).
* **Baseline Agent quên chéo phiên**: Baseline Agent chỉ lưu lịch sử hội thoại trong bộ nhớ ngắn hạn (RAM) của từng thread ID cụ thể. Khi truy vấn thông tin ở một thread ID mới, Baseline Agent không có bất kỳ thông tin nào và trả về kết quả mặc định (không biết).
* **Kết quả**: Điều này giúp Advanced Agent đạt điểm recall chéo phiên rất cao (**96.4%** trong kiểm thử chuẩn và **100.0%** trong stress test), trong khi Baseline Agent đạt **0.0%** vì hoàn toàn quên thông tin cũ.

---

## 2. Vì sao Advanced Agent có thể tốn token hơn ở hội thoại ngắn?

* **Chi phí cố định nạp Profile**: Ở các hội thoại ngắn (chỉ 1-2 lượt chat đầu), Advanced Agent luôn phải đọc và gắn toàn bộ nội dung của file `User.md` cộng với các đoạn tóm tắt hội thoại cũ (nếu có) vào System Prompt.
* **Chi phí phân tích trích xuất (Fact Extraction)**: Mỗi khi nhận tin nhắn mới từ người dùng, Advanced Agent phải thực hiện phân tích để lọc thông tin mới và cập nhật `User.md`.
* **Kết quả**: Lượng ngữ cảnh cố định được mang theo này khiến tổng số `Prompt tokens processed` của Advanced Agent cao hơn Baseline Agent khi hội thoại còn ngắn (Standard Benchmark: 26,466 tokens của Advanced so với 16,777 tokens của Baseline).

---

## 3. Vì sao Compact giúp Advanced Agent có lợi thế ở hội thoại rất dài?

* **Giới hạn phình của hội thoại (Context Window)**: Ở Baseline Agent, mọi tin nhắn cũ đều được giữ nguyên văn và gửi lại đầy đủ lên LLM ở các lượt sau. Chi phí token của Baseline tăng tiến theo hàm số bậc hai (quadratic growth) theo số lượt hội thoại.
* **Tự động nén (Compaction)**: Advanced Agent theo dõi lượng token trong phiên chat. Khi vượt ngưỡng (ví dụ: `1000` tokens), cơ chế Compact Memory Manager sẽ gộp tất cả các tin nhắn cũ hơn ngoài lượng tin nhắn cần giữ lại (`keep_messages`) và tóm tắt chúng thành một chuỗi ngắn gọn.
* **Kết quả**: Trong stress test với chuỗi hội thoại cực dài, Advanced Agent thực hiện **22 lần nén**, giúp loại bỏ sự phình to của prompt ngữ cảnh, ngăn chặn hiện tượng tràn ngữ cảnh (context overflow) và kiểm soát chi phí token trên mỗi lượt chat.

---

## 4. Tốc độ tăng trưởng của file bộ nhớ và các rủi ro đi kèm

* **Tốc độ tăng trưởng**: File bộ nhớ `User.md` tăng trưởng theo số lượng thông tin/sự kiện độc lập mới được học từ người dùng (trong standard test tăng thêm **220 bytes** và stress test tăng **183 bytes**). Do chỉ lưu trữ thông tin ở dạng key-value cô đọng (facts) thay vì toàn bộ lịch sử chat, kích thước file tăng trưởng rất chậm và có kiểm soát.
* **Các rủi ro đi kèm**:
  * **Trích xuất sai thông tin (False Extraction)**: Heuristic regex hoặc LLM trích xuất có thể hiểu lầm các câu hỏi nghi vấn, giả thuyết hoặc trò đùa của người dùng thành các sự thật cần lưu giữ (ví dụ: đùa chuyển nghề làm Product Manager).
  * **Phình to dài hạn**: Dù tăng trưởng chậm, nếu người dùng tương tác liên tục nhiều năm, file profile vẫn sẽ phình to và làm chậm thời gian tải prompt.
  * **Độ trễ và đồng bộ**: Ghi file ổ đĩa liên tục trên hệ thống lớn có thể tạo ra nút thắt cổ chai về I/O hoặc xung đột đồng thời ghi (race conditions).

---

## 5. Giải pháp khắc phục đề xuất
* **Confidence Threshold**: Thiết lập bộ lọc hoặc yêu cầu LLM xác nhận độ tin cậy của thông tin trước khi cập nhật.
* **Memory Decay (Suy hao bộ nhớ)**: Tự động loại bỏ hoặc lưu trữ các thông tin cũ/ít khi được người dùng hoặc hệ thống gợi nhớ lại.
* **Conflict Handling (Đã triển khai)**: Tự động phát hiện đính chính từ người dùng để thay thế giá trị cũ bằng giá trị mới thay vì ghi đè song song cả hai.
