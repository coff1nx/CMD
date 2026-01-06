import sys
import os
import subprocess
import signal
import io
import keyboard
import ctypes
import time
from PyQt6.QtGui import QIcon


try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
        QPlainTextEdit, QLineEdit, QPushButton, QFileDialog, QLabel, 
        QRadioButton, QScrollArea, QMenu
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer, QPoint
    from PyQt6.QtGui import QFont, QTextCursor, QAction
except ImportError:
    print("Ошибка: Необходимо установить PyQt6 (pip install PyQt6)")
    sys.exit(1)


os.environ["PYTHONIOENCODING"] = "utf-8"
PROJECTS_FILE = "projects.txt"
CMD_PATH = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "cmd.exe")

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def universal_decode(raw_bytes):
    """Декодирует байты, перебирая кодировки (решает проблему иероглифов)"""
    for enc in ['utf-8', 'cp866', 'cp1251']:
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode('utf-8', errors='replace')


class RealCmdSession(QObject):
    output_received = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, cwd):
        super().__init__()
        self.cwd = cwd
        self.process = None
        self._keep_reading = True
        self.first_run = True

    def run(self):
        try:
            self.process = subprocess.Popen(
                [CMD_PATH],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.cwd,
                text=False,
                bufsize=0,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            import msvcrt
            handle = msvcrt.get_osfhandle(self.process.stdout.fileno())

            while self._keep_reading:
                from ctypes import wintypes
                dwAvail = wintypes.DWORD()
                if ctypes.windll.kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(dwAvail), None):
                    if dwAvail.value > 0:
                        raw_bytes = self.process.stdout.read(dwAvail.value)
                        if raw_bytes:
                            text = universal_decode(raw_bytes)
                            if self.first_run:
                                if ">" in text:
                                    text = text.split(">", 1)[-1].lstrip()
                                    self.first_run = False
                                else: continue
                            self.output_received.emit(text)
                if self.process.poll() is not None: break
                time.sleep(0.01)
        except Exception as e:
            self.output_received.emit(f"\n[Критическая ошибка CMD]: {str(e)}\n")
        finally:
            self.finished.emit()

    def send_command(self, cmd):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write((cmd + "\r\n").encode('cp866'))
                self.process.stdin.flush()
            except: pass

    def stop_current_task(self):
        if self.process:
            self.process.send_signal(signal.CTRL_BREAK_EVENT)

    def terminate(self):
        self._keep_reading = False
        if self.process:
            try: self.process.kill()
            except: pass


class ProcessWorker(QObject):
    output_received = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, command, cwd):
        super().__init__()
        self.command = command
        self.cwd = cwd
        self.process = None
        self._is_running = True

    def run(self):
        try:
            cmd = self.command
            
            if cmd.strip().lower().startswith("python "):
                if " -u " not in cmd.lower():
                    cmd = cmd.replace("python ", "python -u ", 1)

            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            
            self.process = subprocess.Popen(
                cmd, shell=True, cwd=self.cwd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                bufsize=0, env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )

            
            while self._is_running:
                line = self.process.stdout.readline()
                if not line and self.process.poll() is not None:
                    break
                if line:
                    self.output_received.emit(universal_decode(line))
        except Exception as e:
            self.output_received.emit(f"\n[Shell Error]: {str(e)}\n")
        finally:
            self.finished.emit()

    def stop(self):
        self._is_running = False
        if self.process:
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.process.pid)], capture_output=True)


