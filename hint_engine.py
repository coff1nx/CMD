import re

class HintEngine:
    def __init__(self):
        self.patterns = {
            r"ModuleNotFoundError": "Подсказка: Отсутствует библиотека. Используйте pip install.",
            r"SyntaxError": "Подсказка: Ошибка в синтаксисе. Проверьте скобки или двоеточия.",
            r"IndentationError": "Подсказка: Проблема с отступами (Tab/Space).",
            r"NameError": "Подсказка: Использование необъявленной переменной."
        }

    def get_hint(self, text: str):
        """Имя метода теперь совпадает с вызовом в main.py"""
        for pattern, hint in self.patterns.items():
            if re.search(pattern, text):
                return hint
        return None