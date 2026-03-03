# 🎬 SRT Tool Pro - Dịch Phụ Đề Hàng Loạt Bằng AI (Gemini)

![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)
![Gemini AI](https://img.shields.io/badge/AI-Google_Gemini-orange.svg)

**SRT Tool Pro** là một công cụ giao diện đồ họa (GUI) mạnh mẽ giúp bạn tự động hóa hoàn toàn quá trình dịch file phụ đề `.srt` sang nhiều ngôn ngữ khác nhau bằng sức mạnh của **Google Gemini AI**. 

Được thiết kế để giải quyết triệt để bài toán **"AI làm hỏng timecode"**, công cụ này sử dụng thuật toán bóc tách text và gán mã ID thông minh, đảm bảo cấu trúc thời gian của video luôn khớp 100% sau khi dịch.

---

## ✨ Tính Năng Nổi Bật

* 🎯 **Bảo Toàn Timecode Tuyệt Đối:** Sử dụng cơ chế gán ID (`0|||`, `1|||`) trước khi đẩy cho AI, loại bỏ hoàn toàn rủi ro AI tự ý gộp dòng, xóa dòng hay làm lệch mốc thời gian.
* 📁 **Dịch Hàng Loạt (Batch Processing):** Hỗ trợ kéo thả nguyên một thư mục chứa hàng chục tập phim. Tool sẽ tự động tạo kịch bản `.bat` để dịch một lèo.
* 🧠 **Từ Điển Thuật Ngữ (Context Box):** Cung cấp hộp văn bản để bạn ra lệnh cho AI (VD: *"Xưng hô anh-em, không dịch tên riêng"*). Bản dịch sẽ mượt mà và đúng ngữ cảnh.
* 💻 **Terminal Tích Hợp:** Chạy ngầm Gemini CLI trực tiếp trong phần mềm với giao diện theo dõi tiến trình (Loading Spinner) thời gian thực.
* 🧹 **Quét Dọn Rác:** Chỉ với 1 click, dọn dẹp sạch sẽ toàn bộ các file text trung gian (`.txt`, `_VIET.txt`, `.bat`).

---

## 🛠 Yêu Cầu Hệ Thống

Trước khi sử dụng, hãy đảm bảo máy tính của bạn đã cài đặt:
1. **Python 3.x**
2. **Gemini CLI:** Đã được cấu hình xác thực tài khoản Google (lệnh `gemini` chạy được trên terminal).
3. Các thư viện Python cần thiết.

Cài đặt các thư viện phụ thuộc:
```bash
pip install pysrt PyQt6
```
## 🚀 Hướng Dẫn Cài Đặt

**Clone kho lưu trữ này về máy:
```bash
git clone [https://github.com/thehienn3838/srt-translator-pro.git](https://github.com/thehienn3838/srt_tool_.git)
```

##📖 Hướng Dẫn Sử Dụng
Quy trình dịch thuật được tối ưu hóa chỉ với 3 bước kéo thả:
1. Trích xuất: Kéo thả file .srt (hoặc thư mục chứa nhiều file .srt) vào khung số 1. Bấm Trích xuất ra file TXT.
2. Dịch thuật AI: * (Tùy chọn) Nhập yêu cầu bối cảnh vào ô Từ Điển / Bối Cảnh.
  - Bấm nút cam ⚡ Tạo Lệnh Dịch Tự Động ở cột bên phải.
  - Ấn phím Enter tại thanh nhập lệnh của Terminal. Đi pha một ly cafe và chờ vòng quay tiến trình hoàn tất!
3. Ghép nối & Hoàn thiện:
  - Sau khi nhận thông báo ✅ màu Xanh lá và tiếng chuông báo hoàn thành.
  - Bấm nút ▶ Ghép nối hoàn chỉnh để tạo ra file _Vi.srt.
  - Bấm nút Dọn Rác để dọn sạch thư mục làm việc.
