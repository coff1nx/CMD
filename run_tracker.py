import json
import os

class RunTracker:
    def __init__(self, path="storage/runs.json"):
        self.path = path
        # Строгий список игнорирования из ТЗ
        self.ignore_list = ['pip', 'git', 'dir', 'cls', 'help', 'type', 'copy']

    def should_save(self, command: str) -> bool:
        cmd_lower = command.lower().strip()
        if not cmd_lower:
            return False
            
        # Проверка на системные команды (начало строки)
        if any(cmd_lower.startswith(sys_cmd) for sys_cmd in self.ignore_list):
            return False

        # Условия сохранения из ТЗ
        is_python_file = ".py" in cmd_lower
        is_python_call = "python" in cmd_lower
        is_venv_call = "venv\\scripts\\python.exe" in cmd_lower

        return is_python_file or is_python_call or is_venv_call

    def save_run(self, command: str, work_dir: str):
        if not self.should_save(command):
            return

        # ИСПРАВЛЕНО: теперь вызываем load_runs() вместо load_all()
        data = self.load_runs() 
        
        # Сохраняем как объект, чтобы избежать дублей по паре Команда+Путь
        entry = {"command": command, "path": work_dir}
        
        if entry not in data:
            data.append(entry)
            # Гарантируем наличие папки storage
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

    def load_runs(self):
        if not os.path.exists(self.path): 
            return []
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: 
            return []

    def delete_run(self, command: str, work_dir: str):
        data = self.load_runs()
        # Оставляем только те записи, которые НЕ совпадают с удаляемой
        new_data = [item for item in data if not (item['command'] == command and item['path'] == work_dir)]
        
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, indent=4, ensure_ascii=False)        