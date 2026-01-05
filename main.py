import sys
import os
# Принудительно ставим UTF-8 для вывода в консоль, чтобы не было ошибок с эмодзи
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QLineEdit, QPushButton, 
                             QListWidget, QListWidgetItem, QFileDialog, QMenu)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QAction

from cmd_engine import CMDEngine
from terminal_view import TerminalView
from run_tracker import RunTracker
from hint_engine import HintEngine
from theme_manager import ThemeManager
from hotkeys import HotkeyManager

def load_stylesheet(app):
    if os.path.exists("style.qss"):
        with open("style.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    else:
        print("Файл style.qss не найден!")

class DevCMDApp(QMainWindow):
    def __init__(self):
        super().__init__()
        app_font = QFont("Segoe UI", 12) 
        self.setFont(app_font)
        self.setWindowFlags(Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        load_stylesheet(QApplication.instance())
        
        self.setWindowTitle("DevCMD Launcher")
        self.resize(1100, 800)

        # 1. Инициализация модулей
        self.engine = CMDEngine()
        self.tracker = RunTracker()
        self.hinter = HintEngine()
        self.themes = ThemeManager()
        self.hotkeys = HotkeyManager()

        # 2. Инициализация интерфейса
        self.init_ui()
        
        # 3. Настройка окна (Поверх всех)
        # Добавляем WindowStaysOnTopHint, чтобы приложение всегда было над IDE/браузером
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        # 4. Подключение сигналов
        self.setup_connections()
        
        # 5. Установка темы
        self.current_theme = self.themes.get_theme()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()
            event.accept()    

    def init_ui(self):
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            main_layout = QVBoxLayout(central_widget)
            main_layout.setContentsMargins(15, 15, 15, 15) # Отступы от краев окна
            main_layout.setSpacing(10)

            self.splitter = QSplitter(Qt.Horizontal)
            
            # ЛЕВАЯ ЧАСТЬ
            self.terminal = TerminalView()
            terminal_font = QFont("Consolas", 13) 
            self.terminal.setFont(terminal_font)
            left_widget = QWidget()
            left_layout = QVBoxLayout(left_widget)
            
            
            # Блок кнопок управления над вводом
            btn_layout = QHBoxLayout()
            self.stop_btn = QPushButton("⛔ STOP")
            self.stop_btn.setStyleSheet("background-color: #cf222e; color: white; font-weight: bold;")
            self.stop_btn.setFixedHeight(30)
            
            self.input_line = QLineEdit()
            self.input_line.setPlaceholderText("Введите команду...")
            
            left_layout.addWidget(self.terminal)
            left_layout.addLayout(btn_layout)
            left_layout.addWidget(self.stop_btn) # Кнопка стоп под терминалом
            left_layout.addWidget(self.input_line)

            # ПРАВАЯ ЧАСТЬ
            right_widget = QWidget()
            right_layout = QVBoxLayout(right_widget)
            
            self.run_file_btn = QPushButton("🚀 ЗАПУСТИТЬ ФАЙЛ (RUN)")
            self.run_file_btn.setFixedHeight(45)
            self.run_file_btn.setStyleSheet("font-weight: bold; background-color: #2da44e; color: white;")
            
            # ПУНКТ 1: ПОИСК
            self.search_input = QLineEdit()
            self.search_input.setPlaceholderText("🔍 Поиск по командам...")
            
            self.runs_list = QListWidget()
            # Добавляем контекстное меню для удаления
            self.runs_list.setContextMenuPolicy(Qt.CustomContextMenu)
            self.runs_list.customContextMenuRequested.connect(self.show_context_menu)
            
            right_layout.addWidget(self.run_file_btn)
            right_layout.addWidget(self.search_input) # Поиск
            right_layout.addWidget(self.runs_list)

            self.splitter.addWidget(left_widget)
            self.splitter.addWidget(right_widget)
            main_layout.addWidget(self.splitter)
            
            
            # Чтобы стили ID заработали, пропиши их кнопкам:
            self.run_file_btn.setObjectName("run_btn")
            self.stop_btn.setObjectName("stop_btn")
            
            self.refresh_runs()

    def choose_and_run(self):
        """Проводник для выбора файла"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите Python файл для запуска", "", "Python Files (*.py)"
        )
        if file_path:
            file_path = os.path.normpath(file_path)
            directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            
            # Добавили флаг -u для мгновенного вывода логов
            full_command = f'cd /d "{directory}" && python -u "{filename}"'
            
            self.terminal.append_formatted(f"\n[LAUNCHING FILE...]\n", "hint")
            self.terminal.append_formatted(f"> {full_command}\n", "user_cmd")
            
            self.engine.execute(full_command)
            self.tracker.save_run(f'python -u "{filename}"', directory) # Сохраняем тоже с -u
            self.refresh_runs()

    def setup_connections(self):
        # Отключаем старый обработчик перед подключением нового, чтобы не копились
        try:
            self.engine.output_received.disconnect(self.handle_output)
        except (TypeError, RuntimeError):
            pass # Если еще не был подключен
            
        self.engine.output_received.connect(self.handle_output)
        self.hotkeys.hotkey_pressed.connect(self.toggle_window)
        self.engine.output_received.connect(self.handle_output)
        self.input_line.returnPressed.connect(self.send_command)
        self.stop_btn.clicked.connect(self.engine.stop_process)
        self.search_input.textChanged.connect(self.filter_runs)
        self.runs_list.itemDoubleClicked.connect(self.run_saved_item)
        self.run_file_btn.clicked.connect(self.choose_and_run)

    def filter_runs(self, text):
        for i in range(self.runs_list.count()):
            item = self.runs_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())    

    def show_context_menu(self, pos):
        item = self.runs_list.itemAt(pos)
        if item:
            menu = QMenu()
            del_action = menu.addAction("❌ Удалить из истории")
            action = menu.exec(self.runs_list.mapToGlobal(pos))
            if action == del_action:
                data = item.data(Qt.UserRole)
                self.tracker.delete_run(data['command'], data['path'])
                self.refresh_runs()        

    def handle_link_click(self, url):
        path = url.toString()
        if os.path.exists(path):
            os.startfile(path)            

    def send_command(self):
        cmd = self.input_line.text().strip()
        if cmd:
            self.terminal.append_formatted(f"> {cmd}\n", "user_cmd")
            self.engine.execute(cmd)
            self.tracker.save_run(cmd, os.getcwd())
            self.input_line.clear()
            self.refresh_runs()

    def handle_output(self, text, out_type):
        final_type = out_type
        text_upper = text.upper()
        if hasattr(self, '_last_cmd') and self._last_cmd in text:
            return
        if "TRACEBACK" in text_upper or ("FILE \"" in text_upper and "LINE" in text_upper):
            final_type = "traceback"
        elif any(word in text_upper for word in ["ERROR", "EXCEPTION", "FAILED"]):
            final_type = "error"
        elif any(word in text_upper for word in ["WARNING", "CAUTION"]):
            final_type = "warning"
        elif any(word in text_upper for word in ["INFO", "OK", "SUCCESS", "DONE"]):
            final_type = "success"

        self.terminal.append_formatted(text, final_type)
        
        hint = self.hinter.get_hint(text)
        if hint:
            self.terminal.append_formatted(f"{hint}\n", "hint")

    def refresh_runs(self):
        self.runs_list.clear()
        runs = self.tracker.load_runs()
        for run in runs:
            item = QListWidgetItem(f"{run['command']}\n[{run['path']}]")
            item.setData(Qt.UserRole, run)
            self.runs_list.addItem(item)

    def run_saved_item(self, item):
        # ЗАЩИТА ОТ ДВОЙНОГО КЛИКА
        import time
        if hasattr(self, '_last_run_time'):
            if time.time() - self._last_run_time < 0.5: # Если прошло меньше 0.5 сек
                return
        self._last_run_time = time.time()

        # 1. Останавливаем старый процесс
        self.engine.stop_process() 
        
        data = item.data(Qt.UserRole)
        path = data['path']
        cmd = data['command']
        
        if "python" in cmd and "-u" not in cmd:
            cmd = cmd.replace("python", "python -u")
            
        full_command = f'cd /d "{path}" && {cmd}'
        
        # Печатаем в терминал (теперь это вызовется строго 1 раз)
        self.terminal.append_formatted(f"\n[RESTARTING PROJECT...]\n", "hint")
        self.terminal.append_formatted(f"> {full_command}\n", "user_cmd")
        
        # Запускаем команду
        self.engine.execute(full_command)

    def toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.themes.save_theme(self.current_theme)
        self.themes.apply(QApplication.instance(), self.current_theme)

    def toggle_window(self):
        """Логика хоткея: показать поверх всех / скрыть"""
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            # Убеждаемся, что флаг «всегда сверху» активен при показе
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()
            self.raise_()
            self.activateWindow()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # ПРИМЕНЯЕМ СТИЛЬ ЗДЕСЬ
    load_stylesheet(app)
    
    window = DevCMDApp()
    window.show()
    sys.exit(app.exec())