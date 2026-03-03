import sys
import os
import re
import pysrt
import winsound
import shutil
import subprocess
import time
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QTextEdit, QGroupBox,
                             QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

# =====================================================================
# LỚP WORKER (ĐỘNG CƠ ĐA LUỒNG) - ĐÃ THÊM TÍNH NĂNG HỦY (CANCEL)
# =====================================================================
class TranslationWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int) # (Current, Total)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int, int) # (Success_count, Total_count)

    def __init__(self, target_files, context_rules):
        super().__init__()
        self.target_files = target_files
        self.context_rules = context_rules
        
        self.CHUNK_SIZE = 288
        self.MAX_RETRIES = 3 
        self.TOLERANCE_RATE = 0.95 
        
        # Biến kiểm soát trạng thái Hủy
        self._is_running = True
        self.current_process = None

    def stop(self):
        """Hàm này được gọi từ giao diện khi bấm nút Hủy"""
        self._is_running = False
        if self.current_process:
            try:
                self.current_process.kill() # Tiêu diệt lập tức tiến trình CMD đang chạy
            except:
                pass

    def run(self):
        success_files = 0
        total_files = len(self.target_files)

        for file_idx, srt_path in enumerate(self.target_files):
            if not self._is_running: break # Kiểm tra lệnh hủy

            self.status_signal.emit(f"Đang xử lý: {os.path.basename(srt_path)}")
            
            backup_path = srt_path.replace('.srt', '_backup.srt')
            shutil.copy(srt_path, backup_path)
            self.log_signal.emit(f"[*] Đã tạo backup: {os.path.basename(backup_path)}")

            try:
                subs = pysrt.open(srt_path, encoding='utf-8')
                total_chunks = (len(subs) // self.CHUNK_SIZE) + (1 if len(subs) % self.CHUNK_SIZE != 0 else 0)
                self.log_signal.emit(f"[*] File có {len(subs)} dòng. Đã chia làm {total_chunks} chunks lớn.")
                
                for chunk_idx in range(total_chunks):
                    if not self._is_running: break # Kiểm tra lệnh hủy trước mỗi chunk
                    
                    start_idx = chunk_idx * self.CHUNK_SIZE
                    end_idx = min(start_idx + self.CHUNK_SIZE, len(subs))
                    chunk_subs = subs[start_idx:end_idx]
                    
                    # Gọi hàm xử lý chunk (sẽ trả về False nếu bị hủy)
                    success = self.process_chunk_with_retry(chunk_subs, chunk_idx + 1, total_chunks)
                    if not success and not self._is_running:
                        break
                    
                    current_progress = (file_idx * 100) + int(((chunk_idx + 1) / total_chunks) * 100)
                    total_progress = total_files * 100
                    self.progress_signal.emit(current_progress, total_progress)

                # Nếu đang chạy mà bị hủy thì không lưu đè file
                if not self._is_running:
                    break

                out_srt_path = srt_path.replace('.srt', '_Vi.srt')
                subs.save(out_srt_path, encoding='utf-8')
                self.log_signal.emit(f"[+] HOÀN TẤT: Đã lưu {os.path.basename(out_srt_path)}")
                success_files += 1

            except Exception as e:
                self.log_signal.emit(f"[!] LỖI TẠI FILE {os.path.basename(srt_path)}: {e}")

        # Báo cáo kết quả cuối cùng (Bị hủy = trả về -1)
        if not self._is_running:
            self.log_signal.emit("TIẾN TRÌNH ĐÃ BỊ HỦY BỞI NGƯỜI DÙNG.")
            self.finished_signal.emit(-1, total_files)
        else:
            self.finished_signal.emit(success_files, total_files)

    def process_chunk_with_retry(self, chunk_subs, chunk_num, total_chunks):
        input_lines = []
        for sub in chunk_subs:
            clean_text = sub.text.replace('\n', ' <br> ')
            input_lines.append(f"{sub.index}||| {clean_text}")
        
        chunk_text = "\n".join(input_lines)
        base_prompt = "Translate the following text to Vietnamese. STRICTLY keep the ID tags (e.g. 0|||, 1|||) at the beginning of each line. Do not merge lines, do not delete lines."
        prompt = f"{base_prompt} TRANSLATION RULES: {self.context_rules}" if self.context_rules else base_prompt

        for attempt in range(1, self.MAX_RETRIES + 1):
            if not self._is_running: return False
            self.log_signal.emit(f"   ⏳ [Chunk {chunk_num}/{total_chunks}] Đang dịch {len(chunk_subs)} dòng... (Lần thử: {attempt}/{self.MAX_RETRIES})")
            
            try:
                cmd = ['gemini', '--prompt', prompt]
                
                # SỬ DỤNG Popen ĐỂ CÓ THỂ KILL ĐƯỢC KHI ĐANG CHẠY
                self.current_process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                out_bytes, err_bytes = self.current_process.communicate(input=chunk_text.encode('utf-8'), timeout=120)
                
                if not self._is_running: return False

                output_text = out_bytes.decode('utf-8', errors='replace').strip()
                error_text = err_bytes.decode('utf-8', errors='replace').strip()

                if self.current_process.returncode != 0 or not output_text:
                    self.log_signal.emit(f"   [!] Lỗi CLI/Network (Mã lỗi: {self.current_process.returncode}). Đang chờ phục hồi...")
                    time.sleep(3) 
                    continue

                parsed_results = {}
                for line in output_text.split('\n'):
                    match = re.match(r"^(\d+)\|\|\|(.*)", line.strip())
                    if match:
                        parsed_results[int(match.group(1))] = match.group(2).strip()

                min_required_lines = int(len(chunk_subs) * self.TOLERANCE_RATE)
                if len(parsed_results) < min_required_lines:
                    self.log_signal.emit(f"   [!] VALIDATION FAIL: AI trả thiếu dòng ({len(parsed_results)}/{len(chunk_subs)}). Không đạt {self.TOLERANCE_RATE*100}%. Bắt buộc Retry!")
                    time.sleep(3)
                    continue
                
                for sub in chunk_subs:
                    if sub.index in parsed_results:
                        sub.text = parsed_results[sub.index].replace(' <br> ', '\n').replace('<br>', '\n')
                
                self.log_signal.emit(f"   [+] [Chunk {chunk_num}/{total_chunks}] Thành công ({len(parsed_results)}/{len(chunk_subs)} dòng)!")
                return True

            except subprocess.TimeoutExpired:
                if self.current_process: self.current_process.kill()
                self.log_signal.emit(f"   [!] Lỗi Timeout (AI phản hồi quá lâu do kẹt server). Đang thử lại...")
                time.sleep(2)
            except Exception as e:
                self.log_signal.emit(f"   [!] Lỗi hệ thống ngầm: {e}")
                
        self.log_signal.emit(f"Bỏ cuộc Chunk {chunk_num} sau {self.MAX_RETRIES} lần thử. Giữ nguyên tiếng gốc.")
        return True

# =====================================================================
# LỚP GIAO DIỆN CHÍNH (ĐÃ XÓA TERMINAL VÀ GỘP THÀNH 1 CỘT)
# =====================================================================
class DropLabel(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel { border: 2px dashed #aaa; border-radius: 5px; padding: 10px; background-color: #2b2b2b; font-size: 14px; color: #ffffff; }
            QLabel:hover { background-color: #3b3b3b; border-color: #ffffff; }
        """)
        self.setAcceptDrops(True)
        self.file_path = ""

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.file_path = urls[0].toLocalFile()
            file_name = os.path.basename(self.file_path)
            prefix = "📁 Thư mục (Batch):" if os.path.isdir(self.file_path) else "📄 File đơn:"
            self.setText(f"{prefix} {file_name}")
            self.setStyleSheet("QLabel { border: 2px solid #4CAF50; border-radius: 5px; padding: 10px; background-color: #1e3a1e; font-size: 14px; color: #4CAF50; font-weight: bold; }")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SRT Tool Pro v3.3 - Giao Diện Tập Trung")
        if os.path.exists('app_icon.ico'): self.setWindowIcon(QIcon('app_icon.ico'))
        
        # CHỈNH LẠI KÍCH THƯỚC CỬA SỔ (Gọn gàng hơn do đã bỏ Terminal)
        self.resize(750, 800)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # SỬ DỤNG DUY NHẤT 1 LAYOUT DỌC
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        self.target_files = []
        self.worker = None 
        self.current_status_text = "Sẵn sàng. Chưa có tiến trình nào chạy."

        # 1. Trích xuất
        group_extract = QGroupBox("1. Kéo File/Thư mục vào đây")
        group_extract.setFixedHeight(150) 
        layout_extract = QVBoxLayout()
        layout_extract.setContentsMargins(10, 15, 10, 10)
        self.lbl_drop_srt = DropLabel("Kéo thả SRT vào đây")
        self.lbl_drop_srt.setFixedHeight(50)
        self.btn_load = QPushButton("▶ Nhận diện danh sách file")
        self.btn_load.setFixedHeight(35)
        self.btn_load.clicked.connect(self.load_files)
        layout_extract.addWidget(self.lbl_drop_srt)
        layout_extract.addWidget(self.btn_load)
        group_extract.setLayout(layout_extract)
        main_layout.addWidget(group_extract)

        # 2. Bối cảnh
        group_context = QGroupBox("Từ Điển / Bối Cảnh")
        group_context.setFixedHeight(95)
        layout_context = QVBoxLayout()
        layout_context.setContentsMargins(10, 15, 10, 10)
        self.txt_context = QTextEdit()
        self.txt_context.setPlaceholderText("Ví dụ: Đây là phim tình cảm. Xưng hô 'anh' và 'em'...")
        self.txt_context.setFixedHeight(45) 
        self.txt_context.setStyleSheet("background-color: #2b2b2b; color: #ffffff; font-size: 13px; border: 1px solid #555;")
        layout_context.addWidget(self.txt_context)
        group_context.setLayout(layout_context)
        main_layout.addWidget(group_context)

        # 3. Trạng thái & Tiến trình
        group_status = QGroupBox("2. Trạng Thái Hệ Thống")
        group_status.setFixedHeight(110) 
        layout_status = QVBoxLayout()
        layout_status.setContentsMargins(10, 15, 10, 10)
        
        self.lbl_status = QLabel(self.current_status_text)
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setFixedHeight(35)
        self.lbl_status.setStyleSheet("QLabel { background-color: #1e1e1e; border: 1px solid #555; border-radius: 5px; font-size: 14px; font-weight: bold; color: #ffffff; }")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("QProgressBar { border: 1px solid #555; border-radius: 5px; text-align: center; height: 20px; color: white; } QProgressBar::chunk { background-color: #FF9800; }")

        layout_status.addWidget(self.lbl_status)
        layout_status.addWidget(self.progress_bar)
        group_status.setLayout(layout_status)
        main_layout.addWidget(group_status)

        # 4. HÀNG NÚT BẤM (BẮT ĐẦU & HỦY)
        btn_layout = QHBoxLayout()
        
        self.btn_auto_cmd = QPushButton("BẮT ĐẦU DỊCH TỰ ĐỘNG")
        self.btn_auto_cmd.setMinimumHeight(45)
        self.btn_auto_cmd.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold; font-size: 15px; border-radius: 5px;")
        self.btn_auto_cmd.clicked.connect(self.start_translation)
        
        self.btn_cancel = QPushButton("HỦY TIẾN TRÌNH")
        self.btn_cancel.setMinimumHeight(45)
        self.btn_cancel.setEnabled(False) # Mặc định làm mờ, chỉ sáng khi đang chạy
        self.btn_cancel.setStyleSheet("""
            QPushButton { background-color: #555555; color: #aaaaaa; font-weight: bold; font-size: 15px; border-radius: 5px; }
            QPushButton:enabled { background-color: #F44336; color: white; }
            QPushButton:enabled:hover { background-color: #D32F2F; }
        """)
        self.btn_cancel.clicked.connect(self.cancel_translation)

        # Nút Bắt đầu dài hơn nút Hủy (Tỷ lệ 3:1)
        btn_layout.addWidget(self.btn_auto_cmd, stretch=3)
        btn_layout.addWidget(self.btn_cancel, stretch=1)
        main_layout.addLayout(btn_layout)

        # 5. Nhật ký
        main_layout.addWidget(QLabel("Nhật ký hệ thống (Báo lỗi & Tiến trình):"))
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background-color: #0c0c0c; color: #00ff00; font-family: Consolas; font-size: 13px; border: 1px solid #555;")
        main_layout.addWidget(self.log_box)

        # === BIẾN VÒNG QUAY ===
        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self.update_spinner)
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_idx = 0
        self.is_translating = False

    def log(self, message):
        self.log_box.append(message)
        scrollbar = self.log_box.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_status_text(self, msg):
        self.current_status_text = msg
        if not self.is_translating:
            self.lbl_status.setText(msg)

    def load_files(self):
        path = self.lbl_drop_srt.file_path
        if not path:
            self.log("[LỖI] Vui lòng kéo thả file/thư mục vào ô số 1!")
            return

        self.target_files = []
        if os.path.isdir(path):
            for f in os.listdir(path):
                if f.lower().endswith('.srt') and not f.lower().endswith('_vi.srt') and not f.lower().endswith('_backup.srt'):
                    self.target_files.append(os.path.normpath(os.path.join(path, f)))
        elif os.path.isfile(path) and path.lower().endswith('.srt'):
            self.target_files.append(os.path.normpath(path))

        if not self.target_files:
            self.log("[!] Không tìm thấy file SRT hợp lệ nào.")
        else:
            self.log(f"[*] Đã nạp danh sách: {len(self.target_files)} file srt chờ dịch.")
            self.update_status_text(f"📁 Đã nạp {len(self.target_files)} file. Sẵn sàng dịch!")

    def start_translation(self):
        if not self.target_files:
            self.log("[!] Chưa có file. Hãy kéo thả và bấm 'Nhận diện danh sách' trước.")
            return

        if self.worker and self.worker.isRunning():
            self.log("[!] Động cơ đang chạy. Vui lòng đợi hoàn tất.")
            return

        # CẬP NHẬT TRẠNG THÁI NÚT BẤM
        self.btn_auto_cmd.setEnabled(False)
        self.btn_auto_cmd.setText("⏳ ĐANG DỊCH (VUI LÒNG ĐỢI)...")
        self.btn_auto_cmd.setStyleSheet("background-color: #757575; color: white; font-weight: bold; font-size: 15px; border-radius: 5px;")
        self.btn_cancel.setEnabled(True) # Mở khóa nút Hủy
        
        self.progress_bar.setValue(0)
        self.log("KHỞI ĐỘNG ĐỘNG CƠ V3.3...")

        context = self.txt_context.toPlainText().strip()
        
        self.worker = TranslationWorker(self.target_files, context)
        self.worker.log_signal.connect(self.log)
        self.worker.status_signal.connect(self.update_status_text)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.translation_finished)
        
        self.worker.start()
        
        self.is_translating = True
        self.spinner_timer.start(100)

    def cancel_translation(self):
        if self.worker and self.worker.isRunning():
            self.log("[!] Đang gửi lệnh ngắt kết nối và dừng động cơ...")
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.setText("⏳ ĐANG HỦY...")
            self.worker.stop() # Gửi lệnh Stop cho Worker

    def update_spinner(self):
        char = self.spinner_chars[self.spinner_idx]
        self.lbl_status.setText(f"<span style='color: #FF9800; font-size: 18px;'>{char}</span> {self.current_status_text}")
        self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)

    def update_progress(self, current, total):
        percentage = int((current / total) * 100)
        self.progress_bar.setValue(percentage)

    def translation_finished(self, success_count, total_count):
        self.is_translating = False
        self.spinner_timer.stop()
        
        # PHỤC HỒI NÚT BẤM
        self.btn_auto_cmd.setEnabled(True)
        self.btn_auto_cmd.setText("⚡ BẮT ĐẦU DỊCH TỰ ĐỘNG")
        self.btn_auto_cmd.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold; font-size: 15px; border-radius: 5px;")
        
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("HỦY TIẾN TRÌNH")

        if success_count == -1: # Trường hợp bị người dùng bấm Hủy
            self.update_status_text("TIẾN TRÌNH ĐÃ BỊ HỦY.")
            self.lbl_status.setStyleSheet("QLabel { background-color: #3b1e1e; border: 1px solid #F44336; border-radius: 5px; font-size: 14px; font-weight: bold; color: #F44336; }")
        else: # Trường hợp chạy thành công trót lọt
            self.progress_bar.setValue(100)
            self.update_status_text(f"✅ HOÀN TẤT: Dịch thành công {success_count}/{total_count} file!")
            self.lbl_status.setStyleSheet("QLabel { background-color: #1e3a1e; border: 1px solid #4CAF50; border-radius: 5px; font-size: 14px; font-weight: bold; color: #4CAF50; }")
            try:
                winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
            except:
                pass

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())