import sys
import os
import subprocess
import signal
import io
import keyboard  # Не забудь: pip install keyboard
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPlainTextEdit, QLineEdit, QPushButton, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QTextCursor

# --- Стили (styles.py) ---
STYLE_SHEET = """
QMainWindow { background-color: #0c0c0c; }
QPlainTextEdit {
    background-color: #0c0c0c;
    color: #cccccc;
    border: none;
    selection-background-color: #ffffff;
    selection-color: #0c0c0c;
}
QLineEdit {
    background-color: #0c0c0c;
    color: #ffffff;
    border: none;
    padding: 5px;
}
QPushButton {
    background-color: #333;
    color: white;
    border: 1px solid #555;
    padding: 5px 15px;
    border-radius: 2px;
}
QPushButton:hover { background-color: #444; }
"""

# --- Логика выполнения процесса (process_worker.py) ---
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
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"

            self.process = subprocess.Popen(
                self.command,
                shell=True,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                bufsize=0,
                env=env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )

            reader = io.TextIOWrapper(self.process.stdout, encoding='utf-8', errors='replace')

            while self._is_running:
                char = reader.read(1)
                if not char and self.process.poll() is not None:
                    break
                if char:
                    self.output_received.emit(char)
            
        except Exception as e:
            self.output_received.emit(f"\n[ERROR]: {str(e)}\n")
        finally:
            self.finished.emit()

    def stop(self):
        self._is_running = False
        if self.process:
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.process.pid)], capture_output=True)

# --- Главное окно (main.py) ---
class CmdPlus(QMainWindow):
    # Сигнал для безопасного взаимодействия потока хоткея с GUI
    toggle_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CMD+")
        self.resize(1000, 600)
        
        # ПОПРАВКА 3: Всегда поверх всех окон
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        self.current_dir = os.getcwd()
        self.history = []
        self.history_index = -1
        self.active_worker = None
        self.active_thread = None

        self.init_ui()
        self.print_initial_info()
        
        # ПОПРАВКА 2: Инициализация глобального хоткея
        self.setup_global_hotkey()

    def setup_global_hotkey(self):
        self.toggle_signal.connect(self.toggle_visibility)
        # Регистрируем сочетание клавиш Shift + Caps Lock
        keyboard.add_hotkey('shift+caps lock', lambda: self.toggle_signal.emit())

    def toggle_visibility(self):
        """Сворачивает или разворачивает окно"""
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow() # Фокус на окно

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFont(QFont("Consolas", 11))
        layout.addWidget(self.terminal)

        input_layout = QHBoxLayout()
        self.input_line = QLineEdit()
        self.input_line.setFont(QFont("Consolas", 11))
        self.input_line.returnPressed.connect(self.handle_command)
        input_layout.addWidget(self.input_line)
        layout.addLayout(input_layout)

        button_panel = QHBoxLayout()
        button_panel.setContentsMargins(5, 5, 5, 5)
        self.btn_open = QPushButton("📂 Открыть и запустить")
        self.btn_open.clicked.connect(self.open_file_dialog)
        self.btn_stop = QPushButton("⛔ Стоп")
        self.btn_stop.clicked.connect(self.stop_process)
        self.btn_stop.setEnabled(False)
        
        button_panel.addWidget(self.btn_open)
        button_panel.addWidget(self.btn_stop)
        button_panel.addStretch()
        layout.addLayout(button_panel)

        self.setStyleSheet(STYLE_SHEET)

    def print_initial_info(self):
        try:
            ver = subprocess.check_output("ver", shell=True).decode('cp866').strip()
            self.terminal.appendPlainText(f"Microsoft Windows [Version {ver.split('[Version ')[1]}")
        except:
            self.terminal.appendPlainText("Microsoft Windows [Version 10.0]")
        self.terminal.appendPlainText("(c) Microsoft Corporation. All rights reserved.\n")
        self.print_prompt()

    def print_prompt(self):
        self.terminal.insertPlainText(f"{self.current_dir}>")
        self.terminal.moveCursor(QTextCursor.MoveOperation.End)

    def handle_command(self):
        cmd_text = self.input_line.text()
        self.input_line.clear()
        
        self.terminal.insertPlainText(f"{cmd_text}\n")
        
        if not cmd_text.strip():
            self.print_prompt()
            return

        self.history.append(cmd_text)
        self.history_index = len(self.history)

        parts = cmd_text.strip().split()
        base_cmd = parts[0].lower()

        if base_cmd == "cls":
            self.terminal.clear()
            self.print_prompt()
            return
        
        if base_cmd == "cd":
            try:
                new_path = cmd_text.strip()[3:].replace('"', '')
                if new_path:
                    os.chdir(new_path)
                    self.current_dir = os.getcwd()
                self.terminal.insertPlainText("\n")
                self.print_prompt()
            except Exception as e:
                self.terminal.appendPlainText(f"Ошибка: {e}")
                self.print_prompt()
            return

        self.execute_external(cmd_text)

    def execute_external(self, cmd_text):
        self.btn_stop.setEnabled(True)
        self.input_line.setEnabled(False)

        if cmd_text.strip().lower().startswith("python ") and "-u" not in cmd_text:
            cmd_text = cmd_text.replace("python ", "python -u ", 1)

        self.active_thread = QThread()
        self.active_worker = ProcessWorker(cmd_text, self.current_dir)
        self.active_worker.moveToThread(self.active_thread)

        self.active_thread.started.connect(self.active_worker.run)
        self.active_worker.output_received.connect(self.safe_append)
        self.active_worker.finished.connect(self.on_process_finished)
        
        self.active_thread.start()

    def safe_append(self, text):
        self.terminal.insertPlainText(text)
        self.terminal.verticalScrollBar().setValue(
            self.terminal.verticalScrollBar().maximum()
        )   

    def on_process_finished(self):
        self.btn_stop.setEnabled(False)
        self.input_line.setEnabled(True)
        self.input_line.setFocus()
        self.print_prompt()
        self.active_thread.wait()
        self.active_thread = None
        self.active_worker = None

    def stop_process(self):
        if self.active_worker:
            self.active_worker.stop()
            self.terminal.appendPlainText("\n[PROCESS TERMINATED]\n")

    # ПОПРАВКА 1: Выбор файла сразу запускает его
    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать и запустить")
        if path:
            formatted_path = f'"{os.path.normpath(path)}"'
            # Вставляем путь в строку ввода (визуально) и имитируем нажатие Enter
            self.input_line.setText(formatted_path)
            self.handle_command()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Up and self.history:
            self.history_index = max(0, self.history_index - 1)
            self.input_line.setText(self.history[self.history_index])
        elif event.key() == Qt.Key.Key_Down and self.history:
            if self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.input_line.setText(self.history[self.history_index])
            else:
                self.history_index = len(self.history)
                self.input_line.clear()
        super().keyPressEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CmdPlus()
    window.show()
    sys.exit(app.exec())