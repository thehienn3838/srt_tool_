import sys
import os
import re
import pysrt
import winsound  # THƯ VIỆN PHÁT ÂM THANH CỦA WINDOWS
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QTextEdit, QGroupBox,
                             QSplitter, QLineEdit)
from PyQt6.QtCore import Qt, QProcess, QTimer

# --- LỚP GIAO DIỆN KÉO THẢ (DRAG & DROP) ---
class DropLabel(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                border-radius: 5px;
                padding: 20px;
                background-color: #f9f9f9;
                font-size: 14px;
                color: #333333;
            }
            QLabel:hover {
                background-color: #e9e9e9;
                border-color: #333;
            }
        """)
        self.setAcceptDrops(True)
        self.file_path = ""
        self.is_folder = False

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.file_path = urls[0].toLocalFile()
            file_name = os.path.basename(self.file_path)
            
            if os.path.isdir(self.file_path):
                self.is_folder = True
                self.setText(f"📁 Thư mục (Batch): {file_name}")
            else:
                self.is_folder = False
                self.setText(f"📄 File đơn: {file_name}")
                
            self.setStyleSheet("""
                QLabel {
                    border: 2px solid #4CAF50;
                    border-radius: 5px;
                    padding: 20px;
                    background-color: #e8f5e9;
                    font-size: 14px;
                    color: #2E7D32; 
                    font-weight: bold;
                }
            """)

# --- CỬA SỔ CHÍNH ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SRT Tool Pro")
        
        # --- ĐÃ KÍCH HOẠT HIỂN THỊ ICON CHO CỬA SỔ APP ---
        # Đảm bảo bạn có file app_icon.ico nằm cùng thư mục
        if os.path.exists('app_icon.ico'):
            self.setWindowIcon(QIcon('app_icon.ico'))
            
        self.resize(1200, 800)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.target_files = []
        
        # ==========================================
        # CỘT BÊN TRÁI
        # ==========================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0) 

        group_extract = QGroupBox("1. Trích Xuất Text (Hỗ trợ kéo Thư mục)")
        layout_extract = QVBoxLayout()
        self.lbl_drop_srt = DropLabel("Kéo thả File hoặc Thư mục chứa SRT vào đây")
        self.btn_extract = QPushButton("▶ Trích xuất")
        self.btn_extract.setMinimumHeight(40)
        self.btn_extract.clicked.connect(self.run_extract)
        layout_extract.addWidget(self.lbl_drop_srt)
        layout_extract.addWidget(self.btn_extract)
        group_extract.setLayout(layout_extract)
        left_layout.addWidget(group_extract)

        group_context = QGroupBox("Từ Điển / Bối Cảnh (Sẽ chèn vào AI)")
        layout_context = QVBoxLayout()
        self.txt_context = QTextEdit()
        self.txt_context.setPlaceholderText("Ví dụ: Đây là phim tình cảm. Xưng hô 'anh' và 'em'. Không dịch tên riêng 'Hoshino'...")
        self.txt_context.setMaximumHeight(60)
        self.txt_context.setStyleSheet("background-color: #fff; color: #333; font-size: 13px; border: 1px solid #ccc;")
        layout_context.addWidget(self.txt_context)
        group_context.setLayout(layout_context)
        left_layout.addWidget(group_context)

        group_merge = QGroupBox("2. Ghép Nối Phụ Đề (Merge)")
        layout_merge = QVBoxLayout()
        self.lbl_drop_srt_merge = DropLabel("Khung Nạp File/Thư Mục")
        self.lbl_drop_txt_merge = DropLabel("Trạng Thái Dịch")
        
        merge_btn_layout = QHBoxLayout()
        self.btn_merge = QPushButton("▶ Ghép nối")
        self.btn_merge.setMinimumHeight(40)
        self.btn_merge.setStyleSheet("font-weight: bold;")
        self.btn_merge.clicked.connect(self.run_merge)
        
        self.btn_clean = QPushButton("Dọn Rác")
        self.btn_clean.setMinimumHeight(40)
        self.btn_clean.setStyleSheet("background-color: #F44336; color: white; font-weight: bold;")
        self.btn_clean.clicked.connect(self.run_cleanup)
        
        merge_btn_layout.addWidget(self.btn_merge, stretch=3)
        merge_btn_layout.addWidget(self.btn_clean, stretch=1)

        layout_merge.addWidget(self.lbl_drop_srt_merge)
        layout_merge.addWidget(self.lbl_drop_txt_merge)
        layout_merge.addLayout(merge_btn_layout)
        group_merge.setLayout(layout_merge)
        left_layout.addWidget(group_merge)

        left_layout.addWidget(QLabel("Nhật ký hoạt động:"))
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background-color: #2b2b2b; color: #00FF00; font-family: Consolas; font-size: 13px;")
        left_layout.addWidget(self.log_box)

        # ==========================================
        # CỘT BÊN PHẢI (TERMINAL)
        # ==========================================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)

        term_header_layout = QHBoxLayout()
        term_header_layout.addWidget(QLabel("Terminal"))
        self.btn_auto_cmd = QPushButton("⚡ Tạo Lệnh Dịch")
        self.btn_auto_cmd.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold; padding: 5px;")
        self.btn_auto_cmd.clicked.connect(self.generate_auto_command)
        term_header_layout.addWidget(self.btn_auto_cmd)
        right_layout.addLayout(term_header_layout)
        
        self.term_output = QTextEdit()
        self.term_output.setReadOnly(True)
        self.term_output.setStyleSheet("background-color: #0c0c0c; color: #cccccc; font-family: Consolas; font-size: 13px;")
        
        self.term_input = QLineEdit()
        self.term_input.setStyleSheet("background-color: #333333; color: #ffffff; font-family: Consolas; font-size: 14px; padding: 5px;")
        self.term_input.setPlaceholderText("Gõ lệnh...")
        self.term_input.returnPressed.connect(self.send_command)

        right_layout.addWidget(self.term_output)
        right_layout.addWidget(self.term_input)

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([550, 650]) 
        
        layout_main = QVBoxLayout(main_widget)
        layout_main.addWidget(main_splitter)

        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self.update_spinner)
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_idx = 0
        self.is_translating = False
        self.output_buffer = ""

        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.start("cmd.exe", ["/K", "chcp 65001"])

        self.log("Sẵn sàng! Kéo thả File hoặc Thư mục vào ô số 1.")

    def run_extract(self):
        path = self.lbl_drop_srt.file_path
        if not path:
            self.log("[LỖI] Vui lòng kéo thả file/thư mục vào ô trích xuất!")
            return

        self.target_files = []
        
        if os.path.isdir(path):
            for f in os.listdir(path):
                if f.lower().endswith('.srt') and not f.lower().endswith('_vi.srt'):
                    self.target_files.append(os.path.normpath(os.path.join(path, f)))
        elif os.path.isfile(path) and path.lower().endswith('.srt'):
            self.target_files.append(os.path.normpath(path))

        if not self.target_files:
            self.log("[!] Không tìm thấy file SRT hợp lệ nào.")
            return

        self.log(f"[*] Đang xử lý trích xuất {len(self.target_files)} file...")
        
        success_count = 0
        for srt_path in self.target_files:
            txt_path = srt_path.replace('.srt', '.txt')
            try:
                subs = pysrt.open(srt_path, encoding='utf-8')
                with open(txt_path, 'w', encoding='utf-8') as f:
                    for i, sub in enumerate(subs):
                        line = sub.text.replace('\n', ' <br> ')
                        f.write(f"{i}||| {line}\n\n")
                success_count += 1
            except Exception as e:
                self.log(f"[!] Lỗi khi trích xuất {os.path.basename(srt_path)}: {e}")

        self.log(f"[+] Đã trích xuất thành công {success_count}/{len(self.target_files)} file txt!")

    def generate_auto_command(self):
        if not self.target_files:
            self.log("[!] Danh sách file trống. Hãy Trích xuất trước.")
            return

        base_prompt = "Translate the following text to Vietnamese. STRICTLY keep the ID tags (e.g. 0|||, 1|||) at the beginning of each line. Do not merge lines, do not delete lines."
        user_context = self.txt_context.toPlainText().strip()
        
        if user_context:
            prompt = f"{base_prompt} TRANSLATION RULES: {user_context}"
        else:
            prompt = base_prompt

        work_dir = os.path.dirname(self.target_files[0])
        bat_path = os.path.join(work_dir, "gemini_batch_run.bat")
        
        try:
            with open(bat_path, "w", encoding="utf-8") as bat:
                bat.write("@echo off\n")
                bat.write("chcp 65001 >nul\n")
                
                for srt_path in self.target_files:
                    txt_path = srt_path.replace('.srt', '.txt')
                    out_txt_path = srt_path.replace('.srt', '_VIET.txt')
                    
                    bat.write(f'echo [*] Translating: {os.path.basename(txt_path)}...\n')
                    bat.write(f'type "{txt_path}" | gemini --prompt "{prompt}" > "{out_txt_path}"\n')
                
                bat.write("echo ===DONE_AI===\n")
                
        except Exception as e:
            self.log(f"[!] Lỗi tạo file batch: {e}")
            return

        self.lbl_drop_srt_merge.setText(f"📁 Đã nạp {len(self.target_files)} file gốc")
        self.lbl_drop_srt_merge.setStyleSheet("QLabel { border: 2px solid #2196F3; border-radius: 5px; padding: 20px; background-color: #E3F2FD; font-size: 14px; color: #1565C0; font-weight: bold; }")

        self.lbl_drop_txt_merge.setText(f"⏳ Chờ bạn ấn Enter ở Terminal...")
        self.lbl_drop_txt_merge.setStyleSheet("QLabel { border: 2px dashed #aaa; border-radius: 5px; padding: 20px; background-color: #f9f9f9; font-size: 14px; color: #333333; }")

        cmd = f'@call "{bat_path}"'
        self.term_input.setText(cmd)
        self.log(f"[*] Đã đóng gói {len(self.target_files)} file vào chuỗi dịch tự động. Ấn Enter ở Terminal để chạy 1 lèo!")

    def run_merge(self):
        if not self.target_files:
            self.log("[!] Chưa có danh sách file để ghép.")
            return

        success_count = 0
        for srt_path in self.target_files:
            txt_path = srt_path.replace('.srt', '_VIET.txt')
            out_srt_path = srt_path.replace('.srt', '_Vi.srt')

            if not os.path.exists(txt_path) or os.path.getsize(txt_path) == 0:
                continue

            try:
                subs = pysrt.open(srt_path, encoding='utf-8')
                with open(txt_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]

                for line in lines:
                    match = re.match(r"^(\d+)\|\|\|(.*)", line)
                    if match:
                        idx = int(match.group(1))
                        text = match.group(2).strip()
                        if idx < len(subs):
                            subs[idx].text = text.replace(' <br> ', '\n').replace('<br>', '\n')

                subs.save(out_srt_path, encoding='utf-8')
                success_count += 1
            except Exception as e:
                self.log(f"[!] Lỗi khi ghép {os.path.basename(srt_path)}: {e}")

        if success_count > 0:
            self.log(f"[+] Tuyệt vời! Đã ghép nối hoàn chỉnh {success_count} file SRT.")
            self.lbl_drop_txt_merge.setStyleSheet("QLabel { border: 2px solid #4CAF50; border-radius: 5px; padding: 20px; background-color: #e8f5e9; font-size: 14px; color: #2E7D32; font-weight: bold; }")
            self.lbl_drop_txt_merge.setText(f"✅ Đã lưu {success_count} video Vietsub!")

    def run_cleanup(self):
        if not self.target_files:
            self.log("[!] Chưa có thông tin file để dọn dẹp.")
            return

        deleted_count = 0
        for srt_path in self.target_files:
            f_txt = srt_path.replace('.srt', '.txt')
            f_viet = srt_path.replace('.srt', '_VIET.txt')
            
            if os.path.exists(f_txt): 
                os.remove(f_txt)
                deleted_count += 1
            if os.path.exists(f_viet): 
                os.remove(f_viet)
                deleted_count += 1

        work_dir = os.path.dirname(self.target_files[0])
        bat_path = os.path.join(work_dir, "gemini_batch_run.bat")
        if os.path.exists(bat_path):
            os.remove(bat_path)
            
        self.log(f"[🧹] Dọn dẹp hoàn tất! Đã xóa sạch {deleted_count} file rác.")

    def start_translation_ui(self):
        self.is_translating = True
        self.output_buffer = ""
        self.spinner_idx = 0
        self.btn_merge.setEnabled(False) 
        self.lbl_drop_txt_merge.setStyleSheet("QLabel { border: 2px dashed #FF9800; border-radius: 5px; padding: 20px; background-color: #FFF3E0; font-size: 14px; color: #E65100; font-weight: bold; }")
        self.spinner_timer.start(100)

    def update_spinner(self):
        char = self.spinner_chars[self.spinner_idx]
        self.lbl_drop_txt_merge.setText(f"{char} AI Đang Dịch Hàng Loạt ({len(self.target_files)} file)...")
        self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)

    def finish_translation_ui(self):
        self.is_translating = False
        self.spinner_timer.stop() 
        self.btn_merge.setEnabled(True) 
        
        success_count = 0
        for srt in self.target_files:
            out_txt = srt.replace('.srt', '_VIET.txt')
            if os.path.exists(out_txt) and os.path.getsize(out_txt) > 0:
                success_count += 1

        if success_count > 0:
            self.lbl_drop_txt_merge.setStyleSheet("QLabel { border: 2px solid #4CAF50; border-radius: 5px; padding: 20px; background-color: #e8f5e9; font-size: 14px; color: #2E7D32; font-weight: bold; }")
            self.lbl_drop_txt_merge.setText(f"✅ Dịch xong {success_count}/{len(self.target_files)} file. Hãy ghép nối!")
            self.log(f"[*] Tiến trình Batch AI đã hoàn tất.")
            
           # === PHÁT ÂM THANH KHI THÀNH CÔNG ===
            try:
                # Gọi âm thanh "Ting" (SystemAsterisk) mặc định của Windows
                winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
                # Hoặc nếu bạn thích tiếng "Bíp" tiêu chuẩn hơn, có thể dùng dòng dưới thay thế:
                # winsound.MessageBeep(winsound.MB_OK)
            except Exception as e:
                self.log(f"[-] {e}")
    def send_command(self):
        cmd = self.term_input.text()
        self.term_input.clear()
        if cmd.strip():
            self.term_output.append(f"<br><span style='color: #00ffff;'>&gt; {cmd}</span>")
            self.process.write((cmd + "\n").encode('utf-8'))
            
            if "gemini_batch_run.bat" in cmd:
                self.start_translation_ui()

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode('utf-8', errors='replace')
        
        display_data = data.replace("===DONE_AI===\r\n", "").replace("===DONE_AI===\n", "").replace("===DONE_AI===", "")
        self.term_output.insertPlainText(display_data)
        
        if self.is_translating:
            self.output_buffer += data
            lines = [line.strip() for line in self.output_buffer.split('\n')]
            if "===DONE_AI===" in lines:
                self.finish_translation_ui()
                self.output_buffer = "" 

        scrollbar = self.term_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode('utf-8', errors='replace')
        self.term_output.insertPlainText(data)
        scrollbar = self.term_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def log(self, message):
        self.log_box.append(message)
        scrollbar = self.log_box.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())