class CmdPlus(QMainWindow):
    toggle_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("cmd+")
        self.resize(1150, 720)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        self.current_dir = os.getcwd()
        self.admin_status = "Administrator" if self.is_admin() else "User"
        self.projects = self.load_projects()
        
        self.real_cmd_active = False
        self.real_session = None
        self.real_thread = None
        self.active_worker = None
        self.active_thread = None

        self.init_ui()
        self.setup_global_hotkey()
        self.print_initial_info()
        self.icon_path = get_resource_path("icon.ico")
        if os.path.exists(self.icon_path):
            self.setWindowIcon(QIcon(self.icon_path))

    def is_admin(self):
        try: return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except: return False

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(230)
        self.sidebar.setStyleSheet("background-color: #111; border-right: 1px solid #222;")
        sidebar_layout = QVBoxLayout(self.sidebar)
        
        lbl_head = QLabel("PROJECT HISTORY")
        lbl_head.setStyleSheet("color: #444; font-weight: bold; font-size: 10px; margin: 10px;")
        sidebar_layout.addWidget(lbl_head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background: transparent;")
        self.project_list_widget = QWidget()
        self.project_list_layout = QVBoxLayout(self.project_list_widget)
        self.project_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.project_list_widget)
        sidebar_layout.addWidget(self.scroll)
        main_layout.addWidget(self.sidebar)

        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        
        header = QWidget()
        header.setFixedHeight(45)
        header.setStyleSheet("background-color: #1a1a1a; border-bottom: 1px solid #222;")
        h_layout = QHBoxLayout(header)
        
        self.lbl_mode = QLabel(f"MODE: Shell | {self.admin_status}")
        self.lbl_mode.setStyleSheet("color: #00ff00; font-family: Consolas; font-weight: bold; font-size: 13px;")
        
        self.rb_shell = QRadioButton("Shell")
        self.rb_real = QRadioButton("Real CMD")
        self.rb_shell.setChecked(True)
        self.rb_shell.setStyleSheet("color: #aaa;")
        self.rb_real.setStyleSheet("color: #aaa;")
        self.rb_real.toggled.connect(self.switch_mode)

        h_layout.addWidget(self.lbl_mode)
        h_layout.addStretch()
        h_layout.addWidget(self.rb_shell)
        h_layout.addWidget(self.rb_real)
        right_layout.addWidget(header)

        
        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFont(QFont("Consolas", 11))
        self.terminal.setStyleSheet("background-color: #080808; color: #d0d0d0; border: none; padding: 10px;")
        right_layout.addWidget(self.terminal)

        
        self.input_line = QLineEdit()
        self.input_line.setFont(QFont("Consolas", 11))
        self.input_line.setPlaceholderText("Введите команду...")
        self.input_line.setStyleSheet("background-color: #080808; color: #fff; border: none; padding: 15px; border-top: 1px solid #222;")
        self.input_line.returnPressed.connect(lambda: self.handle_command())
        right_layout.addWidget(self.input_line)

        
        footer = QWidget()
        footer.setFixedHeight(50)
        footer.setStyleSheet("background-color: #111; border-top: 1px solid #222;")
        f_layout = QHBoxLayout(footer)
        
        btn_file = QPushButton("📂 ВЫБРАТЬ ФАЙЛ")
        btn_file.setStyleSheet("background: #222; color: #eee; border: 1px solid #333; padding: 5px 15px;")
        btn_file.clicked.connect(self.open_file_dialog)

        self.btn_stop = QPushButton("⛔ ОСТАНОВИТЬ")
        self.btn_stop.setStyleSheet("background: #2a1010; color: #ff5555; border: 1px solid #442222; padding: 5px 15px; font-weight: bold;")
        self.btn_stop.clicked.connect(self.stop_process)
        
        f_layout.addWidget(btn_file)
        f_layout.addStretch()
        f_layout.addWidget(self.btn_stop)
        right_layout.addWidget(footer)

        main_layout.addWidget(right_panel)
        self.refresh_project_list()

    def handle_command(self, cmd_override=None):
        cmd = cmd_override if cmd_override else self.input_line.text()
        if not cmd_override: self.input_line.clear()
        if not cmd.strip(): return

        if self.real_cmd_active:
            if self.real_session: self.real_session.send_command(cmd)
        else:
            self.terminal.insertPlainText(f"\n> {cmd}\n")
            if ".py" in cmd.lower() or os.path.isfile(cmd.replace('"', '').strip()):
                self.add_project(cmd)
            if cmd.lower() == "cls":
                self.terminal.clear(); self.print_prompt(); return
            self.execute_external(cmd)

    def execute_external(self, cmd):
        self.input_line.setEnabled(False)
        self.active_thread = QThread()
        self.active_worker = ProcessWorker(cmd, self.current_dir)
        self.active_worker.moveToThread(self.active_thread)
        self.active_thread.started.connect(self.active_worker.run)
        self.active_worker.output_received.connect(self.safe_append)
        self.active_worker.finished.connect(self.on_shell_finished)
        self.active_thread.start()

    def on_shell_finished(self):
        self.input_line.setEnabled(True); self.input_line.setFocus()
        self.terminal.insertPlainText(f"\n{self.current_dir}>")
        self.active_thread.quit()

    def switch_mode(self):
        is_real = self.rb_real.isChecked()
        self.real_cmd_active = is_real
        if is_real:
            self.lbl_mode.setText(f"MODE: Real CMD | {self.admin_status}")
            self.lbl_mode.setStyleSheet("color: #ffaa00; font-weight: bold;")
            if not self.real_session: self.start_real_session()
        else:
            self.lbl_mode.setText(f"MODE: Shell | {self.admin_status}")
            self.lbl_mode.setStyleSheet("color: #00ff00; font-weight: bold;")
        self.input_line.setFocus()

    def start_real_session(self):
        self.real_thread = QThread()
        self.real_session = RealCmdSession(self.current_dir)
        self.real_session.moveToThread(self.real_thread)
        self.real_thread.started.connect(self.real_session.run)
        self.real_session.output_received.connect(self.safe_append)
        self.real_thread.start()

    def safe_append(self, text):
        self.terminal.insertPlainText(text)
        self.terminal.moveCursor(QTextCursor.MoveOperation.End)

    def add_project(self, cmd):
        if cmd.strip() not in self.projects:
            self.projects.append(cmd.strip())
            self.save_projects(); self.refresh_project_list()

    def refresh_project_list(self):
        for i in reversed(range(self.project_list_layout.count())): 
            self.project_list_layout.itemAt(i).widget().setParent(None)
        for p in self.projects:
            name = os.path.basename(p.replace('"', '').strip())
            btn = QPushButton(f"  {name}")
            btn.setToolTip(p)
            btn.setStyleSheet("text-align: left; padding: 8px; color: #888; background: #1a1a1a; border: 1px solid #222; margin: 2px;")
            btn.clicked.connect(lambda ch, c=p: self.handle_command(c))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, c=p: self.show_project_menu(pos, c))
            self.project_list_layout.addWidget(btn)

    def show_project_menu(self, pos, cmd):
        menu = QMenu()
        menu.setStyleSheet("background-color: #222; color: white;")
        del_act = menu.addAction("❌ Удалить из истории")
        action = menu.exec(self.sender().mapToGlobal(pos))
        if action == del_act:
            self.projects.remove(cmd); self.save_projects(); self.refresh_project_list()

    def open_file_dialog(self):
        file, _ = QFileDialog.getOpenFileName(self, "Выбрать файл", "", "Python (*.py);;All (*.*)")
        if file: self.handle_command(f'"{os.path.normpath(file)}"')

    def load_projects(self):
        if os.path.exists(PROJECTS_FILE):
            with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                return [l.strip() for l in f if l.strip()]
        return []

    def save_projects(self):
        with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
            for p in self.projects: f.write(p + "\n")

    def stop_process(self):
        if self.real_cmd_active and self.real_session: self.real_session.stop_current_task()
        elif self.active_worker: self.active_worker.stop()

    def setup_global_hotkey(self):
        self.toggle_signal.connect(self.toggle_visibility)
        keyboard.add_hotkey('shift+caps lock', lambda: self.toggle_signal.emit())

    def toggle_visibility(self):
        if self.isVisible(): self.hide()
        else: self.showNormal(); self.activateWindow()

    def print_initial_info(self):
        self.terminal.appendPlainText(f"cmdplus ready | {self.admin_status}")
        self.terminal.appendPlainText(f"{self.current_dir}>")

    def closeEvent(self, event):
        if self.real_session: self.real_session.terminate()
        keyboard.unhook_all()
        super().closeEvent(event)

if __name__ == "__main__":
    
    myappid = 'com.myteam.cmdplus.v2' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    app = QApplication(sys.argv)
    
    
    icon_path = get_resource_path("icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        
    window = CmdPlus()
    window.show()
    sys.exit(app.exec())