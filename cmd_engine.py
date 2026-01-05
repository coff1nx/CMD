import subprocess
import threading
import os
from PySide6.QtCore import QObject, Signal

class CMDEngine(QObject):
    output_received = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.process = None
        self._start_new_session()

    def _start_new_session(self):
        """Запуск свежего процесса CMD (БЕЗ рекурсии)"""
        # Если процесс уже запущен и живой — ничего не делаем
        if self.process and self.process.poll() is None:
            return

        self.process = subprocess.Popen(
            ['cmd.exe', '/Q', '/K', 'chcp 65001 > nul && @echo off'], 
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        threading.Thread(target=self._read_stream, args=(self.process.stdout, "normal"), daemon=True).start()
        threading.Thread(target=self._read_stream, args=(self.process.stderr, "error"), daemon=True).start()

    def _read_stream(self, stream, out_type):
        try:
            for line in iter(stream.readline, ''):
                if line:
                    self.output_received.emit(line, out_type)
                if not self.process or self.process.poll() is not None:
                    break
        except:
            pass

    def execute(self, command: str):
        # Если процесса нет или он умер - создаем новый перед выполнением
        if self.process is None or self.process.poll() is not None:
            self._start_new_session()
            
        try:
            self.process.stdin.write(command + '\n')
            self.process.stdin.flush()
        except Exception as e:
            print(f"Ошибка записи в поток: {e}")

    def stop_process(self):
        """Только убивает, ничего не запуская"""
        if self.process:
            try:
                import subprocess
                # Убиваем дерево процессов (CMD + запущенный Python)
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.process.pid)], 
                             capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            except:
                pass
            self.process = None